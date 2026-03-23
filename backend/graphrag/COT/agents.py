# COT/agents.py
# ═════════════════════════════════════════════════════════════
"""
Chain-of-Thought (CoT) wrapper with five collaborating LLM agents
plus an external static retriever:

    ┌──────────────────┐
    │ planner_agent    │   «Given the context, which facts are still
    └──────────────────┘     missing to answer the question?»
              │
              ▼
    ┌──────────────────┐
    │ questioner_agent │   «Ask ONE atomic, self-contained question
    └──────────────────┘     that reveals the next missing fact.»
              │
              ▼
      graphrag_answer()      ← static Graph-RAG retriever
              │
              ▼
    ┌──────────────────┐
    │ reflection_agent │   «Do we have enough?  If yes, stop – else
    └──────────────────┘     reflect and iterate.»
              │
              ▼   (loop until answer_ready==True or wall-clock limit)
    ┌──────────────────┐
    │ aggregator_agent │   «Stitch the gathered facts into ONE
    └──────────────────┘     paragraph starting with yes/no/maybe.»
              │
              ▼
    ┌──────────────────┐
    │ classifier_agent │   «Return {"final":"yes|no|maybe"}»
    └──────────────────┘

`cot_controller(question, *, depth=1, time_limit=100)` drives the loop
and returns the entire *context-chain* (`list[dict]`).

All chat calls use **GPT-4-nano**.  Swap `MODEL_NAME` if desired.
"""

from __future__ import annotations

import json
import time
from typing import Dict, List

from openai import OpenAI
from pydantic import BaseModel, ValidationError

from graphrag.graph_algorithm.wrapper import graphrag_answer

from django.conf import settings


# ─────────────────────────────────────────────────────────────
#  OpenAI client
# ─────────────────────────────────────────────────────────────

MODEL_NAME     = "gpt-4.1-nano"
_client = OpenAI(api_key=settings.OPENAI_API_KEY)

# ─────────────────────────────────────────────────────────────
# helper: wrap chat-completion
# ─────────────────────────────────────────────────────────────
def _chat_completion(
    system: str,
    user: str,
    *,
    temperature: float = 0.0,
) -> str:
    """Call the chat-completion endpoint and return **stripped** text."""
    resp = _client.chat.completions.create(
        model=MODEL_NAME,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
    )
    return resp.choices[0].message.content.strip()


# ─────────────────────────────────────────────────────────────
# 1) PLANNER
# ─────────────────────────────────────────────────────────────
def planner_agent(context_chain: List[Dict[str, str]]) -> str:
    """
    Emit ≤ 3 bullet points describing which *concrete facts* are still
    required to confidently answer the original question.
    """
    sys = (
        "You are the *planner* in a CoT system.\n"
        "In a paragraph, output your thoughts on what needs to be known to answer the question."
    )
    user = json.dumps({"context_chain": context_chain}, indent=2)
    return _chat_completion(sys, user, temperature=0.0)


# ─────────────────────────────────────────────────────────────
# 2) QUESTIONER
# ─────────────────────────────────────────────────────────────
def questioner_agent(context_chain: List[Dict[str, str]]) -> str:
    """
    Produce ONE standalone biomedical question (no pronouns, no references)
    whose answer would best progress the reasoning.
    """
    sys = (
        "You are the *questioner*.\n"
        "Craft ONE atomic, self-contained biomedical question that, when "
        "answered, fills the next most important knowledge gap."
    )
    user = json.dumps({"context_chain": context_chain}, indent=2)
    return _chat_completion(sys, user, temperature=0.0)


# ─────────────────────────────────────────────────────────────
# 3) REFLECTION
# ─────────────────────────────────────────────────────────────
class _Reflection(BaseModel):
    """Schema enforced on the reflection agent output."""
    answer_ready: bool
    reflection: str


def reflection_agent(context_chain: List[Dict[str, str]]) -> _Reflection:
    """
    Decide, via JSON, whether a satisfactory final answer paragraph is
    already present.  Always returns a valid `_Reflection`.
    """
    sys = (
        "You are a *self-reflection* agent that thinks about whether or not the question has been answered.\n"
        "Return ONLY JSON of the exact form:\n"
        '{ "answer_ready": <true|false>, "reflection": "<≤3 sentences>" }'
    )
    user = json.dumps({"context_chain": context_chain}, indent=2)
    raw  = _chat_completion(sys, user, temperature=0.0)

    try:
        return _Reflection.model_validate_json(raw)
    except (ValidationError, json.JSONDecodeError):
        return _Reflection(answer_ready=False, reflection="Parser error – continue.")


# ─────────────────────────────────────────────────────────────
# 4) AGGREGATOR  – custom prompt
# ─────────────────────────────────────────────────────────────
def aggregator_agent(context_chain: List[Dict[str, str]]) -> str:
    """
    Build ONE concise paragraph that **starts** with “yes,” “no,” or “maybe,”
    then justifies the stance using *only* information from RETRIEVER steps.
    """
    question = context_chain[0]["content"]
    evidence = "\n\n".join(
        step["content"] for step in context_chain if step["role"] == "retriever"
    )

    sys = (
        "You are the *aggregator* agent.\n"
        "Using ONLY the evidence paragraphs provided, write ONE cohesive "
        "paragraph that answers the biomedical question.\n"
        "• The paragraph MUST begin with exactly one of: Yes, No, or Maybe \n"
        "• Do NOT introduce new knowledge.\n"
    )
    user = json.dumps(
        {
            "question": question,
            "evidence_paragraphs": evidence,
            "instructions": "Start with yes/no/maybe, then justification.",
        },
        indent=2,
    )

    paragraph = _chat_completion(sys, user, temperature=0.0)

    # safety-net: enforce prefix if the LLM forgot
    if not paragraph.lstrip().lower().startswith(("yes", "no", "maybe")):
        paragraph = "maybe, " + paragraph.lstrip()

    return paragraph


# ─────────────────────────────────────────────────────────────
# 5) CLASSIFIER  – paragraph → yes|no|maybe
# ─────────────────────────────────────────────────────────────
class _Decision(BaseModel):
    decision: str  # yes | no | maybe


def classifier_agent(paragraph: str) -> str:
    """
    Map the aggregated paragraph to {'decision':'yes|no|maybe'} via a tiny LLM
    call.  Falls back to “maybe” on parse glitches.
    """
    sys = (
        "Return ONLY a JSON object {'decision': 'yes'|'no'|'maybe'} indicating "
        "whether the answer implies YES, NO, or MAYBE to the question."
    )
    raw = _chat_completion(sys, paragraph, temperature=0.0)

    try:
        return _Decision.model_validate_json(raw).decision
    except (ValidationError, json.JSONDecodeError):
        return "maybe"



# ─────────────────────────────────────────────────────────────
# Controller
# ─────────────────────────────────────────────────────────────
def cot_controller(
    original_question: str,
    *,
    depth: int = 1,
    time_limit: int = 100,
) -> List[Dict[str, str]]:
    """
    Execute planner → questioner → retriever → reflection cycles until
    `answer_ready` or the wall-clock `time_limit` (s) is hit.

    The returned context-chain always ends with:
      • an *aggregator* paragraph
      • a *classifier* label
      • a *system* note  «Total loops: <n>»
    """
    t0   = time.perf_counter()
    loops = 0                                                     # ← counter
    ctx: List[Dict[str, str]] = [{"role": "question", "content": original_question}]

    while True:
        loops += 1                                                # ─── loop ++

        # 1) plan
        ctx.append({"role": "planner", "content": planner_agent(ctx)})

        # 2) ask follow-up
        q_next = questioner_agent(ctx)
        ctx.append({"role": "questioner", "content": q_next})

        # 3) retrieve
        ctx.append(
            {
                "role": "retriever",
                "content": graphrag_answer(q_next, depth=depth),
            }
        )

        # 4) reflect
        refl = reflection_agent(ctx)
        ctx.append({"role": "reflection", "content": refl.reflection})

        # 5) stop?
        if refl.answer_ready or (time.perf_counter() - t0 > time_limit):
            if not refl.answer_ready:          # timeout note
                ctx.append(
                    {
                        "role": "system",
                        "content": f"Time limit of {time_limit}s reached – stopping.",
                    }
                )

            # 6) aggregate & classify
            final_para = aggregator_agent(ctx)
            ctx.append({"role": "aggregator", "content": final_para})

            final_label = classifier_agent(final_para)
            ctx.append({"role": "classifier", "content": final_label})

            # 7) record loop count
            ctx.append({"role": "system", "content": f"Total loops: {loops}"})
            break

    return ctx


# ─────────────────────────────────────────────────────────────
# re-exports
# ─────────────────────────────────────────────────────────────
__all__ = [
    "planner_agent",
    "questioner_agent",
    "reflection_agent",
    "aggregator_agent",
    "classifier_agent",
    "cot_controller",
]