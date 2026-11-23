"""Validate bounded synthetic evidence and evaluate exact PlanCriterion edges."""

import base64
import binascii
from decimal import Decimal
import hashlib
import operator
import re

from .test_plan_services import _error, digest


MAX_ARTIFACT_BYTES = 8192
MAX_ASSESSMENTS = 50
DECIMAL = re.compile(r'-?(0|[1-9][0-9]*)(\.[0-9]+)?')
COMPARISONS = {'gt': operator.gt, 'gte': operator.ge, 'lt': operator.lt,
               'lte': operator.le, 'eq': operator.eq}


def shape(value, keys, path=''):
    if not isinstance(value, dict) or set(value) != set(keys.split()):
        _error(path, 'invalid_shape')


def text(value, path):
    if (not isinstance(value, str) or not value.strip() or len(value) > 2000 or
            any(ord(char) < 32 and char not in '\n\t\r' for char in value)):
        _error(path, 'invalid_text')
    return value.strip()


def expected_id(value, prefix, path, *, nullable=False):
    if value is None and nullable:
        return None
    if not isinstance(value, str) or not re.fullmatch(rf'{prefix}-[0-9a-f]{{8}}(?:-[0-9a-f]{{4}}){{3}}-[0-9a-f]{{12}}', value):
        _error(path, 'invalid_format')
    return value


def criterion_edges(run, *, require_complete=False):
    edges = list(run.plan_version.associations.filter(kind='PlanCriterion').select_related('criterion_version'))
    applicable = []
    for edge in edges:
        criterion = edge.criterion_version
        scope = criterion.fields.get('applies_to')
        if (criterion.classification != run.plan_version.classification or
                criterion.authority_reference != run.plan_version.authority_reference or
                (require_complete and scope not in ('baseline', 'all_configurations'))):
            _error('/assessments', 'inconsistent_criterion')
        if run.configuration_key == 'baseline' or scope != 'baseline':
            applicable.append(edge)
    return applicable


def criterion_context(edge):
    return {'criterion_edge_id': edge.public_id, 'criterion_version_id': edge.criterion_version.public_id,
            'criterion_digest': edge.criterion_version.row_digest, 'edge_digest': edge.row_digest,
            'rule': edge.criterion_version.fields}


def _decimal(value, path):
    if not isinstance(value, str) or len(value) > 128 or DECIMAL.fullmatch(value) is None:
        _error(path, 'invalid_decimal')
    return Decimal(value)


def _assess(edge, item, path):
    shape(item, 'criterion_edge_id criterion_version_id sample_satisfied observed_value reported_outcome explanation', path)
    context = criterion_context(edge)
    if item['criterion_version_id'] != context['criterion_version_id']:
        _error(path + '/criterion_version_id', 'inconsistent_context')
    rule = context['rule']
    sample = item['sample_satisfied']
    if type(sample) is not bool:
        _error(path + '/sample_satisfied', 'invalid_value')
    if (type(rule.get('mandatory')) is not bool or edge.required != rule['mandatory'] or
            not all(rule.get(name) for name in ('name', 'metric', 'sample_requirement', 'evaluator_role'))):
        _error(path, 'incomplete_criterion')
    observed = item['observed_value']
    reported = item['reported_outcome']
    evaluation = 'inconclusive'
    if rule.get('rule_type') == 'numeric':
        comparator = rule.get('operator')
        if not rule.get('units') or comparator not in (*COMPARISONS, 'between_inclusive'):
            _error(path, 'incomplete_criterion')
        lower = _decimal(rule.get('threshold'), path)
        upper = _decimal(rule.get('upper_threshold'), path) if comparator == 'between_inclusive' else None
        if reported is not None:
            _error(path + '/reported_outcome', 'incompatible_field')
        value = _decimal(observed, path + '/observed_value') if sample or observed is not None else None
        if sample:
            passed = lower <= value <= upper if upper is not None else COMPARISONS[comparator](value, lower)
            evaluation = 'passed' if passed else 'failed'
    elif rule.get('rule_type') == 'objective_rule' and rule.get('objective_rule'):
        if observed is not None or reported not in ('passed', 'failed', 'inconclusive') or (not sample and reported != 'inconclusive'):
            _error(path + '/reported_outcome', 'incompatible_field')
        evaluation = reported
    else:
        _error(path, 'incomplete_criterion')
    return {**context, 'sample_satisfied': sample, 'observed_value': observed,
            'reported_outcome': reported, 'evaluation': evaluation,
            'explanation': text(item['explanation'], path + '/explanation')}


def assess_criteria(run, items):
    edges = criterion_edges(run, require_complete=True)
    if not isinstance(items, list) or len(items) != len(edges) or len(items) > MAX_ASSESSMENTS:
        _error('/assessments', 'exact_coverage_required')
    by_id = {edge.public_id: edge for edge in edges}
    results = {}
    for index, item in enumerate(items):
        path = f'/assessments/{index}'
        shape(item, 'criterion_edge_id criterion_version_id sample_satisfied observed_value reported_outcome explanation', path)
        edge_id = expected_id(item['criterion_edge_id'], 'TPAS', path + '/criterion_edge_id')
        if edge_id not in by_id or edge_id in results:
            _error(path + '/criterion_edge_id', 'inconsistent_context')
        results[edge_id] = _assess(by_id[edge_id], item, path)
    ordered = [results[edge.public_id] for edge in edges]
    mandatory = [item['evaluation'] for item in ordered if item['rule']['mandatory']]
    if 'failed' in mandatory:
        return ordered, 'mandatory_fail'
    return ordered, 'criteria_pass' if mandatory and all(item == 'passed' for item in mandatory) else 'inconclusive'


def stage_artifact(item, path='/artifact'):
    shape(item, 'content_base64 sha256 synthetic_confirmed', path)
    encoded = item['content_base64']
    if (item['synthetic_confirmed'] is not True or not isinstance(encoded, str) or
            not 1 <= len(encoded) <= 4 * ((MAX_ARTIFACT_BYTES + 2) // 3)):
        _error(path, 'invalid_synthetic_artifact')
    try:
        data = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error):
        _error(path + '/content_base64', 'invalid_base64')
    if not 1 <= len(data) <= MAX_ARTIFACT_BYTES or base64.b64encode(data).decode('ascii') != encoded:
        _error(path + '/content_base64', 'invalid_size_or_encoding')
    checksum = hashlib.sha256(data).hexdigest()
    if item['sha256'] != checksum:
        _error(path + '/sha256', 'digest_mismatch')
    return data, checksum


def seal_artifact(*, actor_name, run, result, checksum):
    manifest = {
        'schema_version': '1.0', 'state': 'sealed', 'integrity_scope': 'local_synthetic_only',
        'classification': 'synthetic', 'media_type': 'application/octet-stream',
        'byte_length': len(result.artifact_bytes), 'sha256': checksum,
        'authority_reference': run.plan_version.authority_reference,
        'run_id': run.public_id, 'run_digest': run.row_digest,
        'external_reference': run.external_reference, 'plan_version_id': run.plan_version.public_id,
        'plan_version_digest': run.plan_version.row_digest, 'configuration_key': run.configuration_key,
        'configuration_digest': run.parameter_digest, 'reported_by': actor_name,
        'watermark': {'result_version_id': result.public_id, 'completed_event_id': result.completed_event.public_id,
                      'completed_event_digest': result.completed_event.row_digest,
                      'assessment_digest': digest(result.assessments)},
    }
    return {**manifest, 'manifest_digest': digest(manifest)}
