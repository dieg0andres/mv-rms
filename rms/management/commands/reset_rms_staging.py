"""One reusable RMS-only reset; default is a local plan without a DB connection."""
import json
from datetime import datetime
from io import StringIO

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from rms.staging_test_reset import (
    AUTH_TABLES, POLICY_REF, RMS_TABLES, ResetRejected, reset_in_transaction, validate_binding,
)


class Command(BaseCommand):
    help = "Reset disposable staging RMS rows while preserving users/auth. Defaults to offline plan."
    requires_system_checks = []

    def add_arguments(self, parser):
        parser.add_argument("--project", required=True)
        parser.add_argument("--database-container", required=True)
        parser.add_argument("--execute", action="store_true")
        parser.add_argument("--reseed", action="store_true")
        parser.add_argument("--actor", help="Existing editor username; no account/group changes.")
        parser.add_argument("--review-time", help="Explicit fictional UTC review timestamp ending in Z.")

    def handle(self, *args, **options):
        try:
            validate_binding(connection.settings_dict, project=options['project'], container=options['database_container'])
            if options['reseed']:
                stamp = options.get('review_time') or ''
                if not options.get('actor') or not stamp.endswith('Z') or datetime.fromisoformat(stamp).utcoffset().total_seconds() != 0:
                    raise ResetRejected('existing_editor_and_utc_review_time_required')
            if not options['execute']:
                self.stdout.write(json.dumps({'mode': 'OFFLINE_PLAN_ONLY', 'policy_comment': POLICY_REF,
                    'rms_allowlist': RMS_TABLES, 'auth_preserved': AUTH_TABLES,
                    'reseed': options['reseed'], 'database_connections': 0}, sort_keys=True))
                return
            seed_output = StringIO()  # Release only after the outer commit succeeds.
            def reseed():
                call_command('load_rms_hn_fixture', actor=options['actor'], review_time=options['review_time'], stdout=seed_output)
            with transaction.atomic():
                with connection.cursor() as cursor:
                    result = reset_in_transaction(cursor, reseed=reseed if options['reseed'] else None)
            self.stdout.write(json.dumps(result, sort_keys=True))
            if options['reseed']:
                self.stdout.write(seed_output.getvalue().rstrip())
        except (ResetRejected, ValueError, CommandError) as error:
            code = str(error) if isinstance(error, ResetRejected) else 'fixture_or_options_rejected'
            raise CommandError('RESET_NOT_COMMITTED: ' + code) from None
        except Exception:
            # DB messages can carry submitted row values. Preserve redacted failure
            # outcome; Operations investigates in its approved local runtime channel.
            # A lost connection during COMMIT is uncertain. Inspect state before
            # any retry; never announce that data rolled back from this exception.
            raise CommandError('RESET_RESULT_UNCERTAIN: database_operation_failed; inspect before retry') from None
