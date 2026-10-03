"""Director composition checks with invented readers and no database lifecycle."""

from unittest.mock import patch
import json

from django.db import DatabaseError
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.urls import resolve, reverse
from rest_framework.test import force_authenticate

from rms import api, hypothesis_services
from rms.hypothesis_api import ResearchRecordView
from rms.navigation_views import (
    NavigationPage, RecordDetailPage, RecordEditorPage, RecordHistoryPage,
    SchemaUnavailable,
)
from rms.research_context_common import AuthenticationRequired, Forbidden
from rms.services import ResourceNotFound, ServiceError
from rms.views import IdeaDetailPage, IdeaHistoryPage, SourceHistoryPage
from tests.django_hypothesis_frontend_integration_tests import invented_actor


class DirectorIntegrationTests(SimpleTestCase):
    @override_settings(CSRF_TRUSTED_ORIGINS=["https://private.example.invalid:4443"])
    def test_private_browser_origin_and_csrf_token_survive_adapter_host_rewrite(self):
        from django.middleware.csrf import get_token
        from rms.navigation_views import flatten_input, read_navigation_schema
        from rms.services import StoredResponse
        from tests.django_hypothesis_frontend_integration_tests import ConnectedFrontendTests
        fixture = ConnectedFrontendTests()
        fixture.schema = read_navigation_schema()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        seed = fixture.factory.get("/hypotheses/new")
        token = get_token(seed)
        for origin, status in (("https://private.example.invalid:4443", 303), ("https://other.example.invalid:4443", 403)):
            data = {**flatten_input(fixture.create_payload()), "csrfmiddlewaretoken": token, "idempotency_key": "invented-origin-check"}
            request = fixture.factory.post("/hypotheses/new", data, HTTP_HOST="localhost", HTTP_ORIGIN=origin)
            request._dont_enforce_csrf_checks = False
            request.COOKIES["csrftoken"] = seed.META["CSRF_COOKIE"]
            force_authenticate(request, user=invented_actor())
            with self.subTest(origin=origin), patch.object(hypothesis_services, "create_hypothesis", return_value=StoredResponse(201, json.dumps(fixture.record).encode())) as save:
                response = resolve(request.path).func(request)
                self.assertEqual(response.status_code, status)
                self.assertEqual(save.called, status == 303)

    @override_settings(RMS_DEPLOYED_COMMIT="a" * 40)
    def test_navigation_uses_the_validated_runtime_release_identity(self):
        from django.template.loader import render_to_string
        from rms.navigation_views import navigation_context
        html = render_to_string("rms/navigation.html", {**navigation_context(role="founder_viewer"), "heading": "Home"})
        self.assertIn("a" * 40, html)
        self.assertNotIn("not a deployed release", html)

    def test_actual_root_mounts_browser_and_api_without_shadowing_legacy_routes(self):
        routes = {
            "/": NavigationPage,
            "/sources": NavigationPage,
            "/ideas": NavigationPage,
            "/hypotheses": NavigationPage,
            "/research-context": NavigationPage,
            "/hypotheses/new": RecordEditorPage,
            "/research-families/new": RecordEditorPage,
            "/investigations/new": RecordEditorPage,
            "/hypotheses/HYP-invented/history": RecordHistoryPage,
            "/hypotheses/HYP-invented/versions/1": RecordDetailPage,
            "/api/v1/hypotheses": ResearchRecordView,
            "/api/v1/research-families": ResearchRecordView,
            "/api/v1/investigations": ResearchRecordView,
            "/api/v1/sources": api.SourceCreateView,
            "/api/v1/ideas": api.IdeaCreateView,
            "/sources/FIC-INVENTED/history": SourceHistoryPage,
            "/ideas/IDE-invented": IdeaDetailPage,
            "/ideas/IDE-invented/history": IdeaHistoryPage,
        }
        for path, expected in routes.items():
            with self.subTest(path=path):
                self.assertIs(resolve(path).func.view_class, expected)
        self.assertEqual(reverse("rms-home"), "/")
        self.assertEqual(reverse("source-create"), "/api/v1/sources")
        self.assertEqual(reverse("idea-create"), "/api/v1/ideas")

    def idea_page(self, actor, error):
        idea_id = "IDE-11111111-1111-4111-8111-111111111111"
        detail = {
            "idea_id": idea_id, "latest_version": 1,
            "latest_idea_version_id": "IDEV-11111111-1111-4111-8111-111111111111",
            "latest": {"version": 1, "title": "Invented private Idea title", "contributions": []},
        }
        request = RequestFactory().get("/ideas/" + idea_id)
        force_authenticate(request, user=actor)
        view = resolve(request.path).func
        with patch("rms.views.get_idea"), patch("rms.views.idea_detail", return_value=detail), patch.object(hypothesis_services, "list_hypotheses", side_effect=error):
            response = view(request, idea_id=idea_id)
        response.render()
        return response, response.content.decode()

    def test_idea_detail_failures_preserve_status_navigation_and_non_disclosure(self):
        cases = (
            (ResourceNotFound(), 404, False),
            (Forbidden(), 403, False),
            (AuthenticationRequired(), 401, False),
            (ServiceError("PRIVATE diagnostic"), 409, False),
            (DatabaseError("PRIVATE diagnostic"), 200, True),
            (SchemaUnavailable("PRIVATE diagnostic"), 200, True),
        )
        for role in ("editor", "founder_viewer"):
            for error, status, show_idea in cases:
                with self.subTest(role=role, error=type(error).__name__):
                    response, html = self.idea_page(invented_actor(role), error)
                    self.assertEqual(response.status_code, status)
                    self.assertIn('href="/"', html)
                    self.assertNotIn("PRIVATE diagnostic", html)
                    self.assertEqual("Invented private Idea title" in html, show_idea)
                    self.assertEqual(response["Cache-Control"], "private, no-store")
                    if status == 401:
                        self.assertIn("WWW-Authenticate", response)
                    if show_idea:
                        self.assertIn("the count is unknown", html)
                        self.assertNotIn("Permitted linked records: 0", html)

    def test_idea_denial_precedes_detail_and_linked_reader(self):
        request = RequestFactory().get("/ideas/IDE-11111111-1111-4111-8111-111111111111")
        force_authenticate(request, user=invented_actor("unassigned"))
        with patch("rms.views.get_idea") as detail, patch.object(hypothesis_services, "list_hypotheses") as linked:
            response = resolve(request.path).func(request, idea_id=request.path.split("/")[-1])
        self.assertEqual(response.status_code, 403)
        detail.assert_not_called()
        linked.assert_not_called()
        response.render()
        self.assertIn('href="/"', response.content.decode())
