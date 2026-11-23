"""Synthetic custody. No uploads, external transfer, or live authority."""

import base64

from django.db import transaction
from django.utils import timezone

from .custody_models import CustodyEvent
from .hypothesis_validation import HypothesisValidationError
from .research_context_common import StaleVersion, execute_write, field_error, lock_lineage, wire
from .run_result_services import ResultIntegrityError, _run, _verify_result
from .run_result_validation import MAX_ARTIFACT_BYTES
from .services import ResourceNotFound, ServiceError, canonical_json_bytes
from .stage_gate_services import _access, _current_record, _mapping
from .test_plan_services import digest


PURPOSE = 'synthetic_custody_only'
DESTINATION = 'fixture:local-download'
SCHEMA = 'fixture:MAU-170:v1'
OPERATIONS = ('stage', 'verify', 'seal', 'export')
STATES = dict(zip(OPERATIONS, ('staged', 'verified', 'sealed', 'sealed'), strict=True)) | {'reconcile': 'quarantined'}


class CustodyDenied(ServiceError):
    code = 'custody_denied'
    safe_message = 'The exact synthetic custody claim is unavailable for this operation.'
    http_status = 409


def custody_access(actor, plan_id, *, write=False):
    custody = _mapping(_access(actor=actor, plan_id=plan_id, write=write).get('custody'))
    if custody.get('enabled') is not True:
        raise ResourceNotFound
    return custody


def _result(plan_id, version_id, run_id, result_version_id, *, lock=False):
    run = _run(plan_id, version_id, run_id, lock=lock)
    result = run.result_versions.filter(public_id=result_version_id).select_related('completed_event', 'supersedes').first()
    if result is None:
        raise ResourceNotFound
    result.run = run
    return result


def _head(result):
    return result.custody_events.order_by('-sequence').first()


def snapshot(result):
    """Exact single-object database and byte watermark."""
    if not result.artifact_bytes or len(result.artifact_bytes) > MAX_ARTIFACT_BYTES:
        raise CustodyDenied
    try:
        _verify_result(result)
    except ResultIntegrityError as error:
        raise CustodyDenied from error
    run, manifest = result.run, result.artifact_manifest
    prior = result.supersedes
    if prior and (prior.run_id != result.run_id or prior.version + 1 != result.version):
        raise CustodyDenied
    return {
        'plan_version_id': run.plan_version.public_id, 'plan_digest': run.plan_version.row_digest,
        'run_id': run.public_id, 'run_digest': run.row_digest, 'configuration_digest': run.parameter_digest,
        'result_version_id': result.public_id, 'result_digest': result.row_digest,
        'result_predecessor': {'id': prior.public_id, 'digest': prior.row_digest} if prior else None,
        'completed_event_id': result.completed_event.public_id, 'completed_event_digest': result.completed_event.row_digest,
        'artifact': {'role': 'original', 'required': True, 'sha256': manifest['sha256'],
                     'byte_length': manifest['byte_length'], 'manifest_digest': manifest['manifest_digest']},
    }


def _live_snapshot(result):
    if (result.run.plan_version.version != result.run.plan_version.record.latest_version or
            result.run.result_versions.filter(version__gt=result.version).exists()):
        raise CustodyDenied
    return snapshot(result)


def _bindings(fixture, *, operation, scope, actor_id, now):
    records = _mapping(_mapping(fixture.get('bindings')).get(operation))
    authority = _current_record(_mapping(records.get('authority')), operation=operation, scope=scope, now=now,
                                status='approved', extra={}, error='authority')
    rights = _current_record(_mapping(records.get('rights')), operation=operation, scope=scope, now=now,
                             status='allowed', extra={'principal': actor_id, 'purpose': PURPOSE,
                                                     'destination': DESTINATION}, error='rights')
    return {'authority': authority, 'rights': rights}


def _link(event):
    return {'id': event.public_id, 'digest': event.manifest_digest} if event else None


def _manifest(event, scope, bindings):
    return {'schema': SCHEMA, 'id': event.public_id, 'operation': event.operation, 'sequence': event.sequence,
            'state': STATES[event.operation], 'actor': event.actor_id, 'recorded_at': wire(event.recorded_at),
            'predecessor': _link(event.predecessor), 'impact_of': _link(event.impact_of),
            'scope': scope, 'bindings': bindings, 'custody': 'local_fixture_only', 'omissions': []}


def _check_chain(fixture, result, scope, now):
    prior = None
    for sequence, event in enumerate(result.custody_events.select_related('predecessor', 'impact_of').order_by('sequence'), 1):
        if (sequence > len(OPERATIONS) or event.operation != OPERATIONS[sequence - 1] or event.sequence != sequence or
                event.predecessor_id != (prior.pk if prior else None)):
            raise CustodyDenied
        bindings = _bindings(fixture, operation=event.operation, scope=scope, actor_id=event.actor_id, now=now)
        expected = _manifest(event, scope, bindings)
        if event.manifest != expected or event.manifest_digest != digest(expected):
            raise CustodyDenied
        prior = event


def _validate(_name, payload):
    if (not isinstance(payload, dict) or set(payload) != {'operation', 'expected_sequence'} or
            payload['operation'] not in (*OPERATIONS, 'reconcile') or type(payload['expected_sequence']) is not int or
            not 0 <= payload['expected_sequence'] <= len(OPERATIONS)):
        field_error('/operation', 'invalid_custody_command')
    return payload


def _summary(event):
    return {'id': event.public_id, 'operation': event.operation, 'sequence': event.sequence, 'state': STATES[event.operation]}


def read_custody(*, actor, plan_id, version_id, run_id, result_version_id):
    custody_access(actor, plan_id)
    result = _result(plan_id, version_id, run_id, result_version_id)
    return [_summary(event) for event in result.custody_events.order_by('sequence')]


def record_custody(*, actor, plan_id, version_id, run_id, result_version_id, idempotency_key, payload):
    custody_access(actor, plan_id, write=True)
    _result(plan_id, version_id, run_id, result_version_id)
    path = f'/test-plans/{plan_id}/versions/{version_id}/runs/{run_id}/results/{result_version_id}/custody'

    def operation(values):
        fixture = custody_access(actor, plan_id, write=True)
        result = _result(plan_id, version_id, run_id, result_version_id, lock=True)
        prior = _head(result)
        sequence = prior.sequence if prior else 0
        if sequence != values['expected_sequence']:
            raise StaleVersion
        action = values['operation']
        if prior and prior.operation == 'reconcile':
            raise CustodyDenied
        now = timezone.now()
        actor_id = str(actor.pk)
        if action == 'reconcile':
            if prior is None:
                raise CustodyDenied
            try:
                _check_chain(fixture, result, _live_snapshot(result), now)
            except (CustodyDenied, HypothesisValidationError):
                scope, bindings = {'incident': 'integrity_or_binding_mismatch'}, None
            else:
                raise CustodyDenied
        else:
            if sequence >= len(OPERATIONS) or action != OPERATIONS[sequence]:
                raise CustodyDenied
            scope = _live_snapshot(result)
            _check_chain(fixture, result, scope, now)
            bindings = _bindings(fixture, operation=action, scope=scope, actor_id=actor_id, now=now)
        impact = prior if action == 'reconcile' else (
            _head(result.supersedes) if action == 'stage' and result.supersedes_id else None
        )
        event = CustodyEvent(result=result, predecessor=prior, impact_of=impact, sequence=sequence + 1,
                             operation=action, actor_id=actor_id, recorded_at=now)
        event.manifest = _manifest(event, scope, bindings)
        event.manifest_digest = digest(event.manifest)
        event.save(force_insert=True)
        return 201, {'stable_id': result.public_id, **_summary(event)}

    return execute_write(actor=actor, idempotency_key=idempotency_key, payload=payload, request_name='Custody',
                         path=path, operation=operation, validate=_validate)


@transaction.atomic
def download_export(*, actor, plan_id, version_id, run_id, result_version_id):
    fixture = custody_access(actor, plan_id, write=True)
    lock_lineage()
    result = _result(plan_id, version_id, run_id, result_version_id, lock=True)
    event = _head(result)
    if event is None or event.operation != 'export' or event.actor_id != str(actor.pk):
        raise ResourceNotFound
    _check_chain(fixture, result, _live_snapshot(result), timezone.now())
    return canonical_json_bytes({'manifest': event.manifest, 'manifest_digest': event.manifest_digest,
                                 'content_base64': base64.b64encode(result.artifact_bytes).decode('ascii')})
