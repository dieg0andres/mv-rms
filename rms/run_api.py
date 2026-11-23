"""Shared HTTP boundary for Runs JSON adapters."""

from django.http import HttpResponse, HttpResponseForbidden
from django.utils.cache import patch_vary_headers
from rest_framework.authentication import CSRFCheck

from .hypothesis_api import ResearchRecordView
from .test_plan_api import StrictJSONParser
from .test_plan_services import _error


class RunsApi(ResearchRecordView):
    parser_classes = [StrictJSONParser]

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response['Cache-Control'] = 'private, no-store'
        patch_vary_headers(response, ('Authorization', 'Cookie'))
        return response

    def mutate(self, request, operation, **context):
        """Gate browser POSTs before parsing JSON or invoking the receipt-aware service."""
        http_request = request._request
        headers = http_request.META
        if (headers.get('HTTP_COOKIE') or 'HTTP_ORIGIN' in headers or 'HTTP_REFERER' in headers
                or any(name.startswith('HTTP_SEC_FETCH_') for name in headers)):
            check = CSRFCheck(lambda unused_request: None)
            check.process_request(http_request)
            if check.process_view(http_request, None, (), {}):
                return HttpResponseForbidden()

        if request.query_params:
            _error('', 'unknown_field')
        stored = operation(actor=request.user, **context, idempotency_key=request.headers.get('Idempotency-Key'),
                           payload=request.data)
        return HttpResponse(stored.body, status=stored.status, content_type='application/json; charset=utf-8')
