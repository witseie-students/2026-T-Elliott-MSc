# backend/knowledge_graph_generator/management/commands/024_paragraph_triple_recombine.py
"""
Paragraph-level back-validation via recomposed triples + proposition/coref aggregates.

For each paragraph:
  1) For each proposition with a non-empty coreference sentence:
       - Extract triples (S, P, O) WITHOUT reason.
       - LLM: combine those triples into ONE sentence.
  2) Concatenate all recomposed sentences (prop-id order) → a "recombined" paragraph.
  3) Concatenate all proposition texts for the paragraph → "props" paragraph.
  4) Concatenate all coreference sentences for the paragraph → "corefs" paragraph.
  5) Compute cosine similarity of each aggregate vs the original paragraph (Paragraph.input_text).
  6) Write one CSV row per paragraph:
       paragraph_id,
       recombined_triple_similarity,
       combined_proposition_similarity,
       combined_coref_similarity

Output CSV:
  results/paragrph_level_results/combined_paragraph_from_triples.csv

Options:
  --para-workers     threads over paragraphs (default: 4)
  --prop-workers     threads over propositions in a paragraph (default: 4)
  --limit            optional cap on number of paragraphs
  --start-id         process paragraphs with id >= start-id
"""

from django.core.management.base import BaseCommand
from knowledge_graph_generator.models import Proposition
from knowledge_graph_generator.pipeline_utilities.sentence_similarity import compute_similarity

from pathlib import Path
from pydantic import BaseModel
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional, Tuple, Dict
import threading, queue
import csv, sys, time, os

from django.conf import settings

# ─────────────────────────────────────────────────────────────────────────────
# OpenAI client (via env var; one client per worker thread)
# ─────────────────────────────────────────────────────────────────────────────
try:
    from openai import OpenAI
except Exception:
    OpenAI = None

_thread_ctx = threading.local()

def _get_thread_client() -> OpenAI:
    """Create/reuse one OpenAI client per worker thread."""
    if getattr(_thread_ctx, "client", None) is None:
        if not getattr(settings, "OPENAI_API_KEY", None):
            raise RuntimeError(
                "OPENAI_API_KEY is not configured. "
                "Set it in the project's .env file."
            )

        if OpenAI is None:
            raise RuntimeError(
                "openai package not installed. Run: pip install openai pydantic"
            )

        _thread_ctx.client = OpenAI(api_key=settings.OPENAI_API_KEY)

    return _thread_ctx.client

# ─────────────────────────────────────────────────────────────────────────────
# Typed schemas for triple extraction + NL output
# ─────────────────────────────────────────────────────────────────────────────
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

# ─────────────────────────────────────────────────────────────────────────────
# LLM helpers
# ─────────────────────────────────────────────────────────────────────────────
def extract_triples_no_reason(text: str) -> List[TripleWithEntityTypes]:
    """Extract triples (+ entity/predicate types), NO reason."""
    client = _get_thread_client()
    sys_prompt = (
        "Extract knowledge triples and their types for every relationship in the given sentence. "
        "Each triple must include: subject (name + types), predicate (string + types), object (name + types). "
        "Do not omit any triple. Return strict JSON."
    )
    rsp = client.beta.chat.completions.parse(
        model="gpt-4.1-mini",
        temperature=0,
        messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "user",   "content": text},
        ],
        response_format=KnowledgeTriplesWithEntitiesResponse,
    )
    return rsp.choices[0].message.parsed.triples

def combine_triples_to_sentence(triples: List[dict]) -> Optional[str]:
    """ONE sentence that conveys ALL & ONLY the facts in the triples."""
    if not triples:
        return None
    lines = []
    for idx, t in enumerate(triples, start=1):
        s = t["subject"]["name"] if isinstance(t["subject"], dict) else str(t["subject"])
        p = t["predicate"]
        o = t["object"]["name"]  if isinstance(t["object"],  dict) else str(t["object"])
        lines.append(f"{idx}) subject: {s}\n   predicate: {p}\n   object: {o}")

    client = _get_thread_client()
    sys_prompt = (
        "You convert one or more knowledge-graph triples into ONE clear English sentence. "
        "Include all and only the information in the triples; no external facts. "
        "Join naturally when multiple triples exist. "
        'Return JSON only: {"sentence": "..."}'
    )
    user_prompt = "Triples:\n" + "\n".join(lines) + "\n\nReturn the JSON object."

    comp = client.beta.chat.completions.parse(
        model="gpt-4.1-mini",
        temperature=0,
        messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        response_format=NLResponse,
    )
    return comp.choices[0].message.parsed.sentence.strip()

# ─────────────────────────────────────────────────────────────────────────────
# Utilities
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

# IMPORTANT: your Paragraph model stores the text in `input_text`.
def get_paragraph_text_safe(paragraph) -> Optional[str]:
    """Resolve the paragraph's main text; tailored to your model."""
    # Prefer the exact field you have:
    if hasattr(paragraph, "input_text") and isinstance(paragraph.input_text, str) and paragraph.input_text.strip():
        return paragraph.input_text
    # Fallbacks (just in case):
    for attr in ("text", "raw_text", "content", "contents", "body", "paragraph_text", "original_text"):
        if hasattr(paragraph, attr):
            val = getattr(paragraph, attr)
            if isinstance(val, str) and val.strip():
                return val
    return None

def get_proposition_text_safe(prop) -> Optional[str]:
    """Your Proposition.text field."""
    if hasattr(prop, "text") and isinstance(prop.text, str) and prop.text.strip():
        return prop.text
    # Fallbacks:
    for attr in ("proposition_text", "proposition", "content", "raw_text", "sentence"):
        if hasattr(prop, attr):
            val = getattr(prop, attr)
            if isinstance(val, str) and val.strip():
                return val
    return None

# ─────────────────────────────────────────────────────────────────────────────
# Core worker: process ONE paragraph
# ─────────────────────────────────────────────────────────────────────────────
def process_one_paragraph(
    para_id: int,
    para_text: str,
    items: List[Tuple[int, str, Optional[str]]],  # (prop_id, coref_text, prop_text)
    prop_workers: int
) -> Tuple[int, Optional[float], Optional[float], Optional[float]]:
    """
    Returns:
      (paragraph_id,
       recombined_triple_similarity,
       combined_proposition_similarity,
       combined_coref_similarity)
    """

    def _one_coref_to_sentence(_pid: int, _coref: str) -> Tuple[int, Optional[str]]:
        try:
            triples_obj = extract_triples_no_reason(_coref)
        except Exception:
            triples_obj = []
        triples_norm = [
            {"subject": {"name": t.subject.name}, "predicate": t.predicate, "object": {"name": t.object.name}}
            for t in triples_obj
        ]
        try:
            sent = combine_triples_to_sentence(triples_norm) if triples_norm else None
        except Exception:
            sent = None
        return (_pid, sent)

    # 1) Recompose triples per coref → sentence; keep original proposition order
    recomposed: List[Tuple[int, Optional[str]]] = []
    if prop_workers and prop_workers > 1 and len(items) > 1:
        with ThreadPoolExecutor(max_workers=prop_workers) as ex:
            futs = [ex.submit(_one_coref_to_sentence, pid, coref) for (pid, coref, _ptxt) in items]
            for f in as_completed(futs):
                try:
                    recomposed.append(f.result())
                except Exception:
                    pass
        recomposed.sort(key=lambda t: t[0])
    else:
        for pid, coref, _ptxt in items:
            recomposed.append(_one_coref_to_sentence(pid, coref))

    # 2) Build aggregates
    recomposed_sents = [s for (_pid, s) in recomposed if s and s.strip()]
    recon_paragraph = " ".join(recomposed_sents) if recomposed_sents else None

    prop_texts = [ptxt.strip() for (_pid, _coref, ptxt) in items if isinstance(ptxt, str) and ptxt.strip()]
    props_paragraph = " ".join(prop_texts) if prop_texts else None

    coref_texts = [coref.strip() for (_pid, coref, _ptxt) in items if isinstance(coref, str) and coref.strip()]
    coref_paragraph = " ".join(coref_texts) if coref_texts else None

    # 3) Similarities vs original paragraph
    def _sim(a: Optional[str]) -> Optional[float]:
        if not a:
            return None
        try:
            v = compute_similarity(para_text, a)
            return float(v) if isinstance(v, (int, float)) else None
        except Exception:
            return None

    return (
        para_id,
        _sim(recon_paragraph),
        _sim(props_paragraph),
        _sim(coref_paragraph),
    )

# ─────────────────────────────────────────────────────────────────────────────
# Management Command
# ─────────────────────────────────────────────────────────────────────────────
class Command(BaseCommand):
    help = (
        "Paragraph-level back-validation via recomposed triples, plus proposition/coref aggregates:\n"
        "  • For each paragraph, extract triples per coreference sentence and recombine to one sentence\n"
        "  • Concatenate those sentences to a paragraph (recombined triples)\n"
        "  • Concatenate all proposition texts and all coreference sentences\n"
        "  • Compute cosine similarities vs the original paragraph (Paragraph.input_text)\n"
        "Writes CSV to results/paragrph_level_results/combined_paragraph_from_triples.csv\n"
        "Columns: paragraph_id, recombined_triple_similarity, combined_proposition_similarity, combined_coref_similarity\n"
        "Options: --para-workers --prop-workers --limit --start-id"
    )

    def add_arguments(self, parser):
        parser.add_argument("--para-workers", type=int, default=4, help="Threads over paragraphs.")
        parser.add_argument("--prop-workers", type=int, default=4, help="Threads per paragraph over propositions.")
        parser.add_argument("--limit", type=int, default=None, help="Optional cap on number of paragraphs.")
        parser.add_argument("--start-id", type=int, default=None, help="Process paragraphs with id >= start-id.")

    def handle(self, *args, **options):
        # Build (paragraph_id -> (paragraph_text, [(prop_id, coref_text, prop_text), ...]))
        qs = (Proposition.objects
              .select_related("paragraph")
              .exclude(coreferenced_text__isnull=True)
              .exclude(coreferenced_text__exact="")
              .order_by("paragraph_id", "id"))

        start_id = options.get("start_id")
        if start_id:
            qs = qs.filter(paragraph_id__gte=start_id)

        para_map: Dict[int, Tuple[str, List[Tuple[int, str, Optional[str]]]]] = {}
        for prop in qs:
            p = prop.paragraph
            para_text = get_paragraph_text_safe(p)  # <-- now reads Paragraph.input_text
            if not para_text:
                # Skip if we can't resolve paragraph text
                continue
            coref = (prop.coreferenced_text or "").strip()
            if not coref:
                continue
            prop_text = get_proposition_text_safe(prop)

            entry = para_map.get(p.id)
            if entry is None:
                para_map[p.id] = (para_text, [(prop.id, coref, prop_text)])
            else:
                entry[1].append((prop.id, coref, prop_text))

        # Sort proposition lists (safety; queryset already ordered)
        for pid in list(para_map.keys()):
            txt, lst = para_map[pid]
            para_map[pid] = (txt, sorted(lst, key=lambda t: t[0]))

        # Optional LIMIT on number of paragraphs
        para_ids = sorted(para_map.keys())
        if options.get("limit"):
            para_ids = para_ids[: int(options["limit"])]

        total = len(para_ids)
        if total == 0:
            self.stdout.write(self.style.WARNING("No paragraphs with usable coreference sentences found."))
            return

        # Output path (folder name as requested: 'paragrph_level_results')
        cmd_path     = Path(__file__).resolve()
        backend_dir  = cmd_path.parents[3]       # .../backend
        project_root = backend_dir.parent        # .../the-everything-engine
        out_dir      = project_root / "results" / "00_fully`-organized_results" / "04_overall_system_results"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_csv      = out_dir / "combined_paragraph_from_triples.csv"

        # Prepare CSV (overwrite each run)
        with out_csv.open("w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([
                "paragraph_id",
                "recombined_triple_similarity",
                "combined_proposition_similarity",
                "combined_coref_similarity"
            ])

        para_workers = max(1, int(options.get("para_workers") or 1))
        prop_workers = max(1, int(options.get("prop_workers") or 1))

        # Writer thread
        Q: "queue.Queue[Optional[Tuple[int, Optional[float], Optional[float], Optional[float]]]]" = queue.Queue(maxsize=2000)
        STOP = object()

        def writer():
            with out_csv.open("a", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                while True:
                    item = Q.get()
                    if item is STOP:
                        break
                    para_id, sim_recon, sim_props, sim_corefs = item  # type: ignore
                    w.writerow([
                        str(para_id),
                        f"{sim_recon:.6f}"  if isinstance(sim_recon,  float) else "",
                        f"{sim_props:.6f}"  if isinstance(sim_props,  float) else "",
                        f"{sim_corefs:.6f}" if isinstance(sim_corefs, float) else "",
                    ])
                    Q.task_done()

        wt = threading.Thread(target=writer, daemon=True)
        wt.start()

        # Parallel over paragraphs
        start_t = time.perf_counter()
        done = 0

        def _submit_one(pid: int):
            ptxt, lst = para_map[pid]
            return process_one_paragraph(pid, ptxt, lst, prop_workers)

        self.stdout.write("\nStarting paragraph-level recombination & aggregates…\n")

        with ThreadPoolExecutor(max_workers=para_workers) as pool:
            futs = [pool.submit(_submit_one, pid) for pid in para_ids]
            for f in as_completed(futs):
                try:
                    row = f.result()
                except Exception:
                    row = None
                if row:
                    Q.put(row)
                done += 1
                progress_bar(done, total, start_t)

        # Drain & stop writer
        Q.join()
        Q.put(STOP)
        wt.join()

        self.stdout.write(self.style.SUCCESS("\nExport complete."))
        self.stdout.write(f"Paragraphs processed: {done}/{total}")
        self.stdout.write(f"Output: {out_csv}")
        self.stdout.write(f"para-workers={para_workers}  prop-workers={prop_workers}")