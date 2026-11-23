"""Custodian-owned file fixture for named readers of a saved synthetic Plan."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import override_settings


class SyntheticPlanReaders:
    def __init__(self, test, plan):
        directory = TemporaryDirectory()
        test.addCleanup(directory.cleanup)
        self.path = Path(directory.name) / 'readers.json'
        setting = override_settings(RMS_RR14_SCOPE_FILE=self.path)
        setting.enable()
        test.addCleanup(setting.disable)
        self.case_id = plan['research_context']['investigation']['stable_id']
        self.plan_id = plan['plan_id']
        self.grants = {}

    def allow(self, *actors):
        for actor in actors:
            self.grants[str(actor.pk)] = {
                'username': actor.get_username(), 'cases': [self.case_id], 'plans': [self.plan_id],
            }
        replacement = self.path.with_suffix('.next')
        replacement.write_text(json.dumps({'format': 'rr14-disposable-synthetic-v1', 'principals': self.grants}))
        replacement.replace(self.path)
