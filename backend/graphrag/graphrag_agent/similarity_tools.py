"""
similarity_tools.py
───────────────────
Utilities for retrieving similarity scores, detecting a cumulative-sum cluster,
and (optionally) generating similarity plots.

📌 2025-06-13
    *Plotting temporarily disabled to prevent GUI backend errors
    when GraphRAG runs inside a Django thread.*
"""

from __future__ import annotations

from typing import List, Tuple
from pathlib import Path
from datetime import datetime

import numpy as np
# import matplotlib.pyplot as plt          # ⟵ disabled for now
from graphrag.graphrag_agent.question_search import similar_quadruple_ids


# ─────────────────────────────────────────────────────────────────────
# Retrieval
# ─────────────────────────────────────────────────────────────────────
def get_ranked_similarities(
    question: str,
    *,
    top_n: int = 10,
    similarity_threshold: float = 0.0,
) -> List[Tuple[str, float]]:
    """
    Embed *question* and return the top-*n* (qid, similarity) pairs,
    sorted highest → lowest.
    """
    pairs = similar_quadruple_ids(
        question,
        similarity_threshold=similarity_threshold,
        max_candidates=top_n,
    )
    return pairs


# ─────────────────────────────────────────────────────────────────────
# Cluster detection (cumulative-sum method)
# ─────────────────────────────────────────────────────────────────────
def group_until_cumsum(scores: list[float], target: float = 1.0) -> list[int]:
    """
    Return indices of the top scores whose cumulative sum ≥ *target*.
    """
    indices: List[int] = []
    running_sum = 0.0

    for i, sim in enumerate(scores):
        running_sum += sim
        indices.append(i)
        if running_sum >= target:
            break

    return indices


# ─────────────────────────────────────────────────────────────────────
# Main wrapper
# ─────────────────────────────────────────────────────────────────────
def analyze_similarity_cluster(
    question: str,
    top_n: int = 10,
    *,
    outdir: str | Path = "similarity_plots",
    savefig: str | None = None,
    show: bool = False,
) -> List[Tuple[str, float]]:
    """
    Identify the top semantic cluster of similar quadruples for *question*.

    **Plotting is currently de-activated.**  All parameters related to figure
    saving (`outdir`, `savefig`, `show`) are kept for future use but ignored.
    """
    outdir = Path(outdir).expanduser()
    outdir.mkdir(parents=True, exist_ok=True)

    # Determine filename even though we will not actually save a figure
    if savefig is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        savefig = outdir / f"{ts}_similarity_cluster_plot.png"
    else:
        savefig = Path(savefig).expanduser()
        if not savefig.is_absolute():
            savefig = outdir / savefig

    # 1. Retrieve the top-n similarities
    pairs = get_ranked_similarities(question, top_n=top_n)
    if not pairs:
        raise ValueError("No matches found.")

    qids, sims = zip(*pairs)
    sims = list(sims)

    # 2. Determine cluster indices via cumulative-sum
    cluster_indices = group_until_cumsum(sims, target=1.0)
    cluster_pairs   = [pairs[i] for i in cluster_indices]

    # 3. Plotting (💤 disabled)
    # -----------------------------------------------------------------
    # If you want the visual back, delete the triple-quoted block markers
    # and re-enable the `import matplotlib.pyplot as plt` line at the top.
    """
    cutoff = sims[cluster_indices[-1]]
    fig = plt.figure(figsize=(6, 4))
    ranks = np.arange(1, len(sims) + 1)

    # Plot full similarity curve
    plt.plot(ranks, sims, color="blue", linestyle="-", label="Similarity")

    # Scatter points
    for i, sim in enumerate(sims):
        color = "green" if i in cluster_indices else "blue"
        plt.scatter(ranks[i], sim, color=color)

    # Horizontal cutoff
    plt.axhline(
        y=cutoff, linestyle="--", color="red",
        label=f"cluster cutoff = {cutoff:.4f}",
    )

    plt.title("Nearest-neighbour similarity curve")
    plt.xlabel("Rank")
    plt.ylabel("Similarity score (1 − distance)")
    plt.grid(True, alpha=0.3)
    plt.legend()

    fig.savefig(savefig, dpi=150, bbox_inches="tight")
    if show:
        plt.show()
    else:
        plt.close(fig)
    """

    return cluster_pairs