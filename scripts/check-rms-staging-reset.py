"""Focused reset-source checks; forbid every Django and psycopg connection."""
import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    os.environ['DJANGO_SETTINGS_MODULE'] = 'rms_project.settings'
    from django.db.backends.base.base import BaseDatabaseWrapper
    import psycopg
    with patch.object(BaseDatabaseWrapper, 'ensure_connection', side_effect=AssertionError('DATABASE FORBIDDEN')) as django_guard, patch.object(psycopg, 'connect', side_effect=AssertionError('DATABASE FORBIDDEN')) as psycopg_guard:
        import django
        django.setup()
        with (args.output / 'checks.log').open('w') as log:
            suite = unittest.defaultTestLoader.loadTestsFromName('tests.test_staging_test_reset')
            result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
        source = ['rms/staging_test_reset.py', 'rms/management/commands/reset_rms_staging.py',
                  'tests/test_staging_test_reset.py', 'scripts/check-rms-staging-reset.py']
        summary = {'run': os.environ.get('PAPERCLIP_RUN_ID'), 'tests': result.testsRun,
            'pass': result.wasSuccessful(), 'django_connection_attempts': django_guard.call_count,
            'psycopg_connection_attempts': psycopg_guard.call_count,
            'source_sha256': {name: sha256((ROOT / name).read_bytes()).hexdigest() for name in source},
            'checks_log_sha256': sha256((args.output / 'checks.log').read_bytes()).hexdigest(),
            'scope': 'source simulation only; no live SQL, H01-H20, browser or role acceptance'}
    (args.output / 'summary.json').write_text(json.dumps(summary, indent=2, sort_keys=True) + '\n')
    print(json.dumps(summary))
    return 0 if result.wasSuccessful() and django_guard.call_count == psycopg_guard.call_count == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
