from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.conf import settings
from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase
from django.urls import resolve
from rest_framework.test import force_authenticate

from rms.navigation_views import (
    HypothesisDraftPreviewPage,
    SCHEMA_COMMIT,
    SCHEMA_PATH,
    SCHEMA_SHA256,
    SchemaUnavailable,
    hypothesis_draft_context,
    hypothesis_draft_groups,
    hypothesis_record_presentation,
    navigation_context,
    read_navigation_schema,
    research_context_groups,
)


IDEA_ID = "IDE-11111111-1111-4111-8111-111111111111"
IDEA_VERSION_ID = "IDEV-11111111-1111-4111-8111-111111111111"


def invented_endpoint(prefix, version=1):
    return {
        "stable_id": prefix + "-11111111-1111-4111-8111-111111111111",
        "version_id": prefix + "V-11111111-1111-4111-8111-111111111111",
        "version": version,
    }


def invented_record(schema):
    idea = invented_endpoint("IDE")
    source = {"stable_id": "synthetic-hn-source", "version_id": "SRCV-11111111-1111-4111-8111-111111111111", "version": 1}
    family = invented_endpoint("RFAM")
    case = invented_endpoint("INV")
    assessment = invented_endpoint("PRA")
    hypothesis = invented_endpoint("HYP")

    def association(kind, origin, target, identity):
        return {
            "kind": kind, "version_id": identity,
            "from": origin, "to": target, "rationale": "Invented fixture grouping only",
        }

    return {
        "hypothesis_id": hypothesis["stable_id"],
        "hypothesis_version_id": hypothesis["version_id"],
        "version": 1, "schema_version": "1.0", "classification": "synthetic",
        "status": "draft", "draft_completeness": "incomplete",
        "created_at": "2026-10-03T00:00:00Z", "created_by": "Invented editor",
        "corrects_version": None, "correction_reason": None, "changed_fields": [],
        "fields": {name: "Invented hypothesis" if name == "title" else None for name in schema["$defs"]["HypothesisFields"]["properties"]},
        "origin": {
            "idea": idea,
            "association": association("IdeaHypothesis", idea, hypothesis, "synthetic-origin-association-v1"),
            "sources": [{"source": source, "contribution_version_id": "synthetic-contribution-v1"}],
        },
        "research_context": {
            "family": family, "investigation": case, "assessment": assessment,
            "idea_family_association": association("IdeaFamily", idea, family, "synthetic-idea-family-v1"),
            "investigation_family_association": association("InvestigationFamily", case, family, "synthetic-case-family-v1"),
            "investigation_assessment_association": association("PriorResearchInvestigation", assessment, case, "synthetic-case-assessment-v1"),
            "hypothesis_investigation_association": association("HypothesisInvestigation", hypothesis, case, "synthetic-hypothesis-case-v1"),
        },
        "missing_fields": [{"path": "/fields/claim", "code": "missing", "message": "Invented missing claim"}],
        "upstream_notices": [{"code": "review_needed", "pinned": idea, "newer": {**idea, "version": 2, "version_id": "IDEV-22222222-2222-4222-8222-222222222222"}, "impact_version_id": "synthetic-impact-v1"}],
    }


class SchemaPresentationTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        source = Path(settings.BASE_DIR) / SCHEMA_PATH
        if source.exists():
            cls.schema = read_navigation_schema(source)
        else:
            result = subprocess.run(
                ["git", "show", f"{SCHEMA_COMMIT}:{SCHEMA_PATH}"],
                cwd=settings.BASE_DIR, capture_output=True, check=True,
            )
            if sha256(result.stdout).hexdigest() != SCHEMA_SHA256:
                raise RuntimeError("Test input does not match the single receipted Backend schema.")
            cls.schema = json.loads(result.stdout)

    def render_draft(self, **kwargs):
        return render_to_string("rms/hypothesis_draft_shell.html", {
            **navigation_context(section="hypotheses", role="editor"),
            **hypothesis_draft_context(self.schema, **kwargs),
        })

    def controls(self, groups):
        return {control["path"]: control for group in groups for control in group["controls"]}

    def test_all_29_fields_come_from_the_single_schema(self):
        controls = self.controls(hypothesis_draft_groups(self.schema))
        names = {path.split("/")[2] for path in controls if path.startswith("/fields/")}
        self.assertEqual(names, set(self.schema["$defs"]["HypothesisFields"]["properties"]))
        self.assertEqual(len(names), 29)
        self.assertNotIn("/fields/horizon", controls)
        self.assertNotIn("/fields/sizing", controls)
        self.assertNotIn("/created_by", controls)
        self.assertNotIn("/status", controls)

    def test_enum_choices_have_no_defaults_or_added_values(self):
        controls = self.controls(hypothesis_draft_groups(self.schema))
        for name in ("market", "direction", "claim_basis", "sizing_method"):
            control = controls[f"/fields/{name}"]
            self.assertEqual([choice[0] for choice in control["choices"]], [value for value in self.schema["$defs"]["HypothesisFields"]["properties"][name]["enum"] if value is not None])
            self.assertEqual(control["value"], "")
        html = self.render_draft()
        self.assertIn("Choose explicitly — no default", html)
        self.assertNotIn("value=\"long\" selected", html)

    def test_preview_has_no_native_submission_or_browser_persistence(self):
        html = self.render_draft()
        self.assertNotIn("<form", html)
        self.assertNotIn("type=\"submit\"", html)
        self.assertIn("disabled>Save draft (not connected)", html)
        self.assertNotIn("data-api-url", html)
        self.assertIn("Reload persistence is not available", html)

    def test_duration_and_holding_controls_are_distinct_and_visible(self):
        controls = self.controls(hypothesis_draft_groups(self.schema))
        self.assertNotEqual(controls["/fields/effect_horizon/start_anchor"]["id"], controls["/fields/maximum_holding_period/start_anchor"]["id"])
        self.assertIn("/fields/effect_horizon/calendar", controls)
        self.assertIn("/fields/effect_horizon/bar_definition", controls)
        self.assertIn("/fields/maximum_holding_period/if_event_never_occurs", controls)
        self.assertIn("/fields/maximum_holding_period/rationale", controls)
        self.assertNotIn("no_fixed_time_limit", dict(controls["/fields/effect_horizon/kind"]["choices"]))
        self.assertIn("no_fixed_time_limit", dict(controls["/fields/maximum_holding_period/kind"]["choices"]))
        html = self.render_draft()
        self.assertIn("clear incompatible kind/unit fields explicitly", html)
        self.assertNotIn(" hidden", html)

    def test_input_decimal_and_invalid_kind_survive_validation(self):
        html = self.render_draft(submitted={
            "/fields/maximum_holding_period/quantity": "0001.2500",
            "/fields/effect_horizon/kind": "invented-invalid",
            "/fields/effect_horizon/calendar": "  Preserve calendar text  ",
        }, issues=[{"path": "/fields/effect_horizon/calendar", "code": "invalid", "message": "Invented field failure"}])
        self.assertIn("value=\"0001.2500\"", html)
        self.assertIn("value=\"invented-invalid\" selected", html)
        self.assertIn("  Preserve calendar text  </textarea>", html)
        self.assertIn("href=\"#draft-fields-effect_horizon-calendar\"", html)
        self.assertIn("aria-invalid=\"true\"", html)

    def test_manual_context_has_no_inferred_assessment_or_family(self):
        controls = self.controls(research_context_groups(self.schema))
        for name in self.schema["$defs"]["AssessmentFields"]["required"]:
            self.assertIn(f"/context/case/prior_research_assessment/{name}", controls)
        policy = controls["/context/case/prior_research_assessment/policy_version"]
        self.assertEqual(policy["value"], self.schema["$defs"]["AssessmentFields"]["properties"]["policy_version"]["const"])
        self.assertTrue(policy["readonly"])
        self.assertEqual(controls["/context/case/prior_research_assessment/finding"]["value"], "")
        self.assertEqual(controls["/context/case/prior_research_assessment/record_links"]["value"], "")
        html = self.render_draft()
        self.assertIn("Case state: proposed", html)
        self.assertIn("No selection is persisted or confirmed", html)
        self.assertIn("explicit [] if none were available", html)

    def test_binding_modes_and_grouping_reason_remain_explicit(self):
        controls = self.controls(hypothesis_draft_groups(self.schema))
        self.assertEqual(controls["/idea_family_binding/mode"]["choices"], [("existing", "Existing"), ("create", "Create")])
        for path in ("/idea_family_binding/association_version_id", "/idea_family_binding/family_version_id", "/idea_family_binding/rationale"):
            self.assertIn(path, controls)
        self.assertEqual(controls["/idea_family_binding/mode"]["value"], "")

    def test_correction_context_includes_retained_or_successor_assessment(self):
        groups = research_context_groups(self.schema, correction=True)
        controls = self.controls(groups)
        for path in (
            "/context/family/expected_latest_version", "/context/family/correction_reason",
            "/context/case/prior_research_assessment/assessment_version_id",
            "/context/case/prior_research_assessment/corrects_assessment_version_id",
            "/context/case/prior_research_assessment/expected_latest_assessment_version",
            "/context/case/prior_research_assessment/fields/limitations",
        ):
            self.assertIn(path, controls)
        self.assertEqual(controls["/context/case/prior_research_assessment/mode"]["choices"], [("existing", "Existing"), ("correct", "Correct")])

    def test_correction_requires_reason_but_does_not_require_nullable_content(self):
        controls = self.controls(hypothesis_draft_groups(self.schema, correction=True))
        self.assertTrue(controls["/correction_reason"]["required"])
        self.assertTrue(controls["/expected_latest_version"]["required"])
        self.assertFalse(controls["/fields/claim"]["required"])

    def test_conflict_preserves_context_and_uses_safe_optional_compare_link(self):
        html = self.render_draft(conflict=True, submitted={
            "/fields/title": "  losing invented title  ",
            "/context/case/prior_research_assessment/limitations": "Unsaved invented limits",
        }, latest_url=f"/ideas/{IDEA_ID}")
        self.assertIn("value=\"  losing invented title  \"", html)
        self.assertIn("Unsaved invented limits</textarea>", html)
        self.assertIn("target=\"_blank\" rel=\"noopener\"", html)
        self.assertIn("Do not overwrite or automatically retry", html)
        for unsafe in ("javascript:invented()", "//untrusted.invalid", "/\\untrusted.invalid", "/ unsafe"):
            self.assertNotIn("Compare authorized latest record", self.render_draft(conflict=True, latest_url=unsafe))

    def test_context_field_errors_are_focusable_and_escaped(self):
        html = self.render_draft(submitted={"/context/family/fields/name": "</textarea><script>invented()</script>"}, issues=[{
            "path": "/context/family/fields/name", "message": "<b>Invented context error</b>",
        }])
        self.assertIn("href=\"#draft-context-family-fields-name\"", html)
        self.assertIn("&lt;script&gt;invented()&lt;/script&gt;", html)
        self.assertIn("&lt;b&gt;Invented context error&lt;/b&gt;", html)
        self.assertNotIn("<script>invented()", html)

    def test_presentation_does_not_mutate_schema_or_raw_inputs(self):
        original = deepcopy(self.schema)
        submitted = {"/fields/title": "  Invented raw value  "}
        hypothesis_draft_context(self.schema, submitted=submitted)
        self.assertEqual(self.schema, original)
        self.assertEqual(submitted, {"/fields/title": "  Invented raw value  "})

    def test_preview_is_editor_only_before_schema_access(self):
        for roles, expected in (({"editor"}, 200), ({"founder_viewer"}, 403), (set(), 403)):
            with self.subTest(roles=roles), patch("rms.navigation_views.read_navigation_schema", return_value=self.schema) as read_schema:
                groups = Mock()
                groups.filter.side_effect = lambda **query: SimpleNamespace(exists=lambda: bool(roles.intersection(query["name__in"])))
                request = RequestFactory().get("/hypotheses/draft-preview")
                force_authenticate(request, user=SimpleNamespace(is_authenticated=True, groups=groups))
                response = HypothesisDraftPreviewPage.as_view()(request)
                self.assertEqual(response.status_code, expected)
                response.render()
                if expected == 403:
                    read_schema.assert_not_called()
                    self.assertNotIn(b"prior_research_assessment", response.content)
        with patch("rms.navigation_views.read_navigation_schema") as read_schema:
            response = HypothesisDraftPreviewPage.as_view()(RequestFactory().get("/hypotheses/draft-preview"))
            self.assertEqual(response.status_code, 401)
            read_schema.assert_not_called()

    def test_schema_missing_or_changed_fails_closed(self):
        with self.assertRaises(SchemaUnavailable):
            read_navigation_schema(Path(settings.BASE_DIR) / "invented-absent-schema.json")
        with patch.object(Path, "read_bytes", return_value=b"{}"):
            with self.assertRaises(SchemaUnavailable):
                read_navigation_schema()
        groups = Mock()
        groups.filter.return_value.exists.return_value = True
        request = RequestFactory().get("/hypotheses/draft-preview")
        force_authenticate(request, user=SimpleNamespace(is_authenticated=True, groups=groups))
        with patch("rms.navigation_views.read_navigation_schema", side_effect=SchemaUnavailable("Invented private path must not leak")):
            response = HypothesisDraftPreviewPage.as_view()(request)
        self.assertEqual(response.status_code, 503)
        response.render()
        self.assertNotIn(b"Invented private path", response.content)
        self.assertIn(b"No guessed controls or payload", response.content)

    def test_preview_route_is_prepared_not_registered_in_project(self):
        self.assertIs(resolve("/hypotheses/draft-preview", urlconf="rms.navigation_urls").func.view_class, HypothesisDraftPreviewPage)
        self.assertNotIn("rms.navigation_urls", (Path(settings.BASE_DIR) / "rms_project/urls.py").read_text())

    def test_exact_lineage_and_associations_never_retarget_to_newer(self):
        record = invented_record(self.schema)
        original = deepcopy(record)
        context = hypothesis_record_presentation(record)
        html = render_to_string("rms/includes/hypothesis_record_preview.html", context)
        self.assertIn(f"/ideas/{IDEA_ID}/history#idea-version-1", html)
        self.assertIn("/sources/synthetic-hn-source/history#source-version-1", html)
        self.assertNotIn("history#idea-version-2", html)
        self.assertIn("synthetic-idea-family-v1", html)
        self.assertIn("synthetic-case-assessment-v1", html)
        self.assertIn("exact-version page not connected", html)
        self.assertIn("Upstream review — separate from completeness", html)
        self.assertEqual(record, original)

    def test_record_correction_missing_values_and_untrusted_text_are_distinct(self):
        record = invented_record(self.schema)
        record.update(version=2, corrects_version=1, correction_reason="<script>Invented reason</script>", changed_fields=["claim"], draft_completeness="complete")
        html = render_to_string("rms/includes/hypothesis_record_preview.html", hypothesis_record_presentation(record))
        self.assertIn("Corrects v1", html)
        self.assertIn("Draft complete", html)
        self.assertIn("Missing / unknown", html)
        self.assertIn("&lt;script&gt;Invented reason&lt;/script&gt;", html)
        self.assertNotIn("<script>Invented reason", html)

    def test_existing_history_anchors_match_reference_links(self):
        idea = render_to_string("rms/includes/idea_version.html", {"version": {"version": 1, "idea_version_id": IDEA_VERSION_ID}})
        source = render_to_string("rms/source_history.html", {"detail": {"source_id": "synthetic-hn-source", "synthetic": True, "latest": {"source_version_id": "SRCV-11111111-1111-4111-8111-111111111111"}}, "history": [{"version": 1}]})
        self.assertIn("id=\"idea-version-1\"", idea)
        self.assertIn("id=\"source-version-1\"", source)

    def test_unsafe_or_unknown_origin_paths_are_not_links(self):
        record = invented_record(self.schema)
        record["origin"]["idea"]["stable_id"] = "javascript:invented()"
        record["origin"]["sources"][0]["source"]["stable_id"] = "../private"
        context = hypothesis_record_presentation(record)
        self.assertIsNone(context["pinned_references"][0]["url"])
        self.assertIsNone(context["pinned_references"][1]["url"])
