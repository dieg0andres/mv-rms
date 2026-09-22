import io

from django.core.management import call_command
from django.test import TransactionTestCase

from rms.management.commands.load_rms_vs_1_fixture import (
    SOURCE_CREATED,
    SOURCE_ID,
    SOURCE_UUID,
    V1_BYTES,
    V2_BYTES,
)
from rms.models import Source


class DeterministicFixtureTests(TransactionTestCase):
    def test_load_twice_is_idempotent_and_export_is_reproducible(self):
        first_load = io.StringIO()
        second_load = io.StringIO()
        call_command("load_rms_vs_1_fixture", stdout=first_load)
        first_export = self._export()
        call_command("load_rms_vs_1_fixture", stdout=second_load)
        second_export = self._export()

        source = Source.objects.get(pk=SOURCE_UUID)
        self.assertEqual(source.source_id, SOURCE_ID)
        self.assertEqual(source.created_at, SOURCE_CREATED)
        self.assertEqual(source.latest_version, 2)
        self.assertEqual(
            [bytes(version.content) for version in source.versions.order_by("version")],
            [V1_BYTES, V2_BYTES],
        )
        self.assertIn("loaded", first_load.getvalue())
        self.assertIn("unchanged", second_load.getvalue())
        self.assertEqual(first_export, second_export)

    @staticmethod
    def _export() -> bytes:
        output = io.StringIO()
        call_command("export_rms_vs_1_fixture", stdout=output)
        return output.getvalue().encode("utf-8")
