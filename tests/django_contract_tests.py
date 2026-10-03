import base64

from django.contrib.auth.models import Group, User
from django.db import DatabaseError, transaction
from django.test import Client, TransactionTestCase

from rms.models import IdempotencyRecord, Source, SourceVersion


class FrozenRouteAndDatabaseContractTests(TransactionTestCase):
    def setUp(self):
        editor_group = Group.objects.create(name="editor")
        viewer_group = Group.objects.create(name="founder_viewer")
        editor = User.objects.create_user("contract-editor", password="invented-pass")
        editor.groups.add(editor_group)
        viewer = User.objects.create_user("contract-viewer", password="invented-pass")
        viewer.groups.add(viewer_group)
        self.editor = self._client("contract-editor")
        self.viewer = self._client("contract-viewer")

    @staticmethod
    def _client(username: str) -> Client:
        client = Client()
        token = base64.b64encode(f"{username}:invented-pass".encode()).decode()
        client.defaults["HTTP_AUTHORIZATION"] = f"Basic {token}"
        return client

    def _create(self):
        return self.editor.post(
            "/api/v1/sources",
            data={
                "source_id": "contract-source",
                "synthetic": True,
                "content_base64": base64.b64encode(b"invented contract bytes").decode(),
                "title": "Invented contract Source",
                "source_type": "other",
                "citation": "Fictional contract citation",
                "observed_available_at": "2026-09-22T00:00:00Z",
                "authors": None,
                "publisher": None,
                "published_at": None,
                "canonical_url": None,
                "rights_note": None,
            },
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY="contract-create",
        )

    def test_success_and_error_shapes_and_manifest_headers_are_frozen(self):
        created = self._create()
        missing = self.viewer.get("/api/v1/sources/missing-source")
        manifest = self.viewer.get("/api/v1/sources/contract-source/manifest")

        self.assertEqual(
            set(created.json()),
            {"source_id", "synthetic", "latest_version", "latest_source_version_id", "created_at", "latest"},
        )
        self.assertEqual(
            set(created.json()["latest"]),
            {
                "source_version_id",
                "version",
                "corrects_source_version_id",
                "corrects_version",
                "correction_reason",
                "changed_fields",
                "title",
                "source_type",
                "citation",
                "observed_available_at",
                "authors",
                "publisher",
                "published_at",
                "canonical_url",
                "rights_note",
                "synthetic",
                "byte_length",
                "content_sha256",
                "created_at",
                "created_by",
            },
        )
        self.assertEqual(missing.status_code, 404)
        self.assertEqual(set(missing.json()), {"error"})
        self.assertEqual(
            set(missing.json()["error"]), {"code", "message", "request_id"}
        )
        self.assertEqual(
            manifest.headers["Content-Disposition"],
            'attachment; filename="contract-source-manifest-v1.json"',
        )
        self.assertRegex(manifest.headers["X-Manifest-SHA256"], r"^[0-9a-f]{64}$")

    def test_missing_idempotency_key_is_validation_error_without_write(self):
        response = self.editor.post(
            "/api/v1/sources",
            data={
                "source_id": "contract-source",
                "synthetic": True,
                "content_base64": base64.b64encode(b"invented").decode(),
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error"]["code"], "validation_error")
        self.assertEqual(Source.objects.count(), 0)

    def test_unsupported_safe_method_is_405_after_auth_but_write_is_403(self):
        self.assertEqual(self.viewer.get("/api/v1/sources").status_code, 405)
        self.assertEqual(
            self.viewer.put(
                "/api/v1/sources",
                data={},
                content_type="application/json",
            ).status_code,
            403,
        )

    def test_database_rejects_skipped_version_source_change_and_idempotency_change(self):
        self._create()
        source = Source.objects.get()
        idempotency = IdempotencyRecord.objects.get()
        with self.assertRaises(DatabaseError), transaction.atomic():
            SourceVersion.objects.create(
                source=source,
                version=3,
                corrects_version=2,
                content=b"invented skipped bytes",
                synthetic=True,
            )
        with self.assertRaises(DatabaseError), transaction.atomic():
            Source.objects.filter(pk=source.pk).update(source_id="rewritten")
        with self.assertRaises(DatabaseError), transaction.atomic():
            IdempotencyRecord.objects.filter(pk=idempotency.pk).update(
                response_status=200
            )
        source.refresh_from_db()
        self.assertEqual(source.source_id, "contract-source")
        self.assertEqual(source.latest_version, 1)
        self.assertEqual(SourceVersion.objects.count(), 1)
