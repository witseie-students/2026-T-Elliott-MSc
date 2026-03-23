# 011_ordinary_RAG.py
# ════════════════════════════════════════════════════════════════════════════
"""Ordinary RAG pipeline – full CSV processing.

For **every** row in `PUBMED_QA2.csv` the command now:
    1. Retrieves context sentences (cos ≥ 0.60).
    2. Generates a free‑text answer using ONLY that context.
    3. Classifies the answer as **yes / no / maybe**.
    4. Collects results into a DataFrame and saves to
       `results/01_graphrag/01_ordinary_rag/ordinary_rag_qa_outcome.csv`.

The console shows streaming progress every 50 rows plus a summary table for the
first few as a sanity check.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import List, Tuple

import numpy as np
import pandas as pd
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError

from knowledge_graph_generator.chroma_db.client import question_collection
from knowledge_graph_generator.chroma_db.embedding import get_embedding
from knowledge_graph_generator.models import StagedQuadruple
from django.conf import settings

# ── configuration ───────────────────────────────────────────────────────────
ROOT_DIR = Path(settings.BASE_DIR).parent
DATA_CSV = ROOT_DIR / "data/PUBMEDQA/PUBMED_QA2.csv"

FETCH_K   = 200
THRESHOLD = 0.60

OPENAI_API_KEY = settings.OPENAI_API_KEY
MODEL_NAME     = "gpt-4.1-nano"
client = OpenAI(api_key=OPENAI_API_KEY)

# ── helpers ────────────────────────────────────────────────────────────────

def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def _is_inferred(point_id: str | None, meta: dict | None) -> bool:
    if isinstance(meta, dict) and "inferred" in meta:
        return bool(meta["inferred"])
    if isinstance(point_id, str):
        return point_id.startswith("i-")
    return False

# ----------  stage 1  – generate answer ----------

def _answer_question(question: str, sentences: List[str]) -> str:
    ctx = "\n".join(f"- {s}" for s in sentences)
    prompt = (
        "You are a biomedical Q&A assistant. Answer the question below using "
        "the provided information as your only source of knowledge to do so. "
        "Use none of your own knowledge and only the knowledge within the "
        "context. Your answer should start with yes, no or maybe and then "
        "provide context as justification.\n\n"
        f"Question:\n{question}\n\nContext:\n{ctx}"
    )
    resp = client.chat.completions.create(
        temperature=0.0,
        model=MODEL_NAME,
        messages=[
            {"role": "system", "content": "Answer concisely and accurately."},
            {"role": "user", "content": prompt},
        ],
    )
    return resp.choices[0].message.content.strip()

# ----------  stage 2  – yes / no / maybe ----------

class DecisionOutput(BaseModel):
    decision: str = Field(..., description="'yes', 'no', or 'maybe'")

    @classmethod
    def validate(cls, value):  # type: ignore[override]
        obj = super().validate(value)  # type: ignore[arg-type]
        if obj.decision not in {"yes", "no", "maybe"}:
            raise ValueError("decision must be 'yes', 'no', or 'maybe'")
        return obj


def _classify_answer(question: str, answer: str) -> str:
    prompt = (
        "Return ONLY a JSON object {'decision': 'yes'|'no'|'maybe'} indicating "
        "whether the answer implies YES, NO, or MAYBE to the question."
    )
    user_block = f"Question:\n{question}\n\nAnswer:\n{answer}"
    resp = client.chat.completions.create(
        model=MODEL_NAME,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": user_block},
        ],
    )
    try:
        parsed = DecisionOutput.model_validate_json(resp.choices[0].message.content)
        return parsed.decision
    except ValidationError:
        return "maybe"


        

# ----------  retrieval helper ----------

def _retrieve_context(question: str) -> List[str]:
    q_vec = np.asarray(get_embedding(question))
    res = question_collection.query(
        query_embeddings=[q_vec.tolist()],
        n_results=FETCH_K,
        include=["documents", "embeddings", "metadatas"],
    )
    ids   = res["ids"][0]
    embs  = res["embeddings"][0]
    metas = res.get("metadatas", [[]])[0]

    scored: List[Tuple[float, str]] = []
    for pid, emb, meta in zip(ids, embs, metas):
        if not meta or "quadruple_id" not in meta:
            continue
        sim = _cosine(q_vec, np.asarray(emb))
        if sim < THRESHOLD:
            continue
        quad_id = meta["quadruple_id"]
        inferred = _is_inferred(pid, meta)
        stq = StagedQuadruple.objects.filter(quadruple_id=quad_id).first()
        if not stq:
            continue
        sentence = (
            stq.natural_language_sentence if inferred else stq.coreference_sentence
        )
        if sentence:
            scored.append((sim, sentence.strip()))

    if not scored:
        return []

    # sort + deduplicate
    scored.sort(key=lambda t: t[0], reverse=True)
    seen: set[str] = set()
    context: List[str] = []
    for _sim, sent in scored:
        key = sent.lower()
        if key not in seen:
            seen.add(key)
            context.append(sent)
    return context

# ── management command ─────────────────────────────────────────────────────
class Command(BaseCommand):
    help = (
        "Process PubMed-QA questions, save results CSV, show progress bar, and "
        "report accuracy + confusion matrix (yes/no/maybe)."
    )

    def handle(self, *args, **opts):
        from time import time
        try:
            from tqdm import tqdm  # optional
            use_tqdm = True
        except ImportError:
            use_tqdm = False

        if not DATA_CSV.exists():
            raise CommandError(f"Missing file: {DATA_CSV}")
        if question_collection.count() == 0:
            raise CommandError("Chroma questions collection is empty – ingest first.")

        # load CSV rows
        with DATA_CSV.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            rows = list(reader)
        total = len(rows)
        self.stdout.write(self.style.NOTICE(f"🔄  Processing {total:,} questions…"))

        iterator = tqdm(rows, total=total, unit="qns") if use_tqdm else rows
        start_ts = time()
        results: List[dict] = []

        for idx, row in enumerate(iterator, 1):
            question = row.get("question", "").strip()
            if not question:
                continue

            # 1) retrieve context
            context_sentences = _retrieve_context(question)

            # 2) generate answer
            answer = _answer_question(question, context_sentences) if context_sentences else "Insufficient information."

            # 3) classify answer
            decision = _classify_answer(question, answer)

            results.append(
                {
                    "pubmed_id": row.get("pubid", "").strip(),
                    "question": question,
                    "answer": answer,
                    "final_result": decision,
                    "actual_result": row.get("final_decision", "").strip().lower(),
                    "actual_answer": row.get("long_answer", "").strip(),
                }
            )

            if not use_tqdm and idx % 50 == 0:
                elapsed = time() - start_ts
                avg_per_q = elapsed / idx
                eta = avg_per_q * (total - idx)
                self.stdout.write(
                    f"• processed {idx}/{total}  |  elapsed {elapsed/60:.1f} min  |  ETA {eta/60:.1f} min",
                    ending="\r",
                )

        if use_tqdm:
            iterator.close()

        # build DataFrame and save CSV
        df = pd.DataFrame(results)
        out_dir = ROOT_DIR / "results/01_graphrag/01_ordinary_rag"
        out_dir.mkdir(parents=True, exist_ok=True)
        csv_path = out_dir / "ordinary_rag_qa_outcome.csv"
        df.to_csv(csv_path, index=False)

        # accuracy & confusion matrix
        accuracy = (df["final_result"] == df["actual_result"]).mean()
        cm = pd.crosstab(df["actual_result"], df["final_result"], rownames=["Actual"], colnames=["Predicted"], margins=True)

        print("\n===== SAMPLE OUTPUT (first 5 rows) =====")
        print(df.head().to_string(index=False, max_colwidth=80))
        print("===== END SAMPLE =====\n")

        print("Accuracy: {:.2%}".format(accuracy))
        print("\nConfusion Matrix (counts):")
        print(cm)

        self.stdout.write(self.style.SUCCESS(f"✅  All done. Results saved → {csv_path}"))