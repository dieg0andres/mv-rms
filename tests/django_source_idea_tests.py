import base64
from concurrent.futures import ThreadPoolExecutor

from django.contrib.auth.models import Group, User
from django.db import DatabaseError, close_old_connections, transaction
from django.test import Client, TransactionTestCase

from rms.models import (
    IdempotencyRecord,
    Idea,
    IdeaContribution,
    IdeaVersion,
    Source,
    SourceManifest,
    SourceVersion,
)


class SourceIdeaContractTests(TransactionTestCase):
    source_id = "fictional-contract-source"
    content_v1 = b"fictional source bytes version one"
    content_v2 = b"fictional source bytes version two"

    def setUp(self):
        editor_group = Group.objects.create(name="editor")
        viewer_group = Group.objects.create(name="founder_viewer")
        editor = User.objects.create_user("si-editor", password="fictional-pass")
        editor.groups.add(editor_group)
        viewer = User.objects.create_user("si-viewer", password="fictional-pass")
        viewer.groups.add(viewer_group)

    @staticmethod
    def make_client(username=None):
        client = Client()
        if username:
            token = base64.b64encode(f"{username}:fictional-pass".encode()).decode()
            client.defaults["HTTP_AUTHORIZATION"] = f"Basic {token}"
        return client

    @classmethod
    def source_fields(cls, **changes):
        fields = {
            "title": "Fictional Source One",
            "source_type": "working_paper",
            "citation": "Fictional Author (2026), Fictional Source One.",
            "observed_available_at": "2026-09-01T16:00:00+02:00",
            "authors": ["Fictional Author", "Invented Coauthor"],
            "publisher": "Fictional Publisher",
            "published_at": "2026-08-31T12:00:00-04:00",
            "canonical_url": "https://example.invalid/fictional-source",
            "rights_note": "Invented fixture rights note only.",
        }
        fields.update(changes)
        return fields

    @classmethod
    def source_create_payload(cls, **changes):
        payload = {
            "source_id": cls.source_id,
            "synthetic": True,
            "content_base64": base64.b64encode(cls.content_v1).decode(),
            **cls.source_fields(),
        }
        payload.update(changes)
        return payload

    @classmethod
    def source_correction_payload(cls, **changes):
        payload = {
            "synthetic": True,
            "expected_latest_version": 1,
            "correction_reason": "Correct the fictional publication timestamp.",
            "content_base64": None,
            **cls.source_fields(published_at="2026-09-01T12:00:00Z"),
        }
        payload.update(changes)
        return payload

    @staticmethod
    def idea_payload(source_version_id, **changes):
        payload = {
            "synthetic": True,
            "title": "Fictional Idea",
            "mechanism": "An invented mechanism for contract testing.",
            "testable_claim": "The fictional observation changes in a testable way.",
            "falsification": "The invented observation does not change.",
            "eligible_market": "equities",
            "workflow_status": "draft",
            "rejection_reason": None,
            "contributions": [
                {
                    "source_version_id": source_version_id,
                    "contribution": "Exact fictional evidence contribution.",
                }
            ],
        }
        payload.update(changes)
        return payload

    def create_source(self, key="source-create", **changes):
        return self.make_client("si-editor").post(
            "/api/v1/sources",
            data=self.source_create_payload(**changes),
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY=key,
        )

    def correct_source(self, key="source-correct", **changes):
        return self.make_client("si-editor").post(
            f"/api/v1/sources/{self.source_id}/corrections",
            data=self.source_correction_payload(**changes),
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY=key,
        )

    def create_idea(self, source_version_id, key="idea-create", **changes):
        return self.make_client("si-editor").post(
            "/api/v1/ideas",
            data=self.idea_payload(source_version_id, **changes),
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY=key,
        )

    def test_source_metadata_timezones_correction_and_historical_manifest(self):
        created = self.create_source()
        self.assertEqual(created.status_code, 201)
        created_json = created.json()
        self.assertEqual(
            created_json["latest"]["observed_available_at"],
            "2026-09-01T14:00:00.000000Z",
        )
        self.assertEqual(
            created_json["latest"]["published_at"],
            "2026-08-31T16:00:00.000000Z",
        )
        v1_id = created_json["latest_source_version_id"]
        manifest_v1 = self.make_client("si-viewer").get(
            f"/api/v1/sources/{self.source_id}/manifest?through_version=1"
        )

        corrected = self.correct_source()
        self.assertEqual(corrected.status_code, 201)
        source = Source.objects.get(source_id=self.source_id)
        self.assertEqual(bytes(source.versions.get(version=1).content), self.content_v1)
        self.assertEqual(bytes(source.versions.get(version=2).content), self.content_v1)
        history = self.make_client("si-viewer").get(
            f"/api/v1/sources/{self.source_id}/versions"
        ).json()["versions"]
        self.assertEqual(history[1]["corrects_source_version_id"], v1_id)
        self.assertEqual(history[1]["changed_fields"], ["published_at"])
        self.assertEqual(history[1]["correction_reason"], self.source_correction_payload()["correction_reason"])
        after = self.make_client("si-viewer").get(
            f"/api/v1/sources/{self.source_id}/manifest?through_version=1"
        )
        self.assertEqual(after.content, manifest_v1.content)
        self.assertEqual(
            after.headers["X-Manifest-SHA256"],
            manifest_v1.headers["X-Manifest-SHA256"],
        )
        self.assertEqual(SourceManifest.objects.count(), 2)

    def test_idea_binds_exact_source_version_across_source_correction_without_bytes(self):
        source = self.create_source().json()
        v1_id = source["latest_source_version_id"]
        idea_created = self.create_idea(v1_id)
        self.assertEqual(idea_created.status_code, 201)
        idea = idea_created.json()
        idea_id = idea["idea_id"]
        contribution = idea["latest"]["contributions"][0]
        self.assertEqual(contribution["source_version_id"], v1_id)
        self.assertEqual(contribution["source_summary"]["title"], "Fictional Source One")

        correction = self.correct_source(
            content_base64=base64.b64encode(self.content_v2).decode(),
            title="Fictional Source Two",
        )
        self.assertEqual(correction.status_code, 201)
        reread = self.make_client("si-viewer").get(f"/api/v1/ideas/{idea_id}").json()
        preserved = reread["latest"]["contributions"][0]
        self.assertEqual(preserved["source_version_id"], v1_id)
        self.assertEqual(preserved["source_summary"]["title"], "Fictional Source One")
        rendered = str(reread)
        self.assertNotIn("content_base64", rendered)
        self.assertNotIn(self.content_v1.decode(), rendered)
        self.assertNotIn(self.content_v2.decode(), rendered)

    def test_idea_correction_replay_stale_rollback_and_global_key_conflict(self):
        source = self.create_source().json()
        source_version_id = source["latest_source_version_id"]
        first = self.create_idea(source_version_id)
        replay = self.create_idea(source_version_id)
        self.assertEqual(replay.status_code, 201)
        self.assertEqual(replay.content, first.content)
        self.assertEqual(Idea.objects.count(), 1)
        self.assertEqual(IdeaVersion.objects.count(), 1)
        self.assertEqual(IdeaContribution.objects.count(), 1)

        idea_id = first.json()["idea_id"]
        first_idea_version_id = first.json()["latest_idea_version_id"]
        corrected_payload = self.idea_payload(
            source_version_id,
            title="Corrected Fictional Idea",
            workflow_status="accepted",
        )
        corrected_payload.update(
            expected_latest_version=1,
            correction_reason="Correct the fictional workflow intake status.",
        )
        corrected = self.make_client("si-editor").post(
            f"/api/v1/ideas/{idea_id}/corrections",
            data=corrected_payload,
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY="idea-correct",
        )
        self.assertEqual(corrected.status_code, 201)
        self.assertEqual(
            corrected.json()["latest"]["changed_fields"],
            ["title", "workflow_status"],
        )
        self.assertEqual(
            corrected.json()["latest"]["corrects_idea_version_id"],
            first_idea_version_id,
        )

        stale_payload = dict(corrected_payload)
        stale_payload["title"] = "Stale Fictional Idea"
        stale = self.make_client("si-editor").post(
            f"/api/v1/ideas/{idea_id}/corrections",
            data=stale_payload,
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY="idea-stale",
        )
        self.assertEqual(stale.status_code, 409)
        self.assertEqual(stale.json()["error"]["code"], "stale_correction")
        self.assertEqual(IdeaVersion.objects.count(), 2)
        self.assertEqual(IdeaContribution.objects.count(), 2)
        self.assertFalse(IdempotencyRecord.objects.filter(key="idea-stale").exists())

        conflict = self.create_idea(source_version_id, key="source-create")
        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(conflict.json()["error"]["code"], "idempotency_conflict")
        self.assertEqual(Idea.objects.count(), 1)

        version = IdeaVersion.objects.get(version=2)
        edge = IdeaContribution.objects.get(idea_version=version)
        with self.assertRaises(DatabaseError), transaction.atomic():
            IdeaVersion.objects.filter(pk=version.pk).update(title="rewrite")
        with self.assertRaises(DatabaseError), transaction.atomic():
            IdeaContribution.objects.filter(pk=edge.pk).delete()

    def test_validation_and_authorization_fail_closed_without_partial_rows(self):
        bad_times = (
            "2026-09-01T14:00:00",
            "2026-09-01",
            "2026-09-01T14:00:00 UTC",
            "2026-09-01T14:00:60Z",
        )
        for index, timestamp in enumerate(bad_times):
            response = self.create_source(
                key=f"bad-time-{index}", observed_available_at=timestamp
            )
            self.assertEqual(response.status_code, 400)
        invalid_fields = (
            {"title": " trailing title "},
            {"authors": ["Duplicate Author", "Duplicate Author"]},
            {"canonical_url": "https://user:secret@example.invalid/source"},
            {"source_type": "unsupported"},
            {"rights_note": "bad\x00control"},
        )
        for index, changes in enumerate(invalid_fields):
            response = self.create_source(key=f"bad-field-{index}", **changes)
            self.assertEqual(response.status_code, 400)
        self.assertEqual(Source.objects.count(), 0)
        self.assertEqual(IdempotencyRecord.objects.count(), 0)

        source = self.create_source().json()
        source_version_id = source["latest_source_version_id"]
        invalid = self.create_idea(
            source_version_id,
            key="invalid-rejected",
            workflow_status="rejected",
            rejection_reason=None,
        )
        duplicate = self.create_idea(
            source_version_id,
            key="duplicate",
            contributions=[
                {
                    "source_version_id": source_version_id,
                    "contribution": "duplicate fictional contribution",
                },
                {
                    "source_version_id": source_version_id,
                    "contribution": "duplicate fictional contribution",
                },
            ],
        )
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(duplicate.status_code, 400)
        self.assertEqual(Idea.objects.count(), 0)

        viewer_write = self.make_client("si-viewer").post(
            "/api/v1/ideas/not-a-real-id/corrections",
            data={},
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY="viewer-denied",
        )
        self.assertEqual(viewer_write.status_code, 403)
        anonymous_existing = self.make_client().get(f"/api/v1/sources/{self.source_id}")
        anonymous_missing = self.make_client().get("/api/v1/sources/missing-source")
        self.assertEqual(anonymous_existing.status_code, 401)
        self.assertEqual(anonymous_missing.status_code, 401)
        self.assertEqual(
            anonymous_existing.json()["error"]["message"],
            anonymous_missing.json()["error"]["message"],
        )
        invalid_read = self.make_client("si-viewer").get("/api/v1/ideas/not-an-id")
        missing_read = self.make_client("si-viewer").get(
            "/api/v1/ideas/IDE-00000000-0000-4000-8000-000000000000"
        )
        self.assertEqual(invalid_read.status_code, 404)
        self.assertEqual(missing_read.status_code, 404)
        self.assertEqual(
            invalid_read.json()["error"]["message"],
            missing_read.json()["error"]["message"],
        )

    def test_two_concurrent_idea_corrections_accept_exactly_one(self):
        source_version_id = self.create_source().json()["latest_source_version_id"]
        idea_id = self.create_idea(source_version_id).json()["idea_id"]

        def submit(index):
            close_old_connections()
            try:
                payload = self.idea_payload(
                    source_version_id, title=f"Concurrent Fictional Idea {index}"
                )
                payload.update(
                    expected_latest_version=1,
                    correction_reason=f"Concurrent fictional correction {index}.",
                )
                response = self.make_client("si-editor").post(
                    f"/api/v1/ideas/{idea_id}/corrections",
                    data=payload,
                    content_type="application/json",
                    HTTP_IDEMPOTENCY_KEY=f"idea-concurrent-{index}",
                )
                return response.status_code
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = sorted(pool.map(submit, (1, 2)))
        self.assertEqual(statuses, [201, 409])
        self.assertEqual(IdeaVersion.objects.count(), 2)
        self.assertEqual(IdeaContribution.objects.count(), 2)
