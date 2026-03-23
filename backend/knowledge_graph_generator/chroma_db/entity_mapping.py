# knowledge_graph_generator/chroma_db/entity_mapping.py
# ════════════════════════════════════════════════════════════════════════════
# Canonical-entity mapping + Chroma nearest-neighbour lookup.
#
#  ✦  Pipeline in a nutshell
#  ──────────────────────────────────────────────────────────────────────────
#      1. Embed the incoming surface form (`get_embedding`)
#      2. Look up the *single* nearest neighbour in the `entity_collection`
#      3. Decision tree
#         ┌───────────────────────────────────────────────────────────────┐
#         │ cosine == 1.0          → definitely the same entity          │
#         │ cosine ≥ THRESHOLD     → ask the LLM as tiebreaker           │
#         │ otherwise              → create a new canonical group        │
#         └───────────────────────────────────────────────────────────────┘
#
#      4. If the entities are judged identical, link the new alias to the
#         neighbour’s `EntityCanonicalGroup` (or create a fresh group
#         containing both aliases if the neighbour isn’t yet in the DB).
#
#  ✦  Why skip the LLM on perfect matches?
#  ──────────────────────────────────────────────────────────────────────────
#      cos(⃗a,⃗b) == 1 implies both vectors are identical ⇒ same input
#      string (or at least the same embedding).  The expensive LLM call
#      would be superfluous, so we short-circuit for speed & cost.
# ════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

from collections import Counter
from typing import Optional, List, Dict

import numpy as np
from pydantic import BaseModel

# ── Vector-DB & embedding helpers ─────────────────────────────────────────
from knowledge_graph_generator.chroma_db.client import entity_collection
from knowledge_graph_generator.chroma_db.embedding import get_embedding

# ── Django ORM models ─────────────────────────────────────────────────────
from knowledge_graph_generator.models import EntityAlias, EntityCanonicalGroup

# ── LLM for semantic tie-breaking ─────────────────────────────────────────
from openai import OpenAI
from django.conf import settings

# **CONFIG** ---------------------------------------------------------------
SIMILARITY_THRESHOLD: float = 0.80     # below ⇒ “different” without asking LLM
client = OpenAI(api_key=settings.OPENAI_API_KEY)


# ════════════════════════════════════════════════════════════════════════════
#  Utility helpers
# ════════════════════════════════════════════════════════════════════════════
def cosine_similarity(a: List[float], b: List[float]) -> float:
    """Plain-vanilla cosine similarity of two embedding vectors."""
    a_arr, b_arr = np.asarray(a), np.asarray(b)
    return float(np.dot(a_arr, b_arr) / (np.linalg.norm(a_arr) * np.linalg.norm(b_arr)))


class _LLMResponse(BaseModel):
    """Pydantic schema for the JSON assistant-response."""
    are_same: bool


def _llm_entities_equal(e1: str, e2: str) -> bool:
    """
    One-shot GPT call asking: “are these two surface forms *exactly* the
    same entity?”.  Wrapped in a helper so it’s easy to mock in tests.
    """
    prompt = (
        "Determine if the following two biomedical entity names refer to "
        "the *exact* same entity.  Respond with a JSON object "
        '`{"are_same": true}` or `{"are_same": false}`.\n\n'
        f"Entity 1: {e1}\nEntity 2: {e2}"
    )
    completion = client.beta.chat.completions.parse(
        model="gpt-4o-mini-2024-07-18",
        messages=[
            {"role": "system", "content": "You answer strictly in JSON."},
            {"role": "user", "content": prompt},
        ],
        response_format=_LLMResponse,
    )
    return completion.choices[0].message.parsed.are_same


# ════════════════════════════════════════════════════════════════════════════
#  Public entry-point
# ════════════════════════════════════════════════════════════════════════════
def map_entity_to_canonical(
    name: str,
    quadruple_id: str,
    *,
    role: str,
    change_log: Optional[List[Dict]] = None,
    mapping_log: Optional[List[Dict]] = None,
) -> None:
    """
    Main API used by the staging-ingest step.

    Parameters
    ----------
    name          : surface form to map (early-return if empty)
    quadruple_id  : parent quad PK – used for constructing alias IDs
    role          : "subject" | "object"  (suffix for alias ID)
    change_log    : optional list that collects “alias → canonical” updates
    mapping_log   : optional list that collects *all* mappings (incl. no-ops)

    Notes
    -----
    * Every alias ID has the shape  `<quadruple_id>-<role>`
    * The function is idempotent: if the alias already exists it exits early.
    """
    if not name:
        return

    entity_id = f"{quadruple_id}-{role}"

    # Early exit – alias already known
    if EntityAlias.objects.filter(id=entity_id).exists():
        return

    # 1. ── Embed ------------------------------------------------------
    embedding = get_embedding(name)

    # 2. ── Empty vector DB? → nothing to match ------------------------
    if entity_collection.count() == 0:
        _create_new_group(entity_id, name, change_log, mapping_log)
        return

    # 3. ── Nearest neighbour search ----------------------------------
    nn = entity_collection.query(
        query_embeddings=[embedding],
        n_results=1,
        include=["embeddings", "metadatas"],
    )

    if not nn["metadatas"][0]:
        _create_new_group(entity_id, name, change_log, mapping_log)
        return

    neighbour_meta   = nn["metadatas"][0][0]
    neighbour_vec    = nn["embeddings"][0][0]
    neighbour_name   = neighbour_meta["name"]
    neighbour_alias  = neighbour_meta.get("entity_id") or neighbour_meta["id"]

    sim = cosine_similarity(embedding, neighbour_vec)

    # 4. ── Decision matrix -------------------------------------------
    if sim == 1.0:
        # identical vector → treat as same entity immediately
        _link_to_existing_group(
            new_id=entity_id,
            new_name=name,
            matched_id=neighbour_alias,
            matched_name=neighbour_name,
            change_log=change_log,
            mapping_log=mapping_log,
        )
    elif sim >= SIMILARITY_THRESHOLD and _llm_entities_equal(name, neighbour_name):
        _link_to_existing_group(
            new_id=entity_id,
            new_name=name,
            matched_id=neighbour_alias,
            matched_name=neighbour_name,
            change_log=change_log,
            mapping_log=mapping_log,
        )
    else:
        _create_new_group(entity_id, name, change_log, mapping_log)


# ════════════════════════════════════════════════════════════════════════════
#  Internal linking helpers
# ════════════════════════════════════════════════════════════════════════════
def _link_to_existing_group(
    *,
    new_id: str,
    new_name: str,
    matched_id: str,
    matched_name: str,
    change_log: Optional[List[Dict]],
    mapping_log: Optional[List[Dict]],
) -> None:
    """
    Attach a *new* surface form to the canonical group of an existing alias.
    """
    matched_alias = EntityAlias.objects.get(id=matched_id)
    cg = matched_alias.canonical_group

    EntityAlias.objects.create(id=new_id, name=new_name, canonical_group=cg)
    _update_canonical_entity(cg)

    canonical_name = cg.get_canonical_name()

    if mapping_log is not None:
        mapping_log.append(
            dict(
                entity_id=new_id,
                entity_name=new_name,
                canonical_entity_name=canonical_name,
                canonical_group_id=cg.id,
            )
        )
    if change_log is not None and new_name != canonical_name:
        change_log.append(
            dict(
                old_entity_id=new_id,
                old_entity_name=new_name,
                canonical_entity_name=canonical_name,
                canonical_group_id=cg.id,
            )
        )


def _create_new_group(
    new_id: str,
    new_name: str,
    change_log: Optional[List[Dict]],
    mapping_log: Optional[List[Dict]],
) -> None:
    """
    Stand-up a fresh canonical group with a single alias.
    """
    cg = EntityCanonicalGroup.objects.create()
    EntityAlias.objects.create(id=new_id, name=new_name, canonical_group=cg)

    if mapping_log is not None:
        mapping_log.append(
            dict(
                entity_id=new_id,
                entity_name=new_name,
                canonical_entity_name=new_name,
                canonical_group_id=cg.id,
            )
        )
    # no change_log entry – nothing changed yet


def _update_canonical_entity(cg: EntityCanonicalGroup) -> None:
    """
    Pick the **case-sensitive** surface form with the highest frequency
    and treat it as the display label for the group.
    """
    alias_names = [a.name for a in cg.aliases.all()]
    if not alias_names:
        return
    canonical, freq = Counter(alias_names).most_common(1)[0]
    # nothing to persist – we compute on the fly – but log for traceability
    print(f"🏷️  Canonical label for group #{cg.id}: '{canonical}' (freq = {freq})")
