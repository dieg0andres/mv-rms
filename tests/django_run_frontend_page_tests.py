"""Browser request contracts with invented service responses and no database."""
from urllib.parse import urlencode
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings
from django.urls import include, path, reverse
from rest_framework.test import APIRequestFactory

from rms.research_context_common import StaleVersion
from rms.run_workflow_forms import ResultForm
from rms.services import ResourceNotFound
from tests.django_run_attempt_registration_tests import LISTING, PLAN, VERSION, actor, dispatch


urlpatterns = [
    path('', include('rms.run_attempt_urls')),
    path('', include('rms.run_workflow_urls')),
    path('', include('rms.test_plan_navigation_urls')),
]
RUN = 'RUN-00000000-0000-4000-8000-000000000003'
EVENT = 'RUE-00000000-0000-4000-8000-000000000004'
RUN_CONTEXT = {'run_id': RUN, 'plan_version_id': VERSION, 'state': 'registered', 'current_event_id': None,
               'available_actions': ['event'], 'allowed_event_states': ['failed'], 'events': [], 'criteria': []}
EMPTY_RESULTS = {'results': [], 'next_offset': None}


class RunEntryRouteTests(SimpleTestCase):
    @patch('rms.test_plan_views.plan_service')
    @patch('rms.run_workflow_views.services.list_results', return_value=EMPTY_RESULTS)
    @patch('rms.run_workflow_views.services.read_run')
    @patch('rms.run_attempt_views.list_attempts')
    def test_exact_plan_runs_detail_round_trip_in_project_urlconf(self, list_attempts, read_run, results, read_plan):
        older_version = 'TPLV-00000000-0000-4000-8000-000000000001'
        older_run = 'RUN-00000000-0000-4000-8000-000000000005'
        versions = ((1, older_version, older_run), (2, VERSION, RUN))
        factory = APIRequestFactory()
        for role in ('editor', 'founder_viewer'):
            for number, version_id, run_id in versions:
                with self.subTest(role=role, version=number):
                    viewer = actor(role)
                    example = f'synthetic:attempt-{number}'
                    run = {**RUN_CONTEXT, 'run_id': run_id, 'plan_version_id': version_id,
                           'external_reference': example, 'configuration_key': 'baseline'}
                    list_attempts.return_value = {**LISTING, 'plan_version_id': version_id, 'runs': [run]}
                    read_run.return_value = run
                    read_plan.return_value = {'plan_id': PLAN, 'plan_version_id': version_id, 'version': number,
                                              'fields': {'title': 'Invented plan'}, 'classification': 'synthetic',
                                              'criteria': [], 'data_requirements': []}
                    plan_path = f'/test-plans/{PLAN}/versions/{version_id}'
                    runs_path = f'{plan_path}/runs'
                    run_path = f'{runs_path}/{run_id}'
                    listing = dispatch(runs_path, factory.get(runs_path), viewer)
                    self.assertContains(listing, f'<a href="{run_path}">{example}</a>', html=True)
                    if role == 'founder_viewer':
                        self.assertNotContains(listing, 'Register synthetic attempt')
                    detail = dispatch(run_path, factory.get(run_path), viewer)
                    self.assertContains(detail, f'<a href="{plan_path}">Exact Test Plan definition</a>', html=True)
                    self.assertContains(detail, f'<code>{version_id}</code>', html=True)
                    self.assertContains(detail, f'<code>{run_id}</code>', html=True)
                    if role == 'founder_viewer':
                        self.assertNotContains(detail, 'run-actions-heading')
                    plan = dispatch(plan_path, factory.get(plan_path), viewer)
                    self.assertContains(plan, f'<a href="{runs_path}">Runs and Results for this exact version</a>', html=True)
                    self.assertContains(plan, f'<code>{version_id}</code>', html=True)
                    list_attempts.assert_called_with(actor=viewer, plan_id=PLAN, version_id=version_id, offset='0')
                    read_run.assert_called_with(actor=viewer, plan_id=PLAN, version_id=version_id, run_id=run_id)
                    results.assert_called_with(actor=viewer, plan_id=PLAN, version_id=version_id, run_id=run_id)
                    read_plan.assert_called_with('read_test_plan_version', actor=viewer, plan_id=PLAN,
                                                 version_id=version_id)


@override_settings(ROOT_URLCONF=__name__)
class RunWorkflowPageTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.attempt = reverse('rms-run-detail', args=[PLAN, VERSION, RUN])
        self.event = reverse('rms-run-action', args=[PLAN, VERSION, RUN, 'event'])

    @patch('rms.run_workflow_views.services.list_results', return_value=EMPTY_RESULTS)
    @patch('rms.run_workflow_views.services.read_run', return_value=RUN_CONTEXT)
    def test_editor_affordance_and_founder_viewer_read_only(self, read, listing):
        founder = actor('founder_viewer')
        page = dispatch(self.attempt, self.factory.get(self.attempt), founder)
        self.assertContains(page, RUN)
        self.assertNotContains(page, 'Record an observed execution event')
        self.assertEqual(page['Cache-Control'], 'private, no-store')
        read.assert_called_once_with(actor=founder, plan_id=PLAN, version_id=VERSION, run_id=RUN)
        page = dispatch(self.attempt, self.factory.get(self.attempt), actor('editor'))
        self.assertContains(page, self.event)

    @patch('rms.run_workflow_views.services.list_results', return_value=EMPTY_RESULTS)
    @patch('rms.run_workflow_views.services.read_run', return_value=RUN_CONTEXT)
    def test_fresh_event_form_uses_only_service_advertised_states(self, read, listing):
        page = dispatch(self.event, self.factory.get(self.event), actor('editor'))
        self.assertContains(page, '<option value="failed">Failed</option>', html=True)
        for state in ('running', 'completed', 'cancelled'):
            self.assertNotContains(page, f'value="{state}"')

    @patch('rms.run_workflow_views.services.list_results', return_value=EMPTY_RESULTS)
    @patch('rms.run_workflow_views.services.read_run')
    def test_missing_actions_or_event_states_hide_controls_and_fresh_form(self, read, listing):
        editor = actor('editor')
        for capability in ('available_actions', 'allowed_event_states'):
            with self.subTest(capability=capability):
                read.return_value = {key: value for key, value in RUN_CONTEXT.items() if key != capability}
                detail = dispatch(self.attempt, self.factory.get(self.attempt), editor)
                self.assertNotContains(detail, 'run-actions-heading')
                self.assertNotContains(detail, self.event)
                form = dispatch(self.event, self.factory.get(self.event), editor)
                self.assertNotContains(form, 'Observed execution state', status_code=404)

    @patch('rms.run_workflow_views.services.read_run')
    def test_role_denials_precede_record_and_form_lookup(self, read):
        self.assertEqual(dispatch(self.event, self.factory.get(self.event), actor('founder_viewer')).status_code, 403)
        self.assertEqual(dispatch(self.event, self.factory.post(self.event), actor('founder_viewer')).status_code, 403)
        self.assertEqual(dispatch(self.attempt, self.factory.get(self.attempt), actor('outsider')).status_code, 403)
        read.assert_not_called()

    @patch('rms.run_workflow_views.services.read_run', side_effect=ResourceNotFound)
    def test_unknown_exact_version_scope_does_not_echo_ids(self, read):
        page = dispatch(self.attempt, self.factory.get(self.attempt), actor('founder_viewer'))
        self.assertNotContains(page, RUN, status_code=404)
        self.assertNotContains(page, VERSION, status_code=404)

    @patch('rms.run_workflow_views.services.read_run')
    def test_missing_csrf_is_rejected_before_record_lookup(self, read):
        strict = APIRequestFactory(enforce_csrf_checks=True)
        browser = strict.post(self.event, urlencode({'idempotency_key': 'invented'}),
                              content_type='application/x-www-form-urlencoded')
        self.assertEqual(dispatch(self.event, browser, actor('editor')).status_code, 403)
        read.assert_not_called()


    @patch('rms.run_workflow_views.services.list_results', return_value=EMPTY_RESULTS)
    @patch('rms.run_workflow_views.services.read_run', return_value={**RUN_CONTEXT, 'current_event_id': EVENT,
           'state': 'failed', 'available_actions': [], 'allowed_event_states': []})
    def test_stale_but_bound_form_keeps_original_head_key_and_input(self, read, listing):
        from rms.run_workflow_views import OPERATIONS

        operation = OPERATIONS['event']
        with patch.dict(OPERATIONS, event=(operation[0], operation[1], lambda **kwargs: self.raise_stale(**kwargs))):
            browser = self.factory.post(self.event, urlencode({'expected_event_id': '', 'idempotency_key': 'invented-key',
                'state': 'running', 'reason': '<fixture external report>'}), content_type='application/x-www-form-urlencoded')
            browser._dont_enforce_csrf_checks = True
            page = dispatch(self.event, browser, actor('editor'))
        self.assertContains(page, 'data-run-error-summary', status_code=409)
        self.assertContains(page, '&lt;fixture external report&gt;', status_code=409)
        self.assertContains(page, 'Back to exact Run attempt', status_code=409)
        self.assertContains(page, '<option value="running" selected>Running</option>', status_code=409, html=True)
        self.assertContains(page, 'value="invented-key"', status_code=409)
        self.assertNotContains(page, f'value="{EVENT}"', status_code=409)

    def raise_stale(self, **kwargs):
        self.assertIsNone(kwargs['payload']['expected_event_id'])
        self.assertEqual(kwargs['idempotency_key'], 'invented-key')
        raise StaleVersion

    def test_result_form_uses_exact_edges_and_preserves_zero_as_observation(self):
        criterion = {'criterion_version_id': 'CRIV-fixture', 'criterion_edge_id': 'TPAS-fixture',
                     'rule': {'name': 'Invented threshold', 'rule_type': 'numeric', 'operator': 'gte',
                              'threshold': '2', 'units': 'rows'}}
        form = ResultForm({'idempotency_key': 'invented-key', 'expected_event_id': EVENT,
            'summary': 'Invented result', '0_sample_satisfied': 'yes', '0_observed_value': '0',
            '0_explanation': 'Invented zero', 'artifact_text': 'invented\n', 'synthetic_confirmed': 'on'},
            criteria=[criterion])
        self.assertTrue(form.is_valid(), form.errors)
        payload = form.payload()
        self.assertEqual(payload['assessments'][0]['criterion_edge_id'], 'TPAS-fixture')
        self.assertEqual(payload['assessments'][0]['observed_value'], '0')
        self.assertEqual(payload['artifact']['content_base64'], 'aW52ZW50ZWQK')
        self.assertEqual(form.error_field('/assessments/0/observed_value'), '0_observed_value')
