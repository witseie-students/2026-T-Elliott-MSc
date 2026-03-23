"""
trace_prettifier.py
───────────────────
Render Markdown traces as compact, icon-rich Trees-of-Thought.

Additions (2025-06-03)
----------------------
• ℹ️  *INFO* rows coming from the reasoner now include the planner’s
  assessment of how many candidate “plans” exist at that turn:
      frontier=3 depth=1 plans=single (1)
      frontier=4 depth=2 plans=multiple (5)

  These are parsed and shown in the tree (clipped when necessary).

Public API
----------
markdown_to_tree(markdown: str) -> str
"""
from __future__ import annotations

import re
import shutil
from typing import List

# ── dynamic terminal width ─────────────────────────────────────────────
_TERM_WIDTH = shutil.get_terminal_size(fallback=(80, 20)).columns
WIDTH       = max(40, _TERM_WIDTH)            # keep at least 40 chars

# ── tree glyphs & icons ────────────────────────────────────────────────
INDENT_UNIT  = "│   "
BRANCH_MARK  = "├─ "

ICON_Q          = "❓"
ICON_EDGE       = "🔗"
ICON_EVIDENCE   = "📜"
ICON_PLANNER    = "🔀"
ICON_STOP       = "🛑"
ICON_NARR_THINK = "💭"
ICON_NARR_FINAL = "💡"
ICON_STORE_YES  = "📦"
ICON_STORE_NO   = "🚫"
ICON_INFO       = "ℹ️"       # new

# ── regex helpers ──────────────────────────────────────────────────────
_RE_EDGE_HDR   = re.compile(r"### GRAPH EDGE\s+\[(?P<qid>[^\]]+)\]\s+\((?P<t>inferred|extracted)\)")
_RE_PLANNER_EX = re.compile(r"### PLANNER DECISION – EXPAND \[(?P<qid>[^\]]+)\]")
_RE_INFO       = re.compile(r"### INFO (?P<body>.+)")

# ╔═════════════════════════════════════════════════════════════════════╗
# ║  Tree renderer                                                      ║
# ╚═════════════════════════════════════════════════════════════════════╝
def markdown_to_tree(md: str) -> str:
    """
    Convert the given Markdown trace into a single-string tree view.
    """
    lines = md.splitlines()
    out: List[str] = ["🌳  GraphRAG execution begins"]

    depth = 0
    evidence_buf: List[str] = []

    for idx, raw in enumerate(lines):
        line = raw.strip()

        # QUESTION -------------------------------------------------------
        if line == "### QUESTION":
            _emit(out, depth, f"{ICON_Q}: {lines[idx + 1].strip()}")
            continue

        # GRAPH EDGE header ---------------------------------------------
        if m := _RE_EDGE_HDR.match(line):
            qid, kind = m.groups()
            triple = lines[idx + 1].strip() if idx + 1 < len(lines) else "?"
            tag = "inferred" if kind == "inferred" else "extracted"
            depth = max(depth, 1)
            _emit(out, depth, f"{ICON_EDGE} [{qid}] ({tag}) {triple}")
            evidence_buf.clear()
            continue

        # evidence -------------------------------------------------------
        if line.startswith('evidence: "'):
            evidence_buf.append(line[len('evidence: "'):-1])
            continue

        # narrator thought / final --------------------------------------
        if line.startswith("### NARRATOR THOUGHT"):
            _dump_evidence(out, depth, evidence_buf)
            _emit(out, depth, f"{ICON_NARR_THINK}: {_collect_block(lines, idx + 1)}")
            continue

        if line.startswith("### NARRATOR FINAL THOUGHT"):
            _dump_evidence(out, depth, evidence_buf)
            _emit(out, depth, f"{ICON_NARR_FINAL}: {_collect_block(lines, idx + 1)}")
            continue

        # INFO rows (frontier/depth/plans) ------------------------------
        if m := _RE_INFO.match(line):
            _dump_evidence(out, depth, evidence_buf)
            _emit(out, depth, f"{ICON_INFO}: {m.group('body')}")
            continue

        # store decision -------------------------------------------------
        if line.startswith("→ Store this context?"):
            ok = "YES" in line.upper()
            _emit(out, depth, f"{ICON_STORE_YES if ok else ICON_STORE_NO}  store = {'yes' if ok else 'no'}")
            continue

        # planner expand / stop -----------------------------------------
        if m := _RE_PLANNER_EX.match(line):
            qid = m.group("qid")
            rationale = _collect_block(lines, idx + 1) or "…"
            _emit(out, depth, f"{ICON_PLANNER}: expand **{qid}** – {rationale}")
            depth += 1
            continue

        if line.startswith("### PLANNER DECISION – STOP"):
            rationale = _collect_block(lines, idx + 1) or "…"
            _emit(out, depth, f"{ICON_STOP}: {rationale}")
            depth = 0
            continue

        # final answer ---------------------------------------------------
        if line.startswith("### FINAL ANSWER"):
            _emit(out, depth, f"{ICON_NARR_FINAL}: {_collect_block(lines, idx + 1)}")
            continue

    return "\n".join(out)


# ╔═════════════════════════════════════════════════════════════════════╗
# ║  helpers                                                           ║
# ╚═════════════════════════════════════════════════════════════════════╝
def _emit(out: List[str], depth: int, body: str) -> None:
    prefix = INDENT_UNIT * depth + BRANCH_MARK
    avail  = WIDTH - len(prefix)
    clipped = body if len(body) <= avail else body[: avail - 1] + "…"
    out.append(prefix + clipped)

def _dump_evidence(out: List[str], depth: int, buf: List[str]) -> None:
    for ev in buf:
        _emit(out, depth, f"{ICON_EVIDENCE}: {ev}")
    buf.clear()

def _collect_block(lines: List[str], start: int) -> str:
    acc: List[str] = []
    for j in range(start, len(lines)):
        t = lines[j]
        if not t or t.startswith("### "):
            break
        acc.append(t.strip())
    return " ".join(acc)