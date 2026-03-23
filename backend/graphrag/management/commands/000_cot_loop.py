# backend/graphrag/management/commands/018_cot_loop.py
# ══════════════════════════════════════════════════════
"""
Chain-of-Thought Graph-RAG runner.
Writes every run to
  results/01_graphrag/05_cot_graphrag/cot_graphrag_d<DEPTH>.csv

Columns:
    pubmed_id       – PMID from PUBMED_QA2.csv
    question        – original question
    paragraph       – final aggregated paragraph
    prediction      – yes / no / maybe (classifier)
    loops           – how many planner→questioner→retriever turns
    gold_label      – PubMed-QA ground-truth label
    reasoning_chain – full CoT trace as JSON (list[dict])
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import List, Dict

import pandas as pd
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from graphrag.COT.agents import cot_controller

# ── fixed defaults (edit if you like) ───────────────────────────────
N_ROWS = 350      # how many PubMed-QA questions to process
DEPTH  = 1      # hop-depth for every Graph-RAG retrieval
LIMIT  = 100     # wall-clock seconds per question

# ── paths -----------------------------------------------------------
ROOT_DIR  = Path(settings.BASE_DIR).parent
DATA_CSV  = ROOT_DIR / "data/PUBMEDQA/PUBMED_QA2.csv"
OUT_DIR   = ROOT_DIR / "results/01_graphrag/05_cot_graphrag"
OUT_DIR.mkdir(parents=True, exist_ok=True)


# ── management command ---------------------------------------------
class Command(BaseCommand):
    help = "Run the full CoT Graph-RAG loop and export a CSV of the results."

    # CLI flags still override the hard-coded defaults ----------------
    def add_arguments(self, parser):
        parser.add_argument("--rows",  type=int, default=N_ROWS,
                            help=f"How many PubMed-QA rows to process (default {N_ROWS}).")
        parser.add_argument("--depth", type=int, default=DEPTH,
                            help=f"Graph hop-depth (default {DEPTH}).")
        parser.add_argument("--limit", type=int, default=LIMIT,
                            help=f"Wall-clock time-limit per question in seconds (default {LIMIT}).")

    # ───────────────────────────────────────────────────────────
    def handle(self, *args, **opts):
        n_rows = opts["rows"]
        depth  = opts["depth"]
        limit  = opts["limit"]

        if n_rows < 1 or depth < 1 or limit < 1:
            raise CommandError("All numeric flags must be ≥ 1.")
        if not DATA_CSV.exists():
            raise CommandError(f"CSV not found: {DATA_CSV}")

        # Load the first n_rows questions ----------------------------
        with DATA_CSV.open(newline="", encoding="utf-8") as fh:
            rows = [row for _, row in zip(range(n_rows), csv.DictReader(fh))]
        if not rows:
            self.stdout.write(self.style.WARNING("No rows loaded – nothing to do."))
            return

        results: List[Dict[str, str]] = []

        # Iterate ----------------------------------------------------
        for idx, row in enumerate(rows, 1):
            question   = row["question"].strip()
            pubmed_id  = row["pubid"].strip()
            gold_label = row["final_decision"].strip().lower()

            self.stdout.write(f"\n╔═ Question {idx}/{n_rows} ══")
            self.stdout.write(question)
            self.stdout.write("╟───────── reasoning chain ─────────")

            chain = cot_controller(question, depth=depth, time_limit=limit)

            # pretty-print chain -------------------------------------
            for step in chain:
                self.stdout.write(f"\n[{step['role'].upper()}]\n{step['content']}")

            # extract final artefacts -------------------------------
            paragraph  = next(s for s in chain if s["role"] == "aggregator")["content"]
            prediction = next(s for s in chain if s["role"] == "classifier")["content"]
            loops_str  = next(s for s in chain if s["content"].startswith("Total loops"))["content"]
            loops      = int(loops_str.split(":")[1].strip())

            self.stdout.write("\n\n── FINAL ANSWER ──")
            self.stdout.write(paragraph)
            self.stdout.write(f"\nLabel : {prediction}")
            self.stdout.write(f"\n{loops_str}")
            self.stdout.write("\n╚═════════════════════════════════════\n")

            # serialise the full chain as JSON (readable, non-ASCII ok)
            chain_json = json.dumps(chain, ensure_ascii=False, indent=2)

            # accumulate CSV row -------------------------------------
            results.append(
                {
                    "pubmed_id":      pubmed_id,
                    "question":       question,
                    "paragraph":      paragraph,
                    "prediction":     prediction,
                    "loops":          loops,
                    "gold_label":     gold_label,
                    "reasoning_chain": chain_json,
                }
            )

        # save CSV ---------------------------------------------------
        csv_path = OUT_DIR / f"cot_graphrag_d{depth}.csv"
        pd.DataFrame(results).to_csv(csv_path, index=False)
        self.stdout.write(self.style.SUCCESS(f"\n✅  Saved → {csv_path}"))