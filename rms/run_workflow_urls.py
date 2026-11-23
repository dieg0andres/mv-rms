from django.urls import path

from .run_assurance_views import RunAssuranceActionPage, RunAssurancePage
from .run_workflow_views import RunActionPage, RunDetailPage, RunResultPage


RUN = 'test-plans/<str:plan_id>/versions/<str:version_id>/runs/<str:run_id>'
RESULT = RUN + '/results/<str:result_version_id>'
ASSURANCE = RESULT + '/assurance'
urlpatterns = [
    path(RUN, RunDetailPage.as_view(), name='rms-run-detail'),
    path(RESULT, RunResultPage.as_view(), name='rms-run-result-detail'),
    path(RUN + '/record/<str:operation>', RunActionPage.as_view(), name='rms-run-action'),
    path(ASSURANCE, RunAssurancePage.as_view(), name='rms-run-assurance'),
    path(ASSURANCE + '/record/<str:operation>', RunAssuranceActionPage.as_view(), name='rms-run-assurance-action'),
    path(ASSURANCE + '/<str:kind>', RunAssurancePage.as_view(), name='rms-run-assurance-history'),
    path(ASSURANCE + '/<str:kind>/<str:record_id>', RunAssurancePage.as_view(), name='rms-run-assurance-record'),
]
