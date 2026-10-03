from copy import deepcopy

from django.template.loader import render_to_string
from django.test import SimpleTestCase

from rms.navigation_views import draft_presentation, navigation_context


GROUPS = [{"label": "Invented component examples", "controls": [
    {"id": "example-title", "path": "example.title", "label": "Example title", "kind": "text", "help": "Invented input only."},
    {"id": "example-description", "path": "example.description", "label": "Example description", "help": "Keep secrets out."},
    {"id": "example-choice", "path": "example.choice", "label": "Example choice", "kind": "select", "choices": [("one", "Invented choice one")], "help": "Choose explicitly."},
]}]


class DraftPresentationTests(SimpleTestCase):
    def render_draft(self, **kwargs):
        return render_to_string("rms/hypothesis_draft_shell.html", {
            **navigation_context(section="hypotheses", role="editor"),
            **draft_presentation(GROUPS, **kwargs),
        })

    def test_validation_preserves_raw_input_and_escapes_content(self):
        html = self.render_draft(submitted={
            "example.title": "  invented unsaved title  ",
            "example.description": "</textarea><script>invented()</script>",
        }, issues=[{"path": "example.title", "message": "Invented server field error"}])
        self.assertIn("value=\"  invented unsaved title  \"", html)
        self.assertIn("&lt;/textarea&gt;&lt;script&gt;invented()&lt;/script&gt;", html)
        self.assertNotIn("<script>invented()", html)
        self.assertIn("aria-invalid=\"true\"", html)
        self.assertIn("example-title-errors", html)
        self.assertIn("data-error-summary", html)
        self.assertIn("href=\"#example-title\"", html)

    def test_conflict_does_not_replace_or_retry_input(self):
        html = self.render_draft(submitted={"example.title": "losing unsaved input"}, conflict=True)
        self.assertIn("value=\"losing unsaved input\"", html)
        self.assertIn("Do not overwrite or automatically retry", html)
        self.assertNotIn("data-api-url", html)

    def test_unknown_choice_remains_visible_not_silently_replaced(self):
        html = self.render_draft(submitted={"example.choice": "invented-unknown"})
        self.assertIn("value=\"invented-unknown\" selected", html)
        self.assertIn("Submitted input: invented-unknown", html)
        self.assertNotIn("value=\"one\" selected", html)

    def test_no_preselected_default_and_no_save_capability(self):
        html = self.render_draft()
        self.assertIn("Choose explicitly — no default", html)
        self.assertIn("disabled>Save draft (not connected)", html)
        self.assertIn("Reload persistence is not available", html)
        self.assertNotIn("name=\"status\"", html)

    def test_inline_context_links_keep_same_document(self):
        html = self.render_draft()
        self.assertIn("href=\"#research-context\"", html)
        self.assertIn("href=\"#hypothesis-fields\"", html)
        self.assertIn("Case state: proposed", html)

    def test_general_error_has_no_invented_field_target(self):
        html = self.render_draft(issues=[{"path": "not-a-control", "message": "Invented general failure"}])
        self.assertIn("<li>Invented general failure</li>", html)
        self.assertNotIn("href=\"#not-a-control\"", html)

    def test_presentation_does_not_mutate_inputs(self):
        original = deepcopy(GROUPS)
        submitted = {"example.title": "Unchanged raw input"}
        draft_presentation(GROUPS, submitted=submitted)
        self.assertEqual(GROUPS, original)
        self.assertEqual(submitted, {"example.title": "Unchanged raw input"})
