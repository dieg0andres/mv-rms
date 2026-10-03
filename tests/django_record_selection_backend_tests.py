"""R4/R5 source verification with database connections forbidden.

Invented in-memory rows and mocked ORM boundaries do not establish actual
account/database/browser acceptance or research credit.
"""

from contextlib import ExitStack
from datetime import UTC, datetime, timedelta
import hashlib
import json
import os
from pathlib import Path
import subprocess
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "rms_project.settings")
import django
django.setup()

from django.contrib.auth.models import AnonymousUser
from django.db import DatabaseError
from django.db.backends.base.base import BaseDatabaseWrapper
from django.urls import resolve
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, force_authenticate

from rms import api, hypothesis_api, hypothesis_services, permissions
from rms import record_selection_services as selection
from rms import research_context_services as context
from rms.hypothesis_validation import HypothesisValidationError, SCHEMA, _validate, validate_request
from rms.models import Idea, IdeaVersion, Source, SourceVersion
from rms.research_context_common import AuthenticationRequired, Forbidden, require_actor
from rms.services import StoredResponse


UUID = "11111111-1111-4111-8111-111111111111"
IDEA_ID = "IDE-" + UUID


def actor(*roles, active=True, staff=False):
    groups = Mock()
    groups.filter.side_effect = lambda **kw: SimpleNamespace(
        exists=lambda: bool(set(roles) & set(kw.get("name__in", (kw.get("name"),))))
    )
    return SimpleNamespace(is_authenticated=True, is_active=active, groups=groups,
                           is_staff=staff, is_superuser=staff, pk=UUID,
                           get_username=lambda: "invented-selection-actor")


class DatabaseDeniedCase(unittest.TestCase):
    def setUp(self):
        self.connection_guard = patch.object(
            BaseDatabaseWrapper, "ensure_connection",
            side_effect=AssertionError("R4/R5 source checks forbid database connections"),
        )
        self.denied = self.connection_guard.start()
        self.addCleanup(self.connection_guard.stop)
        self.addCleanup(self.denied.assert_not_called)
        self.factory = APIRequestFactory()

    def request(self, path, user, method="get", body=None):
        request = self.factory.get(path) if method == "get" else self.factory.post(
            path, body if body is not None else {}, format="json",
            HTTP_IDEMPOTENCY_KEY="invented-selection-key",
        )
        if user is not None:
            force_authenticate(request, user=user)
        match = resolve(path.split("?")[0])
        return match.func(request, **match.kwargs)


class RoleBoundaryTests(DatabaseDeniedCase):
    def test_shared_role_matrix_and_no_staff_bypass(self):
        for user, read, write in (
            (None, False, False), (AnonymousUser(), False, False),
            (actor(), False, False), (actor(staff=True), False, False),
            (actor("editor", active=False), False, False),
            (actor("founder_viewer", active=False), False, False),
            (actor("founder_viewer"), True, False),
            (actor("editor"), True, True),
            (actor("editor", "founder_viewer"), True, True),
        ):
            with self.subTest(user=user):
                self.assertIs(permissions.has_rms_read_access(user), read)
                self.assertIs(permissions.has_rms_write_access(user), write)
                for is_write, allowed in ((False, read), (True, write)):
                    if allowed:
                        require_actor(user, write=is_write)
                    else:
                        error = AuthenticationRequired if not getattr(user, "is_authenticated", False) else Forbidden
                        with self.assertRaises(error):
                            require_actor(user, write=is_write)

    def test_legacy_read_denials_precede_record_and_manifest_lookup(self):
        paths = ["/api/v1/sources/FIC-SELECTION", "/api/v1/sources/FIC-SELECTION/versions",
                 "/api/v1/sources/FIC-SELECTION/manifest", f"/api/v1/ideas/{IDEA_ID}",
                 f"/api/v1/ideas/{IDEA_ID}/versions", "/api/v1/sources", "/api/v1/ideas"]
        with ExitStack() as stack:
            lookups = [stack.enter_context(patch.object(api, name)) for name in
                       ("_source_or_response", "_idea_or_response", "manifest_for_version", "list_sources", "list_ideas")]
            for user, status in ((None, 401), (actor(), 403), (actor(staff=True), 403),
                                 (actor("editor", active=False), 403)):
                for path in paths:
                    with self.subTest(path=path, status=status):
                        response = self.request(path, user)
                        self.assertEqual(response.status_code, status)
                        self.assertEqual(response.data["error"]["code"], "authentication_required" if status == 401 else "forbidden")
            for lookup in lookups:
                lookup.assert_not_called()

    def test_all_hn_read_adapters_enforce_roles_before_dispatch(self):
        for endpoint in SCHEMA["x-endpoints"]:
            if endpoint["method"] != "GET" or endpoint["path"] in ("/api/v1/sources", "/api/v1/ideas"):
                continue
            path = endpoint["path"]
            for key in ("hypothesis_id", "family_id", "investigation_id", "assessment_id", "association_id"):
                path = path.replace("{" + key + "}", "invented-id")
            path = path.replace("{version}", "1")
            match = resolve(path, urlconf="rms.hypothesis_api_urls")
            with patch.object(hypothesis_api.ResearchRecordView, "get") as dispatch:
                for user, status in ((None, 401), (actor(), 403), (actor("founder_viewer", active=False), 403)):
                    request = self.factory.get(path)
                    if user is not None:
                        force_authenticate(request, user=user)
                    response = match.func(request, **match.kwargs)
                    self.assertEqual(response.status_code, status, path)
                dispatch.assert_not_called()
                dispatch.return_value = Response({"invented": "authorized read"})
                for user in (actor("editor"), actor("founder_viewer")):
                    request = self.factory.get(path)
                    force_authenticate(request, user=user)
                    response = match.func(request, **match.kwargs)
                    self.assertEqual(response.status_code, 200, path)
                self.assertEqual(dispatch.call_count, 2)

    def test_shared_hn_read_services_deny_before_lookup_count_or_validation(self):
        calls = [
            (hypothesis_services.get_hypothesis, {"hypothesis_id": "hidden"}),
            (hypothesis_services.get_hypothesis_history, {"hypothesis_id": "hidden"}),
            (hypothesis_services.list_hypotheses, {"query": {}}),
            (context.get_research_family, {"family_id": "hidden"}),
            (context.get_research_family_history, {"family_id": "hidden"}),
            (context.list_research_families, {"query": {}}),
            (context.get_investigation, {"investigation_id": "hidden"}),
            (context.get_investigation_history, {"investigation_id": "hidden"}),
            (context.list_investigations, {"query": {}}),
            (context.get_prior_research_assessment, {"assessment_id": "hidden", "version": 1}),
            (context.get_idea_family_for_idea, {"idea_version_id": "hidden"}),
            (context.get_idea_family_association, {"association_id": "hidden"}),
            (context.get_idea_family_association_history, {"association_id": "hidden"}),
            (selection.list_sources, {"query": {}}), (selection.list_ideas, {"query": {}}),
        ]
        with ExitStack() as stack:
            boundaries = []
            for module in (hypothesis_services, context, selection):
                for name in ("latest", "resolve", "visible"):
                    if hasattr(module, name):
                        boundaries.append(stack.enter_context(patch.object(module, name)))
            for function, kwargs in calls:
                for user, error in ((None, AuthenticationRequired), (actor(), Forbidden),
                                    (actor("editor", active=False), Forbidden)):
                    with self.subTest(function=function.__name__, user=user), self.assertRaises(error):
                        function(actor=user, **kwargs)
            for boundary in boundaries:
                boundary.assert_not_called()

    def test_legacy_write_denials_precede_parsing_and_mutation(self):
        paths = ["/api/v1/sources", "/api/v1/sources/FIC-SELECTION/corrections",
                 "/api/v1/ideas", f"/api/v1/ideas/{IDEA_ID}/corrections"]
        with ExitStack() as stack:
            writes = [stack.enter_context(patch.object(api, name)) for name in
                      ("create_source", "correct_source", "create_idea", "correct_idea")]
            for user, status in ((None, 401), (actor(), 403), (actor("founder_viewer"), 403),
                                 (actor("editor", active=False), 403)):
                for path in paths:
                    self.assertEqual(self.request(path, user, "post", {"invalid": "invented"}).status_code, status)
            for write in writes:
                write.assert_not_called()


class LegacyCompatibilityTests(DatabaseDeniedCase):
    def test_authorized_missing_records_keep_safe_404(self):
        with patch.object(api, "get_source", side_effect=api.SourceNotFound), \
             patch.object(api, "get_idea", side_effect=api.IdeaNotFound):
            for path in ("/api/v1/sources/FIC-MISSING", f"/api/v1/ideas/{IDEA_ID}"):
                for user in (actor("editor"), actor("founder_viewer")):
                    response = self.request(path, user)
                    self.assertEqual(response.status_code, 404)
                    self.assertEqual(response.data["error"]["code"], "not_found")

    def test_both_roles_keep_detail_history_and_manifest_payloads(self):
        manifest = SimpleNamespace(manifest_bytes=b'{"invented":true}', manifest_sha256="a" * 64, through_version=1)
        payload = {"invented": "original adapter payload"}
        paths = ["/api/v1/sources/FIC-SELECTION", "/api/v1/sources/FIC-SELECTION/versions",
                 f"/api/v1/ideas/{IDEA_ID}", f"/api/v1/ideas/{IDEA_ID}/versions"]
        with ExitStack() as stack:
            stack.enter_context(patch.object(api, "_source_or_response", return_value=SimpleNamespace(source_id="FIC-SELECTION")))
            stack.enter_context(patch.object(api, "_idea_or_response", return_value=object()))
            for name in ("source_detail", "source_history", "idea_detail", "idea_history"):
                stack.enter_context(patch.object(api, name, return_value=payload))
            stack.enter_context(patch.object(api, "manifest_for_version", return_value=manifest))
            for user in (actor("editor"), actor("founder_viewer")):
                for path in paths:
                    response = self.request(path, user)
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.data, payload)
                response = self.request("/api/v1/sources/FIC-SELECTION/manifest", user)
                self.assertEqual(response.content, manifest.manifest_bytes)
                self.assertEqual(response["X-Manifest-SHA256"], manifest.manifest_sha256)

    def test_readiness_keeps_separate_no_role_policy(self):
        executor = Mock()
        executor.migration_plan.return_value = []
        with patch.object(api.connection, "cursor"), patch.object(api, "MigrationExecutor", return_value=executor):
            response = self.request("/api/v1/readiness", actor())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, {"status": "ready"})
        self.assertEqual(self.request("/api/v1/readiness", None).status_code, 401)

    def test_editor_posts_keep_registered_routes_and_stored_responses(self):
        source = {"source_id": "FIC-SELECTION", "synthetic": True, "content_base64": "aW52ZW50ZWQ=",
                  "title": "Invented", "source_type": "working_paper", "citation": "Invented citation",
                  "observed_available_at": "2026-10-03T00:00:00Z", "authors": None, "publisher": None,
                  "published_at": None, "canonical_url": None, "rights_note": None}
        idea = {"synthetic": True, "title": "Invented", "mechanism": "Invented", "testable_claim": "Invented",
                "falsification": "Invented", "eligible_market": "etfs", "workflow_status": "draft",
                "rejection_reason": None, "contributions": [{"source_version_id": "SRCV-" + UUID, "contribution": "Invented"}]}
        for path, name, service, payload in (("/api/v1/sources", "source-create", "create_source", source),
                                              ("/api/v1/ideas", "idea-create", "create_idea", idea)):
            self.assertEqual(resolve(path).url_name, name)
            with patch.object(api, service, return_value=StoredResponse(201, b'{"invented":true}')) as write:
                response = self.request(path, actor("editor"), "post", payload)
            self.assertEqual(response.status_code, 201)
            self.assertEqual(response.content, b'{"invented":true}')
            write.assert_called_once()
            self.assertEqual(write.call_args.kwargs["idempotency_key"], "invented-selection-key")


class SelectionQueryTests(DatabaseDeniedCase):
    def test_valid_defaults_bounds_and_no_input_mutation(self):
        for query, expected in (({}, {"page": 1, "page_size": 25}), ({"page_size": 100}, {"page": 1, "page_size": 100}),
                                ({"page": 9, "page_size": 1}, {"page": 9, "page_size": 1})):
            original = dict(query)
            self.assertEqual(validate_request("SelectionQuery", query), expected)
            self.assertEqual(query, original)

    def test_service_rejects_invalid_mapping_before_visibility_count(self):
        bad = [[], None, {"page": True}, {"page_size": False}, {"page": "1"}, {"page": 0},
               {"page": -1}, {"page_size": 101}, {"page_size": 0}, {"page": 1.0}, {"title": "Invented"}]
        with patch.object(selection, "visible") as visibility:
            for listing in (selection.list_sources, selection.list_ideas):
                for query in bad:
                    with self.subTest(query=query), self.assertRaises(HypothesisValidationError):
                        listing(actor=actor("editor"), query=query)
            visibility.assert_not_called()

    def test_http_rejects_repeated_unknown_noncanonical_and_over_limit_query(self):
        bad = ["page=1&page=2", "page_size=25&page_size=25", "title=Invented", "page=01", "page=+1",
               "page=%201", "page=1.0", "page=-1", "page=0", "page_size=101", "page_size=0", "page=",
               "page=%D9%A1", "page=" + "9" * 4301]
        with patch.object(selection, "visible") as visibility:
            for path in ("/api/v1/sources", "/api/v1/ideas"):
                for query in bad:
                    response = self.request(path + "?" + query, actor("founder_viewer"))
                    self.assertEqual(response.status_code, 400, query[:80])
                    self.assertEqual(response.data["error"]["code"], "validation_error")
                    self.assertEqual(set(response.data["error"]), {"code", "message", "request_id"})
            visibility.assert_not_called()


class Rows:
    """Evaluate mocked identity filters/order/slices, retaining boundary evidence."""
    def __init__(self, rows):
        self.rows = list(rows)
        self.events = []

    def filter(self, **kwargs):
        self.events.append(("filter", kwargs))
        self.rows = [row for row in self.rows if all(getattr(row, key) == value for key, value in kwargs.items())]
        return self

    def order_by(self, *fields):
        self.events.append(("order", fields))
        for field in reversed(fields):
            self.rows.sort(key=lambda row: getattr(row, field.lstrip("-")), reverse=field.startswith("-"))
        return self

    def count(self):
        self.events.append(("count", len(self.rows)))
        return len(self.rows)

    def __getitem__(self, selected):
        self.events.append(("slice", selected.start, selected.stop))
        return self.rows[selected]


def invented_record(model, number, created, *, synthetic=True):
    stable_id = f"FIC-SELECTION-{number:03}" if model is Source else f"IDE-{number:08x}-1111-4111-8111-111111111111"
    row = model(**{"source_id" if model is Source else "idea_id": stable_id},
                synthetic=synthetic, created_at=created, latest_version=2)
    item = SimpleNamespace(title=f"Invented selection {number}", version=2,
                           source_version_id="SRCV-" + UUID, idea_version_id="IDEV-" + UUID,
                           workflow_status="rejected")
    versions = Mock()
    versions.only.return_value.get.return_value = item
    row._prefetched_objects_cache = {"versions": versions}
    return row, versions


class SelectionResultsTests(DatabaseDeniedCase):
    def test_order_scope_count_latest_links_and_pagination_through_actual_api(self):
        now = datetime(2026, 10, 3, tzinfo=UTC)
        for model, listing, route, name in ((Source, selection.list_sources, "sources", "SourceSelection"),
                                           (Idea, selection.list_ideas, "ideas", "IdeaSelection")):
            data = [invented_record(model, 3, now - timedelta(days=1)), invented_record(model, 2, now),
                    invented_record(model, 1, now), invented_record(model, 0, now + timedelta(days=1), synthetic=False)]
            qs = Rows([row for row, _ in data])
            with patch.object(model.objects, "filter", side_effect=qs.filter):
                response = self.request(f"/api/v1/{route}?page=1&page_size=2", actor("founder_viewer"))
            self.assertEqual(response.status_code, 200)
            payload = response.data
            self.assertEqual(payload["count"], 3)
            self.assertEqual([v["title"] for v in payload["results"]], ["Invented selection 1", "Invented selection 2"])
            self.assertEqual(payload["next"], f"/api/v1/{route}?page=2&page_size=2")
            self.assertIsNone(payload["previous"])
            self.assertEqual(qs.events, [("filter", {"synthetic": True}),
                                        ("order", ("-created_at", "source_id" if model is Source else "idea_id")),
                                        ("count", 3), ("slice", 0, 2)])
            data[-1][1].only.assert_not_called()
            for result in payload["results"]:
                issues = []
                _validate(result, SCHEMA["$defs"][name], "", issues)
                self.assertEqual(issues, [])
                history = f"/{route}/{result['stable_id']}/history"
                self.assertEqual(result["links"], {
                    "detail": history if model is Source else f"/ideas/{result['stable_id']}",
                    "history": history,
                    "selected_version": history + f"#{'source' if model is Source else 'idea'}-version-2",
                })
                self.assertEqual(set(result), {"stable_id", "title", "latest_version", "latest_version_id", "links"}
                                 | ({"status"} if model is Idea else set()))
            for _, versions in data[1:3]:
                versions.only.return_value.get.assert_called_once_with(version=2, synthetic=True)
                self.assertNotIn("content", versions.only.call_args.args)
            qs = Rows([row for row, _ in data])
            with patch.object(model.objects, "filter", side_effect=qs.filter):
                last = listing(actor=actor("editor"), query={"page": 2, "page_size": 2})
            self.assertEqual([v["title"] for v in last["results"]], ["Invented selection 3"])
            self.assertIsNone(last["next"])
            self.assertEqual(last["previous"], f"/api/v1/{route}?page=1&page_size=2")

    def test_empty_and_out_of_range_are_real_counts_without_version_fetch(self):
        for model, listing in ((Source, selection.list_sources), (Idea, selection.list_ideas)):
            row, versions = invented_record(model, 1, datetime(2026, 10, 3, tzinfo=UTC))
            for rows, count in (([], 0), ([row], 1)):
                qs = Rows(rows)
                with patch.object(model.objects, "filter", side_effect=qs.filter):
                    result = listing(actor=actor("editor"), query={"page": 99})
                self.assertEqual(result["count"], count)
                self.assertEqual(result["results"], [])
                self.assertIsNone(result["next"])
                if count == 0:
                    self.assertIsNone(result["previous"])
                versions.only.assert_not_called()

    def test_missing_or_inaccessible_latest_fails_without_dropping_counted_row(self):
        for model, version_model, listing, route in ((Source, SourceVersion, selection.list_sources, "sources"),
                                                     (Idea, IdeaVersion, selection.list_ideas, "ideas")):
            row, versions = invented_record(model, 1, datetime(2026, 10, 3, tzinfo=UTC))
            versions.only.return_value.get.side_effect = version_model.DoesNotExist("invented restricted title")
            with patch.object(model.objects, "filter", return_value=Rows([row])):
                response = self.request(f"/api/v1/{route}", actor("editor"))
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.data["error"]["code"], "selection_unavailable")
            self.assertNotIn("restricted", json.dumps(response.data))
            row.latest_version = 0
            with patch.object(model.objects, "filter", return_value=Rows([row])), self.assertRaises(selection.SelectionUnavailable):
                listing(actor=actor("founder_viewer"), query={})

    def test_database_unavailable_is_safe_503_and_never_fabricated_zero(self):
        qs = Mock()
        qs.order_by.return_value = qs
        qs.count.side_effect = DatabaseError("invented sensitive database details")
        with patch.object(selection, "visible", return_value=qs):
            for path in ("/api/v1/sources", "/api/v1/ideas"):
                response = self.request(path, actor("editor"))
                self.assertEqual(response.status_code, 503)
                self.assertNotIn("count", response.data)
                self.assertNotIn("sensitive", json.dumps(response.data))

    def test_orm_projection_defers_source_bytes_and_uses_identity_order(self):
        # SQL compilation only: no query is executed.
        sql = str(Source.objects.filter(synthetic=True).order_by("-created_at", "source_id").query)
        self.assertIn('ORDER BY "rms_source"."created_at" DESC, "rms_source"."source_id" ASC', sql)
        version_sql = str(SourceVersion.objects.only("source", "source_version_id", "version", "title", "synthetic").query)
        self.assertNotIn('"content"', version_sql)
        self.assertNotIn('"content_sha256"', version_sql)


class InterfaceCompatibilityTests(DatabaseDeniedCase):
    def test_successor_adds_only_selection_and_keeps_exact_contract(self):
        old = json.loads(subprocess.check_output(["git", "show", "ac5b0291:rms/hypothesis_schema.json"]))
        self.assertEqual(SCHEMA["x-interface-version"], "1.2")
        self.assertEqual(SCHEMA["$id"], "urn:mv-rms:RMS-HN-API-1:1.2")
        self.assertEqual(SCHEMA["x-schema-version"], "1.0")
        self.assertEqual(SCHEMA["x-authority"], old["x-authority"])
        self.assertEqual(SCHEMA["x-endpoints"][:24], old["x-endpoints"])
        self.assertEqual(len(SCHEMA["x-endpoints"]), 26)
        for name, definition in old["$defs"].items():
            if name == "Error":
                definition["properties"]["error"]["properties"]["code"]["enum"].append("selection_unavailable")
            self.assertEqual(SCHEMA["$defs"][name], definition, name)
        contract = Path("docs/RMS_HYPOTHESIS_DESIGN_CONTRACT_V1_0.md").read_bytes()
        self.assertEqual(len(contract), 58395)
        self.assertEqual(hashlib.sha256(contract).hexdigest(), "f9a7ebe54e329d1a994b7f37e5fd5bc62413c215e0f58acae1c8c7d4f604b0c9")
