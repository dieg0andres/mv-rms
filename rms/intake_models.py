"""Synthetic screening assertions and exact lineage bindings."""

from functools import partial

from django.db import models
from django.db.models import Q

from .hypothesis_models import ResearchIdentity, ResearchVersion, identifier


class ResearchIntake(ResearchIdentity):
    public_id = models.CharField(max_length=42, unique=True, default=partial(identifier, "INT"), editable=False)
    idea = models.OneToOneField("Idea", on_delete=models.PROTECT)


class ResearchIntakeVersion(ResearchVersion):
    public_id = models.CharField(max_length=42, unique=True, default=partial(identifier, "INTV"), editable=False)
    record = models.ForeignKey(ResearchIntake, on_delete=models.PROTECT, related_name="versions")
    idea_version = models.ForeignKey("IdeaVersion", on_delete=models.PROTECT)
    family_binding = models.ForeignKey("ResearchAssociation", on_delete=models.PROTECT)
    investigation_version = models.ForeignKey("InvestigationVersion", on_delete=models.PROTECT, null=True)
    assessment_count = models.PositiveIntegerField()

    class Meta(ResearchVersion.Meta):
        constraints = ResearchVersion.Meta.constraints + [models.CheckConstraint(
            condition=Q(state="ready", investigation_version__isnull=False, assessment_count__gt=0)
            | Q(state="early_closed", investigation_version__isnull=True, assessment_count=0),
            name="intake_state_shape",
        )]


class IntakeSourceAssessment(models.Model):
    public_id = models.CharField(primary_key=True, max_length=41, default=partial(identifier, "SASV"), editable=False)
    intake_version = models.ForeignKey(ResearchIntakeVersion, on_delete=models.PROTECT, related_name="source_assessments")
    contribution = models.ForeignKey("IdeaContribution", on_delete=models.PROTECT)
    fields = models.JSONField()
    rights_reference = models.CharField(max_length=128)
    rights_expires_at = models.DateTimeField()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["intake_version", "contribution"], name="intake_assessment_contribution")]


class IntakeHypothesisBinding(models.Model):
    hypothesis_version = models.OneToOneField("HypothesisVersion", on_delete=models.PROTECT, primary_key=True)
    intake_version = models.ForeignKey(ResearchIntakeVersion, on_delete=models.PROTECT, related_name="hypothesis_bindings")
