"""Additive synthetic draft records; endpoints are foreign keys, never ID arrays."""

from functools import partial
import uuid

from django.db import models
from django.db.models import F, Q
from django.utils import timezone


AUTHORITY_REFERENCE = "MAU-140:contract:3982eccc-e180-4ac9-bc70-9c4e16aa47f1"


def identifier(prefix):
    return f"{prefix}-{uuid.uuid4()}"


class ResearchIdentity(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    public_id = models.CharField(max_length=42, unique=True, editable=False)
    synthetic = models.BooleanField(default=True, editable=False)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    latest_version = models.PositiveIntegerField(default=0, editable=False)

    class Meta:
        abstract = True
        constraints = [models.CheckConstraint(condition=Q(synthetic=True), name="%(class)s_synthetic")]


class ResearchVersion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    public_id = models.CharField(max_length=42, unique=True, editable=False)
    version = models.PositiveIntegerField()
    schema_version = models.CharField(max_length=8, default="1.0", editable=False)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    recorded_at = models.DateTimeField(default=timezone.now, editable=False)
    created_by = models.CharField(max_length=150, editable=False)
    classification = models.CharField(max_length=16, default="synthetic", editable=False)
    authority_reference = models.CharField(max_length=128, default=AUTHORITY_REFERENCE, editable=False)
    state = models.CharField(max_length=16, editable=False)
    row_digest = models.CharField(max_length=64, editable=False)
    impact_status = models.CharField(max_length=16, default="unreviewed", editable=False)
    corrects_version = models.PositiveIntegerField(null=True, editable=False)
    correction_reason = models.CharField(max_length=4000, null=True)
    changed_fields = models.JSONField(default=list, editable=False)
    # Named scalar content only. Semantic relationships live in association tables.
    fields = models.JSONField(default=dict)

    class Meta:
        abstract = True
        ordering = ["version"]
        constraints = [
            models.UniqueConstraint(fields=["record", "version"], name="%(class)s_sequence"),
            models.CheckConstraint(condition=Q(version__gt=0), name="%(class)s_positive"),
            models.CheckConstraint(condition=Q(classification="synthetic", schema_version="1.0", authority_reference=AUTHORITY_REFERENCE), name="%(class)s_scope"),
            models.CheckConstraint(condition=Q(version=1, corrects_version__isnull=True, correction_reason__isnull=True) | (Q(version__gt=1, corrects_version=F("version") - 1, correction_reason__isnull=False) & ~Q(correction_reason="")), name="%(class)s_predecessor"),
        ]


class ResearchFamily(ResearchIdentity):
    public_id = models.CharField(max_length=42, unique=True, default=partial(identifier, "RFAM"), editable=False)


class ResearchFamilyVersion(ResearchVersion):
    public_id = models.CharField(max_length=42, unique=True, default=partial(identifier, "RFAMV"), editable=False)
    record = models.ForeignKey(ResearchFamily, on_delete=models.PROTECT, related_name="versions")
    state = models.CharField(max_length=16, default="recorded", editable=False)

    class Meta(ResearchVersion.Meta):
        abstract = False
        constraints = ResearchVersion.Meta.constraints + [models.CheckConstraint(condition=Q(state="recorded"), name="family_recorded")]


class Investigation(ResearchIdentity):
    public_id = models.CharField(max_length=42, unique=True, default=partial(identifier, "INV"), editable=False)


class InvestigationVersion(ResearchVersion):
    public_id = models.CharField(max_length=42, unique=True, default=partial(identifier, "INVV"), editable=False)
    record = models.ForeignKey(Investigation, on_delete=models.PROTECT, related_name="versions")
    state = models.CharField(max_length=16, default="proposed", editable=False)

    class Meta(ResearchVersion.Meta):
        abstract = False
        constraints = ResearchVersion.Meta.constraints + [models.CheckConstraint(condition=Q(state="proposed"), name="investigation_proposed")]


class PriorResearchAssessment(ResearchIdentity):
    public_id = models.CharField(max_length=42, unique=True, default=partial(identifier, "PRA"), editable=False)


class PriorResearchAssessmentVersion(ResearchVersion):
    public_id = models.CharField(max_length=42, unique=True, default=partial(identifier, "PRAV"), editable=False)
    record = models.ForeignKey(PriorResearchAssessment, on_delete=models.PROTECT, related_name="versions")
    state = models.CharField(max_length=16, default="recorded", editable=False)
    link_count = models.PositiveSmallIntegerField(editable=False)
    link_digest = models.CharField(max_length=64, editable=False)

    class Meta(ResearchVersion.Meta):
        abstract = False
        constraints = ResearchVersion.Meta.constraints + [
            models.CheckConstraint(condition=Q(state="recorded"), name="assessment_recorded"),
            models.CheckConstraint(condition=Q(link_count__lte=100, link_digest__regex=r"^[0-9a-f]{64}$") & ~Q(fields__has_key="record_links"), name="assessment_link_seal_shape"),
        ]


class Hypothesis(ResearchIdentity):
    public_id = models.CharField(max_length=42, unique=True, default=partial(identifier, "HYP"), editable=False)


class HypothesisVersion(ResearchVersion):
    public_id = models.CharField(max_length=42, unique=True, default=partial(identifier, "HYPV"), editable=False)
    record = models.ForeignKey(Hypothesis, on_delete=models.PROTECT, related_name="versions")
    state = models.CharField(max_length=16, default="draft", editable=False)

    class Meta(ResearchVersion.Meta):
        abstract = False
        constraints = ResearchVersion.Meta.constraints + [models.CheckConstraint(condition=Q(state="draft"), name="hypothesis_draft")]


class ResearchAssociationIdentity(ResearchIdentity):
    public_id = models.CharField(max_length=42, unique=True, default=partial(identifier, "RAS"), editable=False)
    # One logical classification per exact Idea version; revisions change its family.
    idea_version = models.OneToOneField("rms.IdeaVersion", null=True, on_delete=models.PROTECT, related_name="family_identity")


ASSOCIATION_ENDPOINTS = ("idea", "source", "family", "investigation", "assessment", "hypothesis", "idea_family")


def association_shape(kind, present):
    return Q(kind=kind, **{f"{name}_version__isnull": name not in present for name in ASSOCIATION_ENDPOINTS})


class ResearchAssociation(ResearchVersion):
    public_id = models.CharField(max_length=42, unique=True, default=partial(identifier, "RASV"), editable=False)
    record = models.ForeignKey(ResearchAssociationIdentity, on_delete=models.PROTECT, related_name="versions")
    state = models.CharField(max_length=16, default="effective", editable=False)
    kind = models.CharField(max_length=32)
    rationale = models.CharField(max_length=4000, null=True)
    origin_type = models.CharField(max_length=16, null=True, editable=False)
    position = models.PositiveSmallIntegerField(null=True, editable=False)
    idea_version = models.ForeignKey("rms.IdeaVersion", null=True, on_delete=models.PROTECT, related_name="research_associations")
    source_version = models.ForeignKey("rms.SourceVersion", null=True, on_delete=models.PROTECT, related_name="research_associations")
    family_version = models.ForeignKey(ResearchFamilyVersion, null=True, on_delete=models.PROTECT, related_name="research_associations")
    investigation_version = models.ForeignKey(InvestigationVersion, null=True, on_delete=models.PROTECT, related_name="research_associations")
    assessment_version = models.ForeignKey(PriorResearchAssessmentVersion, null=True, on_delete=models.PROTECT, related_name="research_associations")
    hypothesis_version = models.ForeignKey(HypothesisVersion, null=True, on_delete=models.PROTECT, related_name="research_associations")
    idea_family_version = models.ForeignKey("self", null=True, on_delete=models.PROTECT, related_name="hypothesis_bindings")

    class Meta(ResearchVersion.Meta):
        abstract = False
        constraints = ResearchVersion.Meta.constraints + [
            models.CheckConstraint(condition=Q(state="effective"), name="association_effective"),
            models.CheckConstraint(condition=Q(fields={}), name="association_no_id_arrays"),
            models.CheckConstraint(condition=Q(kind="AssessmentRecord", position__gt=0) | (~Q(kind="AssessmentRecord") & Q(position__isnull=True)), name="association_position_shape"),
            models.UniqueConstraint(fields=["assessment_version", "position"], condition=Q(kind="AssessmentRecord"), name="assessment_link_position"),
            models.CheckConstraint(condition=association_shape("IdeaFamily", {"idea", "family"}) | association_shape("InvestigationFamily", {"investigation", "family"}) | association_shape("PriorResearchInvestigation", {"assessment", "investigation"}) | association_shape("HypothesisInvestigation", {"hypothesis", "investigation"}) | association_shape("IdeaHypothesis", {"idea", "hypothesis", "idea_family"}) | association_shape("AssessmentRecord", {"assessment", "idea"}) | association_shape("AssessmentRecord", {"assessment", "source"}) | association_shape("AssessmentRecord", {"assessment", "family"}) | association_shape("AssessmentRecord", {"assessment", "investigation"}), name="association_endpoint_shape"),
            models.CheckConstraint(condition=Q(kind="IdeaHypothesis", origin_type="direct", rationale__isnull=False) | (~Q(kind="IdeaHypothesis") & Q(origin_type__isnull=True)), name="association_direct_origin"),
            models.UniqueConstraint(fields=["hypothesis_version", "kind"], condition=Q(kind__in=["IdeaHypothesis", "HypothesisInvestigation"]), name="hypothesis_single_endpoints"),
            models.UniqueConstraint(fields=["investigation_version", "kind"], condition=Q(kind__in=["InvestigationFamily", "PriorResearchInvestigation"]), name="investigation_single_context"),
        ]


class AssessmentExternalReference(ResearchVersion):
    public_id = models.CharField(max_length=42, unique=True, default=partial(identifier, "AERV"), editable=False)
    record = models.ForeignKey(ResearchAssociationIdentity, on_delete=models.PROTECT, related_name="external_versions")
    state = models.CharField(max_length=16, default="recorded", editable=False)
    assessment_version = models.ForeignKey(PriorResearchAssessmentVersion, on_delete=models.PROTECT, related_name="external_references")
    reference = models.CharField(max_length=4000)
    position = models.PositiveSmallIntegerField(editable=False)

    class Meta(ResearchVersion.Meta):
        abstract = False
        constraints = ResearchVersion.Meta.constraints + [
            models.CheckConstraint(condition=Q(state="recorded", fields={}, position__gt=0), name="external_reference_shape"),
            models.UniqueConstraint(fields=["assessment_version", "position"], name="external_reference_position"),
        ]


IMPACT_ENDPOINTS = ("source", "idea", "family", "investigation", "assessment", "association")


class HypothesisCorrectionImpact(ResearchVersion):
    public_id = models.CharField(max_length=42, unique=True, default=partial(identifier, "HCIV"), editable=False)
    record = models.ForeignKey(ResearchAssociationIdentity, on_delete=models.PROTECT, related_name="impact_versions")
    state = models.CharField(max_length=16, default="review_needed", editable=False)
    hypothesis_version = models.ForeignKey(HypothesisVersion, on_delete=models.PROTECT, related_name="correction_impacts")
    pinned_source = models.ForeignKey("rms.SourceVersion", null=True, on_delete=models.PROTECT, related_name="pinned_hypothesis_impacts")
    newer_source = models.ForeignKey("rms.SourceVersion", null=True, on_delete=models.PROTECT, related_name="new_hypothesis_impacts")
    pinned_idea = models.ForeignKey("rms.IdeaVersion", null=True, on_delete=models.PROTECT, related_name="pinned_hypothesis_impacts")
    newer_idea = models.ForeignKey("rms.IdeaVersion", null=True, on_delete=models.PROTECT, related_name="new_hypothesis_impacts")
    pinned_family = models.ForeignKey(ResearchFamilyVersion, null=True, on_delete=models.PROTECT, related_name="pinned_hypothesis_impacts")
    newer_family = models.ForeignKey(ResearchFamilyVersion, null=True, on_delete=models.PROTECT, related_name="new_hypothesis_impacts")
    pinned_investigation = models.ForeignKey(InvestigationVersion, null=True, on_delete=models.PROTECT, related_name="pinned_hypothesis_impacts")
    newer_investigation = models.ForeignKey(InvestigationVersion, null=True, on_delete=models.PROTECT, related_name="new_hypothesis_impacts")
    pinned_assessment = models.ForeignKey(PriorResearchAssessmentVersion, null=True, on_delete=models.PROTECT, related_name="pinned_hypothesis_impacts")
    newer_assessment = models.ForeignKey(PriorResearchAssessmentVersion, null=True, on_delete=models.PROTECT, related_name="new_hypothesis_impacts")
    pinned_association = models.ForeignKey(ResearchAssociation, null=True, on_delete=models.PROTECT, related_name="pinned_hypothesis_impacts")
    newer_association = models.ForeignKey(ResearchAssociation, null=True, on_delete=models.PROTECT, related_name="new_hypothesis_impacts")

    class Meta(ResearchVersion.Meta):
        abstract = False
        constraints = ResearchVersion.Meta.constraints + [
            models.CheckConstraint(condition=Q(state="review_needed"), name="impact_review_needed"),
            models.CheckConstraint(condition=Q(fields={}), name="impact_no_id_arrays"),
            models.CheckConstraint(condition=Q(*[Q(**{f"{direction}_{endpoint}__isnull": endpoint != selected for direction in ("pinned", "newer") for endpoint in IMPACT_ENDPOINTS}) for selected in IMPACT_ENDPOINTS], _connector=Q.OR), name="impact_endpoint_pair"),
        ] + [models.UniqueConstraint(fields=["hypothesis_version", f"newer_{endpoint}"], name=f"impact_{endpoint}_unique") for endpoint in IMPACT_ENDPOINTS]
