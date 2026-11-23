"""Internal helper for the disposable MAU-170 recovery rehearsal, not an RMS export API."""

import base64
import hashlib
import json
import os

from django.contrib.auth.models import Group, User
from django.db import DatabaseError, connection, transaction
from django.test import override_settings

from rms.custody_models import CustodyEvent
from rms.custody_services import download_export, read_custody, snapshot
from rms.hypothesis_validation import HypothesisValidationError
from rms.models import RunResultVersion
from rms.run_result_services import read_result
from rms.services import ResourceNotFound
from rms.test_plan_services import digest
from tests.django_custody_tests import CustodyWorkflow, grants


class Fixture(CustodyWorkflow):
    @staticmethod
    def assertEqual(actual, expected, message=None):
        if actual != expected:
            raise AssertionError(message or 'Fixture operation did not match its expected result')


TABLES = (
    'auth_group', 'auth_user', 'auth_user_groups', 'rms_testplan', 'rms_testplanversion',
    'rms_testplanassociation', 'rms_runattempt', 'rms_runlifecycleevent', 'rms_runretry', 'rms_runresultversion',
    'rms_runreview', 'rms_rundecision', 'rms_runlesson', 'rms_syntheticgateevent', 'rms_idempotencyrecord',
)


def checkpoint(custody):
    with transaction.atomic(), connection.cursor() as cursor:
        cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        tables = {}
        for table in (*TABLES, 'rms_custodyevent') if custody else TABLES:
            cursor.execute(f'SELECT to_jsonb(row)::text FROM {table} AS row ORDER BY to_jsonb(row)::text COLLATE "C"')
            rows = [row[0] for row in cursor]
            tables[table] = {'count': len(rows), 'sha256': digest(rows)}
        scope = [snapshot(result) for result in RunResultVersion.objects.order_by('public_id')]
        cursor.execute("SELECT name FROM django_migrations WHERE app='rms' ORDER BY name")
        applied = [row[0] for row in cursor]
        cursor.execute("SELECT tgname, tgenabled FROM pg_trigger WHERE tgrelid=to_regclass('rms_custodyevent') "
                       "AND NOT tgisinternal ORDER BY tgname")
        guards = dict(cursor.fetchall())
        if custody and guards != dict.fromkeys(('custody_event_guard', 'custody_event_immutable',
                                                'custody_event_no_truncate'), 'O'):
            raise AssertionError('Custody guards are missing or not enabled')
        body = {'tables': tables, 'objects': scope, 'migrations': applied, 'guards': guards}
        return body | {'watermark': digest(body)}


def probe(stage):
    if not connection.settings_dict['NAME'].startswith('rms_ma170_rehearsal_'):
        raise RuntimeError('Only a disposable MAU-170 rehearsal DB may run this probe')
    if stage == 'seed':
        fixture = Fixture()
        fixture.setup_custody('ma170-recovery')
        outsider = User.objects.create_user('invented-recovery-outsider')
        outsider.groups.add(Group.objects.get(name='editor'))
        return checkpoint(False)
    if stage == 'post-migration':
        return checkpoint(True)

    fixture = Fixture()
    fixture.editor = User.objects.get(username='invented-editor-ma170-recovery')
    fixture.result = RunResultVersion.objects.get()
    run = fixture.result.run
    plan_id = run.plan_version.record.public_id
    fixture.ids = {'plan_id': plan_id, 'version_id': run.plan_version.public_id, 'run_id': run.public_id,
                   'result_version_id': fixture.result.public_id}
    policy = grants(fixture.editor, plan_id, fixture.result)
    outsider = User.objects.get(username='invented-recovery-outsider')

    def read_original(*, actor, **ids):
        return read_result(actor=actor, artifact=True, **ids)

    def assert_denied(service, actor, expected):
        try:
            service(actor=actor, **fixture.ids)
        except expected:
            return
        raise AssertionError('A denied fixture read was permitted')

    with override_settings(RMS_SYNTHETIC_STAGE_GATES=policy):
        if stage == 'seal':
            fixture.advance(4)
        export = download_export(actor=fixture.editor, **fixture.ids)
        artifact = read_original(actor=fixture.editor, **fixture.ids)
        original = base64.b64decode(artifact['content_base64'], validate=True)
        fixture.assertEqual(artifact['content_base64'], json.loads(export)['content_base64'])
        fixture.assertEqual(original, bytes(fixture.result.artifact_bytes))
        fixture.assertEqual(artifact['manifest'], fixture.result.artifact_manifest)
        for service in (read_custody, download_export, read_original):
            assert_denied(service, outsider, ResourceNotFound)
    binding = policy[plan_id]['custody']['bindings']['export']
    for record_name, denial in (('rights', 'denied'), ('authority', 'revoked')):
        record = binding[record_name]
        status = record['status']
        record['status'] = denial
        with override_settings(RMS_SYNTHETIC_STAGE_GATES=policy):
            for service in (download_export, read_original):
                assert_denied(service, fixture.editor, HypothesisValidationError)
        record['status'] = status
    with override_settings(RMS_SYNTHETIC_STAGE_GATES={}):
        for service in (download_export, read_original):
            assert_denied(service, fixture.editor, ResourceNotFound)
    try:
        with transaction.atomic():
            CustodyEvent.objects.update(manifest={})
    except DatabaseError:
        pass
    else:
        raise AssertionError('Custody history could be rewritten')
    return checkpoint(True) | {
        'export_sha256': hashlib.sha256(export).hexdigest(),
        'original_sha256': hashlib.sha256(original).hexdigest(),
        'both_byte_paths_deny_unscoped_and_revoked': True,
    }


def main():
    print(json.dumps(probe(os.environ['RMS_CUSTODY_PROBE']), sort_keys=True))
