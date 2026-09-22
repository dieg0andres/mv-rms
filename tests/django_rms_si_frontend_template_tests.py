from django.template.loader import render_to_string
from django.test import SimpleTestCase

SOURCE = {"source_version_id": "SRCV-00000000-0000-4000-8000-000000000001", "source_id": "fictional-source", "version": 2, "title": "Fictional Source", "citation": "Invented citation"}

class RmsSiFrontendTemplateTests(SimpleTestCase):
    def test_source_editor_has_required_identity_and_reasoned_correction(self):
        html = render_to_string("rms/source_editor.html", {"api_url":"/api/v1/sources", "correction":False, "source_fields": [{"name":"title", "label":"Title", "required":True}, {"name":"citation", "label":"Citation", "required":True}]})
        self.assertIn('name="source_id"', html); self.assertIn('name="title"', html); self.assertIn('name="content_file"', html)
    def test_idea_editor_uses_exact_source_version_not_source_id(self):
        html = render_to_string("rms/idea_editor.html", {"api_url":"/api/v1/ideas", "correction":False, "idea_fields": [{"name":"title", "label":"Title", "required":True}], "source_versions":[SOURCE]})
        self.assertIn(SOURCE["source_version_id"], html); self.assertIn('name="contribution"', html); self.assertNotIn('name="source_id"', html)
    def test_history_shows_correction_and_contribution(self):
        v={"idea_version_id":"IDEV-00000000-0000-4000-8000-000000000001","version":2,"corrects_idea_version_id":"IDEV-older","correction_reason":"Clarified fictional claim.","changed_fields":["testable_claim"],"created_at":"2026-09-22T14:00:00.000000Z","created_by":"editor","workflow_status":"rejected","rejection_reason":"Synthetic rejection","title":"Fictional Idea","mechanism":"Invented mechanism","testable_claim":"Invented claim","falsification":"Invented falsification","eligible_market":"equities","contributions":[{"source_version_id":SOURCE["source_version_id"],"source_id":"fictional-source","version":2,"contribution":"Exact contribution","source_summary":SOURCE}]}
        html=render_to_string("rms/idea_history.html", {"idea_id":"IDE-test", "versions":[v]})
        for expected in (v["idea_version_id"],v["corrects_idea_version_id"],v["correction_reason"],"testable_claim",SOURCE["source_version_id"],"Exact contribution"): self.assertIn(expected,html)
