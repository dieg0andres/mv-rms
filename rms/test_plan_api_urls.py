from django.urls import path
from .test_plan_api import TestPlanView

urlpatterns=[
    path('test-plans',TestPlanView.as_view(action='collection'),name='test-plan-list'),
    path('test-plans/<str:plan_id>',TestPlanView.as_view(action='detail'),name='test-plan-detail'),
    path('test-plans/<str:plan_id>/versions',TestPlanView.as_view(action='history'),name='test-plan-history'),
    path('test-plans/<str:plan_id>/versions/<str:version_id>',TestPlanView.as_view(action='version'),name='test-plan-version'),
    path('test-plans/<str:plan_id>/corrections',TestPlanView.as_view(action='correction'),name='test-plan-correction'),
    path('criterion-profiles/versions/<str:version_id>',TestPlanView.as_view(action='criterion'),name='criterion-version'),
    path('data-requirements/versions/<str:version_id>',TestPlanView.as_view(action='requirement'),name='data-requirement-version'),
    path('test-plans/<str:plan_id>/data-checks',TestPlanView.as_view(action='checks'),name='test-plan-data-checks'),
    path('test-plans/<str:plan_id>/data-checks/<str:check_id>',TestPlanView.as_view(action='check'),name='test-plan-data-check'),
]
