"""Request and rendering coverage, without database or deployment access."""

from base64 import b64encode
from dataclasses import replace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase, override_settings
from django.urls import reverse

from rms.dashboard_projection import DashboardSourceUnavailable
from rms.dashboard_views import FounderDashboardPage
from tests.dashboard_fixtures import InventedDashboardProvider


@override_settings(AUTHENTICATION_BACKENDS=["tests.dashboard_fixtures.FixtureAuthenticationBackend"])
class FounderDashboardTests(SimpleTestCase):
    def setUp(self):
        self.route = reverse("rms-founder-dashboard")

    def request(self, role="founder_viewer", method="get", path=None, query=None):
        token = b64encode(f"{role}:invented-dashboard-only".encode()).decode()
        return getattr(self.client, method)(path or self.route, query or {}, HTTP_AUTHORIZATION=f"Basic {token}")

    def ledger_text(self, response, key):
        html = response.content.decode()
        return html.split(f'<h3 id="ledger-{key}">', 1)[1].split("</section>", 1)[0]

    def test_home_link_is_an_ordinary_authorized_entry_point(self):
        with (
            patch("rms.navigation_views.shared_service", return_value={"count": 0, "results": []}),
            patch("rms.test_plan_views.plan_service", return_value={"count": 0, "results": []}),
        ):
            for role in ("editor", "founder_viewer"):
                self.assertContains(self.request(role, path="/"), f'<a href="{self.route}">Founder dashboard</a>', html=True)
            self.assertNotContains(self.request("unassigned", path="/"), self.route, status_code=403)

    def test_denied_roles_and_anonymous_do_not_invoke_any_provider(self):
        provider = Mock(spec=InventedDashboardProvider)
        with patch.object(FounderDashboardPage, "provider", provider):
            for response, status in ((self.client.get(self.route), 401),
                                     (self.request("unassigned"), 403), (self.request("inactive"), 401)):
                self.assertContains(response, "Access required", status_code=status)
                self.assertNotContains(response, "Workflow ledgers", status_code=status)
                self.assertEqual(response["Cache-Control"], "private, no-store")
                self.assertIn("Authorization", response["Vary"])
            self.assertEqual(provider.mock_calls, [])

    def test_real_configuration_reports_all_missing_sources_as_unknown(self):
        response = self.request()
        self.assertContains(response, "Pipeline source unavailable")
        self.assertContains(response, "Source unavailable. Count unknown.", count=4)
        self.assertNotContains(response, "Visible invented examples:")
        self.assertNotContains(response, "Real credit from these examples:")

    def test_decision_reference_is_plain_text_without_deployment_configuration(self):
        self.assertContains(
            self.request(),
            "<p>Stage 2 scope and decisions in Paperclip: MAU-33.</p>",
            html=True,
        )

    def test_invented_cases_show_escaped_text_age_and_uncertainty(self):
        with patch.object(FounderDashboardPage, "provider", InventedDashboardProvider()):
            response = self.request()
        for text in ("Invented maple case", "Casey Example", "Plan review", "2\u00a0days", "Quarantined fixture evidence",
                     "Check &lt;sample&gt; provenance", "Not eligible for review", "Manual approval (information only)",
                     "2026-11-20T18:00:00+00:00", "fixture-policy-1", "Stage 2 scope and decisions in Paperclip"):
            self.assertContains(response, text)
        for text in ("<sample>", "<form", 'aria-current="page"', "Editor-only spruce example", "Hidden"):
            self.assertNotContains(response, text)

    def test_scope_and_counts_are_independent_and_cannot_be_expanded_by_query(self):
        with patch.object(FounderDashboardPage, "provider", InventedDashboardProvider()):
            viewer = self.request(query={"role": "editor", "scope": "all", "actor": "unassigned"})
            editor = self.request("editor")
        self.assertNotContains(viewer, "Editor-only spruce example")
        self.assertContains(editor, "Editor-only spruce example")
        self.assertContains(editor, "<dt>Owner</dt><dd>Unknown</dd>", html=True)
        for response, counts in ((viewer, (2, 0, 5, 1)), (editor, (3, 1, 5, 3))):
            self.assertNotContains(response, "Hidden")
            self.assertEqual(response["Cache-Control"], "private, no-store")
            self.assertIn("Authorization", response["Vary"])
            for (key, version), expected in zip((
                ("activity", "act-2"), ("early_closures", "close-3"),
                ("full_validation", "cycle-4"), ("qualifications", "qual-5"),
            ), counts, strict=True):
                section = self.ledger_text(response, key)
                self.assertIn(f"Visible invented examples: {expected}</p>", section)
                self.assertIn(version, section)
                self.assertEqual("Real credit from these examples: 0" in section,
                                 key in {"full_validation", "qualifications"})

    def test_independent_outage_stale_and_empty_states(self):
        class PartialProvider(InventedDashboardProvider):
            def pipeline(self, *, actor):
                snapshot = super().pipeline(actor=actor)
                return replace(snapshot, cases=(), watermark=replace(snapshot.watermark, freshness="stale"))

            def early_closures(self, *, actor):
                raise DashboardSourceUnavailable("internal connector sentinel")

            def full_validation(self, *, actor):
                snapshot = super().full_validation(actor=actor)
                return replace(snapshot, watermark=replace(snapshot.watermark, freshness="stale"))

            def qualifications(self, *, actor):
                return None

        with patch.object(FounderDashboardPage, "provider", PartialProvider()):
            response = self.request()
        self.assertContains(response, "No cases are available to display in this snapshot")
        self.assertContains(response, "Stale snapshot")
        self.assertNotContains(response, "internal connector sentinel")
        self.assertIn("Visible invented examples: 2", self.ledger_text(response, "activity"))
        self.assertIn("Source unavailable. Count unknown.", self.ledger_text(response, "early_closures"))
        self.assertIn("Source unavailable. Count unknown.", self.ledger_text(response, "qualifications"))
        cycle = self.ledger_text(response, "full_validation")
        self.assertIn("Current count unavailable", cycle)
        self.assertIn("Stale", cycle)
        self.assertNotIn("Visible invented examples", cycle)
        self.assertNotContains(response, "Real credit from these examples:")

    def test_mutation_methods_do_not_invoke_provider_for_either_allowed_role(self):
        provider = Mock(spec=InventedDashboardProvider)
        with patch.object(FounderDashboardPage, "provider", provider):
            for role in ("editor", "founder_viewer"):
                self.assertEqual(self.request(role, method="post").status_code, 405)
        self.assertEqual(provider.mock_calls, [])
