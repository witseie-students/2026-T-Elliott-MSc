
"""
Sum every column (publication year) in the PubMed wide table.

Input : PubMed_total_records_by_publication_year_20250530.csv
Output: PubMed_totals_by_publication_year.csv
"""

import pandas as pd
from pathlib import Path

INPUT_FILE  = "PubMed_total_records_by_publication_year_20250530.csv"
OUTPUT_FILE = "PubMed_totals_by_publication_year.csv"

def main() -> None:
    # 1. Load the dataset (first row is header, first column is index)
    df = pd.read_csv(INPUT_FILE, index_col=0)

    # 2. Sum down each column – skip NA values automatically
    col_sums = df.sum(axis=0, skipna=True)

    # 3. Wrap the result in a one-row DataFrame so we keep the same headers
    result = pd.DataFrame([col_sums], index=["Total"])

    # 4. Write to CSV
    result.to_csv(OUTPUT_FILE)

    print(f"Done! Wrote column totals to {OUTPUT_FILE}")

if __name__ == "__main__":
    # Ensure the input exists before running
    if not Path(INPUT_FILE).is_file():
        raise FileNotFoundError(f"Cannot find {INPUT_FILE} in the current directory.")
    main()
