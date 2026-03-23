# -*- coding: utf-8 -*-
"""
021_batch_resume_pipeline.py
──────────────────────────────────────────────────────────────────────────────
Batch-process PubMedQA abstracts → Neo4j knowledge-graph.

    • Resumable: choose the CSV row to start from (--start, default = 1)
    • Processes up to N rows (--limit, default = 350)
    • Wipes Chroma + Neo4j only when starting from row 1

Run
----
# fresh run (rows 1-350)
python manage.py 021_batch_resume_pipeline

# resume from row 300, process the next 50 rows
python manage.py 021_batch_resume_pipeline --start 300 --limit 50
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, List

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils.timezone import now

# ── clean-slate helpers ────────────────────────────────────────────────
from knowledge_graph_generator.chroma_db.operations import clear_chroma_collections
from knowledge_graph_generator.database_utilities.kg_utilities import (
    clear_neo4j_knowledge_graph,
)

# ── LLM extraction + staging ───────────────────────────────────────────
from knowledge_graph_generator.services import send_paragraph_to_parallel_api
from knowledge_graph_generator.database_utilities.save_paragraph_to_db_staging import (
    save_paragraph_to_db_staging,
)

# ── mapping / vector ingest ────────────────────────────────────────────
from knowledge_graph_generator.chroma_db.ingest_staged_quads import (
    ingest_staging_paragraph,
)

# ── Neo4j persistence ─────────────────────────────────────────────────
from knowledge_graph_generator.database_utilities.save_to_kg import (
    save_json_to_knowledge_graph,
)

# ── models ────────────────────────────────────────────────────────────
from knowledge_graph_generator.models import StagingParagraph

# ----------------------------------------------------------------------
#  CONFIG CONSTANTS (can be edited quickly)
# ----------------------------------------------------------------------
DEFAULT_FILE  = (
    Path(settings.BASE_DIR).parent / "data/PUBMEDQA/pubmedqa_labelled_full.csv"
)
START_ROW     = 0     # ← hard-coded resume point (1-based index)
DEFAULT_LIMIT = 350    # ← how many rows to process from START_ROW


# ----------------------------------------------------------------------
# helper – build Neo4j payload from staged quads
# ----------------------------------------------------------------------
def _build_kg_payload(sp: StagingParagraph, aliases: List[Dict]) -> Dict:
    quad_groups = [{"quadruples": []}]
    inferred_groups: List[Dict] = []

    for sq in sp.quadruples.all():
        qd = {
            "quadruple": {
                "subject":         {"name": sq.subject_name, "types": sq.subject_types},
                "predicate":       sq.predicate,
                "predicate_types": sq.predicate_types,
                "object":          {"name": sq.object_name,  "types": sq.object_types},
                "reason":          sq.context_sentence,
            },
            "proposition_sentence":      sq.proposition_sentence,
            "coreference_sentence":      sq.coreference_sentence,
            "natural_language_sentence": sq.natural_language_sentence,
            "question":                  sq.question,
        }
        if sq.inferred:
            qd["inferred_quadruple_id"] = sq.quadruple_id
            inferred_groups.append(qd)
        else:
            qd["quadruple_id"] = sq.quadruple_id
            quad_groups[0]["quadruples"].append(qd)

    return {
        "paragraph_id":        sp.paragraph_id,
        "quadruples":          quad_groups,
        "inferred_quadruples": inferred_groups,
        "entity_aliases":      aliases,
    }


# ----------------------------------------------------------------------
class Command(BaseCommand):
    help = (
        "Process a batch of PubMedQA abstracts into Neo4j, starting from "
        "an arbitrary CSV row.  Wipes stores only when starting from row 1."
    )

    # ---------------- argparse ----------------
    def add_arguments(self, parser):
        parser.add_argument("--file",  type=str, default=str(DEFAULT_FILE))
        parser.add_argument("--start", type=int, default=START_ROW,
                            help="1-based CSV row to start from (default: 1)")
        parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT,
                            help="How many rows to process (default: 350)")

    # --------------- CSV row generator --------
    @staticmethod
    def _rows(csv_path: Path, start: int, limit: int):
        """
        Yield (absolute_idx, row_dict) for rows >= start, up to *limit* rows.
        """
        with csv_path.open(newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for abs_idx, row in enumerate(reader, 1):
                if abs_idx < start:
                    continue
                if abs_idx >= start + limit:
                    break
                yield abs_idx, row

    # ---------------- main --------------------
    def handle(self, *args, **opts):
        csv_path = Path(opts["file"]).expanduser().resolve()
        start    = int(opts["start"])
        limit    = int(opts["limit"])

        if start < 1:
            raise CommandError("--start must be ≥ 1")
        if limit <= 0:
            raise CommandError("--limit must be ≥ 1")
        if not csv_path.exists():
            raise CommandError(f"CSV not found: {csv_path}")

        # 0) wipe stores only when starting fresh ----------------------
        if start == 1:
            self.stdout.write(self.style.NOTICE("🧹  Clearing Chroma collections …"))
            clear_chroma_collections(verbose=False)
            self.stdout.write(self.style.SUCCESS("   Chroma cleared."))

            self.stdout.write(self.style.NOTICE("🧹  Clearing Neo4j knowledge graph …"))
            clear_neo4j_knowledge_graph()
            self.stdout.write(self.style.SUCCESS("   Neo4j cleared.\n"))
        else:
            self.stdout.write(self.style.WARNING(
                f"↩️  Resuming at row {start} – stores NOT wiped."
            ))

        # cumulative counters
        rollup = dict(paragraphs=0, quads=0, entities=0, types=0, questions=0)

        # 1) processing loop ------------------------------------------
        for abs_idx, row in self._rows(csv_path, start, limit):
            text = (row.get("labelled_contexts") or "").strip()
            if not text:
                self.stdout.write(self.style.WARNING(f"⚠️  Row {abs_idx}: empty text – skipped"))
                continue

            self.stdout.write(self.style.NOTICE(f"⏳  [{abs_idx}/{start+limit-1}] extracting …"))
            resp = send_paragraph_to_parallel_api(text)
            if not resp:
                self.stdout.write(self.style.ERROR(f"❌  Row {abs_idx}: extraction failed"))
                continue

            # stage
            paragraph, *_ = save_paragraph_to_db_staging(resp)
            sp = paragraph.staging_meta
            quad_cnt = sp.quadruples.count()

            # map/vectorise + push
            stats = ingest_staging_paragraph(sp)
            kg_payload = _build_kg_payload(sp, stats["aliases"])
            save_json_to_knowledge_graph(kg_payload)

            # mark as pushed
            sp.pushed_to_graph = True
            sp.push_target     = "neo4j"
            sp.pushed_at       = now()
            sp.save(update_fields=["pushed_to_graph", "push_target", "pushed_at"])

            # progress summary
            self.stdout.write(self.style.SUCCESS(
                f"✅  Row {abs_idx}: paragraph #{paragraph.id} → "
                f"{quad_cnt} quads, {stats['entities']} entities, {stats['types']} types"
            ))

            # roll-up
            rollup["paragraphs"] += 1
            rollup["quads"]      += quad_cnt
            rollup["entities"]   += stats["entities"]
            rollup["types"]      += stats["types"]
            rollup["questions"]  += stats["questions"]

        # 2) final report ---------------------------------------------
        self.stdout.write(self.style.SUCCESS("\n🎉  Batch complete!"))
        self.stdout.write(
            f"   • processed  : {rollup['paragraphs']} paragraph(s)\n"
            f"   • quads      : {rollup['quads']}\n"
            f"   • entities   : {rollup['entities']}\n"
            f"   • types      : {rollup['types']}\n"
            f"   • questions  : {rollup['questions']}"
        )