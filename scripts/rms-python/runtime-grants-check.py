"""Smoke and privilege checks against an operator-created, disposable RMS database."""
import base64
from copy import deepcopy
import hashlib
from io import StringIO
import json
import os
from datetime import timedelta
from unittest.mock import patch
import sys
import unittest

import django

django.setup()
from django.contrib.auth.models import Group, User
from django.core.management import call_command
from django.db import DatabaseError, connection, transaction
from django.utils.timezone import now
from rest_framework.test import APIClient

from rms.management.commands.load_rms_hn_fixture import Command
from rms.run_assurance_policy import design_records, grant_key, provenance_key
from rms.run_result_models import RunResultVersion
from tests.django_run_assurance_tests import AssuranceWorkflow
from rms.test_plan_services import correct_test_plan, create_test_plan
from tests.django_run_result_tests import Workflow
from tests.test_test_plan_backend_validation import complete_fixture


class Smoke(Workflow, unittest.TestCase):
    suffix = 'mau162-runtime'

    def __init__(self):
        super().__init__()
        self.client = APIClient()
        self.login('editor')

    def login(self, role):
        self.login_user(f'mau162-{role}')

    def login_user(self, username):
        self.client.credentials(HTTP_AUTHORIZATION='Basic ' + base64.b64encode(
            f"{username}:{os.environ['RMS_REHEARSAL_PASSWORD']}".encode()).decode())

    def readiness(self, expected_status):
        response = self.client.get('/api/v1/readiness')
        self.assertEqual(response.status_code, expected_status)
        if expected_status == 200:
            self.assertEqual(response.json(), {'status': 'ready'})
        else:
            self.assertEqual(response.json()['error']['code'], 'not_ready')

    def seed(self):
        stream = StringIO()
        call_command(Command(), actor='mau162-editor', review_time='2026-10-03T12:00:00Z', stdout=stream)
        payload = complete_fixture()
        payload['hypothesis_version_id'] = json.loads(stream.getvalue())['hypothesis_versions'][0]['version_id']
        actor = User.objects.get(username='mau162-editor')
        plan = json.loads(create_test_plan(actor=actor, idempotency_key='mau162-plan', payload=payload).body)
        correction = deepcopy(payload)
        correction.update(expected_latest_version=1, correction_reason='Invented threshold revision')
        correction['criteria'][0]['fields']['threshold'] = '3'
        correct_test_plan(actor=actor, plan_id=plan['plan_id'], idempotency_key='mau162-plan-v2', payload=correction)
        print(json.dumps(plan))

    def use_plan(self, filename):
        with open(filename) as handle:
            self.plan = json.load(handle)
        self.root = f"/api/v1/test-plans/{self.plan['plan_id']}/versions/{self.plan['plan_version_id']}/runs"

    def read_run(self, run):
        url = f'{self.root}/{run}'
        self.login('founder_viewer')
        self.assertEqual(self.client.get(self.root).status_code, 200)
        self.assertEqual(self.client.post(f'{url}/events', {}, format='json').status_code, 403)
        self.login('outsider')
        self.assertEqual(self.client.get(self.root).status_code, 403)
        self.login('editor')
        self.assertEqual(self.client.get(url).status_code, 200)

    def results(self, original_run):
        failed = self.event(original_run, 'failed', None)
        first = self.post(f'{self.root}/{original_run}/retry', 'retry-mau162', {
            'expected_event_id': failed['event_id'], 'external_reference': 'synthetic:mau162-retry',
            'reason': 'Invented retry',
        }).json()
        run = first['run_id']
        completed = self.complete(run)
        url = f'{self.root}/{run}/results'
        payload = self.result_payload(run, completed)
        result = self.post(url, 'result-mau162', payload).json()
        self.assertEqual(self.post(url, 'result-mau162', payload).json(), result)
        self.assertEqual(result['assessment_outcome'], 'mandatory_fail')
        corrected = self.result_payload(run, completed, value='2', artifact=b'invented corrected bytes')
        corrected.update(expected_result_version_id=result['result_version_id'], correction_reason='Invented correction')
        successor = self.post(url, 'correction-mau162', corrected).json()
        self.assertEqual(successor['assessment_outcome'], 'criteria_pass')
        self.read_run(run)
        exact = f"{url}/{result['result_version_id']}"
        self.assertEqual(self.client.get(exact).json(), result)
        artifact = base64.b64decode(self.client.get(exact + '/artifact').json()['content_base64'])
        digest = hashlib.sha256(artifact).hexdigest()
        self.assertEqual(digest, payload['artifact']['sha256'])
        print(json.dumps({'run': run, 'url': exact, 'row_digest': result['row_digest'], 'artifact_sha256': digest,
                          'current_url': f"{url}/{successor['result_version_id']}",
                          'current_row_digest': successor['row_digest']}))

    def verify_restore(self, filename):
        with open(filename) as handle:
            receipt = json.load(handle)
        self.read_run(receipt['run'])
        self.assertEqual(self.client.get(receipt['url']).json()['row_digest'], receipt['row_digest'])
        self.assertEqual(self.client.get(receipt['current_url']).json()['row_digest'], receipt['current_row_digest'])
        artifact = base64.b64decode(self.client.get(receipt['url'] + '/artifact').json()['content_base64'])
        self.assertEqual(hashlib.sha256(artifact).hexdigest(), receipt['artifact_sha256'])


class AssuranceSmoke(AssuranceWorkflow, Smoke):
    def as_actor(self, actor):
        self.login_user(actor.username)

    def assure(self, receipt):
        self.url = receipt['current_url']
        self.result = RunResultVersion.objects.get(public_id=self.url.rsplit('/', 1)[1])
        self.assertEqual(self.result.row_digest, receipt['current_row_digest'])
        self.reviewer = User.objects.get(username='mau162-reviewer')
        self.decider = User.objects.get(username='mau162-decider')
        self.lesson_author = User.objects.get(username='mau162-lesson')
        editor = User.objects.get(username='mau162-editor')
        viewer = User.objects.get(username='mau162-founder_viewer')
        unrelated = User.objects.get(username='mau162-unrelated')
        self.bindings = {provenance_key(record): str(editor.pk) for record in design_records(self.result)}
        self.expires_at = now() + timedelta(hours=1)
        self.grants = {grant_key(viewer, self.result, 'review'): self.expires_at}
        self.grant(self.reviewer, 'review')
        self.grant(self.decider, 'decision')
        self.grant(self.lesson_author, 'lesson')
        with self.configured():
            review, decision, lesson = self.chain()
            self.assertEqual([row['actor_id'] for row in (review, decision, lesson)],
                             [str(user.pk) for user in (self.reviewer, self.decider, self.lesson_author)])
            correction = self.review_payload(expected_review_id=review['review_id'],
                                             correction_reason='Invented restore smoke correction')
            before = self.counts()
            for actor in (viewer, unrelated):
                self.as_actor(actor)
                self.assertEqual(self.context()['available_actions'], [])
                self.publish('reviews', 'denied-assurance', correction, 403)
            self.as_actor(self.reviewer)
            with patch('rms.run_assurance_policy.now', return_value=self.expires_at):
                self.assertEqual(self.context()['available_actions'], [])
                self.publish('reviews', 'review-1', self.review_payload(), 403)
                self.publish('reviews', 'expired-correction', correction, 403)
            self.assertEqual(self.counts(), before)
            successor = self.publish('reviews', 'review-correction', correction).json()
            self.as_actor(viewer)
            old = self.detail('reviews', review['review_id'])
            self.assertEqual(old['row_digest'], review['row_digest'])
            self.assertEqual(old['superseded_by_id'], successor['review_id'])
            self.assertEqual(old['impact'], {'decisions': [decision['decision_id']], 'lessons': [lesson['lesson_id']]})
            checks = [('reviews', review['review_id']), ('reviews', successor['review_id']),
                      ('decisions', decision['decision_id']), ('lessons', lesson['lesson_id'])]
            print(json.dumps({'url': self.url, 'history': [(kind, identity, self.detail(kind, identity))
                                                          for kind, identity in checks]}))

    def verify_assurance(self, receipt):
        self.url = receipt['url']
        self.login('founder_viewer')
        self.assertEqual(self.context()['available_actions'], [])
        for kind, identity, expected in receipt['history']:
            self.assertEqual(self.detail(kind, identity), expected)


def deny(statement, expected):
    try:
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(statement)
    except DatabaseError as error:
        if error.__cause__.sqlstate == expected:
            return
        raise
    raise AssertionError(f'Expected SQLSTATE {expected}: {statement}')


def guards(owner):
    with connection.cursor() as cursor:
        cursor.execute('''SELECT NOT (rolsuper OR rolbypassrls OR rolcreatedb OR rolcreaterole OR rolreplication)
                          AND session_user=current_user AND NOT pg_has_role(current_user,%s,'SET')
                          FROM pg_roles WHERE rolname=current_user''', [owner])
        assert cursor.fetchone() == (True,)
    for statement in (
        'CREATE TABLE public.injected(id int)', 'CREATE TEMP TABLE injected(id int)',
        'ALTER TABLE public.rms_runattempt DISABLE TRIGGER run_immutable',
        'UPDATE public.rms_runattempt SET reported_by=reported_by',
        'DELETE FROM public.rms_runattempt', 'TRUNCATE public.rms_runattempt',
        'UPDATE public.rms_testplanversion SET row_digest=row_digest',
        'UPDATE public.rms_runresultversion SET summary=summary',
        'DELETE FROM public.rms_runlifecycleevent', 'TRUNCATE public.rms_runretry',
        'UPDATE public.auth_user SET is_superuser=is_superuser',
        'DELETE FROM public.auth_user_groups',
        "INSERT INTO public.django_migrations (app, name, applied) VALUES ('fixture', 'invented', now())",
        'UPDATE public.django_migrations SET name=name WHERE false',
        'DELETE FROM public.django_migrations WHERE false', 'TRUNCATE public.django_migrations',
        "SELECT nextval('public.django_migrations_id_seq')",
        "SELECT nextval('public.auth_user_id_seq')",
    ):
        deny(statement, '42501')
    deny('UPDATE public.rms_runattempt SET id=id', '23000')
    deny('UPDATE public.rms_source SET latest_version=latest_version+1', '23000')


def assurance_guards(owner):
    guards(owner)
    for table in ('rms_runreview', 'rms_rundecision', 'rms_runlesson'):
        for statement in (f'UPDATE public.{table} SET id=id WHERE false', f'DELETE FROM public.{table} WHERE false',
                          f'TRUNCATE public.{table}', f'ALTER TABLE public.{table} DISABLE TRIGGER ra_binding'):
            deny(statement, '42501')


mode, *args = sys.argv[1:]
if mode == 'principals':
    for role, group in (('editor', 'editor'), ('founder_viewer', 'founder_viewer'), ('outsider', None),
                        ('reviewer', 'editor'), ('decider', 'editor'), ('lesson', 'editor'), ('unrelated', 'editor')):
        user = User.objects.create_user(f'mau162-{role}', password=os.environ['RMS_REHEARSAL_PASSWORD'])
        if group:
            user.groups.add(Group.objects.get_or_create(name=group)[0])
elif mode == 'seed':
    Smoke().seed()
elif mode == 'readiness':
    with connection.cursor() as cursor:
        cursor.execute('SELECT count(*) FROM public.django_migrations')
        assert cursor.fetchone()[0] > 0
    Smoke().readiness(int(args[0]))
elif mode == 'register':
    smoke = Smoke()
    smoke.use_plan(args[0])
    print(smoke.register())
elif mode == 'results':
    smoke = Smoke()
    smoke.use_plan(args[0])
    smoke.results(args[1])
    guards(args[2])
elif mode in ('assurance', 'assurance_restore'):
    smoke = AssuranceSmoke()
    with open(args[0]) as handle:
        receipt = json.load(handle)
    (smoke.assure if mode == 'assurance' else smoke.verify_assurance)(receipt)
    assurance_guards(args[1])
elif mode == 'restore':
    smoke = Smoke()
    smoke.readiness(200)
    smoke.use_plan(args[0])
    smoke.verify_restore(args[1])
    guards(args[2])
else:
    raise ValueError('Unknown smoke mode')
