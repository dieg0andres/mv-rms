"""Request/rendering checks for the bounded RR14 frontend handoff."""

from base64 import b64encode
from unittest.mock import patch

from django.db import DatabaseError
from django.test import SimpleTestCase, override_settings
from django.urls import reverse

from rms.services import ResourceNotFound


PLAN = "TPL-00000000-0000-4000-8000-000000000001"
VERSION = "TPLV-00000000-0000-4000-8000-000000000002"
WITHHELD = "TPL-00000000-0000-4000-8000-000000000003"
PRIVATE = "unrendered-invented-provenance"


def snapshot(activity=0, closures=0):
    return {
        "classification": "synthetic",
        "plan_id": PLAN,
        "plan_version_id": VERSION,
        "activity_trials": {"count": activity, "origins": [{"id": PRIVATE}]},
        "early_closures": {"count": closures, "origins": [{"id": PRIVATE}]},
        "real_credit_from_these_records": {"full_validation_cycles": 0, "qualifications": 0},
        "real_totals": dict.fromkeys(("activity_trials", "early_closures", "full_validation_cycles", "qualifications")),
        "observed_at": "2026-11-23T01:52:00.000000Z",
    }


@override_settings(
    AUTHENTICATION_BACKENDS=["tests.dashboard_fixtures.FixtureAuthenticationBackend"],
    RMS_RR14_SCOPE_FILE="unused-in-frontend-request-tests",
)
class RR14DashboardTests(SimpleTestCase):
    def get(self, url, role="founder_viewer", **query):
        auth = b64encode(f"{role}:invented-dashboard-only".encode()).decode()
        return self.client.get(url, query, HTTP_AUTHORIZATION=f"Basic {auth}")

    def scoped(self, plan=PLAN):
        return reverse("rms-founder-dashboard-plan", args=(plan, VERSION))

    def test_plan_version_is_linked_after_authorized_read_only(self):
        detail = reverse("rms-test-plan-version", args=(PLAN, VERSION))
        record = {"plan_id": PLAN, "plan_version_id": VERSION, "classification": "synthetic",
                  "fields": {"title": "Invented plan"}, "criteria": [], "data_requirements": []}
        with patch("rms.test_plan_views.plan_service", return_value=record) as reader:
            response = self.get(detail, "editor")
            self.assertContains(response, f'href="{self.scoped()}"')
            self.assertEqual(reader.call_args.args, ("read_test_plan_version",))
            self.assertEqual(reader.call_args.kwargs["version_id"], VERSION)
            reader.side_effect = ResourceNotFound
            self.assertNotContains(self.get(detail, "editor"), self.scoped(), status_code=404)

    def test_backend_snapshot_is_bound_to_request_actor_and_exact_version(self):
        for role in ("founder_viewer", "editor"):
            with self.subTest(role=role), patch(
                "rms.dashboard_views.read_rr14_projection", side_effect=(snapshot(), snapshot(2, 1)),
            ) as reader:
                before = self.get(self.scoped(), role)
                after = self.get(self.scoped(), role, actor="unassigned", plan_id=WITHHELD, version_id="latest")
                self.assertContains(before, "<dt>Saved synthetic attempts</dt><dd>0</dd>", html=True)
                self.assertContains(after, "<dt>Saved synthetic attempts</dt><dd>2</dd>", html=True)
                self.assertContains(after, "<dt>Saved synthetic early closures</dt><dd>1</dd>", html=True)
                self.assertContains(after, "<dt>Real full-validation cycle credit from these records</dt><dd>0</dd>", html=True)
                self.assertContains(after, "<dt>Real qualification credit from these records</dt><dd>0</dd>", html=True)
                self.assertContains(after, "Real ledger totals are unavailable.")
                self.assertContains(after, "2026-11-23T01:52:00+00:00")
                self.assertNotContains(after, PRIVATE)
                self.assertNotContains(after, WITHHELD)
                self.assertEqual(after["Cache-Control"], "private, no-store")
                self.assertIn("Authorization", after["Vary"])
                self.assertEqual(reader.call_count, 2)
                for call in reader.call_args_list:
                    self.assertEqual(call.kwargs["actor"].groups.role, role)
                    self.assertEqual(call.kwargs["plan_id"], PLAN)
                    self.assertEqual(call.kwargs["plan_version_id"], VERSION)

    def test_withheld_and_absent_are_indistinguishable_and_failures_are_not_zero(self):
        self.maxDiff = 1000
        with patch("rms.dashboard_views.read_rr14_projection", side_effect=(
            ResourceNotFound(WITHHELD), ResourceNotFound("absent"), DatabaseError(PRIVATE), None, snapshot(2, 1),
        )):
            responses = [self.get(self.scoped(plan)) for plan in (WITHHELD, "absent", WITHHELD, WITHHELD, WITHHELD)]
        for response in responses:
            self.assertEqual(response.content, responses[0].content)
            self.assertEqual(response["Cache-Control"], "private, no-store")
            self.assertContains(response, "Saved synthetic workflow unavailable.")
            for value in (WITHHELD, VERSION, PRIVATE, "Saved synthetic attempts</dt>", "credit from these records</dt>"):
                self.assertNotContains(response, value)

    def test_role_denial_and_unscoped_home_do_not_retrieve(self):
        with patch("rms.dashboard_views.read_rr14_projection") as reader:
            self.assertNotContains(self.get(self.scoped(), "unassigned"), PLAN, status_code=403)
            self.assertNotContains(self.client.get(self.scoped()), PLAN, status_code=401)
            self.assertNotContains(self.get(reverse("rms-founder-dashboard")), "Saved synthetic workflow")
            with override_settings(RMS_RR14_SCOPE_FILE=""):
                self.assertContains(self.get(self.scoped()), "Saved synthetic workflow unavailable.")
            reader.assert_not_called()
