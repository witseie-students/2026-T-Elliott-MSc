# backend/graphrag/management/commands/019_tot_loop.py
# ══════════════════════════════════════════════════════
"""
Tree-of-Thought Graph-RAG experiment.

• Runs `tot_controller` for the first *N* PubMed-QA rows
• Pretty-prints every reasoning tree with ASCII connectors
• Persists the run to
    results/01_graphrag/06_tot_graphrag/tot_graphrag_d<DEPTH>.csv
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Dict, List

import pandas as pd
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from graphrag.tree_of_thought.agents import tot_controller

# ── hard-coded defaults (override on CLI) ──────────────────────────
N_ROWS = 350
DEPTH  = 2          # hop-depth for Graph-RAG retrieval
LIMIT  = 100        # wall-clock seconds per question

# ── paths -----------------------------------------------------------
ROOT_DIR  = Path(settings.BASE_DIR).parent
DATA_CSV  = ROOT_DIR / "data/PUBMEDQA/PUBMED_QA2.csv"
OUT_DIR   = ROOT_DIR / "results/01_graphrag/06_tot_graphrag"
OUT_DIR.mkdir(parents=True, exist_ok=True)


# ═══════════════════════════════════════════════════════════════════
# Pretty-printer helpers
# ═══════════════════════════════════════════════════════════════════
def _build_last_index_by_depth(tree: List[Dict[str, object]]) -> Dict[int, int]:
    """Return {depth: last_row_index_with_that_depth} for the whole tree."""
    last = {}
    for idx, node in enumerate(tree):
        last[node["depth"]] = idx
    return last


def _pretty_print_tree(tree: List[Dict[str, object]], echo=print) -> None:
    """
    Print the trace in a textbook ASCII tree:

        ├─ role …content
        │   └─ …

    * Assumes `tree` is already in chronological order (as returned).
    """
    last_idx = _build_last_index_by_depth(tree)

    for idx, node in enumerate(tree):
        depth   = node["depth"]
        role    = node["role"].upper()
        content = str(node["content"])

        # build the left gutter with │ or blanks
        gutter = []
        for lvl in range(depth):
            gutter.append("│   " if idx < last_idx.get(lvl, -1) else "    ")
        # connector for the current line
        branch_glyph = "├─ " if idx < last_idx[depth] else "└─ "
        prefix = "".join(gutter) + branch_glyph

        bid = f"[B{node['branch_id']}]" if node["branch_id"] else ""
        # trim very long content for clean terminal width
        trimmed = (content[:120] + "…") if len(content) > 123 else content
        echo(f"{prefix}{bid:<6} {role:<11} {trimmed}")


# ═══════════════════════════════════════════════════════════════════
# Django management command
# ═══════════════════════════════════════════════════════════════════
class Command(BaseCommand):
    help = "Run the Tree-of-Thought Graph-RAG loop and export a CSV log."

    def add_arguments(self, parser):
        parser.add_argument("--rows",  type=int, default=N_ROWS)
        parser.add_argument("--depth", type=int, default=DEPTH)
        parser.add_argument("--limit", type=int, default=LIMIT)

    # ───────────────────────────────────────────────────────────
    def handle(self, *args, **opts):
        n_rows = opts["rows"]; depth = opts["depth"]; limit = opts["limit"]
        if min(n_rows, depth, limit) < 1:
            raise CommandError("All numeric flags must be ≥ 1.")
        if not DATA_CSV.exists():
            raise CommandError(f"CSV not found: {DATA_CSV}")

        # load questions ------------------------------------------------
        with DATA_CSV.open(newline="", encoding="utf-8") as fh:
            rows = [r for _, r in zip(range(n_rows), csv.DictReader(fh))]
        if not rows:
            self.stdout.write(self.style.WARNING("No rows found – nothing to do."))
            return

        results: List[Dict[str, str]] = []

        # main loop -----------------------------------------------------
        for idx, row in enumerate(rows, 1):
            q     = row["question"].strip()
            pmid  = row["pubid"].strip()
            gold  = row["final_decision"].strip().lower()

            self.stdout.write(f"\n╔═ Question {idx}/{n_rows} ═════════════════════════════════════")
            self.stdout.write(q)
            self.stdout.write("╟───────── Tree of Thought ────────────────────────────────────")

            run = tot_controller(q, graph_depth=depth, time_limit=limit, null_hypothesis=False, rumsfeld=False)

            # fancy print
            _pretty_print_tree(run["tree"], echo=self.stdout.write)

            self.stdout.write("\n── FINAL ────────────────────────────────────────────────────")
            self.stdout.write(run["final_paragraph"])
            self.stdout.write(f"\nLabel        : {run['final_label']}")
            self.stdout.write(f"\nTotal loops  : {run['loops']}")
            self.stdout.write("\n╚════════════════════════════════════════════════════════════\n")

            results.append(
                {
                    "pubmed_id":   pmid,
                    "question":    q,
                    "paragraph":   run["final_paragraph"],
                    "prediction":  run["final_label"],
                    "loops":       run["loops"],
                    "gold_label":  gold,
                    "reasoning_tree": json.dumps(run["tree"], ensure_ascii=False, indent=2),
                }
            )

        # save CSV ------------------------------------------------------
        csv_out = OUT_DIR / f"tot_graphrag_d{depth}.csv"
        pd.DataFrame(results).to_csv(csv_out, index=False)
        self.stdout.write(self.style.SUCCESS(f"\n✅  Saved → {csv_out}"))