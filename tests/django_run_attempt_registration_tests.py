"""Database-free request and form checks for synthetic registration."""
from base64 import b64encode
import re
from types import SimpleNamespace
from unittest.mock import Mock, patch
from urllib.parse import urlencode

from django.test import RequestFactory, SimpleTestCase
from django.urls import resolve, reverse
from rest_framework.test import APIClient, APIRequestFactory, force_authenticate

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
AUTHORIZATION = 'Basic ' + b64encode(b'invented-editor:invented-only').decode('ascii')
ORIGIN = 'https://testserver'


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

    @patch('rms.run_attempt_api.register_attempt', return_value=StoredResponse(201, b'{"classification":"synthetic"}'))
    @patch('rest_framework.authentication.authenticate')
    def test_conventional_basic_json_client(self, authenticate, register):
        editor = actor('editor')
        authenticate.return_value = editor
        client = APIClient(enforce_csrf_checks=True)
        response = client.post(self.api_url, PAYLOAD, format='json', HTTP_AUTHORIZATION=AUTHORIZATION,
                               HTTP_IDEMPOTENCY_KEY='example-1')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response['Cache-Control'], 'private, no-store')
        authenticate.assert_called_once()
        register.assert_called_once_with(actor=editor, plan_id=PLAN, version_id=VERSION,
                                         payload=PAYLOAD, idempotency_key='example-1')

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


class RunApiCsrfTests(SimpleTestCase):
    def setUp(self):
        self.editor = actor('editor')
        self.client = APIClient(enforce_csrf_checks=True, HTTP_AUTHORIZATION=AUTHORIZATION)
        self.browser_url = reverse('rms-run-attempts', args=[PLAN, VERSION])
        self.api_url = reverse('run-attempts-api', args=[PLAN, VERSION])
        self.enterContext(patch('rest_framework.authentication.authenticate', return_value=self.editor))
        self.enterContext(patch('rms.run_attempt_views.list_attempts', return_value=LISTING))

    def page_token(self):
        page = self.client.get(self.browser_url, secure=True)
        self.assertEqual(page.status_code, 200)
        self.assertIn('csrftoken', page.cookies)
        return re.search(r'name="csrfmiddlewaretoken" value="([^"]+)"', page.content.decode())[1]

    def post(self, *, url=None, key='example-1', **headers):
        return self.client.post(url or self.api_url, PAYLOAD, format='json', secure=True,
                                HTTP_IDEMPOTENCY_KEY=key, **headers)

    def assert_private(self, response):
        self.assertEqual(response['Cache-Control'], 'private, no-store')
        self.assertTrue({'Authorization', 'Cookie'} <= set(response['Vary'].split(', ')))

    def assert_csrf_denied(self, response):
        self.assertEqual((response.status_code, response.content), (403, b''))
        self.assertNotIn('WWW-Authenticate', response.headers)
        self.assert_private(response)

    @patch('rms.run_attempt_api.register_attempt')
    def test_browser_denials_never_write_or_replay_and_valid_retry_is_unchanged(self, register):
        token = self.page_token()
        attempts, receipts = [], {}

        def register_or_replay(*, payload, idempotency_key, **context):
            if idempotency_key not in receipts:
                attempts.append(payload['external_reference'])
                receipts[idempotency_key] = StoredResponse(201, b'{"registration_status":"registered"}')
            return receipts[idempotency_key]

        register.side_effect = register_or_replay
        headers = {'HTTP_ORIGIN': ORIGIN, 'HTTP_SEC_FETCH_SITE': 'same-origin'}
        accepted = self.post(**headers, HTTP_X_CSRFTOKEN=token)
        self.assertEqual(accepted.status_code, 201)
        self.assert_private(accepted)
        snapshot = (list(attempts), dict(receipts))
        wrong_token = ('B' if token[0] == 'A' else 'A') + token[1:]
        for key in ('example-1', 'unused-key'):
            with self.subTest(key=key):
                self.assert_csrf_denied(self.post(key=key, **headers))
                self.assert_csrf_denied(self.post(key=key, **headers, HTTP_X_CSRFTOKEN=wrong_token))
        self.assert_csrf_denied(self.post(HTTP_ORIGIN='https://different.invalid', HTTP_X_CSRFTOKEN=token))
        self.assert_csrf_denied(self.post(HTTP_X_CSRFTOKEN=token))
        register.assert_called_once_with(actor=self.editor, plan_id=PLAN, version_id=VERSION,
                                         payload=PAYLOAD, idempotency_key='example-1')
        self.assertEqual((attempts, receipts), snapshot)
        replay = self.post(HTTP_REFERER=ORIGIN + self.browser_url, HTTP_X_CSRFTOKEN=token)
        self.assertEqual((replay.status_code, replay.content), (201, accepted.content))
        self.assert_private(replay)
        self.assertEqual((attempts, receipts), snapshot)

    @patch('rms.run_attempt_api.register_attempt')
    def test_browser_indicators_work_without_an_existing_cookie(self, register):
        for headers in ({'HTTP_ORIGIN': ORIGIN}, {'HTTP_SEC_FETCH_SITE': 'same-origin'},
                        {'HTTP_REFERER': ORIGIN + self.browser_url}):
            with self.subTest(headers=tuple(headers)):
                self.assert_csrf_denied(self.post(**headers))
        register.assert_not_called()

    @patch('rms.run_attempt_api.register_attempt')
    def test_anonymous_still_gets_basic_challenge(self, register):
        self.client.defaults.pop('HTTP_AUTHORIZATION')
        denied = self.post(HTTP_ORIGIN=ORIGIN)
        self.assertEqual(denied.status_code, 401)
        self.assertTrue(denied['WWW-Authenticate'].startswith('Basic '))
        self.assert_private(denied)
        register.assert_not_called()

    @patch('rms.run_attempt_api.register_attempt')
    def test_scope_and_validation_keep_existing_statuses(self, register):
        token = self.page_token()
        headers = {'HTTP_ORIGIN': ORIGIN, 'HTTP_X_CSRFTOKEN': token}
        register.side_effect = ResourceNotFound
        scoped = self.post(**headers)
        self.assertEqual(scoped.status_code, 404)
        self.assert_private(scoped)
        invalid = self.client.post(self.api_url, '{', content_type='application/json', secure=True,
                                   HTTP_IDEMPOTENCY_KEY='example-1', **headers)
        self.assertEqual(invalid.status_code, 400)
        self.assert_private(invalid)
        register.assert_called_once()

    @patch('rms.run_attempt_views.register_attempt')
    def test_existing_browser_form_keeps_csrf_and_redirect(self, register):
        token = self.page_token()
        form = {**PAYLOAD, 'idempotency_key': 'form-example'}

        def submit(fields):
            return self.client.post(self.browser_url, urlencode({**form, **fields}),
                                    content_type='application/x-www-form-urlencoded', secure=True, HTTP_ORIGIN=ORIGIN)

        for fields in ({}, {'csrfmiddlewaretoken': 'invalid'}):
            denied = submit(fields)
            self.assertEqual(denied.status_code, 403)
            self.assert_private(denied)
        register.assert_not_called()
        accepted = submit({'csrfmiddlewaretoken': token})
        self.assertEqual(accepted.status_code, 302)
        self.assertEqual(accepted['Location'], self.browser_url)
        self.assert_private(accepted)
        register.assert_called_once_with(actor=self.editor, plan_id=PLAN, version_id=VERSION,
                                         payload=PAYLOAD, idempotency_key='form-example')

    def test_other_runs_write_adapters_share_the_boundary(self):
        token = self.page_token()
        run = f'{self.api_url}/RUN-invented'
        assurance = f'{run}/results/RES-invented'
        operations = {
            **{f'{run}/{suffix}': 'rms.run_result_services.' + name for suffix, name in (
                ('events', 'append_event'), ('reconciliations', 'reconcile_event'),
                ('retry', 'retry_run'), ('results', 'publish_result'),
            )},
            **{f'{assurance}/{suffix}': 'rms.run_assurance_services.' + name for suffix, name in (
                ('reviews', 'publish_review'), ('decisions', 'record_decision'), ('lessons', 'record_lesson'),
            )},
        }
        for url, operation in operations.items():
            with self.subTest(operation=operation), patch(operation, return_value=StoredResponse(201, b'{}')) as service:
                self.assert_csrf_denied(self.post(url=url, HTTP_ORIGIN=ORIGIN))
                service.assert_not_called()
                self.assertEqual(self.post(url=url, HTTP_ORIGIN=ORIGIN, HTTP_X_CSRFTOKEN=token).status_code, 201)
                service.assert_called_once()

    @patch('rms.run_attempt_api.list_attempts', return_value=LISTING)
    def test_safe_and_unsupported_methods_keep_existing_statuses(self, listing):
        self.page_token()
        for method in ('get', 'head', 'options', 'put', 'patch', 'delete'):
            with self.subTest(method=method):
                response = getattr(self.client, method)(self.api_url, secure=True, HTTP_ORIGIN=ORIGIN)
                self.assertEqual(response.status_code, 200 if method in ('get', 'head', 'options') else 405)
                self.assert_private(response)
