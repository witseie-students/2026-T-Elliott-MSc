# backend/graphrag/management/commands/020_tot_null_hypothesis.py
# ══════════════════════════════════════════════════════════════
"""
Tree-of-Thought Graph-RAG *null-hypothesis* experiment.

• Runs `tot_controller(..., null_hypothesis=True)`  
• Pretty-prints the reasoning tree with ASCII connectors  
• Saves results to
    results/01_graphrag/07_tot_null_hypothesis/tot_graphrag_null_d<DEPTH>.csv
"""

from __future__ import annotations

import csv, json
from pathlib import Path
from typing import Dict, List

import pandas as pd
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from graphrag.tree_of_thought.agents import tot_controller

# ── defaults (override on CLI) ─────────────────────────────────────
N_ROWS = 350
DEPTH  = 2
LIMIT  = 100

ROOT_DIR = Path(settings.BASE_DIR).parent
DATA_CSV = ROOT_DIR / "data/PUBMEDQA/PUBMED_QA2.csv"
OUT_DIR  = ROOT_DIR / "results/01_graphrag/07_tot_null_hypothesis"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── pretty-print helper (same as 019) ─────────────────────────────
def _build_last_idx(tree):
    last = {}
    for i, n in enumerate(tree):
        last[n["depth"]] = i
    return last

def _pp(tree, echo=print):
    last = _build_last_idx(tree)
    for i, n in enumerate(tree):
        gut = "".join("│   " if i < last.get(lvl, -1) else "    "
                      for lvl in range(n["depth"]))
        glyph = "├─ " if i < last[n["depth"]] else "└─ "
        bid   = f"[B{n['branch_id']}]" if n["branch_id"] else ""
        txt   = (str(n["content"])[:120] + "…") if len(str(n["content"])) > 123 else n["content"]
        echo(f"{gut}{glyph}{bid:<6} {n['role'].upper():<14} {txt}")

# ──────────────────────────────────────────────────────────────
class Command(BaseCommand):
    help = "ToT Graph-RAG run with a null-hypothesis branch."

    def add_arguments(self, p):
        p.add_argument("--rows", type=int, default=N_ROWS)
        p.add_argument("--depth", type=int, default=DEPTH)
        p.add_argument("--limit", type=int, default=LIMIT)

    def handle(self, *a, **o):
        n, d, lim = o["rows"], o["depth"], o["limit"]
        if min(n, d, lim) < 1:
            raise CommandError("All numeric flags must be ≥1.")
        if not DATA_CSV.exists():
            raise CommandError(f"CSV not found: {DATA_CSV}")

        with DATA_CSV.open(newline="", encoding="utf-8") as fh:
            rows = [r for _, r in zip(range(n), csv.DictReader(fh))]
        if not rows:
            self.stdout.write(self.style.WARNING("No rows loaded – nothing to do."))
            return

        recs: List[Dict[str, str]] = []

        for idx, row in enumerate(rows, 1):
            q   = row["question"].strip()
            pm  = row["pubid"].strip()
            gold= row["final_decision"].strip().lower()

            self.stdout.write(f"\n╔═ Question {idx}/{n} ═════════════════════════════════════")
            self.stdout.write(q)
            self.stdout.write("╟───────── Tree of Thought ────────────────────────────────────")

            run = tot_controller(q, graph_depth=d, time_limit=lim,
                                 null_hypothesis=True, rumsfeld=False)

            _pp(run["tree"], echo=self.stdout.write)

            self.stdout.write("\n── FINAL ────────────────────────────────────────────────────")
            self.stdout.write(run["final_paragraph"])
            self.stdout.write(f"\nLabel        : {run['final_label']}")
            self.stdout.write(f"\nTotal loops  : {run['loops']}")
            self.stdout.write("\n╚════════════════════════════════════════════════════════════\n")

            recs.append(
                {
                    "pubmed_id": pm,
                    "question":  q,
                    "paragraph": run["final_paragraph"],
                    "prediction": run["final_label"],
                    "loops":      run["loops"],
                    "gold_label": gold,
                    "reasoning_tree": json.dumps(run["tree"], ensure_ascii=False, indent=2),
                }
            )

        csv_out = OUT_DIR / f"tot_graphrag_null_d{d}.csv"
        pd.DataFrame(recs).to_csv(csv_out, index=False)
        self.stdout.write(self.style.SUCCESS(f"\n✅  Saved → {csv_out}"))