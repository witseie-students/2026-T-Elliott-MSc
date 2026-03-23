# knowledge_graph_generator/database_utilities/kg_utilities.py
# ═════════════════════════════════════════════════════════════
# Neo4j helpers for the PubMed-QA context pipeline
#
# 2025-05-25  UPDATE
# ─────────────────────────────────────────────────────────────
# • Non-ontological entities are now **paragraph-scoped**:
#       paragraph_scope = 0         → global (ontological = True)
#       paragraph_scope = <para id> → local  (ontological = False)
#   The MERGE pattern keys on  {name, paragraph_scope}.
# • save_quadruple_rel() also keys its MATCH / MERGE on the scope,
#   guaranteeing each edge attaches to the correct node version.
# • ensure_global_merge() extended to accept scope parameters but
#   is no longer used by the pipeline (kept for completeness).
# ═════════════════════════════════════════════════════════════
from __future__ import annotations
from typing import List, Optional

from neo4j import GraphDatabase

# ---------------------------------------------------------------------
#  Connection constants
# ---------------------------------------------------------------------
NEO4J_URI      = "bolt://localhost:7687"
NEO4J_USER     = "neo4j"
NEO4J_PASSWORD = "Turlangton35"
NEO4J_DB       = "pubmedqa-context"


# =====================================================================
#  HOUSEKEEPING
# =====================================================================
def clear_neo4j_knowledge_graph() -> None:
    """Danger-zone: wipe *everything* from the configured Neo4j DB."""
    print("🧹  Clearing Neo4j knowledge graph …")
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        with driver.session(database=NEO4J_DB) as sess:
            sess.run("MATCH (n) DETACH DELETE n")
        driver.close()
        print("✅  Neo4j knowledge graph cleared.\n")
    except Exception as exc:
        print(f"❌  Error clearing Neo4j knowledge graph: {exc}")


# =====================================================================
#  INTERNAL UTILS
# =====================================================================
def _driver():
    """Return a fresh Neo4j driver (keeps call-sites tidy)."""
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


def upsert_entity(
    tx,
    *,
    name: str,
    canonical_names: List[str],
    is_canonical: bool,
    ont_types: List[str],
    aliases: Optional[List[str]] = None,
    is_ontological: bool = False,
    paragraph_id: Optional[int] = None,
):
    """
    Merge an :Entity node keyed by **(name, paragraph_scope)**.

    paragraph_scope = 0   → ontological (global ID space)  
    paragraph_scope = pid → non-ontological, local to *pid*
    """
    aliases = aliases or []
    paragraph_scope = 0 if is_ontological else (paragraph_id or -1)

    tx.run(
        f"""
        MERGE (e:Entity {{name:$name, paragraph_scope:$paragraph_scope}})

        // ─────────────────────────────── ON CREATE
        ON CREATE SET
            e.canonical_names   = apoc.coll.toSet($canonical_names),
            e.aliases           = apoc.coll.toSet($aliases),
            e.ontological_types = $ont_types,
            e.is_canonical      = $is_canonical,
            e.is_ontological    = $is_ontological,
            e.paragraph_ids     = CASE
                                    WHEN $paragraph_id IS NULL
                                    THEN []
                                    ELSE [$paragraph_id]
                                  END

        // ─────────────────────────────── ON MATCH
        ON MATCH SET
            e.canonical_names   = apoc.coll.toSet(e.canonical_names + $canonical_names),
            e.aliases           = apoc.coll.toSet(coalesce(e.aliases,[]) + $aliases),
            e.ontological_types = apoc.coll.toSet(e.ontological_types + $ont_types),
            e.is_canonical      = e.is_canonical OR $is_canonical,
            e.is_ontological    = coalesce(e.is_ontological,false) OR $is_ontological,
            e.paragraph_ids     = apoc.coll.toSet(
                                      coalesce(e.paragraph_ids,[]) +
                                      CASE
                                        WHEN $paragraph_id IS NULL
                                        THEN []
                                        ELSE [$paragraph_id]
                                      END
                                  )
        """,
        name=name,
        paragraph_scope=paragraph_scope,
        canonical_names=canonical_names,
        aliases=aliases,
        ont_types=ont_types,
        is_canonical=is_canonical,
        is_ontological=is_ontological,
        paragraph_id=paragraph_id,
    )


# ---------------------------------------------------------------------
#  OPTIONAL helper – currently unused by the pipeline
# ---------------------------------------------------------------------
def ensure_global_merge(
    tx,
    *,
    name_a: str,
    scope_a: int,
    name_b: str,
    scope_b: int,
):
    """
    Explicitly merge two nodes – only used in ad-hoc maintenance scripts.
    """
    if name_a == name_b and scope_a == scope_b:
        return
    tx.run(
        """
        MATCH (a:Entity {name:$a, paragraph_scope:$sa}),
              (b:Entity {name:$b, paragraph_scope:$sb})
        CALL apoc.refactor.mergeNodes([a,b], {properties:'combine'}) YIELD node
        RETURN node
        """,
        a=name_a,
        sa=scope_a,
        b=name_b,
        sb=scope_b,
    )


# ---------------------------------------------------------------------
#  EDGE persistence
# ---------------------------------------------------------------------
def save_quadruple_rel(
    tx,
    *,
    subj: str,
    subj_scope: int,
    pred: str,
    obj: str,
    obj_scope: int,
    context: str | None,
    propos: str | None,
    coref: str | None,
    natural: str | None,
    question: str | None,
    inferred: bool,
    qid: str,
):
    """
    Create (or update) a SPO edge keyed by paragraph-scope-aware nodes.
    """
    tx.run(
        f"""
        MERGE (s:Entity {{name:$subj, paragraph_scope:$ss}})
        MERGE (o:Entity {{name:$obj,  paragraph_scope:$os}})

        // 1. relationship --------------------------------------------------
        MERGE (s)-[r:`{pred}`]->(o)
        ON CREATE SET
            r.quad_ids = [$qid],
            r.inferred = $inferred
        ON MATCH  SET
            r.quad_ids = apoc.coll.toSet(r.quad_ids + [$qid]),
            r.inferred = coalesce(r.inferred,false) OR $inferred

        // 2. provenance lists ---------------------------------------------
        WITH r
        FOREACH (x IN [coalesce($context,'')] |
            SET r.context_sentences = apoc.coll.toSet(
                                          coalesce(r.context_sentences,[]) +
                                          CASE WHEN x='' THEN [] ELSE [x] END))
        FOREACH (x IN [coalesce($propos,'')] |
            SET r.proposition_sentences = apoc.coll.toSet(
                                              coalesce(r.proposition_sentences,[]) +
                                              CASE WHEN x='' THEN [] ELSE [x] END))
        FOREACH (x IN [coalesce($coref,'')] |
            SET r.coreference_sentences = apoc.coll.toSet(
                                              coalesce(r.coreference_sentences,[]) +
                                              CASE WHEN x='' THEN [] ELSE [x] END))
        FOREACH (x IN [coalesce($natural,'')] |
            SET r.natural_sentences = apoc.coll.toSet(
                                          coalesce(r.natural_sentences,[]) +
                                          CASE WHEN x='' THEN [] ELSE [x] END))
        FOREACH (x IN [coalesce($question,'')] |
            SET r.questions = apoc.coll.toSet(
                                  coalesce(r.questions,[]) +
                                  CASE WHEN x='' THEN [] ELSE [x] END))
        """,
        subj=subj,
        ss=subj_scope,
        obj=obj,
        os=obj_scope,
        context=context,
        propos=propos,
        coref=coref,
        natural=natural,
        question=question,
        inferred=inferred,
        qid=qid,
    )


__all__ = [
    "clear_neo4j_knowledge_graph",
    "_driver",
    "upsert_entity",
    "ensure_global_merge",
    "save_quadruple_rel",
]
