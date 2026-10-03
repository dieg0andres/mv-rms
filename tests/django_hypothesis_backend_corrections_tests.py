"""Director corrections: DB-free regressions, never ordinary-role/SQL proof."""

from copy import deepcopy
import hashlib
import importlib
import json
from types import SimpleNamespace
from unittest.mock import Mock, patch

from tests.django_hypothesis_backend_source_tests import DatabaseFreeCase, actor
from rest_framework.test import APIRequestFactory, force_authenticate
from tests.django_hypothesis_backend_validation_tests import assessment, create_payload
from tests.django_research_context_backend_source_tests import version
from rms import hypothesis_api, research_context_services as context
from rms.hypothesis_assessment_links import assessment_link_seal
from rms.hypothesis_models import (
    AssessmentExternalReference, Investigation, InvestigationVersion,
    PriorResearchAssessment, PriorResearchAssessmentVersion, ResearchAssociation,
    ResearchAssociationIdentity, ResearchFamily, ResearchFamilyVersion,
)
from rms.models import Idea, IdeaVersion, Source, SourceVersion
from rms.research_context_common import (
    AuthenticationRequired, Forbidden, append, wire,
)
from rms.services import ResourceNotFound, StoredResponse, canonical_json_bytes


class JSONTransportCorrections(DatabaseFreeCase):
    def invoke(self, body, media_type, user=None):
        request = APIRequestFactory().post("/api/v1/hypotheses", body, content_type=media_type,
                                           HTTP_IDEMPOTENCY_KEY="invented-key")
        if user is not None:
            force_authenticate(request, user=user)
        view = hypothesis_api.ResearchRecordView.as_view(resource="hypotheses")
        return view(request)

    def test_plain_and_parameterized_json_reach_the_shared_service(self):
        payload = create_payload()
        user = actor()
        original = hypothesis_api.RESOURCES["hypotheses"]
        create = Mock(return_value=StoredResponse(201, b'{"stable_id":"HYP-invented"}'))
        with patch.dict(hypothesis_api.RESOURCES, {"hypotheses": (create, *original[1:])}):
            for media_type in ("application/json", "application/json; charset=utf-8"):
                with self.subTest(media_type=media_type):
                    response = self.invoke(json.dumps(payload), media_type, user)
                    self.assertEqual(response.status_code, 201)
                    create.assert_called_with(actor=user, idempotency_key="invented-key", payload=payload)

    def test_malformed_json_and_unsupported_media_fail_without_service_calls(self):
        original = hypothesis_api.RESOURCES["hypotheses"]
        create = Mock()
        with patch.dict(hypothesis_api.RESOURCES, {"hypotheses": (create, *original[1:])}):
            for body, media_type in ((b'{"title":', "application/json; charset=utf-8"),
                                     (b"secret payload", "text/plain"),
                                     (b"title=secret", "application/x-www-form-urlencoded")):
                with self.subTest(media_type=media_type):
                    response = self.invoke(body, media_type, actor())
                    self.assertEqual(response.status_code, 400)
                    self.assertEqual(response.data["error"]["code"], "validation_error")
                    self.assertNotIn("secret", json.dumps(response.data))
        create.assert_not_called()

    def test_parameterized_malformed_requests_preserve_authentication_and_viewer_denials(self):
        for user, status in ((None, 401), (actor(False), 403)):
            response = self.invoke(b"invalid JSON", "application/json; charset=utf-8", user)
            self.assertEqual(response.status_code, status)
            if status == 401:
                self.assertTrue(response["WWW-Authenticate"].startswith("Basic"))


class ClassificationReaderCorrections(DatabaseFreeCase):
    def setUp(self):
        super().setUp()
        self.idea = IdeaVersion(idea=Idea(idea_id="IDE-invented"), version=1,
                                idea_version_id=create_payload()["originating_idea_version_id"])
        self.family = version(ResearchFamilyVersion, ResearchFamily(public_id="RFAM-invented"), "RFAMV-invented")
        self.record = ResearchAssociationIdentity(public_id="IFA-invented", idea_version=self.idea, latest_version=2)
        self.first = version(ResearchAssociation, self.record, "IFAV-first", kind="IdeaFamily",
                             idea_version=self.idea, family_version=self.family, rationale="Original grouping")
        self.second = version(ResearchAssociation, self.record, "IFAV-second", kind="IdeaFamily",
                              idea_version=self.idea, family_version=self.family, rationale="Explicit corrected grouping")
        self.second.version = 2
        self.second.corrects_version = 1
        self.second.correction_reason = "Explain the reclassification"

    def test_current_exact_and_history_serialize_distinct_immutable_versions(self):
        def latest(model, identity, *, version=None):
            return self.record, self.first if version == 1 else self.second
        visible = Mock()
        visible.filter.return_value.order_by.return_value = [self.first, self.second]
        with patch.object(context, "latest", side_effect=latest), \
             patch.object(context, "resolve"), \
             patch.object(context, "visible", return_value=visible), \
             patch.object(ResearchAssociation.objects, "get", return_value=self.first):
            current = context.get_idea_family_association(actor=actor(False), association_id=self.record.public_id)
            exact = context.get_idea_family_association(actor=actor(False), association_id=self.record.public_id, version=1)
            history = context.get_idea_family_association_history(actor=actor(False), association_id=self.record.public_id)
        self.assertEqual(current["version_id"], "IFAV-second")
        self.assertEqual(exact["version_id"], "IFAV-first")
        self.assertEqual(exact["rationale"], "Original grouping")
        self.assertEqual([v["version"] for v in history["results"]], [1, 2])
        self.assertEqual(history["results"][1]["correction_reason"], "Explain the reclassification")
        self.assertEqual(current["supersedes_version_id"], "IFAV-first")
        self.assertEqual(exact["links"]["self"], "/api/v1/idea-family-associations/IFA-invented/versions/1")
        visible.filter.assert_called_once_with(record=self.record)
        visible.filter.return_value.order_by.assert_called_once_with("version")

    def test_lookup_by_exact_idea_returns_current_assignment(self):
        qs = Mock()
        qs.get.return_value = self.record
        with patch.object(context, "resolve", return_value=self.idea) as resolve, \
             patch.object(context, "visible", return_value=qs), \
             patch.object(context, "get_idea_family_association", return_value={"version_id": "IFAV-second"}) as read:
            result = context.get_idea_family_for_idea(actor=actor(False), idea_version_id=self.idea.idea_version_id)
        resolve.assert_called_once_with(IdeaVersion, self.idea.idea_version_id)
        qs.get.assert_called_once_with(idea_version=self.idea)
        self.assertEqual(read.call_args.kwargs["association_id"], "IFA-invented")
        self.assertEqual(result["version_id"], "IFAV-second")

    def test_anonymous_and_inactive_service_readers_deny_before_retrieval(self):
        calls = (
            lambda user: context.get_idea_family_association(actor=user, association_id="hidden"),
            lambda user: context.get_idea_family_association_history(actor=user, association_id="hidden"),
            lambda user: context.get_idea_family_for_idea(actor=user, idea_version_id="hidden"),
        )
        with patch.object(context, "latest") as latest, patch.object(context, "resolve") as resolve:
            for call in calls:
                for user, error in ((None, AuthenticationRequired), (actor(active=False), Forbidden)):
                    with self.assertRaises(error):
                        call(user)
        latest.assert_not_called()
        resolve.assert_not_called()

    def test_unclassified_hidden_and_wrong_kind_use_uniform_not_found(self):
        qs = Mock()
        qs.get.side_effect = ResearchAssociationIdentity.DoesNotExist
        with patch.object(context, "resolve", return_value=self.idea), patch.object(context, "visible", return_value=qs):
            with self.assertRaises(ResourceNotFound):
                context.get_idea_family_for_idea(actor=actor(False), idea_version_id=self.idea.idea_version_id)
        with patch.object(context, "latest", side_effect=ResourceNotFound):
            with self.assertRaises(ResourceNotFound):
                context.get_idea_family_association(actor=actor(False), association_id="hidden")
        with patch.object(context, "latest", return_value=(self.record, self.first)), \
             patch.object(context, "resolve", side_effect=ResourceNotFound):
            with self.assertRaises(ResourceNotFound):
                context.get_idea_family_association(actor=actor(False), association_id=self.record.public_id)
        self.first.kind = "AssessmentRecord"
        with patch.object(context, "latest", return_value=(self.record, self.first)):
            with self.assertRaises(ResourceNotFound):
                context.get_idea_family_association(actor=actor(False), association_id=self.record.public_id)

    def test_api_lookup_uses_shared_reader_and_rejects_extra_query_fields(self):
        view = hypothesis_api.ResearchRecordView.as_view(resource="idea-family-associations")
        with patch.object(context, "get_idea_family_for_idea", return_value={"version_id": "IFAV-second"}) as read:
            user = actor(False)
            request = APIRequestFactory().get("/api/v1/idea-family-associations", {"idea_version_id": self.idea.idea_version_id})
            force_authenticate(request, user=user)
            self.assertEqual(view(request).status_code, 200)
            read.assert_called_once_with(actor=user, idea_version_id=self.idea.idea_version_id)
            read.reset_mock()
            request = APIRequestFactory().get("/api/v1/idea-family-associations", {"idea_version_id": self.idea.idea_version_id, "page": "1"})
            force_authenticate(request, user=user)
            self.assertEqual(view(request).status_code, 400)
            read.assert_not_called()


class AssessmentSealCorrections(DatabaseFreeCase):
    def setUp(self):
        super().setUp()
        self.fields = {k: v for k, v in assessment().items() if k != "record_links"}
        self.record = PriorResearchAssessment(public_id="PRA-invented")
        self.item = version(PriorResearchAssessmentVersion, self.record, "PRAV-first", fields=self.fields,
                            **assessment_link_seal([]))
        self.source = SourceVersion(source=Source(source_id="invented-source"), source_version_id="SRCV-invented", version=1)
        self.internal = version(ResearchAssociation, ResearchAssociationIdentity(), "RASV-link", kind="AssessmentRecord",
                                assessment_version=self.item, source_version=self.source, position=1)
        self.external = version(AssessmentExternalReference, ResearchAssociationIdentity(), "AERV-link",
                                assessment_version=self.item, reference="Invented external\nUnicode: é : reference", position=2)
        self.internal_manager = Mock()
        self.external_manager = Mock()
        self.internal_manager.filter.return_value.order_by.return_value = []
        self.external_manager.order_by.return_value = []
        for name, manager in (("research_associations", self.internal_manager), ("external_references", self.external_manager)):
            patcher = patch.object(PriorResearchAssessmentVersion, name, manager)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_commitment_covers_order_kind_version_and_external_utf8_content(self):
        links = [{"kind": "source", "version_id": self.source.source_version_id},
                 {"kind": "external_document", "reference": self.external.reference}]
        reference_digest = hashlib.sha256(self.external.reference.encode("utf-8")).hexdigest()
        expected = hashlib.sha256(f"1:source:SRCV-invented\n2:external_document:{reference_digest}\n".encode()).hexdigest()
        seal = assessment_link_seal(links)
        self.assertEqual(seal, {"link_count": 2, "link_digest": expected})
        for altered in (list(reversed(links)), links[:1],
                        [{"kind": "idea", "version_id": "IDEV-invented"}, links[1]],
                        [links[0], {"kind": "external_document", "reference": self.external.reference + " changed"}]):
            self.assertNotEqual(assessment_link_seal(altered), seal)

    def test_empty_set_and_late_internal_external_inserts_fail_closed(self):
        before = context.assessment_read(self.item)
        self.assertEqual(before["fields"]["record_links"], [])
        self.assertEqual(self.item.link_digest, hashlib.sha256(b"").hexdigest())
        self.internal_manager.filter.return_value.order_by.return_value = [self.internal]
        with self.assertRaises(context.AssessmentIntegrityError):
            context.assessment_read(self.item)
        self.internal_manager.filter.return_value.order_by.return_value = []
        self.external.position = 1
        self.external_manager.order_by.return_value = [self.external]
        with self.assertRaises(context.AssessmentIntegrityError):
            context.assessment_read(self.item)
        self.external_manager.order_by.return_value = []
        self.assertEqual(context.assessment_read(self.item), before)

    def test_declared_mixed_links_roundtrip_but_gaps_or_duplicate_positions_fail(self):
        links = [{"kind": "source", "version_id": self.source.source_version_id},
                 {"kind": "external_document", "reference": self.external.reference}]
        seal = assessment_link_seal(links)
        self.item.link_count, self.item.link_digest = seal["link_count"], seal["link_digest"]
        self.internal_manager.filter.return_value.order_by.return_value = [self.internal]
        self.external_manager.order_by.return_value = [self.external]
        before = context.assessment_read(self.item)
        self.assertEqual(before["fields"]["record_links"], links)
        for position in (1, 3):
            self.external.position = position
            with self.assertRaises(context.AssessmentIntegrityError):
                context.assessment_read(self.item)
        self.external.position = 2
        self.assertEqual(context.assessment_read(self.item), before)

    def test_successor_link_changes_preserve_old_case_context_and_version_digest(self):
        before = context.assessment_read(self.item)
        newer_links = [{"kind": "external_document", "reference": "Explicit v2 review reference"}]
        newer = version(PriorResearchAssessmentVersion, self.record, "PRAV-second", fields=deepcopy(self.fields),
                        **assessment_link_seal(newer_links))
        newer.version = 2
        newer.corrects_version = 1
        newer.correction_reason = "Update the explicitly reviewed links"
        case = version(InvestigationVersion, Investigation(public_id="INV-original"), "INVV-original", fields={"title": "Original case"})
        family = version(ResearchFamilyVersion, ResearchFamily(public_id="RFAM-original"), "RFAMV-original")
        family_edge = version(ResearchAssociation, ResearchAssociationIdentity(), "RASV-family", kind="InvestigationFamily", family_version=family, investigation_version=case)
        assessment_edge = version(ResearchAssociation, ResearchAssociationIdentity(), "RASV-assessment", kind="PriorResearchInvestigation", assessment_version=self.item, investigation_version=case)
        with patch.object(context, "edge", side_effect=lambda item, kind: family_edge if kind == "InvestigationFamily" else assessment_edge):
            old_case_before = context.investigation_read(case)
            with patch.object(PriorResearchAssessmentVersion.objects, "get", return_value=self.item):
                self.external.reference, self.external.position = newer_links[0]["reference"], 1
                self.external.assessment_version = newer
                self.external_manager.order_by.return_value = [self.external]
                updated = context.assessment_read(newer)
            self.external_manager.order_by.return_value = []
            self.assertEqual(context.investigation_read(case), old_case_before)
        self.assertEqual(updated["fields"]["record_links"], newer_links)
        self.assertEqual(context.assessment_read(self.item), before)
        self.assertEqual(assessment_edge.assessment_version.public_id, "PRAV-first")

    def test_save_commits_link_seal_before_creating_any_link_rows(self):
        fields = {**self.fields, "record_links": [{"kind": "source", "version_id": self.source.source_version_id}]}
        with patch.object(PriorResearchAssessment.objects, "create", return_value=self.record), \
             patch.object(context, "append", return_value=self.item) as parent, \
             patch.object(context, "association") as child:
            context.save_assessment(actor=actor(), fields=fields, resolved=[("source_version", self.source)])
        saved = parent.call_args.kwargs
        self.assertEqual({k: saved[k] for k in ("link_count", "link_digest")}, assessment_link_seal(fields["record_links"]))
        self.assertNotIn("record_links", saved["fields"])
        child.assert_called_once_with("AssessmentRecord", actor=parent.call_args.kwargs["actor"], assessment_version=self.item, position=1, source_version=self.source)

    def test_parent_row_digest_binds_the_seal_without_storing_json_relationships(self):
        with patch.object(PriorResearchAssessmentVersion, "save"), patch.object(self.record, "refresh_from_db"):
            item = append(PriorResearchAssessmentVersion, actor=actor(), record=self.record,
                          fields=self.fields, **assessment_link_seal([]))
        content = {f.attname: wire(getattr(item, f.attname)) for f in item._meta.concrete_fields if f.name != "row_digest"}
        self.assertEqual(item.row_digest, hashlib.sha256(canonical_json_bytes(content)).hexdigest())
        content.update(assessment_link_seal([{"kind": "source", "version_id": self.source.source_version_id}]))
        self.assertNotEqual(item.row_digest, hashlib.sha256(canonical_json_bytes(content)).hexdigest())
        self.assertNotIn("record_links", item.fields)

    def test_source_guards_cover_parent_empty_set_and_both_child_tables(self):
        # Structural coverage only. Execution and application-role denials are
        # expressly unverified until the preserving DB facility is released.
        sql = importlib.import_module("rms.migrations.0005_hypothesis_history_guards").guard_sql()
        for table in ("rms_priorresearchassessmentversion", "rms_researchassociation", "rms_assessmentexternalreference"):
            self.assertIn(f"hn_assessment_links AFTER INSERT ON {table} DEFERRABLE INITIALLY DEFERRED", sql)
        self.assertIn("actual_count <> expected_count", sql)
        self.assertIn("actual_digest IS DISTINCT FROM expected_digest", sql)
        self.assertIn("distinct_positions <> actual_count", sql)
