"""A disposable Django test database for races that need visible committed rows."""
from uuid import uuid4

from django.db import connection
from django.test import TransactionTestCase


class CommittedDatabaseTestCase(TransactionTestCase):
    @classmethod
    def _fixture_setup(cls):
        cls.original_database = connection.settings_dict["NAME"]
        cls.scratch_database = "test_rms_race_" + uuid4().hex
        options = connection.settings_dict["TEST"]
        previous_test_name = options["NAME"]
        try:
            options["NAME"] = cls.scratch_database
            connection.creation.create_test_db(verbosity=0, autoclobber=False, serialize=False)
            super()._fixture_setup()
        except BaseException:
            if connection.settings_dict["NAME"] == cls.scratch_database:
                cls.discard_scratch_database()
            raise
        finally:
            options["NAME"] = previous_test_name

    @classmethod
    def discard_scratch_database(cls):
        if connection.settings_dict["NAME"] != cls.scratch_database:
            raise RuntimeError("The active database differs from this test's disposable database.")
        connection.creation.destroy_test_db(old_database_name=cls.original_database, verbosity=0)

    def _fixture_teardown(self):
        # The application rejects TRUNCATE on immutable history. Django can
        # discard this test-owned database without changing any history guard.
        self.discard_scratch_database()
