# ════════════════════════════════════════════════════════════
"""Iterative Graph-RAG over the first 5 PubMed-QA rows.

For every question:
• Chroma neighbour search  → QID frontier
• Graph traversal          → evidence bucket
• Evidence bucket          → long answer
• Long answer              → yes / no / maybe
• Compare with gold label, accumulate accuracy

Timings for each stage are captured so you can pinpoint slow spots.
CSV is saved to  results/01_graphrag/03_ordinary_graphrag/ordinary_graphrag_qa_outcome.csv
"""

from __future__ import annotations

import csv
import time
from pathlib import Path
from typing import Any, Dict, List, Set

import numpy as np
import pandas as pd
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from graphrag.graph_traversal.main import run_retriever
from graphrag.graph_traversal.aggregate_answer import generate_answer
from knowledge_graph_generator.chroma_db.client import question_collection
from knowledge_graph_generator.chroma_db.embedding import get_embedding

# ── configuration ────────────────────────────────────────────
ROOT_DIR  = Path(settings.BASE_DIR).parent
DATA_CSV  = ROOT_DIR / "data/PUBMEDQA/PUBMED_QA2.csv"
OUT_DIR   = ROOT_DIR / "results/01_graphrag/03_ordinary_graphrag"
OUT_DIR.mkdir(parents=True, exist_ok=True)
CSV_PATH  = OUT_DIR / "ordinary_graphrag_qa_outcome.csv"

FETCH_K     = 40
THRESHOLD   = 0.60
MAX_ROWS    = 1           # evaluate only the first N rows

# ── helpers ─────────────────────────────────────────────────
def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

def _dedup_preserve(seq: List[str]) -> List[str]:
    out, seen = [], set()
    for x in seq:
        if x not in seen:
            out.append(x)
            seen.add(x)
    return out

# ── command ─────────────────────────────────────────────────
class Command(BaseCommand):
    help = "Run Graph-RAG + aggregation on the first N PubMed-QA rows "\
           "with per-stage timing and progress-bar."

    def handle(self, *args, **opts):
        # initial checks ---------------------------------------------------
        if not DATA_CSV.exists():
            raise CommandError(f"Missing file: {DATA_CSV}")
        if question_collection.count() == 0:
            raise CommandError("Chroma `question_collection` is empty – ingest first.")

        # optional tqdm ----------------------------------------------------
        try:
            from tqdm import tqdm  # type: ignore
            use_tqdm = True
        except ImportError:
            use_tqdm = False

        # load first MAX_ROWS rows ----------------------------------------
        with DATA_CSV.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            rows = [row for _, row in zip(range(MAX_ROWS), reader)]

        iterator = tqdm(rows, total=len(rows), unit="qns") if use_tqdm else rows

        # aggregation containers ------------------------------------------
        results: List[Dict[str, Any]] = []
        correct = 0
        # timing accumulators (seconds)
        t_embed, t_traverse, t_aggregate = 0.0, 0.0, 0.0

        for idx, row in enumerate(iterator, 1):
            q_timer0 = time.perf_counter()

            question   = row.get("question", "").strip()
            gold_label = row.get("final_decision", "").strip().lower()
            if not question or gold_label not in {"yes", "no", "maybe"}:
                continue

            # —— Stage 1 : neighbour search ------------------------------
            t0 = time.perf_counter()
            q_vec = np.asarray(get_embedding(question))
            res = question_collection.query(
                query_embeddings=[q_vec.tolist()],
                n_results=FETCH_K,
                include=["metadatas", "embeddings"],
            )
            neighbour_qids: List[str] = []
            for meta, emb in zip(res["metadatas"][0], res["embeddings"][0]):
                if _cosine(q_vec, np.asarray(emb)) >= THRESHOLD:
                    neighbour_qids.append(meta.get("quadruple_id"))
            neighbour_qids = _dedup_preserve(neighbour_qids)
            t_embed_step = time.perf_counter() - t0
            t_embed += t_embed_step
            if not neighbour_qids:   # no frontier → skip
                continue

            # —— Stage 2 : graph traversal -------------------------------
            t1 = time.perf_counter()
            seen_global: Set[str] = set()
            collection_global: List[Dict[str, Any]] = []
            pending = neighbour_qids.copy()

            while pending:
                seed_qid = pending.pop(0)
                if seed_qid in seen_global:
                    continue
                ret = run_retriever(
                    seed_qid,
                    question,
                    initial_seen=seen_global,
                )
                seen_global.update(ret["seen_qids"])
                collection_global.extend(ret["collection_bucket"])
                pending = [q for q in pending if q not in seen_global]

            t_traverse_step = time.perf_counter() - t1
            t_traverse += t_traverse_step

            # —— Stage 3 : aggregation + classification ------------------
            t2 = time.perf_counter()
            long_ans, decision = generate_answer(question, collection_global)
            t_aggregate_step = time.perf_counter() - t2
            t_aggregate += t_aggregate_step

            is_correct = decision == gold_label
            correct += int(is_correct)

            # store per-question record -----------------------------------
            results.append(
                {
                    "pubmed_id":   row.get("pubid", "").strip(),
                    "question":    question,
                    "long_answer": long_ans,
                    "prediction":  decision,
                    "gold_label":  gold_label,
                    "is_correct":  is_correct,
                    "t_embed":     round(t_embed_step, 2),
                    "t_traverse":  round(t_traverse_step, 2),
                    "t_aggregate": round(t_aggregate_step, 2),
                    "t_total":     round(time.perf_counter() - q_timer0, 2),
                }
            )

            # concise live print (tqdm.write keeps bar intact) ------------
            msg = f"Q{idx} | gold:{gold_label} pred:{decision} | "\
                  f"t={results[-1]['t_total']}s"
            if use_tqdm:
                iterator.write(msg)
            else:
                self.stdout.write(msg)

        if use_tqdm:
            iterator.close()

        # —— save CSV -----------------------------------------------------
        pd.DataFrame(results).to_csv(CSV_PATH, index=False)

        # —— accuracy + timing summary -----------------------------------
        acc = correct / len(results) if results else 0.0
        mean_e = t_embed / len(results) if results else 0.0
        mean_t = t_traverse / len(results) if results else 0.0
        mean_a = t_aggregate / len(results) if results else 0.0

        self.stdout.write(
            self.style.SUCCESS(
                f"\n✅  Saved → {CSV_PATH}\n"
                f"Accuracy on {len(results)} rows : {acc:.0%} "
                f"({correct}/{len(results)})\n"
                f"Avg time per question  |  embed: {mean_e:.2f}s   "
                f"traverse: {mean_t:.2f}s   aggregate: {mean_a:.2f}s\n"
            )
        )