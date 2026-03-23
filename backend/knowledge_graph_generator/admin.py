# backend/knowledge_graph_generator/admin.py
# ════════════════════════════════════════════
# Django-admin customisation for the KG pipeline.
#
#  SECTIONS
#  ------------------------------------------------------------------
#  1. Abstracts         – upstream PubMed metadata
#  2. Pipeline objects  – Paragraph ▸ Proposition ▸ Quad / InferredQuad
#  3. Entity mapping    – canonical groups & aliases
#  4. Staging layer     – StagingParagraph + StagedQuadruple
#  ------------------------------------------------------------------

from django.contrib import admin
from django.utils.html import format_html, escape

from .models import (
    # upstream
    Abstract,
    # pipeline
    Paragraph, Proposition, Quadruple, InferredQuadruple,
    # entity mapping
    EntityCanonicalGroup, EntityAlias,
    # staging
    StagingParagraph, StagedQuadruple,
)

# ====================================================================
# 1.  ABSTRACTS
# ====================================================================
@admin.register(Abstract)
class AbstractAdmin(admin.ModelAdmin):
    list_display  = ("title", "pubmed_id", "journal", "publication_date", "processed")
    list_filter   = ("processed",)
    search_fields = ("title", "pubmed_id", "journal")


# ====================================================================
# 2.  PIPELINE INLINES
# ====================================================================
class QuadrupleInline(admin.TabularInline):
    model   = Quadruple
    extra   = 0
    fields  = ("subject_name", "predicate", "object_name", "reason", "question", "cosine_similarity")
    readonly_fields = fields


class PropositionInline(admin.TabularInline):
    model   = Proposition
    extra   = 0
    show_change_link = True

    fields          = ("text", "coreferenced_text", "quad_summary")
    readonly_fields = fields

    def quad_summary(self, obj):
        first = obj.quadruples.first()
        count = obj.quadruples.count()
        if not first:
            return "—"
        short = f"S:{first.subject_name} P:{first.predicate} O:{first.object_name}"
        return short if count == 1 else f"{short}  (+{count-1} more)"
    quad_summary.short_description = "Quadruples"


class InlineQuadruples(admin.TabularInline):
    model   = Quadruple
    extra   = 0
    fields  = ("subject_name", "predicate", "object_name", "reason", "question")
    readonly_fields = fields


class InferredQuadrupleInline(admin.TabularInline):
    model   = InferredQuadruple
    extra   = 0
    fields  = ("subject_name", "predicate", "object_name", "reason", "question")
    readonly_fields = fields


# ====================================================================
# 2.  PIPELINE ADMINS
# ====================================================================
@admin.register(Paragraph)
class ParagraphAdmin(admin.ModelAdmin):
    list_display  = ("id", "input_text", "propositions_similarity", "coreferenced_similarity", "natural_language_similarity")
    list_filter   = ("propositions_similarity", "coreferenced_similarity", "natural_language_similarity")
    search_fields = ("input_text",)
    inlines       = [PropositionInline, InlineQuadruples, InferredQuadrupleInline]


@admin.register(Proposition)
class PropositionAdmin(admin.ModelAdmin):
    list_display  = ("id", "paragraph", "text")
    search_fields = ("text",)
    inlines       = [QuadrupleInline]


@admin.register(Quadruple)
class QuadrupleAdmin(admin.ModelAdmin):
    list_display  = ("id", "proposition", "subject_name", "predicate", "object_name", "reason", "question")
    search_fields = ("subject_name", "object_name", "predicate", "reason", "question")
    list_filter   = ("cosine_similarity",)


@admin.register(InferredQuadruple)
class InferredQuadrupleAdmin(admin.ModelAdmin):
    list_display  = ("id", "paragraph", "subject_name", "predicate", "object_name", "reason", "question")
    search_fields = ("subject_name", "object_name", "predicate", "reason", "question")


# ====================================================================
# 3.  ENTITY-MAPPING ADMINS
# ====================================================================
@admin.register(EntityCanonicalGroup)
class EntityCanonicalGroupAdmin(admin.ModelAdmin):
    list_display  = ("id", "canonical_name", "created_at", "alias_count")
    readonly_fields = ("created_at", "alias_table")
    fields = ("created_at", "alias_table")

    # helpers ----------------------------------------------------------
    def canonical_name(self, obj): return obj.get_canonical_name()
    canonical_name.short_description = "Canonical Name"

    def alias_count(self, obj): return obj.aliases.count()
    alias_count.short_description = "# Aliases"

    def alias_table(self, obj):
        grouped = {}
        for a in obj.aliases.all():
            grouped.setdefault(a.name, []).append(a.id)
        if not grouped:
            return "—"
        rows = ["<table style='border-collapse:collapse;'>"]
        for name, ids in grouped.items():
            rows.append(f"<tr><td>{escape(name)}</td><td>{', '.join(ids)}</td></tr>")
        rows.append("</table>")
        return format_html("".join(rows))
    alias_table.short_description = "Aliases"


@admin.register(EntityAlias)
class EntityAliasAdmin(admin.ModelAdmin):
    list_display  = ("id", "name", "canonical_group")
    search_fields = ("id", "name")
    list_filter   = ("canonical_group",)


# ====================================================================
# 4.  STAGING LAYER
# ====================================================================

# ---------- helper formatters ---------------------------------------
def json_list(lst):
    """Pretty print list fields without overwhelming the table."""
    if not lst:
        return "[]"
    return "[" + ", ".join(lst) + "]"


def trunc(txt, n=80):
    return (txt[: n - 1] + "…") if txt and len(txt) > n else txt


class StagedQuadInline(admin.TabularInline):
    """Full detail grid inside a StagingParagraph view."""
    model  = StagedQuadruple
    extra  = 0
    show_change_link = True

    fields = (
        "quadruple_id",
        "subject_name", "subject_types", "subject_is_ontological",
        "predicate", "predicate_types",
        "object_name", "object_types", "object_is_ontological",
        "context_sentence", "proposition_sentence", "coreference_sentence",
        "natural_language_sentence", "question",
        "inferred",
    )
    readonly_fields = fields

    # nicer type rendering in list-row
    def subject_types(self, obj):  # type: ignore
        return json_list(obj.subject_types)
    def predicate_types(self, obj):  # type: ignore
        return json_list(obj.predicate_types)
    def object_types(self, obj):  # type: ignore
        return json_list(obj.object_types)


@admin.register(StagingParagraph)
class StagingParagraphAdmin(admin.ModelAdmin):
    list_display  = ("id", "paragraph", "source", "pushed_to_graph", "push_target", "created_at", "pushed_at")
    list_filter   = ("pushed_to_graph", "source", "push_target")
    search_fields = ("paragraph__input_text",)
    readonly_fields = ("created_at", "pushed_at")
    inlines       = [StagedQuadInline]


@admin.register(StagedQuadruple)
class StagedQuadrupleAdmin(admin.ModelAdmin):
    # list helpers -----------------------------------------------------
    def subj_types(self, obj): return json_list(obj.subject_types)
    def pred_types(self, obj): return json_list(obj.predicate_types)
    def obj_types(self, obj):  return json_list(obj.object_types)
    def ctx(self, obj):   return trunc(obj.context_sentence)
    def prop(self, obj):  return trunc(obj.proposition_sentence)
    def coref(self, obj): return trunc(obj.coreference_sentence)
    def nl(self, obj):    return trunc(obj.natural_language_sentence)
    def qns(self, obj):   return trunc(obj.question)

    subj_types.short_description = "S-types"
    pred_types.short_description = "P-types"
    obj_types.short_description  = "O-types"
    ctx.short_description  = "Context"
    prop.short_description = "Proposition"
    coref.short_description= "Coref"
    nl.short_description   = "NL Sentence"
    qns.short_description  = "Question"

    list_display = (
        "quadruple_id",
        "subject_name", "subject_is_ontological", "subj_types",
        "predicate", "pred_types",
        "object_name",  "object_is_ontological", "obj_types",
        "ctx", "prop", "coref", "nl", "qns",
        "inferred",
        "staging_paragraph",
        "created_at",
    )

    list_filter   = (
        "subject_is_ontological", "object_is_ontological",
        "inferred", "created_at",
    )
    search_fields = (
        "quadruple_id", "subject_name", "object_name", "predicate",
        "context_sentence", "proposition_sentence", "coreference_sentence",
        "natural_language_sentence", "question",
    )

    # expose every field in detail view (read-only)
    readonly_fields = [f.name for f in StagedQuadruple._meta.get_fields()]
