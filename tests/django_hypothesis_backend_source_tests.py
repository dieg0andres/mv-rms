"""DB-free source checks. These do not execute H01-H20 or PostgreSQL guards."""

from contextlib import nullcontext
from copy import deepcopy
import json
import os
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "rms_project.settings")
import django
django.setup()

from django.apps import apps
from django.core.checks import run_checks
from django.db import connections
from django.db.migrations.autodetector import MigrationAutodetector
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.state import ProjectState
from django.http import QueryDict
from django.urls import resolve as resolve_url
from rest_framework.test import APIRequestFactory, force_authenticate

from rms import api, hypothesis_api, hypothesis_services
from rms.hypothesis_models import (
    AUTHORITY_REFERENCE, Hypothesis, HypothesisVersion, ResearchFamily,
    ResearchFamilyVersion, ResearchAssociationIdentity,
)
from rms.hypothesis_validation import HypothesisValidationError, SCHEMA
from rms.hypothesis_fixture import hypothesis_fields
from rms.research_context_common import AuthenticationRequired, Forbidden, StaleVersion, check_expected, execute_write
from rms.services import StoredResponse
from tests.django_hypothesis_backend_validation_tests import create_payload


def actor(editor=True, active=True, pk=1):
    user = SimpleNamespace(is_authenticated=True, is_active=active, pk=pk, groups=Mock(), get_username=lambda: "invented-editor")
    roles = {"editor"} if editor else {"founder_viewer"}
    user.groups.filter.side_effect = lambda **kwargs: Mock(exists=lambda: bool(roles & set(kwargs.get("name__in", (kwargs.get("name"),)))))
    return user


class DatabaseFreeCase(unittest.TestCase):
    def setUp(self):
        self.guard = patch.object(connections["default"], "ensure_connection", side_effect=AssertionError("DB access forbidden by source-only authorization"))
        self.guard.start()
        self.addCleanup(self.guard.stop)


class ModelAndRouteSourceTests(DatabaseFreeCase):
    def test_model_checks_and_migration_state_match_without_connection(self):
        self.assertEqual(run_checks(databases=[]), [])
        loader = MigrationLoader(None)
        changes = MigrationAutodetector(loader.project_state(), ProjectState.from_apps(apps)).changes(graph=loader.graph)
        self.assertEqual(changes, {})
        self.assertFalse(loader.disk_migrations[("rms", "0005_hypothesis_history_guards")].operations[0].reversible)

    def test_all_declared_endpoint_routes_resolve(self):
        for endpoint in SCHEMA["x-endpoints"]:
            if endpoint["path"] in ("/api/v1/sources", "/api/v1/ideas"):
                # Selection extends the existing Source/Idea routes, whose
                # URLConf remains Director-owned and is checked separately.
                match = resolve_url(endpoint["path"])
                expected = api.SourceCreateView if endpoint["path"].endswith("sources") else api.IdeaCreateView
                self.assertEqual(match.func.view_class, expected)
                continue
            with self.subTest(endpoint=endpoint["path"]):
                path = endpoint["path"]
                for name in ("hypothesis_id", "family_id", "investigation_id", "assessment_id", "association_id"):
                    path = path.replace("{" + name + "}", "invented-id")
                path = path.replace("{version}", "1")
                match = resolve_url(path, urlconf="rms.hypothesis_api_urls")
                self.assertEqual(match.func.view_class, hypothesis_api.ResearchRecordView)

    def test_origin_cardinality_and_endpoint_keys_are_database_constraints(self):
        model = apps.get_model("rms", "ResearchAssociation")
        self.assertTrue(any(c.name == "hypothesis_single_endpoints" for c in model._meta.constraints))
        for name in ("idea_version", "family_version", "investigation_version", "assessment_version", "hypothesis_version", "idea_family_version"):
            self.assertTrue(model._meta.get_field(name).is_relation)
        self.assertEqual(HypothesisVersion._meta.get_field("state").default, "draft")

    def test_fixture_is_complete_synthetic_description_with_distinct_duration_anchors(self):
        from rms.hypothesis_validation import draft_completeness
        fields = hypothesis_fields()
        self.assertEqual(draft_completeness(fields)["draft_completeness"], "complete")
        self.assertNotEqual(fields["effect_horizon"]["start_anchor"], fields["maximum_holding_period"]["start_anchor"])
        self.assertIn("Invented", fields["title"])


class APIBoundaryTests(DatabaseFreeCase):
    def setUp(self):
        super().setUp()
        self.factory = APIRequestFactory()

    def invoke(self, method="post", payload=None, user=None, action="collection"):
        kwargs = {"resource": "hypotheses", "action": action}
        view = hypothesis_api.ResearchRecordView.as_view(**kwargs)
        if method == "post":
            request = self.factory.post("/api/v1/hypotheses", create_payload() if payload is None else payload, format="json", HTTP_IDEMPOTENCY_KEY="invented-key")
        else:
            request = self.factory.get("/api/v1/hypotheses")
        if user is not None:
            force_authenticate(request, user=user)
        return view(request)

    def test_anonymous_api_preserves_basic_challenge(self):
        response = self.invoke()
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.data["error"]["code"], "authentication_required")
        self.assertTrue(response["WWW-Authenticate"].startswith("Basic"))

    def test_viewer_writes_fail_before_validation_or_database(self):
        response = self.invoke(payload={"classification": "restricted"}, user=actor(editor=False))
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.data["error"]["code"], "forbidden")

    def test_invalid_duration_returns_safe_field_path_before_database(self):
        payload = create_payload()
        payload["fields"]["effect_horizon"] = {"kind": "fixed", "quantity": "NaN"}
        response = self.invoke(payload=payload, user=actor())
        self.assertEqual(response.status_code, 400)
        self.assertIn("/fields/effect_horizon/quantity", [issue["path"] for issue in response.data["error"]["fields"]])
        self.assertNotIn("NaN", json.dumps(response.data))

    def test_owned_metadata_and_second_origin_are_rejected(self):
        for name in ("classification", "created_by", "status", "origins"):
            payload = create_payload()
            payload[name] = "forged"
            response = self.invoke(payload=payload, user=actor())
            self.assertEqual(response.status_code, 400)
            self.assertIn("/" + name, [issue["path"] for issue in response.data["error"]["fields"]])

    def test_query_parser_rejects_duplicate_and_noncanonical_numbers(self):
        for query in ("page=1&page=2", "page=01", "page_size=1.5", "page=-1"):
            with self.assertRaises(HypothesisValidationError):
                hypothesis_api.query_payload(QueryDict(query))

    def test_read_collection_calls_same_service_with_authenticated_actor(self):
        user = actor(editor=False)
        listing = Mock(return_value={"results": [], "page": 1, "page_size": 25, "count": 0, "next": None, "previous": None})
        current = hypothesis_api.RESOURCES["hypotheses"]
        with patch.dict(hypothesis_api.RESOURCES, {"hypotheses": (*current[:3], listing, *current[4:])}):
            response = self.invoke(method="get", user=user)
        self.assertEqual(response.status_code, 200)
        listing.assert_called_once_with(actor=user, query={})


class SharedRequestBoundaryTests(DatabaseFreeCase):
    def test_browser_service_enforces_rights_without_api(self):
        for user, error in ((None, AuthenticationRequired), (actor(False), Forbidden), (actor(active=False), Forbidden)):
            with self.assertRaises(error):
                hypothesis_services.create_hypothesis(actor=user, idempotency_key="invented", payload=create_payload())
        with self.assertRaises(Forbidden):
            hypothesis_services.get_hypothesis(actor=actor(active=False), hypothesis_id="hidden")

    def test_expected_version_is_checked_before_noop(self):
        with self.assertRaises(StaleVersion):
            check_expected(SimpleNamespace(latest_version=2), {"expected_latest_version": 1})

    def execute(self, user, payload, *, replay=None):
        operation = Mock(return_value=(200, {"stable_id": "HYP-invented"}))
        with patch("rms.research_context_common.transaction.atomic", return_value=nullcontext()), \
             patch("rms.research_context_common.lock_lineage"), \
             patch("rms.research_context_common._lock_idempotency_key"), \
             patch("rms.research_context_common._replay_or_conflict", return_value=replay) as replay_lookup, \
             patch("rms.research_context_common.IdempotencyRecord.objects.create") as store:
            result = execute_write(actor=user, idempotency_key="invented-key", payload=payload, request_name="HypothesisCreate", path="/api/v1/hypotheses", operation=operation)
        return result, replay_lookup.call_args.args, operation, store

    def test_actor_scope_and_canonical_payload_bind_request(self):
        payload = create_payload()
        original = deepcopy(payload)
        first, first_lookup, _, store = self.execute(actor(pk=1), payload)
        _, second_lookup, _, _ = self.execute(actor(pk=2), payload)
        _, reordered_lookup, _, _ = self.execute(actor(pk=1), dict(reversed(list(payload.items()))))
        changed = deepcopy(payload)
        changed["fields"]["title"] = "Different invented payload"
        _, changed_lookup, _, _ = self.execute(actor(pk=1), changed)
        self.assertNotEqual(first_lookup[0], second_lookup[0])
        self.assertEqual(first_lookup, reordered_lookup)
        self.assertEqual(first_lookup[0], changed_lookup[0])
        self.assertNotEqual(first_lookup[1], changed_lookup[1])
        self.assertEqual(first.status, 200)
        self.assertEqual(store.call_args.kwargs["response_status"], 200)
        self.assertEqual(payload, original)

    def test_replay_returns_original_bytes_status_without_operation(self):
        saved = StoredResponse(201, b'{"stable_id":"HYP-original","version":1}')
        result, _, operation, store = self.execute(actor(), create_payload(), replay=saved)
        self.assertIs(result, saved)
        operation.assert_not_called()
        store.assert_not_called()


if __name__ == "__main__":
    unittest.main()
