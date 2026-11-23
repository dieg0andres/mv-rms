"""Append-only, reported synthetic execution identities."""
from functools import partial
import uuid

from django.db import models
from django.utils import timezone

from .hypothesis_models import identifier
from .test_plan_models import TestPlanVersion


class RunAttempt(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    public_id = models.CharField(max_length=42, unique=True, default=partial(identifier, 'RUN'), editable=False)
    plan_version = models.ForeignKey(TestPlanVersion, on_delete=models.PROTECT, related_name='run_attempts')
    configuration_key = models.CharField(max_length=64)
    external_reference = models.CharField(max_length=106, unique=True)
    code_commit = models.CharField(max_length=40)
    code_manifest_digest = models.CharField(max_length=64)
    dependency_lock_digest = models.CharField(max_length=64)
    dataset_manifest_digest = models.CharField(max_length=64)
    parameter_digest = models.CharField(max_length=64)
    environment_digest = models.CharField(max_length=64)
    reported_by = models.CharField(max_length=150, editable=False)
    reporter_id = models.CharField(max_length=64, editable=False)
    recorded_at = models.DateTimeField(default=timezone.now, editable=False)
    row_digest = models.CharField(max_length=64, editable=False)

    class Meta:
        ordering = ['-recorded_at', '-public_id']
