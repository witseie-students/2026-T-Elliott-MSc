# backend/graphrag/management/commands/021_tot_rumsfeld.py
# ══════════════════════════════════════════════════════════════
"""
Tree-of-Thought Graph-RAG **Rumsfeld-matrix** experiment.

• Runs `tot_controller(..., null_hypothesis=True, rumsfeld=True)`
• Pretty-prints the reasoning tree with ASCII connectors
• Saves results to
      results/01_graphrag/08_tot_rumsfeld/tot_graphrag_rumsfeld_d<DEPTH>.csv
"""

from __future__ import annotations

import csv, json
from pathlib import Path
from typing import Dict, List

import pandas as pd
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from graphrag.tree_of_thought.agents import tot_controller

# ------------ defaults ---------------------------------------
N_ROWS = 350
DEPTH  = 1
LIMIT  = 100

ROOT_DIR = Path(settings.BASE_DIR).parent
DATA_CSV = ROOT_DIR / "data/PUBMEDQA/PUBMED_QA2.csv"
OUT_DIR  = ROOT_DIR / "results/01_graphrag/08_tot_rumsfeld"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ------------ pretty-printer ---------------------------------
def _last_idx(tree):          # depth → last idx
    d = {}
    for i, n in enumerate(tree): d[n["depth"]] = i
    return d

def _pp(tree, echo=print):
    last = _last_idx(tree)
    for i, n in enumerate(tree):
        gut = "".join("│   " if i < last.get(l, -1) else "    "
                      for l in range(n["depth"]))
        glyph = "├─ " if i < last[n["depth"]] else "└─ "
        bid   = f"[B{n['branch_id']}]" if n["branch_id"] else ""
        txt   = (str(n["content"])[:120] + "…") if len(str(n["content"])) > 123 else n["content"]
        echo(f"{gut}{glyph}{bid:<6} {n['role'].upper():<14} {txt}")

# ------------ management command -----------------------------
class Command(BaseCommand):
    help = "Run Tree-of-Thought with Rumsfeld matrix + null-hypothesis."

    def add_arguments(self, p):
        p.add_argument("--rows",  type=int, default=N_ROWS)
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
            self.stdout.write(self.style.WARNING("No rows – nothing to do."))
            return

        recs: List[Dict[str, str]] = []

        for idx, row in enumerate(rows, 1):
            q    = row["question"].strip()
            pmid = row["pubid"].strip()
            gold = row["final_decision"].strip().lower()

            self.stdout.write(f"\n╔═ Question {idx}/{n} ═════════════════════════════════════")
            self.stdout.write(q)
            self.stdout.write("╟───────── Tree of Thought ────────────────────────────────────")

            run = tot_controller(q,
                                 graph_depth=d, time_limit=lim,
                                 null_hypothesis=True, rumsfeld=True)

            _pp(run["tree"], echo=self.stdout.write)

            self.stdout.write("\n── FINAL ────────────────────────────────────────────────────")
            self.stdout.write(run["final_paragraph"])
            self.stdout.write(f"\nLabel        : {run['final_label']}")
            self.stdout.write(f"\nTotal loops  : {run['loops']}")
            self.stdout.write("\n╚════════════════════════════════════════════════════════════\n")

            recs.append(
                dict(pubmed_id=pmid, question=q,
                     paragraph=run["final_paragraph"],
                     prediction=run["final_label"],
                     loops=run["loops"], gold_label=gold,
                     reasoning_tree=json.dumps(run["tree"], ensure_ascii=False, indent=2))
            )

        csv_out = OUT_DIR / f"tot_graphrag_rumsfeld_d{d}.csv"
        pd.DataFrame(recs).to_csv(csv_out, index=False)
        self.stdout.write(self.style.SUCCESS(f"\n✅  Saved → {csv_out}"))