"""Engineering-only checks for invented assurance over disposable PostgreSQL."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth.models import Group, User
from django.db import DatabaseError, connection, connections, transaction
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils.timezone import now

from rms.models import IdempotencyRecord, RunDecision, RunLesson, RunResultVersion, RunReview
from rms.research_context_common import StaleVersion
from rms.run_assurance_policy import design_records, grant_key, provenance_key
from rms.run_assurance_services import publish_review
from tests.django_run_result_tests import Workflow


def principal(name, group='founder_viewer'):
    actor = User.objects.create_user(f'invented-assurance-{name}')
    if group:
        actor.groups.add(Group.objects.get_or_create(name=group)[0])
    return actor


class AssuranceWorkflow(Workflow):
    def setup_assurance(self, suffix, *, attempt=None):
        if attempt is None:
            self.setup_workflow(suffix)
        self.run = attempt or self.register()
        self.completed = self.complete(self.run)
        self.result_base = f'{self.root}/{self.run}/results'
        first = self.post(self.result_base, 'result-1', self.result_payload(self.run, self.completed)).json()
        self.result = RunResultVersion.objects.get(public_id=first['result_version_id'])
        self.scope = dict(plan_id=self.plan['plan_id'], version_id=self.plan['plan_version_id'],
                          run_id=self.run, result_version_id=self.result.public_id)
        self.url = f'{self.result_base}/{self.result.public_id}'
        self.reviewer = principal(f'{suffix}-reviewer', 'editor')
        self.decider = principal(f'{suffix}-decider', 'editor')
        self.lesson_author = principal(f'{suffix}-lesson', 'editor')
        self.bindings = {provenance_key(record): str(self.editor.pk) for record in design_records(self.result)}
        self.expires_at = now() + timedelta(hours=1)
        self.grants = {}
        self.grant(self.reviewer, 'review')
        self.grant(self.decider, 'decision')
        self.grant(self.lesson_author, 'lesson')

    def grant(self, actor, action, *, result=None):
        self.grants[grant_key(actor, result or self.result, action)] = self.expires_at

    def counts(self):
        return tuple(model.objects.count() for model in (RunReview, RunDecision, RunLesson, IdempotencyRecord))

    def configured(self):
        return override_settings(RMS_SYNTHETIC_ASSURANCE_GRANTS=self.grants,
                                 RMS_SYNTHETIC_ASSURANCE_PROVENANCE=self.bindings)

    def as_actor(self, actor):
        self.client.force_authenticate(actor)

    def publish(self, kind, key, payload, status=201):
        return self.post(f'{self.url}/{kind}', key, payload, status)

    def context(self):
        response = self.client.get(f'{self.url}/assurance')
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()

    def review_payload(self, **changes):
        return dict({'expected_review_id': None, 'correction_reason': None,
                     'artifact_manifest_digest': self.result.artifact_manifest['manifest_digest'],
                     'outcome': 'fail', 'rationale': 'Invented rejection rationale',
                     'limitations': 'Invented sample only'}, **changes)

    def decision_payload(self, review, **changes):
        return dict({'review_id': review['review_id'], 'expected_decision_id': None,
                     'correction_reason': None, 'disposition': 'close_rejected',
                     'rationale': 'Invented synthetic closure'}, **changes)

    def lesson_payload(self, review, decision, **changes):
        return dict({'review_id': review['review_id'], 'decision_id': decision['decision_id'],
                     'expected_lesson_id': None, 'correction_reason': None,
                     'claim': 'Invented synthetic-only observation', 'limitations': 'One fictional example',
                     'uncertainty': 'Not validated', 'applicability': 'Invented examples only',
                     'implication': 'Revise synthetic design'}, **changes)

    def detail(self, kind, identity, url=None, status=200):
        response = self.client.get(f'{url or self.url}/{kind}/{identity}')
        self.assertEqual(response.status_code, status, response.content)
        return response.json()

    def chain(self):
        self.as_actor(self.reviewer)
        self.assertEqual(self.context()['available_actions'], ['review'])
        review_response = self.publish('reviews', 'review-1', self.review_payload())
        self.assertEqual(self.publish('reviews', 'review-1', self.review_payload()).content, review_response.content)
        review = review_response.json()
        self.as_actor(self.decider)
        self.assertEqual(self.context()['available_actions'], ['decision'])
        decision = self.publish('decisions', 'decision-1', self.decision_payload(review)).json()
        self.as_actor(self.lesson_author)
        self.assertEqual(self.context()['available_actions'], ['lesson'])
        lesson = self.publish('lessons', 'lesson-1', self.lesson_payload(review, decision)).json()
        return review, decision, lesson


class AssuranceTests(AssuranceWorkflow, TestCase):
    def setUp(self):
        self.setup_assurance('policy')

    def test_default_off_and_effective_exact_scope_independence(self):
        viewer = principal('ordinary-viewer')
        outsider = principal('unbound-staff', None)
        User.objects.filter(pk=outsider.pk).update(is_staff=True, is_superuser=True)
        outsider.refresh_from_db()
        editor = self.editor
        for actor in (editor, viewer, self.reviewer, self.decider, self.lesson_author):
            self.as_actor(actor)
            self.assertEqual(self.context()['available_actions'], [])
            self.publish('reviews', 'disabled', self.review_payload(), 403)
        self.grant(editor, 'review')
        self.grant(outsider, 'review')
        before = IdempotencyRecord.objects.count()
        with self.configured():
            for actor in (viewer, editor, outsider, self.decider):
                self.as_actor(actor)
                self.publish('reviews', 'forbidden', self.review_payload(), 403)
            self.assertEqual(self.client.get(f'{self.url}/reviews').status_code, 200)
            self.as_actor(outsider)
            self.assertEqual(self.client.get(f'{self.url}/reviews').status_code, 403)
            self.as_actor(self.reviewer)
            self.assertEqual(self.context()['available_actions'], ['review'])
            self.publish('reviews', 'spoof', self.review_payload(actor_id=str(editor.pk)), 400)
            self.publish('reviews', 'bad-manifest', self.review_payload(artifact_manifest_digest='0' * 64), 409)
            self.publish('reviews', 'bad-pass', self.review_payload(outcome='pass'), 409)
            self.assertEqual((RunReview.objects.count(), IdempotencyRecord.objects.count()), (0, before))
            review = self.publish('reviews', 'review-valid', self.review_payload()).json()
            self.assertEqual(review['actor_id'], str(self.reviewer.pk))
            self.grant(self.reviewer, 'decision')
            before_self_disposition = self.counts()
            self.assertNotIn('decision', self.context()['available_actions'])
            self.publish('decisions', 'own-review', self.decision_payload(review), 403)
            self.assertEqual(self.counts(), before_self_disposition)
            self.as_actor(self.decider)
            self.assertEqual(self.context()['available_actions'], ['decision'])
            self.publish('decisions', 'bad-disposition', self.decision_payload(review, disposition='approve'), 400)
            self.assertFalse(RunDecision.objects.exists())

    def test_missing_or_contributor_provenance_is_denied_without_name_inference(self):
        self.as_actor(self.reviewer)
        key = next(key for key in self.bindings if key[0] == 'rms.hypothesisversion')
        self.bindings.pop(key)
        with self.configured():
            self.assertEqual(self.context()['available_actions'], [])
            self.publish('reviews', 'missing-proof', self.review_payload(), 403)
            self.bindings[key] = str(self.reviewer.pk)
            self.assertEqual(self.context()['available_actions'], [])
            self.publish('reviews', 'design-author', self.review_payload(), 403)
            self.bindings[key] = str(self.editor.pk)
            self.assertEqual(self.context()['available_actions'], ['review'])

    def test_three_authors_and_read_only_viewers_even_with_matching_grants(self):
        viewer = principal('read-only-viewer')
        dual = principal('read-only-even-with-editor', 'editor')
        dual.groups.add(Group.objects.get(name='founder_viewer'))
        unrelated = principal('unrelated-non-contributor', 'editor')
        with self.configured():
            review, decision, lesson = self.chain()
            originals = (
                ('reviews', 'review', review, self.reviewer),
                ('decisions', 'decision', decision, self.decider),
                ('lessons', 'lesson', lesson, self.lesson_author),
            )
            self.assertEqual(len({row['actor_id'] for _, _, row, _ in originals}), 3)
            previous = self.counts()
            reason = 'Invented corrective note'
            actions = (
                ('reviews', 'review', self.review_payload(expected_review_id=review['review_id'], correction_reason=reason)),
                ('decisions', 'decision', self.decision_payload(review, expected_decision_id=decision['decision_id'], correction_reason=reason)),
                ('lessons', 'lesson', self.lesson_payload(review, decision, expected_lesson_id=lesson['lesson_id'], correction_reason=reason)),
            )
            other_subject = str(uuid4())
            for actor in (viewer, dual, unrelated):
                self.as_actor(actor)
                for kind, action, row, author in originals:
                    self.assertEqual(self.detail(kind, row[f'{action}_id'])['actor_id'], str(author.pk))
                for kind, action, payload in actions:
                    exact_key = grant_key(actor, self.result, action)
                    wrong_subject = (exact_key[0], other_subject, *exact_key[2:])
                    for configuration in (None, 'unrelated', 'expired', 'matching'):
                        if configuration == 'matching' and actor == unrelated:
                            continue
                        with self.subTest(actor=actor.username, action=action, grant=configuration):
                            self.grants.pop(exact_key, None)
                            self.grants.pop(wrong_subject, None)
                            if configuration == 'unrelated':
                                self.grants[wrong_subject] = self.expires_at
                            elif configuration == 'expired':
                                self.grants[exact_key] = now() - timedelta(seconds=1)
                            elif configuration == 'matching':
                                self.grants[exact_key] = self.expires_at
                            self.assertEqual(self.context()['available_actions'], [])
                            self.publish(kind, 'denied', payload, 403)
                            self.assertEqual(self.counts(), previous)
                    self.grants.pop(exact_key, None)
                    self.grants.pop(wrong_subject, None)

    def test_wrong_or_malformed_grants_are_denied(self):
        actor = principal('invalid-grants', 'editor')
        self.as_actor(actor)
        key = grant_key(actor, self.result, 'review')
        actor_id, result_id, digest, _ = key
        invalid_grants = (
            {grant_key(actor, self.result, 'decision'): self.expires_at},
            {(actor_id, result_id, '0' * 64, 'review'): self.expires_at},
            {(str(self.reviewer.pk), result_id, digest, 'review'): self.expires_at},
            {key: self.expires_at.replace(tzinfo=None)},
            {key: self.expires_at.isoformat()},
            {key: None},
        )
        previous = self.counts()
        for grants in invalid_grants:
            with self.subTest(grants=grants), override_settings(RMS_SYNTHETIC_ASSURANCE_GRANTS=grants,
                    RMS_SYNTHETIC_ASSURANCE_PROVENANCE=self.bindings):
                self.assertNotIn('review', self.context()['available_actions'])
                self.publish('reviews', 'invalid-grant', self.review_payload(), 403)
                self.assertEqual(self.counts(), previous)

    def test_expiry_denies_new_append_and_previously_authorized_replay(self):
        self.as_actor(self.reviewer)
        payload = self.review_payload()
        with self.configured():
            first = self.publish('reviews', 'expiring', payload)
            self.assertEqual(self.publish('reviews', 'expiring', payload).content, first.content)
            previous = self.counts()
            review = first.json()
            with patch('rms.run_assurance_policy.now', return_value=self.expires_at):
                self.assertEqual(self.context()['available_actions'], [])
                self.publish('reviews', 'expiring', payload, 403)
                self.publish('reviews', 'expired-correction', self.review_payload(expected_review_id=review['review_id'],
                             correction_reason='Would be valid before expiry'), 403)
                self.assertEqual(self.counts(), previous)
                self.assertEqual(self.detail('reviews', review['review_id'])['row_digest'], review['row_digest'])

    def test_history_corrections_stale_and_cross_scope_reliance(self):
        with self.configured():
            review, decision, lesson = self.chain()
            self.as_actor(self.lesson_author)
            self.publish('lessons', 'stale-lesson', self.lesson_payload(review, decision), 409)
            self.as_actor(self.reviewer)
            self.publish('reviews', 'review-1', self.review_payload(rationale='Different content'), 409)
            successor = self.publish('reviews', 'review-2', self.review_payload(
                expected_review_id=review['review_id'], correction_reason='Invented scope note')).json()
            self.as_actor(self.decider)
            self.publish('decisions', 'stale-review', self.decision_payload(review,
                         expected_decision_id=decision['decision_id'], correction_reason='Stale basis'), 409)
            self.as_actor(self.lesson_author)
            self.publish('lessons', 'stale-decision', self.lesson_payload(successor, decision,
                         expected_lesson_id=lesson['lesson_id'], correction_reason='Stale basis'), 409)
            self.as_actor(self.decider)
            corrected_decision = self.publish('decisions', 'decision-2', self.decision_payload(successor,
                expected_decision_id=decision['decision_id'], correction_reason='Use corrected review')).json()
            self.as_actor(self.lesson_author)
            corrected_lesson = self.publish('lessons', 'lesson-2', self.lesson_payload(successor, corrected_decision,
                expected_lesson_id=lesson['lesson_id'], correction_reason='Use corrected decision')).json()
            self.assertEqual(corrected_lesson['supersedes_lesson_id'], lesson['lesson_id'])
            self.as_actor(self.editor)
            payload = self.result_payload(self.run, self.completed)
            payload.update(expected_result_version_id=self.result.public_id, correction_reason='Invented better summary')
            other = self.post(self.result_base, 'result-2', payload).json()['result_version_id']
            self.as_actor(principal('historical-reader'))
            self.assertEqual(self.context()['available_actions'], [])
            for kind, identity_key, row in (('reviews', 'review_id', review), ('decisions', 'decision_id', decision),
                                            ('lessons', 'lesson_id', lesson)):
                read = self.detail(kind, row[identity_key])
                self.assertEqual({key: read[key] for key in row}, row)
                self.assertFalse(read['current'])
                self.assertEqual(read['result_head_id'], other)
                self.assertIsNotNone(read['superseded_by_id'])
                self.detail(kind, row[identity_key], f'{self.result_base}/{other}', status=404)
                page = self.client.get(f'{self.url}/{kind}?offset=1').json()
                self.assertEqual(len(page['records']), 1)
            old = self.detail('reviews', review['review_id'])
            self.assertEqual(old['impact'], {'decisions': [decision['decision_id']], 'lessons': [lesson['lesson_id']]})
            self.as_actor(self.reviewer)
            self.publish('reviews', 'stale-result', self.review_payload(expected_review_id=successor['review_id'],
                         correction_reason='No new reliance'), 409)
            result2 = RunResultVersion.objects.get(public_id=other)
            self.grant(self.reviewer, 'review', result=result2)
            self.grant(self.decider, 'decision', result=result2)
            self.grant(self.lesson_author, 'lesson', result=result2)
            self.url = f'{self.result_base}/{other}'
            review2 = self.publish('reviews', 'review-other-scope', self.review_payload(
                artifact_manifest_digest=result2.artifact_manifest['manifest_digest'])).json()
            self.as_actor(self.decider)
            self.publish('decisions', 'cross-scope-review', self.decision_payload(review), 409)
            decision2 = self.publish('decisions', 'decision-other-scope', self.decision_payload(review2)).json()
            self.as_actor(self.lesson_author)
            self.publish('lessons', 'cross-scope-decision', self.lesson_payload(review2, decision), 409)
            self.assertNotEqual(decision2['decision_id'], decision['decision_id'])

    def test_unresolved_review_blocks_reliance(self):
        with self.configured():
            self.as_actor(self.reviewer)
            review = self.publish('reviews', 'inconclusive', self.review_payload(outcome='inconclusive')).json()
            self.as_actor(self.decider)
            self.assertEqual(self.context()['available_actions'], [])
            self.publish('decisions', 'cannot-rely', self.decision_payload(review), 409)

    def test_sql_protection_and_byte_tamper_fail_closed(self):
        with self.configured():
            review, decision, lesson = self.chain()
            for model in (RunReview, RunDecision, RunLesson):
                with self.assertRaises(DatabaseError), transaction.atomic():
                    model.objects.update(recorded_by='invented spoof')
                with self.assertRaises(DatabaseError), transaction.atomic(), connection.cursor() as cursor:
                    cursor.execute(f'TRUNCATE {model._meta.db_table} CASCADE')
            with self.assertRaises(DatabaseError), transaction.atomic():
                existing = RunDecision.objects.get(public_id=decision['decision_id'])
                RunDecision.objects.create(result=self.result, result_digest=self.result.row_digest,
                    artifact_manifest_digest='0' * 64, sequence=2, supersedes=existing, review=existing.review,
                    correction_reason='Invented malformed append', disposition='return_for_revision',
                    actor_id=str(self.decider.pk), recorded_by=self.decider.username)
            with transaction.atomic(), connection.cursor() as cursor:
                cursor.execute('SET CONSTRAINTS ALL IMMEDIATE')
                cursor.execute('ALTER TABLE rms_runresultversion DISABLE TRIGGER rr_no_edit')
                RunResultVersion.objects.filter(pk=self.result.pk).update(artifact_bytes=b'fabricated mismatch')
                cursor.execute('ALTER TABLE rms_runresultversion ENABLE TRIGGER rr_no_edit')
                self.as_actor(self.reviewer)
                self.publish('reviews', 'tampered', self.review_payload(expected_review_id=review['review_id'],
                             correction_reason='Unverifiable bytes'), 409)
                self.detail('lessons', lesson['lesson_id'], status=409)
                self.assertEqual(RunReview.objects.count(), 1)
                transaction.set_rollback(True)


class AssuranceRetryTests(AssuranceWorkflow, TestCase):
    def test_retry_ancestry_lifecycle_contributor_cannot_review(self):
        self.setup_workflow('retry-contributor')
        run = self.register()
        contributor = principal('ancestry-editor', 'editor')
        self.as_actor(contributor)
        terminal = self.event(run, 'failed', None)['event_id']
        self.as_actor(self.editor)
        retry = self.post(f'{self.root}/{run}/retry', 'retry-1', {
            'expected_event_id': terminal, 'external_reference': 'synthetic:assurance-retry-contributor',
            'reason': 'Invented retry after failure'})
        self.setup_assurance('retry-contributor', attempt=retry.json()['run_id'])
        self.grant(contributor, 'review')
        with self.configured():
            self.as_actor(contributor)
            self.assertEqual(self.context()['available_actions'], [])
            self.publish('reviews', 'ancestral-lifecycle', self.review_payload(), 403)
            self.as_actor(self.reviewer)
            self.publish('reviews', 'independent', self.review_payload())


class AssuranceConcurrencyTests(AssuranceWorkflow, TransactionTestCase):
    available_apps = ['django.contrib.auth', 'django.contrib.contenttypes']

    def test_postgres_serializes_duplicate_then_competing_corrections(self):
        self.setup_assurance('concurrency')

        def race(payloads, keys):
            barrier = Barrier(2)

            def worker(index):
                try:
                    actor = User.objects.get(pk=self.reviewer.pk)
                    barrier.wait(timeout=10)
                    return publish_review(actor=actor, **self.scope, payload=payloads[index], idempotency_key=keys[index])
                except StaleVersion:
                    return None
                finally:
                    connections.close_all()

            with ThreadPoolExecutor(max_workers=2) as threads:
                return list(threads.map(worker, range(2)))

        with self.configured():
            duplicate = race([self.review_payload()] * 2, ['duplicate'] * 2)
            self.assertEqual(duplicate[0].body, duplicate[1].body)
            original = RunReview.objects.get(result=self.result)
            payloads = [self.review_payload(expected_review_id=original.public_id,
                         correction_reason=f'Invented competing correction {index}') for index in range(2)]
            results = race(payloads, ['candidate-one', 'candidate-two'])
            self.assertEqual(sum(value is None for value in results), 1)
            self.assertEqual(RunReview.objects.filter(result=self.result).count(), 2)
            self.assertEqual(RunReview.objects.get(result=self.result, sequence=2).supersedes_id, original.pk)
            self.assertEqual(IdempotencyRecord.objects.filter(response_identity__startswith='REV-').count(), 2)
