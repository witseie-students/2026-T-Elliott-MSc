#!/usr/bin/env python
# backend/graphrag/management/commands/022_baseline_null_hypothesis.py
# ═══════════════════════════════════════════════════════════════════
"""
Baseline with *null-hypothesis* augmentation.

Per PubMed-QA row
-----------------
1. Rewrite the original biomedical question so it tests the NULL
   hypothesis (i.e. the opposite relation).
2. Run the *generator* **twice** (original-Q & null-Q).
3. Feed the **concatenated** answers to the *classifier*.
4. Report yes / no / maybe.

Generator & classifier prompts are **identical** to the original
two-agent baseline — only the null-hypothesis step is new.

Edit the single constant `N_ROWS` below to change row count.
Results →  results/01_graphrag/09_baseline_null/tot_baseline_null_d1.csv
"""
from __future__ import annotations

import csv, json
from pathlib import Path
from typing import Dict, List

import pandas as pd
from pydantic import BaseModel, Field, ValidationError
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from openai import OpenAI

# ──────────────────────────────────────────────────────────────
#  Hard-coded row count – tweak here
# ──────────────────────────────────────────────────────────────
N_ROWS = 350            # ← number of PubMed-QA rows to process

# ──────────────────────────────────────────────────────────────
#  Paths
# ──────────────────────────────────────────────────────────────
ROOT_DIR  = Path(settings.BASE_DIR).parent
DATA_CSV  = ROOT_DIR / "data/PUBMEDQA/PUBMED_QA2.csv"
OUT_DIR   = ROOT_DIR / "results/01_graphrag/09_baseline_null"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ──────────────────────────────────────────────────────────────
#  OpenAI client
# ──────────────────────────────────────────────────────────────
OPENAI_API_KEY = "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"
MODEL_GEN      = "gpt-4.1-nano"     # generator
MODEL_CLS      = "gpt-4.1-nano"     # classifier
_client        = OpenAI(api_key=OPENAI_API_KEY)

# ──────────────────────────────────────────────────────────────
#  Decision schema + helper copied verbatim from baseline 014
# ──────────────────────────────────────────────────────────────
LABEL_SET = {"yes", "no", "maybe"}


class DecisionOutput(BaseModel):
    decision: str = Field(..., description="'yes', 'no', or 'maybe'")

    @classmethod
    def validate(cls, value):  # type: ignore[override]
        obj = super().validate(value)  # type: ignore[arg-type]
        if obj.decision not in LABEL_SET:
            raise ValueError("decision must be yes/no/maybe")
        return obj


def _format_context(raw: str) -> str:
    """
    Extracts the 'contexts', 'labels', 'meshes' blocks from the raw JSON-ish
    string in PubMed-QA and formats them into a readable section-labelled
    text block – identical logic to the original baseline.
    """
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

    # sentinel '.,' splits
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

# ══════════════════════════════════════════════════════════════
#  Null-hypothesis agent
# ══════════════════════════════════════════════════════════════
def _nullify_question(question: str) -> str:
    sys_prompt = (
        "Rewrite the biomedical question so it tests the NULL hypothesis – "
        "i.e. it asserts that the original relationship is **not** present.\n"
        "Keep all entities & context intact.\n\n"
        "Example:\n"
        "User question  :  Does drug X improve survival in cancer Y?\n"
        "Null-hypothesis:  Is there no improvement in survival in patients "
        "with cancer Y treated with drug X compared with controls?\n\n"
        "Only return the re-phrased question – no explanations."
    )
    resp = _client.chat.completions.create(
        model       = MODEL_GEN,
        temperature = 0.0,
        messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "user",   "content": question},
        ],
    )
    return resp.choices[0].message.content.strip()

# ══════════════════════════════════════════════════════════════
#  Generator & classifier helpers  (prompts unchanged)
# ══════════════════════════════════════════════════════════════
def _generate_answer(question: str, ctx: str) -> str:
    resp = _client.chat.completions.create(
        model       = MODEL_GEN,
        temperature = 0.0,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are an expert assistant. Using ONLY the provided "
                    "context, write a concise, evidence-based answer to the "
                    "user's question. Do not add information that is not "
                    "present in the context."
                ),
            },
            {
                "role": "user",
                "content": f"Question:\n{question}\n\nContext:\n{ctx}\n\nAnswer:",
            },
        ],
    )
    return resp.choices[0].message.content.strip()


def _classify_answer(question: str, combined_answer: str) -> str:
    sys_prompt = (
        "Return ONLY a JSON object {'decision': 'yes'|'no'|'maybe'} indicating "
        "whether the answer implies YES, NO, or MAYBE to the question."
    )
    user_json = json.dumps({"question": question, "answer": combined_answer}, indent=2)
    resp = _client.chat.completions.create(
        model       = MODEL_CLS,
        temperature = 0.0,
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

# ══════════════════════════════════════════════════════════════
#  Wrapper – generator twice + classifier
# ══════════════════════════════════════════════════════════════
def _predict(question: str, ctx: str) -> Dict[str, str]:
    answer_main = _generate_answer(question, ctx)

    null_q      = _nullify_question(question)
    answer_null = _generate_answer(null_q, ctx)

    combined    = (
        answer_main.strip()
        + "\n\n[Null-hypothesis answer]\n"
        + answer_null.strip()
    )
    label = _classify_answer(question, combined)

    return dict(
        null_question = null_q,
        answer_main   = answer_main,
        answer_null   = answer_null,
        prediction    = label,
    )

# ══════════════════════════════════════════════════════════════
#  Django management command
# ══════════════════════════════════════════════════════════════
class Command(BaseCommand):
    help = (
        "Generator + classifier baseline augmented with a null-hypothesis "
        "question.  Row count is fixed by the N_ROWS constant."
    )

    # no CLI flags – pure constant-driven run -------------------------

    def handle(self, *args, **opts):
        if N_ROWS < 1:
            raise CommandError("N_ROWS must be ≥1")
        if not DATA_CSV.exists():
            raise CommandError(f"Missing CSV: {DATA_CSV}")

        with DATA_CSV.open(newline="", encoding="utf-8") as fh:
            rows = [r for _, r in zip(range(N_ROWS), csv.DictReader(fh))]

        records: List[Dict[str, str]] = []

        for idx, r in enumerate(rows, 1):
            q_raw   = r.get("question", "").strip()
            ctx_raw = r.get("context", "").strip()
            gold    = r.get("final_decision", "").strip().lower()
            pmid    = r.get("pubid", "").strip()

            if not q_raw or not ctx_raw or gold not in LABEL_SET:
                continue

            ctx       = _format_context(ctx_raw)
            pred_dict = _predict(q_raw, ctx)

            # print first example verbosely ---------------------------
            if idx == 1:
                self.stdout.write("\n===== FIRST EXAMPLE =====")
                self.stdout.write(f"PMID      : {pmid}")
                self.stdout.write(f"Question  : {q_raw}")
                self.stdout.write(f"Null-Q    : {pred_dict['null_question']}")
                self.stdout.write("\nContext\n-------")
                self.stdout.write(ctx)
                self.stdout.write("\nAnswer (main)\n-------------")
                self.stdout.write(pred_dict["answer_main"])
                self.stdout.write("\nAnswer (null-hypothesis)\n-----------------------")
                self.stdout.write(pred_dict["answer_null"])
                self.stdout.write(
                    f"\nModel decision: {pred_dict['prediction']}   |  Gold: {gold}"
                )
                self.stdout.write("===== END EXAMPLE =====\n")

            records.append(
                dict(
                    pubmed_id     = pmid,
                    question      = q_raw,
                    null_question = pred_dict["null_question"],
                    answer_main   = pred_dict["answer_main"],
                    answer_null   = pred_dict["answer_null"],
                    prediction    = pred_dict["prediction"],
                    gold_label    = gold,
                )
            )

        # metrics -----------------------------------------------------
        df  = pd.DataFrame(records)
        acc = (df["prediction"] == df["gold_label"]).mean()
        cm  = pd.crosstab(df["gold_label"], df["prediction"],
                          rownames=["Actual"], colnames=["Predicted"], margins=True)

        print(f"\nAccuracy: {acc:.2%}\n")
        print(cm)

        # save --------------------------------------------------------
        out_csv = OUT_DIR / "tot_baseline_null_d1.csv"
        df.to_csv(out_csv, index=False)
        self.stdout.write(self.style.SUCCESS(f"\n✅  Saved → {out_csv}"))