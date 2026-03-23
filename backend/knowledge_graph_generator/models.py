# backend/knowledge_graph_generator/models.py
# ════════════════════════════════════════════
# FULL DATA SCHEMA – *ready for migrations*
# -------------------------------------------------------------------------
#  • “Pipeline models”      – clean representation after extraction
#  • “Staging models”       – raw landing zone + audit metadata
#  • “Entity-mapping models”– canonical groups & aliases
# -------------------------------------------------------------------------
# 2025-05-22 note:
# ──────────────────────────────────────────────────────────────────────────
#   `StagedQuadruple.staging_paragraph` is now **nullable** so the migration
#   can run without prompting.  Existing rows get NULL; all *new* rows created
#   by the updated ingestion code will populate the FK.
#   Once legacy data are back-filled you can switch it to `null=False`.
# -------------------------------------------------------------------------

from django.db import models


# =====================================================================
#  SOURCE ABSTRACTS
# =====================================================================
class Abstract(models.Model):
    """PubMed abstract that may spawn one or more Paragraphs."""
    pubmed_id        = models.CharField(max_length=20, unique=True)
    title            = models.CharField(max_length=500)
    abstract_text    = models.TextField()
    journal          = models.CharField(max_length=255)
    publication_date = models.DateField(null=True, blank=True)
    processed        = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.title} ({self.pubmed_id})"


# =====================================================================
#  PIPELINE MODELS
# =====================================================================
class Paragraph(models.Model):
    """Input paragraph + derived paraphrases / similarity scores."""
    input_text                  = models.TextField()
    propositions_paragraph      = models.TextField(blank=True, null=True)
    coreferenced_paragraph      = models.TextField(blank=True, null=True)
    natural_language_paragraph  = models.TextField(blank=True, null=True)
    propositions_similarity     = models.FloatField(blank=True, null=True)
    coreferenced_similarity     = models.FloatField(blank=True, null=True)
    natural_language_similarity = models.FloatField(blank=True, null=True)

    def __str__(self):
        return f"Paragraph #{self.id}"


class Proposition(models.Model):
    paragraph         = models.ForeignKey(Paragraph, on_delete=models.CASCADE, related_name="propositions")
    text              = models.TextField()
    coreferenced_text = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Prop #{self.id} (Para #{self.paragraph.id})"


class Quadruple(models.Model):
    """Extractor S-P-O triple + context & QA metadata."""
    paragraph    = models.ForeignKey(Paragraph, on_delete=models.CASCADE, related_name="quadruples", null=True, blank=True)
    proposition  = models.ForeignKey(Proposition, on_delete=models.CASCADE, related_name="quadruples")

    subject_name    = models.CharField(max_length=255)
    subject_types   = models.JSONField(default=list)
    predicate       = models.CharField(max_length=255)
    predicate_types = models.JSONField(default=list)
    object_name     = models.CharField(max_length=255)
    object_types    = models.JSONField(default=list)

    reason                     = models.TextField()
    natural_language_sentence  = models.TextField(blank=True, null=True)
    cosine_similarity          = models.FloatField(blank=True, null=True)
    question           = models.TextField(blank=True, null=True)
    answer_to_question = models.TextField(blank=True, null=True)
    answer_similarity  = models.FloatField(blank=True, null=True)

    def __str__(self):
        return f"Quad #{self.id} (Prop #{self.proposition.id})"


class InferredQuadruple(models.Model):
    """Quadruple produced by iterative inference."""
    paragraph = models.ForeignKey(Paragraph, on_delete=models.CASCADE, related_name="inferred_quadruples")

    subject_name    = models.CharField(max_length=255)
    subject_types   = models.JSONField(default=list)
    predicate       = models.CharField(max_length=255)
    predicate_types = models.JSONField(default=list)
    object_name     = models.CharField(max_length=255)
    object_types    = models.JSONField(default=list)

    reason                    = models.TextField()
    natural_language_sentence = models.TextField(blank=True, null=True)
    question                  = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"InferredQuad #{self.id} (Para #{self.paragraph.id})"


# =====================================================================
#  ENTITY-MAPPING
# =====================================================================
class EntityCanonicalGroup(models.Model):
    """Set of surface forms that the mapping step deems identical."""
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Canonical Group #{self.id}"

    # helper -----------------------------------------------------------
    def get_canonical_name(self):
        freq = {}
        for a in self.aliases.all():
            freq[a.name] = freq.get(a.name, 0) + 1
        return max(freq, key=freq.get) if freq else None


class EntityAlias(models.Model):
    id              = models.CharField(max_length=100, primary_key=True)  # e.g. "<quad>-subject"
    name            = models.CharField(max_length=255)
    canonical_group = models.ForeignKey(EntityCanonicalGroup, on_delete=models.CASCADE, related_name="aliases")

    def __str__(self):
        return f"{self.name} ({self.id})"


# =====================================================================
#  STAGING  – audit wrapper + raw quads
# =====================================================================
class StagingParagraph(models.Model):
    """
    One-to-one wrapper around Paragraph for batch promotion & audit.
    """
    paragraph       = models.OneToOneField(Paragraph, on_delete=models.CASCADE, related_name="staging_meta")
    source          = models.CharField(max_length=50, default="pubmedqa-context")
    pushed_to_graph = models.BooleanField(default=False)
    push_target     = models.CharField(max_length=100, blank=True, null=True)
    pushed_at       = models.DateTimeField(blank=True, null=True)
    created_at      = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["pushed_to_graph", "created_at"])]

    def __str__(self):
        return f"StagingPara #{self.id} (Para #{self.paragraph.id})"


class StagedQuadruple(models.Model):
    """
    Raw quadruple (extracted or inferred) tied to a StagingParagraph.
    NULL FK allowed for legacy rows created before this model existed.
    """
    quadruple_id       = models.CharField(max_length=100, primary_key=True)
    staging_paragraph  = models.ForeignKey(
        StagingParagraph,
        on_delete      = models.CASCADE,
        related_name   = "quadruples",
        null=True,
        blank=True,
        help_text      = "NULL only for rows created prior to the staging-paragraph migration.",
    )
    created_at         = models.DateTimeField(auto_now_add=True)

    # -------- S-P-O ---------------------------------------------------
    subject_name           = models.CharField(max_length=255)
    subject_types          = models.JSONField(default=list, blank=True)
    subject_is_ontological = models.BooleanField(default=False)

    predicate              = models.CharField(max_length=255)
    predicate_types        = models.JSONField(default=list, blank=True)

    object_name            = models.CharField(max_length=255)
    object_types           = models.JSONField(default=list, blank=True)
    object_is_ontological  = models.BooleanField(default=False)

    # -------- provenance ---------------------------------------------
    context_sentence          = models.TextField(null=True, blank=True)
    proposition_sentence      = models.TextField()
    coreference_sentence      = models.TextField(blank=True, null=True)
    natural_language_sentence = models.TextField(blank=True, null=True)
    question                 = models.TextField(blank=True, null=True)

    inferred = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        tag = "INF" if self.inferred else "EXT"
        return f"[{tag}] {self.quadruple_id}: {self.subject_name} –{self.predicate}→ {self.object_name}"
