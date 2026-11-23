"""JSON adapters for authorized exact-version synthetic run observations."""

from django.http import HttpResponse
from django.urls import path
from django.utils.cache import patch_vary_headers
from rest_framework.response import Response

from . import run_result_services as services
from .hypothesis_api import ResearchRecordView
from .test_plan_api import StrictJSONParser
from .test_plan_services import _error


class RunResultApi(ResearchRecordView):
    parser_classes = [StrictJSONParser]
    action = None

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response['Cache-Control'] = 'private, no-store'
        patch_vary_headers(response, ('Authorization', 'Cookie'))
        return response

    def get(self, request, **context):
        allowed = {'offset'} if self.action == 'results' else set()
        if set(request.query_params) - allowed or len(request.query_params.getlist('offset')) > 1:
            _error('', 'unknown_field')
        context['actor'] = request.user
        if self.action == 'run':
            return Response(services.read_run(**context))
        if self.action == 'events':
            run = services.read_run(**context)
            return Response({key: run[key] for key in ('run_id', 'state', 'current_event_id', 'events')})
        if self.action == 'event_evidence':
            return Response(services.read_event_evidence(**context))
        if self.action == 'results':
            return Response(services.list_results(**context, offset=request.query_params.get('offset', '0')))
        if self.action in ('result', 'artifact'):
            return Response(services.read_result(**context, artifact=self.action == 'artifact'))
        self.http_method_not_allowed(request)

    def post(self, request, **context):
        operation = {'events': services.append_event, 'reconcile': services.reconcile_event, 'retry': services.retry_run,
                     'results': services.publish_result}.get(self.action)
        if operation is None:
            self.http_method_not_allowed(request)
        if request.query_params:
            _error('', 'unknown_field')
        stored = operation(actor=request.user, **context, idempotency_key=request.headers.get('Idempotency-Key'),
                           payload=request.data)
        return HttpResponse(stored.body, status=stored.status, content_type='application/json; charset=utf-8')


RUN = 'test-plans/<str:plan_id>/versions/<str:version_id>/runs/<str:run_id>'
RESULT = RUN + '/results/<str:result_version_id>'
urlpatterns = [
    path(RUN, RunResultApi.as_view(action='run'), name='run-detail-api'),
    path(RUN + '/events', RunResultApi.as_view(action='events'), name='run-events-api'),
    path(RUN + '/events/<str:event_id>/evidence', RunResultApi.as_view(action='event_evidence'), name='run-event-evidence-api'),
    path(RUN + '/reconciliations', RunResultApi.as_view(action='reconcile'), name='run-reconciliation-api'),
    path(RUN + '/retry', RunResultApi.as_view(action='retry'), name='run-retry-api'),
    path(RUN + '/results', RunResultApi.as_view(action='results'), name='run-results-api'),
    path(RESULT, RunResultApi.as_view(action='result'), name='run-result-version-api'),
    path(RESULT + '/artifact', RunResultApi.as_view(action='artifact'), name='run-result-artifact-api'),
]
