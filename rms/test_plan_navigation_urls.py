"""Director registers these browser routes in the project URLconf."""
from django.urls import path
from .test_plan_views import (TestPlanEditorPage, TestPlanListPage, TestPlanDetailPage,
    TestPlanHistoryPage, DataCheckEditorPage, DataCheckListPage)

urlpatterns = [
    path('test-plans', TestPlanListPage.as_view(), name='rms-test-plan-list'),
    path('test-plans/new', TestPlanEditorPage.as_view(), name='rms-test-plan-create'),
    path('test-plans/<str:plan_id>/revise', TestPlanEditorPage.as_view(), name='rms-test-plan-revise'),
    path('test-plans/<str:plan_id>/history', TestPlanHistoryPage.as_view(), name='rms-test-plan-history'),
    path('test-plans/<str:plan_id>/versions/<str:version_id>', TestPlanDetailPage.as_view(), name='rms-test-plan-version'),
    path('test-plans/<str:plan_id>/data-checks', DataCheckListPage.as_view(), name='rms-test-plan-checks'),
    path('test-plans/<str:plan_id>/data-checks/new', DataCheckEditorPage.as_view(), name='rms-test-plan-check-create'),
    path('test-plans/<str:plan_id>/data-checks/<str:check_id>', DataCheckListPage.as_view(), name='rms-test-plan-check-detail'),
    path('test-plans/<str:plan_id>', TestPlanDetailPage.as_view(), name='rms-test-plan-detail'),
]
