"""PostgreSQL records for the bounded synthetic Source-to-Idea slice."""

import uuid

from django.db import models
from django.db.models import F, Func, Value
from django.utils import timezone


SOURCE_TYPES = (
    "academic_paper",
    "working_paper",
    "journal_article",
    "book",
    "practitioner_publication",
    "regulatory_filing",
    "exchange_notice",
    "market_data_release",
    "dataset_documentation",
    "news",
    "web_page",
    "other",
)
ELIGIBLE_MARKETS = ("equities", "etfs", "options", "crypto", "forex", "multi_asset")
WORKFLOW_STATUSES = ("draft", "screened", "accepted", "rejected")


def source_version_identifier() -> str:
    return f"SRCV-{uuid.uuid4()}"


def idea_identifier() -> str:
    return f"IDE-{uuid.uuid4()}"


def idea_version_identifier() -> str:
    return f"IDEV-{uuid.uuid4()}"


def contribution_identifier() -> str:
    return f"SIE-{uuid.uuid4()}"


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
    source_version_id = models.CharField(
        max_length=41, unique=True, default=source_version_identifier, editable=False
    )
    version = models.PositiveIntegerField()
    corrects_version = models.PositiveIntegerField(null=True, blank=True)
    correction_reason = models.CharField(max_length=1000, null=True, blank=True)
    changed_fields = models.JSONField(default=list, editable=False)
    title = models.CharField(max_length=500)
    source_type = models.CharField(
        max_length=32, choices=((value, value) for value in SOURCE_TYPES)
    )
    citation = models.CharField(max_length=2000)
    observed_available_at = models.DateTimeField()
    authors = models.JSONField(null=True, blank=True)
    publisher = models.CharField(max_length=500, null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    canonical_url = models.CharField(max_length=2048, null=True, blank=True)
    rights_note = models.CharField(max_length=4000, null=True, blank=True)
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
    created_by = models.CharField(max_length=150, editable=False)

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


class Idea(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    idea_id = models.CharField(
        max_length=40, unique=True, default=idea_identifier, editable=False
    )
    synthetic = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    latest_version = models.PositiveIntegerField(default=0, editable=False)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=models.Q(synthetic=True), name="idea_synthetic_true"
            ),
        ]


class IdeaVersion(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    idea = models.ForeignKey(Idea, on_delete=models.PROTECT, related_name="versions")
    idea_version_id = models.CharField(
        max_length=41, unique=True, default=idea_version_identifier, editable=False
    )
    version = models.PositiveIntegerField()
    corrects_version = models.PositiveIntegerField(null=True, blank=True)
    correction_reason = models.CharField(max_length=1000, null=True, blank=True)
    changed_fields = models.JSONField(default=list, editable=False)
    title = models.CharField(max_length=500)
    mechanism = models.CharField(max_length=4000)
    testable_claim = models.CharField(max_length=4000)
    falsification = models.CharField(max_length=4000)
    eligible_market = models.CharField(
        max_length=16, choices=((value, value) for value in ELIGIBLE_MARKETS)
    )
    workflow_status = models.CharField(
        max_length=16, choices=((value, value) for value in WORKFLOW_STATUSES)
    )
    rejection_reason = models.CharField(max_length=2000, null=True, blank=True)
    synthetic = models.BooleanField(default=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    created_by = models.CharField(max_length=150, editable=False)

    class Meta:
        ordering = ["version"]
        constraints = [
            models.UniqueConstraint(
                fields=("idea", "version"), name="idea_version_unique"
            ),
            models.CheckConstraint(
                condition=models.Q(version__gt=0), name="idea_version_positive"
            ),
            models.CheckConstraint(
                condition=models.Q(synthetic=True), name="idea_version_synthetic_true"
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(version=1, corrects_version__isnull=True)
                    | (
                        models.Q(version__gt=1)
                        & models.Q(corrects_version=F("version") - 1)
                    )
                ),
                name="idea_version_immediate_predecessor",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(workflow_status="rejected", rejection_reason__isnull=False)
                    | (
                        ~models.Q(workflow_status="rejected")
                        & models.Q(rejection_reason__isnull=True)
                    )
                ),
                name="idea_rejection_reason_state",
            ),
        ]


class IdeaContribution(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    contribution_id = models.CharField(
        max_length=40, unique=True, default=contribution_identifier, editable=False
    )
    idea_version = models.ForeignKey(
        IdeaVersion, on_delete=models.PROTECT, related_name="contributions"
    )
    source_version = models.ForeignKey(
        SourceVersion, on_delete=models.PROTECT, related_name="idea_contributions"
    )
    contribution = models.CharField(max_length=4000)
    position = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ["position"]
        constraints = [
            models.UniqueConstraint(
                fields=("idea_version", "position"),
                name="idea_contribution_position_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(position__gt=0),
                name="idea_contribution_position_positive",
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
