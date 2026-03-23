# graphrag/graph_traversal/main.py
# ════════════════════════════════════════════════════════════════════
"""
Graph-RAG traversal (BFS) with a pretty ASCII tree print-out.

Returns
-------
dict {
  "seen_qids":         list[str],
  "collection_bucket": list[dict]        # qid / sentence / reasoning
}
"""

from __future__ import annotations
import time
from collections import defaultdict, deque
from typing import Dict, Any, Set, List

from .knowledge_graph_utilities import fetch_central_and_neighbours
from .agent import thought_agent, planner_agent


# ── tree drawing helper ─────────────────────────────────────────────
def _render_tree(root: str, children: Dict[str, List[str]]) -> List[str]:
    """Return the tree rooted at *root* as a list of ascii lines."""
    def _draw(node: str, prefix: str, is_last: bool) -> List[str]:
        connector = "└─ " if is_last else "├─ "
        line = f"{prefix}{connector}{node}"
        lines = [line]
        new_prefix = f"{prefix}{'   ' if is_last else '│  '}"
        kids = children.get(node, [])
        for i, kid in enumerate(kids):
            lines += _draw(kid, new_prefix, i == len(kids) - 1)
        return lines

    # root printed without connector
    lines = [root]
    for i, kid in enumerate(children.get(root, [])):
        lines += _draw(kid, "", i == len(children[root]) - 1)
    return lines


# ── traversal -------------------------------------------------------
def react_loop(
    seed_qid: str,
    question: str,
    max_depth: int = 5,
    *,
    initial_seen: Set[str] | None = None,
) -> Dict[str, Any]:

    frontier: deque[str] = deque([seed_qid])
    path_by_qid: Dict[str, List[str]] = {seed_qid: [seed_qid]}

    # parent->children mapping for the final tree
    children: Dict[str, List[str]] = defaultdict(list)

    seen_qids: Set[str] = set(initial_seen or [])
    collection_bucket: List[Dict[str, Any]] = []

    depth = 0
    while frontier and depth < max_depth:
        depth += 1
        next_frontier: deque[str] = deque()

        while frontier:
            curr_qid = frontier.popleft()
            branch_path = path_by_qid[curr_qid]

            # 1) fetch ------------------------------------------------
            graph = fetch_central_and_neighbours(curr_qid, exclude_qids=seen_qids)
            entry = graph["central"]
            if entry is None:
                continue
            seen_qids.update(entry["quadruple_ids"])

            # 2) THOUGHT ----------------------------------------------
            thought = thought_agent(
                context_chain=[{"proposition": entry}],
                question=question,
            )
            if thought.get("save"):
                collection_bucket.append(
                    {
                        "qid": entry["quadruple_ids"][0],
                        "sentence": entry["sentence"],
                        "reasoning": thought["reasoning"],
                    }
                )

            # 3) neighbours + PLANNER --------------------------------
            neighbours = [
                n for n in graph["neighbours"]
                if not any(q in seen_qids for q in n["quadruple_ids"])
            ]
            neigh_by_qid = {n["quadruple_ids"][0]: n for n in neighbours}

            planner = planner_agent(
                context_chain=[{"proposition": entry, "thought": thought}],
                neighbours=neighbours,
                question=question,
            )

            if planner.get("action") == "expand":
                for q in planner.get("selected_qids", []):
                    if q in seen_qids or q in path_by_qid:
                        continue
                    # build tree structure
                    parent = curr_qid
                    children[parent].append(q)

                    # queue for BFS
                    path_by_qid[q] = branch_path + [q]
                    next_frontier.append(q)
                    seen_qids.update(neigh_by_qid.get(q, {}).get("quadruple_ids", []))

        frontier = next_frontier

    # ── pretty-print the tree ---------------------------------------
    print("\n".join(_render_tree(seed_qid, children)), end="\n\n")

    return {
        "seen_qids": sorted(seen_qids),
        "collection_bucket": collection_bucket,
    }


# ── public wrapper --------------------------------------------------
def run_retriever(
    seed_qid: str,
    query_question: str,
    *,
    initial_seen: Set[str] | None = None,
) -> Dict[str, Any]:
    return react_loop(seed_qid, query_question, initial_seen=initial_seen)