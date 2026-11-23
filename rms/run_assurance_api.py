"""Thin, private JSON routes for exact-result assurance records."""

from django.urls import path
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from . import run_assurance_services as services
from .permissions import IsRmsReader
from .run_result_api import RESULT, RunResultApi
from .test_plan_services import _error


class RunAssuranceApi(RunResultApi):
    permission_classes = [IsAuthenticated, IsRmsReader]

    def get(self, request, *, kind=None, record_id=None, **context):
        allowed = {'offset'} if kind and record_id is None else set()
        if set(request.query_params) - allowed or len(request.query_params.getlist('offset')) > 1:
            _error('', 'unknown_field')
        context['actor'] = request.user
        if kind is None:
            return Response(services.read_assurance(**context))
        if record_id is not None:
            return Response(services.read_assurance_record(**context, kind=kind, record_id=record_id))
        return Response(services.list_assurance(**context, kind=kind, offset=request.query_params.get('offset', '0')))

    def post(self, request, *, kind=None, record_id=None, **context):
        operations = {'reviews': services.publish_review, 'decisions': services.record_decision,
                      'lessons': services.record_lesson}
        if kind not in operations or record_id is not None:
            self.http_method_not_allowed(request)
        return self.mutate(request, operations[kind], **context)


urlpatterns = [path(RESULT + '/assurance', RunAssuranceApi.as_view(), name='run-assurance-api')]
for kind in ('reviews', 'decisions', 'lessons'):
    urlpatterns.extend((
        path(RESULT + f'/{kind}', RunAssuranceApi.as_view(), {'kind': kind}, name=f'run-{kind}-api'),
        path(RESULT + f'/{kind}/<str:record_id>', RunAssuranceApi.as_view(), {'kind': kind}, name=f'run-{kind}-record-api'),
    ))
