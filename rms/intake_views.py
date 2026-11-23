"""Small browser and JSON adapters for exact synthetic intake."""

from uuid import uuid4

from django import forms
from django.db import DatabaseError
from django.http import HttpResponse, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.cache import patch_vary_headers
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework.response import Response

from .hypothesis_api import ResearchRecordView
from .hypothesis_validation import HypothesisValidationError
from .intake_services import CLOSURE, PRIORITY, SOURCE_ASSESSMENT, form_context, hypothesis_draft_ready, read_intake, save_intake
from .services import ResourceNotFound, ServiceError
from .views import RmsPage


class IntakeAPI(ResearchRecordView):
    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "private, no-store"
        patch_vary_headers(response, ("Authorization", "Cookie"))
        return response

    def get(self, request, idea_id):
        return Response(read_intake(actor=request.user, idea_id=idea_id))

    def post(self, request, idea_id):
        stored = save_intake(actor=request.user, idea_id=idea_id, payload=request.data,
                             idempotency_key=request.headers.get("Idempotency-Key"))
        return HttpResponse(stored.body, status=stored.status, content_type="application/json")


class IntakeForm(forms.Form):
    idea_version_id = forms.CharField(max_length=41, widget=forms.HiddenInput)
    expected_latest_version = forms.IntegerField(min_value=0, widget=forms.HiddenInput)
    idempotency_key = forms.CharField(max_length=128, widget=forms.HiddenInput)
    family_version_id = forms.CharField(label="Exact family version ID", max_length=42)
    distinctness = forms.ChoiceField(choices=[("candidate", "Candidate (no distinctness approval)"), ("related_variant", "Related variant — same family")])
    family_rationale = forms.CharField(max_length=2000, widget=forms.Textarea(attrs={"rows": 2}))
    correction_reason = forms.CharField(max_length=2000, required=False)

    def __init__(self, *, contributions, outcome, **kwargs):
        super().__init__(**kwargs)
        self.contributions = contributions
        self.outcome = outcome
        if outcome == "ready":
            self.fields["investigation_version_id"] = forms.CharField(label="Exact case version ID", max_length=42)
            for key in PRIORITY:
                self.add_text("priority_" + key, "Priority: " + key.replace("_", " "))
            for contribution in contributions:
                for key in SOURCE_ASSESSMENT:
                    self.add_text(f"{contribution['id']}_{key}", f"Source {contribution['source']}: {key.replace('_', ' ')}")
        else:
            for key in CLOSURE:
                self.add_text("closure_" + key, key.replace("_", " ").capitalize())

    def add_text(self, key, label):
        self.fields[key] = forms.CharField(label=label, max_length=2000, widget=forms.Textarea(attrs={"rows": 2}))

    def payload(self):
        values = self.cleaned_data
        result = {key: values[key] for key in ("idea_version_id", "expected_latest_version", "family_version_id", "distinctness", "family_rationale")}
        result["outcome"] = self.outcome
        if values["correction_reason"]:
            result["correction_reason"] = values["correction_reason"]
        if self.outcome == "ready":
            result["investigation_version_id"] = values["investigation_version_id"]
            result["priority"] = {key: values["priority_" + key] for key in PRIORITY}
            result["source_assessments"] = {c["id"]: {key: values[f"{c['id']}_{key}"] for key in SOURCE_ASSESSMENT} for c in self.contributions}
        else:
            result["closure"] = {key: values["closure_" + key] for key in CLOSURE}
        return result


@method_decorator(csrf_protect, name="dispatch")
class IntakePage(RmsPage):
    def get(self, request, idea_id):
        self._require_reader(request)
        return self.show(request, idea_id)

    def post(self, request, idea_id):
        self._require_editor(request)
        return self.show(request, idea_id, data=request.data)

    def show(self, request, idea_id, data=None):
        try:
            history = read_intake(actor=request.user, idea_id=idea_id)
            outcome = "early_closed" if request.query_params.get("outcome") == "early_closed" else "ready"
            context = {"idea_id": idea_id, "history": history, "outcome": outcome}
            status = 200
            inputs = form_context(actor=request.user, idea_id=idea_id)
            if inputs:
                latest = history["results"][-1] if history["results"] else None
                if latest and latest["state"] == "ready":
                    context["can_draft"] = hypothesis_draft_ready(
                        actor=request.user, version_id=latest["version_id"], idea_version_id=latest["idea"]["version_id"],
                        case_version_id=latest["investigation"]["version_id"],
                        family_binding_version_id=latest["family_binding"]["version_id"],
                    )
                initial = {"idea_version_id": inputs["idea_version_id"], "expected_latest_version": history["latest_version"], "idempotency_key": str(uuid4())}
                form = IntakeForm(contributions=inputs["contributions"], outcome=outcome, initial=initial, data=data)
                context.update(form=form, can_assess=bool(inputs["contributions"]), exact_idea_version_id=inputs["idea_version_id"])
                if data is not None:
                    status = 400
                    if form.is_valid():
                        try:
                            save_intake(actor=request.user, idea_id=idea_id, payload=form.payload(), idempotency_key=form.cleaned_data["idempotency_key"])
                        except HypothesisValidationError as error:
                            for issue in error.issues:
                                form.add_error(None, f"{issue['path']}: {issue['code'].replace('_', ' ')}")
                        except ResourceNotFound:
                            raise
                        except ServiceError as error:
                            form.add_error(None, error.safe_message)
                            status = getattr(error, "http_status", 409)
                        else:
                            return HttpResponseRedirect(reverse("rms-intake", kwargs={"idea_id": idea_id}))
            elif data is not None:
                return TemplateResponse(request._request, "rms/denied.html", status=403)
            return TemplateResponse(request._request, "rms/intake.html", context, status=status)
        except ResourceNotFound:
            return self._not_found(request)
        except DatabaseError:
            return TemplateResponse(request._request, "rms/service_unavailable.html", status=503)
