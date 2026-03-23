"""
Ontology-worthy entity detection – ensemble, single-shot version
----------------------------------------------------------------

Changes in this revision
~~~~~~~~~~~~~~~~~~~~~~~~
* The majority-vote list is **re-filtered** so that only names whose
  *lower-case form matches exactly* a surface form in the triples are
  returned.
* Internal comments clarified where lowercase comparison happens.
"""

from __future__ import annotations

import os
import time
from collections import Counter
from math import ceil
from typing import Any, Dict, List, Set, Tuple

from openai import OpenAI
from pydantic import BaseModel, ValidationError

from django.conf import settings

# ────────────────────────────────────────────────────────────── #
#  Configuration
# ────────────────────────────────────────────────────────────── #

client = OpenAI(api_key=settings.OPENAI_API_KEY)

# I left this here for ease of demo purposes, previously used a gemini and claude model in addition. However, fetching and maintaining the api keys is a mission and this serves the same purpose when an increased temperature is used.
LLM_MODELS: List[str] = [
    "gpt-4.1-nano",
    "gpt-4.1-nano",
    "gpt-4.1-nano",
]
VOTE_THRESHOLD = ceil(len(LLM_MODELS) / 2)      # ≥ 2 of 3
TEMPERATURE = 0.3
TIMEOUT_S = 90

# ────────────────────────────────────────────────────────────── #
#  Pydantic schema
# ────────────────────────────────────────────────────────────── #
class KeepEntityOutput(BaseModel):
    keep_entities: List[str]

# ────────────────────────────────────────────────────────────── #
#  Helpers
# ────────────────────────────────────────────────────────────── #
def _collect_entities_and_triples(
    quadruples: List[Dict[str, Any]]
) -> Tuple[List[str], List[str]]:
    """
    Returns
    -------
    entities       : list[str]
        Unique subject/object surface forms (original casing).
    triples        : list[str]
        Pretty-printed triples, subject & object surrounded by [ ].
    """
    seen: Set[str] = set()
    entities, triples = [], []
    for q in quadruples:
        core = q.get("quadruple", q)
        s = core.get("subject", {}).get("name", "")
        p = core.get("predicate", "")
        o = core.get("object", {}).get("name", "")
        if s and o:
            triples.append(f"• [{s}] — {p} → [{o}]")
        for ent in (s, o):
            if ent:
                key = ent.strip().lower()
                if key not in seen:
                    seen.add(key)
                    entities.append(ent.strip())
    return entities, triples


def _prompt(triples_block: str) -> List[Dict[str, str]]:
    """
    Prompt that asks for ontology-worthy entities only.
    """
    system = (
        "Below are knowledge-graph triples from ONE paragraph. "
        "Names in square brackets are the subject or object.\n\n"
        "Return the names of the entities that are grounded and SHOULD be kept in a global medical ontology "
        "(well-defined diseases, cell types, proteins, procedures, drugs …).\n\n"
        'Respond with *JSON only*:\n'
        '{"keep_entities": ["Name 1", "Name 2", ...]}.'
    )

    assistant_ex = (
        "Example triples:\n"
        "• [BRCA1] — associated_with → [breast cancer]\n"
        "• [group A] — received → [500 mg amoxicillin]\n\n"
        "Correct JSON:\n"
        '{"keep_entities": ["BRCA1", "breast cancer", "amoxicillin"]}'
    )

    user = f"Triples:\n{triples_block}\n\nRespond with the JSON only."
    return [
        {"role": "system", "content": system},
        {"role": "assistant", "content": assistant_ex},
        {"role": "user", "content": user},
    ]


def _call_llm(
    model: str,
    triples_block: str,
    allowed_entities_lc: Set[str],
) -> Tuple[List[str], float]:
    """
    Single shot → returns only names whose *lowercase* form occurs in
    `allowed_entities_lc` (the lowercase entity list from the triples).
    """
    try:
        rsp = client.chat.completions.create(
            model=model,
            temperature=TEMPERATURE,
            timeout=TIMEOUT_S,
            response_format={"type": "json_object"},
            messages=_prompt(triples_block),
        )
        keep_list = KeepEntityOutput.model_validate_json(
            rsp.choices[0].message.content
        ).keep_entities
    except (Exception, ValidationError) as exc:
        print(f"⚠️  {model} call failed:", exc)
        return [], 0.0

    # Keep only exact lowercase matches
    hits = [s for s in keep_list if s.lower() in allowed_entities_lc]
    pct = (len(hits) / len(keep_list) * 100) if keep_list else 0.0
    print(f"✅ {model}: {len(hits)}/{len(keep_list)} match ({pct:.1f}%)")
    return hits, pct


# ────────────────────────────────────────────────────────────── #
#  Public API
# ────────────────────────────────────────────────────────────── #
def identify_ontological_entities(
    paragraph: str,
    quadruples: List[Dict[str, Any]],
) -> List[str]:
    """
    Majority-vote extraction of ontology-worthy entity names.

    Returns
    -------
    keep_list : list[str]
        Names retained by ≥ VOTE_THRESHOLD models.
    (The average % match is printed for diagnostics but **not returned**.)
    """
    entities, triple_lines = _collect_entities_and_triples(quadruples)
    if not entities:
        return []

    triples_block = "\n".join(triple_lines)
    allowed_lc = {e.lower() for e in entities}

    all_keep_lists, pct_scores = [], []

    t0 = time.perf_counter()
    for model in LLM_MODELS:
        keeps, pct = _call_llm(model, triples_block, allowed_lc)
        all_keep_lists.append(keeps)
        pct_scores.append(pct)
        print(f"• {model} keep list → {keeps}")

    counter = Counter(s.lower() for lst in all_keep_lists for s in lst)
    lc_to_orig = {e.lower(): e for e in entities}

    voted = [
        lc_to_orig[name]
        for name, count in counter.items()
        if count >= VOTE_THRESHOLD and name in allowed_lc
    ]

    avg_pct = sum(pct_scores) / len(pct_scores) if pct_scores else 0.0
    print(
        f"🏷️  Majority vote ({VOTE_THRESHOLD}/{len(LLM_MODELS)}) "
        f"→ {voted}   [avg match {avg_pct:.1f}% in {time.perf_counter()-t0:.2f}s]"
    )
    return voted
