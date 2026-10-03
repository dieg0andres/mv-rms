import base64
import json
from datetime import UTC, datetime

from django.contrib.auth.models import Group, User
from django.test import Client, TransactionTestCase

from rms.models import Idea, SourceVersion
from rms.services import create_idea, create_source, correct_idea, correct_source


class RmsSiFrontendPageTests(TransactionTestCase):
    source_id = "fictional-integrated-source"
    source_bytes = b"invented integration Source bytes"
    contribution = "The exact fictional v1 publication claim contributes context."

    def setUp(self):
        editor_group, _ = Group.objects.get_or_create(name="editor")
        viewer_group, _ = Group.objects.get_or_create(name="founder_viewer")
        self.editor = User.objects.create_user("ui-editor", password="invented-editor-pass")
        self.editor.groups.add(editor_group)
        self.viewer = User.objects.create_user("ui-viewer", password="invented-viewer-pass")
        self.viewer.groups.add(viewer_group)
        self.other = User.objects.create_user("ui-other", password="invented-other-pass")

        self.source_fields_v1 = {
            "title": "Invented integration Source",
            "source_type": "working_paper",
            "citation": "Fictional Author (2026), invented citation",
            "observed_available_at": datetime(2026, 9, 1, 15, tzinfo=UTC),
            "authors": ["Fictional Author"],
            "publisher": "Invented Publisher",
            "published_at": datetime(2026, 8, 31, 12, tzinfo=UTC),
            "canonical_url": "https://example.invalid/invented-source",
            "rights_note": "Fictional content for local verification only.",
        }
        create_source(
            source_id=self.source_id,
            content=self.source_bytes,
            fields=self.source_fields_v1,
            actor="ui-editor",
            idempotency_key="ui-source-create",
            request_path="/api/v1/sources",
        )
        self.source_v1 = SourceVersion.objects.get(source__source_id=self.source_id, version=1)
        self.idea_fields_v1 = {
            "title": "Invented integration Idea",
            "mechanism": "A fictional mechanism for UI verification.",
            "testable_claim": "A fictional claim exists solely for integration verification.",
            "falsification": "Reject the fictional claim if its invented condition fails.",
            "eligible_market": "equities",
            "workflow_status": "draft",
            "rejection_reason": None,
        }
        idea_response = create_idea(
            fields=self.idea_fields_v1,
            contributions=[
                {
                    "source_version_id": self.source_v1.source_version_id,
                    "contribution": self.contribution,
                }
            ],
            actor="ui-editor",
            idempotency_key="ui-idea-create",
            request_path="/api/v1/ideas",
        )
        self.idea_id = json.loads(idea_response.body)["idea_id"]

        source_fields_v2 = {
            **self.source_fields_v1,
            "published_at": datetime(2026, 9, 1, 12, tzinfo=UTC),
        }
        correct_source(
            source_id=self.source_id,
            content=None,
            fields=source_fields_v2,
            actor="ui-editor",
            expected_latest_version=1,
            correction_reason="Correct the fictional publication timestamp.",
            idempotency_key="ui-source-correct",
            request_path=f"/api/v1/sources/{self.source_id}/corrections",
        )
        self.source_v2 = SourceVersion.objects.get(source__source_id=self.source_id, version=2)
        correct_idea(
            idea_id=self.idea_id,
            fields={
                **self.idea_fields_v1,
                "testable_claim": "A clarified fictional claim exists solely for verification.",
            },
            contributions=[
                {
                    "source_version_id": self.source_v1.source_version_id,
                    "contribution": self.contribution,
                }
            ],
            actor="ui-editor",
            expected_latest_version=1,
            correction_reason="Clarify the fictional testable claim.",
            idempotency_key="ui-idea-correct",
            request_path=f"/api/v1/ideas/{self.idea_id}/corrections",
        )

    @staticmethod
    def _client(username, password):
        token = base64.b64encode(f"{username}:{password}".encode()).decode()
        client = Client()
        client.defaults["HTTP_AUTHORIZATION"] = f"Basic {token}"
        return client

    def test_editor_pages_bind_complete_source_and_idea_corrections(self):
        editor = self._client("ui-editor", "invented-editor-pass")
        self.assertEqual(editor.get("/sources/new").status_code, 200)
        source_correction = editor.get(f"/sources/{self.source_id}/correct")
        self.assertEqual(source_correction.status_code, 200)
        self.assertContains(source_correction, 'name="expected_latest_version" value="2"')
        self.assertContains(source_correction, "Invented integration Source")
        self.assertContains(source_correction, "Working Paper")

        self.assertEqual(editor.get("/ideas/new").status_code, 200)
        idea_correction = editor.get(f"/ideas/{self.idea_id}/correct")
        self.assertEqual(idea_correction.status_code, 200)
        self.assertContains(idea_correction, 'name="expected_latest_version" value="2"')
        self.assertContains(idea_correction, self.source_v1.source_version_id)
        self.assertContains(idea_correction, self.contribution)
        self.assertContains(idea_correction, "Clarify the fictional testable claim.", count=0)

    def test_reader_pages_show_versions_manifests_and_exact_v1_citation_without_bytes(self):
        viewer = self._client("ui-viewer", "invented-viewer-pass")
        source_history = viewer.get(f"/sources/{self.source_id}/history")
        self.assertEqual(source_history.status_code, 200)
        self.assertContains(source_history, self.source_v1.source_version_id)
        self.assertContains(source_history, self.source_v2.source_version_id)
        self.assertContains(source_history, "manifest?through_version=1")
        self.assertContains(source_history, "manifest?through_version=2")
        self.assertNotContains(source_history, self.source_bytes.decode())

        detail = viewer.get(f"/ideas/{self.idea_id}")
        history = viewer.get(f"/ideas/{self.idea_id}/history")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(history.status_code, 200)
        for response in (detail, history):
            self.assertContains(response, self.source_v1.source_version_id)
            self.assertContains(response, self.contribution)
            self.assertNotContains(response, self.source_v2.source_version_id)
            self.assertNotContains(response, self.source_bytes.decode())
        idea = Idea.objects.get(idea_id=self.idea_id)
        for version in idea.versions.order_by("version"):
            self.assertContains(history, version.idea_version_id)

    def test_editor_viewer_other_and_anonymous_boundaries_are_server_enforced(self):
        editor = self._client("ui-editor", "invented-editor-pass")
        viewer = self._client("ui-viewer", "invented-viewer-pass")
        other = self._client("ui-other", "invented-other-pass")
        self.assertEqual(editor.get(f"/ideas/{self.idea_id}").status_code, 200)
        self.assertEqual(editor.get(f"/sources/{self.source_id}/history").status_code, 200)
        self.assertEqual(viewer.get("/sources/new").status_code, 403)
        self.assertEqual(viewer.get(f"/ideas/{self.idea_id}/correct").status_code, 403)
        self.assertEqual(other.get(f"/ideas/{self.idea_id}").status_code, 403)
        self.assertEqual(other.get(f"/sources/{self.source_id}/history").status_code, 403)

        anonymous_existing = Client().get(f"/ideas/{self.idea_id}")
        anonymous_missing = Client().get("/ideas/IDE-00000000-0000-4000-8000-000000000000")
        self.assertEqual(anonymous_existing.status_code, 401)
        self.assertEqual(anonymous_existing.content, anonymous_missing.content)

    def test_authenticated_missing_and_invalid_idea_ids_are_generic(self):
        viewer = self._client("ui-viewer", "invented-viewer-pass")
        missing = viewer.get("/ideas/IDE-00000000-0000-4000-8000-000000000000")
        invalid = viewer.get("/ideas/not-an-idea")
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(invalid.status_code, 404)
        self.assertEqual(missing.content, invalid.content)
