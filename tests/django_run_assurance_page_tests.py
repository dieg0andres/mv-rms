"""Exact-result HTML contracts through the project URLconf, with mocked services."""
import json
import re
from unittest.mock import Mock, patch
from urllib.parse import urlencode

from django.conf import settings
from django.test import SimpleTestCase
from django.urls import reverse
from rest_framework.test import APIClient

from rms.research_context_common import Forbidden, StaleVersion
from rms.run_assurance_services import AssuranceConflict
from rms.run_assurance_views import WRITERS
from rms.services import ResourceNotFound, StoredResponse
from tests.django_run_attempt_registration_tests import PLAN, VERSION, actor
from tests.django_run_frontend_page_tests import RUN


RESULT = 'RESV-00000000-0000-4000-8000-000000000005'
REVIEW = 'REV-00000000-0000-4000-8000-000000000006'
DECISION = 'DEC-00000000-0000-4000-8000-000000000007'
LESSON = 'LES-00000000-0000-4000-8000-000000000008'
PREVIOUS = 'REV-00000000-0000-4000-8000-000000000009'
NEW_RESULT = 'RESV-00000000-0000-4000-8000-000000000010'
IDS = (PLAN, VERSION, RUN, RESULT)
MANIFEST = 'f' * 64
CONTEXT = {'result_head_id': RESULT, 'review_head_id': REVIEW, 'decision_head_id': DECISION,
           'lesson_head_id': None, 'artifact_manifest_digest': MANIFEST}
REVIEW_ROW = {'review_id': REVIEW, 'supersedes_review_id': PREVIOUS, 'current': False,
              'impact': {'decisions': [DECISION]}, 'outcome': 'fail', 'rationale': '<fixture review>',
              'limitations': 'Invented limitation', 'result_digest': 'a' * 64, 'artifact_manifest_digest': MANIFEST,
              'row_digest': 'b' * 64, 'actor_id': '2', 'recorded_by': 'invented-reviewer',
              'recorded_at': '2026-11-22T18:00:00Z', 'correction_reason': 'Invented correction'}


class AssurancePages(SimpleTestCase):
    def browser(self, role):
        client = APIClient(enforce_csrf_checks=True)
        client.force_authenticate(user=actor(role))
        return client

    def hidden(self, page, name):
        field = re.search(rf'name="{name}" value="([^"]+)"', page.content.decode())
        self.assertIsNotNone(field, name)
        return field[1]

    def submit(self, client, url, fields):
        return client.post(url, urlencode(fields), content_type='application/x-www-form-urlencoded',
                           secure=True, headers={'origin': 'https://testserver'})

    def action(self, operation):
        return reverse('rms-run-assurance-action', args=[*IDS, operation])

    @patch('rms.run_assurance_views.services.read_assurance')
    def test_overview_filters_links_by_exact_capability_not_editor_role(self, read):
        url = reverse('rms-run-assurance', args=IDS)
        labels = {'review': 'Publish review', 'decision': 'Record disposition', 'lesson': 'Record lesson'}
        for role, capability in (('founder_viewer', None), ('editor', None), ('editor', 'review'),
                                 ('editor', 'decision'), ('editor', 'lesson')):
            with self.subTest(role=role, capability=capability):
                read.return_value = {**CONTEXT, 'review_head_id': None, 'decision_head_id': None,
                                     **({'available_actions': [capability]} if capability else {})}
                client = self.browser(role)
                page = client.get(url)
                self.assertContains(page, RESULT)
                self.assertEqual(page['Cache-Control'], 'private, no-store')
                for operation in WRITERS:
                    link = self.action(operation)
                    if capability == operation:
                        self.assertContains(page, f'<a href="{link}">{labels[operation]}</a>', html=True)
                    else:
                        self.assertNotContains(page, link)
        read.reset_mock()
        denied = self.browser('outsider').get(url)
        self.assertNotContains(denied, RESULT, status_code=403)
        read.assert_not_called()

    @patch('rms.run_assurance_views.services.list_assurance', return_value={'records': [REVIEW_ROW], 'next_offset': '50'})
    @patch('rms.run_assurance_views.services.read_assurance_record', return_value=REVIEW_ROW)
    def test_history_links_keep_the_exact_result_and_escape_narrative(self, read, listing):
        client = self.browser('founder_viewer')
        history = reverse('rms-run-assurance-history', args=[*IDS, 'reviews'])
        detail = reverse('rms-run-assurance-record', args=[*IDS, 'reviews', REVIEW])
        self.assertContains(client.get(history), f'href="{detail}"')
        self.assertContains(client.get(history), '?offset=50')
        page = client.get(detail)
        self.assertContains(page, 'Historical — not available for new reliance')
        self.assertContains(page, '&lt;fixture review&gt;')
        self.assertContains(page, f'href="{history}/{PREVIOUS}"')
        decision = reverse('rms-run-assurance-record', args=[*IDS, 'decisions', DECISION])
        self.assertContains(page, f'href="{decision}"')
        self.assertEqual(read.call_args.kwargs['result_version_id'], RESULT)
        read.side_effect = ResourceNotFound
        self.assertNotContains(client.get(detail), REVIEW, status_code=404)

    @patch('rms.run_assurance_views.services.read_assurance')
    def test_each_form_get_sets_csrf_cookie_and_post_binds_exact_references(self, read):
        labels = {'review': 'Correct review', 'decision': 'Correct disposition', 'lesson': 'Record lesson'}
        cases = (
            ('review', REVIEW, {'outcome': 'fail', 'rationale': 'Invented failure', 'limitations': 'Invented limit'},
             {'expected_review_id': REVIEW, 'artifact_manifest_digest': MANIFEST}),
            ('decision', DECISION, {'disposition': 'close_rejected', 'rationale': 'Invented rejection'},
             {'expected_decision_id': DECISION, 'review_id': REVIEW}),
            ('lesson', LESSON, {'claim': 'Invented claim', 'limitations': 'Invented limit', 'uncertainty': 'Invented uncertainty',
                                'applicability': 'Invented applicability', 'implication': 'Invented implication'},
             {'expected_lesson_id': None, 'review_id': REVIEW, 'decision_id': DECISION}),
        )
        for operation, record_id, values, references in cases:
            with self.subTest(operation=operation):
                editor = actor('editor')
                client = self.browser('editor')
                client.force_authenticate(user=editor)
                read.return_value = {**CONTEXT, 'available_actions': [operation]}
                url = self.action(operation)
                self.assertNotIn(settings.CSRF_COOKIE_NAME, client.cookies)
                page = client.get(url)
                self.assertContains(page, RESULT)
                self.assertContains(page, f'<button type="submit">{labels[operation]}</button>', html=True)
                self.assertIn(settings.CSRF_COOKIE_NAME, page.cookies)
                key = self.hidden(page, 'idempotency_key')
                token = self.hidden(page, 'csrfmiddlewaretoken')
                fields = {**values, **{name: value or '' for name, value in references.items()}, 'idempotency_key': key}
                for name, value in references.items():
                    if value:
                        self.assertEqual(self.hidden(page, name), value)
                correction = 'Invented correction' if references[f'expected_{operation}_id'] else None
                if correction:
                    fields['correction_reason'] = correction
                writer = Mock(return_value=StoredResponse(201, json.dumps({f'{operation}_id': record_id}).encode()))
                bad_token = ('A' if token[0] != 'A' else 'B') + token[1:]
                with patch.dict(WRITERS, {operation: writer}):
                    read.reset_mock()
                    self.assertEqual(self.submit(client, url, fields).status_code, 403)
                    self.assertEqual(self.submit(client, url, {**fields, 'csrfmiddlewaretoken': bad_token}).status_code, 403)
                    read.assert_not_called()
                    writer.assert_not_called()
                    valid = {**fields, 'csrfmiddlewaretoken': token}
                    read.return_value = {**CONTEXT, 'available_actions': []}
                    writer.side_effect = Forbidden
                    client.force_authenticate(user=actor('founder_viewer'))
                    self.assertNotContains(self.submit(client, url, valid), RESULT, status_code=403)
                    client.force_authenticate(user=editor)
                    self.assertNotContains(self.submit(client, url, valid), RESULT, status_code=403)
                    self.assertEqual(writer.call_count, 2)
                    writer.reset_mock(side_effect=True)
                    read.return_value = {**CONTEXT, 'available_actions': [operation]}
                    saved = self.submit(client, url, valid)
                    target = reverse('rms-run-assurance-record', args=[*IDS, f'{operation}s', record_id])
                    self.assertRedirects(saved, target, fetch_redirect_response=False)
                    writer.assert_called_once_with(actor=editor, plan_id=PLAN, version_id=VERSION, run_id=RUN,
                                                   result_version_id=RESULT, idempotency_key=key,
                                                   payload={**references, **values, 'correction_reason': correction})

    @patch('rms.run_assurance_views.services.read_assurance', return_value={**CONTEXT, 'available_actions': ['review']})
    def test_conflict_keeps_submitted_head_key_and_values(self, read):
        client = self.browser('editor')
        url = self.action('review')
        page = client.get(url)
        key = self.hidden(page, 'idempotency_key')
        token = self.hidden(page, 'csrfmiddlewaretoken')
        fields = {'idempotency_key': key, 'csrfmiddlewaretoken': token, 'expected_review_id': REVIEW,
                  'artifact_manifest_digest': MANIFEST, 'outcome': 'fail', 'rationale': '<invented rationale>',
                  'limitations': 'Invented limit', 'correction_reason': 'Invented correction'}
        for view in ({**CONTEXT, 'review_head_id': PREVIOUS, 'available_actions': ['review']},
                     {**CONTEXT, 'result_head_id': NEW_RESULT, 'available_actions': []}):
            with self.subTest(view=view):
                read.return_value = view
                writer = Mock(side_effect=StaleVersion)
                with patch.dict(WRITERS, review=writer):
                    stale = self.submit(client, url, fields)
                self.assertContains(stale, 'tabindex="-1" data-run-error-summary', status_code=409)
                self.assertContains(stale, '&lt;invented rationale&gt;', status_code=409)
                self.assertContains(stale, 'Check the exact history', status_code=409)
                self.assertNotContains(stale, f'<form method="post" action="{url}"', status_code=409)
                self.assertEqual(self.hidden(stale, 'idempotency_key'), key)
                self.assertEqual(self.hidden(stale, 'expected_review_id'), REVIEW)
                self.assertEqual(self.hidden(stale, 'artifact_manifest_digest'), MANIFEST)
                writer.assert_called_once()
                self.assertEqual(writer.call_args.kwargs['result_version_id'], RESULT)
                self.assertEqual(writer.call_args.kwargs['payload']['expected_review_id'], REVIEW)
        history = reverse('rms-run-assurance', args=IDS)
        self.assertContains(stale, f'href="{history}"', status_code=409)
        self.assertNotContains(client.get(history), url)
        record = reverse('rms-run-assurance-record', args=[*IDS, 'reviews', REVIEW])
        with patch('rms.run_assurance_views.services.read_assurance_record', return_value=REVIEW_ROW):
            self.assertContains(client.get(record), 'Historical — not available for new reliance')

    @patch('rms.run_assurance_views.services.read_assurance', return_value={**CONTEXT, 'available_actions': ['decision']})
    def test_lost_review_reliance_leaves_bound_disposition_visible(self, read):
        client = self.browser('editor')
        url = self.action('decision')
        page = client.get(url)
        read.return_value = {**CONTEXT, 'review_head_id': PREVIOUS, 'available_actions': []}
        writer = Mock(side_effect=AssuranceConflict)
        with patch.dict(WRITERS, decision=writer):
            stale = self.submit(client, url, {
                'csrfmiddlewaretoken': self.hidden(page, 'csrfmiddlewaretoken'),
                'idempotency_key': self.hidden(page, 'idempotency_key'), 'expected_decision_id': DECISION,
                'review_id': REVIEW, 'disposition': 'close_rejected', 'rationale': 'Invented disposition',
                'correction_reason': 'Invented correction',
            })
        self.assertContains(stale, 'Invented disposition', status_code=409)
        self.assertEqual(self.hidden(stale, 'review_id'), REVIEW)
        writer.assert_called_once()
