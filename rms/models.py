"""PostgreSQL records for the bounded synthetic Source slice."""

import uuid

from django.db import models
from django.db.models import F, Func, Value
from django.utils import timezone


class Digest(Func):
    function = "digest"


class Encode(Func):
    function = "encode"


class OctetLength(Func):
    function = "octet_length"


class Source(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source_id = models.CharField(max_length=128, unique=True)
    synthetic = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    latest_version = models.PositiveIntegerField(default=0, editable=False)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(synthetic=True), name="source_synthetic_true"
            ),
        ]


class SourceVersion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source = models.ForeignKey(
        Source, on_delete=models.PROTECT, related_name="versions"
    )
    version = models.PositiveIntegerField()
    corrects_version = models.PositiveIntegerField(null=True, blank=True)
    content = models.BinaryField(editable=False)
    byte_length = models.GeneratedField(
        expression=OctetLength(F("content")),
        output_field=models.IntegerField(),
        db_persist=True,
    )
    content_sha256 = models.GeneratedField(
        expression=Encode(Digest(F("content"), Value("sha256")), Value("hex")),
        output_field=models.CharField(max_length=64),
        db_persist=True,
    )
    synthetic = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        ordering = ["version"]
        constraints = [
            models.UniqueConstraint(
                fields=("source", "version"), name="source_version_unique"
            ),
            models.CheckConstraint(
                condition=models.Q(version__gt=0), name="source_version_positive"
            ),
            models.CheckConstraint(
                condition=models.Q(synthetic=True), name="source_version_synthetic_true"
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(version=1, corrects_version__isnull=True)
                    | (
                        models.Q(version__gt=1)
                        & models.Q(corrects_version=F("version") - 1)
                    )
                ),
                name="source_version_immediate_predecessor",
            ),
        ]


class SourceManifest(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source = models.ForeignKey(
        Source, on_delete=models.PROTECT, related_name="manifests"
    )
    through_version = models.PositiveIntegerField()
    schema_version = models.PositiveIntegerField(default=1)
    version_count = models.PositiveIntegerField()
    manifest_bytes = models.BinaryField(editable=False)
    byte_length = models.GeneratedField(
        expression=OctetLength(F("manifest_bytes")),
        output_field=models.IntegerField(),
        db_persist=True,
    )
    manifest_sha256 = models.GeneratedField(
        expression=Encode(
            Digest(F("manifest_bytes"), Value("sha256")), Value("hex")
        ),
        output_field=models.CharField(max_length=64),
        db_persist=True,
    )
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("source", "through_version"),
                name="source_manifest_through_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(through_version__gt=0),
                name="source_manifest_version_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(schema_version=1),
                name="source_manifest_schema_one",
            ),
            models.CheckConstraint(
                condition=models.Q(version_count=F("through_version")),
                name="source_manifest_count_matches",
            ),
        ]


class IdempotencyRecord(models.Model):
    key = models.CharField(primary_key=True, max_length=128)
    request_method = models.CharField(max_length=8)
    request_path = models.CharField(max_length=512)
    request_sha256 = models.CharField(max_length=64)
    response_status = models.PositiveSmallIntegerField()
    response_identity = models.CharField(max_length=128)
    response_bytes = models.BinaryField(editable=False)
    response_sha256 = models.GeneratedField(
        expression=Encode(
            Digest(F("response_bytes"), Value("sha256")), Value("hex")
        ),
        output_field=models.CharField(max_length=64),
        db_persist=True,
    )
    created_at = models.DateTimeField(default=timezone.now, editable=False)
