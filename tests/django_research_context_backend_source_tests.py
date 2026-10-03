"""Pure context compatibility and historical representation checks."""

from copy import deepcopy
import os
from types import SimpleNamespace
from unittest.mock import Mock, patch

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "rms_project.settings")
import django
django.setup()

from rms.hypothesis_models import (
    Hypothesis, HypothesisVersion, Investigation, InvestigationVersion,
    PriorResearchAssessment, PriorResearchAssessmentVersion,
    ResearchAssociation, ResearchAssociationIdentity, ResearchFamily, ResearchFamilyVersion,
)
from rms.hypothesis_validation import HypothesisValidationError
from rms.models import Idea, IdeaVersion, Source, SourceVersion
from rms import hypothesis_services as services
from rms import research_context_services as context
from rms.research_context_common import endpoint
from tests.django_hypothesis_backend_source_tests import DatabaseFreeCase
from tests.django_hypothesis_backend_validation_tests import create_payload


def version(model, identity, public_id, **kwargs):
    return model(record=identity, public_id=public_id, version=1, row_digest="a" * 64,
                 created_by="invented-editor", **kwargs)


class ContextSourceTests(DatabaseFreeCase):
    def setUp(self):
        super().setUp()
        self.idea = IdeaVersion(idea=Idea(idea_id="IDE-invented"), idea_version_id=create_payload()["originating_idea_version_id"], version=1)
        self.family = version(ResearchFamilyVersion, ResearchFamily(public_id="RFAM-invented"), "RFAMV-invented")
        self.case = version(InvestigationVersion, Investigation(public_id="INV-invented"), create_payload()["investigation_version_id"])
        self.classification = version(ResearchAssociation, ResearchAssociationIdentity(public_id="IFA-invented", latest_version=1), create_payload()["idea_family_binding"]["association_version_id"],
                                      kind="IdeaFamily", idea_version=self.idea, family_version=self.family)
        self.family_edge = version(ResearchAssociation, ResearchAssociationIdentity(public_id="RAS-family"), "RASV-family", kind="InvestigationFamily", investigation_version=self.case, family_version=self.family)

    def resolve(self, payload):
        def lookup(model, public_id):
            return {IdeaVersion: self.idea, InvestigationVersion: self.case, ResearchAssociation: self.classification, ResearchFamilyVersion: self.family}[model]
        with patch("rms.hypothesis_services.resolve", side_effect=lookup), \
             patch("rms.hypothesis_services.edge", return_value=self.family_edge):
            return services.resolve_context(payload)

    def test_compatible_existing_family_returns_exact_versions(self):
        idea, case, classification = self.resolve(create_payload())
        self.assertIs(idea, self.idea)
        self.assertIs(case, self.case)
        self.assertIs(classification, self.classification)

    def test_cross_family_or_second_origin_binding_rejected(self):
        other_family = ResearchFamily(public_id="RFAM-other")
        for changes in ({"family_version": version(ResearchFamilyVersion, other_family, "RFAMV-other")}, {"idea_version": IdeaVersion(idea=Idea(), idea_version_id="IDEV-other", version=1)}):
            previous = {key: getattr(self.classification, key) for key in changes}
            for key, value in changes.items():
                setattr(self.classification, key, value)
            with self.assertRaises(HypothesisValidationError):
                self.resolve(create_payload())
            for key, value in previous.items():
                setattr(self.classification, key, value)

    def test_exact_historical_family_assignment_is_not_silently_replaced(self):
        self.classification.record.latest_version = 2
        self.assertIs(self.resolve(create_payload())[2], self.classification)

    def test_create_binding_requires_exact_case_family_and_unclassified_idea(self):
        payload = create_payload()
        payload["idea_family_binding"] = {"mode": "create", "family_version_id": self.family.public_id, "rationale": "Explicit invented assignment"}
        with patch("rms.hypothesis_services.ResearchAssociationIdentity.objects.filter") as identities:
            identities.return_value.exists.return_value = False
            self.assertIsNone(self.resolve(payload)[2])
            identities.return_value.exists.return_value = True
            with self.assertRaises(HypothesisValidationError) as caught:
                self.resolve(payload)
            self.assertEqual(caught.exception.issues[0]["code"], "already_classified")

    def test_historical_serializer_keeps_origin_source_context_and_separate_notice(self):
        hyp = version(HypothesisVersion, Hypothesis(public_id="HYP-invented"), "HYPV-invented", fields={"title": "Invented incomplete historical draft"})
        origin = version(ResearchAssociation, ResearchAssociationIdentity(public_id="RAS-origin"), "RASV-origin", kind="IdeaHypothesis",
                         idea_version=self.idea, hypothesis_version=hyp, idea_family_version=self.classification, rationale="Invented direct origin", origin_type="direct")
        case_edge = version(ResearchAssociation, ResearchAssociationIdentity(public_id="RAS-case"), "RASV-case", kind="HypothesisInvestigation", hypothesis_version=hyp, investigation_version=self.case)
        assessment = version(PriorResearchAssessmentVersion, PriorResearchAssessment(public_id="PRA-invented"), "PRAV-invented")
        assessment_edge = version(ResearchAssociation, ResearchAssociationIdentity(public_id="RAS-assessment"), "RASV-assessment", kind="PriorResearchInvestigation", assessment_version=assessment, investigation_version=self.case)
        source = SourceVersion(source=Source(source_id="invented-source"), source_version_id="SRCV-invented-original", version=1)
        newer = SourceVersion(source=source.source, source_version_id="SRCV-invented-newer", version=2)
        contributions = Mock()
        contributions.select_related.return_value.order_by.return_value = [SimpleNamespace(source_version=source, contribution_id="SIE-invented")]
        impacts = Mock()
        impacts.order_by.return_value = [SimpleNamespace(public_id="HCIV-invented", newer_source_id=newer.pk, pinned_source=source, newer_source=newer,
                                                        newer_idea_id=None, newer_family_id=None, newer_investigation_id=None, newer_assessment_id=None, newer_association_id=None)]
        def lookup(item, kind):
            return {"IdeaHypothesis": origin, "HypothesisInvestigation": case_edge, "InvestigationFamily": self.family_edge, "PriorResearchInvestigation": assessment_edge}[kind]
        before = deepcopy(hyp.fields)
        with patch("rms.hypothesis_services.edge", side_effect=lookup), \
             patch.object(IdeaVersion, "contributions", contributions), \
             patch.object(HypothesisVersion, "correction_impacts", impacts):
            result = services.hypothesis_read(hyp)
            upstream = services.pinned_upstream(hyp)
        self.assertIn(("source", source), upstream)
        self.assertIn(("idea", self.idea), upstream)
        self.assertEqual(result["origin"]["idea"], endpoint(self.idea))
        self.assertEqual(result["origin"]["sources"][0]["source"]["version_id"], source.source_version_id)
        self.assertEqual(result["research_context"]["family"], endpoint(self.family))
        self.assertEqual(result["research_context"]["assessment"], endpoint(assessment))
        self.assertEqual(result["upstream_notices"][0]["newer"]["version_id"], newer.source_version_id)
        self.assertEqual(result["status"], "draft")
        self.assertEqual(result["draft_completeness"], "incomplete")
        from django.urls import resolve
        self.assertEqual(resolve(result["links"]["origin_idea_history"]).url_name, "idea-history")
        self.assertEqual(result["links"]["origin_idea_history"], "/api/v1/ideas/IDE-invented/versions")
        self.assertEqual(hyp.fields, before)

    def test_transitive_source_correction_targets_original_hypothesis_version(self):
        source = SourceVersion(source=Source(source_id="invented-source"), source_version_id="SRCV-old", version=1)
        newer = SourceVersion(source=source.source, source_version_id="SRCV-new", version=2)
        hyp = version(HypothesisVersion, Hypothesis(public_id="HYP-invented"), "HYPV-original", fields={"title": "Invented"})
        qs = Mock()
        qs.order_by.return_value = [hyp]
        with patch("rms.hypothesis_services.visible", return_value=qs), \
             patch("rms.hypothesis_services.pinned_upstream", return_value=[("idea", self.idea), ("source", source)]), \
             patch("rms.hypothesis_services.add_impact") as add:
            services.record_upstream_impacts("source", newer, actor="invented-editor")
        self.assertEqual(add.call_args.args, (hyp, "source", source, newer))
        self.assertEqual(source.version, 1)
        self.assertEqual(self.idea.version, 1)

    def test_unchanged_hypothesis_snapshot_does_not_append_any_version(self):
        from tests.django_hypothesis_backend_source_tests import actor
        hyp = version(HypothesisVersion, Hypothesis(public_id="HYP-invented", latest_version=1), "HYPV-original", fields={"title": "Invented"})
        origin = version(ResearchAssociation, ResearchAssociationIdentity(public_id="RAS-origin"), "RASV-origin", kind="IdeaHypothesis",
                         idea_version=self.idea, hypothesis_version=hyp, idea_family_version=self.classification, rationale="Same rationale", origin_type="direct")
        case_edge = version(ResearchAssociation, ResearchAssociationIdentity(public_id="RAS-case"), "RASV-case", kind="HypothesisInvestigation", hypothesis_version=hyp, investigation_version=self.case)
        payload = {"fields": hyp.fields, "expected_latest_version": 1, "correction_reason": "No substantive change", "origin_rationale": "Same rationale"}
        def execute(**kwargs):
            return kwargs["operation"](payload)
        with patch("rms.hypothesis_services.execute_write", side_effect=execute), \
             patch("rms.hypothesis_services.latest", return_value=(hyp.record, hyp)), \
             patch("rms.hypothesis_services.resolve_context", return_value=(self.idea, self.case, self.classification)), \
             patch("rms.hypothesis_services.edge", side_effect=lambda item, kind: origin if kind == "IdeaHypothesis" else case_edge), \
             patch("rms.hypothesis_services.hypothesis_read", return_value={"version": 1}), \
             patch("rms.hypothesis_services.append") as append:
            result = services.correct_hypothesis(actor=actor(), hypothesis_id=hyp.record.public_id, idempotency_key="invented", payload=payload)
        self.assertEqual(result, (200, {"version": 1}))
        append.assert_not_called()
