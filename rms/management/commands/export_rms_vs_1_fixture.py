"""Export deterministic public history/manifest evidence for RMS-VS-1-F1."""

import base64

from django.core.management.base import BaseCommand, CommandError

from rms.management.commands.load_rms_vs_1_fixture import SOURCE_ID
from rms.models import Source
from rms.services import canonical_json_bytes, latest_manifest, source_history


class Command(BaseCommand):
    help = "Write a deterministic synthetic-only RMS-VS-1-F1 evidence export."

    def handle(self, *args, **options):
        try:
            source = Source.objects.get(source_id=SOURCE_ID)
        except Source.DoesNotExist as error:
            raise CommandError("RMS-VS-1-F1 is not loaded") from error
        manifest = latest_manifest(source)
        export = {
            "fixture": "RMS-VS-1-F1",
            "history": source_history(source),
            "manifest_base64": base64.b64encode(
                bytes(manifest.manifest_bytes)
            ).decode("ascii"),
            "manifest_sha256": manifest.manifest_sha256,
        }
        self.stdout.write(canonical_json_bytes(export).decode("utf-8"))
