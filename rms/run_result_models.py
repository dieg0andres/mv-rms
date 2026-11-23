"""Append-only lifecycle and reported results for synthetic RunAttempts."""

from functools import partial
import uuid

from django.db import models
from django.db.models import Q
from django.utils import timezone

from .hypothesis_models import identifier


class RunRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recorded_at = models.DateTimeField(default=timezone.now, editable=False)
    recorded_by = models.CharField(max_length=150, editable=False)
    actor_id = models.CharField(max_length=64, editable=False)
    row_digest = models.CharField(max_length=64, editable=False)

    class Meta:
        abstract = True


class RunLifecycleEvent(RunRecord):
    STATES = ('running', 'completed', 'failed', 'cancelled')
    public_id = models.CharField(max_length=42, unique=True, default=partial(identifier, 'RUE'), editable=False)
    run = models.ForeignKey('rms.RunAttempt', on_delete=models.PROTECT, related_name='lifecycle_events')
    state = models.CharField(max_length=12)
    sequence = models.PositiveSmallIntegerField()
    previous_event = models.OneToOneField('self', null=True, on_delete=models.PROTECT)
    reason = models.CharField(max_length=2000)

    class Meta:
        ordering = ['sequence']
        constraints = [
            models.UniqueConstraint(fields=['run', 'sequence'], name='run_event_sequence'),
            models.CheckConstraint(condition=(Q(sequence=1, previous_event__isnull=True,
                                                state__in=['running', 'failed', 'cancelled']) |
                                              Q(sequence=2, previous_event__isnull=False,
                                                state__in=['completed', 'failed', 'cancelled'])),
                                   name='run_event_shape'),
        ]


class RunRetry(RunRecord):
    predecessor = models.OneToOneField('rms.RunAttempt', on_delete=models.PROTECT, related_name='retry_edge')
    successor = models.OneToOneField('rms.RunAttempt', on_delete=models.PROTECT, related_name='predecessor_edge')
    terminal_event = models.OneToOneField(RunLifecycleEvent, on_delete=models.PROTECT)
    reason = models.CharField(max_length=2000)


class RunResultVersion(RunRecord):
    OUTCOMES = ('mandatory_fail', 'inconclusive', 'criteria_pass')
    public_id = models.CharField(max_length=42, unique=True, default=partial(identifier, 'RESV'), editable=False)
    run = models.ForeignKey('rms.RunAttempt', on_delete=models.PROTECT, related_name='result_versions')
    completed_event = models.ForeignKey(RunLifecycleEvent, on_delete=models.PROTECT)
    version = models.PositiveIntegerField()
    supersedes = models.OneToOneField('self', null=True, on_delete=models.PROTECT)
    correction_reason = models.CharField(max_length=2000, null=True)
    summary = models.CharField(max_length=2000)
    assessment_outcome = models.CharField(max_length=16)
    assessments = models.JSONField()
    artifact_bytes = models.BinaryField(editable=False)
    artifact_manifest = models.JSONField()

    class Meta:
        ordering = ['version']
        constraints = [
            models.UniqueConstraint(fields=['run', 'version'], name='run_result_sequence'),
            models.CheckConstraint(condition=(Q(version=1, supersedes__isnull=True, correction_reason__isnull=True) |
                                              (Q(version__gt=1, supersedes__isnull=False, correction_reason__isnull=False) &
                                               ~Q(correction_reason=''))), name='run_result_lineage_shape'),
            models.CheckConstraint(condition=Q(assessment_outcome__in=['mandatory_fail', 'inconclusive', 'criteria_pass']),
                                   name='run_result_outcome'),
        ]
