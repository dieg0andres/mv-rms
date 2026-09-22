import base64
import json
from concurrent.futures import ThreadPoolExecutor

from django.contrib.auth.models import Group, User
from django.db import DatabaseError, close_old_connections, transaction
from django.test import Client, TransactionTestCase

from rms.models import IdempotencyRecord, Source, SourceManifest, SourceVersion


SOURCE_ID = "synthetic-api-source-001"
V1 = b"invented API Source version one"
V2 = b"invented API Source version two correction"


def encoded(content: bytes) -> str:
    return base64.b64encode(content).decode("ascii")


class SourceApiTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        super().setUp()
        editor_group, _ = Group.objects.get_or_create(name="editor")
        viewer_group, _ = Group.objects.get_or_create(name="founder_viewer")
        self.editor = User.objects.create_user("editor", password="invented-editor-pass")
        self.editor.groups.add(editor_group)
        self.viewer = User.objects.create_user("viewer", password="invented-viewer-pass")
        self.viewer.groups.add(viewer_group)

    def editor_client(self) -> Client:
        client = Client()
        client.defaults["HTTP_AUTHORIZATION"] = self.basic("editor", "invented-editor-pass")
        return client

    def viewer_client(self) -> Client:
        client = Client()
        client.defaults["HTTP_AUTHORIZATION"] = self.basic("viewer", "invented-viewer-pass")
        return client

    @staticmethod
    def basic(username: str, password: str) -> str:
        token = base64.b64encode(f"{username}:{password}".encode()).decode()
        return f"Basic {token}"

    def create(self, *, key: str = "create-1", source_id: str = SOURCE_ID):
        return self.editor_client().post(
            "/api/v1/sources",
            data={
                "source_id": source_id,
                "synthetic": True,
                "content_base64": encoded(V1),
            },
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY=key,
        )

    def correct(self, *, key: str = "correct-1", expected: int = 1, content=V2):
        return self.editor_client().post(
            f"/api/v1/sources/{SOURCE_ID}/corrections",
            data={
                "synthetic": True,
                "expected_latest_version": expected,
                "content_base64": encoded(content),
            },
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY=key,
        )

    def test_create_correct_detail_history_and_manifest_preserve_original(self):
        created = self.create()
        corrected = self.correct()

        self.assertEqual(created.status_code, 201)
        self.assertEqual(corrected.status_code, 201)
        source = Source.objects.get(source_id=SOURCE_ID)
        self.assertEqual(source.latest_version, 2)
        self.assertEqual(bytes(source.versions.get(version=1).content), V1)
        self.assertEqual(bytes(source.versions.get(version=2).content), V2)

        detail = self.viewer_client().get(f"/api/v1/sources/{SOURCE_ID}")
        history = self.viewer_client().get(f"/api/v1/sources/{SOURCE_ID}/versions")
        manifest = self.viewer_client().get(f"/api/v1/sources/{SOURCE_ID}/manifest")
        self.assertEqual(detail.json()["latest_version"], 2)
        self.assertEqual([item["version"] for item in history.json()["versions"]], [1, 2])
        self.assertEqual([item["corrects_version"] for item in history.json()["versions"]], [None, 1])
        self.assertEqual(manifest.status_code, 200)
        self.assertEqual(manifest.content, bytes(source.manifests.get(through_version=2).manifest_bytes))
        self.assertNotIn(V1, manifest.content)
        self.assertNotIn(V2, manifest.content)
        self.assertEqual(manifest.headers["X-Manifest-SHA256"], source.manifests.get(through_version=2).manifest_sha256)

    def test_same_key_same_canonical_request_replays_byte_identical_response(self):
        first = self.create()
        replay = self.create()

        self.assertEqual(replay.status_code, 201)
        self.assertEqual(replay.content, first.content)
        self.assertEqual(Source.objects.count(), 1)
        self.assertEqual(SourceVersion.objects.count(), 1)
        self.assertEqual(SourceManifest.objects.count(), 1)
        self.assertEqual(IdempotencyRecord.objects.count(), 1)

    def test_same_key_different_request_conflicts_without_partial_write(self):
        self.create()
        conflict = self.editor_client().post(
            "/api/v1/sources",
            data={
                "source_id": "different-source",
                "synthetic": True,
                "content_base64": encoded(V1),
            },
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY="create-1",
        )

        self.assertEqual(conflict.status_code, 409)
        self.assertEqual(Source.objects.count(), 1)
        self.assertEqual(IdempotencyRecord.objects.count(), 1)

    def test_stale_correction_has_no_version_manifest_or_idempotency_record(self):
        self.create()
        stale = self.correct(key="stale", expected=2)

        self.assertEqual(stale.status_code, 409)
        self.assertEqual(SourceVersion.objects.count(), 1)
        self.assertEqual(SourceManifest.objects.count(), 1)
        self.assertFalse(IdempotencyRecord.objects.filter(key="stale").exists())

    def test_founder_viewer_is_read_only_and_anonymous_is_denied(self):
        self.create()
        viewer_write = self.viewer_client().post(
            f"/api/v1/sources/{SOURCE_ID}/corrections",
            data={
                "synthetic": True,
                "expected_latest_version": 1,
                "content_base64": encoded(V2),
            },
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY="viewer-write",
        )
        existing = Client().get(f"/api/v1/sources/{SOURCE_ID}")
        missing = Client().get("/api/v1/sources/does-not-exist")

        self.assertEqual(viewer_write.status_code, 403)
        self.assertEqual(existing.status_code, 401)
        self.assertEqual(missing.status_code, 401)
        self.assertEqual(existing.json()["error"]["code"], "authentication_required")
        self.assertEqual(missing.json()["error"]["code"], "authentication_required")
        self.assertEqual(SourceVersion.objects.count(), 1)

    def test_validation_rejects_unknown_fields_non_synthetic_and_bad_base64(self):
        invalid_payloads = [
            {"source_id": SOURCE_ID, "synthetic": False, "content_base64": encoded(V1)},
            {"source_id": SOURCE_ID, "synthetic": True, "content_base64": "not base64"},
            {"source_id": SOURCE_ID, "synthetic": True, "content_base64": encoded(V1), "extra": 1},
        ]
        for index, payload in enumerate(invalid_payloads):
            with self.subTest(payload=payload):
                response = self.editor_client().post(
                    "/api/v1/sources",
                    data=payload,
                    content_type="application/json",
                    HTTP_IDEMPOTENCY_KEY=f"bad-{index}",
                )
                self.assertEqual(response.status_code, 400)
        self.assertEqual(Source.objects.count(), 0)
        self.assertEqual(IdempotencyRecord.objects.count(), 0)

    def test_database_rejects_version_and_manifest_mutation(self):
        self.create()
        version = SourceVersion.objects.get()
        manifest = SourceManifest.objects.get()

        with self.assertRaises(DatabaseError), transaction.atomic():
            SourceVersion.objects.filter(pk=version.pk).update(content=b"rewritten")
        with self.assertRaises(DatabaseError), transaction.atomic():
            SourceManifest.objects.filter(pk=manifest.pk).delete()
        self.assertEqual(bytes(SourceVersion.objects.get().content), V1)

    def test_database_rejects_changed_manifest_bytes(self):
        self.create()
        source = Source.objects.get()
        with self.assertRaises(DatabaseError), transaction.atomic():
            SourceManifest.objects.create(
                source=source,
                through_version=1,
                schema_version=1,
                version_count=1,
                manifest_bytes=b'{"schema_version":1,"versions":[]}',
            )
        self.assertEqual(SourceManifest.objects.count(), 1)

    def test_two_concurrent_corrections_accept_exactly_one(self):
        self.create()

        def submit(index: int) -> int:
            close_old_connections()
            try:
                response = self.correct(
                    key=f"concurrent-{index}",
                    content=f"invented concurrent correction {index}".encode(),
                )
                return response.status_code
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = sorted(pool.map(submit, (1, 2)))

        self.assertEqual(statuses, [201, 409])
        self.assertEqual(SourceVersion.objects.count(), 2)
        self.assertEqual(SourceManifest.objects.count(), 2)
        self.assertEqual(IdempotencyRecord.objects.count(), 2)
        self.assertEqual(Source.objects.get().latest_version, 2)

    def test_readiness_requires_authentication_and_reports_migration_head(self):
        self.assertEqual(Client().get("/api/v1/readiness").status_code, 401)
        self.assertEqual(
            self.viewer_client().get("/api/v1/readiness").json(), {"status": "ready"}
        )
