"""Render synthetic Run records using the same services as JSON requests."""
import base64
import json

from django.db import DatabaseError
from django.http import HttpResponse, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from rest_framework.parsers import FormParser

from . import run_result_services as services
from .navigation_views import service_failure
from .permissions import has_rms_write_access
from .run_workflow_forms import EventForm, ReconciliationForm, ResultForm, RetryForm
from .services import ResourceNotFound, ServiceError
from .test_plan_validation import TestPlanValidationError
from .views import RmsPage


OUTCOME_LABELS = {'criteria_pass': 'Applicable mandatory criteria passed', 'mandatory_fail': 'Mandatory criterion failed',
                  'inconclusive': 'Inconclusive'}
OPERATIONS = {
    'event': ('Record an observed execution event', EventForm, services.append_event),
    'reconcile': ('Reconcile an unknown execution state', ReconciliationForm, services.reconcile_event),
    'retry': ('Register a separate synthetic retry', RetryForm, services.retry_run),
    'result': ('Record a synthetic result', ResultForm, services.publish_result),
}


def workflow_scope(plan_id, version_id, run_id):
    args = [plan_id, version_id]
    return {
        'plan_url': reverse('rms-test-plan-version', args=args),
        'runs_url': reverse('rms-run-attempts', args=args),
        'attempt_url': reverse('rms-run-detail', args=[*args, run_id]),
        'plan_version_id': version_id, 'run_id': run_id,
    }


def result_url(ids, result_id):
    return reverse('rms-run-result-detail', args=[*ids, result_id])


def page_result(ids, row, head_id):
    result_id = row['result_version_id']
    return {'id': result_id, 'number': row['version'], 'url': result_url(ids, result_id),
            'outcome': OUTCOME_LABELS[row['assessment_outcome']], 'current': result_id == head_id,
            'recorded_by': row['recorded_by'], 'recorded_at': row['recorded_at']}


def action_url(ids, operation):
    return reverse('rms-run-action', args=[*ids, operation])


def advertised_actions(run):
    return [operation for operation in run.get('available_actions', ()) if operation in OPERATIONS
            and (operation != 'event' or run.get('allowed_event_states'))]


def action_links(actor, ids, run, head_id):
    if not has_rms_write_access(actor):
        return []
    actions = []
    for operation in advertised_actions(run):
        label = 'Correct the current result' if operation == 'result' and head_id else OPERATIONS[operation][0]
        actions.append({'url': action_url(ids, operation), 'label': label})
    return actions


class RunWorkflowPage(RmsPage):
    parser_classes = [FormParser]

    def context(self, request, plan_id, version_id, run_id):
        keys = {'actor': request.user, 'plan_id': plan_id, 'version_id': version_id, 'run_id': run_id}
        run = services.read_run(**keys)
        results = services.list_results(**keys)
        head = results['results'][0] if results['results'] else None
        ids = (plan_id, version_id, run_id)
        scope = workflow_scope(*ids)
        return keys, run, results, head, ids, scope

    def unavailable(self, request):
        return TemplateResponse(request._request, 'rms/service_unavailable.html', status=503)


class RunDetailPage(RunWorkflowPage):
    def get(self, request, plan_id, version_id, run_id):
        self._require_reader(request)
        try:
            keys, run, results, head, ids, scope = self.context(request, plan_id, version_id, run_id)
            offset = request.query_params.get('offset', '0')
            page = results if offset == '0' else services.list_results(**keys, offset=offset)
        except TestPlanValidationError:
            return TemplateResponse(request._request, 'rms/unavailable.html', status=400)
        except ServiceError as error:
            return service_failure(self, request, error)
        except DatabaseError:
            return self.unavailable(request)
        head_id = head['result_version_id'] if head else None
        known_links = {}
        for source, display in (('retry_of_run_id', 'retry_of'), ('retry_run_id', 'retry_successor')):
            if run.get(source):
                known_links[display] = run[source]
                known_links[f'{display}_url'] = workflow_scope(plan_id, version_id, run[source])['attempt_url']
        return TemplateResponse(request._request, 'rms/run_attempt_detail.html', {
            'scope': scope, 'attempt': {**run, **known_links}, 'execution_state': run['state'].capitalize(),
            'events': [{**event, 'label': event['state'].capitalize()} for event in run['events']],
            'result_outcome': OUTCOME_LABELS[head['assessment_outcome']] if head else None,
            'result_versions': [page_result(ids, item, head_id) for item in page['results']],
            'previous_offset': max(0, int(offset) - 50) if int(offset) else None, 'next_offset': page['next_offset'],
            'actions': action_links(request.user, ids, run, head_id),
        })


class RunResultPage(RunWorkflowPage):
    def get(self, request, plan_id, version_id, run_id, result_version_id):
        self._require_reader(request)
        try:
            keys, run, _, head, ids, scope = self.context(request, plan_id, version_id, run_id)
            row = services.read_result(**keys, result_version_id=result_version_id)
        except ServiceError as error:
            return service_failure(self, request, error)
        except DatabaseError:
            return self.unavailable(request)
        result = page_result(ids, row, head['result_version_id'] if head else None)
        prior_id = row['supersedes_result_version_id']
        if prior_id:
            result.update(corrects={'id': prior_id, 'url': result_url(ids, prior_id)}, correction_reason=row['correction_reason'])
        result.update(explanation=row['summary'], digest=row['row_digest'], completed_event_id=row['completed_event_id'])
        manifest = row['artifact']
        return TemplateResponse(request._request, 'rms/run_result_detail.html', {
            'scope': scope, 'execution_state': run['state'].capitalize(), 'result': result,
            'assurance_url': reverse('rms-run-assurance', args=[*ids, result_version_id]),
            'evidence_url': reverse('rms-run-result-evidence', args=[*ids, result_version_id]),
            'criteria': [{'label': item['rule']['name'], 'id': item['criterion_version_id'],
                          'requirement': 'Mandatory' if item['rule']['mandatory'] else 'Optional',
                          'outcome': item['evaluation'].capitalize(), 'observation': item['observed_value'],
                          'explanation': item['explanation']} for item in row['assessments']],
            'artifacts': [{'label': 'Synthetic artifact manifest', 'sha256': manifest['sha256'],
                           'byte_length': manifest['byte_length'], 'provenance': manifest['external_reference'],
                           'reporter': manifest['reported_by'], 'manifest_digest': manifest['manifest_digest'],
                           'integrity': manifest['integrity_scope']}],
        })


class RunEvidencePage(RunWorkflowPage):
    def get(self, request, plan_id, version_id, run_id, *, event_id=None, result_version_id=None):
        self._require_reader(request)
        keys = {'actor': request.user, 'plan_id': plan_id, 'version_id': version_id, 'run_id': run_id}
        ids = [plan_id, version_id, run_id]
        try:
            if event_id is not None:
                evidence = services.read_event_evidence(**keys, event_id=event_id)
                record_url = reverse('rms-run-detail', args=ids)
                record_label = 'Execution history'
                title = 'Event evidence'
                identity = evidence['manifest']['event_id']
            else:
                evidence = services.read_result(**keys, result_version_id=result_version_id, artifact=True)
                record_url = result_url(ids, result_version_id)
                record_label = 'Result details'
                title = 'Result evidence'
                identity = evidence['manifest']['watermark']['result_version_id']
        except ServiceError as error:
            return service_failure(self, request, error)
        except DatabaseError:
            return self.unavailable(request)

        data = base64.b64decode(evidence['content_base64'], validate=True)
        if request.query_params.get('download') == '1':
            response = HttpResponse(data, content_type='application/octet-stream')
            response['Content-Disposition'] = f'attachment; filename="{identity}.bin"'
            response['X-Content-Type-Options'] = 'nosniff'
            return response

        try:
            preview = data.decode('utf-8')
        except UnicodeDecodeError:
            preview = None
        if preview and any(not (char.isprintable() or char in '\t\r\n') for char in preview):
            preview = None
        return TemplateResponse(request._request, 'rms/run_evidence.html', {
            'title': title, 'identity': identity, 'record_label': record_label, 'record_url': record_url,
            'manifest': evidence['manifest'], 'preview': preview,
        })


class RunActionPage(RunWorkflowPage):
    def render_action(self, request, scope, action, form, status=200, save_error=None):
        return TemplateResponse(request._request, 'rms/run_workflow_action.html',
                                {'scope': scope, 'action': action, 'form': form, 'save_error': save_error}, status=status)

    def handle_action(self, request, plan_id, version_id, run_id, operation, *, submit):
        self._require_editor(request)
        if operation not in OPERATIONS:
            return self._not_found(request)
        label, form_type, write = OPERATIONS[operation]
        try:
            keys, run, _, head, ids, scope = self.context(request, plan_id, version_id, run_id)
        except ServiceError as error:
            return service_failure(self, request, error)
        except DatabaseError:
            return self.unavailable(request)
        if not submit and operation not in advertised_actions(run):
            return self._not_found(request)
        head_id = head['result_version_id'] if head else None
        form_data = request.data if submit else None
        options = {'event_id': run['current_event_id']}
        if operation == 'result':
            options.update(criteria=run['criteria'], result_id=head_id)
            expected_head = form_data.get('expected_result_version_id') if submit else head_id
            if expected_head:
                label = 'Correct a synthetic result'
        form = form_type(form_data, **options)
        if operation in ('event', 'reconcile') and not submit:
            states = run['allowed_event_states' if operation == 'event' else 'allowed_reconciliation_states']
            form.fields['state'].choices = [('', 'Choose a state'), *((state, state.capitalize()) for state in states)]
        action = {'label': label, 'url': action_url(ids, operation), 'return_url': scope['attempt_url'],
                  'return_label': 'Back to exact Run attempt', 'submit_label': label}
        if not submit:
            return self.render_action(request, scope, action, form)
        if not form.is_valid():
            return self.render_action(request, scope, action, form, status=400)
        try:
            saved = write(**keys, idempotency_key=form.cleaned_data['idempotency_key'], payload=form.payload())
        except TestPlanValidationError as error:
            for issue in error.issues:
                field = form.error_field(issue['path'])
                form.add_error(field if field in form.fields else None, issue['message'])
            return self.render_action(request, scope, action, form, status=400)
        except ResourceNotFound:
            return self._not_found(request)
        except ServiceError as error:
            status = getattr(error, 'http_status', 409)
            if status in (401, 403, 404):
                return service_failure(self, request, error)
            detail = error.safe_message
            if status == 409:
                detail += ' Your values are retained. Return to the attempt and check its current history before starting a new form.'
            return self.render_action(request, scope, action, form, status=status, save_error=detail)
        except DatabaseError:
            return self.render_action(request, scope, action, form, status=503,
                                      save_error='Save could not be confirmed. Retry this exact submission without changing it.')
        row = json.loads(saved.body)
        target = scope['attempt_url']
        if operation == 'result':
            target = result_url(ids, row['result_version_id'])
        elif operation == 'retry':
            target = workflow_scope(plan_id, version_id, row['run_id'])['attempt_url']
        return HttpResponseRedirect(target)

    @method_decorator(ensure_csrf_cookie)
    def get(self, request, plan_id, version_id, run_id, operation):
        return self.handle_action(request, plan_id, version_id, run_id, operation, submit=False)

    @method_decorator(csrf_protect)
    def post(self, request, plan_id, version_id, run_id, operation):
        return self.handle_action(request, plan_id, version_id, run_id, operation, submit=True)
