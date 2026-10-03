"""Thin DRF adapters; browser submissions use the same persistence services."""

import uuid

from django.http import HttpResponse
from rest_framework import exceptions
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView

from . import hypothesis_services as hypotheses
from . import research_context_services as context
from .hypothesis_validation import HypothesisValidationError, validate_request
from .permissions import IsEditor
from .services import ResourceNotFound, ServiceError


RESOURCES = {
    "hypotheses": (hypotheses.create_hypothesis, hypotheses.correct_hypothesis, hypotheses.get_hypothesis,
                   hypotheses.list_hypotheses, hypotheses.get_hypothesis_history, "hypothesis_id"),
    "research-families": (context.create_research_family, context.correct_research_family, context.get_research_family,
                          context.list_research_families, context.get_research_family_history, "family_id"),
    "investigations": (context.create_investigation, context.correct_investigation, context.get_investigation,
                       context.list_investigations, context.get_investigation_history, "investigation_id"),
}


def error_response(code, message, status, fields=None):
    error = {"code": code, "message": message, "request_id": uuid.uuid4().hex}
    if fields is not None:
        error["fields"] = list(fields)
    return Response({"error": error}, status=status)


def query_payload(query):
    result = {}
    issues = []
    for key in query:
        values = query.getlist(key)
        value = values[0]
        if len(values) != 1:
            issues.append({"path": "/" + key, "code": "duplicate_field", "message": "Supply this query field once."})
        if key in ("page", "page_size"):
            try:
                canonical = value.isascii() and value.isdecimal() and str(int(value)) == value
            except ValueError:
                canonical = False
            if not canonical:
                issues.append({"path": "/" + key, "code": "invalid_type", "message": "Supply a positive integer."})
            else:
                value = int(value)
        result[key] = value
    if issues:
        raise HypothesisValidationError(issues)
    return result


class ResearchRecordView(APIView):
    permission_classes = [IsAuthenticated, IsEditor]
    # DRF matches the parsed media type, including normal charset parameters.
    # JSON alone is permitted; malformed JSON still takes the safe 400 path.
    parser_classes = [JSONParser]
    resource = None
    action = "collection"

    def handle_exception(self, exc):
        if isinstance(exc, HypothesisValidationError):
            return error_response("validation_error", "The request is invalid.", 400, exc.issues)
        if isinstance(exc, ServiceError):
            return error_response(exc.code, exc.safe_message, getattr(exc, "http_status", 404 if isinstance(exc, ResourceNotFound) else 409))
        if isinstance(exc, (exceptions.NotAuthenticated, exceptions.AuthenticationFailed)):
            response = error_response("authentication_required", "Authentication is required.", 401)
            challenge = self.get_authenticate_header(self.request)
            if challenge:
                response["WWW-Authenticate"] = challenge
            return response
        if isinstance(exc, exceptions.PermissionDenied):
            return error_response("forbidden", "This operation is not permitted.", 403)
        if isinstance(exc, (exceptions.ParseError, exceptions.UnsupportedMediaType)):
            return error_response("validation_error", "The request is invalid.", 400)
        if isinstance(exc, exceptions.MethodNotAllowed):
            return error_response("method_not_allowed", "Method not allowed.", 405)
        raise exc

    def get(self, request, record_id=None, version=None):
        if self.action != "collection" and request.query_params:
            raise HypothesisValidationError([{"path": "", "code": "unknown_field", "message": "This read route accepts no query fields."}])
        if self.resource == "prior-research-assessments":
            return Response(context.get_prior_research_assessment(actor=request.user, assessment_id=record_id, version=version))
        if self.action == "correction":
            raise exceptions.MethodNotAllowed("GET")
        if self.resource == "idea-family-associations":
            if self.action == "collection":
                query = validate_request("IdeaFamilyQuery", query_payload(request.query_params))
                return Response(context.get_idea_family_for_idea(actor=request.user, idea_version_id=query["idea_version_id"]))
            if self.action == "history":
                return Response(context.get_idea_family_association_history(actor=request.user, association_id=record_id))
            return Response(context.get_idea_family_association(actor=request.user, association_id=record_id, version=version))
        _, _, detail, listing, history, identity_key = RESOURCES[self.resource]
        if self.action == "collection":
            return Response(listing(actor=request.user, query=query_payload(request.query_params)))
        kwargs = {"actor": request.user, identity_key: record_id}
        if self.action == "history":
            return Response(history(**kwargs))
        return Response(detail(**kwargs, version=version))

    def post(self, request, record_id=None, version=None):
        if self.action not in ("collection", "correction"):
            raise exceptions.MethodNotAllowed("POST")
        if self.resource == "idea-family-associations" and self.action != "correction":
            raise exceptions.MethodNotAllowed("POST")
        kwargs = {"actor": request.user, "idempotency_key": request.headers.get("Idempotency-Key"), "payload": request.data}
        if self.resource == "idea-family-associations":
            stored = context.correct_idea_family_association(**kwargs, association_id=record_id)
        else:
            create, correct, _, _, _, identity_key = RESOURCES[self.resource]
            stored = create(**kwargs) if self.action == "collection" else correct(**kwargs, **{identity_key: record_id})
        return HttpResponse(stored.body, status=stored.status, content_type="application/json; charset=utf-8")
