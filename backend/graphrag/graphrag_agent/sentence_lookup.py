"""Return evidence sentences for a list of quadruple IDs."""

from typing import Dict, List

from knowledge_graph_generator.database_utilities.kg_utilities import (
    _driver,
    NEO4J_DB,
)


def sentences_for_quadruples(qids: List[str]) -> List[Dict]:
    """
    For every *qid* in *qids* fetch:

      • 'natural_sentences'  if relation is inferred (`r.inferred = true`)
      • 'coreference_sentences' otherwise

    Returns
    -------
    list[dict]
        [
          {
            "quadruple_id": "e-6551",
            "inferred": false,
            "sentences": ["…", "…"]
          },
          …
        ]
        (entries with **no** sentences are omitted)
    """
    if not qids:
        return []

    payload: List[Dict] = []
    with _driver().session(database=NEO4J_DB) as sess:
        for qid in qids:
            row = sess.run(
                """
                MATCH (s)-[r]->(o)
                WHERE $qid IN r.quad_ids
                RETURN r.inferred              AS inferred,
                       r.natural_sentences     AS natural,
                       r.coreference_sentences AS coref
                LIMIT 1
                """,
                qid=qid,
            ).single()

            if not row:
                continue  # no such id in KG

            sentences = (row["natural"] if row["inferred"] else row["coref"]) or []
            if sentences:
                payload.append(
                    {
                        "quadruple_id": qid,
                        "inferred": row["inferred"],
                        "sentences": sentences,
                    }
                )

    return payload
