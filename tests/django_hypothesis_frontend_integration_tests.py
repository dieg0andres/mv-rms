"""Invented DB-free adapter/rendering checks; no persisted saves are claimed."""

from copy import deepcopy
import json
from html.parser import HTMLParser
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import RequestFactory, SimpleTestCase, override_settings
from django.db import DatabaseError
from django.middleware.csrf import get_token
from django.urls import resolve
from rest_framework.test import APIClient, force_authenticate

from rms import hypothesis_api, hypothesis_services, research_context_services
from rms.hypothesis_validation import HypothesisValidationError, validate_request
from rms.navigation_views import (
    NavigationPage, RecordDetailPage, RecordEditorPage, RecordHistoryPage,
    flatten_input, form_payload, read_navigation_schema, revision_snapshot,
)
from rms.research_context_common import Forbidden, StaleVersion
from rms.services import ResourceNotFound, StoredResponse
from rms.views import IdeaDetailPage
from tests.django_hypothesis_frontend_schema_tests import invented_record


def invented_actor(role="editor", active=True):
    groups = Mock()
    groups.filter.side_effect = lambda **query: SimpleNamespace(exists=lambda: role in query.get("name__in", [query.get("name")]))
    return SimpleNamespace(is_authenticated=True, is_active=active, groups=groups, pk=101, get_username=lambda: "Invented editor")


def listing(records=(), page=1):
    return {"page": page, "page_size": 25, "count": len(records), "results": list(records), "next": None, "previous": None}


class ConnectedFrontendTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.schema = read_navigation_schema()

    def setUp(self):
        self.actor = invented_actor()
        self.factory = RequestFactory()
        self.record = invented_record(self.schema)
        self.family = {"family_id": "RFAM-11111111-1111-4111-8111-111111111111", "family_version_id": "RFAMV-11111111-1111-4111-8111-111111111111", "version": 1, "fields": {"name": "Invented family", "mechanism_boundary": "Invented boundary", "distinctness_rule": "Invented distinctness", "risk_review_reference": None}}
        self.case = {"investigation_id": "INV-11111111-1111-4111-8111-111111111111", "investigation_version_id": "INVV-11111111-1111-4111-8111-111111111111", "version": 1, "fields": {"title": "Invented case", "owner_role": "Invented Research", "priority": "normal", "next_action": "Record invented draft", "blocker_text": None}, "family": self.record["research_context"]["family"], "prior_research_assessment": {"assessment_id": "PRA-11111111-1111-4111-8111-111111111111", "assessment_version_id": "PRAV-11111111-1111-4111-8111-111111111111", "version": 1, "fields": self.assessment_fields()}, "family_association": self.record["research_context"]["investigation_family_association"], "assessment_association": self.record["research_context"]["investigation_assessment_association"]}
        for name, result in (("list_research_families", listing([self.family])), ("list_investigations", listing([self.case]))):
            context = patch.object(research_context_services, name, return_value=result)
            context.start()
            self.addCleanup(context.stop)

    def assessment_fields(self):
        return {"query_scope": "Invented fixture Idea only", "query_time": "2026-10-03T12:00:00Z", "policy_version": self.schema["$defs"]["AssessmentFields"]["properties"]["policy_version"]["const"], "result_watermark": "Invented fixture v1", "finding": "no_relevant_work_found", "rationale": "No other invented records inspected", "limitations": "No real research reviewed", "record_links": []}

    def create_payload(self):
        return {"fields": {"title": "  Invented draft  "}, "originating_idea_version_id": self.record["origin"]["idea"]["version_id"], "origin_rationale": "Invented origin only", "investigation_version_id": self.case["investigation_version_id"], "idea_family_binding": {"mode": "existing", "association_version_id": "IFAV-11111111-1111-4111-8111-111111111111"}}

    def request(self, method="get", data=None, actor=None, path="/hypotheses/new", csrf=False):
        request = getattr(self.factory, method)(path, data=data or {})
        request._dont_enforce_csrf_checks = not csrf
        if actor is not False:
            force_authenticate(request, user=actor or self.actor)
        return request

    def submit(self, payload, *, kind="hypothesis", record_id=None, operation="save", extra=None, actor=None):
        data = {**flatten_input(payload), "operation": operation, "idempotency_key": "invented-fixed-request-key", **(extra or {})}
        kwargs = {"record_id": record_id} if record_id else {}
        return RecordEditorPage.as_view(kind=kind)(self.request("post", data=data, actor=actor), **kwargs)

    def render(self, response):
        response.render()
        return response.content.decode()

    def test_create_passes_actor_key_and_schema_payload_to_shared_service(self):
        payload = self.create_payload()
        result = StoredResponse(201, json.dumps(self.record).encode())
        with patch.object(hypothesis_services, "create_hypothesis", return_value=result) as save:
            response = self.submit(payload)
        self.assertEqual(response.status_code, 303)
        self.assertTrue(response["Location"].endswith("/versions/1"))
        kwargs = save.call_args.kwargs
        self.assertIs(kwargs["actor"], self.actor)
        self.assertEqual(kwargs["idempotency_key"], "invented-fixed-request-key")
        self.assertEqual(kwargs["payload"]["fields"]["title"], "  Invented draft  ")
        self.assertEqual(validate_request("HypothesisCreate", kwargs["payload"]), validate_request("HypothesisCreate", payload))
        self.assertEqual(response["Cache-Control"], "private, no-store")

    def test_browser_and_api_bind_the_same_create_payload(self):
        payload = self.create_payload()
        result = StoredResponse(201, json.dumps(self.record).encode())
        with patch.object(hypothesis_services, "create_hypothesis", return_value=result) as browser_save:
            self.submit(payload)
        encoded = browser_save.call_args.kwargs["payload"]
        service = Mock(return_value=result)
        original = hypothesis_api.RESOURCES["hypotheses"]
        with patch.dict(hypothesis_api.RESOURCES, {"hypotheses": (service, *original[1:])}):
            request = self.factory.post("/api/v1/hypotheses", data=json.dumps(encoded), content_type="application/json", HTTP_IDEMPOTENCY_KEY="invented-fixed-request-key")
            force_authenticate(request, user=self.actor)
            api = hypothesis_api.ResearchRecordView.as_view(resource="hypotheses")(request)
        self.assertEqual(api.status_code, 201)
        self.assertEqual(service.call_args.kwargs, browser_save.call_args.kwargs)

    def test_correction_sends_every_field_null_and_restated_bindings(self):
        payload = revision_snapshot("hypothesis", self.record)
        payload["correction_reason"] = "Invented correction reason"
        payload["idea_family_binding"]["association_version_id"] = "IFAV-11111111-1111-4111-8111-111111111111"
        with patch.object(hypothesis_services, "correct_hypothesis", return_value=StoredResponse(200, json.dumps(self.record).encode())) as save:
            response = self.submit(payload, record_id=self.record["hypothesis_id"])
        self.assertEqual(response.status_code, 303)
        actual = save.call_args.kwargs["payload"]
        self.assertEqual(set(actual["fields"]), set(self.schema["$defs"]["HypothesisFields"]["properties"]))
        self.assertEqual(actual["expected_latest_version"], 1)
        self.assertIsNone(actual["fields"]["claim"])
        self.assertEqual(validate_request("HypothesisCorrection", actual)["idea_family_binding"], payload["idea_family_binding"])

    def test_double_native_submission_retains_same_key_and_payload(self):
        with patch.object(hypothesis_services, "create_hypothesis", return_value=StoredResponse(201, json.dumps(self.record).encode())) as save:
            first = self.submit(self.create_payload())
            second = self.submit(self.create_payload())
        self.assertEqual(first["Location"], second["Location"])
        self.assertEqual(save.call_args_list[0], save.call_args_list[1])
        # Only request binding is verified; persistence deduplication is Backend/Test-owned.

    def test_conflict_preserves_losing_input_and_context(self):
        payload = revision_snapshot("hypothesis", self.record)
        payload["fields"]["title"] = "  losing invented input  "
        payload["fields"]["claim"] = "</textarea><script>invented()</script>"
        with patch.object(hypothesis_services, "correct_hypothesis", side_effect=StaleVersion):
            response = self.submit(payload, record_id=self.record["hypothesis_id"], extra={"/context/case/prior_research_assessment/limitations": "Unsaved invented limits"})
        html = self.render(response)
        self.assertEqual(response.status_code, 409)
        self.assertIn("  losing invented input  ", html)
        self.assertIn("Unsaved invented limits</textarea>", html)
        self.assertIn("&lt;script&gt;invented()&lt;/script&gt;", html)
        self.assertNotIn("<script>invented()", html)
        self.assertIn('target="_blank" rel="noopener"', html)
        self.assertIn("Do not overwrite or automatically retry", html)
        self.assertIn("data-error-summary", html)

    def test_invalid_duration_is_sent_to_backend_and_errors_focus_field(self):
        payload = self.create_payload()
        payload["fields"]["effect_horizon"] = {"kind": "fixed", "quantity": "-2", "unit": "bars", "calendar": "Keep conflicting invented calendar"}
        issues = [{"path": "/fields/effect_horizon/quantity", "code": "invalid", "message": "Invented server field error"}]
        with patch.object(hypothesis_services, "create_hypothesis", side_effect=HypothesisValidationError(issues)) as save:
            response = self.submit(payload)
        self.assertEqual(save.call_args.kwargs["payload"]["fields"]["effect_horizon"]["quantity"], "-2")
        html = self.render(response)
        self.assertEqual(response.status_code, 400)
        self.assertIn('href="#draft-fields-effect_horizon-quantity"', html)
        self.assertIn('aria-invalid="true"', html)
        self.assertIn("Keep conflicting invented calendar", html)

    def test_first_family_requires_explicit_confirmation_before_service(self):
        payload = self.create_payload()
        payload["idea_family_binding"] = {"mode": "create", "family_version_id": self.family["family_version_id"], "rationale": "Invented grouping"}
        with patch.object(hypothesis_services, "create_hypothesis", return_value=StoredResponse(201, json.dumps(self.record).encode())) as save:
            denied = self.submit(payload)
            save.assert_not_called()
            accepted = self.submit(payload, extra={"confirm_first_family": "yes"})
        self.assertEqual(denied.status_code, 400)
        self.assertEqual(accepted.status_code, 303)

    def test_family_creation_selects_confirmed_version_without_losing_draft(self):
        data = flatten_input({"fields": self.family["fields"]}, "/context/family")
        with patch.object(research_context_services, "create_research_family", return_value=StoredResponse(201, json.dumps(self.family).encode())) as save:
            response = self.submit(self.create_payload(), operation="create_family", extra=data)
        html = self.render(response)
        self.assertEqual(response.status_code, 200)
        self.assertIn("  Invented draft  ", html)
        self.assertIn("Research family version 1 saved and selected. Hypothesis input remains unsaved.", html)
        self.assertIn(self.family["family_version_id"], html)
        self.assertEqual(save.call_args.kwargs["payload"]["fields"]["name"], "Invented family")

    def test_case_creation_preserves_manual_review_and_draft_input(self):
        case_payload = {"family_version_id": self.family["family_version_id"], "fields": self.case["fields"], "prior_research_assessment": self.assessment_fields()}
        with patch.object(research_context_services, "create_investigation", return_value=StoredResponse(201, json.dumps(self.case).encode())) as save:
            response = self.submit(self.create_payload(), operation="create_case", extra=flatten_input(case_payload, "/context/case"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("  Invented draft  ", self.render(response))
        self.assertEqual(save.call_args.kwargs["payload"]["prior_research_assessment"]["record_links"], [])
        self.assertEqual(validate_request("InvestigationCreate", save.call_args.kwargs["payload"]), validate_request("InvestigationCreate", case_payload))

    def test_context_validation_error_maps_back_to_inline_control(self):
        error = HypothesisValidationError([{"path": "/prior_research_assessment/limitations", "code": "missing", "message": "Invented review limitation required"}])
        with patch.object(research_context_services, "create_investigation", side_effect=error):
            response = self.submit(self.create_payload(), operation="create_case", extra={"/context/case/prior_research_assessment/record_links": "[]"})
        self.assertIn('href="#draft-context-case-prior_research_assessment-limitations"', self.render(response))

    def test_case_revision_retains_assessment_or_encodes_explicit_successor(self):
        payload = revision_snapshot("case", self.case)
        payload["correction_reason"] = "Invented case correction"
        inputs = flatten_input(payload)
        inputs["/prior_research_assessment/fields/policy_version"] = self.assessment_fields()["policy_version"]
        encoded = form_payload(self.schema, self.schema["$defs"]["InvestigationCorrection"], inputs)
        self.assertEqual(validate_request("InvestigationCorrection", encoded)["prior_research_assessment"], payload["prior_research_assessment"])
        payload["prior_research_assessment"] = {"mode": "correct", "corrects_assessment_version_id": self.case["prior_research_assessment"]["assessment_version_id"], "expected_latest_assessment_version": 1, "correction_reason": "Invented assessment correction", "fields": self.assessment_fields()}
        encoded = form_payload(self.schema, self.schema["$defs"]["InvestigationCorrection"], flatten_input(payload))
        self.assertEqual(validate_request("InvestigationCorrection", encoded)["prior_research_assessment"]["mode"], "correct")

    def test_viewer_anonymous_inactive_and_unassigned_never_reach_write(self):
        for actor, status in ((invented_actor("founder_viewer"), 403), (invented_actor("unassigned"), 403), (invented_actor(active=False), 403), (False, 401)):
            with self.subTest(status=status, actor=actor), patch.object(hypothesis_services, "create_hypothesis") as save:
                response = self.submit(self.create_payload(), actor=actor)
                self.assertEqual(response.status_code, status)
                save.assert_not_called()
                self.assertNotIn("Invented draft", self.render(response))

    def test_csrf_failure_is_denied_before_write_and_has_navigation(self):
        with patch.object(hypothesis_services, "create_hypothesis") as save:
            request = self.request("post", flatten_input(self.create_payload()), csrf=True)
            response = RecordEditorPage.as_view()(request)
        self.assertEqual(response.status_code, 403)
        self.assertIn('href="/"', self.render(response))
        save.assert_not_called()

    def test_valid_csrf_cookie_and_form_token_allow_authorized_submit(self):
        seed = self.factory.get("/hypotheses/new")
        token = get_token(seed)
        data = {**flatten_input(self.create_payload()), "csrfmiddlewaretoken": token, "idempotency_key": "invented-csrf-request"}
        request = self.request("post", data, csrf=True)
        request.COOKIES["csrftoken"] = seed.META["CSRF_COOKIE"]
        with patch.object(hypothesis_services, "create_hypothesis", return_value=StoredResponse(201, json.dumps(self.record).encode())) as save:
            response = RecordEditorPage.as_view()(request)
        self.assertEqual(response.status_code, 303)
        save.assert_called_once()

    def fresh_editor_form(self, path="/hypotheses/new"):
        client = APIClient(enforce_csrf_checks=True)
        client.force_authenticate(user=self.actor)
        response = client.get(path, secure=True)
        self.assertEqual(response.status_code, 200)
        class TokenParser(HTMLParser):
            token = None
            def handle_starttag(self, tag, attrs):
                attributes = dict(attrs)
                if tag == "input" and attributes.get("name") == "csrfmiddlewaretoken":
                    self.token = attributes.get("value")
        parser = TokenParser()
        parser.feed(response.content.decode())
        self.assertTrue(parser.token)
        return client, response, parser.token

    @override_settings(MIDDLEWARE=[], CSRF_TRUSTED_ORIGINS=["https://private.example.invalid:4443"])
    def test_fresh_editor_get_cookie_allows_bound_native_post(self):
        idea = {"idea_version_id": self.record["origin"]["idea"]["version_id"], "version": 1}
        path = "/hypotheses/new?idea_id=IDE-11111111-1111-4111-8111-111111111111&idea_version=1"
        with patch("rms.navigation_views.exact_idea", return_value=idea):
            client, form, token = self.fresh_editor_form(path)
        self.assertIn("csrftoken", form.cookies)
        self.assertEqual(form["Cache-Control"], "private, no-store")
        data = {**flatten_input(self.create_payload()), "csrfmiddlewaretoken": token,
                "operation": "save", "idempotency_key": "invented-fresh-csrf-key"}
        with patch.object(hypothesis_services, "create_hypothesis", return_value=StoredResponse(201, json.dumps(self.record).encode())) as save:
            response = client.post(path, data, secure=True, HTTP_ORIGIN="https://private.example.invalid:4443")
        self.assertEqual(response.status_code, 303)
        save.assert_called_once()
        self.assertEqual(save.call_args.kwargs["idempotency_key"], data["idempotency_key"])
        self.assertEqual(validate_request("HypothesisCreate", save.call_args.kwargs["payload"]),
                         validate_request("HypothesisCreate", self.create_payload()))

    @override_settings(MIDDLEWARE=[])
    def test_fresh_shared_editor_forms_issue_cookie(self):
        for path in ("/hypotheses/new", "/research-families/new", "/investigations/new"):
            with self.subTest(path=path):
                _, response, _ = self.fresh_editor_form(path)
                self.assertIn("csrftoken", response.cookies)
        with patch.object(hypothesis_services, "get_hypothesis", return_value=self.record), patch("rms.navigation_views.exact_idea", return_value={"version": 1}):
            _, response, _ = self.fresh_editor_form(f"/hypotheses/{self.record['hypothesis_id']}/revise")
        self.assertIn("csrftoken", response.cookies)

    @override_settings(MIDDLEWARE=[])
    def test_fresh_form_still_rejects_missing_cookie_and_bad_token(self):
        for mode in ("missing_cookie", "bad_token"):
            with self.subTest(mode=mode):
                client, _, token = self.fresh_editor_form()
                if mode == "missing_cookie":
                    client.cookies.clear()
                else:
                    token = "A" * 64 if token != "A" * 64 else "B" * 64
                data = {**flatten_input(self.create_payload()), "csrfmiddlewaretoken": token}
                with patch.object(hypothesis_services, "create_hypothesis") as save:
                    response = client.post("/hypotheses/new", data, secure=True, HTTP_ORIGIN="https://testserver")
                self.assertEqual(response.status_code, 403)
                save.assert_not_called()

    @override_settings(MIDDLEWARE=[], CSRF_TRUSTED_ORIGINS=["https://private.example.invalid:4443"])
    def test_fresh_form_still_rejects_foreign_origin_and_referer(self):
        for headers in ({"HTTP_ORIGIN": "https://foreign.example.invalid"},
                        {"HTTP_REFERER": "https://foreign.example.invalid/hypotheses/new"}):
            with self.subTest(headers=headers):
                client, _, token = self.fresh_editor_form()
                data = {**flatten_input(self.create_payload()), "csrfmiddlewaretoken": token}
                with patch.object(hypothesis_services, "create_hypothesis") as save:
                    response = client.post("/hypotheses/new", data, secure=True, **headers)
                self.assertEqual(response.status_code, 403)
                save.assert_not_called()

    def test_unconfirmed_save_retains_original_key_and_input(self):
        with patch.object(hypothesis_services, "create_hypothesis", side_effect=DatabaseError("Invented private database diagnostic")):
            response = self.submit(self.create_payload())
        html = self.render(response)
        self.assertEqual(response.status_code, 503)
        self.assertIn('name="idempotency_key" value="invented-fixed-request-key"', html)
        self.assertIn("  Invented draft  ", html)
        self.assertIn("save outcome could not be confirmed", html)
        self.assertNotIn("Invented private database diagnostic", html)

    def test_missing_schema_keeps_escaped_submitted_input_without_guessed_controls(self):
        from rms.navigation_views import SchemaUnavailable
        payload = self.create_payload()
        payload["fields"]["claim"] = "<script>invented()</script>"
        with patch("rms.navigation_views.read_navigation_schema", side_effect=SchemaUnavailable("Invented private schema path")), patch.object(hypothesis_services, "create_hypothesis") as save:
            response = self.submit(payload)
        html = self.render(response)
        self.assertEqual(response.status_code, 503)
        self.assertIn("Unsaved submitted input", html)
        self.assertIn("&lt;script&gt;invented()&lt;/script&gt;", html)
        self.assertNotIn("Invented private schema path", html)
        save.assert_not_called()

    def test_family_case_and_assessment_detail_use_exact_shared_readers(self):
        assessment = self.case["prior_research_assessment"]
        for kind, name, record, identity in (("family", "get_research_family", self.family, self.family["family_id"]), ("case", "get_investigation", self.case, self.case["investigation_id"]), ("assessment", "get_prior_research_assessment", assessment, assessment["assessment_id"])):
            with self.subTest(kind=kind), patch.object(research_context_services, name, return_value=record) as read:
                response = RecordDetailPage.as_view(kind=kind)(self.request(actor=invented_actor("founder_viewer")), record_id=identity, version=1)
                html = self.render(response)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(read.call_args.kwargs["version"], 1)
                self.assertNotIn("/revise", html)
                if kind == "case":
                    self.assertIn("/prior-research-assessments/", html)

    def test_idea_detail_links_creation_history_and_permitted_hypotheses(self):
        identity = self.record["origin"]["idea"]["stable_id"]
        detail = {"idea_id": identity, "latest_version": 1, "latest_idea_version_id": self.record["origin"]["idea"]["version_id"], "latest": {"version": 1, "title": "Invented originating Idea", "contributions": []}}
        with patch("rms.views.get_idea"), patch("rms.views.idea_detail", return_value=detail), patch.object(hypothesis_services, "list_hypotheses", return_value=listing([self.record])) as read:
            response = IdeaDetailPage.as_view()(self.request(path="/ideas/" + identity), idea_id=identity)
        self.assertEqual(read.call_args.kwargs["query"], {"originating_idea_id": identity})
        html = self.render(response)
        self.assertIn("/hypotheses/new?idea_id=" + identity + "&amp;idea_version=1", html)
        self.assertIn("Permitted linked records: 1", html)
        self.assertIn("/ideas/" + identity + "/history", html)
        self.assertIn('href="/ideas" aria-current="page"', html)

    def test_rendered_form_ids_and_labels_cover_all_visible_controls(self):
        class Structure(HTMLParser):
            def __init__(self):
                super().__init__()
                self.ids, self.labels, self.controls = [], set(), []
                self.inside_label = False
            def handle_starttag(self, tag, attributes):
                values = dict(attributes)
                if "id" in values:
                    self.ids.append(values["id"])
                if tag == "label":
                    self.inside_label = True
                    if "for" in values:
                        self.labels.add(values["for"])
                if tag in ("input", "select", "textarea") and values.get("type") != "hidden":
                    self.controls.append((values.get("id"), self.inside_label))
            def handle_endtag(self, tag):
                if tag == "label":
                    self.inside_label = False
        parser = Structure()
        parser.feed(self.render(RecordEditorPage.as_view()(self.request())))
        self.assertEqual(len(parser.ids), len(set(parser.ids)))
        self.assertGreater(len(parser.controls), 50)
        self.assertTrue(all(wrapped or identity in parser.labels for identity, wrapped in parser.controls))

    def test_uniform_hidden_and_missing_detail_does_not_leak(self):
        with patch.object(hypothesis_services, "get_hypothesis", side_effect=ResourceNotFound):
            response = RecordDetailPage.as_view()(self.request(), record_id=self.record["hypothesis_id"])
        self.assertEqual(response.status_code, 404)
        self.assertNotIn(self.record["hypothesis_id"], self.render(response))

    def test_exact_detail_links_pinned_versions_and_viewer_has_no_edit(self):
        viewer = invented_actor("founder_viewer")
        with patch.object(hypothesis_services, "get_hypothesis", return_value=self.record) as read:
            response = RecordDetailPage.as_view()(self.request(actor=viewer), record_id=self.record["hypothesis_id"], version=1)
        html = self.render(response)
        self.assertEqual(read.call_args.kwargs["version"], 1)
        self.assertIn("Exact historical version 1", html)
        self.assertIn("history#idea-version-1", html)
        self.assertIn("history#source-version-1", html)
        self.assertIn("/research-families/" + self.family["family_id"] + "/versions/1", html)
        self.assertIn("/prior-research-assessments/", html)
        self.assertNotIn("Revise hypothesis", html)
        self.assertNotIn("supplied record preview", html)

    def test_history_keeps_old_and_corrected_snapshots(self):
        newer = deepcopy(self.record)
        newer.update(version=2, corrects_version=1, correction_reason="Invented correction", changed_fields=["/fields/title"])
        newer["fields"]["title"] = "Invented new title"
        with patch.object(hypothesis_services, "get_hypothesis_history", return_value={"results": [self.record, newer]}):
            response = RecordHistoryPage.as_view()(self.request(), record_id=self.record["hypothesis_id"])
        html = self.render(response)
        self.assertIn("Open exact version 1", html)
        self.assertIn("Open exact version 2", html)
        self.assertIn("Invented hypothesis", html)
        self.assertIn("Invented new title", html)
        self.assertIn("Corrects v1: Invented correction", html)

    def test_selection_uses_shared_authorized_counts_and_query_parser(self):
        result = {**listing([self.record], page=2), "count": 28, "next": "/api/v1/hypotheses?page=3&page_size=25", "previous": "/api/v1/hypotheses?page=1&page_size=25"}
        with patch.object(hypothesis_services, "list_hypotheses", return_value=result) as read:
            response = NavigationPage.as_view(section="hypotheses")(self.request(path="/hypotheses?page=2"))
        self.assertEqual(read.call_args.kwargs["query"], {"page": 2})
        html = self.render(response)
        self.assertIn("Permitted records: 28", html)
        self.assertIn('/hypotheses?page=3&amp;page_size=25', html)

    def test_invalid_duplicate_unknown_queries_reuse_api_errors(self):
        for query in ("page=02", "page=1&page=2", "unrecognized=secret"):
            with patch.object(hypothesis_services, "list_hypotheses", side_effect=HypothesisValidationError([{"path": "", "message": "Invented invalid query"}])) as read:
                response = NavigationPage.as_view(section="hypotheses")(self.request(path="/hypotheses?" + query))
            self.assertEqual(response.status_code, 400)
            self.assertNotIn("secret", self.render(response))
            if not query.startswith("unrecognized"):
                read.assert_not_called()

    def test_routes_resolve_exact_versions_without_registering_root(self):
        for route in ("hypotheses", "research-families", "investigations"):
            for suffix in ("new", "invented/history", "invented/versions/1", "invented/revise"):
                resolve("/" + route + "/" + suffix, urlconf="rms.navigation_urls")
        resolve("/prior-research-assessments/invented/versions/1", urlconf="rms.navigation_urls")

    def test_create_get_renders_real_form_and_explicit_selection_without_defaults(self):
        response = RecordEditorPage.as_view()(self.request())
        html = self.render(response)
        self.assertEqual(response.status_code, 200)
        self.assertIn('method="post" data-record-form', html)
        self.assertIn('name="csrfmiddlewaretoken"', html)
        self.assertIn("Create and select family", html)
        self.assertIn("Create and select case", html)
        self.assertIn(self.case["investigation_version_id"], html)
        self.assertIn("Choose explicitly — no default", html)
        self.assertNotIn('value="create" selected', html)

    def test_denied_lists_return_no_counts_or_private_title(self):
        with patch.object(hypothesis_services, "list_hypotheses") as read:
            response = NavigationPage.as_view(section="hypotheses")(self.request(actor=invented_actor("unassigned")))
        read.assert_not_called()
        self.assertEqual(response.status_code, 403)
        self.assertNotIn("Permitted records:", self.render(response))
