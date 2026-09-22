"""Independent Test-owned RMS-SI-1.0 boundary and denial checks.

These checks supplement, rather than replace, the builder-authored focused suites.
All values are invented and all persistence is Django's isolated PostgreSQL test DB.
"""

from unittest.mock import patch
import base64
import copy
import hashlib
import json

from django.contrib.auth.models import Group, User
from django.db import DatabaseError, transaction
from django.test import Client, TransactionTestCase

from rms.models import (
    ELIGIBLE_MARKETS,
    SOURCE_TYPES,
    WORKFLOW_STATUSES,
    IdempotencyRecord,
    Idea,
    IdeaContribution,
    IdeaVersion,
    Source,
    SourceManifest,
    SourceVersion,
)


class IndependentRmsSiVerificationTests(TransactionTestCase):
    password = "invented-independent-pass"

    def setUp(self):
        editor_group = Group.objects.create(name="editor")
        viewer_group = Group.objects.create(name="founder_viewer")
        editor = User.objects.create_user("independent-editor", password=self.password)
        editor.groups.add(editor_group)
        viewer = User.objects.create_user("independent-viewer", password=self.password)
        viewer.groups.add(viewer_group)
        User.objects.create_user("independent-other", password=self.password)

    def api_client(self, principal=None):
        client = Client()
        if principal:
            token = base64.b64encode(f"independent-{principal}:{self.password}".encode()).decode()
            client.defaults["HTTP_AUTHORIZATION"] = f"Basic {token}"
        return client

    @staticmethod
    def source_payload(source_id="fixture.source.increment1", **changes):
        payload = {
            "source_id": source_id,
            "synthetic": True,
            "content_base64": base64.b64encode(
                b"invented increment-one source bytes v1"
            ).decode(),
            "title": "Fictional volatility note",
            "source_type": "working_paper",
            "citation": "Example, A. (2026). Fictional volatility note.",
            "observed_available_at": "2026-09-01T14:00:00Z",
            "authors": ["Ada Fiction", "Ben Example"],
            "publisher": "Invented Research Press",
            "published_at": "2026-08-31T12:00:00-04:00",
            "canonical_url": "https://example.invalid/fictional-volatility-note",
            "rights_note": "Synthetic fixture; no external rights claim.",
        }
        payload.update(changes)
        return payload

    @staticmethod
    def idea_payload(source_version_id, **changes):
        payload = {
            "synthetic": True,
            "title": "Fictional availability-to-volatility idea",
            "mechanism": "An invented availability lag may alter a fictional response.",
            "testable_claim": "The invented response is larger after availability.",
            "falsification": "No larger invented response falsifies the claim.",
            "eligible_market": "equities",
            "workflow_status": "draft",
            "rejection_reason": None,
            "contributions": [
                {
                    "source_version_id": source_version_id,
                    "contribution": "The exact fictional v1 motivates the invented mechanism.",
                }
            ],
        }
        payload.update(changes)
        return payload

    def post_source(self, payload, key):
        return self.api_client("editor").post(
            "/api/v1/sources",
            data=payload,
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY=key,
        )

    def create_source(self, source_id="fixture.source.increment1", key="rms-si-1:source"):
        response = self.post_source(self.source_payload(source_id), key)
        self.assertEqual(response.status_code, 201, response.content)
        return response

    def post_idea(self, payload, key):
        return self.api_client("editor").post(
            "/api/v1/ideas",
            data=payload,
            content_type="application/json",
            HTTP_IDEMPOTENCY_KEY=key,
        )

    def assert_generic_validation(self, response):
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["error"]["message"], "The request is invalid."
        )

    def test_all_source_enums_nulls_and_boundary_cardinalities(self):
        for index, source_type in enumerate(SOURCE_TYPES):
            response = self.post_source(
                self.source_payload(
                    f"fixture.enum.{index}",
                    source_type=source_type,
                    authors=None,
                    publisher=None,
                    published_at=None,
                    canonical_url=None,
                    rights_note=None,
                ),
                f"rms-si-1:enum:{index}",
            )
            self.assertEqual(response.status_code, 201, response.content)
            for field in (
                "authors",
                "publisher",
                "published_at",
                "canonical_url",
                "rights_note",
            ):
                self.assertIsNone(response.json()["latest"][field])

        boundary = self.post_source(
            self.source_payload(
                "fixture.boundaries",
                title="t" * 500,
                citation="c" * 2000,
                authors=[f"Author {number:03d}" for number in range(100)],
                publisher="p" * 500,
                rights_note="r" * 4000,
            ),
            "rms-si-1:source-boundary",
        )
        self.assertEqual(boundary.status_code, 201, boundary.content)
        self.assertEqual(len(boundary.json()["latest"]["authors"]), 100)

        before = (Source.objects.count(), IdempotencyRecord.objects.count())
        invalid_changes = (
            {"source_type": "unlisted"},
            {"title": ""},
            {"title": " "},
            {"title": " untrimmed"},
            {"title": "t" * 501},
            {"citation": "bad\x00value"},
            {"citation": "bad\x01value"},
            {"authors": [f"Author {number:03d}" for number in range(101)]},
            {"authors": ["duplicate", "duplicate"]},
        )
        for index, changes in enumerate(invalid_changes):
            response = self.post_source(
                self.source_payload(f"fixture.invalid.{index}", **changes),
                f"rms-si-1:invalid:{index}",
            )
            self.assert_generic_validation(response)
        self.assertEqual(
            (Source.objects.count(), IdempotencyRecord.objects.count()), before
        )

    def test_timestamps_urls_base64_unknown_and_missing_fields(self):
        valid_times = (
            ("2026-09-01T14:00:00Z", "2026-09-01T14:00:00.000000Z"),
            ("2026-09-01T16:00:00+02:00", "2026-09-01T14:00:00.000000Z"),
            ("2026-09-01T09:00:00-05:00", "2026-09-01T14:00:00.000000Z"),
        )
        for index, (submitted, emitted) in enumerate(valid_times):
            response = self.post_source(
                self.source_payload(
                    f"fixture.time.{index}",
                    observed_available_at=submitted,
                    published_at="2026-09-02T00:00:00Z",
                ),
                f"rms-si-1:time:{index}",
            )
            self.assertEqual(response.status_code, 201, response.content)
            self.assertEqual(response.json()["latest"]["observed_available_at"], emitted)

        invalid_changes = (
            {"observed_available_at": "2026-09-01T14:00:00"},
            {"observed_available_at": "2026-09-01"},
            {"observed_available_at": "2026-09-01T14:00:00 UTC"},
            {"observed_available_at": "2026-09-01T14:00:60Z"},
            {"canonical_url": "ftp://example.invalid/source"},
            {"canonical_url": "https://user:secret@example.invalid/source"},
            {"canonical_url": "https://example.invalid/" + "x" * 2030},
            {"content_base64": "aW52ZW50ZWQ"},
        )
        for index, changes in enumerate(invalid_changes):
            response = self.post_source(
                self.source_payload(f"fixture.bad-wire.{index}", **changes),
                f"rms-si-1:bad-wire:{index}",
            )
            self.assert_generic_validation(response)

        unknown = self.source_payload("fixture.unknown", extra="forbidden")
        missing = self.source_payload("fixture.missing")
        del missing["title"]
        for index, payload in enumerate((unknown, missing)):
            self.assert_generic_validation(
                self.post_source(payload, f"rms-si-1:shape:{index}")
            )

    def test_idea_enums_rejection_matrix_and_contribution_limits(self):
        source = self.create_source().json()
        source_version_id = source["latest_source_version_id"]
        index = 0
        for market in ELIGIBLE_MARKETS:
            for status in WORKFLOW_STATUSES:
                rejection_reason = "Invented rejection reason." if status == "rejected" else None
                response = self.post_idea(
                    self.idea_payload(
                        source_version_id,
                        title=f"Fictional matrix Idea {index}",
                        eligible_market=market,
                        workflow_status=status,
                        rejection_reason=rejection_reason,
                    ),
                    f"rms-si-1:idea-matrix:{index}",
                )
                self.assertEqual(response.status_code, 201, response.content)
                self.assertEqual(response.json()["latest"]["rejection_reason"], rejection_reason)
                index += 1

        one_hundred = [
            {
                "source_version_id": source_version_id,
                "contribution": f"Distinct fictional contribution {number:03d}.",
            }
            for number in range(100)
        ]
        accepted = self.post_idea(
            self.idea_payload(source_version_id, contributions=one_hundred),
            "rms-si-1:idea-100",
        )
        self.assertEqual(accepted.status_code, 201, accepted.content)
        self.assertEqual(len(accepted.json()["latest"]["contributions"]), 100)

        invalid_payloads = (
            self.idea_payload(
                source_version_id, workflow_status="rejected", rejection_reason=None
            ),
            self.idea_payload(
                source_version_id,
                workflow_status="draft",
                rejection_reason="not allowed",
            ),
            self.idea_payload(source_version_id, contributions=one_hundred + [one_hundred[0]]),
            self.idea_payload(source_version_id, contributions=[]),
            self.idea_payload(
                source_version_id,
                contributions=[one_hundred[0], copy.deepcopy(one_hundred[0])],
            ),
            self.idea_payload(
                "SRCV-00000000-0000-4000-8000-000000000000"
            ),
        )
        counts = (Idea.objects.count(), IdeaVersion.objects.count(), IdeaContribution.objects.count())
        for number, payload in enumerate(invalid_payloads):
            response = self.post_idea(payload, f"rms-si-1:idea-invalid:{number}")
            self.assertIn(response.status_code, (400, 404))
        self.assertEqual(
            (Idea.objects.count(), IdeaVersion.objects.count(), IdeaContribution.objects.count()),
            counts,
        )

    def test_failure_does_not_reserve_key_and_canonical_timestamp_replays(self):
        key = "rms-si-1:failure-then-success"
        invalid = self.source_payload("fixture.failure-key")
        invalid["title"] = ""
        self.assert_generic_validation(self.post_source(invalid, key))
        self.assertFalse(IdempotencyRecord.objects.filter(key=key).exists())
        valid = self.post_source(self.source_payload("fixture.failure-key"), key)
        self.assertEqual(valid.status_code, 201)

        canonical_key = "rms-si-1:canonical-time"
        first_payload = self.source_payload(
            "fixture.canonical-time",
            observed_available_at="2026-09-01T16:00:00+02:00",
        )
        second_payload = self.source_payload(
            "fixture.canonical-time",
            observed_available_at="2026-09-01T14:00:00Z",
        )
        first = self.post_source(first_payload, canonical_key)
        second = self.post_source(second_payload, canonical_key)
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)
        self.assertEqual(first.content, second.content)
        self.assertEqual(Source.objects.filter(source_id="fixture.canonical-time").count(), 1)

    def test_all_role_denials_precede_lookup_and_leave_no_rows(self):
        source = self.create_source().json()
        source_id = source["source_id"]
        source_version_id = source["latest_source_version_id"]
        idea = self.post_idea(
            self.idea_payload(source_version_id), "rms-si-1:role-idea"
        ).json()
        idea_id = idea['idea_id']
        counts = (
            Source.objects.count(),
            SourceVersion.objects.count(),
            Idea.objects.count(),
            IdeaVersion.objects.count(),
            IdeaContribution.objects.count(),
            IdempotencyRecord.objects.count(),
        )

        for principal in ("viewer", "other"):
            for path in (
                "/api/v1/sources/missing-source/corrections",
                "/api/v1/ideas/IDE-00000000-0000-4000-8000-000000000000/corrections",
            ):
                denied = self.api_client(principal).post(
                    path,
                    data={},
                    content_type="application/json",
                    HTTP_IDEMPOTENCY_KEY=f"rms-si-1:denied:{principal}:{path}",
                )
                self.assertEqual(denied.status_code, 403)
                self.assertEqual(denied.json()["error"]["message"], "This operation is not permitted.")

        for path in (
            f"/api/v1/sources/{source_id}",
            "/api/v1/sources/missing-source",
            f"/api/v1/ideas/{idea_id}",
            "/api/v1/ideas/IDE-00000000-0000-4000-8000-000000000000",
        ):
            denied = self.api_client().get(path)
            self.assertEqual(denied.status_code, 401)
            self.assertEqual(denied.json()["error"]["message"], "Authentication is required.")

        self.assertEqual(
            (
                Source.objects.count(),
                SourceVersion.objects.count(),
                Idea.objects.count(),
                IdeaVersion.objects.count(),
                IdeaContribution.objects.count(),
                IdempotencyRecord.objects.count(),
            ),
            counts,
        )

    def test_three_manifests_are_historical_and_content_free(self):
        editor = self.api_client("editor")
        viewer = self.api_client("viewer")
        created = self.create_source().json()
        v1_id = created["latest_source_version_id"]
        saved = {}
        for version in (1, 2, 3):
            if version > 1:
                payload = self.source_payload()
                payload.pop("source_id")
                payload.update(
                    expected_latest_version=version - 1,
                    correction_reason=f"Invented correction {version}.",
                    content_base64=None if version == 2 else base64.b64encode(
                        b"invented increment-one source bytes v3"
                    ).decode(),
                    published_at="2026-08-31T16:30:00Z",
                    title=(
                        "Fictional volatility note"
                        if version == 2
                        else "Fictional volatility note — corrected edition"
                    ),
                )
                response = editor.post(
                    "/api/v1/sources/fixture.source.increment1/corrections",
                    data=payload,
                    content_type="application/json",
                    HTTP_IDEMPOTENCY_KEY=f"rms-si-1:source-correction:{version}",
                )
                self.assertEqual(response.status_code, 201, response.content)
            for historical_version in range(1, version + 1):
                manifest = viewer.get(
                    "/api/v1/sources/fixture.source.increment1/manifest",
                    {"through_version": str(historical_version)},
                )
                self.assertEqual(manifest.status_code, 200)
                self.assertEqual(
                    hashlib.sha256(manifest.content).hexdigest(),
                    manifest.headers["X-Manifest-SHA256"],
                )
                self.assertNotIn(b"invented increment-one source bytes", manifest.content)
                if historical_version in saved:
                    self.assertEqual(saved[historical_version], manifest.content)
                saved[historical_version] = manifest.content

        history = viewer.get(
            "/api/v1/sources/fixture.source.increment1/versions"
        ).json()["versions"]
        self.assertEqual(history[0]["source_version_id"], v1_id)
        self.assertEqual(history[1]["changed_fields"], ["published_at"])
        self.assertEqual(history[2]["changed_fields"], ["content_sha256", "title"])
        self.assertEqual(SourceManifest.objects.count(), 3)

    def test_database_rejects_cross_record_predecessors_and_history_mutation(self):
        first = self.create_source("fixture.db.first", "rms-si-1:db-first").json()
        second = self.create_source("fixture.db.second", "rms-si-1:db-second").json()
        first_source = Source.objects.get(source_id=first["source_id"])
        second_source = Source.objects.get(source_id=second["source_id"])
        first_version = SourceVersion.objects.get(source=first_source, version=1)

        with self.assertRaises(DatabaseError), transaction.atomic():
            SourceVersion.objects.filter(pk=first_version.pk).update(
                source=second_source
            )
        with self.assertRaises(DatabaseError), transaction.atomic():
            SourceVersion.objects.filter(pk=first_version.pk).update(title="rewrite")
        with self.assertRaises(DatabaseError), transaction.atomic():
            Source.objects.filter(pk=first_source.pk).delete()
        self.assertEqual(SourceVersion.objects.filter(source=first_source).count(), 1)
        self.assertEqual(SourceVersion.objects.filter(source=second_source).count(), 1)

    def test_injected_source_and_idea_failures_roll_back_whole_transaction(self):
        with patch("rms.services._create_manifest", side_effect=RuntimeError("injected")):
            response = self.post_source(
                self.source_payload("fixture.rollback.source-create"),
                "rms-si-1:rollback-source-create",
            )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            (Source.objects.count(), SourceVersion.objects.count(), SourceManifest.objects.count(), IdempotencyRecord.objects.count()),
            (0, 0, 0, 0),
        )

        source = self.create_source().json()
        source_version_id = source["latest_source_version_id"]
        source_counts = (Source.objects.count(), SourceVersion.objects.count(), SourceManifest.objects.count(), IdempotencyRecord.objects.count())
        correction = self.source_payload()
        correction.pop("source_id")
        correction.update(expected_latest_version=1, correction_reason="Injected fictional rollback.", content_base64=None, title="Fictional title that must roll back")
        with patch("rms.services._store_idempotency", side_effect=RuntimeError("injected")):
            response = self.api_client("editor").post(
                "/api/v1/sources/fixture.source.increment1/corrections",
                data=correction,
                content_type="application/json",
                HTTP_IDEMPOTENCY_KEY="rms-si-1:rollback-source-correction",
            )
        self.assertEqual(response.status_code, 400)
        self.assertEqual((Source.objects.count(), SourceVersion.objects.count(), SourceManifest.objects.count(), IdempotencyRecord.objects.count()), source_counts)
        self.assertEqual(Source.objects.get().latest_version, 1)

        with patch("rms.services._store_idempotency", side_effect=RuntimeError("injected")):
            response = self.post_idea(self.idea_payload(source_version_id), "rms-si-1:rollback-idea-create")
        self.assertEqual(response.status_code, 400)
        self.assertEqual((Idea.objects.count(), IdeaVersion.objects.count(), IdeaContribution.objects.count()), (0, 0, 0))
        self.assertFalse(IdempotencyRecord.objects.filter(key="rms-si-1:rollback-idea-create").exists())

        idea = self.post_idea(self.idea_payload(source_version_id), "rms-si-1:rollback-idea-fixture").json()
        idea_counts = (Idea.objects.count(), IdeaVersion.objects.count(), IdeaContribution.objects.count(), IdempotencyRecord.objects.count())
        idea_correction = self.idea_payload(source_version_id, expected_latest_version=1, correction_reason="Injected fictional Idea rollback.", falsification="This fictional change must roll back.")
        with patch("rms.services._store_idempotency", side_effect=RuntimeError("injected")):
            response = self.api_client("editor").post(
                f"/api/v1/ideas/{idea['idea_id']}/corrections",
                data=idea_correction,
                content_type="application/json",
                HTTP_IDEMPOTENCY_KEY="rms-si-1:rollback-idea-correction",
            )
        self.assertEqual(response.status_code, 400)
        self.assertEqual((Idea.objects.count(), IdeaVersion.objects.count(), IdeaContribution.objects.count(), IdempotencyRecord.objects.count()), idea_counts)
        self.assertEqual(Idea.objects.get().latest_version, 1)

    def test_ui_intake_labels_rejection_and_byte_non_disclosure(self):
        source = self.create_source().json()
        source_version_id = source["latest_source_version_id"]
        raw = b"invented increment-one source bytes v1"
        for status in ("accepted", "rejected"):
            reason = "Invented rejection reason." if status == "rejected" else None
            idea = self.post_idea(
                self.idea_payload(
                    source_version_id,
                    workflow_status=status,
                    rejection_reason=reason,
                    title=f"Fictional {status} Idea",
                ),
                f"rms-si-1:ui:{status}",
            ).json()
            page = self.api_client("viewer").get(f"/ideas/{idea['idea_id']}")
            self.assertEqual(page.status_code, 200)
            self.assertNotIn(raw, page.content)
            self.assertNotIn(base64.b64encode(raw), page.content)
            if status == "accepted":
                self.assertContains(page, "Intake only — not validated or trading-approved.")
            else:
                self.assertContains(page, reason)

    def test_route_inventory_has_only_frozen_slice(self):
        required = {
            "/sources/new",
            "/sources/<str:source_id>/correct",
            "/sources/<str:source_id>/history",
            "/ideas/new",
            "/ideas/<str:idea_id>",
            "/ideas/<str:idea_id>/correct",
            "/ideas/<str:idea_id>/history",
            "/api/v1/sources",
            "/api/v1/sources/<str:source_id>/corrections",
            "/api/v1/sources/<str:source_id>",
            "/api/v1/sources/<str:source_id>/versions",
            "/api/v1/sources/<str:source_id>/manifest",
            "/api/v1/ideas",
            "/api/v1/ideas/<str:idea_id>/corrections",
            "/api/v1/ideas/<str:idea_id>",
            "/api/v1/ideas/<str:idea_id>/versions",
            "/api/v1/readiness",
        }
        from rms_project.urls import urlpatterns

        actual = {f"/{pattern.pattern}" for pattern in urlpatterns}
        self.assertEqual(actual, required)
        for excluded in (
            "/api/v1/search",
            "/api/v1/import",
            "/api/v1/hypotheses",
            "/api/v1/approvals",
            "/api/v1/dashboard",
            "/api/v1/connectors",
        ):
            self.assertEqual(self.api_client("editor").get(excluded).status_code, 404)

