"""Immutable events scoped to an existing exact synthetic Test Plan version."""

from functools import partial

from django.db import models
from django.db.models import Q

from .hypothesis_models import identifier


class SyntheticGateEvent(models.Model):
    public_id = models.CharField(max_length=42, unique=True, default=partial(identifier, "SGEV"), editable=False)
    plan_version = models.ForeignKey("TestPlanVersion", on_delete=models.PROTECT)
    intake_version = models.ForeignKey("ResearchIntakeVersion", on_delete=models.PROTECT)
    predecessor = models.OneToOneField("self", null=True, on_delete=models.PROTECT, related_name="successor")
    sequence = models.PositiveSmallIntegerField()
    operation = models.CharField(max_length=12)
    recorded_state = models.CharField(max_length=12)
    authority = models.JSONField(null=True)
    rights = models.JSONField(null=True)
    impact_reason = models.CharField(max_length=500, default="")
    actor_id = models.CharField(max_length=150)
    recorded_at = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=("plan_version", "sequence"), name="synthetic_gate_single_sequence"),
            models.CheckConstraint(name="synthetic_gate_event_shape", condition=(
                Q(operation="freeze", recorded_state="frozen", sequence=1, predecessor__isnull=True,
                  authority__isnull=False, rights__isnull=False, impact_reason="")
                | Q(operation="release", recorded_state="released", sequence=2, predecessor__isnull=False,
                    authority__isnull=False, rights__isnull=False, impact_reason="")
                | (Q(operation="invalidate", recorded_state="invalidated", sequence__in=[2, 3],
                     predecessor__isnull=False, authority__isnull=True, rights__isnull=True) & ~Q(impact_reason=""))
            )),
        ]
