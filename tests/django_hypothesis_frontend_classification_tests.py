"""Invented classification service/render checks; all persistence is mocked."""

from copy import deepcopy
import json
from unittest.mock import patch

from django.db import DatabaseError
from django.test import SimpleTestCase
from django.urls import resolve
from rms import hypothesis_api, hypothesis_services, research_context_services as services
from rms.hypothesis_validation import HypothesisValidationError, validate_request
from rms.navigation_views import (
    ClassificationLookupPage, RecordDetailPage, RecordEditorPage, RecordHistoryPage,
    flatten_input, revision_snapshot, read_navigation_schema,
)
from rms.research_context_common import StaleVersion
from rms.services import ResourceNotFound, StoredResponse, ServiceError
from tests import django_hypothesis_frontend_integration_tests as fixtures
from tests.django_hypothesis_frontend_integration_tests import invented_actor


class ClassificationFrontendTests(SimpleTestCase):
    # Reuse invented fixture/request builders without inheriting their test cases.
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.schema = read_navigation_schema()

    assessment_fields = fixtures.ConnectedFrontendTests.assessment_fields
    request = fixtures.ConnectedFrontendTests.request
    submit = fixtures.ConnectedFrontendTests.submit
    render = fixtures.ConnectedFrontendTests.render
    create_payload = fixtures.ConnectedFrontendTests.create_payload

    def setUp(self):
        fixtures.ConnectedFrontendTests.setUp(self)
        self.classification = {
            "stable_id": "IFA-11111111-1111-4111-8111-111111111111",
            "version_id": "IFAV-22222222-2222-4222-8222-222222222222",
            "version": 2, "schema_version": "1.0", "classification": "synthetic",
            "kind": "IdeaFamily", "state": "proposed",
            "from": deepcopy(self.record["origin"]["idea"]),
            "to": deepcopy(self.record["research_context"]["family"]),
            "rationale": "Invented corrected grouping <script>unsafe()</script>",
            "created_at": "2026-10-03T12:00:00Z", "created_by": "Invented editor",
            "recorded_at": "2026-10-03T12:00:00Z", "corrects_version": 1,
            "correction_reason": "Invented reclassification reason",
            "supersedes_version_id": "IFAV-11111111-1111-4111-8111-111111111111",
            "changed_fields": ["/rationale"], "links": {},
        }
        self.identity = self.classification["stable_id"]

    def test_lookup_shared_exact_idea_reader_and_current_render(self):
        query = {"idea_version_id": self.classification["from"]["version_id"]}
        with patch.object(services, "get_idea_family_for_idea", return_value=self.classification) as reader:
            response = ClassificationLookupPage.as_view()(self.request(data=query, path="/idea-family-associations"))
        reader.assert_called_once_with(actor=self.actor, **query)
        html = self.render(response)
        self.assertEqual(response.status_code, 200)
        self.assertIn(self.identity + "/versions/2", html)
        self.assertIn(self.identity + "/history", html)
        self.assertIn(self.identity + "/revise", html)
        self.assertIn("&lt;script&gt;unsafe()&lt;/script&gt;", html)
        self.assertIn("does not change a Hypothesis citation", html)
        self.assertEqual(response["Cache-Control"], "private, no-store")

    def test_empty_lookup_does_not_infer_classification_or_count(self):
        with patch.object(services, "get_idea_family_for_idea") as reader:
            response = ClassificationLookupPage.as_view()(self.request())
        reader.assert_not_called()
        self.assertNotIn("record", response.context_data)
        self.assertIn("absence is not proof", self.render(response))

    def test_lookup_reuses_duplicate_unknown_and_missing_query_validation(self):
        for query in ("?idea_version_id=x&idea_version_id=y", "?page=1", "?idea_version_id=unknown", "?idea_version_id=" ):
            with self.subTest(query=query), patch.object(services, "get_idea_family_for_idea") as reader:
                response = ClassificationLookupPage.as_view()(self.request(path="/idea-family-associations" + query))
                self.assertEqual(response.status_code, 400)
                reader.assert_not_called()

    def test_current_and_exact_readers_receive_distinct_versions(self):
        for version in (None, 2):
            with self.subTest(version=version), patch.object(services, "get_idea_family_association", return_value=self.classification) as reader:
                response = RecordDetailPage.as_view(kind="classification")(self.request(), record_id=self.identity, version=version)
                reader.assert_called_once_with(actor=self.actor, association_id=self.identity, version=version)
                self.assertEqual(response.context_data["historical"], version is not None)
                html = self.render(response)
                self.assertIn("#idea-version-1", html)
                self.assertIn("/research-families/" + self.family["family_id"] + "/versions/1", html)

    def test_history_preserves_order_predecessor_reason_and_exact_endpoints(self):
        original = {**self.classification, "version": 1, "version_id": self.classification["supersedes_version_id"], "corrects_version": None, "correction_reason": None, "supersedes_version_id": None, "rationale": "Invented original grouping"}
        with patch.object(services, "get_idea_family_association_history", return_value={"results": [original, self.classification]}) as reader:
            response = RecordHistoryPage.as_view(kind="classification")(self.request(), record_id=self.identity)
        reader.assert_called_once_with(actor=self.actor, association_id=self.identity)
        html = self.render(response)
        self.assertLess(html.index('id="record-version-1"'), html.index('id="record-version-2"'))
        self.assertIn("Original version", html)
        self.assertIn("Corrects v1: Invented reclassification reason", html)
        self.assertIn(self.classification["supersedes_version_id"], html)

    def test_revision_get_restates_the_exact_snapshot_and_readonly_idea(self):
        with patch.object(services, "get_idea_family_association", return_value=self.classification):
            response = RecordEditorPage.as_view(kind="classification")(self.request(), record_id=self.identity)
        controls = {c["path"]: c["value"] for g in response.context_data["field_groups"] for c in g["controls"]}
        for path, value in flatten_input(revision_snapshot("classification", self.classification)).items():
            self.assertEqual(controls[path], value)
        self.assertIn(self.classification["from"]["version_id"], self.render(response))

    def test_correction_success_api_browser_payload_parity_and_exact_redirect(self):
        payload = revision_snapshot("classification", self.classification)
        payload["correction_reason"] = "Invented next correction"
        stored = StoredResponse(201, json.dumps(self.classification).encode())
        with patch.object(services, "correct_idea_family_association", return_value=stored) as save:
            response = self.submit(payload, kind="classification", record_id=self.identity)
            browser_args = save.call_args.kwargs
            request = self.factory.post("/api/v1/idea-family-associations/" + self.identity + "/corrections", data=json.dumps(payload), content_type="application/json; charset=utf-8", HTTP_IDEMPOTENCY_KEY="invented-fixed-request-key")
            from rest_framework.test import force_authenticate
            force_authenticate(request, user=self.actor)
            api = hypothesis_api.ResearchRecordView.as_view(resource="idea-family-associations", action="correction")(request, record_id=self.identity)
            self.assertEqual(save.call_args.kwargs, browser_args)
        self.assertEqual(validate_request("IdeaFamilyCorrection", browser_args["payload"]), validate_request("IdeaFamilyCorrection", payload))
        self.assertEqual(response.status_code, 303)
        self.assertEqual(api.status_code, 201)
        self.assertEqual(response["Location"], "/idea-family-associations/" + self.identity + "/versions/2")

    def test_correction_conflict_and_validation_keep_losing_input_and_focus(self):
        payload = revision_snapshot("classification", self.classification)
        payload["rationale"] = "Invented losing <script>text</script>"
        for error, status in ((StaleVersion(), 409), (HypothesisValidationError([{"path": "/rationale", "code": "invalid", "message": "Invented server rationale error"}]), 400)):
            with self.subTest(status=status), patch.object(services, "correct_idea_family_association", side_effect=error):
                response = self.submit(payload, kind="classification", record_id=self.identity)
                html = self.render(response)
                self.assertEqual(response.status_code, status)
                self.assertIn("Invented losing &lt;script&gt;text&lt;/script&gt;", html)
                self.assertIn("data-error-summary", html)
                self.assertIn(payload["prior_association_version_id"], html)

    def test_browser_denies_all_readers_before_service_and_viewer_has_no_revision_link(self):
        for actor, status in ((False, 401), (invented_actor("unassigned"), 403), (invented_actor(active=False), 403)):
            with self.subTest(status=status), patch.object(services, "get_idea_family_association") as reader, patch.object(services, "get_idea_family_for_idea") as lookup:
                response = RecordDetailPage.as_view(kind="classification")(self.request(actor=actor), record_id=self.identity)
                self.assertEqual(response.status_code, status)
                response = ClassificationLookupPage.as_view()(self.request(data={"idea_version_id": self.classification["from"]["version_id"]}, actor=actor))
                self.assertEqual(response.status_code, status)
                reader.assert_not_called()
                lookup.assert_not_called()
        with patch.object(services, "get_idea_family_association", return_value=self.classification):
            response = RecordDetailPage.as_view(kind="classification")(self.request(actor=invented_actor("founder_viewer")), record_id=self.identity)
        self.assertNotIn(self.identity + "/revise", self.render(response))
        with patch.object(services, "correct_idea_family_association") as save:
            response = self.submit(revision_snapshot("classification", self.classification), kind="classification", record_id=self.identity, actor=invented_actor("founder_viewer"))
            self.assertEqual(response.status_code, 403)
            save.assert_not_called()

    def test_classification_missing_and_restricted_lookup_use_uniform_not_found(self):
        with patch.object(services, "get_idea_family_for_idea", side_effect=ResourceNotFound):
            response = ClassificationLookupPage.as_view()(self.request(data={"idea_version_id": self.classification["from"]["version_id"]}))
        self.assertEqual(response.status_code, 404)
        self.assertNotIn(self.identity, self.render(response))

    def test_inspection_keeps_old_draft_binding_all_input_and_calls_no_write(self):
        payload = self.create_payload()
        with patch.object(services, "get_idea_family_for_idea", return_value=self.classification), patch.object(hypothesis_services, "create_hypothesis") as save:
            response = self.submit(payload, operation="lookup_classification", extra={"/context/case/fields/title": "Unfinished invented case"})
        save.assert_not_called()
        html = self.render(response)
        self.assertIn(payload["idea_family_binding"]["association_version_id"], html)
        self.assertIn("Unfinished invented case", html)
        self.assertIn("binding has not changed", html)
        self.assertIn('value="adopt_classification"', html)
        self.assertEqual(response.context_data["idempotency_key"], "invented-fixed-request-key")

    def test_explicit_selection_authorizes_exact_reader_and_changes_only_binding_branch(self):
        payload = self.create_payload()
        payload["idea_family_binding"] = {"mode": "create", "family_version_id": self.family["family_version_id"], "rationale": "Unused first assignment"}
        extra = {"classification_id": self.identity, "classification_version": "2", "confirm_first_family": "yes", "/context/case/fields/title": "Unfinished invented case"}
        with patch.object(services, "get_idea_family_association", return_value=self.classification) as reader, patch.object(hypothesis_services, "create_hypothesis") as save:
            response = self.submit(payload, operation="adopt_classification", extra=extra)
        reader.assert_called_once_with(actor=self.actor, association_id=self.identity, version=2)
        save.assert_not_called()
        values = {c["path"]: c["value"] for g in response.context_data["field_groups"] for c in g["controls"]}
        self.assertEqual(values["/idea_family_binding/mode"], "existing")
        self.assertEqual(values["/idea_family_binding/association_version_id"], self.classification["version_id"])
        self.assertEqual(values["/idea_family_binding/family_version_id"], "")
        self.assertEqual(values["/originating_idea_version_id"], payload["originating_idea_version_id"])
        self.assertEqual(values["/investigation_version_id"], payload["investigation_version_id"])
        self.assertFalse(response.context_data["confirm_first_family"])
        self.assertIn("Unfinished invented case", self.render(response))

    def test_lookup_or_selection_failure_retains_every_draft_binding_and_input(self):
        for error, status in ((ResourceNotFound(), 404), (DatabaseError(), 503), (StaleVersion(), 409)):
            with self.subTest(status=status), patch.object(services, "get_idea_family_for_idea", side_effect=error):
                payload = self.create_payload()
                response = self.submit(payload, operation="lookup_classification")
                self.assertEqual(response.status_code, status)
                html = self.render(response)
                self.assertIn(payload["idea_family_binding"]["association_version_id"], html)
                self.assertIn(payload["fields"]["title"], html)
                self.assertNotIn('value="adopt_classification"', html)

    def test_explicit_selection_invalid_version_does_not_read_or_drop_input(self):
        with patch.object(services, "get_idea_family_association") as reader:
            response = self.submit(self.create_payload(), operation="adopt_classification", extra={"classification_version": "invalid"})
        self.assertEqual(response.status_code, 400)
        reader.assert_not_called()
        self.assertIn("  Invented draft  ", self.render(response))

    def test_hypothesis_exact_detail_links_pinned_classification_without_lookup(self):
        self.record["upstream_notices"] = [{"pinned": {"stable_id": self.identity, "version_id": self.classification["supersedes_version_id"], "version": 1}, "newer": {"stable_id": self.identity, "version_id": self.classification["version_id"], "version": 2}, "impact_version_id": "Invented impact"}]
        with patch.object(hypothesis_services, "get_hypothesis", return_value=self.record), patch.object(services, "get_idea_family_for_idea") as lookup:
            response = RecordDetailPage.as_view()(self.request(), record_id=self.record["hypothesis_id"], version=1)
        lookup.assert_not_called()
        html = self.render(response)
        self.assertIn("/idea-family-associations/" + self.identity + "/versions/1", html)
        self.assertIn("/idea-family-associations/" + self.identity + "/versions/2", html)
        self.assertIn("This citation remains pinned", html)

    def test_read_failure_and_integrity_error_keep_503_without_success_or_conflict(self):
        class InventedIntegrityError(ServiceError):
            http_status = 503
        with patch.object(services, "get_idea_family_association", side_effect=DatabaseError):
            response = RecordDetailPage.as_view(kind="classification")(self.request(), record_id=self.identity)
        self.assertEqual(response.status_code, 503)
        with patch.object(services, "correct_idea_family_association", side_effect=InventedIntegrityError):
            response = self.submit(revision_snapshot("classification", self.classification), kind="classification", record_id=self.identity)
        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.context_data["conflict"])
        self.assertEqual(response.context_data["idempotency_key"], "invented-fixed-request-key")
        self.assertIn("could not confirm a save", self.render(response))

    def test_routes_cover_current_exact_history_revision_and_lookup_no_create(self):
        for tail, name in (("", "detail"), ("/versions/2", "version"), ("/history", "history"), ("/revise", "revise")):
            match = resolve("/idea-family-associations/" + self.identity + tail, urlconf="rms.navigation_urls")
            self.assertEqual(match.url_name, "rms-classification-" + name)
        self.assertEqual(resolve("/idea-family-associations", urlconf="rms.navigation_urls").url_name, "rms-classification-lookup")
        self.assertFalse(any(p.name == "rms-classification-create" for p in __import__("rms.navigation_urls", fromlist=["urlpatterns"]).urlpatterns))
