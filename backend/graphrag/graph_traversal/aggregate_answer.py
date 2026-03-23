# graphrag/graph_traversal/aggregate_answer.py
# ═════════════════════════════════════════════
"""
Turn a collection-bucket of evidence into
(1) a long-form answer and (2) a yes / maybe / no decision.
"""

from __future__ import annotations

import json
from typing import List, Dict, Tuple

from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError

from django.conf import settings

# ── OpenAI client ────────────────────────────────────────────────────
MODEL_NAME     = "gpt-4.1-nano"
_client = OpenAI(api_key=settings.OPENAI_API_KEY)


# ── schema for the yes/no/maybe decider ─────────────────────────────
class _Decision(BaseModel):
    decision: str = Field(pattern="^(yes|no|maybe)$")


# ── internal helper LLM calls ───────────────────────────────────────
def _aggregator_agent(question: str,
                      bucket: List[Dict[str, str]]) -> str:
    """Return a free-text synthesis (no JSON)."""
    sys_prompt = (
        "Combine all of the propositions below into a natural paragraph. Use none of your own information. Do not encorporate any biases from the reasoning or any of your own information.\n\n"
    )
    user_content = json.dumps(
        {
            "evidence": bucket,
        },
        indent=2,
    )
    resp = _client.chat.completions.create(
        model=MODEL_NAME,
        temperature=0.2,
        messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "user",   "content": user_content},
        ],
    )
    return resp.choices[0].message.content.strip()


def _decider_agent(question: str, long_answer: str) -> str:
    """Return 'yes' / 'no' / 'maybe'."""
    sys_prompt = (
        "Return ONLY a JSON object {'decision': 'yes'|'no'|'maybe'} indicating "
        "whether the answer implies YES, NO, or MAYBE to the question."
    )
    user_json = json.dumps(
        {
            "question": question,
            "answer":   long_answer,
        },
        indent=2,
    )
    resp = _client.chat.completions.create(
        model=MODEL_NAME,
        temperature=0.0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "user",   "content": user_json},
        ],
    )

    # robust JSON parse with fallback to "maybe"
    try:
        return _Decision.model_validate_json(resp.choices[0].message.content).decision
    except (ValidationError, json.JSONDecodeError):
        try:
            return json.loads(resp.choices[0].message.content).get("decision", "maybe")
        except Exception:  # still malformed
            return "maybe"


# ── PUBLIC API ──────────────────────────────────────────────────────
def generate_answer(question: str,
                    collection_bucket: List[Dict[str, str]]
                    ) -> Tuple[str, str]:
    """Return (long_answer_text, yes_no_maybe_decision)."""
    long_answer = _aggregator_agent(question, collection_bucket)
    decision    = _decider_agent(question, long_answer)
    return long_answer, decision