# 027_pubmedqa_question_cosines.py
# ────────────────────────────────────────────────────────────────────────────
# For every PubMed-QA row:
#   1. embed the question
#   2. pull FETCH_K nearest neighbours from Chroma
#   3. recompute cosine similarities locally
#   4. keep the best TOP_K
#   5. append to CSV
#        pubid , question , answer , rank , cosine_similarity
#
# Output:  results/01_graphrag/00_retriever/question_cosines.csv
# ────────────────────────────────────────────────────────────────────────────

from __future__ import annotations
import csv
from pathlib import Path
from typing import List

import numpy as np
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from knowledge_graph_generator.chroma_db.client import question_collection
from knowledge_graph_generator.chroma_db.embedding import get_embedding

# ── paths & constants ───────────────────────────────────────────────────────
ROOT_DIR  = Path(settings.BASE_DIR).parent
DATA_CSV  = ROOT_DIR / "data/PUBMEDQA/PUBMED_QA2.csv"
OUT_DIR   = ROOT_DIR / "results/01_graphrag/00_retriever"
OUT_CSV   = OUT_DIR / "question_cosines.csv"

FETCH_K   = 100          # pull this many from Chroma for safety
TOP_K     = 20           # keep best TOP_K after re-ranking


# ── helper ------------------------------------------------------------------
def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    """Classic cosine similarity for two numpy vectors."""
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


# ── management command ------------------------------------------------------
class Command(BaseCommand):
    help = (
        f"Embed every PubMed-QA question, compute its TOP-{TOP_K} nearest "
        f"neighbours, and save a CSV with columns:\n"
        "   pubid , question , answer , rank , cosine_similarity"
    )

    def handle(self, *args, **opts):
        # ── sanity checks --------------------------------------------------
        if not DATA_CSV.exists():
            raise CommandError(f"Missing file: {DATA_CSV}")
        if question_collection.count() == 0:
            raise CommandError("Chroma question_collection is empty.")

        total_rows = sum(1 for _ in open(DATA_CSV, encoding="utf-8")) - 1
        self.stdout.write(
            self.style.NOTICE(
                f"🔍  Processing {total_rows:,} PubMed-QA questions "
                f"(keeping TOP-{TOP_K} from {FETCH_K} fetched)…"
            )
        )

        # ── output CSV -----------------------------------------------------
        OUT_DIR.mkdir(parents=True, exist_ok=True)
        with OUT_CSV.open("w", newline="", encoding="utf-8") as fh_out:
            writer = csv.writer(fh_out)
            writer.writerow(
                ["pubid", "question", "answer", "rank", "cosine_similarity"]
            )

            # ── iterate PubMed-QA -----------------------------------------
            with DATA_CSV.open(newline="", encoding="utf-8") as fh_in:
                reader = csv.DictReader(fh_in)

                for idx, row in enumerate(reader, 1):
                    pubid   = row.get("pubid", "").strip()
                    q_text  = row.get("question", "").strip()
                    answer  = row.get("final_decision", "").strip().lower()  # yes / no / maybe

                    if not q_text:
                        continue

                    # 1) embed query
                    q_vec = np.asarray(get_embedding(q_text))

                    # 2) query Chroma
                    res = question_collection.query(
                        query_embeddings=[q_vec.tolist()],
                        n_results=FETCH_K,
                        include=["embeddings"],
                    )
                    vecs: List[List[float]] = res["embeddings"][0]

                    # 3) local cosine similarities
                    sims = [_cosine(q_vec, np.asarray(v)) for v in vecs]

                    # 4) keep TOP_K
                    for rank, sim in enumerate(sorted(sims, reverse=True)[:TOP_K], 1):
                        writer.writerow([pubid, q_text, answer, rank, f"{sim:.6f}"])

                    # 5) console progress every 200
                    if idx % 200 == 0 or idx == total_rows:
                        self.stdout.write(f"• processed {idx}/{total_rows}", ending="\r")

        self.stdout.write(self.style.SUCCESS(f"\n✅  Saved all results → {OUT_CSV}"))