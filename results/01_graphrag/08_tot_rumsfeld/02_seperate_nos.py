#!/usr/bin/env python
# 02_separate_no.py
# ════════════════════════════════════════════════════════════
"""
Extract rows where the *gold* answer is “no” **but** the model’s
prediction is not “no”, then save them to a new CSV that clearly
reflects this subset.

Default behaviour (same folder as the script):
    input  : tot_graphrag_rumsfeld_d1.csv
    output : 02_no_incorrect_tot_graphrag_rumsfeld_d1.csv

Custom paths:
    python 02_separate_no.py  <input.csv>  [<output.csv>]
"""
from __future__ import annotations
import sys
from pathlib import Path

import pandas as pd


def main() -> None:
    here = Path(__file__).resolve().parent

    # ── paths ────────────────────────────────────────────────────────
    in_path  = Path(sys.argv[1]) if len(sys.argv) >= 2 else here / "tot_graphrag_rumsfeld_d1.csv"
    default_out = in_path.parent / f"02_no_incorrect_{in_path.name}"
    out_path = Path(sys.argv[2]) if len(sys.argv) >= 3 else default_out

    if not in_path.exists():
        sys.exit(f"❌  Input CSV not found: {in_path}")

    # ── load & filter ───────────────────────────────────────────────
    df = pd.read_csv(in_path)
    wrong = df[
        (df["gold_label"].str.lower() == "no") &
        (df["prediction"].str.lower() != "no")
    ]

    # ── save & report ───────────────────────────────────────────────
    wrong.to_csv(out_path, index=False)
    print(f"✅  Exported {len(wrong)} row(s) → {out_path}")


if __name__ == "__main__":
    main()