"""MAU-168 gates tested with the exact MAU-167 invented intake journey."""

import json
from copy import deepcopy
from datetime import timedelta

from django.contrib.auth.models import AnonymousUser, Group, User
from django.db import DatabaseError, connection, transaction
from django.test import Client, TestCase
from django.utils import timezone

from rms.intake_services import read_intake
from rms.models import IdempotencyRecord
from rms.research_context_common import AuthenticationRequired, Forbidden
from rms.services import ResourceNotFound
from rms.stage_gate_models import SyntheticGateEvent
from rms.stage_gate_services import POLICY, read_gate, record_gate
from rms.test_plan_models import TestPlanVersion
from rms.test_plan_services import create_test_plan, digest
from tests import django_intake_tests
from tests.test_test_plan_backend_validation import minimal


class StageGateTests(TestCase):
    setUpTestData = classmethod(django_intake_tests.IntakeTests.setUpTestData.__func__)
    make_case = classmethod(django_intake_tests.IntakeTests.make_case.__func__)
    source_grant = django_intake_tests.IntakeTests.source_grant
    hypothesis = django_intake_tests.IntakeTests.hypothesis
    payload = django_intake_tests.IntakeTests.payload
    post_intake = django_intake_tests.IntakeTests.post

    def prepare(self, distinctness="candidate"):
        self.source_rights = self.source_grant(self.source)
        with self.settings(RMS_INTAKE_SYNTHETIC_RIGHTS={self.source.source_version_id: self.source_rights}):
            response = self.post_intake(self.payload() | {"distinctness": distinctness})
            self.assertEqual(response.status_code, 201, response.content)
            screened = read_intake(actor=self.editor, idea_id=self.idea_id)["results"][0]
            response = self.hypothesis(screened)
            self.assertEqual(response.status_code, 201, response.content)
            self.hypothesis_version = response.json()["version_id"]
            result = create_test_plan(actor=self.editor, idempotency_key="gate-plan",
                                      payload=minimal() | {"hypothesis_version_id": self.hypothesis_version})
        self.plan = TestPlanVersion.objects.get(public_id=json.loads(result.body)["plan_version_id"])
        self.plan_id = self.plan.record.public_id
        self.exact = f"/test-plans/{self.plan_id}/versions/{self.plan.public_id}"
        self.browser = self.exact + "/synthetic-gates"
        self.api = "/api/v1" + self.browser
        self.artifacts = {"code_sha256": "1" * 64, "data_sha256": "2" * 64}
        scope = {"plan_version_id": self.plan.public_id, "plan_digest": self.plan.row_digest,
                 "hypothesis_version_id": self.hypothesis_version, "case_version_id": self.case,
                 "intake_version_id": screened["version_id"], "intake_digest": screened["row_digest"],
                 "config_digest": self.plan.config_digest, "profile_link_digest": self.plan.link_digest, **self.artifacts}
        now = timezone.now()
        shared = {"revision": 2, "policy": POLICY, "scope": scope,
                  "effective_at": (now - timedelta(hours=1)).isoformat(), "expires_at": (now + timedelta(hours=1)).isoformat()}
        self.fixture = {
            "readers": [str(self.founder_viewer.pk)], "operators": [str(self.editor.pk)],
            "artifacts": self.artifacts, "blockers": [],
            "authority": {operation: shared | {"operation": operation, "status": "approved", "reference": "fixture:decision-" + operation}
                          for operation in ("freeze", "release")},
            "rights": {operation: shared | {"operation": operation, "status": "allowed", "reference": "fixture:rights-" + operation,
                                             "principal": str(self.editor.pk), "purpose": "synthetic_gate_only"}
                       for operation in ("freeze", "release")},
        }

    def fixture_settings(self, fixture=None, *, source=True):
        return self.settings(RMS_SYNTHETIC_STAGE_GATES={self.plan_id: self.fixture if fixture is None else fixture},
                             RMS_INTAKE_SYNTHETIC_RIGHTS={self.source.source_version_id: self.source_rights} if source else {})

    def command(self, action="freeze", sequence=0):
        record = self.fixture["authority"][action]
        return {"operation": action, "expected_sequence": sequence,
                "authority": {"reference": record["reference"], "revision": record["revision"], "digest": digest(record)}}

    def post(self, payload, key="fixture-freeze", role="editor"):
        return self.client.post(self.api, payload, content_type="application/json", HTTP_IDEMPOTENCY_KEY=key, **self.headers[role])

    def denied(self, command, *, code=None, status=400, key="fixture-denial"):
        before = list(SyntheticGateEvent.objects.values()), IdempotencyRecord.objects.count()
        response = self.post(command, key=key)
        self.assertEqual(response.status_code, status, response.content)
        if code:
            self.assertEqual(response.json()["error"]["fields"][0]["code"], code)
        self.assertEqual((list(SyntheticGateEvent.objects.values()), IdempotencyRecord.objects.count()), before)

    def test_freeze_release_invalidate_history_and_replays(self):
        self.prepare()
        with self.fixture_settings():
            self.denied(self.command("release"), code="invalid_transition")
            freeze = self.post(self.command())
            self.assertEqual(freeze.status_code, 201, freeze.content)
            self.denied(self.command("release"), status=409)
            self.denied(self.command("release", 1), status=409, key="fixture-freeze")
            release = self.post(self.command("release", 1), key="fixture-release")
            self.assertEqual(release.status_code, 201, release.content)
            response = self.post({"operation": "invalidate", "expected_sequence": 2, "reason": "Invented source correction impact"}, key="impact")
            self.assertEqual(response.status_code, 201, response.content)
            replay = self.post(self.command())
            self.assertEqual(replay.content, freeze.content)
            self.denied(self.command("release", 3), code="invalid_transition")
            history = self.client.get(self.api, **self.headers["founder_viewer"]).json()
        first, second, impact = history["events"]
        self.assertEqual(history["recorded_state"], "invalidated")
        self.assertEqual(first["authority"]["digest"], self.command()["authority"]["digest"])
        self.assertEqual(first["rights"]["purpose"], "synthetic_gate_only")
        self.assertEqual(second["predecessor_event_id"], first["event_id"])
        self.assertEqual(impact["predecessor_event_id"], second["event_id"])
        self.assertEqual(impact["impact_reason"], "Invented source correction impact")

    def test_invalid_and_stale_authority_or_rights_leave_nothing(self):
        self.prepare()
        with self.fixture_settings():
            for key in ("reference", "revision", "digest"):
                command = self.command()
                del command["authority"][key]
                self.denied(command, code="invalid_input")
            for key, value in (("reference", "fixture:unknown"), ("revision", 1), ("digest", "0" * 64)):
                command = self.command()
                command["authority"][key] = value
                self.denied(command, code="missing_or_stale_authority")
        for key, value in (("status", "revoked"), ("expires_at", (timezone.now() - timedelta(seconds=1)).isoformat()),
                           ("effective_at", (timezone.now() + timedelta(seconds=30)).isoformat()),
                           ("expires_at", "2026-12-01T00:00:00"), ("policy", "fixture:wrong-policy"), ("scope", {})):
            with self.subTest(field=key):
                fixture = deepcopy(self.fixture)
                fixture["authority"]["freeze"][key] = value
                with self.fixture_settings(fixture):
                    self.denied(self.command(), code="missing_or_stale_authority")
        for delta, code in (({"rights": {}}, "missing_or_stale_rights"), ({"blockers": ["invented blocker"]}, "unresolved_blockers"),
                            ({"blockers": None}, "unresolved_blockers"), ({"artifacts": {}}, "missing_exact_artifacts")):
            with self.fixture_settings(self.fixture | delta):
                self.denied(self.command(), code=code)
        with self.fixture_settings(source=False):
            self.denied(self.command(), code="missing_or_stale_rights")

    def test_release_rechecks_freeze_and_intake_but_allows_fail_safe_invalidation(self):
        self.prepare()
        with self.fixture_settings():
            self.assertEqual(self.post(self.command()).status_code, 201)
        fixture = deepcopy(self.fixture)
        fixture["authority"]["freeze"]["revision"] += 1
        with self.fixture_settings(fixture):
            self.denied(self.command("release", 1), code="invalidated_freeze")
        fixture["authority"]["freeze"]["status"] = "revoked"
        with self.fixture_settings(fixture):
            self.denied(self.command("release", 1), code="missing_or_stale_authority")
        with self.fixture_settings(source=False):
            self.denied(self.command("release", 1), code="missing_or_stale_rights")
            impact = {"operation": "invalidate", "expected_sequence": 1, "reason": "Fixture intake right lost"}
            self.assertEqual(self.post(impact, key="invalidate-rights").status_code, 201)

    def test_related_variant_cannot_freeze(self):
        self.prepare(distinctness="related_variant")
        with self.fixture_settings():
            self.denied(self.command(), code="not_a_distinct_candidate")

    def test_dal_permissions_and_replay_are_scoped(self):
        self.prepare()
        editor_group = Group.objects.get(name="editor")
        self.founder_viewer.groups.add(editor_group)
        other = User.objects.create_user("other-gate-editor")
        other.groups.add(editor_group)
        args = {"plan_id": self.plan_id, "version_id": self.plan.public_id}
        with self.fixture_settings():
            with self.assertRaises(AuthenticationRequired):
                read_gate(actor=AnonymousUser(), **args)
            with self.assertRaises(Forbidden):
                read_gate(actor=self.outsider, **args)
            with self.assertRaises(ResourceNotFound):
                read_gate(actor=other, **args)
            with self.assertRaises(Forbidden):
                record_gate(actor=self.founder_viewer, **args, idempotency_key="fixture-freeze", payload=self.command())
            self.assertEqual(self.post(self.command()).status_code, 201)
            self.assertEqual(self.client.get(self.api, **self.headers["founder_viewer"]).headers["Cache-Control"], "private, no-store")
            self.assertEqual(self.client.get(self.api).status_code, 401)
            self.assertEqual(self.client.get(self.api, **self.headers["outsider"]).status_code, 403)
        with self.fixture_settings(self.fixture | {"operators": []}):
            self.assertEqual(self.post(self.command()).status_code, 404)
        with self.assertRaises(ResourceNotFound):
            read_gate(actor=self.editor, **args)

    def test_authenticated_normal_browser_workflow_and_csrf(self):
        self.prepare()
        with self.fixture_settings():
            browser = Client(enforce_csrf_checks=True)
            auth = self.headers["editor"]
            detail = browser.get(self.exact, **auth)
            self.assertContains(detail, self.browser)
            view = browser.get(self.browser, **auth)
            self.assertContains(view, "Invented fixtures only")
            self.assertNotContains(browser.get(self.browser, **self.headers["founder_viewer"]), "<form")
            body = self.command()["authority"] | {"operation": "freeze", "expected_sequence": "0", "idempotency_key": "browser"}
            self.assertEqual(browser.post(self.browser, body, **auth).status_code, 403)
            self.assertEqual(browser.post(self.browser, body | {"csrfmiddlewaretoken": view.cookies["csrftoken"].value}, **auth).status_code, 302)
            self.assertContains(browser.get(self.browser, **auth), "Last recorded state: frozen")

    def test_history_is_append_only_even_through_direct_sql(self):
        self.prepare()
        with self.fixture_settings():
            self.assertEqual(self.post(self.command()).status_code, 201)
        for raw in ("UPDATE rms_syntheticgateevent SET impact_reason = ''", "DELETE FROM rms_syntheticgateevent",
                    "TRUNCATE rms_syntheticgateevent CASCADE"):
            with self.subTest(sql=raw), self.assertRaises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
                cursor.execute(raw)
        first = SyntheticGateEvent.objects.get()
        with self.assertRaises(DatabaseError), transaction.atomic():
            SyntheticGateEvent.objects.create(plan_version=first.plan_version, intake_version=first.intake_version,
                                              sequence=3, predecessor=first, recorded_state="invalidated", operation="invalidate",
                                              impact_reason="Invented out-of-order append", actor_id=first.actor_id, recorded_at=first.recorded_at)
        self.assertEqual(SyntheticGateEvent.objects.count(), 1)
