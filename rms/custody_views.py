"""Authenticated, private adapters for synthetic custody."""

from uuid import uuid4

from django import forms
from django.http import HttpResponse, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework.parsers import FormParser

from .custody_services import OPERATIONS, custody_access, download_export, read_custody, record_custody
from .hypothesis_validation import HypothesisValidationError
from .navigation_views import service_failure
from .research_context_common import Forbidden
from .services import ResourceNotFound, ServiceError
from .views import RmsPage


def may_access(actor, plan_id, *, write=False):
    try:
        custody_access(actor, plan_id, write=write)
    except (ResourceNotFound, Forbidden):
        return False
    return True


class CustodyForm(forms.Form):
    operation = forms.ChoiceField(choices=[(action, action.capitalize()) for action in (*OPERATIONS, 'reconcile')])
    expected_sequence = forms.IntegerField(min_value=0, max_value=4, widget=forms.HiddenInput)
    key = forms.CharField(max_length=128, widget=forms.HiddenInput)


@method_decorator(csrf_protect, name='dispatch')
class CustodyPage(RmsPage):
    parser_classes = [FormParser]

    def get(self, request, **ids):
        return self.show(request, ids)

    def post(self, request, **ids):
        return self.show(request, ids, data=request.data)

    def show(self, request, ids, data=None):
        self._require_reader(request)
        actor = request.user
        if data is not None:
            try:
                custody_access(actor, ids['plan_id'], write=True)
            except ServiceError as error:
                return service_failure(self, request, error)
        try:
            history = read_custody(actor=actor, **ids)
        except ServiceError as error:
            return service_failure(self, request, error)
        sequence = history[-1]['sequence'] if history else 0
        writer = may_access(actor, ids['plan_id'], write=True)
        form, status = None, 200
        if data is not None or (writer and sequence <= 4 and not (history and history[-1]['state'] == 'quarantined')):
            form = CustodyForm(data, initial={'expected_sequence': sequence, 'key': str(uuid4())})
        if data is not None:
            status = 400
            if form.is_valid():
                payload = {field: form.cleaned_data[field] for field in ('operation', 'expected_sequence')}
                try:
                    record_custody(actor=actor, idempotency_key=form.cleaned_data['key'], payload=payload, **ids)
                except (ResourceNotFound, Forbidden) as error:
                    return service_failure(self, request, error)
                except (HypothesisValidationError, ServiceError) as error:
                    status = getattr(error, 'http_status', 400)
                    form.add_error(None, 'The command was denied. Check the exact fixture binding and refresh the history.')
                else:
                    return HttpResponseRedirect(request.path)
        return TemplateResponse(request._request, 'rms/custody.html', {
            'history': history, 'form': form, 'result_url': reverse('rms-run-result-detail', kwargs=ids),
            'export_url': reverse('rms-custody-export', kwargs=ids) if writer and history and
            history[-1]['operation'] == 'export' else None,
        }, status=status)


class CustodyExportPage(RmsPage):
    def get(self, request, **ids):
        self._require_reader(request)
        try:
            content = download_export(actor=request.user, **ids)
        except HypothesisValidationError:
            return self._not_found(request)
        except ServiceError as error:
            return service_failure(self, request, error)
        return HttpResponse(content, content_type='application/json', headers={
            'Content-Disposition': 'attachment; filename="synthetic-custody-export.json"',
            'X-Content-Type-Options': 'nosniff',
        })
