# backend/knowledge_graph_generator/management/commands/028_calculate_longest_paths.py
# ═════════════════════════════════════════════════════════════════════════════
"""
Compute, for each Paragraph, the longest shortest path (in hops) between
any two relationships that originate from that paragraph **and save the
results to <results/01_graphrag/00_retriever/paragraph_longest_paths.csv>**.

• One “hop”  = moving from one relationship to another via a shared entity node.
• A relationship is *in-scope* for a paragraph if *any* of its `quad_ids`
  belongs to one of that paragraph’s (extracted or inferred) quads.

Usage
─────
# single paragraph (e.g. id 123)
python manage.py 028_calculate_longest_paths --paragraph 123

# all paragraphs (≈ 350 rows) and write the CSV
python manage.py 028_calculate_longest_paths
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import networkx as nx                       # pip install networkx
from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Prefetch
from tabulate import tabulate                # pip install tabulate

from knowledge_graph_generator.database_utilities.kg_utilities import _driver
from knowledge_graph_generator.models import (
    InferredQuadruple,
    Paragraph,
    Quadruple,
)

# ─────────────────────────────────────────────────────────────────────────────
#  output CSV path (same hierarchy as 027_pubmedqa_question_cosines.py)
# ─────────────────────────────────────────────────────────────────────────────
ROOT_DIR     = Path(settings.BASE_DIR).parent
RESULTS_DIR  = ROOT_DIR / "results/01_graphrag/00_retriever"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
OUT_CSV      = RESULTS_DIR / "paragraph_longest_paths.csv"

# ─────────────────────────────────────────────────────────────────────────────
#  helpers
# ─────────────────────────────────────────────────────────────────────────────
def _quad_ids_for_paragraph(p: Paragraph) -> list[str]:
    """Build the exact `quad_id` strings stored on Neo4j relationships."""
    extracted = [f"e-{qid}" for qid in p.quadruples.values_list("id", flat=True)]
    inferred  = [f"i-{qid}" for qid in p.inferred_quadruples.values_list("id", flat=True)]
    return extracted + inferred


def _neo4j_edges_for_quad_ids(qids: list[str]) -> list[tuple[int, int, int]]:
    """(rel_id, subj_id, obj_id) triples for relationships whose `quad_ids` intersect *qids*."""
    if not qids:
        return []
    cypher = """
        MATCH (s:Entity)-[r]->(o:Entity)
        WHERE any(qid IN r.quad_ids WHERE qid IN $qids)
        RETURN id(r) AS rid, id(s) AS sid, id(o) AS oid
    """
    with _driver().session(database="pubmedqa-context") as sess:
        return [(rec["rid"], rec["sid"], rec["oid"]) for rec in sess.run(cypher, qids=qids)]


def _max_hops(edges: list[tuple[int, int, int]]) -> int:
    """
    Build a *relationship graph* and return its diameter (longest shortest-path length).
    Returns 0 if the paragraph has ≤ 1 relationship.
    """
    rel_to_pair = {rid: (sid, oid) for rid, sid, oid in edges}
    g = nx.Graph()

    rel_ids = list(rel_to_pair)
    for i, rid1 in enumerate(rel_ids):
        s1, o1 = rel_to_pair[rid1]
        for rid2 in rel_ids[i + 1 :]:
            s2, o2 = rel_to_pair[rid2]
            if {s1, o1} & {s2, o2}:              # share an endpoint → adjacent
                g.add_edge(rid1, rid2)

    if g.number_of_nodes() <= 1:
        return 0

    max_hops = 0
    for comp in nx.connected_components(g):
        sub = g.subgraph(comp)
        if sub.number_of_nodes() <= 1:
            continue
        lengths  = nx.all_pairs_shortest_path_length(sub)
        comp_dia = max(max(d.values()) for _, d in lengths)
        max_hops = max(max_hops, comp_dia)
    return max_hops


# ─────────────────────────────────────────────────────────────────────────────
#  management command
# ─────────────────────────────────────────────────────────────────────────────
class Command(BaseCommand):
    help = (
        "Compute the paragraph-level graph diameter (in relationship hops) and "
        "write the results to results/01_graphrag/00_retriever/paragraph_longest_paths.csv"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--paragraph",
            type=int,
            help="Process only the given Paragraph ID (handy for testing).",
        )

    # ------------------------------------------------------------------ main
    def handle(self, *args, **opts):
        only_pid = opts.get("paragraph")

        qs = (
            Paragraph.objects.all()
            .order_by("id")
            .prefetch_related(
                Prefetch("quadruples",          queryset=Quadruple.objects.only("id")),
                Prefetch("inferred_quadruples", queryset=InferredQuadruple.objects.only("id")),
            )
        )
        if only_pid:
            qs = qs.filter(id=only_pid)
            if not qs.exists():
                self.stderr.write(self.style.ERROR(f"Paragraph id={only_pid} not found"))
                sys.exit(1)

        rows: list[tuple[int, int]] = []   # [(paragraph_id, max_hops)]

        self.stdout.write(self.style.NOTICE("⏳  Calculating …\n"))
        for p in qs:
            qids  = _quad_ids_for_paragraph(p)
            edges = _neo4j_edges_for_quad_ids(qids)
            hops  = _max_hops(edges)
            rows.append((p.id, hops))
            self.stdout.write(f"Paragraph {p.id:<5} → max hops = {hops}")

        # ── console summary table ────────────────────────────────────
        self.stdout.write("\n" + tabulate(rows,
                                          headers=["Paragraph ID", "Max Hops"],
                                          tablefmt="github"))

        # ── write CSV ────────────────────────────────────────────────
        with OUT_CSV.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["paragraph_id", "max_hops"])
            writer.writerows(rows)

        rel_path = OUT_CSV.relative_to(ROOT_DIR)
        self.stdout.write(self.style.SUCCESS(f"\n✅  Saved results → {rel_path}"))