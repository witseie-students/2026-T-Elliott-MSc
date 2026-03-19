#!/usr/bin/env python3
"""Combine ordinary-RAG results with extracted-only results.

Assumes the following CSV files live in the same folder as this script:
  • ordinary_rag_qa_outcome.csv                (all propositions)
  • ordinary_rag_qa_outcome_no_inferred.csv    (no inferred propositions)

It merges the two on `pubmed_id` and *filters* to keep only rows where at
least **one** method’s `final_result` differs from `actual_result` (i.e. at
least one method was wrong).

The output CSV is written as:
    ordinary_rag_compare_errors.csv
with columns:
    pubmed_id, question, actual_answer,
    answer_ordinary,  result_ordinary,
    answer_no_inferred, result_no_inferred,
    actual_result
"""

import pandas as pd
from pathlib import Path

# ---- paths ---------------------------------------------------------------
HERE = Path(__file__).resolve().parent
csv_all      = HERE / "ordinary_rag_qa_outcome.csv"
csv_noinf    = HERE / "ordinary_rag_qa_outcome_no_inferred.csv"
out_csv      = HERE / "99_ordinary_rag_compare_errors.csv"

# ---- load ---------------------------------------------------------------
print("📂  Loading CSV files…")

df_all   = pd.read_csv(csv_all)
df_noinf = pd.read_csv(csv_noinf)

# ---- sanity checks ------------------------------------------------------
required_cols = {"pubmed_id", "question", "answer", "final_result", "actual_answer", "actual_result"}
for name, df in {"ordinary": df_all, "no_inferred": df_noinf}.items():
    missing = required_cols - set(df.columns)
    if missing:
        raise ValueError(f"{name} CSV missing columns: {missing}")

# ---- rename & merge -----------------------------------------------------

rename_map_all = {
    "answer": "answer_ordinary",
    "final_result": "result_ordinary",
}
rename_map_noinf = {
    "answer": "answer_no_inferred",
    "final_result": "result_no_inferred",
}

df_all   = df_all.rename(columns=rename_map_all)
df_noinf = df_noinf.rename(columns=rename_map_noinf)

common_cols = ["pubmed_id", "question", "actual_answer", "actual_result"]

merged = pd.merge(
    df_all[common_cols + list(rename_map_all.values())],
    df_noinf[common_cols + list(rename_map_noinf.values())],
    on=["pubmed_id", "question", "actual_answer", "actual_result"],
    how="inner",
    suffixes=("_all", "_noinf"),
)

# ---- filter rows where at least one method was wrong --------------------
mask_wrong_all   = merged["result_ordinary"]     != merged["actual_result"]
mask_wrong_noinf = merged["result_no_inferred"] != merged["actual_result"]
filtered = merged[mask_wrong_all | mask_wrong_noinf].copy()

print(f"🔍  Retained {len(filtered):,} rows where at least one method erred (out of {len(merged):,} total).")

# ---- save ----------------------------------------------------------------
filtered.to_csv(out_csv, index=False)
print(f"💾  Saved comparison CSV → {out_csv}")

# ---- show sample --------------------------------------------------------
if not filtered.empty:
    print("\nPreview (first 5 rows):")
    print(filtered.head().to_string(index=False, max_colwidth=50))
else:
    print("No disagreements detected – nothing to save.")
