"""
graph_reasoner.py
──────────────────
Depth-first *Graph-of-Thought* executor for GraphRAG
====================================================

High-level flow
---------------
1. **Seed selection** (done outside – see ``wrapper.py``) picks one or more
   “entry” quadruples by semantic similarity to the user question.

2. **DFS exploration** (this file):
   ┌─ For every edge:
   │   a. *Narrator* (`llm_helpers.py`) receives the running **context
          window** (question, prior narrator thoughts, planner rationales,
          etc.) **plus the single edge** currently under inspection and its
          source sentences.  
          It replies with **JSON** in the form  
          `{ "action": "think", "narrative": "..." }`.
          The narrator never stores anything and never ends the run.
   │   b. The edge & narrator thought form a *candidate* dictionary.
   │   c. *Planner* (`planner_helpers.py`) sees the full context **and** a
          list of neighbour edges.  
          It decides to
          • **branch** (many next edges),  
          • **pick**   (one next edge), or  
          • **stop**   (optionally giving a ``final_answer``).  
          Every planner action also includes  
          ``"store": "yes" | "no"`` telling whether the **previous edge** –
          i.e. the candidate – should be added to the global evidence bucket.
   │   d. DFS continues recursively according to the planner’s picks.
   └───────────────────────────────────────────────────────────────────

3. **Aggregation / final answer**
   * If *any* PlannerStop returned a ``final_answer`` we trust it and skip
     aggregation.
   * Else, when the DFS finishes (or when many seeds were explored),
     ``aggregate_answer()`` is called to turn the collected evidence into
     a concise reply.

Console trace legend
--------------------
🔗  GRAPH EDGE [qid]
📜 evidence …
💭  NARRATOR:
<narrative …>

📦  planner: STORED       (only printed when planner.store == “yes”)

🔀: single (1) / multi (k)
📝: <planner rationale(s)>

⏹  Depth limit reached   (MAX_DEPTH)
⏹  No neighbours – back-track
Parameters
----------
* ``MAX_DEPTH``   – maximum additional hops after the seed.
* ``NEIGH_LIMIT`` – limit of neighbour edges fetched from Neo4j per step.

2025-06-10 Finalised post-refactor:
• Narrator can **only** think (no final answer, no store flag).  
• Planner alone decides storage **and** termination.  
• Narrator store suggestion lines removed.

Additions (2025-06-13)
----------------------
* New optional parameter ``root_question``.
* Both questions are injected into the initial context window, labelled
  “MAIN QUESTION” and “SUB QUESTION”, so Narrator/Planner can see them.
"""

from __future__ import annotations

import json
import shutil
from typing import Dict, List, Optional, Set, Tuple

from graphrag.graphrag_agent.question_search import nearest_quadruple_ids
from graphrag.graphrag_agent.sentence_lookup import sentences_for_quadruples
from graphrag.graphrag_agent.neo4j_helpers import get_triple, get_neighbour_edges
from graphrag.graphrag_agent.llm_helpers import narrator_think, NarratorThink
from graphrag.graphrag_agent.planner_helpers import (
    planner_choose,
    PlannerBranch,
    PlannerPick,
    PlannerStop,
)
from graphrag.graphrag_agent.aggregator_helpers import aggregate_answer

# ── tunables ───────────────────────────────────────────────────────────
MAX_DEPTH = 3
NEIGH_LIMIT = 30
_TERM_COLS = shutil.get_terminal_size(fallback=(120, 20)).columns


# ── tiny pretty helpers (unchanged) ────────────────────────────────────
def _clip(t: str) -> str:
    return t if len(t) <= _TERM_COLS else t[: _TERM_COLS - 1] + "…"


def _p(depth: int, icon: str, text: str = "", clip: bool = True) -> None:
    indent = "│   " * depth + ("├─ " if depth else "")
    line = indent + icon + ": " + text
    print(_clip(line) if clip else line)


# ╔══════════════════════════════════════════════════════════════════════╗
# ║  Public entry                                                       ║
# ╚══════════════════════════════════════════════════════════════════════╝
def run_reasoning(
    question: str,                       # sub-question
    *,
    root_question: Optional[str] = None, # ← NEW
    seed_qid: Optional[str] = None,
    collected_bucket: Optional[List[dict]] = None,
    aggregate: bool = True,
) -> List[dict]:
    """
    Execute a Graph-of-Thought DFS from *seed_qid* (or the NN edge).

    Parameters
    ----------
    question         : sub-question in natural language.
    root_question    : original user query providing broader context (optional).
    seed_qid         : starting quadruple ID (optional).
    collected_bucket : shared evidence list across seeds.
    aggregate        : if True and no PlannerStop answer, call aggregator.
    """
    # 1 – pick seed ------------------------------------------------------
    if seed_qid is None:
        ids = nearest_quadruple_ids(question, k=1)
        if not ids:
            print("❗  No quadruple found.")
            return collected_bucket or []
        seed_qid = ids[0]

    collected: List[dict] = collected_bucket if collected_bucket is not None else []
    final_ans: Dict[str, Optional[str]] = {"text": None}

    print("\n🌳  Graph-of-Thought execution begins\n")
    if root_question:
        _p(0, "❓", f"MAIN QUESTION: {root_question}", clip=False)
    _p(0, "❓", f"SUB  QUESTION: {question}", clip=False)

    # ---- initial context window ---------------------------------------
    if root_question:
        context: List[str] = [
            "### MAIN QUESTION", root_question, "",
            "### SUB QUESTION",  question,
        ]
    else:
        context = ["### QUESTION", question]

    visited: Set[str] = {seed_qid}

    _dfs(
        depth=0,
        qid=seed_qid,
        question=question,
        context=context,
        visited=visited,
        collected=collected,
        final_ans=final_ans,
    )

    # 2 – dump evidence --------------------------------------------------
    print("\n📦  Collected evidence JSON")
    print(json.dumps(collected, indent=2) if collected else "[]")

    # 3 – answer ---------------------------------------------------------
    if final_ans["text"] is not None:
        print("\n✅  FINAL ANSWER (Planner)")
        print(final_ans["text"])
    elif aggregate:
        try:
            answer = aggregate_answer(question, collected)
            print("\n✅  FINAL AGGREGATED ANSWER")
            print(answer)
        except Exception as exc:
            print(f"\n⚠️  Aggregator error: {exc}")

    print("\n🏁  DFS finished\n")
    return collected


# ═══════════════════════════════════════════════════════════════════════
def _dfs(
    depth: int,
    qid: str,
    question: str,
    context: List[str],
    visited: Set[str],
    collected: List[dict],
    final_ans: Dict[str, Optional[str]],
) -> None:
    """
    Recursive DFS step.
    """
    if depth >= MAX_DEPTH:
        _p(depth, "⏹", "Depth limit reached")
        return

    # ── narrator step ──────────────────────────────────────────────────
    blk, candidate = _narrate_block(question, qid, context)
    context += blk
    _print_block(depth, blk)

    # ── fetch neighbours ───────────────────────────────────────────────
    neigh = get_neighbour_edges(qid, limit=NEIGH_LIMIT)
    if not neigh:
        _p(depth, "⏹", "No neighbours – back-track")
        return

    # ── planner decision ───────────────────────────────────────────────
    decision, _ = planner_choose("\n".join(context), _prompt_neigh(neigh))

    # … store? (planner flag only) --------------------------------------
    if getattr(decision, "store", "no").lower() == "yes":
        collected.append(candidate)
        _p(depth, "📦", "planner: STORED")

    # … stop? -----------------------------------------------------------
    if isinstance(decision, PlannerStop):
        _p(depth, "🔀", "stop")
        if decision.final_answer:
            final_ans["text"] = decision.final_answer.strip()
        return

    # … branch / pick ---------------------------------------------------
    picks = (
        [(decision.qid, decision.rationale)]
        if isinstance(decision, PlannerPick)
        else [(p.qid, p.rationale) for p in decision.picks]
    )

    tag = "single" if len(picks) == 1 else "multi"
    _p(depth, "🔀", f"{tag} ({len(picks)})")

    for nxt, rat in picks:
        _p(depth + 1, "📝", rat)
        if nxt in visited:
            _p(depth + 2, "↩️", f"already visited {nxt} – skip")
            continue
        visited.add(nxt)

        child_ctx = context.copy()
        child_ctx.append(f"### PLANNER RATIONALE [{nxt}] {rat}")

        _dfs(
            depth + 1,
            nxt,
            question,
            child_ctx,
            visited,
            collected,
            final_ans,
        )


# ═════════════════ narrator helpers ════════════════════════════════════
def _narrate_block(
    question: str, qid: str, context: List[str]
) -> Tuple[List[str], dict]:
    """
    Call the narrator on *qid* and build the printable block **and**
    candidate evidence dict (not stored yet).
    """
    triple = get_triple(qid) or ("?", "?", "?")
    subj, pred, obj = triple
    ev = sentences_for_quadruples([qid]) or [{}]
    sentences = ev[0].get("sentences", [])
    inferred = ev[0].get("inferred", False)

    hdr = f"### GRAPH EDGE   [{qid}] {'(inferred)' if inferred else '(extracted)'}"
    line = f"({subj}) —{pred}→ ({obj})"
    edge_part = [hdr, line] + [f'evidence: "{s}"' for s in sentences]

    rsp: NarratorThink = narrator_think("\n".join(context + [""] + edge_part))

    blk = edge_part + ["", "### NARRATOR THOUGHT", rsp.narrative.strip()]

    candidate = {
        "qid": qid,
        "triple": triple,
        "sentences": sentences,
        "narrative": rsp.narrative.strip(),
    }
    return blk, candidate


def _print_block(depth: int, blk: List[str]) -> None:
    """
    Pretty-print narrator block with icons and indent.
    """
    for ln in blk:
        if ln.startswith("### GRAPH EDGE"):
            _p(depth, "🔗", ln.split("   ")[1])
        elif ln.startswith("("):
            _p(depth, "    " + ln)
        elif ln.startswith("evidence:"):
            _p(depth, "📜", " " + ln.split(":", 1)[1].strip())
        elif ln.startswith("### NARRATOR"):
            _p(depth, "💭", "NARRATOR:")
        else:
            _p(depth, "   " + ln)


def _prompt_neigh(neigh) -> List[str]:
    """
    Build the neighbour-edge block shown to the planner.
    """
    lines: List[str] = []
    for i, nb in enumerate(neigh, 1):
        tag = "inf" if nb["inferred"] else "ext"
        triple = f"({nb['from_node']}) —{nb['predicate']}→ ({nb['to_node']})"
        lines += [f"### CANDIDATE EDGE #{i}   [{nb['qid']}] ({tag})", triple]
        lines += [f'evidence: "{s}"' for s in nb["sentences"]]
        lines.append("")
    return lines