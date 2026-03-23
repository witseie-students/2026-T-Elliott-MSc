"""
Scientific‑style visualiser – coloured outlines + bold headings
==============================================================
• Bold role heading on top of each node (HTML‑label).
• Distinct coloured border per role; light neutral fill.
• Fixed *answer* regex so GraphRAG answers are correctly classified.
"""
from __future__ import annotations

import html, itertools, re, textwrap
from datetime import datetime
from importlib import import_module
from pathlib import Path
from typing import Any, Dict, List, Tuple

try:
    import graphviz  # type: ignore
except ImportError as exc:
    raise ImportError("pip install graphviz (and system binaries)") from exc

BASE_DIR = Path(__file__).resolve().parent
OUT_DIR  = (BASE_DIR.parent / "static" / "tot_trees").resolve(); OUT_DIR.mkdir(parents=True, exist_ok=True)

WRAP, MAX_BULLETS = 40, 7

_id: itertools.count[int]
LINE2ID: Dict[str, str]
PARENT_IDS: List[str]

# Greyscale fill + coloured outline (Apple-esque accent)
STYLE: Dict[str, Tuple[str, str]] = {
    "root":      ("#0A84FF", "#FFFFFF"),
    "narrative": ("#8E8E93", "#F7F7F7"),
    "rumsfeld":  ("#FF9F0A", "#FDF8F2"),   # ← NEW (orange border)
    "plan":      ("#BF5AF2", "#F7F7F7"),
    "question":  ("#64D2FF", "#F7F7F7"),
    "answer":    ("#30D158", "#F7F7F7"),
    "final":     ("#34C759", "#F7F7F7"),
    "branch":    ("#FFD60A", "#F7F7F7"),
    "stop":      ("#FF453A", "#F7F7F7"),
    "bundle":    ("#8E8E93", "#FFFFF7"),
}

ROLE_HEAD = {
    "root": "Question",
    "narrative": "Narrator",
    "rumsfeld": "Rumsfeld",
    "plan": "Plan",
    "question": "Query",
    "answer": "Answer",
    "final": "Answer",
    "branch": "Branch",
    "stop": "Depth-Limit",
    "bundle": "Bundle",
}

_RX = [                                           # ← add detection for Rumsfeld lines
    ("root", re.compile(r"^ORIGINAL QUESTION:", re.I)),
    ("narrative", re.compile(r"^NARRATIVE", re.I)),
    ("rumsfeld", re.compile(r"^RUMSFELD", re.I)),
    ("plan", re.compile(r"^PLAN", re.I)),
    ("question", re.compile(r"^QUESTION", re.I)),
    ("answer", re.compile(r"^ANSWER [\d.]+:", re.I)),
    ("final", re.compile(r"^FINAL ANSWER", re.I)),
    ("branch", re.compile(r"^BRANCH", re.I)),
    ("stop",  re.compile(r"\[stopped:", re.I)),
]

def _kind(line: str) -> str:
    for k, rx in _RX:
        if rx.search(line):
            return k
    return "narrative"

def _wrap(txt: str) -> List[str]:
    return textwrap.wrap(txt, WRAP) or [txt]

def _nid() -> str:
    return f"n{next(_id)}"


def _html_label(role: str, lines: List[str]) -> str:
    esc = lambda t: html.escape(t, quote=True)
    body = "<BR ALIGN='LEFT'/>".join(esc(l) for l in lines)
    return f"<<TABLE BORDER='0' CELLBORDER='0' CELLPADDING='2'><TR><TD ALIGN='LEFT'><B>{esc(role)}</B></TD></TR><TR><TD ALIGN='LEFT'>{body}</TD></TR></TABLE>>"


def _ensure_node(g: "graphviz.Digraph", line: str) -> str:
    if line in LINE2ID:
        return LINE2ID[line]

    nid  = _nid(); LINE2ID[line] = nid
    kind = _kind(line)
    border_col, fill_col = STYLE[kind]
    shape = "box" if kind != "branch" else "diamond"
    style = "rounded,filled" + (",dashed" if kind == "stop" else "")

    content = re.split(r":\s+", line, 1)[-1].strip() or line
    label   = _html_label(ROLE_HEAD[kind], _wrap(content))

    g.node(
        nid,
        label=label,
        shape=shape,
        style=style,
        fillcolor=fill_col,
        color=border_col,
        fontname="Times New Roman",
        fontsize="9",
        penwidth="2" if kind in {"answer", "final"} else "1",
        margin="0.05,0.03",
    )

    if kind in {"final", "stop"}:
        PARENT_IDS.append(nid)
    return nid


def _walk(g: "graphviz.Digraph", node: Dict[str, Any], prev: List[str], parent: str | None):
    trace = node.get("trace", [])
    for ln in trace[len(prev):]:
        if not ln.strip():
            continue
        nid = _ensure_node(g, ln)
        if parent:
            g.edge(parent, nid, color="#7F7F7F", penwidth="0.7")
        parent = nid
    for child in (node.get("children") or {}).values():
        _walk(g, child, trace, parent)

# ── Public API ────────────────────────────────────────────────────────────

def save_tree_image(tree: Dict[str, Any], *, bundles: List[Dict[str, Any]] | None = None, aggregate: str | None = None, fmt: str = "png", out_dir: str | Path | None = None) -> Path:
    try:
        fmts = getattr(import_module("graphviz.backend"), "FORMATS", None)
    except Exception:
        fmts = None
    if fmts and fmt.lower() not in fmts:
        raise ValueError("Unsupported format")

    out = Path(out_dir or OUT_DIR); out.mkdir(parents=True, exist_ok=True)
    fname = "tot_" + datetime.utcnow().isoformat(timespec="seconds").replace(":", "-")

    g = graphviz.Digraph(
        "ToT",
        filename=fname,
        format=fmt.lower(),
        directory=str(out),
        graph_attr={"rankdir": "TB", "dpi": "120", "fontname": "Times New Roman"},
        node_attr={"margin": "0.05,0.03"},
    )

    global _id, LINE2ID, PARENT_IDS
    _id = itertools.count(1); LINE2ID, PARENT_IDS = {}, []

    _walk(g, tree, [], None)

    parent_iter = iter(PARENT_IDS)
    for b in bundles or []:
        txt = b.get("answer", "(no answer)")
        # build a *flat* list of wrapped lines
        lines: List[str] = _wrap(txt)
        for reason in b.get("reasoning", [])[:MAX_BULLETS]:
            lines.extend(_wrap(reason))
        if (conf := b.get("confidence")) is not None:
            lines.append(f"confidence: {conf:.2f}")

        bid = _nid()
        b_label = _html_label(ROLE_HEAD["bundle"], lines)
        border, fill = STYLE["bundle"]
        g.node(
            bid,
            label=b_label,
            shape="note",
            style="filled",
            fillcolor=fill,
            color=border,
            fontname="Times New Roman",
            fontsize="9",
        )
        if (parent := next(parent_iter, None)):
            g.edge(parent, bid, style="dashed", color="#A0A0A0", penwidth="0.8")

    return Path(g.render(cleanup=True))
