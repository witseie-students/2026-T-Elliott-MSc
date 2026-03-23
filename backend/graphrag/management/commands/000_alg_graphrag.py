# backend/graphrag/management/commands/016_alg_graphrag.py
# ════════════════════════════════════════════════════════════
"""
ALG-GraphRAG – depth-sweep experiment
-------------------------------------

For each requested hop-depth D (default 2‥7) and each of the first N rows
(default 1):

    1. Chroma neighbours  (sim ≥ 0.60)
    2. Iterated sub-graphs (depth D, duplicate-QID filtering)
    3. LLM aggregation  → paragraph
    4. LLM classification → yes / no / maybe
    5. Save per-question results to
         results/01_graphrag/04_alg_graphrag/alg_graphrag_d{D}_qa_outcome.csv
"""

from __future__ import annotations

import csv, time
from pathlib import Path
from typing import Any, Dict, List, Set, Sequence

import numpy as np
import pandas as pd
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from graphrag.graph_algorithm.knowledge_graph_functions import (
    fetch_subgraph,
    render_outline_3A,
)
from graphrag.graph_algorithm.llm_answer import generate_answer
from knowledge_graph_generator.chroma_db.client import question_collection
from knowledge_graph_generator.chroma_db.embedding import get_embedding

# ── static configuration ───────────────────────────────────────────
ROOT_DIR   = Path(settings.BASE_DIR).parent
DATA_CSV   = ROOT_DIR / "data/PUBMEDQA/PUBMED_QA2.csv"

OUT_DIR    = ROOT_DIR / "results/01_graphrag/04_alg_graphrag"
OUT_DIR.mkdir(parents=True, exist_ok=True)

FETCH_K    = 40
THRESHOLD  = 0.60
MAX_ROWS   = 350     # default no. CSV rows if not overridden

# ── helpers ---------------------------------------------------------
def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

def _truncate(txt: str, w: int) -> str:
    return txt if len(txt) <= w else txt[: w - 1] + "…"

# ────────────────────────────────────────────────────────────────────
class Command(BaseCommand):
    help = "Run ALG-GraphRAG for a sweep of graph depths and save a CSV per depth."

    def add_arguments(self, parser):
        parser.add_argument("--rows",  type=int, default=MAX_ROWS,
                            help=f"Number of CSV rows to process (default {MAX_ROWS}).")
        parser.add_argument("--start_depth", type=int, default=1,
                            help="Starting hop-depth (inclusive).")
        parser.add_argument("--end_depth",   type=int, default=7,
                            help="Ending hop-depth (inclusive).")

    # ────────────────────────────────────────────────────────────
    def handle(self, *args, **opts):
        n_rows       : int = opts["rows"]
        start_depth  : int = opts["start_depth"]
        end_depth    : int = opts["end_depth"]
        depths: Sequence[int] = range(start_depth, end_depth + 1)

        # quick sanity checks
        if not DATA_CSV.exists():
            raise CommandError(f"Missing CSV: {DATA_CSV}")
        if question_collection.count() == 0:
            raise CommandError("Chroma `question_collection` is empty – ingest first.")
        if start_depth < 1 or end_depth < start_depth:
            raise CommandError("Depth parameters invalid (must satisfy 1 ≤ start ≤ end).")

        # load subset of CSV rows once
        with DATA_CSV.open(newline="", encoding="utf-8") as fh:
            rows = [row for _, row in zip(range(n_rows), csv.DictReader(fh))]
        if not rows:
            self.stdout.write(self.style.WARNING("No rows loaded – nothing to do."))
            return

        # =========================================================
        for depth in depths:
            self.stdout.write(self.style.NOTICE(f"\n=== DEPTH {depth} ==="))

            results: List[Dict[str, Any]] = []
            acc_good = 0
            t_embed_acc = t_graph_acc = t_llm_acc = 0.0

            for idx, row in enumerate(rows, 1):
                start_total = time.perf_counter()

                question   = row["question"].strip()
                pubmed_id  = row["pubid"].strip()
                gold       = row["final_decision"].strip().lower()

                if not question:
                    continue

                # 1) embed + neighbour search ---------------------------
                t0 = time.perf_counter()
                q_vec = np.asarray(get_embedding(question))
                res = question_collection.query(
                    query_embeddings=[q_vec.tolist()],
                    n_results=FETCH_K,
                    include=["documents", "embeddings", "metadatas"],
                )
                t_embed = time.perf_counter() - t0
                t_embed_acc += t_embed

                neighbours = []
                for pid, doc, emb, meta in zip(
                    res["ids"][0], res["documents"][0],
                    res["embeddings"][0], res["metadatas"][0]
                ):
                    sim = _cosine(q_vec, np.asarray(emb))
                    if sim >= THRESHOLD:
                        neighbours.append(
                            {"qid":  meta.get("quadruple_id", pid),
                             "sim":  float(sim),
                             "doc":  doc}
                        )
                neighbours.sort(key=lambda d: d["sim"], reverse=True)

                # 2) iterated sub-graphs -------------------------------
                t1 = time.perf_counter()
                outlines: List[str] = []
                seen: Set[str] = set()
                for n in neighbours:
                    qid = n["qid"]
                    if qid in seen:
                        continue
                    edges, seen_local = fetch_subgraph(qid, depth=depth)
                    seen.update(seen_local)
                    outlines.append(render_outline_3A(edges, seed_qid=qid))
                t_graph = time.perf_counter() - t1
                t_graph_acc += t_graph

                if not outlines:
                    continue

                # 3) LLM aggregation + decision ------------------------
                t2 = time.perf_counter()
                paragraph, decision = generate_answer(question, "\n\n".join(outlines))
                t_llm = time.perf_counter() - t2
                t_llm_acc += t_llm

                is_correct = decision == gold
                acc_good  += int(is_correct)

                results.append(
                    {
                        "pubmed_id":  pubmed_id,
                        "question":   question,
                        "paragraph":  paragraph,
                        "prediction": decision,
                        "gold_label": gold,
                        "is_correct": is_correct,
                        "t_embed":    round(t_embed,  2),
                        "t_graph":    round(t_graph,  2),
                        "t_llm":      round(t_llm,    2),
                        "t_total":    round(time.perf_counter() - start_total, 2),
                    }
                )

            # ---- save CSV for this depth -----------------------------
            csv_out = OUT_DIR / f"alg_graphrag_d{depth}_qa_outcome.csv"
            pd.DataFrame(results).to_csv(csv_out, index=False)

            # ---- summary per depth -----------------------------------
            if results:
                n = len(results)
                acc = acc_good / n
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Depth {depth} → saved {n} rows → {csv_out.name}  |  "
                        f"Accuracy {acc:.0%} ({acc_good}/{n})"
                    )
                )
            else:
                self.stdout.write(self.style.WARNING(f"Depth {depth} produced no results."))