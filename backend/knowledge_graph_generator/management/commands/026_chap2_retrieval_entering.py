# ------------------------------------------------------------------------------
# 026_chap2_retrieval_entering.py
# ------------------------------------------------------------------------------
# Retrieve the top-N closest stored questions to a fixed query, display them
# (question row + provenance-sentence row) and save the same data to a single
# CSV file called “retrieval.csv”.
# ------------------------------------------------------------------------------

from __future__ import annotations
from typing import List, Tuple
import csv
from pathlib import Path

import numpy as np
from django.conf import settings
from django.core.management.base import BaseCommand

from knowledge_graph_generator.chroma_db.client import question_collection
from knowledge_graph_generator.chroma_db.embedding import get_embedding
from knowledge_graph_generator.models import StagedQuadruple

# ── parameters --------------------------------------------------------------
QUERY = (
    "BCRABL transcript detection by quantitative real-time PCR : are correlated results possible from homebrew assays?"
)
TOP_K = 25
COL_Q = 250  # console width for question
COL_S = COL_Q
CSV_DIR = (
    Path(settings.BASE_DIR)  # “…/backend”
    .parent                  # project root
    / "results/01_graphrag/00_retriever"
)
CSV_FILE = CSV_DIR / "retrieval.csv"
# ──────────────────────────────────────────────────────────────────────────────


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def _truncate(txt: str, width: int) -> str:
    return txt if len(txt) <= width else txt[: width - 1] + "…"


class Command(BaseCommand):
    help = "Retrieve nearest questions, show provenance, and save to retrieval.csv"

    # ------------------------------------------------------------------ #
    def handle(self, *args, **opts):
        # 0) sanity check
        if question_collection.count() == 0:
            self.stdout.write(self.style.ERROR("❌  question_collection is empty."))
            return

        # 1) embed query
        q_vec = np.asarray(get_embedding(QUERY))

        # 2) nearest-neighbour search (Chroma)
        res = question_collection.query(
            query_embeddings=[q_vec.tolist()],
            n_results=max(TOP_K, 50),
            include=["documents", "embeddings", "metadatas"],
        )
        docs:  List[str]         = res["documents"][0]
        vecs:  List[List[float]] = res["embeddings"][0]
        metas: List[dict]        = res["metadatas"][0]
        sims = [_cosine(q_vec, np.asarray(v)) for v in vecs]
        ranked = sorted(zip(sims, docs, metas), key=lambda t: t[0], reverse=True)[:TOP_K]

        # 3) fetch provenance sentences
        rows: List[Tuple[int, str, str, float]] = []
        for idx, (sim, question_text, meta) in enumerate(ranked, 1):
            quad_id = meta.get("quadruple_id")
            sentence = "⚠️  provenance not found"
            if quad_id:
                stq = StagedQuadruple.objects.filter(quadruple_id=quad_id).first()
                if stq:
                    sentence = (
                        stq.natural_language_sentence
                        if stq.inferred
                        else stq.coreference_sentence
                    ) or "(sentence missing)"
            rows.append((idx, question_text, sentence, sim))

        # 4) pretty console table
        print("\n📌  Original question\n" + QUERY + "\n")

        h = "┌────┬" + "─" * (COL_Q + 2) + "┬────────┐"
        m = "├────┼" + "─" * (COL_Q + 2) + "┼────────┤"
        f = "└────┴" + "─" * (COL_Q + 2) + "┴────────┘"

        print("🏷️  Top-10 closest questions\n")
        print(h)
        print(f"│ #  │ {'Question'.ljust(COL_Q)} │ CosSim │")
        print(m)

        for idx, q_text, sent, sim in rows:
            q_disp = _truncate(q_text, COL_Q)
            s_disp = _truncate('↳ ' + sent, COL_S)

            print(f"│ {idx:>2} │ {q_disp.ljust(COL_Q)} │ {sim:6.3f} │")
            print(f"│    │ {s_disp.ljust(COL_S)} │        │")
            if idx != len(rows):
                print(m)
        print(f)

        # 5) CSV export (overwrite)
        CSV_DIR.mkdir(parents=True, exist_ok=True)
        with CSV_FILE.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["rank", "question", "sentence", "cosine_similarity"])
            for idx, q_text, sent, sim in rows:
                writer.writerow([idx, q_text, sent, f"{sim:.6f}"])

        self.stdout.write(self.style.SUCCESS(f"\n💾  Results saved to: {CSV_FILE}"))