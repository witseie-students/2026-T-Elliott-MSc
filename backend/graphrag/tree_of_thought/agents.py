# tree_of_thought/agents.py
# ══════════════════════════════════════════════════════════════
"""
Tree-of-Thought (ToT) Graph-RAG scaffold
----------------------------------------

Five LLM agents cooperate around a static Graph-RAG retriever.
See header comments in earlier revision for the full diagram.
"""
from __future__ import annotations
import itertools, json, time
from collections import deque
from typing import Dict, List, Literal, Optional, Tuple

from openai import OpenAI
from pydantic import BaseModel, ValidationError
from graphrag.graph_algorithm.wrapper import graphrag_answer
from django.conf import settings

# ──────────────────────────────────────────────────────────────
# OpenAI client
# ──────────────────────────────────────────────────────────────

MODEL_NAME     = "gpt-4.1-nano"
_client = OpenAI(api_key=settings.OPENAI_API_KEY)

def _chat_completion(system: str, user: str, *, temperature: float = 0.0) -> str:
    resp = _client.chat.completions.create(
        model       = MODEL_NAME,
        temperature = temperature,
        messages=[{"role": "system", "content": system},
                  {"role": "user",   "content": user}],
    )
    return resp.choices[0].message.content.strip()

# ══════════════════════════════════════════════════════════════
# 1) PLANNER  – branching
# ══════════════════════════════════════════════════════════════
class BranchDecision(BaseModel):
    branch: Literal["single", "multi"]
    plan:   Optional[str]        = None
    plans:  Optional[List[str]]  = None


def planner_agent(ctx: List[Dict[str, str]], *, max_children: int = 10) -> List[str]:
    sys_prompt = f"""
You are the *planner* in a Tree-of-thought system.\n
In **one** or **several** independent paragraphs, output your thoughts on every possible way of determining what needs to be known to answer the question. 
Respond **ONLY JSON** matching exactly one of the two formats:
–– single path ––
{{ "branch":"single",
  "plan":"<40-60 word self-contained plan (≤90 tokens)>" }}
–– many paths ––
{{ "branch":"multi",
  "plans":[
     "<40-60 word self-contained plan>",
     …                             // 2–{max_children} items
  ] }}
""".strip()

    raw = _chat_completion(sys_prompt,
                           json.dumps({"context_chain": ctx}, indent=2))
    print("\n[PLANNER-RAW]\n" + raw + "\n")            # diagnostic

    try:
        bd = BranchDecision.model_validate_json(raw)
        if bd.branch == "single" and bd.plan:
            return [bd.plan]
        if bd.branch == "multi" and bd.plans:
            return bd.plans[:max_children] or ["(empty plan)"]
    except ValidationError:
        pass
    return [raw.strip() or "(empty plan)"]

# ══════════════════════════════════════════════════════════════
# 2) QUESTIONER & helpers
# ══════════════════════════════════════════════════════════════
def questioner_agent(ctx: List[Dict[str, str]]) -> str:
    sys = ("You are the *questioner*.\n"
           "Craft ONE atomic, self-contained biomedical question that, when "
           "answered, fills the next most important knowledge gap.")
    return _chat_completion(sys, json.dumps(ctx, indent=2))

def null_hypothesis_agent(question: str) -> str:
    sys = ("Rewrite the biomedical question so it tests the NULL hypothesis – "
        "i.e. it asserts that the original relationship is **not** present.\n"
        "Keep all entities & context intact.\n\n"
        "Example:\n"
        "User question  :  Does drug X improve survival in cancer Y?\n"
        "Null-hypothesis:  Is there no improvement in survival in patients "
        "with cancer Y treated with drug X compared with controls?\n\n"
        "Only return the re-phrased question – no explanations.")
    return _chat_completion(sys, question)

class _Rumsfeld(BaseModel):
    known_known:   str
    known_unknown: str
def rumsfeld_agent(ctx: List[Dict[str, str]]) -> _Rumsfeld:
    sys = (
        "Produce JSON {\"known_known\":\"…\",\"known_unknown\":\"…\"} :\n"
        "• *known_known*  – paragraph summarising what the evidence firmly shows excluding any internal bias or gaps in knowledge\n"
        "• *known_unknown* – paragraph on remaining gaps that could be uncertain."
    )
    raw = _chat_completion(sys, json.dumps(ctx, indent=2))
    try:
        return _Rumsfeld.model_validate_json(raw)
    except (ValidationError, json.JSONDecodeError):
        return _Rumsfeld(known_known="(parser error)", known_unknown="(parser error)")

# ══════════════════════════════════════════════════════════════
# 3) REFLECTION
# ══════════════════════════════════════════════════════════════
class _Reflection(BaseModel):
    answer_ready: bool
    reflection: str
def reflection_agent(ctx: List[Dict[str, str]]) -> _Reflection:
    sys = (
        "You are a *self-reflection* agent that thinks about whether or not the question has been answered and what exactly the knowledge base knows to answer that question.\n"
        "Return ONLY JSON of the exact form:\n"
        '{ "answer_ready": <true|false>, "reflection": "paragraph reflective thoughts" }'
    )
    raw = _chat_completion(sys, json.dumps(ctx, indent=2))
    try:
        return _Reflection.model_validate_json(raw)
    except (ValidationError, json.JSONDecodeError):
        return _Reflection(answer_ready=False, reflection="Parser error – continue.")

# ══════════════════════════════════════════════════════════════
# 4) AGGREGATOR  & CLASSIFIER
# ══════════════════════════════════════════════════════════════
def aggregator_agent(question: str, evidence: str) -> str:
    sys = (
        "You are an expert assistant. Using ONLY the provided "
        "context, write an evidence-based answer to the "
        "user's question. Do not add information that is not "
        "present in the context."
    )
    user = json.dumps({"question": question,
                       "evidence_paragraphs": evidence}, indent=2)
    para = _chat_completion(sys, user)
    if not para.lower().lstrip().startswith(("yes", "no", "maybe")):
        para = "Maybe, " + para.lstrip()
    return para

class _Decision(BaseModel):
    decision: str
def classifier_agent(paragraph: str) -> str:
    sys = (
        "Return ONLY a JSON object {'decision': 'yes'|'no'|'maybe'} indicating "
        "whether the answer implies YES, NO, or MAYBE to the question."
    )
    raw = _chat_completion(sys, paragraph)
    try:
        return _Decision.model_validate_json(raw).decision
    except (ValidationError, json.JSONDecodeError):
        return "maybe"

# ══════════════════════════════════════════════════════════════
#  Helper: branch container
# ══════════════════════════════════════════════════════════════
class _Branch:
    _id_iter = itertools.count(1)
    def __init__(self, ctx: List[Dict[str, str]], depth: int):
        self.id    = next(self._id_iter)
        self.ctx   = ctx
        self.depth = depth
        self.done  = False

# ══════════════════════════════════════════════════════════════
#  Breadth-first controller
# ══════════════════════════════════════════════════════════════
def tot_controller(
    question: str,
    *,
    graph_depth   : int = 1,
    time_limit    : int = 100,
    null_hypothesis: bool = False,
    rumsfeld      : bool = False,
) -> Dict[str, object]:
    """
    Breadth-first Tree-of-Thought exploration supporting:
    • a separate *null* root branch  (when `null_hypothesis=True`)
    • null-hypothesis sub-answers for **every** generated sub-question
      (same flag)
    • optional Rumsfeld matrices (`rumsfeld=True`)
    """
    t0, loops = time.perf_counter(), 0

    # ── initialise BFS queue with one or two roots ──────────────────
    root           = _Branch([{"role": "question", "content": question}], depth=0)
    queue : deque[_Branch] = deque([root])
    trace : List[Dict[str, object]] = [
        {"branch_id": root.id, "depth": 0,
         "role": "question", "content": question}
    ]

    if null_hypothesis:
        null_q    = null_hypothesis_agent(question)
        null_root = _Branch([{"role": "null_question", "content": null_q}], depth=0)
        queue.append(null_root)
        trace.append({"branch_id": null_root.id, "depth": 0,
                      "role": "null_question", "content": null_q})

    finished: List[_Branch] = []

    # ───── main BFS loop ────────────────────────────────────────────
    while queue and (time.perf_counter() - t0) < time_limit:
        br = queue.popleft()
        if br.done:
            continue

        # 1) PLAN
        plans = planner_agent(br.ctx)
        trace.append({"branch_id": br.id, "depth": br.depth,
                      "role": "planner", "content": json.dumps(plans)})

        for idx, plan in enumerate(plans):
            tgt = br if idx == 0 else _Branch([*br.ctx], depth=br.depth)
            if idx > 0:
                queue.append(tgt)
                trace.append({"branch_id": tgt.id, "depth": tgt.depth,
                              "role": "branch",
                              "content": f"← forked from {br.id}"})

            tgt.ctx.append({"role": "plan", "content": plan})
            trace.append({"branch_id": tgt.id, "depth": tgt.depth,
                          "role": "plan", "content": plan})

            # 2) QUESTIONER
            q = questioner_agent(tgt.ctx)
            tgt.ctx.append({"role": "questioner", "content": q})
            trace.append({"branch_id": tgt.id, "depth": tgt.depth,
                          "role": "questioner", "content": q})

            # 3) RETRIEVER – original question
            para = graphrag_answer(q, depth=graph_depth)
            tgt.ctx.append({"role": "retriever", "content": para})
            trace.append({"branch_id": tgt.id, "depth": tgt.depth,
                          "role": "retriever", "content": para})

            # 3b) RETRIEVER – null-hypothesis version (if enabled)
            if null_hypothesis:
                q_null = null_hypothesis_agent(q)
                para_n = graphrag_answer(q_null, depth=graph_depth)
                tgt.ctx.append({"role": "retriever", "content": para_n})
                trace.append({"branch_id": tgt.id, "depth": tgt.depth,
                              "role": "retriever", "content": para_n})

            loops += 1

            # 4) REFLECTION
            refl = reflection_agent(tgt.ctx)
            tgt.ctx.append({"role": "reflection", "content": refl.reflection})
            trace.append({"branch_id": tgt.id, "depth": tgt.depth,
                          "role": "reflection", "content": refl.reflection})

            if refl.answer_ready:
                if rumsfeld:
                    rum = rumsfeld_agent(tgt.ctx)
                    tgt.ctx += [
                        {"role": "known_known",   "content": rum.known_known},
                        {"role": "known_unknown", "content": rum.known_unknown},
                    ]
                    trace.append({"branch_id": tgt.id, "depth": tgt.depth,
                                   "role": "rumsfeld", "content": json.dumps(rum.dict())})
                else:
                    evid = "\n\n".join(s["content"] for s in tgt.ctx
                                       if s["role"] == "retriever")
                    agg  = aggregator_agent(question, evid)
                    tgt.ctx.append({"role": "aggregator", "content": agg})
                    trace.append({"branch_id": tgt.id, "depth": tgt.depth,
                                  "role": "aggregator", "content": agg})
                tgt.done = True
                finished.append(tgt)
            else:
                tgt.depth += 1
                if (time.perf_counter() - t0) < time_limit:
                    queue.append(tgt)

        if (time.perf_counter() - t0) >= time_limit:
            break

    # ─── Rumsfeld for leftovers ─────────────────────────────────────
    if rumsfeld:
        for b in [b for b in queue if not b.done]:
            rum = rumsfeld_agent(b.ctx)
            b.ctx += [
                {"role": "known_known",   "content": rum.known_known},
                {"role": "known_unknown", "content": rum.known_unknown},
            ]
            trace.append({"branch_id": b.id, "depth": b.depth,
                          "role": "rumsfeld", "content": json.dumps(rum.dict())})

    if not finished:
        finished = list(queue)      # fallback evidence

    # ─── global aggregation ─────────────────────────────────────────
    merged_ctx = [{"role": "question", "content": question}]
    if rumsfeld:
        for b in finished:
            merged_ctx.extend(s for s in b.ctx if s["role"] == "known_known")
    else:
        for b in finished:
            merged_ctx.extend(s for s in b.ctx if s["role"] == "retriever")

    evidence     = "\n\n".join(s["content"] for s in merged_ctx
                               if s["role"] != "question")
    final_para   = aggregator_agent(question, evidence)
    final_label  = classifier_agent(final_para)

    trace += [
        {"branch_id": 0, "depth": 0, "role": "FINAL",  "content": final_para},
        {"branch_id": 0, "depth": 0, "role": "LABEL",  "content": final_label},
        {"branch_id": 0, "depth": 0, "role": "system",
         "content": f"Total loops: {loops}"},
    ]

    return dict(tree=trace, loops=loops,
                final_paragraph=final_para, final_label=final_label)

# ──────────────────────────────────────────────────────────────
__all__ = [
    "planner_agent", "questioner_agent", "reflection_agent",
    "aggregator_agent", "classifier_agent",
    "tot_controller", "null_hypothesis_agent", "rumsfeld_agent",
]