"""Engineering-owned disposable synthetic RR14 fixture (not Test's target)."""

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from urllib.parse import urlencode
from uuid import uuid4

from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from rms.models import IdempotencyRecord, RunAttempt, RunDecision
from rms.record_search import search_versions
from rms.test_plan_models import DataAccessCheck, TestPlan, TestPlanVersion
from rms.test_plan_services import correct_test_plan, record_data_access_check
from rms.test_plan_views import revision_payload
from tests.django_run_assurance_tests import AssuranceWorkflow, principal
from tests.django_run_result_tests import fixture
from tests.test_test_plan_backend_validation import complete_fixture


class RR14Scopes(AssuranceWorkflow, TestCase):
    def setUp(self):
        scratch = TemporaryDirectory(dir=os.environ.get('PAPERCLIP_RUN_SCRATCH_DIR'))
        self.addCleanup(scratch.cleanup)
        self.scope_file = Path(scratch.name) / 'scope.json'
        scope_setting = override_settings(RMS_RR14_SCOPE_FILE=self.scope_file)
        scope_setting.enable()
        self.addCleanup(scope_setting.disable)
        self.principals = {}
        self.suffix = 'rr14-eng-' + uuid4().hex[:12]
        with self.fixture_recipe(self.suffix):
            self.setup_workflow(self.suffix)
        self.scope_for(self.editor)
        self.reader = principal(self.suffix + '-reader')
        self.scope_for(self.reader)
        self.outsider = principal(self.suffix + '-outsider', None)
        self.scope_for(self.outsider)

    def write_scope(self):
        replacement = self.scope_file.with_suffix('.next')
        replacement.write_text(json.dumps({'format': 'rr14-disposable-synthetic-v1', 'principals': self.principals}))
        replacement.chmod(0o600)
        replacement.replace(self.scope_file)

    def fixture_recipe(self, suffix):
        return patch.multiple('rms.management.commands.load_rms_hn_fixture',
                              FIXTURE_ID='RMS-' + suffix, SOURCE_ID='synthetic-' + suffix)

    def scope_for(self, actor, *, plan=None):
        plan = plan or self.plan
        self.principals[str(actor.pk)] = {
            'username': actor.username, 'cases': [plan['research_context']['investigation']['stable_id']],
            'plans': [plan['plan_id']],
        }
        self.write_scope()

    def projection(self):
        return f'{self.root.removesuffix("/runs")}/rr14-origins'

    def check_projection(self, attempts, closure):
        self.as_actor(self.reader)
        response = self.client.get(self.projection())
        self.assertEqual(response.status_code, 200, response.content)
        saved = response.json()
        self.assertEqual(saved['plan_version_id'], self.plan['plan_version_id'])
        self.assertEqual(saved['activity_trials']['count'], len(attempts))
        self.assertEqual({item['id'] for item in saved['activity_trials']['origins']}, set(attempts))
        self.assertEqual(saved['early_closures']['count'], int(closure is not None))
        self.assertEqual(saved['real_credit_from_these_records'], {'full_validation_cycles': 0, 'qualifications': 0})
        self.assertTrue(all(value is None for value in saved['real_totals'].values()))
        if closure:
            (origin,) = saved['early_closures']['origins']
            self.assertEqual(origin['id'], closure['decision_id'])
            self.assertEqual(origin['result_version_id'], self.result.public_id)
            self.assertEqual(origin['result_digest'], self.result.row_digest)
            self.assertEqual(origin['review_id'], closure['review_id'])
            self.assertEqual(origin['digest'], closure['row_digest'])
            self.assertEqual(len(saved['activity_trials']['retry_edges']), 1)
        self.assertEqual(self.client.head(self.projection()).status_code, 200)
        self.assertEqual(self.client.post(self.projection(), {}, format='json').status_code, 405)

    def test_saved_lineage_deltas_and_no_replay_credit(self):
        self.check_projection([], None)
        self.as_actor(self.editor)
        failed = self.register()
        self.assertEqual(self.register(), failed)
        terminal = self.event(failed, 'failed', None)
        retry = self.post(f'{self.root}/{failed}/retry', 'retry-once', {
            'external_reference': f'synthetic:{self.suffix}-retry',
            'expected_event_id': terminal['event_id'], 'reason': 'Invented RR14 retry',
        }).json()
        self.setup_assurance(self.suffix, attempt=retry['run_id'])
        for actor in (self.reviewer, self.decider, self.lesson_author):
            self.scope_for(actor)
        with self.configured():
            review, decision, lesson = self.chain()
            self.as_actor(self.editor)
            self.post(self.result_base, 'result-2', {
                **self.result_payload(self.run, self.completed, value='1'),
                'expected_result_version_id': self.result.public_id, 'correction_reason': 'Invented correction',
            })
        self.check_projection([failed, self.run], decision)
        self.assertEqual(RunDecision.objects.get(public_id=decision['decision_id']).result_id, self.result.pk)
        self.assertTrue(lesson['lesson_id'])

    def test_private_no_store_on_rr14_json_success_and_error_boundary(self):
        case = self.plan['research_context']['investigation']
        case_detail = f"/api/v1/investigations/{case['stable_id']}"
        case_version = case_detail + f"/versions/{case['version']}"
        plan_detail = f"/api/v1/test-plans/{self.plan['plan_id']}"
        plan_version = self.root.removesuffix('/runs')
        pinned = (plan_detail, plan_detail + '/versions', plan_version,
                  case_detail, case_detail + '/history', case_version)

        def check(response, expected):
            self.assertEqual(response.status_code, expected, response.content)
            self.assertEqual(response.get('Cache-Control'), 'private, no-store')

        self.as_actor(self.reader)
        for path in ('/api/v1/test-plans', '/api/v1/investigations', *pinned):
            with self.subTest(path=path):
                check(self.client.get(path), 200)
        check(self.client.head(case_version), 200)
        check(self.client.get(plan_version + '?unexpected=1'), 400)
        self.as_actor(self.editor)
        check(self.client.put(case_version), 405)
        check(self.client.get(case_detail + '/versions/not-an-integer'), 404)

        self.principals.pop(str(self.reader.pk))
        self.write_scope()
        self.as_actor(self.reader)
        for path in pinned:
            with self.subTest(revoked=path):
                check(self.client.get(path), 404)
        self.as_actor(self.outsider)
        check(self.client.get(plan_detail), 403)
        check(self.client.get(case_version), 403)
        check(APIClient().get(plan_version), 401)

    def test_correct_tuple_cannot_reveal_reads_search_or_counts_after_revocation(self):
        self.as_actor(self.editor)
        run = self.register()
        self.setup_assurance(self.suffix, attempt=run)
        case = self.plan['research_context']['investigation']
        family = self.plan['research_context']['family']
        report = self.plan['research_context']['assessment']
        classification = self.plan['research_context']['idea_family_association']['stable_id']
        api_plan = self.root.removesuffix('/runs')
        browser_plan = api_plan.removeprefix('/api/v1')
        paths = [api_plan, api_plan.rsplit('/versions/', 1)[0] + '/versions', self.root,
                 f'{self.root}/{run}', self.url, f'{self.url}/assurance', self.projection(), browser_plan,
                 reverse('rms-case-version', args=[case['stable_id'], case['version']]),
                 reverse('rms-case-history', args=[case['stable_id']]),
                 reverse('rms-family-version', args=[family['stable_id'], family['version']]),
                 reverse('rms-assessment-version', args=[report['stable_id'], report['version']]),
                 reverse('rms-classification-detail', args=[classification])]
        self.as_actor(self.reader)
        for path in paths:
            self.assertEqual(self.client.get(path).status_code, 200, path)

        with self.fixture_recipe(self.suffix + '-unrelated'):
            unrelated, other = fixture(self.suffix + '-unrelated')
        self.scope_for(unrelated, plan=other)
        self.principals.pop(str(self.reader.pk))
        self.write_scope()
        absent_run = 'RUN-00000000-0000-4000-8000-000000000001'
        protected = (case['stable_id'], self.plan['plan_id'], self.plan['plan_version_id'], run, self.result.public_id)
        for denied in (unrelated, self.reader, self.outsider):
            self.as_actor(denied)
            for path in paths:
                with self.subTest(actor=denied.username, path=path):
                    response = self.client.get(path)
                    self.assertIn(response.status_code, (403, 404))
                    self.assertIn('no-store', response['Cache-Control'])
                    for identity in protected:
                        self.assertNotIn(identity.encode(), response.content)
            known, absent = (self.client.get(f'{self.root}/{identity}') for identity in (run, absent_run))
            def safe_error(response):
                error = response.json()['error']
                error.pop('request_id', None)
                return response.status_code, error
            self.assertEqual(safe_error(known), safe_error(absent))
            if denied != self.outsider:
                plans = self.client.get('/api/v1/test-plans').json()
                self.assertEqual(plans['count'], int(denied == unrelated))
                results, more = search_versions(actor=denied, term=self.plan['plan_id'], collection='',
                                                include_history=True, page=1)
                self.assertEqual((results, more), ([], False))

        self.as_actor(self.editor)
        before = (RunAttempt.objects.count(), IdempotencyRecord.objects.count())
        self.principals.pop(str(self.editor.pk))
        self.write_scope()
        record = RunAttempt.objects.get(public_id=run)
        replay_payload = {field: getattr(record, field) for field in (
            'configuration_key', 'external_reference', 'code_commit', 'code_manifest_digest',
            'dependency_lock_digest', 'dataset_manifest_digest', 'parameter_digest', 'environment_digest',
        )}
        replay = self.client.post(self.root, replay_payload, format='json', HTTP_IDEMPOTENCY_KEY=f'{self.suffix}-register')
        self.assertEqual(replay.status_code, 404)
        self.assertEqual((RunAttempt.objects.count(), IdempotencyRecord.objects.count()), before)

    def new_plan(self, title):
        payload = complete_fixture()
        payload['hypothesis_version_id'] = self.plan['hypothesis_version_id']
        payload['fields']['title'] = title
        return payload

    def save_json(self, url, key, payload):
        return self.client.post(url, payload, format='json', HTTP_IDEMPOTENCY_KEY=key)

    def browser_post(self, url, key, payload, initial_url=None):
        from tests.django_test_plan_frontend_render_tests import TestPlanRenderingTests

        browser = APIClient(enforce_csrf_checks=True)
        browser.force_authenticate(self.editor)
        form = TestPlanRenderingTests().submitted(payload)
        form['idempotency_key'] = key
        form_page = browser.get(initial_url or url)
        self.assertEqual(form_page.status_code, 200)
        self.assertEqual(browser.post(url, form).status_code, 403)
        csrf = browser.cookies['csrftoken'].value
        return browser.post(url, form, HTTP_X_CSRFTOKEN=csrf)

    def test_plan_create_acknowledgement_and_custodian_only_discovery(self):
        self.as_actor(self.editor)
        collection = '/api/v1/test-plans'
        p1, u1 = (self.new_plan(name) for name in ('Invented P1', 'Invented U1'))
        before = TestPlan.objects.count()
        for key, payload in (('p1-create', p1), ('u1-create', u1), ('p1-create', p1)):
            reply = self.save_json(collection, key, payload)
            self.assertEqual((reply.status_code, reply.json()), (201, {'saved': True}))
            self.assertNotIn('Location', reply)
        self.assertEqual(TestPlan.objects.count(), before + 2)
        self.assertEqual(self.save_json(collection, 'p1-create', u1).status_code, 409)
        p1_row = TestPlanVersion.objects.get(fields__title='Invented P1')
        u1_row = TestPlanVersion.objects.get(fields__title='Invented U1')
        for row in (p1_row, u1_row):
            self.assertEqual(self.client.get(f'{collection}/{row.record.public_id}').status_code, 404)
        self.principals[str(self.editor.pk)]['plans'].append(p1_row.record.public_id)
        self.write_scope()
        listed = self.client.get(collection)
        self.assertContains(listed, p1_row.record.public_id)
        self.assertNotContains(listed, u1_row.record.public_id)
        self.assertEqual(self.client.get(f'{collection}/{p1_row.record.public_id}/versions/{p1_row.public_id}').status_code, 200)
        self.assertEqual(self.save_json(collection, f'invented-plan-{self.suffix}', self.new_plan(self.plan['fields']['title'])).json(), {'saved': True})

        response = self.browser_post('/test-plans/new', 'browser-create', self.new_plan('Invented browser draft'),
                                     '/test-plans/new?hypothesis_version_id=' + p1['hypothesis_version_id'])
        browser_row = TestPlanVersion.objects.get(fields__title='Invented browser draft')
        self.assertContains(response, 'Draft saved', status_code=201)
        self.assertNotIn('Location', response)
        for identity in (browser_row.record.public_id, browser_row.public_id, p1['hypothesis_version_id']):
            self.assertNotContains(response, identity, status_code=201)

    def test_plan_correction_and_check_receipts_are_scoped_and_minimal(self):
        self.as_actor(self.editor)
        plan_id = self.plan['plan_id']
        api = f'/api/v1/test-plans/{plan_id}'
        page = f'/test-plans/{plan_id}'
        original = TestPlanVersion.objects.get(public_id=self.plan['plan_version_id'])
        proposal = revision_payload(self.plan)
        proposal['fields']['title'] = 'Invented P2'
        proposal['correction_reason'] = 'Invented P2 correction'
        response = self.save_json(api + '/corrections', 'p2', proposal)
        self.assertEqual(response.status_code, 201)
        p2 = response.json()
        self.assertEqual(set(p2), {'plan_id', 'plan_version_id', 'version'})
        self.assertEqual(p2['version'], 2)
        self.assertEqual(self.save_json(api + '/corrections', 'p2', proposal).content, response.content)
        self.assertEqual(self.save_json(api + '/corrections', 'p2',
                                        {**proposal, 'correction_reason': 'Invented conflicting mutation'}).status_code, 409)
        self.assertEqual(self.save_json(api + '/corrections', 'fresh-stale', proposal).status_code, 409)
        current = self.client.get(api).json()
        next_proposal = revision_payload(current)
        next_proposal['fields']['title'] = 'Invented legacy saved draft'
        next_proposal['correction_reason'] = 'Invented legacy correction'
        legacy = correct_test_plan(actor=self.editor,plan_id=plan_id,idempotency_key='old-correction',payload=next_proposal)
        self.assertIn(b'Invented legacy saved draft', legacy.body)
        legacy_replay = self.save_json(api + '/corrections', 'old-correction', next_proposal)
        self.assertEqual(legacy_replay.status_code, 201)
        self.assertEqual(set(legacy_replay.json()), set(p2))
        self.assertNotIn(b'Invented legacy saved draft', legacy_replay.content)
        self.assertEqual(self.client.get(api + '/versions/' + original.public_id).json()['row_digest'], original.row_digest)

        check = {'plan_version_id': p2['plan_version_id'],
                 'data_requirement_version_id': current['data_requirements'][0]['data_requirement_version_id'],
                 'configuration_key': 'baseline', 'performed_at': '2026-10-03T12:00:00Z',
                 'performed_by': 'Invented checker', 'tool': 'Invented local reader', 'outcome': 'passed',
                 'check_scope': 'Invented shape only', 'observations': 'Invented private observation',
                 'evidence_references': [{'label': 'Invented source', 'uri': 'urn:mv-rms:invented-check', 'revision': None, 'sha256': None}],
                 'limitations': 'Invented evidence only', 'sanitized_evidence_confirmed': True,
                 'expected_current_check_id': None, 'supersedes_check_id': None, 'correction_reason': None}
        old_check = record_data_access_check(actor=self.editor,plan_id=plan_id,idempotency_key='old-check',payload=check)
        self.assertIn(b'Invented private observation', old_check.body)
        self.assertEqual(self.save_json(api + '/data-checks', 'old-check', check).json(), {'saved': True})
        report = {**check, 'configuration_key': 'longer'}
        check_page = page + '/data-checks/new'
        pins = {key: report[key] for key in ('plan_version_id', 'data_requirement_version_id', 'configuration_key')}
        result = self.browser_post(check_page, 'browser-check', report, check_page + '?' + urlencode(pins))
        self.assertEqual((result.status_code, result.get('Location')), (303, page + '/data-checks'))
        browser_proposal = revision_payload(self.client.get(api).json())
        browser_proposal['fields']['title'] = 'Invented browser revision'
        browser_proposal['correction_reason'] = 'Invented browser save'
        saved = self.browser_post(page + '/revise', 'browser-correction', browser_proposal)
        edited = TestPlanVersion.objects.get(fields__title='Invented browser revision')
        self.assertEqual(saved.status_code, 303)
        self.assertTrue(saved['Location'].startswith(f'{page}/versions/{edited.public_id}?receipt='))
        self.assertEqual(DataAccessCheck.objects.filter(plan_version__public_id=p2['plan_version_id']).count(), 2)

        counts = (TestPlanVersion.objects.count(), DataAccessCheck.objects.count(), IdempotencyRecord.objects.count())
        unrelated = principal(self.suffix + '-other-editor', 'editor')
        self.scope_for(unrelated)
        for actor in (unrelated, self.editor): self.principals[str(actor.pk)]['plans'] = []
        self.write_scope()
        missing = 'TPL-00000000-0000-4000-8000-000000000001'
        for actor, status in ((unrelated, 404), (self.editor, 404), (self.outsider, 403)):
            self.as_actor(actor)
            for suffix, old_key, payload in (('/corrections', 'old-correction', next_proposal),
                                             ('/data-checks', 'old-check', check)):
                responses = [self.save_json(target + suffix, key, payload)
                             for target in (api, '/api/v1/test-plans/' + missing)
                             for key in (old_key, 'new-denied-key')]
                errors = []
                for denied in responses:
                    self.assertEqual(denied.status_code, status)
                    self.assertNotIn(plan_id.encode(), denied.content)
                    self.assertNotIn(b'Invented private observation', denied.content)
                    self.assertNotIn(b'Invented legacy saved draft', denied.content)
                    errors.append({key: value for key, value in denied.json()['error'].items() if key != 'request_id'})
                self.assertTrue(all(error == errors[0] for error in errors))
        self.assertEqual((TestPlanVersion.objects.count(), DataAccessCheck.objects.count(), IdempotencyRecord.objects.count()), counts)

    def test_missing_and_malformed_scope_fail_closed(self):
        self.as_actor(self.reader)
        for contents in ('{}', '{"format":"duplicate","format":"rr14-disposable-synthetic-v1"}', 'null'):
            Path(settings.RMS_RR14_SCOPE_FILE).write_text(contents)
            self.assertEqual(self.client.get(self.projection()).status_code, 404)
        self.scope_file.unlink()
        self.assertEqual(self.client.get(self.projection()).status_code, 404)
