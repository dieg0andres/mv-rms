"""Disposable Engineering coverage for MAU-181; not the independent verdict."""

from copy import deepcopy
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from rms.hypothesis_fixture import hypothesis_fields
from rms.hypothesis_models import HypothesisVersion, InvestigationVersion, ResearchFamilyVersion
from rms.hypothesis_validation import SCHEMA
from rms.models import IdempotencyRecord
from rms.navigation_views import flatten_input
from rms.research_context_services import create_research_family
from rms.services import create_source
from rms.test_plan_models import TestPlanVersion
from tests.django_hypothesis_backend_validation_tests import create_payload
from tests.django_run_assurance_tests import principal
from tests.test_test_plan_backend_validation import complete_fixture


class AuthoringWorkflow:
    def prepare(self, editor, unrelated, viewer):
        self.suffix = 'mau181-eng-' + uuid4().hex[:12]
        self.editor, self.unrelated, self.viewer = editor, unrelated, viewer
        scratch = TemporaryDirectory(dir=os.environ.get('PAPERCLIP_RUN_SCRATCH_DIR'))
        self.addCleanup(scratch.cleanup)
        self.scope_file = Path(scratch.name) / 'scope.json'
        settings = override_settings(RMS_RR14_SCOPE_FILE=self.scope_file)
        settings.enable()
        self.addCleanup(settings.disable)
        self.grants = {str(actor.pk): {'username': actor.get_username(), 'cases': [], 'plans': []}
                       for actor in (editor, unrelated, viewer)}
        self.grant = self.grants[str(editor.pk)]
        self.update_scope()
        self.http = APIClient()

    def update_scope(self):
        replacement = self.scope_file.with_suffix('.tmp')
        replacement.write_text(json.dumps({'format': 'rr14-disposable-synthetic-v1', 'principals': self.grants}))
        replacement.replace(self.scope_file)

    def save(self, route, key, payload, *, actor=None):
        self.http.force_authenticate(self.editor if actor is None else actor)
        return self.http.post('/api/v1/' + route, payload, format='json', HTTP_IDEMPOTENCY_KEY=f'{self.suffix}:{key}')

    def ack(self, response, status=201):
        self.assertEqual(response.status_code, status, response.content)
        self.assertEqual(response.json(), {'saved': True})
        self.assertNotIn('Location', response)
        self.assertIn('no-store', response['Cache-Control'])

    def deny(self, response, *hidden, status=404):
        self.assertEqual(response.status_code, status, response.content)
        data = response.json()
        self.assertEqual(set(data), {'error'})
        self.assertIn('no-store', response['Cache-Control'])
        for token in hidden:
            self.assertNotIn(token, response.content.decode())

    def family_payload(self):
        return {'fields': {'name': self.suffix, 'mechanism_boundary': 'Invented mechanism only.',
                           'distinctness_rule': 'Invented software boundary; no credit.', 'risk_review_reference': None}}

    def test_browser_form_csrf_and_generic_acknowledgement(self):
        browser = APIClient(enforce_csrf_checks=True)
        browser.force_authenticate(self.editor)
        url = '/research-families/new'
        page = browser.get(url)
        self.assertEqual(page.status_code, 200, page.content)
        token = re.search(rb'name="csrfmiddlewaretoken" value="([a-zA-Z0-9]+)"', page.content).group(1).decode()
        data = {**flatten_input(self.family_payload()), 'idempotency_key': self.suffix + ':family-browser', 'operation': 'save'}
        self.assertEqual(browser.post(url, data).status_code, 403)
        saved = browser.post(url, {**data, 'csrfmiddlewaretoken': token})
        self.assertEqual(saved.status_code, 201, saved.content)
        family = ResearchFamilyVersion.objects.get(fields__name=self.suffix)
        self.assertNotIn(family.public_id.encode(), saved.content)
        self.assertNotIn(family.record.public_id.encode(), saved.content)
        self.assertNotIn('Location', saved)
        self.assertIn('no-store', saved['Cache-Control'])
        denied = browser.post(url, {**data, 'csrfmiddlewaretoken': token})
        self.assertEqual(denied.status_code, 404, denied.content)
        self.assertNotIn(family.public_id.encode(), denied.content)

    def test_exact_discovery_and_legacy_redaction(self):
        family_payload = self.family_payload()
        route = 'research-families'
        self.ack(self.save(route, 'family', family_payload))
        exact = ResearchFamilyVersion.objects.get(fields__name=self.suffix)
        self.deny(self.save(route, 'family', family_payload), exact.public_id)
        self.assertEqual(self.http.get('/api/v1/research-families').json()['count'], 0)
        self.grant['family_versions'] = [exact.public_id]
        self.update_scope()
        self.assertEqual(self.http.get('/api/v1/research-families').json()['results'][0]['version_id'], exact.public_id)
        self.ack(self.save(route, 'family', family_payload))
        self.assertEqual(ResearchFamilyVersion.objects.filter(fields__name=self.suffix).count(), 1)
        changed = deepcopy(family_payload)
        changed['fields']['mechanism_boundary'] = 'Changed payload.'
        self.assertEqual(self.save(route, 'family', changed).status_code, 409)
        self.deny(self.save(route, 'viewer', family_payload, actor=self.viewer), exact.public_id, status=403)
        legacy = create_research_family(actor=self.editor, idempotency_key=self.suffix + ':legacy', payload=family_payload)
        legacy_version = json.loads(legacy.body)['version_id']
        self.deny(self.save(route, 'legacy', family_payload), legacy_version)
        self.grant['family_versions'].append(legacy_version)
        self.update_scope()
        self.ack(self.save(route, 'legacy', family_payload))
        correction = {'fields': changed['fields'], 'expected_latest_version': 1, 'correction_reason': 'Invented corrected wording.'}
        family_route = f'{route}/{exact.record.public_id}/corrections'
        self.ack(self.save(family_route, 'family-revise', correction))
        revised = exact.record.versions.get(version=2)
        self.deny(self.save(family_route, 'family-revise', correction), revised.public_id)
        self.grant['family_versions'].append(revised.public_id)
        self.update_scope()
        self.ack(self.save(family_route, 'family-revise', correction))
        self.assertEqual(self.save(family_route, 'family-stale', correction).status_code, 409)
        self.grant['family_versions'] = []
        self.update_scope()
        self.deny(self.save(route, 'legacy', family_payload), legacy_version)

    def test_scoped_case_and_hypothesis(self):
        source = create_source(source_id=self.suffix, content=b'Invented source for software verification.',
            actor=self.editor.get_username(), idempotency_key=self.suffix + ':source', request_path='/api/v1/sources',
            fields={'title': self.suffix, 'source_type': 'other', 'citation': 'Invented E181 fixture.',
                    'observed_available_at': datetime(2026, 10, 3, tzinfo=timezone.utc), 'authors': None,
                    'publisher': None, 'published_at': None, 'canonical_url': None, 'rights_note': 'Invented only.'})
        idea_payload = {'synthetic': True, 'title': self.suffix, 'mechanism': 'Invented mechanism.',
            'testable_claim': 'Invented claim.', 'falsification': 'Invented falsification.', 'eligible_market': 'etfs',
            'workflow_status': 'draft', 'rejection_reason': None,
            'contributions': [{'source_version_id': json.loads(source.body)['latest_source_version_id'], 'contribution': 'Invented rationale.'}]}
        idea = self.save('ideas', 'idea', idea_payload)
        self.assertEqual(idea.status_code, 201, idea.content)
        idea_version = idea.json()['latest_idea_version_id']
        self.ack(self.save('research-families', 'family', self.family_payload()))
        family = ResearchFamilyVersion.objects.get(fields__name=self.suffix)
        self.grant['family_versions'] = [family.public_id]
        self.update_scope()
        case_payload = {'family_version_id': family.public_id, 'fields': {'title': self.suffix, 'owner_role': 'Research',
            'priority': 'normal', 'next_action': 'Inspect only the invented fixture.', 'blocker_text': None},
            'prior_research_assessment': {'query_scope': 'Invented Idea only.', 'query_time': '2026-10-03T00:00:00Z',
                'policy_version': SCHEMA['$defs']['AssessmentFields']['properties']['policy_version']['const'],
                'result_watermark': 'Pinned invented Idea.', 'finding': 'extends', 'rationale': 'Invented fixture only.',
                'limitations': 'No real data.', 'record_links': [{'kind': 'idea', 'version_id': idea_version}]}}
        self.deny(self.save('investigations', 'case', case_payload, actor=self.unrelated), family.public_id)
        self.ack(self.save('investigations', 'case', case_payload))
        case = InvestigationVersion.objects.get(fields__title=self.suffix)
        self.deny(self.save('investigations', 'case', case_payload), case.public_id)
        self.grant['cases'] = [case.record.public_id]
        self.update_scope()
        self.ack(self.save('investigations', 'case', case_payload))
        hypothesis_payload = create_payload()
        hypothesis_payload.update(originating_idea_version_id=idea_version, investigation_version_id=case.public_id,
            idea_family_binding={'mode': 'create', 'family_version_id': family.public_id, 'rationale': 'Invented grouping only.'})
        hypothesis_payload['fields'] = {**hypothesis_fields(), 'title': self.suffix}
        self.ack(self.save('hypotheses', 'hypothesis', hypothesis_payload))
        hypothesis = HypothesisVersion.objects.get(fields__title=self.suffix)
        self.assertEqual(self.http.get('/api/v1/hypotheses').json()['count'], 0)
        self.deny(self.save('hypotheses', 'hypothesis', hypothesis_payload), hypothesis.public_id)
        self.grant['hypotheses'] = [hypothesis.record.public_id]
        self.update_scope()
        self.ack(self.save('hypotheses', 'hypothesis', hypothesis_payload))
        root = '/api/v1/hypotheses/' + hypothesis.record.public_id
        exact = self.http.get(root + '/versions/1').json()
        classification = exact['research_context']['idea_family_association']['version_id']
        classification_id = exact['research_context']['idea_family_association']['stable_id']
        plan_payload = complete_fixture()
        plan_payload.update(hypothesis_version_id=hypothesis.public_id)
        plan_payload['fields']['title'] = self.suffix
        self.ack(self.save('test-plans', 'plan', plan_payload))
        saved_plan = TestPlanVersion.objects.get(fields__title=self.suffix)
        self.grant['plans'] = [saved_plan.record.public_id]
        self.update_scope()
        self.assertEqual(self.http.get('/api/v1/test-plans').json()['count'], 1)
        revise_case = deepcopy(case_payload)
        case_root = f'investigations/{case.record.public_id}'
        saved_case = self.http.get('/api/v1/' + case_root).json()
        revise_case.update(expected_latest_version=1, correction_reason='Invented corrected priority.',
            prior_research_assessment={'mode': 'existing', 'assessment_version_id': saved_case['prior_research_assessment']['version_id']})
        revise_case['fields']['priority'] = 'high'
        self.ack(self.save(case_root + '/corrections', 'case-revise', revise_case))
        self.ack(self.save(case_root + '/corrections', 'case-revise', revise_case))
        self.assertEqual(self.http.get('/api/v1/' + case_root + '/versions/1').json()['row_digest'], saved_case['row_digest'])
        revise_classification = {'prior_association_version_id': classification, 'family_version_id': family.public_id,
            'rationale': 'Corrected invented grouping rationale.', 'expected_latest_version': 1, 'correction_reason': 'Invented correction.'}
        class_route = f'idea-family-associations/{classification_id}/corrections'
        self.ack(self.save(class_route, 'class-revise', revise_classification))
        self.ack(self.save(class_route, 'class-revise', revise_classification))
        correction = deepcopy(hypothesis_payload)
        correction.update(expected_latest_version=1, correction_reason='Invented correction.',
                          idea_family_binding={'mode': 'existing', 'association_version_id': classification})
        correction['fields']['title'] += '-corrected'
        route = 'hypotheses/' + hypothesis.record.public_id + '/corrections'
        self.ack(self.save(route, 'revise', correction))
        self.ack(self.save(route, 'revise', correction))
        self.assertEqual(self.save(route, 'stale', correction).status_code, 409)
        self.assertEqual(self.http.get(root + '/versions/1').json()['row_digest'], exact['row_digest'])
        self.grant['cases'] = []
        self.update_scope()
        filters = IdempotencyRecord.objects.filter
        def reject_key_lookup(*args, **kwargs):
            self.assertNotIn('key', kwargs, 'receipt lookup before scope')
            return filters(*args, **kwargs)
        with patch.object(IdempotencyRecord.objects, 'filter', side_effect=reject_key_lookup):
            self.deny(self.save(route, 'revise', correction), hypothesis.public_id, classification)
            self.deny(self.save(class_route, 'class-revise', revise_classification), classification)


class ScopedAuthoringTests(AuthoringWorkflow, TestCase):
    def setUp(self):
        suffix = 'mau181-' + uuid4().hex[:12]
        self.prepare(principal(suffix, 'editor'), principal(suffix + '-unrelated', 'editor'), principal(suffix + '-viewer'))
