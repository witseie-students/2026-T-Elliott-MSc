"""
llm_helpers.py
──────────────
Narrator functionality – stripped of any storage decision.

Author: <you> · 2025-06-10
"""
from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ValidationError
from openai import OpenAI
from django.conf import settings

# ── OpenAI client setup ────────────────────────────────────────────────
API_KEY = settings.OPENAI_API_KEY
MODEL   = "gpt-4o-mini"
client  = OpenAI(api_key=API_KEY)

# ── output schema ──────────────────────────────────────────────────────
class NarratorThink(BaseModel):
    action: Literal["think"]
    narrative: str                         # ← only field left besides action

NarratorOutput = NarratorThink

# ── system prompt ──────────────────────────────────────────────────────
NARRATOR_SYS = """
You are the *Reasoner* in a Tree-of-Thought loop.

Given a main question and a sub-question and one knowledge-graph edge (plus its evidence),
think aloud about whether – and how – this edge could contribute to
answering either the main question or the sub-question. 

Return **valid JSON** in *exactly* this schema:

{
  "action": "think",
  "narrative": "<inner monologue reasoning on whether this evidence contributes toward answering the question as well as any ambiguity and missing context that could be involved>"
}

Rules
• Do NOT attempt to give a final answer.
• Do NOT invent facts – rely only on the evidence shown.
""".strip()


# ── narrator call helper ───────────────────────────────────────────────
def narrator_think(context_window: str) -> NarratorOutput:
    """
    Call the narrator LLM and return a validated response.
    """
    msgs = [
        {"role": "system", "content": NARRATOR_SYS},
        {"role": "user",   "content": context_window},
    ]

    try:
        rsp = client.chat.completions.create(
            model           = MODEL,
            temperature     = 0,
            response_format = {"type": "json_object"},
            messages        = msgs,
        )
        raw = rsp.choices[0].message.content
        return NarratorThink.model_validate_json(raw)

    except ValidationError as exc:
        raise RuntimeError(f"Narrator JSON invalid: {exc}") from None
    except Exception as exc:
        raise RuntimeError(f"OpenAI error: {exc}") from None