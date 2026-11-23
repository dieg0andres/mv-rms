"""Shared exact-result synthetic assurance persistence and history."""

from dataclasses import dataclass
import re

from django.db import transaction

from .models import IdempotencyRecord
from .research_context_common import Forbidden, HypothesisValidationError, StaleVersion, require_actor, wire
from .run_assurance_models import RunDecision, RunLesson, RunReview, USABLE_REVIEWS
from .run_assurance_policy import require_capability
from .run_assurance_serializers import FIELDS, PREFIXES, RELIANCE, validate_assurance_payload
from .run_result_services import ResultIntegrityError, _append, _record_digest, _run, get_result_version
from .run_result_validation import assess_criteria, expected_id
from .services import (ResourceNotFound, ServiceError, StoredResponse, _lock_idempotency_key,
                       _replay_or_conflict, canonical_json_bytes)
from .test_plan_services import _error, digest


MODELS = {'review': RunReview, 'decision': RunDecision, 'lesson': RunLesson}
KINDS = {action + 's': action for action in MODELS}
RELATED = {'review': ('supersedes', 'successor'), 'decision': ('supersedes', 'successor', 'review'),
           'lesson': ('supersedes', 'successor', 'review', 'decision')}
ASSESSMENT_FIELDS = ('criterion_edge_id', 'criterion_version_id', 'sample_satisfied',
                     'observed_value', 'reported_outcome', 'explanation')


class AssuranceConflict(ServiceError):
    code = 'assurance_reliance_conflict'
    safe_message = 'This operation cannot rely on the supplied synthetic evidence or record.'


def _manifest(result):
    return result.artifact_manifest['manifest_digest']


def _verify_criteria(result):
    try:
        fields = [{name: item[name] for name in ASSESSMENT_FIELDS} for item in result.assessments]
        assessments, outcome = assess_criteria(result.run, fields)
    except (TypeError, KeyError, HypothesisValidationError) as exc:
        raise ResultIntegrityError from exc
    if assessments != result.assessments or outcome != result.assessment_outcome:
        raise ResultIntegrityError


def _reference(result, row):
    if row is not None and (row.result_id != result.pk or row.result_digest != result.row_digest or
                            row.artifact_manifest_digest != _manifest(result) or row.row_digest != _record_digest(row)):
        raise ResultIntegrityError
    return row


def _rows(result, action):
    return MODELS[action].objects.filter(result=result).select_related(*RELATED[action])


def _id(row):
    return row.public_id if row else None


@dataclass(frozen=True)
class Heads:
    result: object
    result_head_id: str
    review: RunReview | None
    decision: RunDecision | None
    lesson: RunLesson | None

    @classmethod
    def read(cls, result):
        return cls(result, result.run.result_versions.values_list('public_id', flat=True).last(),
                   **{action: _reference(result, _rows(result, action).last()) for action in MODELS})

    def current(self, action, row):
        head = getattr(self, action)
        if row is None or head is None or self.result_head_id != self.result.public_id or row.pk != head.pk:
            return False
        if action == 'review':
            return True
        if not self.review or self.review.outcome not in USABLE_REVIEWS or row.review_id != self.review.pk:
            return False
        return action == 'decision' or (self.current('decision', self.decision) and row.decision_id == self.decision.pk)

    def require_reliance(self, actor, action):
        if self.result_head_id != self.result.public_id:
            raise StaleVersion
        if action != 'review':
            if not self.review or self.review.outcome not in USABLE_REVIEWS:
                raise AssuranceConflict
            if action == 'decision' and self.review.actor_id == str(actor.pk):
                raise Forbidden
        if action == 'lesson' and not self.current('decision', self.decision):
            raise AssuranceConflict


def _available(actor, heads):
    actions = []
    for action in MODELS:
        try:
            require_capability(action, actor, heads.result)
            heads.require_reliance(actor, action)
        except (Forbidden, StaleVersion, AssuranceConflict):
            continue
        actions.append(action)
    if actions:
        _verify_criteria(heads.result)
    return actions


def _scope(result):
    return {'plan_id': result.run.plan_version.record.public_id, 'plan_version_id': result.run.plan_version.public_id,
            'run_id': result.run.public_id, 'result_version_id': result.public_id, 'result_digest': result.row_digest,
            'artifact_manifest_digest': _manifest(result)}


def _render(heads, action, row, *, history=True):
    response = {**_scope(heads.result), f'{action}_id': row.public_id, 'sequence': row.sequence,
                'actor_id': row.actor_id, 'recorded_by': row.recorded_by, 'recorded_at': wire(row.recorded_at),
                'row_digest': row.row_digest, 'correction_reason': row.correction_reason,
                f'supersedes_{action}_id': _id(row.supersedes), **{field: getattr(row, field) for field in FIELDS[action]},
                **{f'{kind}_id': _id(getattr(row, kind)) for kind in RELIANCE[action]}}
    if history:
        response.update(current=heads.current(action, row), superseded_by_id=_id(getattr(row, 'successor', None)),
                        result_head_id=heads.result_head_id)
        response['impact'] = {
            relation: list(getattr(row, relation).values_list('public_id', flat=True))
            for relation in ('decisions', 'lessons') if hasattr(row, relation)
        }
    return response


def read_assurance(*, actor, plan_id, version_id, run_id, result_version_id):
    result = get_result_version(actor=actor, plan_id=plan_id, version_id=version_id, run_id=run_id,
                                result_version_id=result_version_id)
    heads = Heads.read(result)
    return {**_scope(result), 'result_head_id': heads.result_head_id, 'available_actions': _available(actor, heads),
            **{f'{action}_head_id': _id(getattr(heads, action)) for action in MODELS}}


def _kind(kind):
    if kind not in KINDS:
        raise ResourceNotFound
    return KINDS[kind]


def list_assurance(*, actor, plan_id, version_id, run_id, result_version_id, kind, offset='0'):
    result = get_result_version(actor=actor, plan_id=plan_id, version_id=version_id, run_id=run_id,
                                result_version_id=result_version_id)
    action = _kind(kind)
    if not isinstance(offset, str) or re.fullmatch(r'[0-9]{1,8}', offset) is None:
        _error('/offset', 'invalid_format')
    start = int(offset)
    heads = Heads.read(result)
    rows = list(_rows(result, action)[start:start + 51])
    return {'records': [_render(heads, action, _reference(result, row)) for row in rows[:50]],
            'next_offset': str(start + 50) if len(rows) > 50 else None}


def read_assurance_record(*, actor, plan_id, version_id, run_id, result_version_id, kind, record_id):
    result = get_result_version(actor=actor, plan_id=plan_id, version_id=version_id, run_id=run_id,
                                result_version_id=result_version_id)
    action = _kind(kind)
    expected_id(record_id, PREFIXES[action], '/record_id')
    try:
        row = _rows(result, action).get(public_id=record_id)
    except MODELS[action].DoesNotExist as exc:
        raise ResourceNotFound from exc
    return _render(Heads.read(result), action, _reference(result, row))


def _write(action, *, actor, plan_id, version_id, run_id, result_version_id, idempotency_key, payload):
    require_actor(actor)
    if not isinstance(idempotency_key, str) or re.fullmatch(r'[A-Za-z0-9._:-]{1,128}', idempotency_key) is None:
        _error('/Idempotency-Key', 'invalid_format')
    clean = validate_assurance_payload(action, payload)
    path = f'/api/v1/test-plans/{plan_id}/versions/{version_id}/runs/{run_id}/results/{result_version_id}/{action}s'
    storage_key = 'ASSURE:' + digest([str(actor.pk), idempotency_key])
    request_digest = digest({'actor': str(actor.pk), 'method': 'POST', 'path': path, 'payload': payload})
    with transaction.atomic():
        _lock_idempotency_key(storage_key)
        _run(plan_id, version_id, run_id, lock=True)
        result = get_result_version(actor=actor, plan_id=plan_id, version_id=version_id, run_id=run_id,
                                    result_version_id=result_version_id)
        require_capability(action, actor, result)
        _verify_criteria(result)
        replay = _replay_or_conflict(storage_key, request_digest)
        if replay is not None:
            return replay
        heads = Heads.read(result)
        heads.require_reliance(actor, action)
        previous = getattr(heads, action)
        if clean.pop(f'expected_{action}_id') != _id(previous):
            raise StaleVersion
        if action == 'review':
            if clean.pop('artifact_manifest_digest') != _manifest(result):
                raise AssuranceConflict
            if clean['outcome'] == 'pass' and result.assessment_outcome != 'criteria_pass':
                raise AssuranceConflict
        for kind in RELIANCE[action]:
            subject = getattr(heads, kind)
            if clean.pop(f'{kind}_id') != _id(subject):
                raise StaleVersion
            clean[kind] = subject
        row = MODELS[action](result=result, result_digest=result.row_digest, artifact_manifest_digest=_manifest(result),
                             sequence=previous.sequence + 1 if previous else 1, supersedes=previous, **clean)
        _append(row, actor)
        data = canonical_json_bytes(_render(heads, action, row, history=False))
        IdempotencyRecord.objects.create(key=storage_key, request_method='POST', request_path=path,
                                         request_sha256=request_digest, response_status=201,
                                         response_identity=row.public_id, response_bytes=data)
        return StoredResponse(201, data)


def publish_review(*, actor, plan_id, version_id, run_id, result_version_id, idempotency_key, payload):
    return _write('review', actor=actor, plan_id=plan_id, version_id=version_id, run_id=run_id,
                  result_version_id=result_version_id, idempotency_key=idempotency_key, payload=payload)


def record_decision(*, actor, plan_id, version_id, run_id, result_version_id, idempotency_key, payload):
    return _write('decision', actor=actor, plan_id=plan_id, version_id=version_id, run_id=run_id,
                  result_version_id=result_version_id, idempotency_key=idempotency_key, payload=payload)


def record_lesson(*, actor, plan_id, version_id, run_id, result_version_id, idempotency_key, payload):
    return _write('lesson', actor=actor, plan_id=plan_id, version_id=version_id, run_id=run_id,
                  result_version_id=result_version_id, idempotency_key=idempotency_key, payload=payload)
