"""Authenticated adapters to the fixture-only stage gate service."""

from uuid import uuid4

from django import forms
from django.http import HttpResponse, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.utils.cache import patch_vary_headers
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework.response import Response

from .hypothesis_api import ResearchRecordView
from .hypothesis_validation import HypothesisValidationError
from .research_context_common import Forbidden
from .services import ResourceNotFound, ServiceError
from .stage_gate_services import can_write_gate, read_gate, record_gate
from .views import RmsPage


class StageGateAPI(ResearchRecordView):
    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "private, no-store"
        patch_vary_headers(response, ("Authorization", "Cookie"))
        return response

    def get(self, request, plan_id, version_id):
        return Response(read_gate(actor=request.user, plan_id=plan_id, version_id=version_id))

    def post(self, request, plan_id, version_id):
        result = record_gate(actor=request.user, plan_id=plan_id, version_id=version_id,
                             idempotency_key=request.headers.get("Idempotency-Key"), payload=request.data)
        return HttpResponse(result.body, status=result.status, content_type="application/json")


class StageGateForm(forms.Form):
    operation = forms.ChoiceField(choices=[("freeze", "Record synthetic freeze"), ("release", "Record synthetic release"),
                                          ("invalidate", "Invalidate a recorded event")])
    expected_sequence = forms.IntegerField(min_value=0, max_value=3, widget=forms.HiddenInput)
    idempotency_key = forms.CharField(max_length=128, widget=forms.HiddenInput)
    reference = forms.CharField(label="Invented authority reference", required=False, max_length=118)
    revision = forms.IntegerField(label="Invented authority revision", required=False, min_value=1)
    digest = forms.CharField(label="Invented decision SHA-256", required=False, max_length=64)
    reason = forms.CharField(label="Invented impact reason (invalidation only)", required=False, max_length=500)

    def command(self):
        values = self.cleaned_data
        payload = {key: values[key] for key in ("operation", "expected_sequence")}
        if values["operation"] == "invalidate":
            return payload | {"reason": values["reason"]}
        return payload | {"authority": {key: values[key] for key in ("reference", "revision", "digest")}}


@method_decorator(csrf_protect, name="dispatch")
class StageGatePage(RmsPage):
    def get(self, request, plan_id, version_id):
        return self.show(request, plan_id, version_id)

    def post(self, request, plan_id, version_id):
        return self.show(request, plan_id, version_id, request.data)

    def show(self, request, plan_id, version_id, data=None):
        self._require_reader(request)
        try:
            history = read_gate(actor=request.user, plan_id=plan_id, version_id=version_id)
        except ResourceNotFound:
            return self._not_found(request)
        form = None
        status = 200
        if can_write_gate(actor=request.user, plan_id=plan_id):
            if data is not None or history["recorded_state"] != "invalidated":
                form = StageGateForm(data, initial={"expected_sequence": history["sequence"], "idempotency_key": str(uuid4())})
            if data is not None:
                status = 400
                if form.is_valid():
                    try:
                        record_gate(actor=request.user, plan_id=plan_id, version_id=version_id,
                                    idempotency_key=form.cleaned_data["idempotency_key"], payload=form.command())
                    except ResourceNotFound:
                        return self._not_found(request)
                    except Forbidden:
                        return TemplateResponse(request._request, "rms/denied.html", status=403)
                    except HypothesisValidationError:
                        form.add_error(None, "Denied: the exact fixture binding, inputs, or transition is not valid.")
                    except ServiceError as error:
                        form.add_error(None, error.safe_message)
                        status = getattr(error, "http_status", 409)
                    else:
                        return HttpResponseRedirect(request.path)
        elif data is not None:
            return TemplateResponse(request._request, "rms/denied.html", status=403)
        return TemplateResponse(request._request, "rms/stage_gates.html", {"history": history, "form": form}, status=status)
