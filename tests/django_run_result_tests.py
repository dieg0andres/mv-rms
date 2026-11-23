"""Invented-only workflow checks on Django's disposable PostgreSQL test DB."""

import base64
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
from io import StringIO
import json
from threading import Barrier

from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.db import DatabaseError, connections, transaction
from django.test import TestCase
from rest_framework.test import APIClient

from rms.models import IdempotencyRecord, RunAttempt, RunLifecycleEvent, RunResultVersion, RunRetry
from rms.management.commands.load_rms_hn_fixture import Command as HypothesisFixture
from rms.research_context_common import StaleVersion
from rms.run_result_services import RunConflict, publish_result, retry_run
from rms.test_plan_services import correct_test_plan, create_test_plan
from tests.committed_database import CommittedDatabaseTestCase
from tests.synthetic_read_scope import SyntheticPlanReaders
from tests.test_test_plan_backend_validation import complete_fixture


def fixture(suffix):
    editor = User.objects.create_user(f'invented-editor-{suffix}')
    editor.groups.add(Group.objects.get_or_create(name='editor')[0])
    stream = StringIO()
    call_command(HypothesisFixture(), actor=editor.username, review_time='2026-10-03T12:00:00Z', stdout=stream)
    payload = complete_fixture()
    payload['hypothesis_version_id'] = json.loads(stream.getvalue())['hypothesis_versions'][0]['version_id']
    plan = json.loads(create_test_plan(actor=editor, idempotency_key=f'invented-plan-{suffix}', payload=payload).body)
    return editor, plan


class Workflow:
    def setup_workflow(self, suffix, *, seed_read_scope=True):
        self.editor, self.plan = fixture(suffix)
        if seed_read_scope:
            self.readers = SyntheticPlanReaders(self, self.plan)
            self.scope_for(self.editor)
        self.client = APIClient()
        self.client.force_authenticate(self.editor)
        self.root = f"/api/v1/test-plans/{self.plan['plan_id']}/versions/{self.plan['plan_version_id']}/runs"
        self.suffix = suffix

    def scope_for(self, actor):
        self.readers.allow(actor)

    def post(self, url, key, payload, status=201):
        response = self.client.post(url, payload, format='json', HTTP_IDEMPOTENCY_KEY=key)
        self.assertEqual(response.status_code, status, response.content)
        self.assertEqual(response.headers['Cache-Control'], 'private, no-store')
        return response

    def register(self):
        config = self.plan['configurations'][1]
        payload = {'configuration_key': config['key'], 'external_reference': f'synthetic:{self.suffix}',
                   'code_commit': 'a' * 40, 'parameter_digest': config['digest']}
        payload.update({name: 'b' * 64 for name in ('code_manifest_digest', 'dependency_lock_digest',
                                                    'dataset_manifest_digest', 'environment_digest')})
        return self.post(self.root, f'{self.suffix}-register', payload).json()['run_id']

    def event(self, run, state, predecessor, status=201, *, label='event'):
        return self.post(f'{self.root}/{run}/events', f'{label}:{run}:{state}',
                         {'state': state, 'expected_event_id': predecessor, 'reason': 'Invented observed event'}, status).json()

    def complete(self, run):
        running = self.event(run, 'running', None)
        return self.event(run, 'completed', running['event_id'])['event_id']

    def result_payload(self, run, event, *, value='-1', artifact=b'invented paper fixture'):
        criteria = self.client.get(f'{self.root}/{run}').json()['criteria']
        return {'completed_event_id': event, 'expected_result_version_id': None, 'correction_reason': None,
                'summary': 'Invented result', 'assessments': [
                    {**{key: criterion[key] for key in ('criterion_edge_id', 'criterion_version_id')},
                     'observed_value': value, 'reported_outcome': None, 'sample_satisfied': True,
                     'explanation': 'Invented observation has the required fictional sample.'} for criterion in criteria],
                'artifact': {'content_base64': base64.b64encode(artifact).decode(),
                             'sha256': hashlib.sha256(artifact).hexdigest(), 'synthetic_confirmed': True}}


class RunResultTests(Workflow, TestCase):
    def setUp(self):
        self.setup_workflow('run-result-fixture')

    def test_event_capabilities_are_writer_only_and_follow_transitions(self):
        run = self.register()
        url = f'{self.root}/{run}'
        registered = self.client.get(url).json()
        self.assertEqual(registered['available_actions'], ['event'])
        self.assertEqual(registered['allowed_event_states'], ['running', 'failed', 'cancelled', 'unknown'])

        viewer = User.objects.create_user('invented-capability-viewer')
        viewer.groups.add(Group.objects.create(name='founder_viewer'))
        self.scope_for(viewer)
        self.client.force_authenticate(viewer)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {key: value for key, value in registered.items()
                                          if key not in ('available_actions', 'allowed_event_states')})
        self.event(run, 'running', None, 403)

        self.client.force_authenticate(self.editor)
        self.event(run, 'completed', None, 409)
        running = self.event(run, 'running', None)
        current = self.client.get(url).json()
        self.assertEqual(current['available_actions'], ['event'])
        self.assertEqual(current['allowed_event_states'], ['completed', 'failed', 'cancelled', 'unknown'])
        self.event(run, 'running', running['event_id'], 409, label='invalid-transition')
        self.event(run, 'completed', running['event_id'], label='terminal-transition')

    def test_failed_attempt_retry_then_mandatory_fail_and_immutable_correction(self):
        failed_run = self.register()
        self.event(failed_run, 'completed', None, 409)
        failed = self.event(failed_run, 'failed', None)
        failed_event = failed['event_id']
        retryable = self.client.get(f'{self.root}/{failed_run}').json()
        self.assertEqual(retryable['available_actions'], ['retry'])
        self.assertNotIn('allowed_event_states', retryable)
        self.post(f'{self.root}/{failed_run}/results', 'failed-result', self.result_payload(failed_run, failed_event), 409)
        retry = {'expected_event_id': failed_event, 'external_reference': 'synthetic:invented-retry', 'reason': 'Invented retry'}
        url = f'{self.root}/{failed_run}/retry'
        first = self.post(url, 'retry', retry)
        self.assertEqual(first.content, self.post(url, 'retry', retry).content)
        self.post(url, 'retry', {**retry, 'reason': 'Conflicting invented reason'}, 409)
        self.post(url, 'duplicate-retry', {**retry, 'external_reference': 'synthetic:another'}, 409)
        run = first.json()['run_id']
        self.assertEqual(first.json()['retry_of_run_id'], failed_run)
        retried = self.client.get(f'{self.root}/{failed_run}').json()
        self.assertEqual(retried['state'], 'failed')
        self.assertEqual(retried['retry_run_id'], run)
        self.assertEqual(retried['available_actions'], [])
        self.assertNotIn('allowed_event_states', retried)
        ended = self.complete(run)
        completed = self.client.get(f'{self.root}/{run}').json()
        self.assertEqual(completed['available_actions'], ['result'])
        self.assertNotIn('allowed_event_states', completed)
        payload = self.result_payload(run, ended)
        response = self.post(f'{self.root}/{run}/results', 'initial', payload)
        original = response.json()
        self.assertEqual(response.content, self.post(f'{self.root}/{run}/results', 'initial', payload).content)
        self.assertEqual(original['assessment_outcome'], 'mandatory_fail')
        self.assertEqual(self.client.get(f'{self.root}/{run}').json(), completed)
        corrected = self.result_payload(run, ended, value='2', artifact=b'invented revised bytes')
        corrected.update(expected_result_version_id=original['result_version_id'], correction_reason='Invented transcription correction')
        successor = self.post(f'{self.root}/{run}/results', 'correction', corrected).json()
        self.assertEqual(successor['assessment_outcome'], 'criteria_pass')
        self.assertEqual(successor['supersedes_result_version_id'], original['result_version_id'])
        self.post(f'{self.root}/{run}/results', 'stale', corrected, 409)
        original_url = f"{self.root}/{run}/results/{original['result_version_id']}"
        self.assertEqual(self.client.get(original_url).json(), original)
        self.assertEqual(self.client.get(original_url + '/artifact').json()['content_base64'], payload['artifact']['content_base64'])
        self.assertEqual(RunAttempt.objects.count(), 2)
        self.assertEqual(RunRetry.objects.count(), 1)
        self.assertEqual(RunResultVersion.objects.count(), 2)
        for model, fields in ((RunAttempt, {'reported_by': 'another'}), (RunLifecycleEvent, {'reason': 'another'}),
                              (RunRetry, {'reason': 'another'}), (RunResultVersion, {'summary': 'another'})):
            with self.assertRaises(DatabaseError), transaction.atomic():
                model.objects.update(**fields)
        forged = RunResultVersion.objects.get(public_id=original['result_version_id'])
        forged.id = None
        forged.public_id = 'RESV-11111111-1111-4111-8111-111111111111'
        forged.run = RunAttempt.objects.get(public_id=failed_run)
        with self.assertRaises(DatabaseError), transaction.atomic():
            forged.save(force_insert=True)

    def test_exact_plan_criteria_permissions_and_no_partial_write(self):
        run = self.register()
        completed = self.complete(run)
        proposal = {name: deepcopy(self.plan[name]) for name in ('hypothesis_version_id', 'fields', 'criteria', 'data_requirements')}
        proposal.update(expected_latest_version=1, correction_reason='Invented successor threshold')
        proposal['criteria'][0]['fields']['threshold'] = '3'
        latest = json.loads(correct_test_plan(actor=self.editor, plan_id=self.plan['plan_id'], idempotency_key='plan-v2', payload=proposal).body)
        wrong_root = self.root.replace(self.plan['plan_version_id'], latest['plan_version_id'])
        url = f'{self.root}/{run}/results'
        payload = self.result_payload(run, completed, value='2')
        before = IdempotencyRecord.objects.count()
        wrong = deepcopy(payload)
        wrong['assessments'][0]['criterion_version_id'] = latest['criteria'][0]['criterion_version_id']
        self.post(url, 'not-consumed', wrong, 400)
        self.post(url, 'not-consumed', {**payload, 'assessments': []}, 400)
        self.post(url, 'not-consumed', {**payload, 'artifact': {**payload['artifact'], 'sha256': '0' * 64}}, 400)
        self.post(url, 'not-consumed', self.result_payload(run, completed, artifact=b'x' * 8193), 400)
        self.post(f'{wrong_root}/{run}/results', 'not-consumed', payload, 404)
        viewer = User.objects.create_user('invented-viewer')
        viewer.groups.add(Group.objects.create(name='founder_viewer'))
        self.scope_for(viewer)
        self.client.force_authenticate(viewer)
        self.assertEqual(self.client.get(f'{self.root}/{run}').status_code, 200)
        self.post(url, 'not-consumed', payload, 403)
        self.client.force_authenticate(User.objects.create_user('invented-outsider'))
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(RunResultVersion.objects.count(), 0)
        self.assertEqual(IdempotencyRecord.objects.count(), before)
        self.client.force_authenticate(self.editor)
        result = self.post(url, 'not-consumed', payload).json()
        self.assertEqual(result['assessment_outcome'], 'criteria_pass')
        self.assertEqual(result['assessments'][0]['rule']['threshold'], '0')

    def test_inadequate_sample_does_not_pass(self):
        run = self.register()
        ended = self.complete(run)
        payload = self.result_payload(run, ended, value='2')
        payload['assessments'][0]['sample_satisfied'] = False
        result = self.post(f'{self.root}/{run}/results', 'inadequate-sample', payload).json()
        self.assertEqual(result['assessment_outcome'], 'inconclusive')
        self.assertEqual(result['assessments'][0]['evaluation'], 'inconclusive')


class RunResultConcurrencyTests(Workflow, CommittedDatabaseTestCase):
    """Use committed threads. The append-only test rows are dropped with the test database."""

    def test_distinct_sessions_race_for_retry_and_result_revision(self):
        self.setup_workflow('run-result-race')
        run = self.register()
        terminal = self.event(run, 'cancelled', None)['event_id']

        def race(operation, context, payloads, conflict, prefix):
            barrier = Barrier(2)

            def worker(index):
                try:
                    actor = User.objects.get(pk=self.editor.pk)
                    barrier.wait(timeout=10)
                    return json.loads(operation(actor=actor, **context, payload=payloads[index],
                                                idempotency_key=f'{prefix}-{index}').body)
                except conflict:
                    return None
                finally:
                    connections.close_all()

            with ThreadPoolExecutor(max_workers=2) as pool:
                attempts = list(pool.map(worker, range(2)))
            self.assertEqual(attempts.count(None), 1)
            return next(item for item in attempts if item)

        context = {'plan_id': self.plan['plan_id'], 'version_id': self.plan['plan_version_id'], 'run_id': run}
        successor = race(retry_run, context, [
            {'external_reference': f'synthetic:concurrent-{index}', 'reason': 'Invented retry race', 'expected_event_id': terminal}
            for index in range(2)], RunConflict, 'retry-race')
        context['run_id'] = successor['run_id']
        completed = self.complete(context['run_id'])
        first = self.result_payload(context['run_id'], completed)
        original = self.post(f"{self.root}/{context['run_id']}/results", 'race-initial', first).json()
        proposals = [{**first, 'summary': f'Invented correction {index}', 'correction_reason': 'Invented race',
                      'expected_result_version_id': original['result_version_id']} for index in range(2)]
        corrected = race(publish_result, context, proposals, StaleVersion, 'correction-race')
        self.assertEqual(corrected['version'], 2)
        self.assertEqual(corrected['supersedes_result_version_id'], original['result_version_id'])
