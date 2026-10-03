import base64
from datetime import UTC, datetime
from django.contrib.auth.models import Group, User
from django.test import Client, TransactionTestCase
from rms.models import SourceManifest
from rms.services import create_source, correct_source

class SourceHistoryPageTests(TransactionTestCase):
    source_id = "synthetic-page-source-001"
    v1 = b"invented Source version one"
    v2 = b"invented Source version two correction"
    def setUp(self):
        viewer_group, _ = Group.objects.get_or_create(name="founder_viewer")
        self.viewer = User.objects.create_user("page-viewer", password="invented-page-pass")
        self.viewer.groups.add(viewer_group)
        fields = {
            "title": "Invented page Source",
            "source_type": "other",
            "citation": "Fictional page citation",
            "observed_available_at": datetime(2026, 9, 1, tzinfo=UTC),
            "authors": None,
            "publisher": None,
            "published_at": None,
            "canonical_url": None,
            "rights_note": None,
        }
        create_source(source_id=self.source_id, content=self.v1, fields=fields, actor="page-editor", idempotency_key="page-create", request_path="/api/v1/sources")
        correct_source(source_id=self.source_id, content=self.v2, fields=fields, actor="page-editor", expected_latest_version=1, correction_reason="Correct invented page bytes.", idempotency_key="page-correct", request_path=f"/api/v1/sources/{self.source_id}/corrections")
    def client_as_viewer(self):
        token = base64.b64encode(b"page-viewer:invented-page-pass").decode()
        client = Client(); client.defaults["HTTP_AUTHORIZATION"] = f"Basic {token}"; return client
    def test_founder_page_matches_history_and_manifest_metadata(self):
        response = self.client_as_viewer().get(f"/sources/{self.source_id}/history")
        manifest = SourceManifest.objects.get(source__source_id=self.source_id, through_version=2)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.source_id)
        self.assertContains(response, "27")
        self.assertContains(response, "38")
        self.assertContains(response, "42fff28d6c54902a3c90843c457664df5ce9f803fa8ccb9934d2bb3741481c86")
        self.assertContains(response, "c16ad70788fce3ea9a392d0a9526c92bb9df47626c11c4c3c7f143dac38e4048")
        self.assertContains(response, manifest.manifest_sha256)
        self.assertContains(response, f"/api/v1/sources/{self.source_id}/manifest")
        self.assertNotContains(response, self.v1.decode())
        self.assertNotContains(response, self.v2.decode())
    def test_anonymous_page_is_a_generic_denial(self):
        existing = Client().get(f"/sources/{self.source_id}/history")
        missing = Client().get("/sources/no-such-source/history")
        self.assertEqual(existing.status_code, 401)
        self.assertEqual(missing.status_code, 401)
        self.assertEqual(existing.content, missing.content)
    def test_manifest_download_matches_stored_bytes(self):
        response = self.client_as_viewer().get(f"/api/v1/sources/{self.source_id}/manifest")
        manifest = SourceManifest.objects.get(source__source_id=self.source_id, through_version=2)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, bytes(manifest.manifest_bytes))
        self.assertEqual(response.headers["X-Manifest-SHA256"], manifest.manifest_sha256)
