# knowledge_graph_generator/database_utilities/save_to_kg.py
# ═══════════════════════════════════════════════════════════
# Persist the staging payload into Neo4j with paragraph-scoped
# handling for non-ontological entities.
#
# 2025-05-25  UPDATE
# ───────────────────────────────────────────────────────────
# • Nodes are keyed on (name, paragraph_scope) where
#       paragraph_scope = 0         → ontological (global)
#       paragraph_scope = <para id> → local  (non-ontological)
# • Edges use the same scoped identity via save_quadruple_rel().
# • The previous “first pass alias loop” has been removed; nodes
#   are created lazily inside `_persist_quad`.
# ═══════════════════════════════════════════════════════════
from __future__ import annotations
from typing import Dict, Optional

from knowledge_graph_generator.database_utilities.kg_utilities import (
    _driver,
    upsert_entity,
    save_quadruple_rel,
)
from knowledge_graph_generator.models import StagedQuadruple


# ---------------------------------------------------------------------
#  Public API
# ---------------------------------------------------------------------
def save_json_to_knowledge_graph(payload: Dict):
    """
    Persist entities + relationships with paragraph-aware scoping.
    """
    quadruple_groups   = payload.get("quadruples", [])
    inferred_quads     = payload.get("inferred_quadruples", [])
    entity_aliases     = payload.get("entity_aliases", [])

    # ---------- quick look-ups --------------------------------------
    alias_by_id = {a["id"]: a for a in entity_aliases}

    with _driver().session(database="pubmedqa-context") as sess:
        # relationships + node upserts
        for pg in quadruple_groups:
            for q in pg["quadruples"]:
                _persist_quad(sess, q, alias_by_id, inferred=False)

        for iq in inferred_quads:
            _persist_quad(sess, iq, alias_by_id, inferred=True)


# ---------------------------------------------------------------------
#  internal
# ---------------------------------------------------------------------
def _persist_quad(sess, q_json: Dict, alias_by_id: Dict[str, Dict], *, inferred: bool):
    quad     = q_json["quadruple"]
    qid      = q_json.get("quadruple_id") or q_json.get("inferred_quadruple_id")

    # ---------- alias → canonical mapping ---------------------------
    subj_alias_name = quad["subject"]["name"]
    obj_alias_name  = quad["object"]["name"]

    subj_alias_info = alias_by_id.get(f"{qid}-subject")
    obj_alias_info  = alias_by_id.get(f"{qid}-object")

    canonical_subj = (
        subj_alias_info["canonical_name"] if subj_alias_info else subj_alias_name
    )
    canonical_obj = (
        obj_alias_info["canonical_name"] if obj_alias_info else obj_alias_name
    )

    # ---------- ontology flags & paragraph provenance ---------------
    sq: Optional[StagedQuadruple] = (
        StagedQuadruple.objects
        .filter(quadruple_id=qid)
        .select_related("staging_paragraph__paragraph")
        .first()
    )

    subj_is_ont = bool(sq.subject_is_ontological) if sq else False
    obj_is_ont  = bool(sq.object_is_ontological)  if sq else False
    para_id     = (
        sq.staging_paragraph.paragraph.id
        if sq and sq.staging_paragraph and sq.staging_paragraph.paragraph_id
        else None
    )

    subj_scope = 0 if subj_is_ont else (para_id or -1)
    obj_scope  = 0 if obj_is_ont  else (para_id or -1)

    # ---------- upsert canonical nodes ------------------------------
    sess.write_transaction(
        upsert_entity,
        name=canonical_subj,
        canonical_names=[canonical_subj],
        is_canonical=True,
        ont_types=quad["subject"]["types"],
        aliases=[subj_alias_name],
        is_ontological=subj_is_ont,
        paragraph_id=para_id,
    )
    sess.write_transaction(
        upsert_entity,
        name=canonical_obj,
        canonical_names=[canonical_obj],
        is_canonical=True,
        ont_types=quad["object"]["types"],
        aliases=[obj_alias_name],
        is_ontological=obj_is_ont,
        paragraph_id=para_id,
    )

    # ---------- SPO edge --------------------------------------------
    sess.write_transaction(
        save_quadruple_rel,
        subj=canonical_subj,
        subj_scope=subj_scope,
        pred=quad["predicate"],
        obj=canonical_obj,
        obj_scope=obj_scope,
        context=quad["reason"],
        propos=q_json.get("proposition_sentence"),
        coref=q_json.get("coreference_sentence"),
        natural=q_json.get("natural_language_sentence"),
        question=q_json.get("question"),
        inferred=inferred,
        qid=qid,
    )
