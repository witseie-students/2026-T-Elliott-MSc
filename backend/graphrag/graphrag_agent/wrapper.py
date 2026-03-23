"""
graphrag/graphrag_agent/wrapper.py
──────────────────────────────────
High-level façade around the GraphRAG pipeline.

Normal flow
-----------
1. Take both questions (root & sub).
2. Fetch:
      • 2 seeds for the *root_question*  (optional)
      • 3 seeds for the *sub_question*   (always attempted)
3. Merge & deduplicate seeds.
4. DFS-reason over the merged list.
5. Aggregate evidence → librarian-style answer.

2025-06-13  Update
------------------
• Similarity search may return *zero* hits – now caught with a try/except.
  Instead of raising a ValueError that bubbles up to Django (500 error),
  we print a warning and keep going.
• If **all** seed searches fail (no seeds at all), we:
    –   skip DFS reasoning,
    –   call the Aggregator with an empty evidence list,
    –   return its answer (likely “insufficient evidence…”).
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Tuple, Optional

from .similarity_tools import analyze_similarity_cluster
from .graph_reasoner     import run_reasoning
from .aggregator_helpers import aggregate_answer


# ─────────────────────────────────────────────────────────────────────
# Helper utilities
# ─────────────────────────────────────────────────────────────────────
def _unique_preserve_order(pairs: List[Tuple[str, float]]
                           ) -> List[Tuple[str, float]]:
    """Remove duplicate qids while preserving the first-seen order."""
    seen: set[str] = set()
    uniq: list[Tuple[str, float]] = []
    for qid, sim in pairs:
        if qid not in seen:
            uniq.append((qid, sim))
            seen.add(qid)
    return uniq


def _run_seeds(
    sub_question: str,
    root_question: Optional[str],
    seeds: Iterable[Tuple[str, float]],
) -> list[dict]:
    """
    Run DFS reasoning from **each** seed while sharing a single evidence bucket.
    Both questions are forwarded so they appear in the context window.
    """
    evidence: list[dict] = []
    for rank, (qid, sim) in enumerate(seeds, start=1):
        print(f"[GraphRAG] Seed {rank}/{len(seeds)}  qid={qid}  sim={sim:.4f}")
        run_reasoning(
            question=sub_question,
            root_question=root_question,
            seed_qid=qid,
            collected_bucket=evidence,
            aggregate=False,   # aggregation happens once at the end
        )
    return evidence


# ─────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────
def answer_question(
    sub_question: str,
    *,
    root_question: str | None = None,
    outdir: str | Path | None = "similarity_plots",
    return_evidence: bool = False,
) -> str | tuple[str, list[dict]]:
    """
    Parameters
    ----------
    sub_question : str
        Branch-level question from the Tree-of-Thought engine.
    root_question : str | None
        User’s original, overarching query (optional).
    outdir : str | Path | None
        Directory for similarity-curve plots (kept for future use).
    return_evidence : bool
        If True return ``(answer, evidence)`` instead of answer only.
    """

    # 1 ─ Similarity search for both questions --------------------------
    combined: list[Tuple[str, float]] = []

    # — root / main question (2 seeds) —
    if root_question:
        try:
            print(f"[GraphRAG] root_question received: «{root_question}»")
            root_seeds = analyze_similarity_cluster(
                question=root_question,
                top_n=1,
                outdir=str(outdir) if outdir else None,
                savefig=None,
                show=False,
            )
            print(f"[GraphRAG] Selected {len(root_seeds)} root-question seeds")
            combined.extend(root_seeds)
        except ValueError:
            # No matches – just warn, do not crash
            print("[GraphRAG] ⚠️  No similarity matches for root_question")

    # — sub / branch question (3 seeds) —
    try:
        sub_seeds = analyze_similarity_cluster(
            question=sub_question,
            top_n=1,
            outdir=str(outdir) if outdir else None,
            savefig=None,
            show=False,
        )
        print(f"[GraphRAG] Selected {len(sub_seeds)} sub-question seeds")
        combined.extend(sub_seeds)
    except ValueError:
        print("[GraphRAG] ⚠️  No similarity matches for sub_question")

    # 2 ─ Merge & deduplicate ------------------------------------------
    cluster = _unique_preserve_order(combined)

    if cluster:
        print("[GraphRAG] Final merged seed list:")
        for idx, (qid, sim) in enumerate(cluster, 1):
            print(f"  {idx:2d}. {qid}   sim={sim:.4f}")

        # 3 ─ DFS reasoning --------------------------------------------
        evidence = _run_seeds(sub_question, root_question, cluster)

    else:
        # No seeds at all – skip graph traversal
        print("[GraphRAG] ❗  No similarity seeds found for either question.")
        evidence = []

    # 4 ─ Aggregation ---------------------------------------------------
    answer = aggregate_answer(
        sub_question,
        evidence,
        root_question=root_question,
    )

    print('---------------------------------------------------------------------------------------------------------------------------------')
    print('Aggregated GraphRAG answer:')
    print(answer)
    print('---------------------------------------------------------------------------------------------------------------------------------')

    return (answer, evidence) if return_evidence else answer