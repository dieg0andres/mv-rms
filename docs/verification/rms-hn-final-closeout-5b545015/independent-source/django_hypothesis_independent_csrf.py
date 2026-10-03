"""Exact-source, DB-denied CSRF bootstrap regression and diagnostic controls.

Expected behavior is declared before execution: a valid authenticated editor's
normal rendered form submission redirects to its saved version (303). Controls
provide a synthetic cookie only to isolate the defect; they are not browser PASS.
No database runner, credentials, staging request, product edit or CSRF exemption.
"""

import argparse
from datetime import datetime, timezone
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

UUID = "11111111-1111-4111-8111-111111111111"
ORIGIN = "https://csrf-fixture.example.invalid"
PATH = "/hypotheses/new?idea_id=IDE-" + UUID + "&idea_version=1"
OBSERVATIONS = []


class Inputs(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.values = {}
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "input" and attrs.get("type") == "hidden":
            self.values[attrs["name"]] = attrs.get("value", "")


def editor():
    return SimpleNamespace(pk=41, is_authenticated=True, is_active=True,
        get_username=lambda: "invented-csrf-editor",
        groups=SimpleNamespace(filter=lambda **kw: SimpleNamespace(
            exists=lambda: "editor" in kw.get("name__in", (kw.get("name"),)))))


class CsrfBootstrapTests(unittest.TestCase):
    def setUp(self):
        from django.test import Client, override_settings
        from django.middleware.csrf import CsrfViewMiddleware, REASON_NO_CSRF_COOKIE
        from rms.services import StoredResponse
        # The runtime rewrites Host to localhost and separately trusts its
        # private HTTPS origin. Use a synthetic origin with the same relationship.
        self.settings = override_settings(CSRF_TRUSTED_ORIGINS=[ORIGIN])
        self.settings.enable()
        self.addCleanup(self.settings.disable)
        self.client = Client(enforce_csrf_checks=True)
        self.reasons = []
        original_reject = CsrfViewMiddleware._reject

        def reject(middleware, request, reason):
            self.reasons.append("CSRF_COOKIE_MISSING" if reason == REASON_NO_CSRF_COOKIE
                else "ORIGIN_REJECTED" if reason.startswith("Origin checking failed")
                else "CSRF_TOKEN_REJECTED" if "CSRF token" in reason
                else "OTHER_CSRF_REJECTION")
            return original_reject(middleware, request, reason)

        for target, kwargs in (
            ("rest_framework.authentication.BasicAuthentication.authenticate", {"return_value": (editor(), None)}),
            ("rms.navigation_views.exact_idea", {"return_value": {
                "idea_id": "IDE-" + UUID, "idea_version_id": "IDEV-" + UUID,
                "version": 1, "title": "Invented pinned Idea", "workflow_status": "proposed"}}),
            ("rms.navigation_views.shared_service", {"side_effect": lambda kind, operation, **kw:
                {"results": []} if operation == "list" else StoredResponse(201,
                    json.dumps({"hypothesis_id": "HYP-" + UUID, "version": 1}).encode())}),
            ("django.middleware.csrf.CsrfViewMiddleware._reject", {"new": reject}),
        ):
            p = patch(target, **kwargs)
            value = p.start()
            self.addCleanup(p.stop)
            if target.endswith("shared_service"):
                self.service = value

    def form(self):
        response = self.client.get(PATH, secure=True, HTTP_HOST="localhost")
        self.assertEqual(response.status_code, 200)
        values = Inputs(response.content.decode()).values
        self.assertTrue(values.get("csrfmiddlewaretoken"))
        values.update({"/fields/title": "Invented independent CSRF draft",
            "/originating_idea_version_id": "IDEV-" + UUID,
            "/investigation_version_id": "INVV-" + UUID,
            "/idea_family_binding/mode": "existing",
            "/idea_family_binding/association_version_id": "IFAV-" + UUID,
            "/origin_rationale": "Invented manual origin", "operation": "save"})
        self.service.reset_mock()
        return response, values

    def submit(self, data, origin=ORIGIN):
        from django.conf import settings
        cookie_present = settings.CSRF_COOKIE_NAME in self.client.cookies
        response = self.client.post(PATH, data, secure=True, HTTP_HOST="localhost", HTTP_ORIGIN=origin)
        OBSERVATIONS.append({"test": self._testMethodName, "get_token_present": True,
            "post_cookie_present": cookie_present, "origin_equals_expected": origin == ORIGIN,
            "post_status": response.status_code, "rejection_reason_enum": self.reasons[-1] if self.reasons else None,
            "create_calls": sum(c.args[1] == "create" for c in self.service.call_args_list)})
        return response

    def cookie_control(self, get_response):
        from django.conf import settings
        # Diagnostic only: a synthetic cookie supplies the secret generated by
        # the actual GET. No protection is disabled or altered.
        self.client.cookies[settings.CSRF_COOKIE_NAME] = get_response.wsgi_request.META["CSRF_COOKIE"]

    def test_normal_get_to_native_post_saves_without_manual_cookie(self):
        _, values = self.form()
        response = self.submit(values)
        self.assertEqual(response.status_code, 303,
            "Valid editor GET-to-POST must save; observe sanitized reason in summary.json")
        self.service.assert_called_once()
        self.assertEqual(self.service.call_args.args[:2], ("hypothesis", "create"))

    def test_matching_cookie_control_reaches_mocked_save(self):
        get_response, values = self.form()
        self.cookie_control(get_response)
        response = self.submit(values)
        self.assertEqual(response.status_code, 303)
        self.service.assert_called_once()
        self.assertEqual(self.service.call_args.args[:2], ("hypothesis", "create"))
        self.assertEqual(response["Location"], "/hypotheses/HYP-" + UUID + "/versions/1")

    def test_foreign_origin_still_denied_with_matching_cookie_and_token(self):
        get_response, values = self.form()
        self.cookie_control(get_response)
        response = self.submit(values, "https://foreign-fixture.example.invalid")
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.reasons, ["ORIGIN_REJECTED"])
        self.service.assert_not_called()

    def test_missing_token_still_denied_with_matching_cookie_and_origin(self):
        get_response, values = self.form()
        self.cookie_control(get_response)
        del values["csrfmiddlewaretoken"]
        response = self.submit(values)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.reasons, ["CSRF_TOKEN_REJECTED"])
        self.service.assert_not_called()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(args.candidate_root.resolve()))
    os.environ["DJANGO_SETTINGS_MODULE"] = "rms_project.settings"
    started = datetime.now(timezone.utc).isoformat()
    from django.db.backends.base.base import BaseDatabaseWrapper
    with patch.object(BaseDatabaseWrapper, "ensure_connection", side_effect=AssertionError("CSRF source test forbids DB")) as db, patch("psycopg.connect", side_effect=AssertionError("CSRF source test forbids psycopg")) as pg:
        import django
        django.setup()
        from django.conf import settings
        with (args.output / "checks.log").open("w") as log:
            result = unittest.TextTestRunner(stream=log, verbosity=2).run(
                unittest.defaultTestLoader.loadTestsFromTestCase(CsrfBootstrapTests))
        summary = {"candidate": "aead8ff52128859fbae8b0f3d8ed2de67aff5131",
            "run_id": os.environ.get("PAPERCLIP_RUN_ID"), "fixture_version": "hn-csrf-bootstrap-v1",
            "started_utc": started, "finished_utc": datetime.now(timezone.utc).isoformat(),
            "django_version": django.get_version(), "middleware": settings.MIDDLEWARE,
            "tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
            "skips": len(result.skipped), "django_connections": db.call_count, "psycopg_connections": pg.call_count,
            "observations": OBSERVATIONS, "scope": "DB-denied actual Django GET/render/POST with mocked editor/services; not live browser or DB acceptance"}
        (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        print(json.dumps(summary))
        return 0 if result.wasSuccessful() and not db.call_count and not pg.call_count else 1


if __name__ == "__main__":
    raise SystemExit(main())
