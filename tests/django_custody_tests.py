"""Fixture-only custody tests through browser, service and PostgreSQL history guards."""

import base64
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from threading import Barrier

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import DatabaseError, connections, transaction
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from rms.custody_models import CustodyEvent
from rms.custody_services import (
    DESTINATION, OPERATIONS, PURPOSE, CustodyDenied, download_export, read_custody, record_custody, snapshot,
)
from rms.hypothesis_validation import HypothesisValidationError
from rms.models import IdempotencyRecord, RunResultVersion
from rms.research_context_common import Forbidden, StaleVersion
from rms.run_result_services import read_result
from rms.services import IdempotencyConflict, ResourceNotFound
from rms.stage_gate_services import POLICY
from rms.test_plan_services import correct_test_plan, digest
from tests.committed_database import CommittedDatabaseTestCase
from tests.django_run_result_tests import Workflow


def grants(actor, plan_id, result, *, readers=(), operators=()):
    scope = snapshot(result)
    bindings = {}
    for operation in OPERATIONS:
        common = {'operation': operation, 'scope': scope, 'policy': POLICY,
                  'effective_at': '2000-01-01T00:00:00Z', 'expires_at': '2099-01-01T00:00:00Z', 'revision': 1}
        bindings[operation] = {
            'authority': dict(common, reference=f'fixture:custody-{operation}-authority', status='approved'),
            'rights': dict(common, reference=f'fixture:custody-{operation}-rights', status='allowed',
                           principal=str(actor.pk), purpose=PURPOSE, destination=DESTINATION),
        }
    return {plan_id: {'operators': [str(actor.pk), *operators], 'readers': list(readers),
                      'custody': {'enabled': True, 'bindings': bindings}}}


class CustodyWorkflow(Workflow):
    def setup_custody(self, suffix):
        self.setup_workflow(suffix)
        self.run_id = self.register()
        self.completed = self.complete(self.run_id)
        self.result_payload_fixture = self.result_payload(self.run_id, self.completed)
        self.result = self.publish(self.result_payload_fixture)
        self.ids = dict(plan_id=self.plan['plan_id'], version_id=self.plan['plan_version_id'], run_id=self.run_id,
                        result_version_id=self.result.public_id)
        self.url = self.root.removeprefix('/api/v1') + f'/{self.run_id}/results/{self.result.public_id}/custody'
        self.settings_fixture = grants(self.editor, self.ids['plan_id'], self.result)

    def publish(self, payload, key='invented-custody-original'):
        row = self.post(f'{self.root}/{self.run_id}/results', key, payload).json()
        return RunResultVersion.objects.get(public_id=row['result_version_id'])

    def command(self, action, sequence, *, key=None, ids=None):
        return record_custody(actor=self.editor, idempotency_key=key or action,
                              payload={'operation': action, 'expected_sequence': sequence}, **(ids or self.ids))

    def advance(self, through):
        for sequence, action in enumerate(OPERATIONS[:through]):
            self.command(action, sequence)


class CustodyTests(CustodyWorkflow, TestCase):
    def setUp(self):
        self.setup_custody('custody')
        self.result_url = '/api/v1' + self.url.removesuffix('/custody')

    def assert_byte_reads_denied(self, actor, error, status):
        browser = APIClient()
        browser.force_authenticate(user=actor)
        for service, url in (
            (download_export, self.url + '/export'),
            (self.read_original, self.result_url + '/artifact'),
        ):
            with self.subTest(path=url), self.assertRaises(error):
                service(actor=actor, **self.ids)
            response = browser.get(url)
            self.assertEqual(response.status_code, status)
            self.assertEqual(response.headers['Cache-Control'], 'private, no-store')
            self.assertNotIn(b'content_base64', response.content)
            self.assertNotIn(self.result_payload_fixture['artifact']['content_base64'].encode(), response.content)

    @staticmethod
    def read_original(**context):
        return read_result(artifact=True, **context)

    def test_both_byte_paths_require_the_same_current_export(self):
        outsider = get_user_model().objects.create_user('invented-byte-outsider')
        outsider.groups.add(Group.objects.get(name='editor'))
        with override_settings(RMS_SYNTHETIC_STAGE_GATES=self.settings_fixture):
            self.assert_byte_reads_denied(self.editor, ResourceNotFound, 404)
            self.advance(3)
            self.assert_byte_reads_denied(self.editor, ResourceNotFound, 404)
            self.advance(4)
            self.assert_byte_reads_denied(outsider, ResourceNotFound, 404)
            response = self.client.get(self.result_url + '/artifact')
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers['Cache-Control'], 'private, no-store')
            package = self.client.get(self.url + '/export').json()
            self.assertEqual(response.json(), {
                'manifest': self.result.artifact_manifest, 'content_base64': package['content_base64'],
            })
            self.assertEqual(base64.b64decode(package['content_base64']), bytes(self.result.artifact_bytes))

        baseline = (CustodyEvent.objects.count(), IdempotencyRecord.objects.count())
        for changes in (None, {'expires_at': '2001-01-01T00:00:00Z'}, {'status': 'denied'}):
            with self.subTest(rights=changes):
                drift = deepcopy(self.settings_fixture)
                binding = drift[self.ids['plan_id']]['custody']['bindings']['export']
                if changes is None:
                    del binding['rights']
                else:
                    binding['rights'].update(changes)
                with override_settings(RMS_SYNTHETIC_STAGE_GATES=drift):
                    self.assert_byte_reads_denied(self.editor, HypothesisValidationError, 404)
        with override_settings(RMS_SYNTHETIC_STAGE_GATES={}):
            self.assert_byte_reads_denied(self.editor, ResourceNotFound, 404)
            metadata = self.client.get(self.result_url).json()
            self.assertEqual(metadata['artifact'], self.result.artifact_manifest)
            self.assertNotIn('content_base64', metadata)
        self.assertEqual((CustodyEvent.objects.count(), IdempotencyRecord.objects.count()), baseline)
        self.result.refresh_from_db()
        self.assertEqual(bytes(self.result.artifact_bytes), base64.b64decode(package['content_base64']))

    def test_plan_correction_closes_both_byte_paths_without_hiding_result_metadata(self):
        with override_settings(RMS_SYNTHETIC_STAGE_GATES=self.settings_fixture):
            self.advance(4)
            proposal = {name: deepcopy(self.plan[name]) for name in (
                'hypothesis_version_id', 'fields', 'criteria', 'data_requirements',
            )}
            proposal.update(expected_latest_version=1, correction_reason='Invented plan correction')
            proposal['criteria'][0]['fields']['threshold'] = '3'
            correct_test_plan(actor=self.editor, plan_id=self.ids['plan_id'], idempotency_key='custody-plan-v2',
                              payload=proposal)
            self.assert_byte_reads_denied(self.editor, CustodyDenied, 409)
            self.assertEqual(self.client.get(self.result_url).json()['artifact'], self.result.artifact_manifest)

    def test_authenticated_entry_csrf_scope_and_repeatable_exact_export(self):
        users = get_user_model().objects
        outsider = users.create_user('invented-other-editor')
        outsider.groups.add(Group.objects.get(name='editor'))
        reader = users.create_user('invented-custody-viewer')
        reader.groups.add(Group.objects.create(name='founder_viewer'))
        self.settings_fixture[self.ids['plan_id']]['readers'] = [str(reader.pk)]
        browser = APIClient(enforce_csrf_checks=True)
        self.assertEqual(browser.get(self.url).status_code, 401)
        browser.force_authenticate(user=self.editor)
        self.assertNotContains(browser.get(self.url.removesuffix('/custody')), self.url)
        with override_settings(RMS_SYNTHETIC_STAGE_GATES=self.settings_fixture):
            self.assertContains(browser.get(self.url.removesuffix('/custody')), self.url)
            page = browser.get(self.url)
            self.assertContains(page, 'Synthetic result custody')
            self.assertEqual(page.headers['Cache-Control'], 'private, no-store')
            payload = {'operation': 'stage', 'expected_sequence': 0, 'key': 'browser-fixture'}
            self.assertEqual(browser.post(self.url, payload).status_code, 403)
            token = browser.cookies['csrftoken'].value
            self.assertEqual(browser.post(self.url, payload, HTTP_X_CSRFTOKEN=token).status_code, 302)
            for sequence, action in enumerate(OPERATIONS[1:], start=1):
                self.command(action, sequence)
            first, second = (browser.get(self.url + '/export') for _ in range(2))
            self.assertEqual(first.status_code, 200)
            self.assertEqual(first.content, second.content)
            self.assertEqual(first.headers['Cache-Control'], 'private, no-store')
            package = first.json()
            self.assertEqual(base64.b64decode(package['content_base64']), bytes(self.result.artifact_bytes))
            self.assertEqual(digest(package['manifest']), package['manifest_digest'])
            self.assertEqual(package['manifest']['scope'], snapshot(self.result))
            self.assertEqual(package['manifest']['bindings']['rights']['destination'], DESTINATION)
            with self.assertRaises(ResourceNotFound):
                read_custody(actor=outsider, **self.ids)
            with self.assertRaises(Forbidden):
                download_export(actor=reader, **self.ids)
            browser.force_authenticate(user=outsider)
            self.assertEqual(browser.get(self.url).content,
                             browser.get(self.url.replace(self.result.public_id, 'invented-missing')).content)
            self.assertEqual(browser.get(self.url + '/export').status_code, 404)
            browser.force_authenticate(user=reader)
            self.assertNotContains(browser.get(self.url), 'fixture:custody-export-rights')
            self.assertNotContains(browser.get(self.url), 'Download the permitted')

    def test_wrong_rights_authority_and_stale_writes_leave_no_partial_receipts(self):
        with override_settings(RMS_SYNTHETIC_STAGE_GATES=self.settings_fixture):
            original = self.command('stage', 0)
            self.assertEqual(self.command('stage', 0).body, original.body)
            with self.assertRaises(IdempotencyConflict):
                self.command('verify', 1, key='stage')
            with self.assertRaises(StaleVersion):
                self.command('verify', 0)
            self.command('verify', 1)
        before = (CustodyEvent.objects.count(), IdempotencyRecord.objects.count())
        for record, index, value in [('rights', 'destination', 'fixture:unapproved'), ('rights', 'principal', 'unknown'),
                                     ('rights', 'expires_at', '2001-01-01T00:00:00Z'), ('authority', 'status', 'revoked'),
                                     ('authority', 'scope', {'result_digest': 'incorrect'})]:
            with self.subTest(record=record, field=index):
                drift = deepcopy(self.settings_fixture)
                drift[self.ids['plan_id']]['custody']['bindings']['seal'][record][index] = value
                with override_settings(RMS_SYNTHETIC_STAGE_GATES=drift), self.assertRaises(HypothesisValidationError):
                    self.command('seal', 2)
                self.assertEqual((CustodyEvent.objects.count(), IdempotencyRecord.objects.count()), before)
        with override_settings(RMS_SYNTHETIC_STAGE_GATES=self.settings_fixture):
            self.command('seal', 2)
            self.command('export', 3)
        revoked = deepcopy(self.settings_fixture)
        revoked[self.ids['plan_id']]['custody']['bindings']['export']['rights']['status'] = 'denied'
        with override_settings(RMS_SYNTHETIC_STAGE_GATES=revoked), self.assertRaises(HypothesisValidationError):
            download_export(actor=self.editor, **self.ids)

    def test_corrupt_or_missing_bytes_quarantine_without_replacement(self):
        with override_settings(RMS_SYNTHETIC_STAGE_GATES=self.settings_fixture):
            self.advance(2)
            baseline = IdempotencyRecord.objects.count()
            original = bytes(self.result.artifact_bytes)
            for artifact in (b'', b'corrupt invented bytes'):
                with transaction.atomic():
                    with connections['default'].cursor() as cursor:
                        cursor.execute('SET CONSTRAINTS ALL IMMEDIATE')
                        cursor.execute('ALTER TABLE rms_runresultversion DISABLE TRIGGER USER')
                    RunResultVersion.objects.filter(pk=self.result.pk).update(artifact_bytes=artifact)
                    with self.assertRaises(CustodyDenied):
                        self.command('seal', 2)
                    self.assertEqual(IdempotencyRecord.objects.count(), baseline)
                    self.assertEqual(CustodyEvent.objects.count(), 2)
                    incident = json.loads(self.command('reconcile', 2).body)
                    self.assertEqual(incident['state'], 'quarantined')
                    self.assertEqual(CustodyEvent.objects.get(public_id=incident['id']).impact_of.sequence, 2)
                    self.assertEqual(bytes(RunResultVersion.objects.get(pk=self.result.pk).artifact_bytes), artifact)
                    transaction.set_rollback(True)
            self.result.refresh_from_db()
            self.assertEqual(bytes(self.result.artifact_bytes), original)

    def test_correction_retains_predecessor_and_export_but_denies_stale_download(self):
        with override_settings(RMS_SYNTHETIC_STAGE_GATES=self.settings_fixture):
            self.advance(4)
            prior = CustodyEvent.objects.get(operation='export')
            corrected = self.publish(dict(self.result_payload_fixture, expected_result_version_id=self.result.public_id,
                                          correction_reason='Invented correction'), key='invented-correction')
            self.assert_byte_reads_denied(self.editor, CustodyDenied, 409)
        with override_settings(RMS_SYNTHETIC_STAGE_GATES=grants(self.editor, self.ids['plan_id'], corrected)):
            response = self.command('stage', 0, key='corrected-stage', ids=dict(self.ids, result_version_id=corrected.public_id))
        edge = CustodyEvent.objects.get(public_id=json.loads(response.body)['id'])
        self.assertEqual(edge.impact_of_id, prior.pk)
        self.assertEqual(edge.manifest['scope']['result_predecessor']['id'], self.result.public_id)
        with self.assertRaises(DatabaseError), transaction.atomic():
            CustodyEvent.objects.filter(pk=prior.pk).update(manifest={})
        self.assertEqual(CustodyEvent.objects.get(pk=prior.pk).manifest, prior.manifest)


class CustodyConcurrencyTests(CustodyWorkflow, CommittedDatabaseTestCase):
    def test_competing_custody_writers_commit_only_one_event_and_key(self):
        self.setup_custody('custody-race')
        barrier = Barrier(2, timeout=10)
        before = IdempotencyRecord.objects.count()

        def compete(index):
            try:
                barrier.wait()
                return self.command('stage', 0, key=f'invented-racer-{index}').status
            except StaleVersion:
                return 409
            finally:
                connections.close_all()

        with override_settings(RMS_SYNTHETIC_STAGE_GATES=self.settings_fixture), ThreadPoolExecutor(2) as pool:
            self.assertEqual(sorted(pool.map(compete, range(2))), [201, 409])
        self.assertEqual(CustodyEvent.objects.count(), 1)
        self.assertEqual(IdempotencyRecord.objects.count(), before + 1)
