"""
backend/knowledge_graph_generator/database_utilities/save_paragraph_to_db_staging.py
═══════════════════════════════════════════════════════════════════════════════
Purpose
───────
Persist *everything* produced by the paragraph-level KG pipeline into the staging
DB layer, while keeping canonical-mapping / Neo4j promotion for a later async
job. This version hardens the function against malformed / partial payloads that
were causing `AttributeError: 'NoneType' object has no attribute 'get'` when a
`None` sneaked into `kg_json["results"]`.

Key changes in this patch (2025‑07‑27)
──────────────────────────────────────
1. **Schema validation + graceful degradation**
   • Early sanity checks on the expected top-level keys (`results`,
     `new_inferred_quadruples`, etc.).
   • Any `None` or non-dict entries inside `results` are skipped with a logged
     warning instead of blowing up.

2. **Safer helpers**
   • `_lc_list()` now tolerates `None` / non-iterables, always returning a list
     of lower‑cased strings.
   • New `_is_mapping()` and `_as_list()` helpers for explicit intent.

3. **Order-safe staging**
   • We no longer rely on `zip(kg_json["results"], paragraph.propositions.all())`
     (which could silently misalign). Instead, we keep an explicit list of
     `(prop_json, prop_obj)` pairs as we create them.

4. **Better logging / debugging**
   • Uses Python's `logging` to surface payload issues with enough context (idx,
     offending value) without crashing the transaction.

5. **Type hints + docstrings**
   • Clearer function signatures and in-line docs for maintainability.

6. **Minor robustness tweaks**
   • Defensive `.get()` chains and defaults throughout.
   • Ontological entity set creation handles `None`.

Usage
──────
Drop-in replacement for the previous module. No call‑site changes required.

"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Tuple
import logging

from django.db import transaction

from knowledge_graph_generator.models import (
    Paragraph,
    Proposition,
    Quadruple,
    InferredQuadruple,
    StagingParagraph,
    StagedQuadruple,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _lc_list(xs: Iterable[str] | None) -> List[str]:
    """Return a new list with every element in **xs** lower-cased.

    Accepts ``None`` or non-iterables and falls back to an empty list.
    """
    if not xs:
        return []
    try:
        return [str(x).lower() for x in xs]
    except TypeError:
        # xs was not iterable
        return []


def _is_mapping(obj: Any) -> bool:
    """Cheap ``Mapping`` check that ignores special Django objects, etc."""
    return isinstance(obj, Mapping)


def _as_list(value: Any) -> List[Any]:
    """Return ``value`` if it's a list, otherwise an empty list.

    ``None`` → []
    Non-lists (e.g. dicts/tuples/strings) are *not* coerced to lists on purpose
    to avoid accidental iteration over chars.
    """
    return value if isinstance(value, list) else []


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
@transaction.atomic
def save_paragraph_to_db_staging(
    kg_json: Dict[str, Any],
) -> Tuple[Paragraph, List[Quadruple], List[InferredQuadruple]]:
    """
    Persist the entire KG output of a single paragraph into the staging DB.

    Parameters
    ----------
    kg_json : dict
        Exact JSON payload returned by the `/api/process-paragraph-parallel/`
        endpoint. Its schema is documented in the service layer. This function
        is now defensive against partial/malformed payloads.

    Returns
    -------
    paragraph : Paragraph
        The freshly-created `Paragraph` row (clean layer).
    extracted_quads : list[Quadruple]
        List of `Quadruple` ORM instances (original casing kept).
    inferred_quads : list[InferredQuadruple]
        List of `InferredQuadruple` ORM instances (original casing kept).

    Notes
    -----
    * All text persisted to **StagedQuadruple** is lower-cased so that every
      downstream component (vector search, canonical mapping, Neo4j merge-keys)
      operates on a normalised representation.
    * A *namespaced* ID ("e-" / "i-") is generated for each staged row to
      guarantee global uniqueness across **all** quads, regardless of their
      source table.
    * If the payload contains unexpected ``None`` or incorrectly typed
      structures, those specific items are skipped and a warning is logged,
      but the transaction still succeeds for the rest of the data.
    """

    # ────────────────────────────────────────────────────────────────
    # 0. Sanity checks & safe extraction
    # ────────────────────────────────────────────────────────────────
    if not _is_mapping(kg_json):
        logger.error("save_paragraph_to_db_staging called with non-dict payload: %r", kg_json)
        raise TypeError("kg_json must be a dict-like mapping")

    results: List[Any] = _as_list(kg_json.get("results"))
    inferred_raw: List[Any] = _as_list(kg_json.get("new_inferred_quadruples"))

    # ────────────────────────────────────────────────────────────────
    # 1. Paragraph  – clean layer
    # ────────────────────────────────────────────────────────────────
    similarities = kg_json.get("similarities") or {}
    paragraph = Paragraph.objects.create(
        input_text                  = kg_json.get("input_paragraph", ""),
        propositions_paragraph      = kg_json.get("propositions_paragraph", ""),
        coreferenced_paragraph      = kg_json.get("coreferenced_paragraph", ""),
        natural_language_paragraph  = kg_json.get("natural_language_paragraph", ""),
        propositions_similarity     = similarities.get("propositions_similarity"),
        coreferenced_similarity     = similarities.get("coreferenced_similarity"),
        natural_language_similarity = similarities.get("natural_language_similarity"),
    )

    # ────────────────────────────────────────────────────────────────
    # 2. StagingParagraph  – audit wrapper
    # ────────────────────────────────────────────────────────────────
    staging_para = StagingParagraph.objects.create(
        paragraph=paragraph,
        source   = kg_json.get("source", "pubmedqa-context"),
    )

    # Containers returned to the caller ---------------------------------------
    extracted_quads: List[Quadruple]         = []
    inferred_quads:  List[InferredQuadruple] = []

    # We also keep a pairing of (prop_json, prop_obj) to avoid fragile zips.
    prop_pairs: List[Tuple[Dict[str, Any], Proposition]] = []

    # ────────────────────────────────────────────────────────────────
    # 3. Propositions ► Quadruples (pipeline tables – keep casing)
    # ────────────────────────────────────────────────────────────────
    for idx, prop_json in enumerate(results):
        if not _is_mapping(prop_json):
            logger.warning("Skipping non-mapping result at index %s: %r", idx, prop_json)
            continue

        prop = Proposition.objects.create(
            paragraph         = paragraph,
            text              = prop_json.get("proposition_sentence", ""),
            coreferenced_text = prop_json.get("coreferenced_sentence", ""),
        )
        prop_pairs.append((prop_json, prop))

        for qd_idx, qd in enumerate(_as_list(prop_json.get("quadruples"))):
            if not _is_mapping(qd):
                logger.warning(
                    "Skipping non-mapping quadruple at result[%s].quadruples[%s]: %r",
                    idx, qd_idx, qd,
                )
                continue

            q = qd.get("quadruple")
            if not _is_mapping(q):
                logger.warning(
                    "Missing/invalid 'quadruple' key at result[%s].quadruples[%s]: %r",
                    idx, qd_idx, qd,
                )
                continue

            try:
                quad = Quadruple.objects.create(
                    paragraph   = paragraph,
                    proposition = prop,
                    subject_name    = q["subject"]["name"],
                    subject_types   = q["subject"].get("types", []),
                    predicate       = q["predicate"],
                    predicate_types = q.get("predicate_types", []),
                    object_name     = q["object"]["name"],
                    object_types    = q["object"].get("types", []),
                    reason                    = q["reason"],
                    natural_language_sentence = qd.get("natural_language_sentence", ""),
                    cosine_similarity         = qd.get("cosine_similarity"),
                    question                  = qd.get("question", ""),
                    answer_to_question        = qd.get("answer_to_question", ""),
                    answer_similarity         = qd.get("answer_similarity"),
                )
            except (KeyError, TypeError) as exc:
                logger.warning(
                    "Failed to create Quadruple for result[%s].quadruples[%s]: %s | payload=%r",
                    idx, qd_idx, exc, qd,
                )
                continue

            extracted_quads.append(quad)

    # ────────────────────────────────────────────────────────────────
    # 4. Inferred quadruples (pipeline table – keep casing)
    # ────────────────────────────────────────────────────────────────
    for i_idx, inf in enumerate(inferred_raw):
        if not _is_mapping(inf):
            logger.warning("Skipping non-mapping inferred_quadruple at index %s: %r", i_idx, inf)
            continue

        q = inf.get("quadruple")
        if not _is_mapping(q):
            logger.warning("Missing/invalid 'quadruple' in inferred[%s]: %r", i_idx, inf)
            continue

        try:
            iq = InferredQuadruple.objects.create(
                paragraph   = paragraph,
                subject_name    = q["subject"]["name"],
                subject_types   = q["subject"].get("types", []),
                predicate       = q["predicate"],
                predicate_types = q.get("predicate_types", []),
                object_name     = q["object"]["name"],
                object_types    = q["object"].get("types", []),
                reason                    = q["reason"],
                natural_language_sentence = inf.get("natural_language_sentence", ""),
                question                  = inf.get("question", ""),
            )
        except (KeyError, TypeError) as exc:
            logger.warning(
                "Failed to create InferredQuadruple for inferred[%s]: %s | payload=%r",
                i_idx, exc, inf,
            )
            continue

        inferred_quads.append(iq)

    # ────────────────────────────────────────────────────────────────
    # 5. Bulk insert ► StagedQuadruple  (lower-case + namespaced IDs)
    # ────────────────────────────────────────────────────────────────
    ontology_set = {str(e).lower() for e in (kg_json.get("ontological_entities") or [])}
    staged_rows: List[StagedQuadruple] = []

    def _stage(
        quad_obj: Quadruple | InferredQuadruple,
        prop_sentence: str,
        coref_sentence: str,
        nl_sentence: str,
        inferred: bool,
        question: str,
    ) -> None:
        """Create one `StagedQuadruple` instance (not yet saved).

        Parameters are expected to be **already** lower/normalised where needed.
        The function itself lower-cases before assigning.
        """
        subj_lc = str(quad_obj.subject_name).lower()
        obj_lc  = str(quad_obj.object_name).lower()
        pred_lc = str(quad_obj.predicate).lower()

        # Namespaced ID ensures global uniqueness
        sq_id = f"{'i' if inferred else 'e'}-{quad_obj.id}"

        staged_rows.append(
            StagedQuadruple(
                quadruple_id       = sq_id,
                staging_paragraph  = staging_para,

                # —— S-P-O (lower-case) ————————————————
                subject_name           = subj_lc,
                subject_types          = _lc_list(getattr(quad_obj, "subject_types", [])),
                subject_is_ontological = subj_lc in ontology_set,

                predicate              = pred_lc,
                predicate_types        = _lc_list(getattr(quad_obj, "predicate_types", [])),

                object_name            = obj_lc,
                object_types           = _lc_list(getattr(quad_obj, "object_types", [])),
                object_is_ontological  = obj_lc in ontology_set,

                # —— provenance (lower-case) ————————————
                context_sentence          = str(getattr(quad_obj, "reason", "")).lower(),
                proposition_sentence      = str(prop_sentence or "").lower(),
                coreference_sentence      = str(coref_sentence or "").lower(),
                natural_language_sentence = str(nl_sentence or "").lower(),
                question                  = str(question or "").lower(),

                inferred = inferred,
            )
        )

    # —— extracted quads → staged rows ——————————————
    # Iterate over our explicit pairs to guarantee correct alignment.
    for prop_json, prop_obj in prop_pairs:
        coref_sentence = prop_json.get("coreferenced_sentence", "")
        for quad in prop_obj.quadruples.all():
            _stage(
                quad_obj       = quad,
                prop_sentence  = prop_obj.text,
                coref_sentence = coref_sentence,
                nl_sentence    = quad.natural_language_sentence,
                inferred       = False,
                question       = quad.question,
            )

    # —— inferred quads → staged rows ————————————————
    for iq in inferred_quads:
        _stage(
            quad_obj       = iq,
            prop_sentence  = "",
            coref_sentence = "",
            nl_sentence    = iq.natural_language_sentence,
            inferred       = True,
            question       = iq.question,
        )

    # Final bulk write -------------------------------------------------
    if staged_rows:
        StagedQuadruple.objects.bulk_create(staged_rows)
    else:
        logger.warning("No staged_rows were created for paragraph id=%s", paragraph.id)

    return paragraph, extracted_quads, inferred_quads
