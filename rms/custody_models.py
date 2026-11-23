"""Append-only custody receipts. Original bytes remain on the exact result."""

from functools import partial
from uuid import uuid4

from django.db import models

from .hypothesis_models import identifier


class CustodyEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    public_id = models.CharField(max_length=42, unique=True, default=partial(identifier, 'CUE'), editable=False)
    result = models.ForeignKey('RunResultVersion', on_delete=models.PROTECT, related_name='custody_events')
    predecessor = models.OneToOneField('self', null=True, on_delete=models.PROTECT, related_name='successor')
    impact_of = models.ForeignKey('self', null=True, on_delete=models.PROTECT, related_name='impacts')
    sequence = models.PositiveSmallIntegerField()
    operation = models.CharField(max_length=12)
    actor_id = models.CharField(max_length=150)
    recorded_at = models.DateTimeField()
    manifest = models.JSONField()
    manifest_digest = models.CharField(max_length=64)

    class Meta:
        constraints = [models.UniqueConstraint(fields=('result', 'sequence'), name='custody_single_sequence')]
