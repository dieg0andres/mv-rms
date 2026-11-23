"""JSON adapter for exact-version synthetic registration."""
from django.http import HttpResponse
from django.utils.cache import patch_vary_headers
from rest_framework.response import Response

from .hypothesis_api import ResearchRecordView
from .run_attempt_services import list_attempts, register_attempt
from .test_plan_api import StrictJSONParser
from .test_plan_services import _error


class RunAttemptApi(ResearchRecordView):
    parser_classes = [StrictJSONParser]

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response['Cache-Control'] = 'private, no-store'
        patch_vary_headers(response, ('Authorization', 'Cookie'))
        return response

    def get(self, request, plan_id, version_id):
        if set(request.query_params) - {'offset'} or len(request.query_params.getlist('offset')) > 1:
            _error('', 'unknown_field')
        return Response(list_attempts(actor=request.user, plan_id=plan_id, version_id=version_id,
                                      offset=request.query_params.get('offset', '0')))

    def post(self, request, plan_id, version_id):
        if request.query_params:
            _error('', 'unknown_field')
        stored = register_attempt(actor=request.user, plan_id=plan_id, version_id=version_id,
                                  idempotency_key=request.headers.get('Idempotency-Key'), payload=request.data)
        return HttpResponse(stored.body, status=stored.status, content_type='application/json; charset=utf-8')
