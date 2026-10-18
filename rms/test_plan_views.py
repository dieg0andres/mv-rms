"""Browser presentation for the Backend-owned Strategy Specification/TestPlan API-1.

No domain validation, completeness calculation, or persistence belongs here.
"""
from copy import deepcopy
from importlib import import_module
import json
from uuid import uuid4

from django.db import DatabaseError
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie

from .navigation_views import navigation_context, SchemaUnavailable, service_failure
from .permissions import has_rms_write_access
from .services import ResourceNotFound, ServiceError
from .views import RmsPage


def plan_service(operation, **kwargs):
    try:
        module = import_module('rms.test_plan_services')
    except ModuleNotFoundError as error:
        if error.name != 'rms.test_plan_services':
            raise
        raise SchemaUnavailable('Test Plan services are unavailable.') from error
    return getattr(module, operation)(**kwargs)


def plan_url(plan_id, version_id=None):
    return '/test-plans/' + plan_id + ('/versions/' + version_id if version_id else '')


def page_context(request):
    return {**navigation_context(section='test-plans', role='editor' if has_rms_write_access(request.user) else 'founder_viewer'), 'repository_preview': False}


class TestPlanEditorPage(RmsPage):
    @method_decorator(ensure_csrf_cookie)
    def get(self, request, plan_id=None):
        self._require_editor(request)
        try:
            schema = read_plan_schema()
            hypothesis = None
            if plan_id:
                record = plan_service('read_test_plan', actor=request.user, plan_id=plan_id)
                payload = revision_payload(record)
                hypothesis = record['hypothesis']
            else:
                hypothesis = plan_service('read_hypothesis_version', actor=request.user,
                    version_id=request.query_params.get('hypothesis_version_id', ''))
                pin = hypothesis['hypothesis_version_id']
                if pin != request.query_params.get('hypothesis_version_id'):
                    raise ResourceNotFound
                payload = {'hypothesis_version_id': pin, 'fields': {}, 'criteria': [], 'data_requirements': []}
            return self.render_form(request, schema, payload, plan_id=plan_id, hypothesis=hypothesis)
        except (SchemaUnavailable, DatabaseError):
            return TemplateResponse(request._request, 'rms/service_unavailable.html', page_context(request), status=503)
        except (ValueError, ResourceNotFound):
            return self._not_found(request)
        except ServiceError as error:
            return service_failure(self, request, error)

    def render_form(self, request, schema, payload, *, plan_id=None, hypothesis=None, issues=(), status=200, key=None, unknown=False, raw=None, notice=None):
        from django.core import signing
        context = page_context(request)
        key = key or str(uuid4())
        groups = editor_groups(schema, payload, raw) if not self.check_form else [{'label': 'External check report', 'nodes': [form_node(schema, schema['$defs']['CheckCreate'], '', payload, raw)]}]
        annotate_errors(groups, issues)
        displayed_issues = [{**item, 'label': ' / '.join(('Item ' + str(int(part) + 1)) if part.isdigit() else label_for(part) for part in item.get('path', '').split('/') if part) or 'Save'} for item in issues]
        context.update(payload=payload, groups=groups, plan_id=plan_id, hypothesis=hypothesis, issues=displayed_issues,
            idempotency_key=key, unknown=unknown, conflict=status == 409,
            preserved_payload=json.dumps(payload, ensure_ascii=False, indent=2), latest_url=plan_url(plan_id) if plan_id else None,
            raw_input=raw, notice=notice, check_form=self.check_form,
            retry_token=signing.dumps({'actor': str(request.user.pk), 'key': key, 'payload': payload}, salt='test-plan-retry') if unknown else None)
        return TemplateResponse(request._request, 'rms/test_plan_form.html', context, status=status)

    check_form = False

    @method_decorator(csrf_protect)
    def post(self, request, plan_id=None):
        self._require_editor(request)
        from django.core import signing
        raw = {key: request.data.get(key, '') for key in request.data if key.startswith('/')}
        key = request.data.get('idempotency_key', '')
        payload = {}
        try:
            schema = read_plan_schema()
        except SchemaUnavailable:
            context = page_context(request)
            context.update(preserved_payload=json.dumps(raw, ensure_ascii=False), issues=[{'path': '', 'message': 'Schema unavailable. No save attempted; input retained.'}])
            return TemplateResponse(request._request, 'rms/test_plan_form.html', context, status=503)
        try:
            if request.data.get('retry_token'):
                retry = signing.loads(request.data['retry_token'], salt='test-plan-retry')
                if retry['actor'] != str(request.user.pk) or retry['key'] != key:
                    raise signing.BadSignature
                payload = retry['payload']
            else:
                name = 'CheckCreate' if self.check_form else 'PlanCorrection' if plan_id else 'PlanCreate'
                duplicates = [path for path in raw if len(request.data.getlist(path)) != 1]
                if duplicates:
                    raise FormTransportError(duplicates[0], 'Supply this form field once; no save attempted.')
                payload = decode_form(schema, schema['$defs'][name], raw)
            if request.data.get('operation', 'save') not in ('save', 'reapply_latest'):
                raise FormTransportError('', 'Choose a supported explicit action; no save attempted.')
            if request.data.get('operation') == 'reapply_latest' and plan_id and not self.check_form:
                latest = plan_service('read_test_plan', actor=request.user, plan_id=plan_id)
                payload['expected_latest_version'] = latest['version']
                # Deliberate reapplication uses current input child references,
                # while retaining the author's definition and ordering. The
                # shared save service still owns all child/plan authorization.
                for collection, identity, version_identity in (
                    ('criteria', 'criterion_id', 'criterion_version_id'),
                    ('data_requirements', 'data_requirement_id', 'data_requirement_version_id')):
                    current = {item[identity]: item for item in latest[collection]}
                    for index, item in enumerate(payload[collection]):
                        target = current.get(item[identity])
                        item[identity] = target[identity] if target else None
                        item[version_identity] = target[version_identity] if target else None
                        raw['/' + collection + '/' + str(index) + '/' + identity] = item[identity] or ''
                        raw['/' + collection + '/' + str(index) + '/' + version_identity] = item[version_identity] or ''
                return self.render_form(request, schema, payload, plan_id=plan_id, raw=raw, notice='Latest head and child input references explicitly adopted. Your definition, item order and Hypothesis proposal remain unchanged. Removed children are proposed as new items. Review all differences and give a revision reason before Save draft.')
            operation = 'record_data_access_check' if self.check_form else 'correct_test_plan' if plan_id else 'create_test_plan'
            stored = plan_service(operation, actor=request.user, payload=payload, idempotency_key=key, **({'plan_id': plan_id} if plan_id else {}))
        except signing.BadSignature:
            return self.render_form(request, schema, payload, plan_id=plan_id, raw=raw, status=400, issues=[{'path': '', 'message': 'Retry receipt is invalid. No save attempted.'}])
        except (SchemaUnavailable, DatabaseError):
            return self.render_form(request, schema, payload, plan_id=plan_id, raw=raw, status=503, key=key, unknown=True, issues=[{'path': '', 'message': 'Save outcome unknown. The proposal is locked for unchanged retry with its original key. Inspect the record before editing.'}])
        except ServiceError as error:
            status = getattr(error, 'http_status', 404 if isinstance(error, ResourceNotFound) else 409)
            if status in (401, 403):
                return service_failure(self, request, error)
            return self.render_form(request, schema, payload, plan_id=plan_id, raw=raw, status=status, issues=[{'path': '', 'message': 'Referenced record unavailable. Missing and restricted references use this same response.' if status == 404 else getattr(error, 'safe_message', 'Proposal conflicts with current state.')}])
        except Exception as error:
            if not hasattr(error, 'issues'):
                raise
            payload = getattr(error, 'proposal', None) or payload
            return self.render_form(request, schema, payload, plan_id=plan_id, raw=raw, status=400, issues=error.issues)
        saved = json.loads(stored.body)
        version_id = saved.get('plan_version_id') or payload.get('plan_version_id')
        identity = saved.get('plan_id', plan_id)
        receipt = signing.dumps({'actor': str(request.user.pk), 'plan': identity, 'version': version_id, 'status': stored.status}, salt='test-plan-saved')
        from urllib.parse import urlencode
        target = plan_url(identity, version_id)
        if self.check_form:
            target = plan_url(identity) + '/data-checks'
        response = HttpResponseRedirect(target + '?' + urlencode({'receipt': receipt}))
        response.status_code = 303
        return response


def revision_payload(record):
    payload = {'fields': deepcopy(record['fields']), 'hypothesis_version_id': record['hypothesis']['version_id'], 'expected_latest_version': record['version'], 'correction_reason': ''}
    payload['criteria'] = [{key: deepcopy(item[key]) for key in ('criterion_id', 'criterion_version_id', 'fields')} for item in record['criteria']]
    payload['data_requirements'] = [{key: deepcopy(item[key]) for key in ('data_requirement_id', 'data_requirement_version_id', 'fields')} for item in record['data_requirements']]
    return payload


# Presentation grouping; types, limits and choices come only from API-1.
PLAN_SECTIONS = (
    ('Purpose and Hypothesis', ('title', 'objective', 'scope_limitations', 'measurement_basis', 'measure_definition', 'hypothesis_alignment')),
    ('Strategy specification', ('universe_definition', 'signal_definition', 'entry_rules', 'exit_rules', 'position_rules', 'decision_timing', 'execution_timing', 'time_zone', 'pseudocode', 'edge_case_policy', 'expected_outputs', 'implementation_notes', 'reviewer_roles', 'parameters', 'parameter_policy')),
    ('Data', ()),
    ('Test design', ('evaluation_design', 'development_start', 'development_end', 'initial_evaluation_start', 'initial_evaluation_end', 'split_policy', 'reserve_boundary', 'sample_rule', 'warmup_rule', 'variations', 'trial_budget', 'related_trial_treatment', 'stopping_rule', 'benchmark_name', 'benchmark_definition', 'benchmark_rationale', 'benchmark_alignment', 'benchmark_difference_reason', 'benchmark_input_mode', 'benchmark_data_keys')),
    ('Evaluation', ('overall_interpretation', 'inconclusive_rule')),
)


SCHEMA_SHA256 = '17e17d366e89fb0e69c3d992dd06da7b2345bcef6193170015b7b733e26df82e'


def read_plan_schema(path=None):
    from pathlib import Path
    from django.conf import settings
    source = Path(path) if path else Path(settings.BASE_DIR) / 'rms/test_plan_schema.json'
    try:
        from hashlib import sha256
        content = source.read_bytes()
        if sha256(content).hexdigest() != SCHEMA_SHA256:
            raise SchemaUnavailable('API-1 schema differs from the adopted bytes.')
        return json.loads(content)
    except (OSError, ValueError) as error:
        raise SchemaUnavailable('The adopted API-1 schema is unavailable.') from error


def shape(schema, definition):
    return schema['$defs'][definition['$ref'].split('/')[-1]] if '$ref' in definition else definition


def label_for(name):
    return name.replace('_', ' ').capitalize()


def scalar_text(value):
    if value is None:
        return ''
    if value is True:
        return 'true'
    if value is False:
        return 'false'
    return str(value)


def form_node(schema, definition, path, value=None, raw=None, depth=0):
    """Schema-driven widgets; this describes inputs without judging validity."""
    definition = shape(schema, definition)
    name = path.rsplit('/', 1)[-1]
    types = definition.get('type', [])
    types = [types] if isinstance(types, str) else types
    node = {'path': path, 'id': 'tp' + path, 'label': label_for(name), 'maxlength': definition.get('maxLength'), 'value': scalar_text(value), 'kind': 'textarea'}
    if raw is not None and path in raw:
        node['value'] = raw[path]
    if 'properties' in definition:
        order = definition.get('x-field-order', list(definition['properties']))
        order = list(order) + [key for key in definition['properties'] if key not in order]
        node.update(kind='object', children=[form_node(schema, definition['properties'][key], path + '/' + key, (value or {}).get(key), raw, depth) for key in order])
    elif 'object' in types:
        node.update(kind='map', value=json.dumps(value or {}, ensure_ascii=False, indent=2))
        if raw is not None and path in raw:
            node['value'] = raw[path]
    elif 'array' in types:
        item = shape(schema, definition['items'])
        if item.get('type') == 'object' or 'properties' in item:
            token = '__row' + str(depth) + '__'
            node.update(kind='repeat', items=[form_node(schema, item, path + '/' + str(i), v, raw, depth + 1) for i, v in enumerate(value or [])], prototype=form_node(schema, item, path + '/' + token, {}, None, depth + 1), token=token, maximum=definition.get('maxItems'))
        else:
            node.update(kind='lines', value='\n'.join(value or []))
            if raw is not None and path in raw:
                node['value'] = raw[path]
    elif name.endswith('_id') or name == 'expected_latest_version':
        node['kind'] = 'hidden'
    elif 'enum' in definition or types == ['boolean'] or types == ['boolean', 'null']:
        choices = definition.get('enum', [True, False])
        node.update(kind='select', choices=[{'value': scalar_text(v), 'label': label_for(scalar_text(v))} for v in choices if v is not None])
        node['unknown_choice'] = bool(node['value'] and node['value'] not in [c['value'] for c in node['choices']])
    elif name in ('title', 'name', 'key', 'time_zone', 'source_time_zone', 'baseline_value') or 'integer' in types or definition.get('format') or definition.get('x-decimal'):
        node['kind'] = 'text'
    if name == 'sanitized_evidence_confirmed':
        node['label'] = 'Confirm evidence contains no credentials or restricted/real data samples'
    return node


def editor_groups(schema, payload, raw=None):
    sections = schema.get('x-completeness-sections')
    if not sections:
        sections = [[('/data_requirements' if label == 'Data' else '/fields/' + name) for name in names] for label, names in PLAN_SECTIONS]
        sections[2] = ['/data_requirements']
        sections[4].insert(0, '/criteria')
    groups = []
    for (label, _), paths in zip(PLAN_SECTIONS, sections):
        nodes = []
        for path in paths:
            definition = schema['$defs']['PlanCreate']
            value = payload
            for part in path.strip('/').split('/'):
                definition = shape(schema, definition)['properties'][part]
                value = (value or {}).get(part)
            nodes.append(form_node(schema, definition, path, value, raw))
        groups.append({'label': label, 'nodes': nodes})
    return groups


class FormTransportError(ValueError):
    def __init__(self, path, message, proposal=None):
        self.proposal = proposal
        self.issues = [{'path': path, 'code': 'invalid_form', 'message': message}]


def _unique_json(text):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate key')
            result[key] = value
        return result
    return json.loads(text, object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('nonfinite number')))


def decode_form(schema, definition, submitted, path='', consumed=None):
    """Convert HTML scalar transport to API-1 types. Services validate the result."""
    consumed = set() if consumed is None else consumed
    definition = shape(schema, definition)
    types = definition.get('type', [])
    types = [types] if isinstance(types, str) else types
    if 'properties' in definition:
        result = {key: decode_form(schema, item, submitted, path + '/' + key, consumed) for key, item in definition['properties'].items()}
        if path == '':
            unknown = sorted({key for key in submitted if key.startswith('/')} - consumed)
            if unknown:
                raise FormTransportError(unknown[0], 'Unknown form field; no save attempted.', result)
        return result
    consumed.add(path)
    raw = submitted.get(path, '')
    if 'array' in types:
        item = shape(schema, definition['items'])
        if 'properties' in item:
            prefix = path + '/'
            indexes = sorted({int(key[len(prefix):].split('/')[0]) for key in submitted if key.startswith(prefix) and key[len(prefix):].split('/')[0].isdigit()})
            return [decode_form(schema, item, submitted, path + '/' + str(i), consumed) for i in indexes]
        return raw.splitlines() if raw != '' else []
    if 'object' in types:
        try:
            return _unique_json(raw) if raw else {}
        except ValueError as error:
            return raw  # Keep malformed/duplicate-key transport intact; service rejects its type.
    if raw == '':
        return None if 'null' in types else ''
    if 'boolean' in types and 'string' not in types:
        return {'true': True, 'false': False}.get(raw, raw)
    if 'integer' in types and 'string' not in types:
        try:
            return int(raw)
        except ValueError:
            return raw  # Shared validator supplies the field error.
    if path.endswith('/baseline_value'):
        sibling = submitted.get(path.rsplit('/', 1)[0] + '/type')
        if sibling == 'integer':
            try:
                return int(raw)
            except ValueError:
                return raw
        if sibling == 'boolean':
            return {'true': True, 'false': False}.get(raw, raw)
    return raw


def definition_nodes(value, label=''):
    """Read-only plain-text projection; never interpret snippets, URLs or HTML."""
    if isinstance(value, dict):
        return [{'label': label_for(key), 'children': definition_nodes(item), 'value': None} for key, item in value.items()]
    if isinstance(value, list):
        return [{'label': 'Item ' + str(i + 1), 'children': definition_nodes(item), 'value': None} for i, item in enumerate(value)] or [{'label': label, 'value': 'No items', 'children': []}]
    return [{'label': label, 'value': scalar_text(value) if value is not None else 'Not supplied (unknown)', 'children': []}]


def confirmed_receipt(request, plan_id, version_id=None):
    from django.core import signing
    token = request.query_params.get('receipt')
    if not token:
        return None
    try:
        receipt = signing.loads(token, salt='test-plan-saved', max_age=3600)
        if receipt['actor'] == str(request.user.pk) and receipt['plan'] == plan_id and (version_id is None or receipt['version'] == version_id):
            return 'Draft saved.' if receipt['status'] == 201 else 'Unchanged draft confirmed; no new version created.'
    except (signing.BadSignature, KeyError):
        pass
    return None


def _page_links(listing, base, query):
    from urllib.parse import urlencode
    for key, delta in (('next', 1), ('previous', -1)):
        if listing.get(key):
            listing[key] = base + '?' + urlencode({**query, 'page': listing['page'] + delta, 'page_size': listing['page_size']})
    return listing


class TestPlanListPage(RmsPage):
    def get(self, request):
        self._require_reader(request)
        from .navigation_views import selection_query
        context = page_context(request)
        try:
            query = selection_query(request)
            listing = plan_service('list_test_plans', actor=request.user, query=query)
            context['listing'] = _page_links(listing, '/test-plans', query)
        except (SchemaUnavailable, DatabaseError):
            context['list_unavailable'] = True
            return TemplateResponse(request._request, 'rms/test_plan_list.html', context, status=503)
        except ServiceError as error:
            return service_failure(self, request, error)
        except Exception as error:
            if not hasattr(error, 'issues'):
                raise
            context['issues'] = error.issues
            return TemplateResponse(request._request, 'rms/test_plan_list.html', context, status=400)
        return TemplateResponse(request._request, 'rms/test_plan_list.html', context)


class TestPlanDetailPage(RmsPage):
    def get(self, request, plan_id, version_id=None):
        self._require_reader(request)
        context = page_context(request)
        try:
            record = plan_service('read_test_plan_version' if version_id else 'read_test_plan', actor=request.user, plan_id=plan_id, **({'version_id': version_id} if version_id else {}))
        except (SchemaUnavailable, DatabaseError):
            return TemplateResponse(request._request, 'rms/service_unavailable.html', context, status=503)
        except ServiceError as error:
            return service_failure(self, request, error)
        context.update(record=record, definition=definition_nodes({'fields': record['fields'], 'criteria': record['criteria'], 'data_requirements': record['data_requirements']}), historical=version_id is not None,
            latest_url=plan_url(plan_id), history_url=plan_url(plan_id) + '/history', revision_url=plan_url(plan_id) + '/revise', checks_url=plan_url(plan_id) + '/data-checks',
            lineage=plan_lineage(record), save_notice=confirmed_receipt(request, plan_id, record['plan_version_id']))
        return TemplateResponse(request._request, 'rms/test_plan_detail.html', context)


def plan_lineage(record):
    hypothesis = record.get('hypothesis', {})
    result = []
    if hypothesis.get('stable_id') and hypothesis.get('version'):
        result.append({'label': 'Pinned Hypothesis', 'url': '/hypotheses/' + hypothesis['stable_id'] + '/versions/' + str(hypothesis['version']), 'version_id': hypothesis['version_id']})
    context = record.get('research_context', {})
    for key, route, label in (('investigation', 'investigations', 'Pinned Research case'), ('family', 'research-families', 'Pinned Research family')):
        endpoint = context.get(key, {})
        if endpoint.get('stable_id') and endpoint.get('version'):
            result.append({'label': label, 'url': '/' + route + '/' + endpoint['stable_id'] + '/versions/' + str(endpoint['version']), 'version_id': endpoint['version_id']})
    from .navigation_views import record_display
    if hypothesis.get('origin'):
        for reference in record_display('hypothesis', hypothesis)['pinned_references']:
            if reference.get('url') and reference['url'] not in [x['url'] for x in result]:
                result.append(reference)
    return result


class TestPlanHistoryPage(RmsPage):
    def get(self, request, plan_id):
        self._require_reader(request)
        context = page_context(request)
        try:
            history = plan_service('read_test_plan_history', actor=request.user, plan_id=plan_id)
        except (SchemaUnavailable, DatabaseError):
            return TemplateResponse(request._request, 'rms/service_unavailable.html', context, status=503)
        except ServiceError as error:
            return service_failure(self, request, error)
        context.update(versions=history['results'], plan_id=plan_id, latest_url=plan_url(plan_id))
        return TemplateResponse(request._request, 'rms/test_plan_history.html', context)


class DataCheckListPage(RmsPage):
    def get(self, request, plan_id, check_id=None):
        self._require_reader(request)
        from .navigation_views import selection_query
        context = page_context(request)
        try:
            if check_id:
                report = plan_service('read_data_access_check', actor=request.user, plan_id=plan_id, check_id=check_id)
                context['report'] = report
                context['definition'] = definition_nodes(report)
            else:
                query = selection_query(request)
                query.pop('receipt', None)
                reports = plan_service('list_data_access_checks', actor=request.user, plan_id=plan_id, query=query)
                context['listing'] = _page_links(reports, plan_url(plan_id) + '/data-checks', query)
        except (SchemaUnavailable, DatabaseError):
            return TemplateResponse(request._request, 'rms/service_unavailable.html', context, status=503)
        except ServiceError as error:
            return service_failure(self, request, error)
        except Exception as error:
            if not hasattr(error, 'issues'):
                raise
            context['issues'] = error.issues
            return TemplateResponse(request._request, 'rms/test_plan_checks.html', context, status=400)
        context.update(plan_id=plan_id, latest_url=plan_url(plan_id), save_notice='External check report saved.' if confirmed_receipt(request, plan_id) else None)
        return TemplateResponse(request._request, 'rms/test_plan_checks.html', context)


class DataCheckEditorPage(TestPlanEditorPage):
    check_form = True

    @method_decorator(ensure_csrf_cookie)
    def get(self, request, plan_id):
        self._require_editor(request)
        try:
            schema = read_plan_schema()
            record = plan_service('read_test_plan_version', actor=request.user, plan_id=plan_id, version_id=request.query_params.get('plan_version_id', ''))
            payload = {'plan_version_id': record['plan_version_id']}
            supersedes = request.query_params.get('supersedes_check_id')
            if supersedes:
                report = plan_service('read_data_access_check', actor=request.user, plan_id=plan_id, check_id=supersedes)
                payload.update({key: deepcopy(report.get(key)) for key in schema['$defs']['CheckCreate']['properties']})
                payload.update(expected_current_check_id=supersedes, supersedes_check_id=supersedes, correction_reason='', sanitized_evidence_confirmed=None)
                if payload['plan_version_id'] != record['plan_version_id']:
                    raise ResourceNotFound
            else:
                payload.update(data_requirement_version_id=request.query_params.get('data_requirement_version_id', ''), configuration_key=request.query_params.get('configuration_key', ''), expected_current_check_id=None, supersedes_check_id=None, correction_reason=None)
            return self.render_form(request, schema, payload, plan_id=plan_id)
        except (SchemaUnavailable, DatabaseError):
            return TemplateResponse(request._request, 'rms/service_unavailable.html', page_context(request), status=503)
        except ServiceError as error:
            return service_failure(self, request, error)


def annotate_errors(groups, issues):
    def visit(node):
        node['issues'] = [item['message'] for item in issues if item.get('path') == node['path']]
        for child in node.get('children', []) + node.get('items', []):
            visit(child)
    for group in groups:
        for node in group['nodes']:
            visit(node)
