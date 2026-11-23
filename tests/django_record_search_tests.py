import base64
import json
from urllib.parse import urlencode
from unittest.mock import patch

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.db import DatabaseError
from django.test import Client, TestCase

from rms.hypothesis_models import HypothesisVersion
from rms.models import IdeaVersion
from rms.record_search import search_versions
from rms.test_plan_services import create_test_plan
from tests.synthetic_read_scope import SyntheticPlanReaders
from tests.test_test_plan_backend_validation import complete_fixture


class RecordSearchTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.clients_by_role = {}
        for role in ("editor", "founder_viewer", "outsider"):
            actor = User.objects.create_user("search-" + role, password="synthetic-test-password")
            if role != "outsider":
                actor.groups.add(Group.objects.get_or_create(name=role)[0])
            token = base64.b64encode(f"{actor.username}:synthetic-test-password".encode()).decode()
            cls.clients_by_role[role] = "Basic " + token
            if role == "editor":
                cls.editor = actor
            elif role == "founder_viewer":
                cls.viewer = actor
        call_command("load_rms_hn_fixture", actor=cls.editor.username, review_time="2026-11-22T12:00:00Z", verbosity=0)
        plan = complete_fixture()
        plan["hypothesis_version_id"] = HypothesisVersion.objects.first().public_id
        receipt = create_test_plan(actor=cls.editor, idempotency_key="search-plan", payload=plan)
        assert receipt.status == 201
        cls.plan = json.loads(receipt.body)

    def setUp(self):
        SyntheticPlanReaders(self, self.plan).allow(self.editor, self.viewer)

    def search(self, role, **values):
        headers = {"HTTP_AUTHORIZATION": self.clients_by_role[role]} if role else {}
        return self.client.post("/search", urlencode(values), content_type="application/x-www-form-urlencoded", **headers)

    def test_all_collections_return_exact_browsable_versions(self):
        response = self.search("founder_viewer", term="invented")
        self.assertEqual(response.status_code, 200)
        rows = response.context_data["results"]
        self.assertEqual({row["kind"] for row in rows}, {"source", "idea", "hypothesis", "family", "case", "plan"})
        for row in rows:
            href = row["url"].split("#")[0]
            result = self.client.get(href, HTTP_AUTHORIZATION=self.clients_by_role["founder_viewer"])
            self.assertEqual(result.status_code, 200, href)
            self.assertContains(result, row["exact_id"])
        self.assertEqual(response["Referrer-Policy"], "same-origin")
        self.assertIn("no-store", response["Cache-Control"])

    def test_historical_scope_and_identity(self):
        prior = IdeaVersion.objects.select_related("idea").get(version=1)
        self.assertGreater(prior.idea.latest_version, prior.version)
        current = self.search("editor", term=prior.idea_version_id, collection="idea")
        self.assertEqual(current.context_data["results"], [])
        old = self.search("editor", term=prior.idea_version_id, collection="idea", include_history="on")
        self.assertEqual([row["result_title"] for row in old.context_data["results"]], [prior.title])
        self.assertContains(old, f"#idea-version-{prior.version}")

    def test_denial_and_invalid_query_precede_record_reads(self):
        with patch("rms.search_views.search_versions") as read:
            self.assertEqual(self.search(None, term="invented").status_code, 401)
            self.assertEqual(self.search("outsider", term="invented").status_code, 403)
            self.assertEqual(self.search("editor", term="x").status_code, 400)
            self.assertEqual(self.search("editor", term="invented", collection="restricted").status_code, 400)
            read.assert_not_called()
        with patch("rms.search_views.search_versions", side_effect=DatabaseError("private detail")):
            response = self.search("editor", term="invented")
        self.assertEqual(response.status_code, 503)
        self.assertNotContains(response, "private detail", status_code=503)
        self.assertNotContains(response, "No matching versions", status_code=503)
        strict = Client(enforce_csrf_checks=True)
        self.assertEqual(strict.post("/search", {"term": "invented"}, HTTP_AUTHORIZATION=self.clients_by_role["editor"]).status_code, 403)

    def test_page_boundaries_are_stable(self):
        with patch("rms.record_search.PAGE_SIZE", 1):
            one, more = search_versions(actor=self.editor, term="invented", collection="", include_history=False, page=1)
            two, _ = search_versions(actor=self.editor, term="invented", collection="", include_history=False, page=2)
        self.assertTrue(more)
        self.assertNotEqual(one[0]["exact_id"], two[0]["exact_id"])
