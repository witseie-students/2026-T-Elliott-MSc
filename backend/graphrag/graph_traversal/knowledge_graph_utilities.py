# graphrag/graph_traversal/knowledge_graph_utilities.py
# ═══════════════════════════════════════════════════════
"""
Neo4j utilities.

• fetch_central_only(seed_qid)
• fetch_central_and_neighbours(seed_qid, exclude_qids=set())

Design
──────
• Nodes are keyed in Neo4j by (name, paragraph_scope).
• For neighbours, we *explicitly* pull subject / object names in Cypher
  using startNode()/endNode(), so the Python side never has to guess
  or fall back to internal element IDs.
"""

from __future__ import annotations
from typing import Dict, Any, List, Set

from neo4j import GraphDatabase
from knowledge_graph_generator.database_utilities.kg_utilities import (
    NEO4J_URI,
    NEO4J_USER,
    NEO4J_PASSWORD,
    NEO4J_DB,
)


# ── connection helper ───────────────────────────────────────────────
def _driver():
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


# ── misc helpers ────────────────────────────────────────────────────
def _first_sentence(props: dict) -> str:
    for k in ("coreference_sentences",
              "natural_sentences",
              "proposition_sentences"):
        v = props.get(k)
        if v:
            return v[0]
    return "(no sentence)"


def _node_name(node) -> str:
    """
    Return a human-readable node name.

    For the central edge we still apply a few fallbacks; for neighbours
    we rely on explicit names returned from Cypher.
    """
    if node is None:
        return "(UNNAMED_ENTITY)"

    # primary: 'name'
    name = node.get("name")
    if isinstance(name, str) and name.strip():
        return name.strip()

    # fallbacks: canonical names / aliases
    for key in ("canonical_names", "aliases"):
        arr = node.get(key)
        if isinstance(arr, list):
            for v in arr:
                if isinstance(v, str) and v.strip():
                    return v.strip()

    # generic fallback over string props
    skip = {
        "id", "element_id", "quad_ids", "quadruple_ids",
        "inferred", "ontological_types", "types",
        "paragraph_scope", "paragraph_ids", "is_ontological",
        "is_canonical",
    }
    for k, v in node.items():
        if k in skip:
            continue
        if isinstance(v, str) and v.strip():
            return v.strip()

    return "(UNNAMED_ENTITY)"


# ── central only ────────────────────────────────────────────────────
def fetch_central_only(seed_quad_id: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {"central": None}
    with _driver().session(database=NEO4J_DB) as sess:
        rec = sess.run(
            """
            MATCH (s:Entity)-[r]->(o:Entity)
            WHERE $qid IN r.quad_ids
            RETURN s,o,r
            LIMIT 1
            """,
            qid=seed_quad_id,
        ).single()

    if rec:
        s_node, o_node, rel = rec["s"], rec["o"], rec["r"]
        out["central"] = {
            "triple":        [_node_name(s_node),
                              type(rel).__name__,
                              _node_name(o_node)],
            "subject_types": s_node.get("ontological_types", []),
            "object_types":  o_node.get("ontological_types", []),
            "quadruple_ids": rel["quad_ids"],
            "inferred":      rel.get("inferred", False),
            "sentence":      _first_sentence(rel),
        }
    return out


# ── central + neighbours ────────────────────────────────────────────
def fetch_central_and_neighbours(seed_quad_id: str,
                                 exclude_qids: Set[str] | None = None
                                 ) -> Dict[str, Any]:
    """
    Return the central edge *and* all 1-hop neighbours.

    Neighbours are any relationships incident on either endpoint of the
    central edge. We explicitly pull the subject / object names in the
    Cypher query to avoid relying on driver-specific Node wrappers.
    """
    exclude_qids = exclude_qids or set()
    payload: Dict[str, Any] = {"central": None, "neighbours": []}
    seen_qids: Set[str] = set()  # dedupe by first QID

    with _driver().session(database=NEO4J_DB) as sess:
        rec = sess.run(
            """
            MATCH (s:Entity)-[r]->(o:Entity)
            WHERE $qid IN r.quad_ids
            WITH s,r,o

            // left neighbours: edges out of the central subject
            OPTIONAL MATCH (s)-[lr]->(ln:Entity)
            WITH s,r,o,
                 collect(
                   { rel:  lr,
                     subj: s.name,
                     obj:  ln.name }
                 ) AS lrels

            // right neighbours: edges into the central object
            OPTIONAL MATCH (rn:Entity)-[rr]->(o)
            WITH s,o,r,lrels,
                 collect(
                   { rel:  rr,
                     subj: rn.name,
                     obj:  o.name }
                 ) AS rrels

            RETURN s,o,r,lrels,rrels
            """,
            qid=seed_quad_id,
        ).single()

    if rec is None:
        return payload

    s_node, o_node, central_rel = rec["s"], rec["o"], rec["r"]

    # central edge ----------------------------------------------------
    payload["central"] = {
        "triple":        [_node_name(s_node),
                          type(central_rel).__name__,
                          _node_name(o_node)],
        "subject_types": s_node.get("ontological_types", []),
        "object_types":  o_node.get("ontological_types", []),
        "quadruple_ids": central_rel["quad_ids"],
        "inferred":      central_rel.get("inferred", False),
        "sentence":      _first_sentence(central_rel),
    }

    # neighbours (left + right) --------------------------------------
    for entry in (rec["lrels"] or []) + (rec["rrels"] or []):
        if entry is None:
            continue
        rel = entry.get("rel")
        if rel is None:
            continue

        qids: List[str] = rel["quad_ids"]
        if any(q in exclude_qids for q in qids):
            continue

        main_qid = qids[0]
        if main_qid in seen_qids:
            continue
        seen_qids.add(main_qid)

        subj_name = entry.get("subj") or "(UNNAMED_ENTITY)"
        obj_name  = entry.get("obj")  or "(UNNAMED_ENTITY)"

        payload["neighbours"].append(
            {
                "triple":        [subj_name,
                                  type(rel).__name__,
                                  obj_name],
                "quadruple_ids": qids,
                "inferred":      rel.get("inferred", False),
                "sentence":      _first_sentence(rel),
            }
        )

    return payload