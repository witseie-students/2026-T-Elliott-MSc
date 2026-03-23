# 014_upper_bound_generator_and_classifier.py
# ════════════════════════════════════════════════════════════════════════════
"""
Two-agent baseline for PubMed-QA:

1. **Generator** – sees the structured abstract (+ MESH) and produces a
   free-text answer to the yes/no/maybe question.

2. **Classifier** – sees the *question* plus the generator’s *answer* and
   converts that answer to JSON: {"decision": "yes" | "no" | "maybe"}.

Accuracy is measured against PubMed-QA gold labels.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import List, Dict

import pandas as pd
from pydantic import BaseModel, Field, ValidationError

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from openai import OpenAI
from django.conf import settings

# ── configuration ───────────────────────────────────────────────────────────
ROOT_DIR  = Path(settings.BASE_DIR).parent
DATA_CSV  = ROOT_DIR / "data/PUBMEDQA/PUBMED_QA2.csv"

OPENAI_API_KEY = settings.OPENAI_API_KEY
MODEL_GEN      = "gpt-4.1-nano"   # generator
MODEL_CLS      = "gpt-4.1-nano"   # classifier
client = OpenAI(api_key=OPENAI_API_KEY)

LABEL_SET = {"yes", "no", "maybe"}

# ── pydantic schema ─────────────────────────────────────────────────────────
class DecisionOutput(BaseModel):
    decision: str = Field(..., description="'yes', 'no', or 'maybe'")

    @classmethod
    def validate(cls, value):  # type: ignore[override]
        obj = super().validate(value)  # type: ignore[arg-type]
        if obj.decision not in LABEL_SET:
            raise ValueError("decision must be yes/no/maybe")
        return obj

# ── context formatter (identical logic as before) ───────────────────────────
def _format_context(raw: str) -> str:
    try:
        ctx_start = raw.index("'contexts': [") + len("'contexts': [")
        ctx_end   = raw.index("]", ctx_start)
        ctx_block = raw[ctx_start:ctx_end]
    except ValueError:
        return raw.strip()

    # labels
    labels: List[str] = []
    try:
        labels_start = raw.index("'labels': [", ctx_end) + len("'labels': [")
        labels_end   = raw.index("]", labels_start)
        labels_block = raw[labels_start:labels_end]
        labels = [tok.strip(" '\"") for tok in labels_block.split(",") if tok.strip()]
    except ValueError:
        labels = []

    # meshes
    meshes: List[str] = []
    try:
        meshes_start = raw.index("'meshes': [") + len("'meshes': [")
        meshes_end   = raw.index("]", meshes_start)
        meshes_block = raw[meshes_start:meshes_end]
        meshes = [tok.strip(" '\"") for tok in meshes_block.split(",") if tok.strip()]
    except ValueError:
        meshes = []

    # split on sentinel '.,'
    positions: List[int] = []
    search_from = 0
    while True:
        idx = ctx_block.find(".,", search_from)
        if idx == -1:
            break
        positions.append(idx)
        search_from = idx + 2

    if labels and len(positions) >= len(labels) - 1 and len(labels) > 0:
        prev = 0
        sections = []
        for i in range(len(labels) - 1):
            pos = positions[i]
            sections.append(ctx_block[prev : pos + 1].strip(" \n,"))
            prev = pos + 2
        sections.append(ctx_block[prev:].strip(" \n,"))
    else:
        sections = [p.strip(" \n,") for p in ctx_block.split(".,") if p.strip()]

    if not labels:
        labels = [f"SECTION_{i+1}" for i in range(len(sections))]
    elif len(labels) < len(sections):
        labels += [f"SECTION_{i+1}" for i in range(len(labels), len(sections))]

    lines = [f"{lab}: {sec}" for lab, sec in zip(labels, sections)]
    if meshes:
        lines.append("MESH: " + ", ".join(meshes))
    return "\n".join(lines)

# ── LLM helpers ────────────────────────────────────────────────────────────
def _generate_answer(question: str, ctx: str) -> str:
    """Generator agent: produce free-text answer using only the context."""
    resp = client.chat.completions.create(
        model=MODEL_GEN,
        temperature=0.0,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an expert assistant. Using ONLY the provided context, "
                    "write a concise, evidence-based answer to the user's question. "
                    "Do not add information that is not present in the context."
                ),
            },
            {
                "role": "user",
                "content": f"Question:\n{question}\n\nContext:\n{ctx}\n\nAnswer:",
            },
        ],
    )
    return resp.choices[0].message.content.strip()

def _classify_answer(question: str, long_answer: str) -> str:
    """Classifier agent with the standardised prompt."""
    sys_prompt = (
        "Return ONLY a JSON object {'decision': 'yes'|'no'|'maybe'} indicating "
        "whether the answer implies YES, NO, or MAYBE to the question."
    )
    user_json = json.dumps(
        {"question": question, "answer": long_answer},
        indent=2,
    )
    resp = client.chat.completions.create(
        model=MODEL_CLS,
        temperature=0.0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "user",   "content": user_json},
        ],
    )
    try:
        return DecisionOutput.model_validate_json(
            resp.choices[0].message.content
        ).decision
    except ValidationError:
        return "maybe"

def _predict(question: str, ctx: str) -> str:
    long_answer = _generate_answer(question, ctx)
    return _classify_answer(question, long_answer)

# ── management command ─────────────────────────────────────────────────────
class Command(BaseCommand):
    help = (
        "Two-agent (generator + classifier) baseline with section-labelled "
        "context; prints the first full example."
    )

    def handle(self, *args, **opts):
        try:
            from tqdm import tqdm
            use_tqdm = True
        except ImportError:
            use_tqdm = False

        if not DATA_CSV.exists():
            raise CommandError(f"Missing file: {DATA_CSV}")

        with DATA_CSV.open(newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))

        iterator = tqdm(rows, total=len(rows), unit="qns") if use_tqdm else rows
        records: List[Dict[str, str]] = []

        for idx, r in enumerate(iterator, 1):
            q        = r.get("question", "").strip()
            raw_ctx  = r.get("context", "").strip()
            gold     = r.get("final_decision", "").strip().lower()

            if not q or not raw_ctx or gold not in LABEL_SET:
                continue

            formatted_ctx = _format_context(raw_ctx)
            pred          = _predict(q, formatted_ctx)

            if idx == 1:
                self.stdout.write("\n===== FIRST EXAMPLE =====")
                self.stdout.write(f"PubMed ID: {r.get('pubid', '').strip()}")
                self.stdout.write(f"Question:\n{q}\n")
                self.stdout.write("Context (formatted):\n" + formatted_ctx + "\n")
                self.stdout.write(f"Model decision: {pred} | Truth: {gold}")
                self.stdout.write("===== END EXAMPLE =====\n")

            records.append(
                {
                    "pubmed_id": r.get('pubid', '').strip(),
                    "predicted": pred,
                    "actual":    gold,
                }
            )

        if use_tqdm:
            iterator.close()

        # ── metrics & save ------------------------------------------------
        df  = pd.DataFrame(records)
        acc = (df["predicted"] == df["actual"]).mean()
        cm  = pd.crosstab(
            df["actual"],
            df["predicted"],
            rownames=["Actual"],
            colnames=["Predicted"],
            margins=True,
        )

        print(f"Accuracy: {acc:.2%}\n")
        print(cm)

        out_dir = ROOT_DIR / "results/01_graphrag/02_upper_bound"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_csv = out_dir / "00_pubmedqa_two_agent_results.csv"
        df.to_csv(out_csv, index=False)
        self.stdout.write(self.style.SUCCESS(f"✅  Saved → {out_csv}"))