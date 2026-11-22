from django.urls import path

from .run_workflow_views import RunActionPage, RunDetailPage, RunResultPage


RUN = 'test-plans/<str:plan_id>/versions/<str:version_id>/runs/<str:run_id>'
urlpatterns = [
    path(RUN, RunDetailPage.as_view(), name='rms-run-detail'),
    path(RUN + '/results/<str:result_version_id>', RunResultPage.as_view(), name='rms-run-result-detail'),
    path(RUN + '/record/<str:operation>', RunActionPage.as_view(), name='rms-run-action'),
]
