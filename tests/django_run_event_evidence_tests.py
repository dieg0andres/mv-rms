import base64
import hashlib

from django.contrib.auth.models import Group, User
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from rms.models import IdempotencyRecord, RunAttempt, RunLifecycleEvent, RunRetry
from tests.django_run_result_tests import Workflow


def artifact(data):
    return {'content_base64': base64.b64encode(data).decode('ascii'),
            'sha256': hashlib.sha256(data).hexdigest(), 'synthetic_confirmed': True}


class RunEventEvidenceTests(Workflow, TestCase):
    def setUp(self):
        self.setup_workflow('event-evidence')
        self.run_id = self.register()
        self.route = f'{self.root}/{self.run_id}'
        self.invented_file = artifact(b'invented partial observation')

    def send_event(self, state, expected=None, *, evidence=None, key='observed-event', reconciliation=False, status=201):
        payload = {'state': state, 'expected_event_id': expected, 'reason': 'Invented execution observation'}
        if evidence is not None:
            payload['partial_evidence'] = evidence
        suffix = 'reconciliations' if reconciliation else 'events'
        return self.post(f'{self.route}/{suffix}', key, payload, status).json()

    def test_unresolved_attempt_is_preserved_and_only_documented_reconciliation_releases_retry(self):
        running = self.send_event('running')['event_id']
        unknown = self.send_event('unknown', running, evidence=self.invented_file, key='unobserved')
        self.assertEqual(self.send_event('unknown', running, evidence=self.invented_file, key='unobserved'), unknown)
        self.assertEqual(self.client.get(self.route).json()['available_actions'], ['reconcile'])
        retry = {'expected_event_id': unknown['event_id'], 'external_reference': 'synthetic:after-reconcile',
                 'reason': 'Invented retry of a resolved failure'}
        counts = (RunAttempt.objects.count(), RunLifecycleEvent.objects.count(), IdempotencyRecord.objects.count())
        self.post(self.route + '/retry', 'too-early', retry, 409)
        self.send_event('failed', unknown['event_id'], key='skip-reconciliation', status=409)
        self.send_event('failed', unknown['event_id'], key='missing-evidence', reconciliation=True, status=400)
        self.send_event('completed', unknown['event_id'], key='bad-evidence', reconciliation=True,
                        evidence={**self.invented_file, 'sha256': '0' * 64}, status=400)
        self.assertEqual(counts, (RunAttempt.objects.count(), RunLifecycleEvent.objects.count(), IdempotencyRecord.objects.count()))
        resolved = self.send_event('failed', unknown['event_id'], evidence=artifact(b'invented recovery report'),
                                   key='reconciled', reconciliation=True)
        self.assertEqual(resolved['reconciles_event_id'], unknown['event_id'])
        retry['expected_event_id'] = resolved['event_id']
        self.post(self.route + '/retry', 'changed-config', {**retry, 'configuration_key': 'other'}, 400)
        successor = self.post(self.route + '/retry', 'same-envelope', retry).json()
        self.assertEqual(successor['retry_of_run_id'], self.run_id)
        self.assertEqual(RunRetry.objects.count(), 1)
        history = self.client.get(self.route).json()['events']
        self.assertEqual([e['state'] for e in history], ['running', 'unknown', 'failed'])
        self.assertEqual([history[1], history[2]], [unknown, resolved])

    def test_exact_failed_evidence_is_readable_in_scope_and_roles_are_checked_before_lookup(self):
        terminal = self.send_event('failed', evidence=self.invented_file)
        path = f"{self.route}/events/{terminal['event_id']}/evidence"
        report = self.client.get(path).json()
        self.assertEqual(report['content_base64'], self.invented_file['content_base64'])
        self.assertEqual(report['manifest']['sha256'], self.invented_file['sha256'])
        self.assertEqual(report['manifest']['event_digest'], terminal['row_digest'])
        ids = (self.plan['plan_id'], self.plan['plan_version_id'], self.run_id)
        response = self.client.get(reverse('rms-run-detail', args=ids))
        self.assertContains(response, path)
        self.assertNotContains(response, self.invented_file['content_base64'])
        viewer = User.objects.create_user('event-evidence-viewer')
        viewer.groups.add(Group.objects.get_or_create(name='founder_viewer')[0])
        self.client.force_authenticate(viewer)
        self.assertEqual(self.client.get(path).json(), report)
        self.send_event('unknown', key='viewer-write', status=403)
        self.assertEqual(self.client.get(path.replace(self.run_id, 'RUN-invented-missing')).status_code, 404)
        self.client.force_authenticate(User.objects.create_user('event-evidence-outsider'))
        for target in (path, path.replace(self.run_id, 'RUN-invented-missing')):
            self.assertEqual(self.client.get(target).status_code, 403)
        self.assertEqual(APIClient().get(path).status_code, 401)

    def test_database_guards_block_invalid_bytes_and_resolving_an_unknown_without_evidence(self):
        observed = self.send_event('unknown')
        event = RunLifecycleEvent.objects.get(public_id=observed['event_id'])
        self.assertNotIn('partial_evidence', observed)
        self.assertEqual(self.client.get(f"{self.route}/events/{observed['event_id']}/evidence").status_code, 404)
        for evidence, checksum in ((None, None), (b'invented incomplete bytes', '0' * 64)):
            with self.subTest(checksum=checksum), self.assertRaises(IntegrityError), transaction.atomic():
                RunLifecycleEvent.objects.create(run=event.run, previous_event=event, sequence=2,
                                                 state='failed', reason='Invented resolution',
                                                 recorded_by='fixture', actor_id='fixture', row_digest='1' * 64,
                                                 partial_evidence_bytes=evidence, partial_evidence_sha256=checksum)
        self.assertEqual(RunLifecycleEvent.objects.count(), 1)
