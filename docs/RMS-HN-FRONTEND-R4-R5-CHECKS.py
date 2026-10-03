"""Run source checks in a disposable aab6d6df composition, never a database.

Invoke using the existing .venv/bin/python -B with composition and output paths.
Append --wording-only for the collection-unavailable checkpoint only.
The composition is read-only to this runner; invented HTML/logs go to output.
This does not start a service or browser, provision, publish or integrate URLs.
"""

from contextlib import ExitStack
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch


MODULES = [
    "tests.django_hypothesis_frontend_navigation_tests",
    "tests.django_hypothesis_frontend_classification_tests",
    "tests.django_hypothesis_frontend_integration_tests",
    "tests.django_hypothesis_frontend_shell_tests",
    "tests.django_hypothesis_frontend_draft_tests",
    "tests.django_hypothesis_frontend_schema_tests",
    "tests.django_rms_si_frontend_template_tests",
]


def main():
    composition = Path(sys.argv[1]).resolve(strict=True)
    output = Path(sys.argv[2]).resolve()
    output.mkdir(parents=True, exist_ok=True)
    os.chdir(composition)
    sys.path.insert(0, str(composition))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "rms_project.settings")
    wording_only = "--wording-only" in sys.argv[3:]
    modules = ["tests.django_hypothesis_frontend_navigation_tests.NavigationFrontendTests.test_selection_failure_is_503_without_record_count_or_private_diagnostic"] if wording_only else MODULES
    from django.db.backends.base.base import BaseDatabaseWrapper

    with patch.object(BaseDatabaseWrapper, "ensure_connection", side_effect=AssertionError("Frontend source checks forbid all Django DB connections")) as connection:
        import django
        django.setup()
        from rms import record_selection_services as selection
        from tests.django_hypothesis_frontend_navigation_tests import (
            LinkStructure, NavigationFrontendTests, invented_actor, invented_selection,
        )

        with (output / "django-checks.log").open("w") as log:
            result = unittest.TextTestRunner(verbosity=2, stream=log).run(unittest.defaultTestLoader.loadTestsFromNames(modules))
        summary = {"tests_run": result.testsRun, "successful": result.wasSuccessful(), "modules": modules, "renders": []}
        if not result.wasSuccessful():
            print((output / "django-checks.log").read_text())
            return 1
        fixture = NavigationFrontendTests()
        fixture.setUp()

        def save(name, response):
            html = fixture.render(response)
            content = html.encode()
            structure = LinkStructure(html)
            assert len(structure.ids) == len(set(structure.ids))
            assert "<script>unsafe()" not in html
            assert response["Cache-Control"] == "private, no-store"
            (output / (name + ".html")).write_bytes(content)
            summary["renders"].append({"name": name, "status": response.status_code, "bytes": len(content), "sha256": sha256(content).hexdigest(), "links": structure.links})
            return html

        if wording_only:
            for section, name in (("sources", "list_sources"), ("ideas", "list_ideas")):
                with patch.object(selection, name, side_effect=selection.SelectionUnavailable()):
                    response = fixture.page(section)
                    assert response.status_code == 503
                    html = save(section + "-unavailable", response)
                    assert section.title() + " selection is unavailable" in html
                    assert "Records and counts are unknown." in html
            summary["database_connection_attempts"] = connection.call_count
            assert connection.call_count == 0
            (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
            print(json.dumps(summary))
            return 0

        for role in ("editor", "founder_viewer"):
            with ExitStack() as stack:
                readers = fixture.home_readers(stack)
                readers[0].return_value = {"count": 4}
                readers[2].side_effect = selection.SelectionUnavailable()
                html = save("home-" + role, fixture.page("home", "/", invented_actor(role)))
                assert "Permitted records: 4" in html
                assert "Permitted records: 0" in html
                assert "Count unavailable (unknown, not zero)" in html
        with patch.object(selection, "list_sources", return_value=invented_selection(page=2, size=10, count=31)):
            html = save("sources-editor-page-2", fixture.page("sources", "/sources?page=2&page_size=10"))
            assert '/sources?page=3&amp;page_size=10' in html
            assert '#source-version-2' in html
        with patch.object(selection, "list_ideas", return_value=invented_selection("ideas")):
            html = save("ideas-viewer", fixture.page("ideas", actor=invented_actor("founder_viewer")))
            assert "Status: rejected" in html
            assert '#idea-version-2' in html
            assert 'href="/ideas/new"' not in html
        with patch.object(selection, "list_sources", return_value=invented_selection(count=0)):
            html = save("sources-empty", fixture.page("sources"))
            assert "No permitted saved records." in html
        with patch.object(selection, "list_sources", side_effect=selection.SelectionUnavailable()):
            response = fixture.page("sources")
            assert response.status_code == 503
            html = save("sources-unavailable", response)
            assert "Permitted records: 0" not in html
        with patch.object(selection, "list_sources") as reader:
            response = fixture.page("sources", actor=invented_actor("unassigned"))
            assert response.status_code == 403
            save("sources-denied", response)
            reader.assert_not_called()
        summary["database_connection_attempts"] = connection.call_count
        assert connection.call_count == 0
        (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        print(json.dumps({key: value for key, value in summary.items() if key != "renders"}))
        print("Separate invented TemplateResponse renders:", len(summary["renders"]))
        return 0


if __name__ == "__main__":
    sys.exit(main())
