"""
neo4j_helpers.py
────────────────
One-stop convenience wrappers around `knowledge_graph_generator.database_utilities`.

Keeps graph-reasoning code agnostic of raw Cypher and driver plumbing.
"""

from typing import List, Dict, Tuple, Optional
from knowledge_graph_generator.database_utilities.kg_utilities import (
    _driver,
    NEO4J_DB,
)


# ------------------------------------------------------------------
# basic
# ------------------------------------------------------------------
def get_triple(qid: str) -> Optional[Tuple[str, str, str]]:
    """Return (subject, predicate, object) for *qid* or None."""
    cypher = """
        MATCH (s)-[r]->(o)
        WHERE $qid IN r.quad_ids
        RETURN s.name AS subj, type(r) AS pred, o.name AS obj
        LIMIT 1
    """
    with _driver().session(database=NEO4J_DB) as sess:
        row = sess.run(cypher, qid=qid).single()
    return (row["subj"], row["pred"], row["obj"]) if row else None


def get_edge_properties(qid: str) -> Optional[Dict]:
    """
    Return a dict with ALL stored properties on the edge: inferred flag,
    sentences lists, etc.  None if qid not found.
    """
    cypher = """
        MATCH (s)-[r]->(o)
        WHERE $qid IN r.quad_ids
        RETURN r AS rel
        LIMIT 1
    """
    with _driver().session(database=NEO4J_DB) as sess:
        row = sess.run(cypher, qid=qid).single()
    return dict(row["rel"]) if row else None


# ------------------------------------------------------------------
# neighbourhood (one hop each direction)
# ------------------------------------------------------------------
def get_neighbour_edges(qid: str, limit: int = 15) -> List[Dict]:
    """
    Return up to *limit* edges touching either node of the given qid.
    Keys in each dict:
        qid, from_node, predicate, to_node, inferred, sentences (list[str])
    """
    cypher = """
        MATCH (s)-[r]->(o)
        WHERE $qid IN r.quad_ids
        WITH s, o
        MATCH (n)-[r2]->(m)
        WHERE (n = s OR n = o OR m = s OR m = o)
              AND NOT $qid IN r2.quad_ids
        RETURN
            r2.quad_ids[0]          AS qid,
            type(r2)                AS predicate,
            n.name                  AS from_node,
            m.name                  AS to_node,
            r2.inferred             AS inferred,
            coalesce(r2.natural_sentences, r2.coreference_sentences, []) AS sentences
        LIMIT $limit
    """
    with _driver().session(database=NEO4J_DB) as sess:
        return sess.run(cypher, qid=qid, limit=limit).data()


