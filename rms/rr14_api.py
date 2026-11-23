"""Exact synthetic saved-origin transport for MAU-169."""

from rest_framework.response import Response

from .hypothesis_api import ResearchRecordView
from .permissions import IsRmsReader
from .rr14_projection import read_saved_origins
from .test_plan_services import _error


class RR14OriginsView(ResearchRecordView):
    permission_classes = [IsRmsReader]
    http_method_names = ['get', 'head', 'options']

    def get(self, request, plan_id, version_id):
        if request.query_params:
            _error('', 'unknown_field')
        return Response(read_saved_origins(actor=request.user, plan_id=plan_id, plan_version_id=version_id))
