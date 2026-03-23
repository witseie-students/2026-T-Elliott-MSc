# knowledge_graph_generator/chroma_db/ingest_staged_quads.py
# ════════════════════════════════════════════════════════════════════════
# Bridge between the *staging* layer and ChromaDB **plus** a neat
# summary of canonical-entity mappings required by the Neo4j loader.
#
# PUBLIC API
# ────────────────────────────────────────────────────────────────────────
# ingest_staging_paragraph(sp: StagingParagraph) -> dict
#
#     {
#       "quad_total" : 12,
#       "entities"   : 24,
#       "types"      : 40,
#       "questions"  : 11,
#       "mapped"     : 18,
#       "aliases"    : [ … ]   # NEW – list of alias dicts (see above)
#     }
#
# The ″counters″ part is 100 % backward-compatible with earlier code;
# the extra `aliases` key is simply ignored if the caller is not yet
# expecting it.
# ════════════════════════════════════════════════════════════════════════
from __future__ import annotations

from typing import List, Dict, Set

from django.db import transaction

# ── Django models ───────────────────────────────────────────────────────
from knowledge_graph_generator.models import (
    StagingParagraph,
    StagedQuadruple,
    EntityAlias,
)

# ── Canonical-mapping & vector-DB helpers ───────────────────────────────
from knowledge_graph_generator.chroma_db.entity_mapping import map_entity_to_canonical
from knowledge_graph_generator.chroma_db.operations import (
    add_entity,
    add_ontological_type,
    add_question,
)

# -----------------------------------------------------------------------
#  INTERNAL HELPERS
# -----------------------------------------------------------------------
def _map_and_vectorise(
    *,
    quad: StagedQuadruple,
    role: str,                   # "subject" | "object"
    name: str,
    types: List[str],
    counters: Dict[str, int],
    tracked_ids: Set[str],
) -> None:
    """
    • Ensure `<quad-id>-<role>` is linked into a canonical group  
    • Add surface-form embedding to `entity_collection`  
    • Add each ontological type to `ontological_type_collection`
    """
    entity_id = f"{quad.quadruple_id}-{role}"

    # 1. ── canonical mapping ------------------------------------------
    if not EntityAlias.objects.filter(id=entity_id).exists():
        map_entity_to_canonical(name, quad.quadruple_id, role=role)
        counters["mapped"] += 1

    tracked_ids.add(entity_id)               # collect for alias dump later

    # 2. ── surface-form vector ----------------------------------------
    try:
        add_entity(entity_id, name, quad.quadruple_id)
        counters["entities"] += 1
    except ValueError:                        # duplicate ID
        pass

    # 3. ── ontological types ------------------------------------------
    for t in types:
        tid = f"{quad.quadruple_id}-{role[0]}type-{t}"
        try:
            add_ontological_type(tid, t, quad.quadruple_id)
            counters["types"] += 1
        except ValueError:
            continue   # already present


# =======================================================================
#  PUBLIC FUNCTION
# =======================================================================
@transaction.atomic
def ingest_staging_paragraph(sp: StagingParagraph) -> Dict[str, object]:
    """
    Ingest every raw quadruple belonging to a *single* `StagingParagraph`.

    Returns
    -------
    dict
        • Six integer counters (unchanged from previous version)  
        • NEW: `"aliases"` → list with canonical-mapping metadata
    """
    counters = {
        "quad_total": 0,
        "entities":   0,
        "types":      0,
        "questions":  0,
        "mapped":     0,
    }
    involved_alias_ids: Set[str] = set()

    # ── LOOP OVER QUADS ───────────────────────────────────────────────
    for quad in sp.quadruples.all():
        counters["quad_total"] += 1

        # SUBJECT ------------------------------------------------------
        if quad.subject_is_ontological and quad.subject_name:
            _map_and_vectorise(
                quad     = quad,
                role     = "subject",
                name     = quad.subject_name,
                types    = quad.subject_types,
                counters = counters,
                tracked_ids = involved_alias_ids,
            )

        # OBJECT -------------------------------------------------------
        if quad.object_is_ontological and quad.object_name:
            _map_and_vectorise(
                quad     = quad,
                role     = "object",
                name     = quad.object_name,
                types    = quad.object_types,
                counters = counters,
                tracked_ids = involved_alias_ids,
            )

        # QUESTION (always stored) ------------------------------------
        if quad.question:
            qid = f"{quad.quadruple_id}-question"
            try:
                add_question(qid, quad.question, quad.quadruple_id)
                counters["questions"] += 1
            except ValueError:
                pass   # duplicate

    # ── BUILD ALIAS-METADATA PAYLOAD ─────────────────────────────────
    alias_payload = []
    for alias in EntityAlias.objects.filter(id__in=involved_alias_ids):
        alias_payload.append(
            dict(
                id                 = alias.id,
                name               = alias.name,
                canonical_group_id = alias.canonical_group_id,
                canonical_name     = alias.canonical_group.get_canonical_name(),
            )
        )

    # ── RETURN ───────────────────────────────────────────────────────
    return {
        **counters,
        "aliases": alias_payload,         # ← NEW FIELD (list[dict])
    }
