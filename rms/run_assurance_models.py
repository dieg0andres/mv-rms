"""Synthetic assurance records; exact reliance is never rebound on correction."""

from functools import partial

from django.db import models
from django.db.models import Q

from .hypothesis_models import identifier
from .run_result_models import RunRecord, RunResultVersion


REVIEW_OUTCOMES = ('pass', 'fail', 'inconclusive', 'invalid')
USABLE_REVIEWS = ('pass', 'fail')
DISPOSITIONS = ('close_rejected', 'return_for_revision')


class AssuranceRecord(RunRecord):
    result = models.ForeignKey(RunResultVersion, on_delete=models.PROTECT, related_name='%(class)s_records')
    result_digest = models.CharField(max_length=64, editable=False)
    artifact_manifest_digest = models.CharField(max_length=64, editable=False)
    sequence = models.PositiveIntegerField()
    supersedes = models.OneToOneField('self', null=True, on_delete=models.PROTECT, related_name='successor')
    correction_reason = models.CharField(max_length=2000, null=True)

    class Meta:
        abstract = True
        ordering = ['sequence']
        constraints = [
            models.UniqueConstraint(fields=['result', 'sequence'], name='%(class)s_sequence'),
            models.CheckConstraint(
                condition=Q(sequence=1, supersedes__isnull=True, correction_reason__isnull=True) |
                (Q(sequence__gt=1, supersedes__isnull=False, correction_reason__isnull=False) & ~Q(correction_reason='')),
                name='%(class)s_lineage',
            ),
        ]


class RunReview(AssuranceRecord):
    public_id = models.CharField(max_length=42, unique=True, default=partial(identifier, 'REV'), editable=False)
    outcome = models.CharField(max_length=16)
    rationale = models.CharField(max_length=2000)
    limitations = models.CharField(max_length=2000)

    class Meta(AssuranceRecord.Meta):
        constraints = AssuranceRecord.Meta.constraints + [
            models.CheckConstraint(condition=Q(outcome__in=REVIEW_OUTCOMES), name='runreview_outcome'),
        ]


class RunDecision(AssuranceRecord):
    public_id = models.CharField(max_length=42, unique=True, default=partial(identifier, 'DEC'), editable=False)
    review = models.ForeignKey(RunReview, on_delete=models.PROTECT, related_name='decisions')
    disposition = models.CharField(max_length=24)
    rationale = models.CharField(max_length=2000)

    class Meta(AssuranceRecord.Meta):
        constraints = AssuranceRecord.Meta.constraints + [
            models.CheckConstraint(condition=Q(disposition__in=DISPOSITIONS), name='rundecision_disposition'),
        ]


class RunLesson(AssuranceRecord):
    public_id = models.CharField(max_length=42, unique=True, default=partial(identifier, 'LES'), editable=False)
    review = models.ForeignKey(RunReview, on_delete=models.PROTECT, related_name='lessons')
    decision = models.ForeignKey(RunDecision, on_delete=models.PROTECT, related_name='lessons')
    claim = models.CharField(max_length=2000)
    limitations = models.CharField(max_length=2000)
    uncertainty = models.CharField(max_length=2000)
    applicability = models.CharField(max_length=2000)
    implication = models.CharField(max_length=2000)
