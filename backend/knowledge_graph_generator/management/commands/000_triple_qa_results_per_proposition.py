# backend/knowledge_graph_generator/management/commands/028_quad_qa_sims_parallel.py
from django.core.management.base import BaseCommand
from knowledge_graph_generator.models import Proposition
from knowledge_graph_generator.pipeline_utilities.sentence_similarity import compute_similarity

from pathlib import Path
from pydantic import BaseModel
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List
import threading, queue
import csv, sys, time
from django.conf import settings

# ─────────────────────────────────────────────────────────────────────────────
# OpenAI client (inline API key as requested)
# ─────────────────────────────────────────────────────────────────────────────
try:
    from openai import OpenAI
except Exception:
    OpenAI = None

_thread_ctx = threading.local()

def _get_thread_client() -> OpenAI:
    """One OpenAI client per worker thread."""
    if getattr(_thread_ctx, "client", None) is None:
        if OpenAI is None:
            raise RuntimeError(
                "openai package not installed. Run: pip install openai pydantic"
            )

        api_key = getattr(settings, "OPENAI_API_KEY", None)
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not configured. Add it to your .env file."
            )

        _thread_ctx.client = OpenAI(api_key=api_key)

    return _thread_ctx.client

# ─────────────────────────────────────────────────────────────────────────────
# Typed response models (match earlier commands)
# ─────────────────────────────────────────────────────────────────────────────
class Entity(BaseModel):
    name: str
    types: List[str]

class QuadrupleWithEntityTypes(BaseModel):
    subject: Entity
    predicate: str
    predicate_types: List[str]
    object: Entity
    reason: str

class KnowledgeQuadruplesWithEntitiesResponse(BaseModel):
    quadruples: List[QuadrupleWithEntityTypes]

class NLResponse(BaseModel):
    sentence: str

# ─────────────────────────────────────────────────────────────────────────────
# Prompts (IDENTICAL to your validated runs)
# ─────────────────────────────────────────────────────────────────────────────
def extract_quads_with_reason(text: str) -> List[QuadrupleWithEntityTypes]:
    client = _get_thread_client()
    sys_prompt = (
        "Extract knowledge triples and their types for every relationship/predicate in the given sentence. "
        "Each quadruple should include:\n"
        "1. **Subject**: Provide the subject name and a list of possible ontological types for the entity.\n"
        "2. **Predicate**: Provide the predicate and a list of possible ontological types for the predicate.\n"
        "3. **Object**: Provide the object name and a list of possible ontological types for the entity.\n"
        "Do not leave any possible triples out. Represent the information in the sentence as accurately as possible. All triples must be able to fully represent the original sentence through their reason. "
        "Ensure the response is in JSON format."
    )
    rsp = client.beta.chat.completions.parse(
        model="gpt-4.1-nano",
        temperature=0,
        messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "user",   "content": text},
        ],
        response_format=KnowledgeQuadruplesWithEntitiesResponse,
    )
    return rsp.choices[0].message.parsed.quadruples

def triple_to_sentence_llm(triple_dict: dict) -> str | None:
    client = _get_thread_client()
    subj = triple_dict["subject"]["name"]
    pred = triple_dict["predicate"]
    obj  = triple_dict["object"]["name"]

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

    try:
        completion = client.beta.chat.completions.parse(
            model="gpt-4.1-mini",
            temperature=0,
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            response_format=NLResponse,
    )
        return completion.choices[0].message.parsed.sentence.strip()
    except Exception:
        return None

def quadruple_to_question(quadruple: dict) -> str | None:
    client = _get_thread_client()
    model = "gpt-4.1-nano"
    subject   = quadruple["subject"]["name"]
    predicate = quadruple["predicate"]
    obj       = quadruple["object"]["name"]
    reason    = quadruple.get("reason", "")

    prompt = (
        "You are a question-generation assistant. Your job is to take a knowledge quadruple and generate a single "
        "natural-language question that would be precisely and completely answered by the information in the quadruple.\n\n"
        f"Here is the quadruple:\n"
        f"Subject: {subject}\n"
        f"Predicate: {predicate}\n"
        f"Object: {obj}\n"
        f"Reason: {reason}\n\n"
        "Write a question that someone might ask to which this exact quadruple would be the complete answer."
    )

    try:
        completion = client.beta.chat.completions.parse(
            model=model,
            temperature=0,
            messages=[
                {"role": "system", "content": "You generate precise questions from structured knowledge data."},
                {"role": "user",   "content": prompt}
            ]
        )
        return completion.choices[0].message.content.strip()
    except Exception:
        return None

def question_to_sentence(question: str) -> str | None:
    client = _get_thread_client()
    model = "gpt-4o-mini"
    system_prompt = (
        "You are an assistant that generates natural-sounding declarative sentences "
        "that directly and completely answer user questions. The sentence should be informative and self-contained."
        "The answer should be a single sentence."
    )
    user_prompt = f"Question: {question}\n\nWrite a complete, natural-sounding sentence that answers the question."

    try:
        completion = client.beta.chat.completions.parse(
            model=model,
            temperature=0,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt}
            ]
        )
        return completion.choices[0].message.content.strip()
    except Exception:
        return None

# ─────────────────────────────────────────────────────────────────────────────
# Progress bar
# ─────────────────────────────────────────────────────────────────────────────
def _fmt_time(seconds: float) -> str:
    seconds = max(0, int(seconds))
    m, s = divmod(seconds, 60); h, m = divmod(m, 60)
    return f"{h:d}h{m:02d}m" if h > 0 else f"{m:d}m{s:02d}s"

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

# ─────────────────────────────────────────────────────────────────────────────
# Per-proposition worker
# ─────────────────────────────────────────────────────────────────────────────
def process_one_prop(item: tuple[int, int, str], quad_workers: int) -> list[list[str]]:
    """
    For one proposition: extract quads, then for each quad compute:
      • triple_similarity (triple→sentence vs coref)
      • qa_similarity     (quad→question→answer vs coref)
    Returns list of CSV rows [paragraph_id, proposition_id, quad_index, triple_similarity, qa_similarity]
    """
    paragraph_id, proposition_id, coref_sentence = item
    try:
        quads = extract_quads_with_reason(coref_sentence)
    except Exception:
        return []

    if not quads:
        # Write at least one row to mark "no quads" (both sims blank)
        return [[str(paragraph_id), str(proposition_id), "0", "", ""]]

    def _do_quad(idx: int, q: QuadrupleWithEntityTypes) -> list[str]:
        subj = q.subject.name
        pred = q.predicate
        obj  = q.object.name

        # Triple → sentence (no reason)
        triple_dict = {"subject": {"name": subj}, "predicate": pred, "object": {"name": obj}}
        triple_sentence = triple_to_sentence_llm(triple_dict)
        triple_sim = compute_similarity(coref_sentence, triple_sentence) if triple_sentence else None

        # Quad (+reason) → question → answer
        quad_dict = {
            "subject": {"name": subj, "types": q.subject.types},
            "predicate": pred,
            "predicate_types": q.predicate_types,
            "object": {"name": obj, "types": q.object.types},
            "reason": q.reason or ""
        }
        question = quadruple_to_question(quad_dict)
        answer_sentence = question_to_sentence(question) if question else None
        qa_sim = compute_similarity(coref_sentence, answer_sentence) if answer_sentence else None

        return [
            str(paragraph_id),
            str(proposition_id),
            str(idx),
            f"{triple_sim:.6f}" if isinstance(triple_sim, (int, float)) else "",
            f"{qa_sim:.6f}"     if isinstance(qa_sim,     (int, float)) else "",
        ]

    rows: list[list[str]] = []
    if quad_workers and quad_workers > 1 and len(quads) > 1:
        with ThreadPoolExecutor(max_workers=quad_workers) as ex:
            futs = [ex.submit(_do_quad, i, q) for i, q in enumerate(quads, start=1)]
            for f in as_completed(futs):
                try:
                    rows.append(f.result())
                except Exception:
                    pass
        rows.sort(key=lambda r: int(r[2]))  # keep stable order by quad_index
    else:
        for i, q in enumerate(quads, start=1):
            try:
                rows.append(_do_quad(i, q))
            except Exception:
                pass

    return rows

# ─────────────────────────────────────────────────────────────────────────────
# Management Command
# ─────────────────────────────────────────────────────────────────────────────
class Command(BaseCommand):
    help = (
        "Parallel export of per-quad similarities only:\n"
        "  • For each proposition with non-empty coreference, extract quadruples (triple+types+reason)\n"
        "  • For each quadruple: compute triple→sentence and question→answer similarities vs coref\n"
        "  • Write minimal CSV rows (no text): paragraph_id, proposition_id, quad_index, triple_similarity, qa_similarity\n"
        "Options: --prop-workers (outer threads), --quad-workers (inner threads), --limit, --start-id"
    )

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=None, help="Optional cap on number of propositions.")
        parser.add_argument("--start-id", type=int, default=None, help="Process propositions with id >= start-id.")
        parser.add_argument("--prop-workers", type=int, default=6, help="Threads over propositions.")
        parser.add_argument("--quad-workers", type=int, default=3, help="Threads per proposition over quadruples.")

    def handle(self, *args, **options):
        # Output path
        cmd_path     = Path(__file__).resolve()
        backend_dir  = cmd_path.parents[3]       # .../backend
        project_root = backend_dir.parent        # .../the-everything-engine
        out_dir      = project_root / "results" / "00_fully_organized_results" / "02_grouped_triples_and_question_extraction_(not_combined)"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_csv      = out_dir / "quad_qa_similarities02.csv"

        # Prepare CSV (overwrite each run)
        with out_csv.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([
                "paragraph_id", "proposition_id", "quad_index",
                "triple_similarity", "qa_similarity"
            ])

        # Query propositions
        qs = (Proposition.objects
              .select_related("paragraph")
              .exclude(coreferenced_text__isnull=True)
              .exclude(coreferenced_text__exact="")
              .order_by("id"))
        start_id = options.get("start_id")
        if start_id:
            qs = qs.filter(id__gte=start_id)
        limit = options.get("limit")
        if limit:
            qs = qs[:limit]

        props = list(qs.values_list("paragraph_id", "id", "coreferenced_text"))
        total = len(props)
        if total == 0:
            self.stdout.write(self.style.WARNING("No propositions with coreference sentences found."))
            return

        prop_workers = max(1, int(options.get("prop_workers") or 1))
        quad_workers = max(1, int(options.get("quad_workers") or 1))

        # Writer thread
        Q: "queue.Queue[list[str] | None]" = queue.Queue(maxsize=2000)
        stop = None

        def writer():
            with out_csv.open("a", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                while True:
                    item = Q.get()
                    if item is stop:
                        break
                    w.writerow(item)
                    Q.task_done()

        wt = threading.Thread(target=writer, daemon=True)
        wt.start()

        # Progress / stats
        start_t = time.perf_counter()
        done = 0
        rows_out = 0

        # Outer pool
        with ThreadPoolExecutor(max_workers=prop_workers) as pool:
            futs = [pool.submit(process_one_prop, item, quad_workers) for item in props]
            for f in as_completed(futs):
                try:
                    rows = f.result()
                except Exception:
                    rows = []
                for r in rows:
                    Q.put(r)
                    rows_out += 1
                done += 1
                progress_bar(done, total, start_t)

        # Drain + stop writer
        Q.join()
        Q.put(stop)
        wt.join()

        self.stdout.write(self.style.SUCCESS("\nExport complete."))
        self.stdout.write(f"Propositions processed: {done}/{total}")
        self.stdout.write(f"Rows written:          {rows_out}")
        self.stdout.write(f"prop-workers={prop_workers}  quad-workers={quad_workers}")