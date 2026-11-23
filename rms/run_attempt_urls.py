from django.urls import path

from .run_attempt_api import RunAttemptApi
from .run_attempt_views import RunAttemptPage

VERSION_RUNS = 'test-plans/<str:plan_id>/versions/<str:version_id>/runs'
urlpatterns = [
    path('api/v1/' + VERSION_RUNS, RunAttemptApi.as_view(), name='run-attempts-api'),
    path(VERSION_RUNS, RunAttemptPage.as_view(), name='rms-run-attempts'),
]
