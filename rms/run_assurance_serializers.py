"""Strict shared input contract for the assurance API and browser adapters."""

import re

from .run_assurance_models import DISPOSITIONS, REVIEW_OUTCOMES
from .run_result_validation import expected_id, shape, text
from .test_plan_services import _error
from .test_plan_validation import validate_json_size


FIELDS = {
    'review': ('outcome', 'rationale', 'limitations'),
    'decision': ('disposition', 'rationale'),
    'lesson': ('claim', 'limitations', 'uncertainty', 'applicability', 'implication'),
}
PREFIXES = {'review': 'REV', 'decision': 'DEC', 'lesson': 'LES'}
RELIANCE = {'review': (), 'decision': ('review',), 'lesson': ('review', 'decision')}


def validate_assurance_payload(action, payload):
    validate_json_size(payload)
    expected = f'expected_{action}_id'
    references = ('artifact_manifest_digest',) if action == 'review' else tuple(
        f'{kind}_id' for kind in RELIANCE[action]
    )
    shape(payload, ' '.join((expected, 'correction_reason', *FIELDS[action], *references)))
    clean = {expected: expected_id(payload[expected], PREFIXES[action], f'/{expected}', nullable=True)}
    reason = payload['correction_reason']
    if (reason is None) != (clean[expected] is None):
        _error('/correction_reason', 'inconsistent_predecessor')
    clean['correction_reason'] = text(reason, '/correction_reason') if reason is not None else None
    for field in FIELDS[action]:
        choices = {'outcome': REVIEW_OUTCOMES, 'disposition': DISPOSITIONS}.get(field)
        value = payload[field]
        if choices is not None and value not in choices:
            _error(f'/{field}', 'invalid_choice')
        clean[field] = value if choices else text(value, f'/{field}')
    for kind in RELIANCE[action]:
        field = f'{kind}_id'
        clean[field] = expected_id(payload[field], PREFIXES[kind], f'/{field}')
    if action == 'review':
        manifest = payload['artifact_manifest_digest']
        if not isinstance(manifest, str) or re.fullmatch(r'[0-9a-f]{64}', manifest) is None:
            _error('/artifact_manifest_digest', 'invalid_format')
        clean['artifact_manifest_digest'] = manifest
    return clean
