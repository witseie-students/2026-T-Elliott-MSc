# graph_algorithm/wrapper.py
# ════════════════════════════════════════════════════════════════════
"""
Light-weight **Graph-RAG wrapper** (single LLM call).

`graphrag_answer(question, depth=1) -> paragraph`

If *no* neighbour exceeds the similarity threshold the code now feeds a
dummy outline —

    "No relevant information could be found to answer that question."

— into the aggregator and, if the LLM returns an empty answer, falls
back to that same sentence.
"""

from __future__ import annotations

from typing import List, Set

import numpy as np

from graphrag.graph_algorithm.knowledge_graph_functions import (
    fetch_subgraph,
    render_outline_3A,
)
from graphrag.graph_algorithm.llm_answer import aggregate_paragraph
from knowledge_graph_generator.chroma_db.client import question_collection
from knowledge_graph_generator.chroma_db.embedding import get_embedding

# ── internal settings ───────────────────────────────────────────────
FETCH_K   = 40
THRESHOLD = 0.60  # cosine-similarity cut-off


# ── utility ----------------------------------------------------------
def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


# ── public API -------------------------------------------------------
def graphrag_answer(
    question: str,
    *,
    depth: int = 1,
    threshold: float = THRESHOLD,
) -> str:
    """
    Parameters
    ----------
    question : str
        Free-text biomedical question.
    depth : int, default 1
        Hop-depth for each sub-graph.
    threshold : float, default 0.60
        Minimum cosine similarity to accept a neighbour.

    Returns
    -------
    paragraph : str
        Concise answer paragraph generated **solely** from the ▸ propositions
        contained in the retrieved graph outlines, or a generic fallback
        when no neighbour is found.
    """
    # 1) embed question → Chroma nearest neighbours
    q_vec = np.asarray(get_embedding(question))
    res   = question_collection.query(
        query_embeddings=[q_vec.tolist()],
        n_results=FETCH_K,
        include=["embeddings", "metadatas"],
    )

    neighbours = [
        {
            "qid": meta.get("quadruple_id", pid),
            "sim": _cosine(q_vec, np.asarray(emb)),
        }
        for pid, emb, meta in zip(
            res["ids"][0], res["embeddings"][0], res["metadatas"][0]
        )
        if _cosine(q_vec, np.asarray(emb)) >= threshold
    ]
    neighbours.sort(key=lambda d: d["sim"], reverse=True)

    # ------------- no entry points → dummy outline -------------------
    if not neighbours:
        dummy_outline = "No relevant information could be found to answer that question."
        paragraph     = aggregate_paragraph(question, dummy_outline).strip()
        return paragraph or dummy_outline

    # 2) pull sub-graphs (skip duplicate QIDs)
    outlines: List[str] = []
    seen_qids: Set[str] = set()
    for n in neighbours:
        qid = n["qid"]
        if qid in seen_qids:
            continue
        edges, seen_local = fetch_subgraph(qid, depth=depth)
        seen_qids.update(seen_local)
        outlines.append(render_outline_3A(edges, seed_qid=qid))

    # 3) single LLM call → paragraph
    combined_outline = "\n\n".join(outlines) or \
        "No relevant information could be found to answer that question."
    paragraph = aggregate_paragraph(question, combined_outline).strip()
    return paragraph or combined_outline


__all__ = ["graphrag_answer"]