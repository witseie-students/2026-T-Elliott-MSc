"""Light-weight retrieval helper for graphRAG."""
"""Helpers for question → quadruple-id retrieval via Chroma."""
from typing import List, Tuple

from knowledge_graph_generator.chroma_db.embedding import get_embedding
from knowledge_graph_generator.chroma_db.client import question_collection



def nearest_quadruple_ids(question: str, k: int = 1) -> List[str]:
    """
    Embed *question* and return up to *k* closest quadruple IDs
    from the Chroma **questions** collection.

    Parameters
    ----------
    question : str
    k        : int  (default 1)

    Returns
    -------
    list[str]
        Ordered by similarity (best first).
    """
    if not question:
        raise ValueError("Question string is empty.")

    emb = get_embedding(question)
    res = question_collection.query(
        query_embeddings=[emb],
        n_results=k,
        include=["metadatas", "distances"],
    )

    metas = res["metadatas"][0] if res["metadatas"] else []
    return [m["quadruple_id"] for m in metas]





# ─────────────────────────────────────────────────────────────────────────
# NEW : similarity-threshold variant
# ─────────────────────────────────────────────────────────────────────────
def similar_quadruple_ids(
    question: str,
    *,
    similarity_threshold: float = 0.5,
    max_candidates: int = 50,
) -> List[Tuple[str, float]]:
    """
    Embed *question* and return **all** quadruple IDs whose cosine-similarity
    meets or exceeds *similarity_threshold* (default 0.5).

    Returns a list of (quadruple_id, similarity) tuples ordered best→worst.
    """
    if not question:
        raise ValueError("Question string is empty.")
    if not (0.0 <= similarity_threshold <= 1.0):
        raise ValueError("similarity_threshold must be in [0, 1].")

    emb = get_embedding(question)
    res = question_collection.query(
        query_embeddings=[emb],
        n_results=max_candidates,
        include=["metadatas", "distances"],
    )

    metas = res["metadatas"][0] if res["metadatas"] else []
    dists = res["distances"][0]  if res["distances"]  else []

    # convert to similarity = 1 – distance (because Chroma defaults to L2)
    sims = [1.0 - d for d in dists]

    pairs = [
        (meta["quadruple_id"], sim)
        for meta, sim in zip(metas, sims)
        if sim >= similarity_threshold
    ]

    # sort descending by similarity
    pairs.sort(key=lambda t: t[1], reverse=True)
    return pairs
