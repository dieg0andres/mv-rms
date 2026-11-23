"""Database-free request and form checks for synthetic registration."""
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import RequestFactory, SimpleTestCase
from django.urls import resolve, reverse
from rest_framework.test import APIRequestFactory, force_authenticate

from rms.run_attempt_services import _registration_fields
from rms.services import ResourceNotFound, StoredResponse
from rms.test_plan_validation import TestPlanValidationError


PLAN = 'TPL-00000000-0000-4000-8000-000000000001'
VERSION = 'TPLV-00000000-0000-4000-8000-000000000002'
PAYLOAD = {
    'configuration_key': 'baseline', 'external_reference': 'synthetic:example-1',
    'code_commit': 'a' * 40, 'code_manifest_digest': 'b' * 64,
    'dependency_lock_digest': 'c' * 64, 'dataset_manifest_digest': 'd' * 64,
    'parameter_digest': 'e' * 64, 'environment_digest': 'f' * 64,
}
LISTING = {
    'plan_id': PLAN, 'plan_version_id': VERSION,
    'configurations': [{'key': 'baseline', 'digest': PAYLOAD['parameter_digest']}],
    'runs': [], 'previous_offset': None, 'next_offset': None,
}


def actor(role):
    groups = Mock()
    groups.filter.side_effect = lambda **query: SimpleNamespace(
        exists=lambda: role in query.get('name__in', [query.get('name')]))
    return SimpleNamespace(pk=1, is_authenticated=True, is_active=True, groups=groups)


def dispatch(path, request, user):
    force_authenticate(request, user=user)
    route = resolve(path)
    response = route.func(request, **route.kwargs)
    if hasattr(response, 'render'):
        response.render()
    return response


class RunRegistrationTests(SimpleTestCase):
    def setUp(self):
        self.browser_url = reverse('rms-run-attempts', args=[PLAN, VERSION])
        self.api_url = reverse('run-attempts-api', args=[PLAN, VERSION])

    def test_strict_synthetic_shape(self):
        self.assertEqual(_registration_fields(PAYLOAD), PAYLOAD)
        for extra in ({'classification': 'real'}, {'external_reference': 'https://example.invalid'},
                      {'parameter_digest': 'not-a-digest'}, {'code_commit': 'master'}):
            with self.subTest(extra=extra), self.assertRaises(TestPlanValidationError):
                _registration_fields({**PAYLOAD, **extra})

    @patch('rms.run_attempt_api.register_attempt', return_value=StoredResponse(201, b'{"classification":"synthetic"}'))
    def test_exact_path_and_editor_api_registration(self, register):
        editor = actor('editor')
        request = APIRequestFactory().post(self.api_url, PAYLOAD, format='json', HTTP_IDEMPOTENCY_KEY='example-1')
        response = dispatch(self.api_url, request, editor)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response['Cache-Control'], 'private, no-store')
        register.assert_called_once_with(actor=editor, plan_id=PLAN, version_id=VERSION,
                                         payload=PAYLOAD, idempotency_key='example-1')

    @patch('rms.run_attempt_api.register_attempt')
    @patch('rms.run_attempt_api.list_attempts')
    def test_deny_viewer_write_and_outsider_lookup_before_service(self, listing, register):
        factory = APIRequestFactory()
        self.assertEqual(dispatch(self.api_url, factory.post(self.api_url, PAYLOAD, format='json'),
                                  actor('founder_viewer')).status_code, 403)
        self.assertEqual(dispatch(self.api_url, factory.get(self.api_url), actor('outsider')).status_code, 403)
        register.assert_not_called()
        listing.assert_not_called()

    @patch('rms.run_attempt_api.list_attempts', side_effect=ResourceNotFound)
    def test_invisible_exact_version_returns_404(self, listing):
        response = dispatch(self.api_url, APIRequestFactory().get(self.api_url), actor('founder_viewer'))
        self.assertEqual(response.status_code, 404)

    @patch('rms.run_attempt_views.list_attempts', return_value=LISTING)
    def test_browser_shows_csrf_form_only_to_editor(self, listing):
        factory = RequestFactory()
        editor = dispatch(self.browser_url, factory.get(self.browser_url), actor('editor'))
        viewer = dispatch(self.browser_url, factory.get(self.browser_url), actor('founder_viewer'))
        self.assertContains(editor, 'Register synthetic attempt')
        self.assertContains(editor, 'csrfmiddlewaretoken')
        self.assertIn('csrftoken', editor.cookies)
        self.assertContains(viewer, VERSION)
        self.assertNotContains(viewer, 'Register synthetic attempt')

    @patch('rms.run_attempt_views.register_attempt')
    @patch('rms.run_attempt_views.list_attempts', return_value=LISTING)
    def test_browser_write_requires_csrf(self, listing, register):
        request = RequestFactory().post(self.browser_url, {**PAYLOAD, 'idempotency_key': 'example-1'})
        response = dispatch(self.browser_url, request, actor('editor'))
        self.assertEqual(response.status_code, 403)
        register.assert_not_called()
