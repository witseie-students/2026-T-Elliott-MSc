# backend/knowledge_graph_generator/management/commands/017_export_propositions_combined.py
from django.core.management.base import BaseCommand
from pathlib import Path
import csv
import time

from knowledge_graph_generator.models import Paragraph


def _fmt_time(seconds: float) -> str:
    seconds = max(0, int(seconds))
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return f"{h:d}h{m:02d}m{s:02d}s" if h else f"{m:d}m{s:02d}s"


def _progress(i: int, total: int, start_t: float, width: int = 44) -> None:
    frac = 0 if total == 0 else i / total
    filled = int(width * frac)
    bar = "█" * filled + "─" * (width - filled)
    elapsed = time.perf_counter() - start_t
    eta = (elapsed / i) * (total - i) if i > 0 else 0
    print(
        f"\rProgress: |{bar}| {i:>6}/{total:<6} ({frac*100:5.1f}%)  ETA {_fmt_time(eta)}",
        end="",
        flush=True,
    )
    if i == total:
        print("")


class Command(BaseCommand):
    help = (
        "Export per-paragraph combined proposition similarity to CSV.\n"
        "Reads Paragraph.propositions_similarity and writes:\n"
        "  results/paragraph_results/propositions_combined.csv\n"
        "Columns: paragraph_id, combined_proposition_similarity"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--only-non-null",
            action="store_true",
            default=False,
            help="If set, include only paragraphs where propositions_similarity is not NULL.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Optional cap on number of paragraphs (for quick tests).",
        )

    def handle(self, *args, **opts):
        # Resolve output path relative to repo root
        cmd_path = Path(__file__).resolve()
        backend_dir = cmd_path.parents[3]        # .../backend
        project_root = backend_dir.parent        # .../the-everything-engine
        out_dir = project_root / "results" / "00_triple_vs_proposition"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_csv = out_dir / "propositions_combined.csv"

        # Build queryset
        qs = Paragraph.objects.all().order_by("id")
        if opts["only_non_null"]:
            qs = qs.exclude(propositions_similarity__isnull=True)
        if opts["limit"]:
            qs = qs[: opts["limit"]]

        total = qs.count()
        if total == 0:
            self.stdout.write(self.style.WARNING("No Paragraph rows match the criteria."))
            return

        self.stdout.write(self.style.SUCCESS(f"Exporting {total} paragraphs → {out_csv}"))
        start_t = time.perf_counter()

        written = 0
        with out_csv.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["paragraph_id", "combined_proposition_similarity"])

            # Stream rows to avoid loading everything into memory
            for i, p in enumerate(qs.iterator(chunk_size=1000), start=1):
                val = p.propositions_similarity
                # Write blank if NULL to preserve CSV shape (consistent with earlier exports)
                w.writerow([p.id, f"{val:.6f}" if isinstance(val, (int, float)) else ""])
                written += 1
                _progress(i, total, start_t)

        self.stdout.write(self.style.SUCCESS(f"Done. Wrote {written} rows to: {out_csv}"))