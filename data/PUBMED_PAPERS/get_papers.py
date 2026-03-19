
"""
get_papers.py

Fetches the number of new PubMed citations added in each calendar
year from 1965 through 2025 and saves them to pubmed_yearly_counts.csv.

Reference – IEEE format
[1] National Library of Medicine, “Entrez Programming Utilities (E-utilities),
    esearch.fcgi – search PubMed database,” U.S. National Center for
    Biotechnology Information, Bethesda, MD. Accessed: May 30, 2025.
    [Online]. Available: https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi
"""

import csv
import time
import requests

API_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
START_YEAR = 1965
END_YEAR   = 2025
DELAY      = 0.34          # seconds between calls (NCBI rate guideline)

def count_citations_for_year(year: int) -> int:
    """Return the number of PubMed records whose EDAT lies in the given calendar year."""
    params = {
        "db": "pubmed",
        "datetype": "edat",
        "term": f"{year}[edat]",
        "mindate": f"{year}/01/01",
        "maxdate": f"{year}/12/31",
        "retmode": "json",
        "retmax": 0           # we only want the count
    }
    r = requests.get(API_URL, params=params, timeout=30)
    r.raise_for_status()
    return int(r.json()["esearchresult"]["count"])

def main() -> None:
    rows = []
    for yr in range(START_YEAR, END_YEAR + 1):
        cnt = count_citations_for_year(yr)
        print(f"{yr}: {cnt:,}")
        rows.append({"year": yr, "new_pubmed_citations": cnt})
        time.sleep(DELAY)     # be kind to the API

    outfile = "pubmed_yearly_counts.csv"
    with open(outfile, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=["year", "new_pubmed_citations"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nSaved {len(rows)} rows to {outfile}")

if __name__ == "__main__":
    main()
