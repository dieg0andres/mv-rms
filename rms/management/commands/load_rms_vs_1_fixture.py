"""Load the deterministic invented RMS-VS-1-F1 PostgreSQL fixture."""

import uuid
from datetime import datetime, timezone

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from rms.models import Source, SourceManifest, SourceVersion
from rms.source_manifests import generate_source_manifest
from rms.source_versions import SourceVersion as DomainSourceVersion


SOURCE_UUID = uuid.UUID("11111111-1111-4111-8111-111111111111")
V1_UUID = uuid.UUID("22222222-2222-4222-8222-222222222222")
V2_UUID = uuid.UUID("33333333-3333-4333-8333-333333333333")
M1_UUID = uuid.UUID("44444444-4444-4444-8444-444444444444")
M2_UUID = uuid.UUID("55555555-5555-4555-8555-555555555555")
SOURCE_ID = "synthetic-source-001"
V1_BYTES = b"invented Source version one"
V2_BYTES = b"invented Source version two correction"
SOURCE_CREATED = datetime(2026, 9, 22, 0, 0, 0, tzinfo=timezone.utc)
V1_CREATED = datetime(2026, 9, 22, 0, 0, 1, tzinfo=timezone.utc)
V2_CREATED = datetime(2026, 9, 22, 0, 0, 2, tzinfo=timezone.utc)


class Command(BaseCommand):
    help = "Load deterministic synthetic fixture RMS-VS-1-F1 without replacing rows."

    def handle(self, *args, **options):
        with transaction.atomic():
            existing = Source.objects.filter(pk=SOURCE_UUID).first()
            if existing is not None:
                self._verify_existing(existing)
                self.stdout.write("RMS-VS-1-F1 unchanged")
                return
            if Source.objects.filter(source_id=SOURCE_ID).exists():
                raise CommandError("RMS-VS-1-F1 logical Source identity conflicts")

            source = Source.objects.create(
                id=SOURCE_UUID,
                source_id=SOURCE_ID,
                synthetic=True,
                created_at=SOURCE_CREATED,
            )
            v1 = SourceVersion.objects.create(
                id=V1_UUID,
                source=source,
                version=1,
                corrects_version=None,
                content=V1_BYTES,
                synthetic=True,
                created_at=V1_CREATED,
            )
            source.refresh_from_db()
            SourceManifest.objects.create(
                id=M1_UUID,
                source=source,
                through_version=1,
                schema_version=1,
                version_count=1,
                manifest_bytes=_manifest((v1,)),
                created_at=V1_CREATED,
            )
            v2 = SourceVersion.objects.create(
                id=V2_UUID,
                source=source,
                version=2,
                corrects_version=1,
                content=V2_BYTES,
                synthetic=True,
                created_at=V2_CREATED,
            )
            source.refresh_from_db()
            SourceManifest.objects.create(
                id=M2_UUID,
                source=source,
                through_version=2,
                schema_version=1,
                version_count=2,
                manifest_bytes=_manifest((v1, v2)),
                created_at=V2_CREATED,
            )
        self.stdout.write("RMS-VS-1-F1 loaded")

    def _verify_existing(self, source: Source) -> None:
        versions = tuple(source.versions.order_by("version"))
        expected = (
            (V1_UUID, 1, None, V1_BYTES, V1_CREATED),
            (V2_UUID, 2, 1, V2_BYTES, V2_CREATED),
        )
        actual = tuple(
            (
                version.id,
                version.version,
                version.corrects_version,
                bytes(version.content),
                version.created_at,
            )
            for version in versions
        )
        manifests = tuple(source.manifests.order_by("through_version"))
        if (
            source.source_id != SOURCE_ID
            or source.synthetic is not True
            or source.created_at != SOURCE_CREATED
            or source.latest_version != 2
            or actual != expected
            or tuple(manifest.id for manifest in manifests) != (M1_UUID, M2_UUID)
            or tuple(bytes(manifest.manifest_bytes) for manifest in manifests)
            != (_manifest(versions[:1]), _manifest(versions))
        ):
            raise CommandError("existing RMS-VS-1-F1 rows do not match the fixture")


def _manifest(versions) -> bytes:
    return generate_source_manifest(
        DomainSourceVersion(
            source_id=SOURCE_ID,
            version=version.version,
            content=bytes(version.content),
            synthetic=version.synthetic,
            corrects_version=version.corrects_version,
        )
        for version in versions
    )
