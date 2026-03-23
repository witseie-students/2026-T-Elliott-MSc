# graphrag/graph_traversal/agent.py
# ════════════════════════════════════════════════════════════════════
"""
ReAct agents.

• thought_agent  – live (LLM)
• planner_agent – live (LLM) deciding stop / which QIDs to explore

Latency for every call is printed, e.g.
    [LLM-time] THOUGHT  0.83 s
    [LLM-time] PLANNER  1.12 s
"""

from __future__ import annotations
import json
import time                                 # ← NEW
from typing import Dict, Any, List

from openai import OpenAI

from django.conf import settings

# ── OpenAI client ────────────────────────────────────────────────────

MODEL_NAME     = "gpt-4.1-nano"
_client = OpenAI(api_key=settings.OPENAI_API_KEY)


# ===================================================================
#  THOUGHT AGENT
# ===================================================================
def thought_agent(context_chain: List[Dict[str, Any]],
                  question: str) -> Dict[str, Any]:
    sys_prompt = (
        "You are the THOUGHT phase in a ReAct graph-traversal agent.\n"
        "Given the biomedical question and the current proposition, decide:\n"
        "  • 'reasoning'  – concise ≤50 words explaining usefulness and what's missing if it does not completely answer the question\n"
        "  • 'save'       – true  if proposition helps answer the question in any way at all; false otherwise\n"
        "Return ONLY a JSON object matching this schema exactly."
    )
    user_json = json.dumps(
        {
            "question":    question,
            "proposition": context_chain[-1]["proposition"],
        },
        indent=2,
    )

    t0 = time.perf_counter()                       # ← start timer
    resp = _client.chat.completions.create(
        temperature=0.0,
        model=MODEL_NAME,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "user",   "content": user_json},
        ],
    )
    dt = time.perf_counter() - t0                  # ← elapsed
    print(f"[LLM-time] THOUGHT  {dt:5.2f}s")       # ← print latency

    return json.loads(resp.choices[0].message.content)


# ===================================================================
#  PLANNER AGENT
# ===================================================================
def planner_agent(context_chain: List[Dict[str, Any]],
                  neighbours: List[Dict[str, Any]],
                  question: str) -> Dict[str, Any]:

    if not neighbours:
        return {
            "action": "stop",
            "selected_qids": [],
            "reasoning": "No unseen neighbours available.",
        }

    sys_prompt = (
        "You are the PLANNER phase of a ReAct graph-traversal agent.\n"
        "Given the biomedical question, the traversal history (context_chain), "
        "and candidate neighbouring propositions, decide which of these neighbours to explore that might help answer the question.\n\n"
        "Return ONLY JSON with keys:\n"
        "  'action'        – 'stop' or 'expand'\n"
        "  'selected_qids' – list[str] of QIDs to explore if action=='expand'\n"
        "  'reasoning'     – ≤60 words justifying why exploring these propositions might be a good idea\n\n"
        "Guidelines:\n"
        "• Stop if the gathered info already answers the question or neighbours seem irrelevant.\n"
    )

    user_json = json.dumps(
        {
            "question": question,
            "context_chain": context_chain,
            "candidates": neighbours,
        },
        indent=2,
    )

    t0 = time.perf_counter()                       # ← start timer
    resp = _client.chat.completions.create(
        temperature=0.0,
        model=MODEL_NAME,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "user",   "content": user_json},
        ],
    )
    dt = time.perf_counter() - t0                  # ← elapsed
    print(f"[LLM-time] PLANNER {dt:5.2f}s")        # ← print latency

    return json.loads(resp.choices[0].message.content)