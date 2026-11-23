"""Shared writes and reads of synthetic observations; never dispatches a run."""

import base64
import hashlib
import re

from django.db import transaction

from .models import IdempotencyRecord
from .permissions import has_rms_write_access
from .research_context_common import StaleVersion, require_actor, wire
from .run_attempt_models import RunAttempt
from .run_attempt_services import FIELD_FORMATS, _create_attempt, _registration_fields, _render, _version
from .run_result_models import RunLifecycleEvent, RunResultVersion, RunRetry
from .run_result_validation import (
    assess_criteria, criterion_context, criterion_edges, expected_id, seal_artifact, shape, stage_artifact, text,
)
from .services import ResourceNotFound, ServiceError, StoredResponse, _lock_idempotency_key, _replay_or_conflict, canonical_json_bytes
from .test_plan_services import _error, digest
from .test_plan_validation import validate_json_size


TRANSITIONS = {
    'registered': ('running', 'failed', 'cancelled'),
    'running': ('completed', 'failed', 'cancelled'),
}


class RunConflict(ServiceError):
    code = 'invalid_run_transition'
    safe_message = 'The operation conflicts with this attempt’s current state.'


class ResultIntegrityError(ServiceError):
    code = 'result_integrity_error'
    safe_message = 'This synthetic result cannot be verified and is unavailable.'


def _run(plan_id, version_id, run_id, *, lock=False):
    plan_version = _version(plan_id, version_id)
    attempts = RunAttempt.objects.filter(plan_version=plan_version, public_id=run_id)
    if lock:
        attempts = attempts.select_for_update()
    try:
        run = attempts.get()
    except RunAttempt.DoesNotExist as exc:
        raise ResourceNotFound from exc
    run.plan_version = plan_version
    return run


def _event_render(event):
    return {'event_id': event.public_id, 'previous_event_id': event.previous_event.public_id if event.previous_event else None,
            'state': event.state, 'sequence': event.sequence, 'reason': event.reason,
            'recorded_by': event.recorded_by, 'recorded_at': wire(event.recorded_at), 'row_digest': event.row_digest}


def _result_render(result, *, detail=False):
    rendered = {'result_version_id': result.public_id, 'run_id': result.run.public_id,
                'plan_version_id': result.run.plan_version.public_id, 'version': result.version,
                'completed_event_id': result.completed_event.public_id,
                'supersedes_result_version_id': result.supersedes.public_id if result.supersedes else None,
                'correction_reason': result.correction_reason, 'assessment_outcome': result.assessment_outcome,
                'recorded_by': result.recorded_by, 'recorded_at': wire(result.recorded_at), 'row_digest': result.row_digest}
    if detail:
        rendered.update(summary=result.summary, assessments=result.assessments, artifact=result.artifact_manifest)
    return rendered


def _links(run):
    retry = RunRetry.objects.filter(predecessor=run).select_related('successor', 'terminal_event').first()
    previous = RunRetry.objects.filter(successor=run).select_related('predecessor', 'terminal_event').first()
    return {
        'retry_run_id': retry.successor.public_id if retry else None,
        'retry_of_run_id': previous.predecessor.public_id if previous else None,
        'retry_reason': previous.reason if previous else None,
        'retry_of_event_id': previous.terminal_event.public_id if previous else None,
    }


def _can_retry(state, *, has_retry):
    return state in ('failed', 'cancelled') and not has_retry


def _can_publish_result(state):
    return state == 'completed'


def read_run(*, actor, plan_id, version_id, run_id):
    require_actor(actor)
    run = _run(plan_id, version_id, run_id)
    events = list(run.lifecycle_events.select_related('previous_event'))
    state = events[-1].state if events else 'registered'
    links = _links(run)
    rendered = {**_render(run, run.plan_version), **links,
                'state': state, 'current_event_id': events[-1].public_id if events else None,
                'events': [_event_render(event) for event in events],
                'criteria': [criterion_context(edge) for edge in criterion_edges(run)]}
    if has_rms_write_access(actor):
        actions = []
        event_states = TRANSITIONS.get(state, ())
        if event_states:
            actions.append('event')
            rendered['allowed_event_states'] = list(event_states)
        if _can_retry(state, has_retry=links['retry_run_id'] is not None):
            actions.append('retry')
        if _can_publish_result(state):
            actions.append('result')
        rendered['available_actions'] = actions
    return rendered


def list_results(*, actor, plan_id, version_id, run_id, offset='0'):
    require_actor(actor)
    if not isinstance(offset, str) or re.fullmatch(r'[0-9]{1,8}', offset) is None:
        _error('/offset', 'invalid_format')
    start = int(offset)
    run = _run(plan_id, version_id, run_id)
    page = list(run.result_versions.select_related('completed_event', 'supersedes').order_by('-version')[start:start + 51])
    for result in page[:50]:
        result.run = run
        _verify_result(result)
    return {'results': [_result_render(result) for result in page[:50]],
            'next_offset': start + 50 if len(page) > 50 else None}


def _record_digest(record):
    return digest({field.attname: wire(getattr(record, field.attname))
                   for field in record._meta.concrete_fields if field.name not in ('row_digest', 'artifact_bytes')})


def _verify_result(result):
    manifest = result.artifact_manifest
    checksum = hashlib.sha256(bytes(result.artifact_bytes)).hexdigest()
    expected = seal_artifact(actor_name=result.recorded_by, run=result.run, result=result, checksum=checksum)
    if (manifest != expected or result.completed_event.run_id != result.run_id or
            result.completed_event.state != 'completed' or result.row_digest != _record_digest(result)):
        raise ResultIntegrityError


def get_result_version(*, actor, plan_id, version_id, run_id, result_version_id):
    """Resolve an authorized exact result for consumers, including independent review."""
    require_actor(actor)
    run = _run(plan_id, version_id, run_id)
    try:
        result = run.result_versions.select_related('completed_event', 'supersedes').get(public_id=result_version_id)
    except RunResultVersion.DoesNotExist as exc:
        raise ResourceNotFound from exc
    result.run = run
    _verify_result(result)
    return result


def read_result(*, artifact=False, **context):
    result = get_result_version(**context)
    if artifact:
        return {'manifest': result.artifact_manifest, 'content_base64': base64.b64encode(result.artifact_bytes).decode('ascii')}
    return _result_render(result, detail=True)


def _append(record, actor):
    record.actor_id = str(actor.pk)
    record.recorded_by = actor.get_username()
    record.row_digest = _record_digest(record)
    record.save(force_insert=True)


def _write(actor, plan_id, version_id, run_id, key, payload, suffix, operation):
    require_actor(actor, write=True)
    if not isinstance(key, str) or re.fullmatch(r'[A-Za-z0-9._:-]{1,128}', key) is None:
        _error('/Idempotency-Key', 'invalid_format')
    validate_json_size(payload)
    path = f'/api/v1/test-plans/{plan_id}/versions/{version_id}/runs/{run_id}/{suffix}'
    storage_key = 'RUN:' + digest([str(actor.pk), key])
    request_digest = digest({'actor': str(actor.pk), 'method': 'POST', 'path': path, 'payload': payload})
    with transaction.atomic():
        _lock_idempotency_key(storage_key)
        run = _run(plan_id, version_id, run_id, lock=True)
        replay = _replay_or_conflict(storage_key, request_digest)
        if replay is not None:
            return replay
        identity, response = operation(run)
        data = canonical_json_bytes(response)
        IdempotencyRecord.objects.create(key=storage_key, request_method='POST', request_path=path,
                                         request_sha256=request_digest, response_status=201,
                                         response_identity=identity, response_bytes=data)
        return StoredResponse(201, data)


def _current_event(run, expected):
    event = run.lifecycle_events.last()
    if expected != (event.public_id if event else None):
        raise StaleVersion
    return event


def append_event(*, actor, plan_id, version_id, run_id, idempotency_key, payload):
    def operation(run):
        shape(payload, 'expected_event_id state reason')
        previous = _current_event(run, expected_id(payload['expected_event_id'], 'RUE', '/expected_event_id', nullable=True))
        target = payload['state']
        if target not in RunLifecycleEvent.STATES:
            _error('/state', 'invalid_value')
        if target not in TRANSITIONS.get(previous.state if previous else 'registered', ()):
            raise RunConflict
        event = RunLifecycleEvent(run=run, previous_event=previous, sequence=previous.sequence + 1 if previous else 1,
                                  state=target, reason=text(payload['reason'], '/reason'))
        _append(event, actor)
        return event.public_id, _event_render(event)

    return _write(actor, plan_id, version_id, run_id, idempotency_key, payload, 'events', operation)


def retry_run(*, actor, plan_id, version_id, run_id, idempotency_key, payload):
    def operation(run):
        shape(payload, 'expected_event_id external_reference reason')
        previous = _current_event(run, expected_id(payload['expected_event_id'], 'RUE', '/expected_event_id'))
        if not _can_retry(previous.state, has_retry=RunRetry.objects.filter(predecessor=run).exists()):
            raise RunConflict
        reason = text(payload['reason'], '/reason')
        fields = {name: getattr(run, name) for name in FIELD_FORMATS}
        fields['external_reference'] = payload['external_reference']
        successor = _create_attempt(actor, run.plan_version, _registration_fields(fields))
        _append(RunRetry(predecessor=run, successor=successor, terminal_event=previous, reason=reason), actor)
        return successor.public_id, {**_render(successor, run.plan_version), **_links(successor), 'state': 'registered'}

    return _write(actor, plan_id, version_id, run_id, idempotency_key, payload, 'retry', operation)


def publish_result(*, actor, plan_id, version_id, run_id, idempotency_key, payload):
    def operation(run):
        shape(payload, 'completed_event_id expected_result_version_id correction_reason summary assessments artifact')
        event = _current_event(run, expected_id(payload['completed_event_id'], 'RUE', '/completed_event_id'))
        if not _can_publish_result(event.state):
            raise RunConflict
        previous = run.result_versions.last()
        expected = expected_id(payload['expected_result_version_id'], 'RESV', '/expected_result_version_id', nullable=True)
        if expected != (previous.public_id if previous else None):
            raise StaleVersion
        reason = payload['correction_reason']
        if previous is None and reason is not None:
            _error('/correction_reason', 'incompatible_field')
        if previous is not None:
            _verify_result(previous)
            reason = text(reason, '/correction_reason')
        assessments, outcome = assess_criteria(run, payload['assessments'])
        data, checksum = stage_artifact(payload['artifact'])
        result = RunResultVersion(run=run, completed_event=event, version=previous.version + 1 if previous else 1,
                                  supersedes=previous, correction_reason=reason, summary=text(payload['summary'], '/summary'),
                                  assessment_outcome=outcome, assessments=assessments, artifact_bytes=data)
        result.artifact_manifest = seal_artifact(actor_name=actor.get_username(), run=run, result=result, checksum=checksum)
        _append(result, actor)
        result.refresh_from_db(fields=['artifact_bytes', 'artifact_manifest'])
        _verify_result(result)
        return result.public_id, _result_render(result, detail=True)

    return _write(actor, plan_id, version_id, run_id, idempotency_key, payload, 'results', operation)
