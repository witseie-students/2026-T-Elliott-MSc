"""
planner_helpers.py
──────────────────
LLM-driven planner for GraphRAG – now also decides whether to
*store* the just-seen edge and may deliver the **final answer**.
"""
from __future__ import annotations

from typing import List, Literal, Optional, Tuple, Union
from pydantic import BaseModel, ValidationError
from openai import OpenAI

from .llm_helpers import API_KEY

MODEL  = "gpt-4o-mini-2024-07-18"
client = OpenAI(api_key=API_KEY)

# ── output schemas ─────────────────────────────────────────────────────
class _PickItem(BaseModel):
    qid: str
    rationale: str

class _CommonStore(BaseModel):
    # mix-in so every action carries the decision
    store: Literal["yes", "no"] = "no"

class PlannerBranch(_CommonStore):
    action: Literal["branch"]
    picks:  List[_PickItem]

class PlannerPick(_CommonStore):
    action: Literal["pick"]
    qid:    str
    rationale: str

class PlannerStop(_CommonStore):
    action: Literal["stop"]
    rationale: str
    final_answer: Optional[str] = None

PlannerOutput = Union[PlannerBranch, PlannerPick, PlannerStop]

# ── system prompt ──────────────────────────────────────────────────────
PLANNER_SYS = """
You are the *Planner* in a graph-of-thought loop.

Input you see:
• The running context stream (question, narrator thoughts, etc.).
• A list of neighbour edges.

Decide what to do next and ALSO whether to retain the **previous edge**.

Return JSON in one of three schemas.

branch   – explore many edges next
{
  "action": "branch",
  "store":  "yes" | "no",          // keep the previous edge?
  "picks": [
    {"qid": "<edge-id>", "rationale": "<why follow>"},
    ...
  ]
}

pick     – explore a single edge
{
  "action": "pick",
  "store":  "yes" | "no",
  "qid":    "<edge-id>",
  "rationale": "<why>"
}

stop     – finished
{
  "action": "stop",
  "store":  "yes" | "no",
  "rationale":  "<why stop>",
  "final_answer": "<answer text if you have it>"
}
""".strip()


# ── helper ------------------------------------------------------------------
def planner_choose(
    context_window: str,
    neighbour_blocks: List[str],
) -> Tuple[PlannerOutput, str]:
    """
    Returns
    -------
    (decision_object, raw_json_string)
    """
    prompt = context_window + "\n\n" + "\n".join(neighbour_blocks)
    msgs   = [
        {"role": "system", "content": PLANNER_SYS},
        {"role": "user",   "content": prompt},
    ]

    try:
        rsp = client.chat.completions.create(
            model           = MODEL,
            temperature     = 0,
            response_format = {"type": "json_object"},
            messages        = msgs,
        )
        raw = rsp.choices[0].message.content
    except Exception as exc:
        raise RuntimeError(f"Planner LLM error: {exc}") from None

    for schema in (PlannerBranch, PlannerPick, PlannerStop):
        try:
            return schema.model_validate_json(raw), raw
        except ValidationError:
            continue
    raise RuntimeError("Planner JSON did not match any schema")