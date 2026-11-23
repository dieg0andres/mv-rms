"""Read-only saved origins for one exact synthetic RR14 Plan version."""

from django.utils import timezone

from .research_context_common import require_actor, wire
from .run_assurance_models import RunDecision, USABLE_REVIEWS
from .run_assurance_services import _reference, _verify_criteria
from .run_attempt_services import _version
from .run_result_models import RunRetry
from .run_result_services import ResultIntegrityError, _record_digest, _verify_result


def _origin(record, identity):
    if record.row_digest != _record_digest(record):
        raise ResultIntegrityError
    return {'id': str(identity), 'digest': record.row_digest, 'recorded_at': wire(record.recorded_at)}


def read_saved_origins(*, actor, plan_id, plan_version_id):
    require_actor(actor)
    version = _version(actor, plan_id, plan_version_id)
    saved_attempts = list(version.run_attempts.prefetch_related('lifecycle_events').order_by('public_id'))
    attempt_keys = [attempt.pk for attempt in saved_attempts]
    attempts = []
    for attempt in saved_attempts:
        attempts.append({**_origin(attempt, attempt.public_id), 'configuration_key': attempt.configuration_key,
                         'parameter_digest': attempt.parameter_digest,
                         'events': [{**_origin(event, event.public_id), 'sequence': event.sequence, 'state': event.state}
                                    for event in attempt.lifecycle_events.all()]})
    retries = [
        {**_origin(edge, edge.pk), 'predecessor_id': edge.predecessor.public_id,
         'successor_id': edge.successor.public_id, 'terminal_event_id': edge.terminal_event.public_id}
        for edge in RunRetry.objects.filter(predecessor_id__in=attempt_keys, successor_id__in=attempt_keys,
                                            terminal_event__run_id__in=attempt_keys)
        .select_related('predecessor', 'successor', 'terminal_event').order_by('pk')
    ]
    decisions = RunDecision.objects.filter(
        result__run_id__in=attempt_keys, result__version=1, result__supersedes__isnull=True,
        sequence=1, supersedes__isnull=True, disposition='close_rejected',
    ).select_related('review', 'result__run__plan_version', 'result__completed_event').order_by('public_id')
    closures = []
    for decision in decisions:
        result, review = decision.result, decision.review
        _verify_result(result)
        _verify_criteria(result)
        _reference(result, decision)
        _reference(result, review)
        if review.outcome not in USABLE_REVIEWS:
            continue
        if decision.actor_id == review.actor_id or (review.outcome == 'pass' and result.assessment_outcome != 'criteria_pass'):
            raise ResultIntegrityError
        closures.append({**_origin(decision, decision.public_id), 'sequence': decision.sequence,
                         'run_id': result.run.public_id, 'result_version_id': result.public_id,
                         'result_digest': result.row_digest, 'artifact_manifest_digest': decision.artifact_manifest_digest,
                         'completed_event_id': result.completed_event.public_id, 'review_id': review.public_id,
                         'review_digest': review.row_digest})
    return {'classification': 'synthetic', 'plan_id': plan_id, 'plan_version_id': plan_version_id,
            'observed_at': wire(timezone.now()),
            'plan_digest': version.row_digest, 'configuration_digest': version.config_digest,
            'activity_trials': {'count': len(attempts), 'origins': attempts, 'retry_edges': retries},
            'early_closures': {'count': len(closures), 'origins': closures},
            'real_credit_from_these_records': {'full_validation_cycles': 0, 'qualifications': 0},
            'real_totals': {'activity_trials': None, 'early_closures': None, 'full_validation_cycles': None,
                            'qualifications': None}}
