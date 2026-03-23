from django.core.management.base import BaseCommand, CommandError
from pathlib import Path
import csv
import os
import sys
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional, Union

from pydantic import BaseModel
from knowledge_graph_generator.models import Paragraph
from knowledge_graph_generator.pipeline_utilities.sentence_similarity import compute_similarity

# --- OpenAI client --------------------------------------------------------
try:
    from openai import OpenAI
except Exception:
    OpenAI = None


# ====== Pydantic schemas ===================================================

class Entity(BaseModel):
    name: str
    types: List[str]

class TripleWithEntityTypes(BaseModel):
    subject: Entity
    predicate: str
    predicate_types: List[str]
    object: Entity

class KnowledgeTriplesWithEntitiesResponse(BaseModel):
    triples: List[TripleWithEntityTypes]

class NLResponse(BaseModel):
    sentence: str


# ====== OpenAI client helpers (thread-safe) ===============================

def _require_api_key() -> str:
    api_key = "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"
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY not set. Export it in your shell, e.g.\n"
            "  export OPENAI_API_KEY='sk-...'\n"
        )
    return api_key

def _get_client() -> OpenAI:
    if OpenAI is None:
        raise RuntimeError("openai package not installed. Run `pip install openai pydantic`.")
    return OpenAI(api_key=_require_api_key())

# one client per worker thread
_thread_ctx = threading.local()
def _get_thread_client() -> OpenAI:
    if getattr(_thread_ctx, "client", None) is None:
        _thread_ctx.client = _get_client()
    return _thread_ctx.client


# ====== Retry helpers ======================================================

def _sleep_backoff(attempt: int) -> None:
    # 1, 2, 4, 8, 16 seconds (cap at 16)
    delay = min(16, 2 ** (attempt - 1))
    time.sleep(delay)

def _extract_with_retries(client: OpenAI, text: str, max_attempts: int = 5) -> List[TripleWithEntityTypes]:
    last_err = None
    for attempt in range(1, max_attempts + 1):
        try:
            sys_prompt = (
                "Extract knowledge triples and their types for every relationship in the given sentence. "
                "Each triple should include:\n"
                "1. **Subject**: Provide the subject name and a list of possible ontological types for the entity.\n"
                "2. **Predicate**: Provide the predicate and a list of possible ontological types for the predicate.\n"
                "3. **Object**: Provide the object name and a list of possible ontological types for the entity.\n\n"
                "Do not leave any possible triples out. Represent the information in the sentence as accurately as possible. "
                "Ensure the response is in JSON format."
            )
            completion = client.beta.chat.completions.parse(
                model="gpt-4.1-mini",
                temperature=0,
                messages=[
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": text},
                ],
                response_format=KnowledgeTriplesWithEntitiesResponse,
            )
            return completion.choices[0].message.parsed.triples
        except Exception as e:
            last_err = e
            if attempt < max_attempts:
                _sleep_backoff(attempt)
            else:
                print(f"⚠️  extract failed after {max_attempts} attempts: {e}")
    return []  # on failure

def _verbalize_with_retries(triple: Union[TripleWithEntityTypes, dict],
                            allow_fallback: bool = True,
                            max_attempts: int = 5) -> Optional[str]:
    client = _get_thread_client()

    if isinstance(triple, TripleWithEntityTypes):
        subj = triple.subject.name
        pred = triple.predicate
        obj  = triple.object.name
    else:
        subj = triple["subject"]["name"]
        pred = triple["predicate"]
        obj  = triple["object"]["name"]

    sys_prompt = (
        "You convert a single knowledge-graph triple into ONE clear English sentence.\n"
        "Do not add facts, qualifiers, or extra context beyond the triple.\n"
        "Use a fluent, neutral style. Output JSON: {\"sentence\": \"...\"}."
    )
    user_prompt = (
        "Triple:\n"
        f"  subject: {subj}\n"
        f"  predicate: {pred}\n"
        f"  object: {obj}\n"
        "\nReturn JSON with one field 'sentence'."
    )

    last_err = None
    for attempt in range(1, max_attempts + 1):
        try:
            completion = client.beta.chat.completions.parse(
                model="gpt-4.1-mini",
                temperature=0,
                messages=[
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format=NLResponse,
            )
            sentence = completion.choices[0].message.parsed.sentence.strip()
            if sentence:
                return sentence
        except Exception as e:
            last_err = e
            if attempt < max_attempts:
                _sleep_backoff(attempt)
            else:
                print(f"⚠️  verbalize failed after {max_attempts} attempts: {e}")

    if allow_fallback:
        # Guarantee a sentence so we can compute similarity
        return f"{subj} {pred} {obj}."
    return None


# ====== Progress bar =======================================================

def _fmt_time(seconds: float) -> str:
    seconds = max(0, int(seconds))
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:d}h{m:02d}m"
    return f"{m:d}m{s:02d}s"

def progress_bar(i: int, total: int, start_t: float, width: int = 44) -> None:
    frac = 0 if total == 0 else i / total
    filled = int(width * frac)
    bar = "█" * filled + "─" * (width - filled)
    elapsed = time.perf_counter() - start_t
    eta = (elapsed / i) * (total - i) if i > 0 else 0
    sys.stdout.write(f"\rProgress: |{bar}| {i:>6}/{total:<6} ({frac*100:5.1f}%)  ETA {_fmt_time(eta)}")
    sys.stdout.flush()
    if i == total:
        sys.stdout.write("\n")


# ====== Django management command =========================================

class Command(BaseCommand):
    help = (
        "For every Paragraph, extract SPO triples (with ontological types) from the paragraph text, "
        "verbalize each triple into a sentence, concatenate those sentences, and compute cosine similarity "
        "vs. the original paragraph text (paraphrase-MiniLM-L6-v2). "
        "Writes results/paragraph_results/single_extraction.csv with columns: "
        "paragraph_id, n_triples, combined_similarity."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--workers", type=int, default=int(os.getenv("BACKTEST_WORKERS", "4")),
            help="Number of worker threads for per-triple verbalisation (default: 4)."
        )
        parser.add_argument(
            "--only-with-text", action="store_true", default=False,
            help="If set, process only paragraphs with non-empty input_text."
        )
        parser.add_argument(
            "--no-fallback", action="store_true", default=False,
            help="Disable templated fallback sentences if verbalisation fails."
        )
        parser.add_argument(
            "--limit", type=int, default=None,
            help="Optional cap on number of paragraphs (for quick tests)."
        )

    def handle(self, *args, **options):
        # Output path
        cmd_path      = Path(__file__).resolve()
        backend_dir   = cmd_path.parents[3]          # .../backend
        project_root  = backend_dir.parent           # .../the-everything-engine
        out_dir       = project_root / "results" / "00_triple_vs_proposition"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_csv_path  = out_dir / "single_extraction.csv"

        # Paragraph queryset
        qs = Paragraph.objects.all().order_by("id")
        if options["only_with_text"]:
            qs = qs.exclude(input_text__isnull=True).exclude(input_text__exact="")

        if options["limit"]:
            qs = qs[: options["limit"]]

        total = qs.count()
        if total == 0:
            self.stdout.write(self.style.WARNING("No paragraphs to process."))
            return

        # OpenAI client used for extraction (per paragraph)
        try:
            main_client = _get_client()
        except Exception as e:
            raise CommandError(str(e))

        max_workers   = max(1, options["workers"])
        allow_fallback = not options["no_fallback"]

        with out_csv_path.open("w", newline="", encoding="utf-8") as out_f:
            writer = csv.writer(out_f)
            writer.writerow(["paragraph_id", "n_triples", "combined_similarity"])

            self.stdout.write(self.style.SUCCESS(
                f"Processing {total} paragraphs with workers={max_workers}..."
            ))
            start_t = time.perf_counter()

            processed = 0
            for para in qs.iterator(chunk_size=250):
                paragraph_id   = para.id
                paragraph_text = (para.input_text or "").strip()

                combined_similarity: Optional[float] = None
                n_triples = 0

                if paragraph_text:
                    # 1) Extract triples (retries)
                    triples = _extract_with_retries(main_client, paragraph_text, max_attempts=5)
                    n_triples = len(triples)

                    # 2) Verbalize each triple (parallel + retries + fallback)
                    sentences: List[str] = []
                    if n_triples > 0:
                        def _proc_one(tr):
                            try:
                                return _verbalize_with_retries(tr, allow_fallback=allow_fallback, max_attempts=5)
                            except Exception:
                                return None

                        with ThreadPoolExecutor(max_workers=max_workers) as ex:
                            futs = [ex.submit(_proc_one, tr) for tr in triples]
                            for fut in as_completed(futs):
                                s = fut.result()
                                if isinstance(s, str) and s.strip():
                                    sentences.append(s.strip())

                    # 3) Similarity vs original paragraph
                    if sentences:
                        combined = " ".join(sentences)
                        try:
                            sim = compute_similarity(paragraph_text, combined)
                            if isinstance(sim, (int, float)):
                                combined_similarity = float(sim)
                        except Exception as e:
                            print(f"⚠️  similarity failed for paragraph {paragraph_id}: {e}")

                # Write row (no text stored)
                writer.writerow([
                    paragraph_id,
                    n_triples,
                    f"{combined_similarity:.6f}" if isinstance(combined_similarity, float) else ""
                ])

                processed += 1
                progress_bar(processed, total, start_t, width=44)

        self.stdout.write(self.style.SUCCESS(
            f"Done. Wrote {total} rows to: {out_csv_path}"
        ))