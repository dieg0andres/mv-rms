"""Reset boundary/atomicity checks; no Django or psycopg connection permitted."""
from contextlib import contextmanager
from copy import deepcopy
from io import StringIO
from pathlib import Path
import re
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from django.apps import apps
from django.core.management import call_command
from django.core.management.base import CommandError
from rms import staging_test_reset as reset
from rms.management.commands import reset_rms_staging as command_module


SETTINGS = {'ENGINE': 'django.db.backends.postgresql', 'NAME': 'rms_staging',
            'HOST': 'db', 'PORT': '5432', 'USER': 'rms_staging'}


class Cursor:
    def __init__(self, full=True):
        self.db = SimpleNamespace(in_atomic_block=True)
        self.full = full
        self.present = set(reset.RMS_TABLES if full else reset.BASE_TABLES) | set(reset.AUTH_TABLES) | {'django_session'}
        self.migrations = reset.BASE_MIGRATIONS | (reset.HN_MIGRATIONS if full else set())
        self.identity = ('rms_staging', 'rms_staging', 'rms_staging', 'off', 5432)
        self.admin = True
        self.external_fk = False
        self.enabled = {table: 'O' for table in reset.HN_TABLES} if full else {}
        self.auth_hash = 'unchanged-protected-state'
        self.rows = 80  # Disposable research state; its contents are not hashed.
        self.calls = []
        self.result = []
        self.fail_truncate = False

    def execute(self, sql, params=None):
        self.calls.append((sql, params))
        self.result = []
        if sql.startswith('SELECT current_database'):
            self.result = [self.identity]
        elif sql.startswith('SELECT rolsuper'):
            self.result = [(self.admin,)]
        elif sql.startswith('SELECT c.relname FROM pg_class'):
            self.result = [(table,) for table in sorted(self.present)]
        elif sql.startswith('SELECT name FROM public.django_migrations'):
            self.result = [(name,) for name in self.migrations]
        elif 'FROM pg_constraint' in sql:
            self.result = [(1,)] if self.external_fk else []
        elif sql.startswith('SELECT count(*)'):
            self.result = [(4, self.auth_hash)]
        elif 'FROM pg_trigger' in sql:
            self.result = [(table, self.enabled[table], 34, 'public', 'rms_reject_row_change')
                           for table in sorted(params[0]) if table in self.enabled]
        elif sql.startswith('ALTER TABLE'):
            table = sql.split('"')[1]
            self.enabled[table] = 'D' if ' DISABLE ' in sql else 'O'
        elif sql.startswith('TRUNCATE TABLE'):
            if self.fail_truncate:
                raise RuntimeError('sensitive database error')
            self.rows = 0

    def fetchone(self):
        return self.result[0] if self.result else None

    def fetchall(self):
        return self.result

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class ResetTests(unittest.TestCase):
    def test_allowlist_matches_actual_registered_product_models(self):
        self.assertEqual({model._meta.db_table for model in apps.get_app_config('rms').get_models()}, set(reset.RMS_TABLES))
        self.assertEqual(len(reset.RMS_TABLES), 19)

    def test_wrong_configurations_fail_before_connection(self):
        reset.validate_binding(SETTINGS, project='mv-rms-staging', container='mv-rms-staging-db-1')
        for key, value in [('ENGINE', 'sqlite'), ('NAME', 'rms_synthetic'), ('HOST', '127.0.0.1'), ('PORT', '5433'), ('USER', 'postgres')]:
            with self.subTest(key=key), self.assertRaises(reset.ResetRejected):
                reset.validate_binding({**SETTINGS, key: value}, project='mv-rms-staging', container='mv-rms-staging-db-1')
        for project, container in [('other', 'mv-rms-staging-db-1'), ('mv-rms-staging', 'other')]:
            with self.assertRaises(reset.ResetRejected):
                reset.validate_binding(SETTINGS, project=project, container=container)

    def test_full_reset_restores_guards_before_fixture_and_never_touches_auth(self):
        cursor = Cursor()
        def seed():
            self.assertEqual(cursor.rows, 0)
            self.assertTrue(all(value == 'O' for value in cursor.enabled.values()))
            cursor.rows = 56
        result = reset.reset_in_transaction(cursor, reseed=seed)
        sql = [statement for statement, _ in cursor.calls]
        truncates = [statement for statement in sql if statement.startswith('TRUNCATE ')]
        self.assertEqual(len(truncates), 1)
        self.assertTrue(truncates[0].endswith('CONTINUE IDENTITY RESTRICT'))
        self.assertEqual(set(truncates[0].split('"')[1::2]), set(reset.RMS_TABLES))
        self.assertEqual(set(re.findall(r'ONLY public\."([^"]+)"', truncates[0])), set(reset.RMS_TABLES))
        self.assertFalse(any(word in '\n'.join(sql) for word in ('CASCADE', 'RESTART IDENTITY', 'DISABLE TRIGGER ALL', 'session_replication_role', 'CREATE ROLE', 'GRANT ', 'DELETE FROM')))
        alters = [statement for statement in sql if statement.startswith('ALTER TABLE')]
        self.assertEqual(len(alters), 24)
        self.assertTrue(all(statement.startswith('ALTER TABLE ONLY ') for statement in alters))
        self.assertTrue(all(statement.endswith('TRIGGER hn_no_truncate') for statement in alters))
        self.assertFalse(set(reset.AUTH_TABLES).intersection(reset.RMS_TABLES))
        self.assertEqual(cursor.rows, 56)
        self.assertTrue(result['authentication_unchanged'])
        self.assertFalse(result['app_role_certification'])
        self.assertEqual(sql[-1], 'SET CONSTRAINTS ALL IMMEDIATE')

    def test_inherited_descendants_are_excluded_from_every_named_operation(self):
        class InheritanceCursor(Cursor):
            def __init__(self):
                super().__init__()
                self.present.add('unrelated_archive')
                self.descendants = {'rms_source': {'unrelated_archive': 9},
                                    'rms_hypothesisversion': {'other_schema.partition': 6}}
            def execute(self, sql, params=None):
                super().execute(sql, params)
                if sql.startswith('TRUNCATE TABLE'):
                    for only, table in re.findall(r'(ONLY\s+)?public\."([^"]+)"', sql):
                        if not only:
                            for child in self.descendants.get(table, {}):
                                self.descendants[table][child] = 0
        cursor = InheritanceCursor()
        before = deepcopy(cursor.descendants)
        reset.reset_in_transaction(cursor)
        self.assertEqual(cursor.descendants, before)
        for sql, _ in cursor.calls:
            if sql.startswith(('LOCK TABLE ', 'ALTER TABLE ', 'TRUNCATE TABLE ')):
                targets = re.findall(r'(ONLY\s+)?public\."([^"]+)"', sql)
                self.assertTrue(targets)
                self.assertTrue(all(only.strip() == 'ONLY' for only, _ in targets))
                self.assertNotIn('unrelated_archive', sql)

    def test_auth_column_insert_check_is_scoped_to_live_protected_columns(self):
        sql = (Path(__file__).resolve().parents[1] / 'docs/RMS-HN-ORDINARY-ROLE-PROPOSAL.sql').read_text()
        # Capture the actual protected-auth INSERT subquery, not a comment or an
        # unrelated RMS-column check. Table and column grants are distinct paths.
        auth = sql.split(') OR EXISTS (', 1)[1].split(') THEN RAISE', 1)[0]
        self.assertIn('JOIN pg_attribute a ON a.attrelid=c.oid AND a.attnum>0 AND NOT a.attisdropped', auth)
        self.assertIn("c.relname LIKE 'auth\\_%'", auth)
        self.assertIn("c.relname IN ('django_content_type','django_migrations')", auth)
        self.assertIn("has_table_privilege('rms_hn_app', c.oid, 'INSERT')", auth)
        self.assertIn("has_column_privilege('rms_hn_app', c.oid, a.attnum, 'INSERT')", auth)

    def test_current_source_idea_only_schema_can_reset_without_schema_update(self):
        cursor = Cursor(full=False)
        result = reset.reset_in_transaction(cursor)
        self.assertEqual(set(result['tables_reset']), set(reset.BASE_TABLES))
        self.assertFalse(result['reseeded'])
        self.assertFalse(any(sql.startswith('ALTER TABLE') for sql, _ in cursor.calls))

    def test_incomplete_unreviewed_schema_migrations_or_guards_stop_before_mutation(self):
        for kind in ('missing_table', 'new_table', 'new_migration', 'missing_guard', 'disabled_guard', 'external_fk', 'wrong_database', 'non_admin', 'reseed_old_schema'):
            cursor = Cursor(full=kind != 'reseed_old_schema')
            if kind == 'missing_table': cursor.present.remove('rms_hypothesis')
            if kind == 'new_table': cursor.present.add('rms_unknown')
            if kind == 'new_migration': cursor.migrations = cursor.migrations | {'0006_unknown'}
            if kind == 'missing_guard': del cursor.enabled['rms_hypothesis']
            if kind == 'disabled_guard': cursor.enabled['rms_hypothesis'] = 'D'
            if kind == 'external_fk': cursor.external_fk = True
            if kind == 'wrong_database': cursor.identity = ('other', *cursor.identity[1:])
            if kind == 'non_admin': cursor.admin = False
            seed = Mock() if kind == 'reseed_old_schema' else None
            with self.subTest(kind=kind), self.assertRaises(reset.ResetRejected):
                reset.reset_in_transaction(cursor, reseed=seed)
            self.assertFalse(any(sql.startswith(('ALTER TABLE', 'TRUNCATE TABLE')) for sql, _ in cursor.calls))
            if seed is not None: seed.assert_not_called()

    def test_identifiers_cannot_expand_scope(self):
        for names in ([], ['auth_user; DROP DATABASE rms_staging'], ['django_migrations'], ['rms_unknown']):
            with self.subTest(names=names), self.assertRaises(reset.ResetRejected):
                reset.qualified(names)

    def test_autocommit_cursor_is_rejected_before_any_sql(self):
        cursor = Cursor()
        cursor.db.in_atomic_block = False
        with self.assertRaisesRegex(reset.ResetRejected, 'atomic_transaction_required'):
            reset.reset_in_transaction(cursor)
        self.assertEqual(cursor.calls, [])

    def test_proposed_grants_bind_actual_tables_and_only_identity_watermarks(self):
        sql = (Path(__file__).resolve().parents[1] / 'docs/RMS-HN-ORDINARY-ROLE-PROPOSAL.sql').read_text()
        match = re.search(r'GRANT SELECT, INSERT ON (.*?) TO rms_hn_app;', sql)
        self.assertEqual({item.strip().removeprefix('public.') for item in match[1].split(',')}, set(reset.RMS_TABLES))
        update_tables = set(re.findall(r'GRANT UPDATE \(latest_version\) ON public\.(\w+) TO', sql))
        self.assertEqual(update_tables, {'rms_source','rms_idea','rms_researchfamily','rms_investigation','rms_priorresearchassessment','rms_hypothesis','rms_researchassociationidentity'})
        self.assertIn('PASSWORD NULL', sql)
        self.assertIn('NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS', sql)
        grants = '\n'.join(line for line in sql.splitlines() if line.startswith('GRANT '))
        for forbidden in ('DELETE', 'TRUNCATE', 'ALL TABLES', 'ALL SEQUENCES', 'CREATE', 'SECURITY DEFINER'):
            self.assertNotIn(forbidden, grants)


class CommandTests(unittest.TestCase):
    def test_actual_management_cli_defaults_to_offline_plan(self):
        fake_connection = SimpleNamespace(settings_dict=SETTINGS, cursor=Mock())
        output = StringIO()
        with patch.object(command_module, 'connection', fake_connection):
            call_command('reset_rms_staging', '--project', 'mv-rms-staging', '--database-container', 'mv-rms-staging-db-1', stdout=output)
        fake_connection.cursor.assert_not_called()
        self.assertIn('OFFLINE_PLAN_ONLY', output.getvalue())

    def execute(self, cursor=None, seed=None, **changes):
        cursor = cursor or Cursor()
        options = {'project': 'mv-rms-staging', 'database_container': 'mv-rms-staging-db-1',
                   'execute': True, 'reseed': True, 'actor': 'existing_editor',
                   'review_time': '2026-10-03T00:00:00Z', **changes}
        self.command = command_module.Command(stdout=StringIO())
        self.out = self.command.stdout._out
        self.seed_calls = Mock(side_effect=seed)
        self.rolled_back = False
        @contextmanager
        def atomic():
            before = deepcopy((cursor.enabled, cursor.auth_hash, cursor.rows))
            try:
                yield
            except Exception:
                cursor.enabled, cursor.auth_hash, cursor.rows = before
                self.rolled_back = True
                raise
        fake_connection = SimpleNamespace(settings_dict=SETTINGS, cursor=Mock(return_value=cursor))
        with patch.object(command_module, 'connection', fake_connection), patch.object(command_module.transaction, 'atomic', atomic), patch.object(command_module, 'call_command', self.seed_calls):
            self.command.handle(**options)
        return cursor, fake_connection

    def test_default_plan_has_zero_connections_and_mutations(self):
        cursor, connection = self.execute(execute=False)
        connection.cursor.assert_not_called()
        self.seed_calls.assert_not_called()
        self.assertEqual(cursor.calls, [])
        self.assertIn('OFFLINE_PLAN_ONLY', self.out.getvalue())

    def test_committed_fixture_uses_existing_loader_and_editor_not_account_creation(self):
        self.execute()
        name, = self.seed_calls.call_args.args
        self.assertEqual(name, 'load_rms_hn_fixture')
        self.assertEqual(self.seed_calls.call_args.kwargs['actor'], 'existing_editor')
        self.assertEqual(self.seed_calls.call_args.kwargs['review_time'], '2026-10-03T00:00:00Z')
        self.assertIn('"authentication_unchanged": true', self.out.getvalue())

    def test_fixture_failure_rolls_back_data_and_guards_without_success_receipt(self):
        cursor = Cursor()
        with self.assertRaisesRegex(CommandError, 'RESET_NOT_COMMITTED'):
            self.execute(cursor, seed=CommandError('invented fixture failure'))
        self.assertTrue(self.rolled_back)
        self.assertEqual(cursor.rows, 80)
        self.assertTrue(all(value == 'O' for value in cursor.enabled.values()))
        self.assertEqual(self.out.getvalue(), '')

    def test_auth_mutation_aborts_the_same_transaction(self):
        cursor = Cursor()
        def corrupt(*args, **kwargs):
            cursor.auth_hash = 'changed'
        with self.assertRaisesRegex(CommandError, 'authentication_changed'):
            self.execute(cursor, seed=corrupt)
        self.assertTrue(self.rolled_back)
        self.assertEqual(cursor.auth_hash, 'unchanged-protected-state')
        self.assertEqual(cursor.rows, 80)
        self.assertEqual(self.out.getvalue(), '')

    def test_fixture_cannot_leave_history_guards_disabled(self):
        cursor = Cursor()
        def corrupt(*args, **kwargs):
            cursor.enabled['rms_hypothesisversion'] = 'D'
        with self.assertRaisesRegex(CommandError, 'history_guard_changed_by_fixture'):
            self.execute(cursor, seed=corrupt)
        self.assertTrue(self.rolled_back)
        self.assertEqual(cursor.rows, 80)
        self.assertTrue(all(value == 'O' for value in cursor.enabled.values()))

    def test_truncate_failure_restores_transactional_guard_state_and_redacts_error(self):
        cursor = Cursor()
        cursor.fail_truncate = True
        with self.assertRaisesRegex(CommandError, 'database_operation_failed') as raised:
            self.execute(cursor)
        self.assertNotIn('sensitive', str(raised.exception))
        self.assertTrue(self.rolled_back)
        self.assertTrue(all(value == 'O' for value in cursor.enabled.values()))
        self.seed_calls.assert_not_called()

    def test_partitioned_parent_rejection_rolls_back_without_scope_expansion(self):
        class PartitionCursor(Cursor):
            def execute(self, sql, params=None):
                if sql.startswith('TRUNCATE TABLE'):
                    targets = re.findall(r'(ONLY\s+)?public\."([^"]+)"', sql)
                    if any(only and table == 'rms_source' for only, table in targets):
                        raise RuntimeError('cannot truncate only a partitioned table')
                super().execute(sql, params)
        cursor = PartitionCursor()
        with self.assertRaisesRegex(CommandError, 'RESET_RESULT_UNCERTAIN'):
            self.execute(cursor)
        self.assertTrue(self.rolled_back)
        self.assertEqual(cursor.rows, 80)
        self.assertTrue(all(value == 'O' for value in cursor.enabled.values()))
        self.seed_calls.assert_not_called()
        self.assertEqual(self.out.getvalue(), '')

    def test_missing_editor_or_time_fails_before_cursor(self):
        for changes in ({'actor': None}, {'review_time': None}, {'review_time': 'tomorrow'}, {'review_time': '2026-10-03T00:00:00+00:00'}):
            with self.subTest(changes=changes), self.assertRaises(CommandError):
                self.execute(**changes)
            self.seed_calls.assert_not_called()
