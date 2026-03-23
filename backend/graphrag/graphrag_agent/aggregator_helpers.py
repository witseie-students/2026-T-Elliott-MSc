"""
aggregator_helpers.py
─────────────────────
*Aggregator* LLM: turns the **collected-evidence JSON** into a concise
final answer.

2025-06-13  NEW:
    • Optional ``root_question`` parameter.
    • When provided, the system prompt changes: the Aggregator now acts like a
      librarian – first answering the SUB question, then adding context that
      may help with the MAIN question.
"""

from __future__ import annotations

import json
from typing import Literal, Optional
from pydantic import BaseModel, ValidationError
from openai import OpenAI

from .llm_helpers import API_KEY          # reuse the existing key

MODEL  = "gpt-4o-mini"
client = OpenAI(api_key=API_KEY)

# ── output schema ──────────────────────────────────────────────────────
class AggregatorAnswer(BaseModel):
    action: Literal["answer"]
    answer: str


# ── dynamic system prompts ─────────────────────────────────────────────
_BASE_SYS = """
You are the *Aggregator* at the end of a graph-of-thought pipeline.

Input
-----
• A natural-language QUESTION                                  {extra_header}
• A JSON array `evidence` – each element contains:
      qid, triple, sentences[], narrative, (optional) final_answer.

Task
----
Produce a SINGLE, correct answer **only** from the provided evidence.
If evidence is conflicting or insufficient, say so explicitly.

Respond in strict JSON:

{{
  "action": "answer",
  "answer": "<your final answer>"
}}
""".strip()

_LIBRARIAN_ADDITION = """
Your role is like a librarian:

1. Begin with: “Here’s what I found about <SUB QUESTION>…”.
2. Summarise the evidence relevant to the sub-question.
3. Then add: “Additionally, this may help with <MAIN QUESTION>…”.
4. Summarise any other evidence that could inform the main question.

Do not ever include any of your own information.
""".strip()


def _build_system_prompt(
    sub_question: str,
    root_question: Optional[str],
) -> str:
    """
    Create the appropriate system prompt depending on whether the caller
    provided both questions or only the sub-question.
    """
    if root_question:
        extra = (
            "\n• SUB QUESTION  : "
            + sub_question
            + "\n• MAIN QUESTION : "
            + root_question
        )
        return _BASE_SYS.format(extra_header=extra) + "\n" + _LIBRARIAN_ADDITION
    # fallback – previous behaviour
    return _BASE_SYS.format(extra_header="")


# ── public helper -------------------------------------------------------
def aggregate_answer(
    sub_question: str,
    evidence: list,
    *,
    root_question: Optional[str] = None,
) -> str:
    """
    Parameters
    ----------
    sub_question : str
        The immediate branch-level question.
    evidence : list
        Collected evidence JSON.
    root_question : str | None
        The overarching user query (optional).

    Returns
    -------
    str – aggregated answer.
    """
    sys_prompt = _build_system_prompt(sub_question, root_question)

    msgs = [
        {"role": "system", "content": sys_prompt},
        # Always include the sub-question first for backward compatibility
        {"role": "user",  "content": f"SUB QUESTION:\n{sub_question}"},
    ]
    if root_question:
        msgs.append({"role": "user", "content": f"MAIN QUESTION:\n{root_question}"})
    msgs.append({"role": "user", "content": json.dumps(evidence, indent=2)})

    try:
        rsp = client.chat.completions.create(
            model=MODEL,
            temperature=0,
            response_format={"type": "json_object"},
            messages=msgs,
        )
        raw = rsp.choices[0].message.content
    except Exception as exc:
        raise RuntimeError(f"Aggregator LLM error: {exc}")

    try:
        obj = AggregatorAnswer.model_validate_json(raw)
    except ValidationError as exc:
        raise RuntimeError(f"Aggregator JSON invalid: {exc}")
    return obj.answer.strip()