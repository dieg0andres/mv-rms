"""Reproduce integrated source verification without a DB lifecycle or service."""

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


MODULES = [
    "tests.django_hypothesis_director_integration_tests",
    "tests.django_hypothesis_frontend_navigation_tests",
    "tests.django_hypothesis_frontend_classification_tests",
    "tests.django_hypothesis_frontend_integration_tests",
    "tests.django_hypothesis_frontend_shell_tests",
    "tests.django_hypothesis_frontend_draft_tests",
    "tests.django_hypothesis_frontend_schema_tests",
    "tests.django_rms_si_frontend_template_tests",
    "tests.test_hypothesis_staging_preflight",
    "tests.test_hypothesis_staging_release",
    "tests.test_hypothesis_staging_package",
    "tests.test_staging_request_policy",
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    os.chdir(root)
    sys.path.insert(0, str(root))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "rms_project.settings")
    args.output.mkdir(parents=True, exist_ok=False)
    from rms.hypothesis_staging_preflight import MANIFEST_PATH, verify_source
    pin = sha256((root / MANIFEST_PATH).read_bytes()).hexdigest()
    verify_source(root, pin)
    from django.db.backends.base.base import BaseDatabaseWrapper
    with patch.object(BaseDatabaseWrapper, "ensure_connection", side_effect=AssertionError("Integrated source verification forbids DB connections")) as guard:
        import django
        django.setup()
        with (args.output / "checks.log").open("w") as log:
            result = unittest.TextTestRunner(verbosity=2, stream=log).run(unittest.defaultTestLoader.loadTestsFromNames(MODULES))
        summary = {"source_manifest_sha256": pin, "tests_run": result.testsRun, "passed": result.wasSuccessful(), "database_connection_attempts": guard.call_count, "modules": MODULES, "run_id": os.environ.get("PAPERCLIP_RUN_ID"), "H01_H20_acceptance": "NOT_EXECUTED"}
        (args.output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        print(json.dumps(summary))
        return 0 if result.wasSuccessful() and guard.call_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
