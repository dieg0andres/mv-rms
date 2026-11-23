"""Invented MAU-167 journeys with PostgreSQL guards in place."""

import base64
from concurrent.futures import ThreadPoolExecutor
import json
from datetime import timedelta
from threading import Barrier
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.db import DatabaseError, connection, connections, transaction
from django.test import TestCase
from django.utils import timezone

from rms.hypothesis_models import ResearchFamilyVersion
from rms.hypothesis_validation import HypothesisValidationError, SCHEMA
from rms.intake_models import IntakeSourceAssessment, ResearchIntakeVersion
from rms.intake_services import CLOSURE, PRIORITY, SOURCE_ASSESSMENT, read_intake, save_intake
from rms.models import IdempotencyRecord, IdeaVersion
from rms.research_context_common import Forbidden, StaleVersion
from rms.research_context_services import create_investigation
from rms.services import create_idea
from rms.test_plan_services import create_test_plan
from tests.committed_database import CommittedDatabaseTestCase
from tests.test_test_plan_backend_validation import minimal


class IntakeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.headers = {}
        for role in ("editor", "founder_viewer", "outsider"):
            actor = User.objects.create_user("intake-" + role, password="invented-test-password")
            if role != "outsider":
                actor.groups.add(Group.objects.create(name=role))
            setattr(cls, role, actor)
            token = base64.b64encode(f"{actor.username}:invented-test-password".encode()).decode()
            cls.headers[role] = {"HTTP_AUTHORIZATION": f"Basic {token}"}
        call_command("load_rms_hn_fixture", actor=cls.editor.username, review_time="2026-10-03T12:00:00Z", verbosity=0)
        cls.idea = IdeaVersion.objects.order_by("-version").first()
        cls.idea_id = cls.idea.idea.idea_id
        cls.url = f"/api/v1/ideas/{cls.idea_id}/intake"
        cls.family = ResearchFamilyVersion.objects.first()
        cls.source = cls.idea.contributions.first().source_version
        cls.prior = {
            "query_scope": "Invented notebook only, no live query",
            "query_time": "2026-10-03T12:00:00Z",
            "policy_version": SCHEMA["$defs"]["AssessmentFields"]["properties"]["policy_version"]["const"],
            "result_watermark": "Invented notebook edition 1",
            "finding": "no_relevant_work_found",
            "rationale": "The invented result has no matching case.",
            "limitations": "Fixture only, not a completed novelty search.",
            "record_links": [],
        }
        cls.case = cls.make_case("case")

    @classmethod
    def make_case(cls, key, **prior):
        return json.loads(create_investigation(actor=cls.editor, idempotency_key=key, payload={
            "family_version_id": cls.family.public_id,
            "fields": {"title": "Invented intake case", "owner_role": "synthetic editor", "priority": "normal", "next_action": "Screen source"},
            "prior_research_assessment": {**cls.prior, **prior},
        }).body)["investigation_version_id"]

    def grant(self, **overrides):
        return self.settings(RMS_INTAKE_SYNTHETIC_RIGHTS={self.source.source_version_id: {
            "reference": "fixture:MAU-167-test",
            "sha256": self.source.content_sha256,
            "operation": "synthetic_intake_assessment",
            "expires_at": (timezone.now() + timedelta(days=1)).isoformat(),
            **overrides,
        }})

    def payload(self):
        return {
            "idea_version_id": self.idea.idea_version_id, "family_version_id": self.family.public_id,
            "investigation_version_id": self.case, "expected_latest_version": 0, "outcome": "ready",
            "distinctness": "candidate", "family_rationale": "Same fictional mechanism boundary.",
            "priority": {key: f"Fictional judgment: {key}" for key in PRIORITY},
            "source_assessments": {row.contribution_id: {key: f"Fictional assessment: {key}" for key in SOURCE_ASSESSMENT} for row in self.idea.contributions.all()},
        }

    def closure(self):
        return {key: value for key, value in self.payload().items() if key not in ("source_assessments", "priority", "investigation_version_id")} | {
            "outcome": "early_closed", "closure": {key: f"Invented failure: {key}" for key in CLOSURE},
        }

    def post(self, payload, key="write", role="editor"):
        return self.client.post(self.url, payload, content_type="application/json", HTTP_IDEMPOTENCY_KEY=key, **self.headers[role])

    def hypothesis(self, item, *, include=True):
        payload = {
            "originating_idea_version_id": self.idea.idea_version_id, "origin_rationale": "Invented direct origin",
            "investigation_version_id": self.case,
            "idea_family_binding": {"mode": "existing", "association_version_id": item["family_binding"]["version_id"]},
            "fields": {"title": "Invented screened Hypothesis"},
        }
        if include:
            payload["intake_version_id"] = item["version_id"]
        return self.client.post("/api/v1/hypotheses", payload, content_type="application/json", HTTP_IDEMPOTENCY_KEY="hypothesis", **self.headers["editor"])

    def test_ready_to_hypothesis_and_plan_then_correction_preserves_original(self):
        with self.grant():
            payload = self.payload()
            first = self.post(payload)
            self.assertEqual(first.status_code, 201, first.content)
            self.assertEqual(self.post(payload).content, first.content)
            self.assertEqual(self.post(payload | {"family_rationale": "Changed"}).status_code, 409)
            item = read_intake(actor=self.editor, idea_id=self.idea_id)["results"][0]
            self.assertFalse(item["credit"])
            self.assertEqual(len(item["source_assessments"]), self.idea.contributions.count())
            self.assertEqual(self.hypothesis(item, include=False).status_code, 400)
            hypothesis = self.hypothesis(item)
            self.assertEqual(hypothesis.status_code, 201, hypothesis.content)
            plan = minimal() | {"hypothesis_version_id": hypothesis.json()["version_id"]}
            self.assertEqual(create_test_plan(actor=self.editor, idempotency_key="plan", payload=plan).status, 201)
            revise = self.closure() | {"correction_reason": "Invented feasibility failure", "expected_latest_version": 1}
            self.assertEqual(self.post(revise, key="revise").status_code, 201)
            self.assertEqual(self.post(revise, key="stale").status_code, 409)
            with self.assertRaises(HypothesisValidationError):
                create_test_plan(actor=self.editor, idempotency_key="plan-stale", payload=plan)
            old, closed = read_intake(actor=self.founder_viewer, idea_id=self.idea_id)["results"]
            self.assertEqual(old["version_id"], item["version_id"])
            self.assertEqual(old["downstream_hypotheses"][0]["version_id"], hypothesis.json()["version_id"])
            self.assertEqual((closed["state"], closed["credit"], closed["supersedes_version_id"]), ("early_closed", False, old["version_id"]))
            page = self.client.get(f"/ideas/{self.idea_id}/intake", **self.headers["editor"])
            self.assertContains(page, "Pinned to superseded screening")

    def test_rights_scope_prior_evidence_and_role_denials_leave_no_writes(self):
        malformed_case = self.make_case("no-links", finding="extends")
        baseline = IdempotencyRecord.objects.count()
        self.assertEqual(self.post(self.payload()).status_code, 400)
        with self.grant(operation="wrong-purpose"):
            self.assertEqual(self.post(self.payload()).status_code, 400)
        with self.grant(expires_at=(timezone.now() - timedelta(minutes=1)).isoformat()):
            self.assertEqual(self.post(self.payload()).status_code, 400)
        with self.grant():
            self.assertEqual(self.post(self.payload() | {"investigation_version_id": malformed_case}).status_code, 400)
            self.assertEqual(self.post(self.payload() | {"source_assessments": {}}).status_code, 400)
            self.assertEqual(self.post(self.payload(), role="founder_viewer").status_code, 403)
            with self.assertRaises(Forbidden):
                save_intake(actor=self.outsider, idea_id=self.idea_id, idempotency_key="direct", payload=self.payload())
            with patch("rms.intake_services._idea") as fetch:
                self.assertEqual(self.client.get(self.url, **self.headers["outsider"]).status_code, 403)
                fetch.assert_not_called()
        self.assertEqual(IdempotencyRecord.objects.count(), baseline)
        self.assertFalse(ResearchIntakeVersion.objects.exists())

    def test_browser_closure_and_history(self):
        auth = self.headers["editor"]
        page = f"/ideas/{self.idea_id}/intake"
        self.assertContains(self.client.get(f"/ideas/{self.idea_id}", **auth), "Screening and prior research")
        self.assertContains(self.client.get(page + "?outcome=early_closed", **auth), "Reusable lesson")
        payload = self.closure()
        form = {key: payload[key] for key in ("idea_version_id", "family_version_id", "expected_latest_version", "distinctness", "family_rationale")}
        form |= {f"closure_{key}": value for key, value in payload["closure"].items()}
        result = self.client.post(page + "?outcome=early_closed", form | {"idempotency_key": "form-closure"}, **auth)
        self.assertEqual(result.status_code, 302, result.content)
        response = self.client.get(page, **self.headers["founder_viewer"])
        self.assertContains(response, "Invented failure: reusable_lesson")
        self.assertNotContains(response, "<form")

    def test_rights_revocation_and_guarded_history(self):
        with self.grant():
            self.assertEqual(self.post(self.payload()).status_code, 201)
            with connection.cursor() as cursor:
                cursor.execute("SET CONSTRAINTS intake_graph IMMEDIATE")
            item = read_intake(actor=self.editor, idea_id=self.idea_id)["results"][0]
            with self.assertRaises(DatabaseError), transaction.atomic():
                IntakeSourceAssessment.objects.update(fields={})
        self.assertEqual(self.hypothesis(item).status_code, 400)
        redacted = read_intake(actor=self.founder_viewer, idea_id=self.idea_id)["results"][0]
        self.assertEqual(redacted["source_assessments"], [])
        self.assertEqual(IntakeSourceAssessment.objects.count(), self.idea.contributions.count())

    def test_variant_stays_grouped_and_has_no_credit(self):
        self.assertEqual(self.post(self.closure()).status_code, 201)
        saved = create_idea(
            actor=self.editor.username, idempotency_key="variant-idea", request_path="/api/v1/ideas",
            fields={"title": "Invented sibling", "mechanism": "Same fictional liquidity pressure",
                    "testable_claim": "Invented alternative horizon", "falsification": "Invented null result",
                    "eligible_market": "etfs", "workflow_status": "draft", "rejection_reason": None},
            contributions=[{"source_version_id": self.source.source_version_id, "contribution": "Invented same source"}],
        )
        variant = json.loads(saved.body)
        request = self.closure() | {"idea_version_id": variant["latest_idea_version_id"]}
        with self.assertRaises(HypothesisValidationError):
            save_intake(actor=self.editor, idea_id=variant["idea_id"], idempotency_key="candidate", payload=request)
        save_intake(actor=self.editor, idea_id=variant["idea_id"], idempotency_key="variant", payload=request | {"distinctness": "related_variant"})
        result = read_intake(actor=self.editor, idea_id=variant["idea_id"])["results"][0]
        self.assertEqual(result["family"]["version_id"], self.family.public_id)
        self.assertEqual(result["fields"]["distinctness"], "related_variant")
        self.assertFalse(result["credit"])


class IntakeRaceTest(CommittedDatabaseTestCase):
    def test_two_concurrent_expected_zero_writes_commit_one_history(self):
        IntakeTests.setUpTestData.__func__(type(self))
        payload = IntakeTests.closure(self)
        barrier = Barrier(2, timeout=10)

        def attempt(number):
            try:
                actor = User.objects.get(pk=self.editor.pk)
                barrier.wait()
                return save_intake(actor=actor, idea_id=self.idea_id, idempotency_key=f"race-{number}", payload=payload).status
            except StaleVersion:
                return 409
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            self.assertEqual(sorted(executor.map(attempt, (1, 2))), [201, 409])
        self.assertEqual(ResearchIntakeVersion.objects.count(), 1)

    payload = IntakeTests.payload
    make_case = classmethod(IntakeTests.make_case.__func__)
