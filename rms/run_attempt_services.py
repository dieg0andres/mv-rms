"""Register reported evidence against one exact synthetic Test Plan version."""
import re

from django.db import transaction

from .models import IdempotencyRecord
from .research_context_common import require_actor, wire
from .run_attempt_models import RunAttempt
from .services import (
    ServiceError, StoredResponse, _lock_idempotency_key, _replay_or_conflict,
    canonical_json_bytes,
)
from .test_plan_models import TestPlanVersion
from .test_plan_services import _error, _get, digest
from .test_plan_validation import validate_json_size


FIELD_FORMATS = {
    'configuration_key': r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}',
    'external_reference': r'synthetic:[A-Za-z0-9][A-Za-z0-9_.-]{0,95}',
    'code_commit': r'[a-f0-9]{40}',
    'code_manifest_digest': r'[a-f0-9]{64}',
    'dependency_lock_digest': r'[a-f0-9]{64}',
    'dataset_manifest_digest': r'[a-f0-9]{64}',
    'parameter_digest': r'[a-f0-9]{64}',
    'environment_digest': r'[a-f0-9]{64}',
}


class ExternalReferenceConflict(ServiceError):
    code = 'duplicate_synthetic_run_reference'
    safe_message = 'This synthetic external run reference is already registered.'
    http_status = 409


class RunListPageInvalid(ServiceError):
    code = 'invalid_run_page'
    safe_message = 'This run list page is invalid.'
    http_status = 400


def _version(plan_id, version_id):
    return _get(TestPlanVersion, version_id, record__public_id=plan_id, record__synthetic=True)


def _render(attempt, plan_version):
    return {
        'run_id': attempt.public_id,
        'plan_id': plan_version.record.public_id,
        'plan_version_id': plan_version.public_id,
        'classification': 'synthetic',
        'registration_status': 'registered',
        'reported_by': attempt.reported_by,
        'recorded_at': wire(attempt.recorded_at),
        'row_digest': attempt.row_digest,
        **{name: getattr(attempt, name) for name in FIELD_FORMATS},
    }


def list_attempts(*, actor, plan_id, version_id, offset='0'):
    require_actor(actor)
    if not isinstance(offset, str) or re.fullmatch(r'[0-9]{1,8}', offset) is None:
        raise RunListPageInvalid
    offset = int(offset)
    plan_version = _version(plan_id, version_id)
    page = list(plan_version.run_attempts.all()[offset:offset + 51])
    return {
        'plan_id': plan_id,
        'plan_version_id': version_id,
        'configurations': plan_version.configurations,
        'runs': [_render(attempt, plan_version) for attempt in page[:50]],
        'previous_offset': max(offset - 50, 0) if offset else None,
        'next_offset': offset + 50 if len(page) > 50 else None,
    }


def _registration_fields(payload):
    validate_json_size(payload)
    if not isinstance(payload, dict) or set(payload) != set(FIELD_FORMATS):
        _error('', 'invalid_shape')
    for name, pattern in FIELD_FORMATS.items():
        value = payload[name]
        if not isinstance(value, str) or re.fullmatch(pattern, value) is None:
            _error('/' + name, 'invalid_format')
    return payload


def _create_attempt(actor, plan_version, fields):
    configuration = next((item for item in plan_version.configurations if item['key'] == fields['configuration_key']), None)
    if configuration is None:
        _error('/configuration_key', 'inconsistent_context')
    if configuration['digest'] != fields['parameter_digest']:
        _error('/parameter_digest', 'inconsistent_context')
    _lock_idempotency_key('RUN-REF:' + fields['external_reference'])
    if RunAttempt.objects.filter(external_reference=fields['external_reference']).exists():
        raise ExternalReferenceConflict
    attempt = RunAttempt(plan_version=plan_version, reported_by=actor.get_username(), reporter_id=str(actor.pk), **fields)
    attempt.row_digest = digest({
        field.attname: wire(getattr(attempt, field.attname))
        for field in attempt._meta.concrete_fields if field.name != 'row_digest'
    })
    attempt.save(force_insert=True)
    return attempt


def register_attempt(*, actor, plan_id, version_id, idempotency_key, payload):
    require_actor(actor, write=True)
    if not isinstance(idempotency_key, str) or re.fullmatch(r'[A-Za-z0-9._:-]{1,128}', idempotency_key) is None:
        _error('/Idempotency-Key', 'invalid_format')
    fields = _registration_fields(payload)
    storage_key = 'RUN:' + digest([str(actor.pk), idempotency_key])
    path = f'/api/v1/test-plans/{plan_id}/versions/{version_id}/runs'
    with transaction.atomic():
        plan_version = _version(plan_id, version_id)
        request_digest = digest({'actor': str(actor.pk), 'method': 'POST', 'path': path, 'payload': fields})
        _lock_idempotency_key(storage_key)
        replay = _replay_or_conflict(storage_key, request_digest)
        if replay is not None:
            return replay
        attempt = _create_attempt(actor, plan_version, fields)
        data = canonical_json_bytes(_render(attempt, plan_version))
        IdempotencyRecord.objects.create(
            key=storage_key, request_method='POST', request_path=path,
            request_sha256=request_digest, response_status=201,
            response_identity=attempt.public_id, response_bytes=data,
        )
        return StoredResponse(201, data)
