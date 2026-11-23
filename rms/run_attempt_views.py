"""Browser adapter for reporting externally observed synthetic attempts."""
from uuid import uuid4

from django import forms
from django.db import DatabaseError
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from rest_framework.parsers import FormParser

from .navigation_views import service_failure
from .permissions import has_rms_write_access
from .run_attempt_services import FIELD_FORMATS, list_attempts, register_attempt
from .services import ResourceNotFound, ServiceError
from .test_plan_validation import TestPlanValidationError
from .views import RmsPage


class RegistrationForm(forms.Form):
    configuration_key = forms.ChoiceField(label='Exact baseline or variation')
    external_reference = forms.CharField(max_length=106, help_text='Invented label with the prefix synthetic:.')
    code_commit = forms.CharField(max_length=40, help_text='Full 40-character Git commit for the invented fixture.')
    code_manifest_digest = forms.CharField(max_length=64)
    dependency_lock_digest = forms.CharField(max_length=64)
    dataset_manifest_digest = forms.CharField(max_length=64)
    parameter_digest = forms.CharField(max_length=64, help_text='Reported digest must match the selected definition below.')
    environment_digest = forms.CharField(max_length=64)
    idempotency_key = forms.CharField(max_length=128, widget=forms.HiddenInput)

    def __init__(self, configurations, data=None):
        super().__init__(data, initial={'idempotency_key': str(uuid4())})
        self.fields['configuration_key'].choices = [('', 'Select a configuration')] + [
            (entry['key'], entry['key']) for entry in configurations
        ]


class RunAttemptPage(RmsPage):
    parser_classes = [FormParser]

    def _render(self, request, listing, form=None, status=200):
        return TemplateResponse(request._request, 'rms/run_attempts.html', {
            'listing': listing,
            'form': form,
            'plan_url': reverse('rms-test-plan-version', kwargs={
                'plan_id': listing['plan_id'], 'version_id': listing['plan_version_id'],
            }),
        }, status=status)

    @method_decorator(ensure_csrf_cookie)
    def get(self, request, plan_id, version_id):
        self._require_reader(request)
        try:
            listing = list_attempts(actor=request.user, plan_id=plan_id, version_id=version_id,
                                    offset=request.query_params.get('offset', '0'))
        except ResourceNotFound:
            return self._not_found(request)
        except ServiceError as error:
            return service_failure(self, request, error)
        except DatabaseError:
            return TemplateResponse(request._request, 'rms/service_unavailable.html', status=503)
        form = RegistrationForm(listing['configurations']) if has_rms_write_access(request.user) else None
        return self._render(request, listing, form)

    @method_decorator(csrf_protect)
    def post(self, request, plan_id, version_id):
        self._require_editor(request)
        try:
            listing = list_attempts(actor=request.user, plan_id=plan_id, version_id=version_id)
        except ResourceNotFound:
            return self._not_found(request)
        except DatabaseError:
            return TemplateResponse(request._request, 'rms/service_unavailable.html', status=503)
        form = RegistrationForm(listing['configurations'], request.data)
        if not form.is_valid():
            return self._render(request, listing, form, status=400)
        try:
            register_attempt(actor=request.user, plan_id=plan_id, version_id=version_id,
                             idempotency_key=form.cleaned_data['idempotency_key'],
                             payload={name: form.cleaned_data[name] for name in FIELD_FORMATS})
        except TestPlanValidationError as error:
            for issue in error.issues:
                field = issue['path'].lstrip('/')
                form.add_error(field if field in form.fields else None, issue['message'])
            return self._render(request, listing, form, status=400)
        except DatabaseError:
            form.add_error(None, 'Save could not be confirmed. Retry this exact submission without changing the fields.')
            return self._render(request, listing, form, status=503)
        except ServiceError as error:
            form.add_error(None, error.safe_message)
            return self._render(request, listing, form, status=getattr(error, 'http_status', 409))
        return HttpResponseRedirect(request.path)
