"""Server-rendered adapter for the exact-result synthetic assurance services."""
import json
from uuid import uuid4

from django import forms
from django.db import DatabaseError
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser

from . import run_assurance_services as services
from .navigation_views import service_failure
from .run_assurance_models import DISPOSITIONS, REVIEW_OUTCOMES
from .run_assurance_serializers import FIELDS, RELIANCE
from .run_result_services import ResultIntegrityError
from .run_workflow_forms import narrative
from .run_workflow_views import result_url, workflow_scope
from .services import ResourceNotFound, ServiceError
from .test_plan_validation import TestPlanValidationError
from .views import RmsPage


LABELS = {'review': 'Independent review', 'decision': 'Synthetic disposition', 'lesson': 'Synthetic lesson'}
ACTION_LABELS = {'review': ('Publish review', 'Correct review'),
                 'decision': ('Record disposition', 'Correct disposition'),
                 'lesson': ('Record lesson', 'Correct lesson')}
CHOICES = {'pass': 'Pass — synthetic evidence assessment only', 'fail': 'Fail', 'inconclusive': 'Inconclusive',
           'invalid': 'Invalid', 'close_rejected': 'Close as rejected', 'return_for_revision': 'Return for revision'}
WRITERS = {'review': services.publish_review, 'decision': services.record_decision, 'lesson': services.record_lesson}


class AssuranceForm(forms.Form):
    idempotency_key = forms.CharField(max_length=128, widget=forms.HiddenInput)

    def __init__(self, operation, data=None, *, context=None):
        expected = f'expected_{operation}_id'
        reference_fields = {expected: f'{operation}_head_id',
                            **{f'{item}_id': f'{item}_head_id' for item in RELIANCE[operation]}}
        if operation == 'review':
            reference_fields['artifact_manifest_digest'] = 'artifact_manifest_digest'
        initial = ({name: context[source] for name, source in reference_fields.items()} |
                   {'idempotency_key': str(uuid4())}) if context is not None else None
        super().__init__(data, initial=initial)
        for field in reference_fields:
            self.fields[field] = forms.CharField(required=field != expected, max_length=64, widget=forms.HiddenInput)
        if self[expected].value():
            self.fields['correction_reason'] = narrative('Reason for correcting the preceding record')
        for field in FIELDS[operation]:
            choices = {'outcome': REVIEW_OUTCOMES, 'disposition': DISPOSITIONS}.get(field)
            self.fields[field] = (forms.ChoiceField(label=field.capitalize(), choices=[('', 'Choose an option'), *(
                (choice, CHOICES[choice]) for choice in choices
            )]) if choices else narrative(field.capitalize()))
        self.references = [(name.replace('_', ' ').capitalize(), self[name].value()) for name in reference_fields
                           if self[name].value()]

    def payload(self):
        return {'correction_reason': None, **{name: value or None for name, value in self.cleaned_data.items()
                                               if name != 'idempotency_key'}}


class RunAssurancePage(RmsPage):
    parser_classes = [FormParser]

    def scope(self, keys):
        ids = (keys['plan_id'], keys['version_id'], keys['run_id'])
        result_id = keys['result_version_id']
        return {**workflow_scope(*ids), 'result_id': result_id, 'result_url': result_url(ids, result_id),
                'assurance_url': reverse('rms-run-assurance', args=[*ids, result_id])}

    def url(self, route, keys, *args):
        return reverse(f'rms-run-assurance-{route}', args=[keys['plan_id'], keys['version_id'], keys['run_id'],
                                                          keys['result_version_id'], *args])

    def render(self, request, handler, **kwargs):
        self._require_reader(request)
        try:
            return handler(request, **kwargs)
        except TestPlanValidationError:
            return TemplateResponse(request._request, 'rms/unavailable.html', status=400)
        except ServiceError as error:
            return service_failure(self, request, error)
        except DatabaseError:
            return TemplateResponse(request._request, 'rms/service_unavailable.html', status=503)

    def page(self, request, keys, **context):
        return TemplateResponse(request._request, 'rms/run_assurance.html', {'scope': self.scope(keys), **context})

    def get(self, request, *, kind=None, record_id=None, **ids):
        return self.render(request, self.read, kind=kind, record_id=record_id, actor=request.user, **ids)

    def read(self, request, *, kind, record_id, **keys):
        if kind is None:
            assurance = services.read_assurance(**keys)
            available = assurance.get('available_actions') or ()
            groups = []
            for operation, label in LABELS.items():
                groups.append({'label': label, 'history_url': self.url('history', keys, f'{operation}s'),
                               'action_url': self.url('action', keys, operation) if operation in available else None,
                               'action_label': ACTION_LABELS[operation][bool(assurance[f'{operation}_head_id'])]})
            return self.page(request, keys, title='Exact-result synthetic assurance', groups=groups,
                             historical=assurance['result_head_id'] != keys['result_version_id'])
        operation = kind.removesuffix('s')
        if operation not in LABELS or kind != f'{operation}s':
            raise ResourceNotFound
        label = LABELS[operation]
        if record_id is None:
            offset = request.query_params.get('offset', '0')
            listing = services.list_assurance(**keys, kind=kind, offset=offset)
            rows = [{**row, 'id': row[f'{operation}_id'],
                     'url': self.url('record', keys, kind, row[f'{operation}_id'])} for row in listing['records']]
            return self.page(request, keys, title=f'{label} history', rows=rows, listing=True,
                             next_offset=listing['next_offset'], previous_offset=max(0, int(offset) - 50) if int(offset) else None)
        row = services.read_assurance_record(**keys, kind=kind, record_id=record_id)
        links = []
        related = [('Preceding record', kind, row.get(f'supersedes_{operation}_id')),
                   ('Successor record', kind, row.get('superseded_by_id'))]
        related.extend((LABELS[item], f'{item}s', row[f'{item}_id']) for item in RELIANCE[operation])
        for group, records in row.get('impact', {}).items():
            if group in ('decisions', 'lessons'):
                related.extend(('Downstream record', group, identity) for identity in records)
        for caption, category, identity in related:
            if identity:
                links.append({'label': caption, 'id': identity, 'url': self.url('record', keys, category, identity)})
        values = [(field.capitalize(), CHOICES.get(row[field], row[field])) for field in FIELDS[operation]]
        return self.page(request, keys, title=label, record=row, record_id=record_id, values=values, links=links,
                         history_url=self.url('history', keys, kind))


class RunAssuranceActionPage(RunAssurancePage):
    @method_decorator(ensure_csrf_cookie)
    def get(self, request, *, operation, **ids):
        return self.render(request, self.action, operation=operation, submit=False, actor=request.user, **ids)

    @method_decorator(csrf_protect)
    def post(self, request, *, operation, **ids):
        return self.render(request, self.action, operation=operation, submit=True, actor=request.user, **ids)

    def action(self, request, *, operation, submit, **keys):
        if operation not in WRITERS:
            raise ResourceNotFound
        if submit:
            form = AssuranceForm(operation, request.data)
        else:
            assurance = services.read_assurance(**keys)
            if operation not in (assurance.get('available_actions') or ()):
                raise ResourceNotFound
            form = AssuranceForm(operation, context=assurance)
        scope = self.scope(keys)
        label = ACTION_LABELS[operation][bool(form[f'expected_{operation}_id'].value())]
        action = {'label': label, 'submit_label': label, 'url': self.url('action', keys, operation),
                  'return_url': scope['assurance_url'], 'return_label': 'Back to exact-result assurance'}

        def render_form(status=200, save_error=None):
            return TemplateResponse(request._request, 'rms/run_workflow_action.html',
                                    {'scope': scope, 'action': action, 'form': form,
                                     'references': form.references, 'save_error': save_error,
                                     'refresh_required': status == 409}, status=status)

        def validation_failure():
            if operation not in (services.read_assurance(**keys).get('available_actions') or ()):
                raise PermissionDenied
            return render_form(400)

        if not submit:
            return render_form()
        if not form.is_valid():
            return validation_failure()
        try:
            saved = WRITERS[operation](**keys, idempotency_key=form.cleaned_data['idempotency_key'], payload=form.payload())
        except TestPlanValidationError as error:
            for issue in error.issues:
                field = issue['path'].strip('/')
                form.add_error(field if field in form.fields else None, issue['message'])
            return validation_failure()
        except (ResourceNotFound, ResultIntegrityError):
            raise
        except ServiceError as error:
            if getattr(error, 'http_status', 409) != 409:
                raise
            return render_form(409, f'{error.safe_message} Your values are retained. Check the exact history before starting a new form.')
        except DatabaseError:
            return render_form(503, 'Save could not be confirmed. Retry this exact submission without changing it.')
        record = json.loads(saved.body)
        return HttpResponseRedirect(self.url('record', keys, f'{operation}s', record[f'{operation}_id']))
