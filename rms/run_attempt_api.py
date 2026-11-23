"""JSON adapter for exact-version synthetic registration."""
from rest_framework.response import Response

from .run_api import RunsApi
from .run_attempt_services import list_attempts, register_attempt
from .test_plan_services import _error


class RunAttemptApi(RunsApi):
    def get(self, request, plan_id, version_id):
        if set(request.query_params) - {'offset'} or len(request.query_params.getlist('offset')) > 1:
            _error('', 'unknown_field')
        return Response(list_attempts(actor=request.user, plan_id=plan_id, version_id=version_id,
                                      offset=request.query_params.get('offset', '0')))

    def post(self, request, plan_id, version_id):
        return self.mutate(request, register_attempt, plan_id=plan_id, version_id=version_id)
