# graph_algorithm/knowledge_graph_functions.py
# ════════════════════════════════════════════
"""
Generic graph-algorithm helpers (Neo4j)
---------------------------------------

fetch_subgraph(seed_qid, depth)
    Breadth-first crawl *outwards from an edge* (quadruple-id) up to the
    requested hop-depth and return **two** objects:

        1. edges : List[Dict]   – unique edge dictionaries, each::
                 { triple, quadruple_ids, inferred, sentence }

        2. seen_qids : Set[str] – every quadruple-id encountered.

render_outline_3A(edges, seed_qid)
    Produce a human-readable outline (variant “3-A”) that starts with the
    entry relationship, then shows 1-hop and 2-hop continuations on the
    LEFT (subject side) and RIGHT (object side).

    • **Every proposition sentence now begins with the glyph `▸`**, so a
      downstream component (LLM prompt, regex, etc.) can unambiguously
      extract factual statements via a simple “lines starting with ▸”
      rule.
"""

from __future__ import annotations

from collections import deque
from typing import Any, Dict, List, Set, Tuple

from graphrag.graph_traversal.knowledge_graph_utilities import (
    fetch_central_and_neighbours,
)

# ────────────────────────────────────────────────────────────────
#  1.  Edge crawl returning (edges, seen_qids)
# ────────────────────────────────────────────────────────────────
def fetch_subgraph(seed_qid: str, depth: int = 1) -> Tuple[List[Dict[str, Any]], Set[str]]:
    """
    Parameters
    ----------
    seed_qid : str
        Quadruple-id of the *relationship* used as the entry point.
    depth : int
        Number of BFS layers to explore (≥ 1).

    Returns
    -------
    (edges, seen_qids)
        edges      – list of unique edge-dicts (central edge first)
        seen_qids  – **all** quadruple-ids encountered in the crawl
    """
    if depth < 1:
        raise ValueError("depth must be ≥ 1")

    seen_qids: Set[str] = set()
    edges: List[Dict[str, Any]] = []

    frontier: deque[str] = deque([seed_qid])
    current_depth = 0

    while frontier and current_depth < depth:
        current_depth += 1
        for _ in range(len(frontier)):
            qid = frontier.popleft()
            if qid in seen_qids:
                continue

            sub = fetch_central_and_neighbours(qid, exclude_qids=seen_qids)

            central = sub.get("central")
            if central:
                edges.append(central)
                seen_qids.update(central["quadruple_ids"])

            for n in sub.get("neighbours", []):
                n_qids = n["quadruple_ids"]
                main_q = n_qids[0]
                if main_q not in seen_qids:
                    frontier.append(main_q)

                edges.append(n)
                seen_qids.update(n_qids)

    # keep first occurrence (by main QID)
    uniq, already = [], set()
    for e in edges:
        q_main = e["quadruple_ids"][0]
        if q_main not in already:
            uniq.append(e)
            already.add(q_main)

    return uniq, seen_qids


# ────────────────────────────────────────────────────────────────
#  2.  Pretty-printer – outline variant 3-A
# ────────────────────────────────────────────────────────────────
def render_outline_3A(
    edges: List[Dict[str, Any]],
    seed_qid: str,
) -> str:
    """
    Format `edges` (typically from ``fetch_subgraph``) into the
    “variant 3-A” outline:

        ENTRY EDGE
          (S) --R0--> (O)
              ▸ proposition sentence …

        LEFT  – from (S)
          • (S) --R1--> (X)
            ▸ …
            ▸ (2-hop) (X) --R2--> (Y)
              ▸ …

        RIGHT – from (O)
          • …

    Returns
    -------
    str  – multi-line outline; propositions start with **▸**.
    """
    if not edges:
        return "<empty sub-graph>"

    # locate the entry edge
    central = next((e for e in edges if seed_qid in e["quadruple_ids"]), edges[0])
    s0, r0, o0 = central["triple"]

    # adjacency for 2-hop indentation
    by_node: Dict[str, List[Dict[str, Any]]] = {}
    for e in edges:
        s, _, o = e["triple"]
        by_node.setdefault(s, []).append(e)
        by_node.setdefault(o, []).append(e)

    def indent(txt: str, n: int) -> str:
        return " " * n + txt

    def fmt_triple(t: List[str]) -> str:
        s, r, o = t
        return f"({s}) --{r}--> ({o})"

    out: List[str] = []

    # ENTRY EDGE ----------------------------------------------------
    out.append("ENTRY EDGE")
    out.append(indent(fmt_triple(central["triple"]), 2))
    out.append(indent("▸ " + central.get("sentence", "(no sentence)"), 6))
    out.append("")

    # helper to emit 1-hop + its 2-hop children --------------------
    def emit(edge: Dict[str, Any], base: int) -> None:
        out.append(indent("• " + fmt_triple(edge["triple"]), base))
        out.append(indent("▸ " + edge.get("sentence", "(no sentence)"), base + 4))

        s, _, o = edge["triple"]
        cont_node = o if s == s0 else (s if o == o0 else None)
        if cont_node:
            for ch in by_node.get(cont_node, []):
                if ch in (edge, central):
                    continue
                out.append(indent("▸ " + fmt_triple(ch["triple"]), base + 4))
                out.append(indent("▸ " + ch.get("sentence", "(no sentence)"), base + 8))

    # LEFT side -----------------------------------------------------
    left = [e for e in edges if e is not central and s0 in e["triple"]]
    if left:
        out.append(f"LEFT  – from ({s0})")
        for e in left:
            emit(e, 2)
        out.append("")

    # RIGHT side ----------------------------------------------------
    right = [e for e in edges if e is not central and o0 in e["triple"]]
    if right:
        out.append(f"RIGHT – from ({o0})")
        for e in right:
            emit(e, 2)

    return "\n".join(out)