"""
views.py – REST endpoints for paragraph-level knowledge-graph generation
========================================================================

Two APIView subclasses expose the pipeline:

1. `ProcessParagraphView`          – serial reference implementation
2. `ProcessParagraphParallelView`  – thread-pool variant (configurable, production path)

Both accept
-----------

    POST /api/…    body = { "paragraph": "<text>" }

Top-level response schema
-------------------------

{
  "input_paragraph": str,                 # raw user paragraph
  "results": [                            # per-proposition bundle (source order)
    {
      "proposition_sentence": str,        # original proposition chunk
      "coreferenced_sentence": str,       # same sentence after coref resolution
      "quadruples": [                     # extracted + enriched quads for this sentence
        {
          "quadruple": {                  # raw KG quadruple (w/ entity + predicate types)
            "subject":  { "name": str, "types": [str, ...] },
            "predicate": str,
            "predicate_types": [str, ...],
            "object":   { "name": str, "types": [str, ...] },
            "reason":   str
          },
          "natural_language_sentence": str | null,  # LLM "triple → sentence"
          "cosine_similarity": float | null,        # NL sentence vs. coref sentence (>=0)
          "question": str | null,                   # LLM "triple → question"
          "answer_to_question": str | null,         # LLM "question → answer sentence"
          "answer_similarity": float | null         # answer vs. coref sentence (>=0)
        },
        ...
      ]
    },
    ...
  ],

  # paragraph-level aggregates (simple joins of the per-sentence strings)
  "propositions_paragraph":     str,
  "coreferenced_paragraph":     str,
  "natural_language_paragraph": str,

  # cosine similarities of the originals vs. the full paragraph
  "similarities": {
    "propositions_similarity":      float | null,
    "coreferenced_similarity":      float | null,
    "natural_language_similarity":  float | null
  },

  # KG expansion (inferred edges). Same enrichment keys as above.
  "new_inferred_quadruples": [
    {
      "quadruple": { ... },                 # same structure as above
      "natural_language_sentence": str | null,
      "cosine_similarity": float | null,    # here: NL vs. *paragraph* (no coref sentence)
      "question": str | null,
      "answer_to_question": str | null,
      "answer_similarity": float | null     # answer vs. *paragraph*
    },
    ...
  ],

  # entities worth adding to your ontology vocab (majority vote, etc.)
  "ontological_entities": [str, ...],

  # runtime diagnostics (seconds)
  "timings": {
    "proposition_chunking_s":                float,
    "coreference_resolution_s":              float,
    "quadruple_extraction_and_validation_s": float,
    "aggregates_and_similarities_s":         float,
    "inferred_generation_s":                 float,   # LLM inference only
    "inferred_enrichment_s":                 float,   # NL/Q/Ans enrichment of inferred
    "ontological_entities_s":                float,
    "total_pipeline_s":                      float,
    "...":                                   float    # any additional ad-hoc timers
  }
}

Notes & conventions
-------------------
• All cosine similarities are clamped to ≥ 0.  
• `null` means the value could not be produced (e.g., model error).  
• The staging layer expects these exact keys (see save_paragraph_to_db_staging.py).  
• Parallel view also logs fine-grained timing to stdout for profiling.  
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError as FuturesTimeout
from typing import List, Tuple

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

# ───────────────────────────────────────────────────────────── #
#  Pipeline utilities
# ───────────────────────────────────────────────────────────── #
from .pipeline_utilities.propositions import split_paragraph_into_propositions
from .pipeline_utilities.coreferences import resolve_coreferences
from .pipeline_utilities.triple_extraction import (
    extract_quadruples_with_entity_types,
    quadruple_to_sentence,
    two_phase_infer_new_quadruples,
)
from .pipeline_utilities.triple_question import quadruple_to_question, question_to_sentence
from .pipeline_utilities.sentence_similarity import compute_similarity, compute_similarities_batch
from .pipeline_utilities.universal_entities import identify_ontological_entities

# --------------------------------------------------------------------------- #
#  Console helper
# --------------------------------------------------------------------------- #
def _log(step: int, msg: str) -> None:
    """Uniform, emoji-friendly progress logger."""
    print(f"💡 [{step}] {msg}")


# --------------------------------------------------------------------------- #
#  Aggregates helper (unchanged)
# --------------------------------------------------------------------------- #
def _aggregate_and_score_fast(
    paragraph: str,
    propositions: List[str],
    corefs: List[str],
    nl_sentences: List[str],
) -> Tuple[dict, dict]:
    """Compute paragraph-level aggregates & cosine similarities in one go."""
    props_para = " ".join(propositions)
    coref_para = " ".join(corefs)
    nl_para    = " ".join(nl_sentences)

    texts = {
        "propositions":     props_para,
        "coreferenced":     coref_para,
        "natural_language": nl_para,
    }
    sims = compute_similarities_batch(paragraph, texts)

    aggs = {
        "propositions_paragraph":     props_para,
        "coreferenced_paragraph":     coref_para,
        "natural_language_paragraph": nl_para,
    }
    return aggs, {
        "propositions_similarity":      sims["propositions"],
        "coreferenced_similarity":      sims["coreferenced"],
        "natural_language_similarity":  sims["natural_language"],
    }


# --------------------------------------------------------------------------- #
#  SERIAL IMPLEMENTATION
# --------------------------------------------------------------------------- #
class ProcessParagraphView(APIView):
    """
    POST endpoint that executes the KG pipeline synchronously.

    The serial version is easier to debug and consumes no thread-pool
    overhead, but will be slower for long paragraphs.
    """

    def post(self, request, *args, **kwargs):
        """Run the entire pipeline in a single thread and return JSON."""
        paragraph: str = request.data.get("paragraph", "").strip()
        if not paragraph:
            return Response(
                {"error": "Paragraph is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        t0 = time.time()
        _log(0, "Serial pipeline started")

        # Response scaffold
        results: dict = {
            "input_paragraph": paragraph,
            "results": [],
            "propositions_paragraph": "",
            "coreferenced_paragraph": "",
            "natural_language_paragraph": "",
            "similarities": {},
            "new_inferred_quadruples": [],
            "ontological_entities": [],
        }

        # ------------------------------------------------------------------ #
        # 1. Pre-processing – split & coref
        # ------------------------------------------------------------------ #
        _log(1, "Splitting paragraph into propositions")
        propositions: List[str] = split_paragraph_into_propositions(paragraph)

        _log(2, "Resolving coreferences")
        coref_sentences: List[str] = resolve_coreferences(propositions)

        # ------------------------------------------------------------------ #
        # 2. Quadruple extraction
        # ------------------------------------------------------------------ #
        _log(3, "Extracting quadruples")
        all_quads: list = []
        for prop, coref in zip(propositions, coref_sentences):
            quads = extract_quadruples_with_entity_types(coref)
            all_quads.extend(quads)

            results["results"].append(
                {
                    "proposition_sentence": prop,
                    "coreferenced_sentence": coref,
                    "quadruples": [
                        {
                            "quadruple": q,
                            "natural_language_sentence": quadruple_to_sentence(q),
                            "question": quadruple_to_question(q),
                        }
                        for q in quads
                    ],
                }
            )

        # ------------------------------------------------------------------ #
        # 3. Aggregates & similarities
        # ------------------------------------------------------------------ #
        _log(4, "Building paragraph-level aggregates and similarities")
        aggs, sims = _aggregate_and_score(
            paragraph, propositions, coref_sentences, all_quads
        )
        results.update(aggs)
        results["similarities"] = sims

        # ------------------------------------------------------------------ #
        # 4. Iterative KG expansion / inference
        # ------------------------------------------------------------------ #
        _log(5, "Running iterative inference for new quadruples")
        inferred = iterative_infer_new_quadruples(" ".join(coref_sentences), all_quads)
        results["new_inferred_quadruples"] = [
            {
                "quadruple": q,
                "natural_language_sentence": quadruple_to_sentence(q),
                "question": quadruple_to_question(q),
            }
            for q in inferred
        ]

        # ------------------------------------------------------------------ #
        # 5. Ontology-worthy entity detection
        # ------------------------------------------------------------------ #
        _log(6, "Detecting ontology-worthy entities to keep")
        keeps = identify_ontological_entities(paragraph, all_quads)
        results["ontological_entities"] = keeps
        print(f"🏷️  Ontological entities → {keeps}")

        # ------------------------------------------------------------------ #
        # Done
        # ------------------------------------------------------------------ #
        _log(7, f"Serial pipeline finished in {time.time() - t0:.2f}s")
        return Response(results, status=status.HTTP_200_OK)


# --------------------------------------------------------------------------- #
#  PARALLEL IMPLEMENTATION
# --------------------------------------------------------------------------- #
MAX_WORKERS = 20         # tune for your CPU / rate-limit budget
PARALLEL_TIMEOUT = 180   # seconds for the whole extraction batch


class ProcessParagraphParallelView(APIView):
    """
    POST endpoint that parallelises quadruple extraction across sentences.

    The heavy lifting (LLM calls) happens inside worker threads:
      • extract_quadruples_with_entity_types
      • quadruple_to_sentence
      • quadruple_to_question
      • question_to_sentence
      • compute_similarity for NL & Q->A vs. the coref sentence

    Result JSON matches the expectations of the staging saver:
      - per-quad keys include: natural_language_sentence, cosine_similarity,
        question, answer_to_question, answer_similarity
    """

    # -------------------------- Worker helper -------------------------- #
    @staticmethod
    def _worker(idx: int, prop: str, coref: str) -> Tuple[int, str, str, list, list]:
        """
        Run extraction AND per-quad NL/Q/answer + similarity in a worker thread.

        Returns
        -------
        idx, prop, coref, raw_quads, enriched_quads
            enriched_quads: list of dicts with keys:
                - "quadruple": original quad dict
                - "natural_language_sentence"
                - "cosine_similarity"        (NL vs. coref)
                - "question"
                - "answer_to_question"
                - "answer_similarity"        (answer vs. coref)
        """
        quads = extract_quadruples_with_entity_types(coref)

        enriched = []
        for q in quads:
            nl  = quadruple_to_sentence(q)
            qst = quadruple_to_question(q)
            ans = question_to_sentence(qst) if qst else None

            # cosine sims (guard for None)
            nl_sim  = compute_similarity(coref, nl)  if nl  else None
            qa_sim  = compute_similarity(coref, ans) if ans else None

            enriched.append(
                {
                    "quadruple": q,
                    "natural_language_sentence": nl,
                    "cosine_similarity": nl_sim,
                    "question": qst,
                    "answer_to_question": ans,
                    "answer_similarity": qa_sim,
                }
            )

        return idx, prop, coref, quads, enriched

    # ----------------------------- Handler ----------------------------- #
    def post(self, request, *args, **kwargs):
        """Run the pipeline using a thread pool and return JSON."""
        paragraph: str = request.data.get("paragraph", "").strip()
        if not paragraph:
            return Response(
                {"error": "Paragraph is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        t0 = time.perf_counter()
        _log(0, "Parallel pipeline started")
        timings: Dict[str, float] = {}

        results: dict = {
            "input_paragraph": paragraph,
            "results": [],
            "propositions_paragraph": "",
            "coreferenced_paragraph": "",
            "natural_language_paragraph": "",
            "similarities": {},
            "new_inferred_quadruples": [],
            "ontological_entities": [],
            "timings": timings,
        }

        # ------------------------------------------------------------------ #
        # 1. Pre-processing – split & coref
        # ------------------------------------------------------------------ #
        t_prop = time.perf_counter()
        propositions = split_paragraph_into_propositions(paragraph)
        timings["proposition_chunking_s"] = time.perf_counter() - t_prop
        _log(1, f"Proposition chunking took {timings['proposition_chunking_s']:.2f}s "
                f"({len(propositions)} sentences)")

        t_coref = time.perf_counter()
        coref_sentences = resolve_coreferences(propositions)
        timings["coreference_resolution_s"] = time.perf_counter() - t_coref
        _log(2, f"Coreference resolution took {timings['coreference_resolution_s']:.2f}s")

        # ------------------------------------------------------------------ #
        # 2. Parallel quadruple extraction (+ NL/Q/Ans + sims)
        # ------------------------------------------------------------------ #
        _log(3, f"Dispatching {len(propositions)} sentences to worker pool")
        t_quad = time.perf_counter()

        sentence_results = [None] * len(propositions)
        all_quads: list = []
        nl_sentences_total: list[str] = []

        with ThreadPoolExecutor(
            max_workers=min(MAX_WORKERS, len(propositions)) or 1
        ) as pool:
            futures = [
                pool.submit(self._worker, i, prop, coref)
                for i, (prop, coref) in enumerate(zip(propositions, coref_sentences))
            ]

            try:
                for f in as_completed(futures, timeout=PARALLEL_TIMEOUT):
                    idx, prop, coref, quads, enriched = f.result()
                    all_quads.extend(quads)
                    nl_sentences_total.extend(
                        e["natural_language_sentence"]
                        for e in enriched
                        if e["natural_language_sentence"]
                    )
                    sentence_results[idx] = {
                        "proposition_sentence": prop,
                        "coreferenced_sentence": coref,
                        "quadruples": enriched,
                    }
            except FuturesTimeout as exc:
                unfinished = sum(1 for fu in futures if not fu.done())
                _log(
                    99,
                    f"Timeout after {PARALLEL_TIMEOUT}s – "
                    f"{unfinished} futures unfinished; partial data returned",
                )
                for fu in futures:
                    if not fu.done():
                        fu.cancel()

        results["results"] = sentence_results
        timings["quadruple_extraction_and_validation_s"] = time.perf_counter() - t_quad
        _log(4, f"Quadruple extraction + validation took "
                f"{timings['quadruple_extraction_and_validation_s']:.2f}s "
                f"({len(all_quads)} quads)")

        # ------------------------------------------------------------------ #
        # 3. Aggregates & similarities
        # ------------------------------------------------------------------ #
        t_aggs = time.perf_counter()
        _log(5, "Building paragraph-level aggregates and similarities")
        aggs, sims = _aggregate_and_score_fast(
            paragraph, propositions, coref_sentences, nl_sentences_total
        )
        results.update(aggs)
        results["similarities"] = sims
        timings["aggregates_and_similarities_s"] = time.perf_counter() - t_aggs
        _log(5, f"Aggregates & similarities took {timings['aggregates_and_similarities_s']:.2f}s")

        # ------------------------------------------------------------------ #
        # 4. Iterative KG expansion / inference  (two-phase, parallel)
        # ------------------------------------------------------------------ #
        t_inf = time.perf_counter()
        _log(6, "Running two-phase inference (global + pairwise)")
        inferred = two_phase_infer_new_quadruples(
            paragraph,
            all_quads,
            max_workers=min(MAX_WORKERS, 16),
        )
        timings["inferred_generation_s"] = time.perf_counter() - t_inf
        _log(7, f"Inferred quadruples (LLM) took {timings['inferred_generation_s']:.2f}s "
                f"({len(inferred)} new quads)")

        # 4b. Enrich inferred quads with NL/Q/Ans + sims (parallel)
        def _enrich_inferred(q: dict) -> dict:
            nl  = quadruple_to_sentence(q)
            qst = quadruple_to_question(q)
            ans = question_to_sentence(qst) if qst else None

            # Use paragraph as reference (no coref sentence for inferred ones)
            nl_sim = compute_similarity(paragraph, nl)  if nl  else None
            qa_sim = compute_similarity(paragraph, ans) if ans else None

            return {
                "quadruple": q,
                "natural_language_sentence": nl,
                "cosine_similarity": nl_sim,
                "question": qst,
                "answer_to_question": ans,
                "answer_similarity": qa_sim,
            }

        t_enrich = time.perf_counter()
        _log(7, "Enriching inferred quads with NL/Q/Ans (parallel)")
        if inferred:
            with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(inferred)) or 1) as pool:
                enriched_inferred = list(pool.map(_enrich_inferred, inferred))
        else:
            enriched_inferred = []
        timings["inferred_enrichment_s"] = time.perf_counter() - t_enrich
        print(f"⏱ Inferred NL/Q enrichment produced {len(enriched_inferred)} items "
              f"in {timings['inferred_enrichment_s']:.2f}s")

        results["new_inferred_quadruples"] = enriched_inferred

        # ------------------------------------------------------------------ #
        # 5. Ontology-worthy entity detection
        # ------------------------------------------------------------------ #
        t_onto = time.perf_counter()
        _log(8, "Detecting ontology-worthy entities to keep")
        keeps = identify_ontological_entities(paragraph, all_quads)
        results["ontological_entities"] = keeps
        timings["ontological_entities_s"] = time.perf_counter() - t_onto
        _log(9, f"Ontology filtering took {timings['ontological_entities_s']:.2f}s "
                f"({len(keeps)} entities)")

        # ------------------------------------------------------------------ #
        # Done
        # ------------------------------------------------------------------ #
        total = time.perf_counter() - t0
        timings["total_pipeline_s"] = total
        _log(10, f"Parallel pipeline finished in {total:.2f}s")

        return Response(results, status=status.HTTP_200_OK)