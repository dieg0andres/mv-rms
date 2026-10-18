"""Interface 1.2 navigation/role checks using invented, DB-denied fixtures."""

from contextlib import ExitStack
from copy import deepcopy
from html.parser import HTMLParser
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import urlsplit

from django.db import DatabaseError
from django.test import RequestFactory, SimpleTestCase
from django.urls import resolve
from rest_framework.test import force_authenticate

from rms import api, record_selection_services as selection, hypothesis_services, research_context_services, test_plan_views
from rms.hypothesis_validation import validate_request
from rms.navigation_views import NavigationPage, SchemaUnavailable
from rms.permissions import has_rms_read_access, has_rms_write_access
from rms.research_context_common import Forbidden, require_actor
from rms.views import SourceCreatePage, SourceCorrectionPage, SourceHistoryPage, IdeaCreatePage, IdeaCorrectionPage, IdeaDetailPage, IdeaHistoryPage
from tests.django_hypothesis_frontend_integration_tests import invented_actor


def invented_selection(section="sources", *, page=1, size=25, count=1):
    identity = "FIC-SELECTION-001" if section == "sources" else "IDE-11111111-1111-4111-8111-111111111111"
    prefix = "source" if section == "sources" else "idea"
    history = f"/{section}/{identity}/history"
    item = {
        "stable_id": identity, "title": "Invented navigation <script>unsafe()</script>",
        "latest_version": 2, "latest_version_id": ("SRCV-" if section == "sources" else "IDEV-") + "22222222-2222-4222-8222-222222222222",
        "links": {"detail": history if section == "sources" else f"/ideas/{identity}", "history": history, "selected_version": history + f"#{prefix}-version-2"},
    }
    if section == "ideas":
        item["status"] = "rejected"
    return {"page": page, "page_size": size, "count": count, "results": [item] if count and (page - 1) * size < count else [],
            "previous": f"/api/v1/{section}?page={page - 1}&page_size={size}" if page > 1 and count else None,
            "next": f"/api/v1/{section}?page={page + 1}&page_size={size}" if page * size < count else None}


class LinkStructure(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.links, self.ids = [], []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if "id" in values:
            self.ids.append(values["id"])
        if tag == "a":
            self.links.append(values)


class NavigationFrontendTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.actor = invented_actor()

    def request(self, path="/", actor=None):
        request = self.factory.get(path)
        if actor is not False:
            force_authenticate(request, user=actor or self.actor)
        return request

    def page(self, section, path=None, actor=None):
        return NavigationPage.as_view(section=section)(self.request(path or "/" + section, actor))

    def render(self, response):
        response.render()
        return response.content.decode()

    def test_clickable_lists_show_exact_service_items_and_escape_text(self):
        for section, name in (("sources", "list_sources"), ("ideas", "list_ideas")):
            with self.subTest(section=section):
                result = invented_selection(section)
                snapshot = deepcopy(result)
                with patch.object(selection, name, return_value=result) as reader:
                    response = self.page(section)
                self.assertEqual(response.status_code, 200)
                reader.assert_called_once_with(actor=self.actor, query={})
                html = self.render(response)
                links = [link["href"] for link in LinkStructure(html).links]
                item = result["results"][0]
                for url in item["links"].values():
                    self.assertIn(url, links)
                for value in (item["stable_id"], item["latest_version_id"], "Latest version 2", "Permitted records: 1"):
                    self.assertIn(value, html)
                self.assertIn("&lt;script&gt;unsafe()&lt;/script&gt;", html)
                self.assertNotIn("<script>unsafe()", html)
                self.assertNotIn('name="record_id"', html)
                if section == "ideas":
                    self.assertIn("Status: rejected", html)
                else:
                    self.assertNotIn("Status:", html)
                self.assertEqual(result, snapshot)

    def test_browser_api_collection_binding_and_both_read_roles_match(self):
        for section, name, view in (("sources", "list_sources", api.SourceCreateView), ("ideas", "list_ideas", api.IdeaCreateView)):
            for role in ("editor", "founder_viewer"):
                with self.subTest(section=section, role=role):
                    actor = invented_actor(role)
                    result = invented_selection(section, page=2, size=10, count=21)
                    with patch.object(selection, name, return_value=result) as browser_reader, patch.object(api, name, return_value=result) as api_reader:
                        browser = self.page(section, f"/{section}?page=2&page_size=10", actor)
                        http = view.as_view()(self.request(f"/api/v1/{section}?page=2&page_size=10", actor))
                    self.assertEqual((browser.status_code, http.status_code), (200, 200))
                    self.assertEqual(browser_reader.call_args.kwargs, api_reader.call_args.kwargs)
                    self.assertEqual(browser_reader.call_args.kwargs["query"], {"page": 2, "page_size": 10})
                    html = self.render(browser)
                    self.assertIn("Editor" if role == "editor" else "Viewer (read-only)", html)
                    self.assertEqual(f'href="/{section}/new"' in html, role == "editor")

    def test_no_role_inactive_anonymous_and_staff_are_denied_before_read(self):
        actors = [(invented_actor("unassigned"), 403), (invented_actor(active=False), 403), (invented_actor("founder_viewer", active=False), 403), (False, 401)]
        staff = invented_actor("unassigned")
        staff.is_staff = staff.is_superuser = True
        actors.append((staff, 403))
        for section, name, view in (("sources", "list_sources", api.SourceCreateView), ("ideas", "list_ideas", api.IdeaCreateView)):
            for actor, expected in actors:
                with self.subTest(section=section, actor=actor), patch.object(selection, name) as browser_reader, patch.object(api, name) as api_reader:
                    browser = self.page(section, actor=actor)
                    http = view.as_view()(self.request(f"/api/v1/{section}", actor))
                    self.assertEqual(browser.status_code, expected)
                    self.assertEqual(http.status_code, expected)
                    browser_reader.assert_not_called()
                    api_reader.assert_not_called()
                    html = self.render(browser)
                    self.assertNotIn("FIC-SELECTION-001", html)
                    self.assertNotIn("Permitted records:", html)
                    self.assertNotIn("Role: Editor", html)
                    self.assertNotIn(f'href="/{section}/new"', html)

    def test_pagination_uses_envelope_values_preserves_order_and_size(self):
        for section, name in (("sources", "list_sources"), ("ideas", "list_ideas")):
            result = invented_selection(section, page=2, size=10, count=31)
            item = deepcopy(result["results"][0])
            item["title"] = "Invented second item"
            result["results"].append(item)
            # URLs are presence indicators only; the page/size envelope wins.
            result.update(next="/api/v1/ignored?page=99&page_size=100", previous="/api/v1/ignored?page=99&page_size=100")
            with patch.object(selection, name, return_value=result):
                html = self.render(self.page(section, f"/{section}?page=2&page_size=10"))
            links = [link["href"] for link in LinkStructure(html).links]
            self.assertIn(f"/{section}?page=3&page_size=10", links)
            self.assertIn(f"/{section}?page=1&page_size=10", links)
            self.assertFalse(any(url.startswith("/api/v1/") for url in links))
            self.assertLess(html.index("Invented navigation"), html.index("Invented second item"))

    def test_first_last_empty_and_out_of_range_pages_keep_real_counts(self):
        for page, size, count, next_page, previous in ((1, 25, 0, False, False), (1, 25, 27, True, False), (2, 25, 27, False, True), (9, 25, 27, False, True)):
            result = invented_selection(page=page, size=size, count=count)
            with self.subTest(page=page, count=count), patch.object(selection, "list_sources", return_value=result):
                html = self.render(self.page("sources", f"/sources?page={page}&page_size={size}"))
                self.assertIn(f"Permitted records: {count}", html)
                self.assertEqual("Next page" in html, next_page)
                self.assertEqual("Previous page" in html, previous)
                if not count:
                    self.assertIn("No permitted saved records.", html)
                elif page == 9:
                    self.assertIn("No permitted records on this page.", html)

    def test_default_and_maximum_size_come_from_backend_validation(self):
        def reader(*, actor, query):
            normalized = validate_request("SelectionQuery", query)
            return invented_selection(page=normalized["page"], size=normalized["page_size"])
        with patch.object(selection, "list_sources", side_effect=reader):
            for query, expected in (("", 25), ("?page_size=100", 100)):
                html = self.render(self.page("sources", "/sources" + query))
                self.assertIn("Page 1", html)
                self.assertIn(f"Page size {expected}", html)

    def test_invalid_queries_have_safe_400_and_no_guessed_count(self):
        def reader(*, actor, query):
            validate_request("SelectionQuery", query)
            raise AssertionError("Invalid query must never retrieve records")
        for section, name in (("sources", "list_sources"), ("ideas", "list_ideas")):
            for query in ("page=02", "page=1&page=2", "page=0", "page=-1", "page_size=101", "page_size=0", "page=%D9%A1", "search=PRIVATE-INVENTED-VALUE"):
                with self.subTest(section=section, query=query), patch.object(selection, name, side_effect=reader):
                    response = self.page(section, f"/{section}?{query}")
                self.assertEqual(response.status_code, 400)
                html = self.render(response)
                self.assertIn("selection query is invalid", html)
                self.assertNotIn("Permitted records:", html)
                self.assertNotIn("PRIVATE-INVENTED-VALUE", html)

    def test_selection_failure_is_503_without_record_count_or_private_diagnostic(self):
        for section, name in (("sources", "list_sources"), ("ideas", "list_ideas")):
            for error in (selection.SelectionUnavailable(), DatabaseError("PRIVATE invented database diagnostic"), SchemaUnavailable("PRIVATE path")):
                with self.subTest(section=section, error=type(error)), patch.object(selection, name, side_effect=error):
                    response = self.page(section)
                    html = self.render(response)
                    self.assertEqual(response.status_code, 503)
                    self.assertIn(f"{section.title()} selection is unavailable", html)
                    self.assertIn("Records and counts are unknown.", html)
                    self.assertIn('href="/">Return Home</a>', html)
                    self.assertNotIn("Source history", html)
                    self.assertNotIn("Permitted records:", html)
                    self.assertNotIn("No permitted saved records.", html)
                    self.assertNotIn("No save or completeness confirmation", html)
                    self.assertNotIn("PRIVATE", html)

    def home_readers(self, stack):
        readers = []
        for module, name in ((selection, "list_sources"), (selection, "list_ideas"), (hypothesis_services, "list_hypotheses"), (research_context_services, "list_research_families"), (research_context_services, "list_investigations")):
            readers.append(stack.enter_context(patch.object(module, name, return_value={"count": 0})))
        readers.append(stack.enter_context(patch.object(test_plan_views, "plan_service", return_value={"count": 0})))
        return readers

    def test_home_counts_use_all_six_authorized_readers_with_minimum_slice(self):
        for role in ("editor", "founder_viewer"):
            actor = invented_actor(role)
            with self.subTest(role=role), ExitStack() as stack:
                readers = self.home_readers(stack)
                response = self.page("home", "/", actor)
                html = self.render(response)
                self.assertEqual(response.status_code, 200)
                for reader in readers[:-1]:
                    reader.assert_called_once_with(actor=actor, query={"page": 1, "page_size": 1})
                readers[-1].assert_called_once_with("list_test_plans", actor=actor, query={"page": 1, "page_size": 1})
                self.assertEqual(html.count("Permitted records: 0"), 6)
                self.assertNotIn("Count unavailable", html)
                self.assertIn('href="/research-context#collection-family"', html)
                self.assertIn('href="/research-context#collection-case"', html)
                self.assertIn('href="/test-plans"', html)

    def test_home_partial_and_total_failure_leave_unknown_distinct_from_zero(self):
        for all_failed in (False, True):
            with self.subTest(all_failed=all_failed), ExitStack() as stack:
                readers = self.home_readers(stack)
                for reader in readers if all_failed else readers[:1]:
                    reader.side_effect = selection.SelectionUnavailable()
                response = self.page("home", "/")
                html = self.render(response)
                self.assertEqual(html.count("Count unavailable (unknown, not zero)"), 6 if all_failed else 1)
                self.assertEqual(html.count("Permitted records: 0"), 0 if all_failed else 5)
                self.assertEqual(response.status_code, 200)

    def test_home_backend_denial_does_not_render_partial_metadata(self):
        with ExitStack() as stack:
            readers = self.home_readers(stack)
            readers[1].side_effect = Forbidden()
            response = self.page("home", "/")
            html = self.render(response)
            self.assertEqual(response.status_code, 403)
            self.assertNotIn("Permitted records:", html)
            readers[2].assert_not_called()

    def test_home_denied_principals_never_reach_any_count_reader(self):
        for actor in (invented_actor("unassigned"), invented_actor(active=False), False):
            with self.subTest(actor=actor), ExitStack() as stack:
                readers = self.home_readers(stack)
                response = self.page("home", "/", actor)
                self.assertIn(response.status_code, (401, 403))
                for reader in readers:
                    reader.assert_not_called()

    def test_legacy_create_pages_use_shared_write_access_without_staff_bypass(self):
        for actor in (invented_actor("founder_viewer"), invented_actor("unassigned"), invented_actor(active=False)):
            actor.is_staff = actor.is_superuser = True
            for view, kwargs in ((SourceCreatePage, {}), (SourceCorrectionPage, {"source_id": "FIC-SELECTION-001"}), (IdeaCreatePage, {}), (IdeaCorrectionPage, {"idea_id": invented_selection("ideas")["results"][0]["stable_id"]})):
                with self.subTest(view=view, actor=actor), patch("rms.views.get_source") as source, patch("rms.views.get_idea") as idea, patch("rms.views._source_version_options") as options:
                    response = view.as_view()(self.request(actor=actor), **kwargs)
                    self.assertEqual(response.status_code, 403)
                    source.assert_not_called()
                    idea.assert_not_called()
                    options.assert_not_called()

    def test_legacy_reads_use_shared_access_before_source_idea_lookup(self):
        for actor in (invented_actor("unassigned"), invented_actor(active=False)):
            for view, kwargs in ((SourceHistoryPage, {"source_id": "FIC-SELECTION-001"}), (IdeaDetailPage, {"idea_id": invented_selection("ideas")["results"][0]["stable_id"]}), (IdeaHistoryPage, {"idea_id": invented_selection("ideas")["results"][0]["stable_id"]})):
                with self.subTest(view=view, actor=actor), patch("rms.views.get_source") as source, patch("rms.views.get_idea") as idea:
                    response = view.as_view()(self.request(actor=actor), **kwargs)
                    self.assertEqual(response.status_code, 403)
                    source.assert_not_called()
                    idea.assert_not_called()

    def test_collection_clicks_reopen_existing_history_and_exact_anchor(self):
        # Follow hrefs obtained from actual rendered HTML, through the existing
        # Source/Idea URLConf. Services remain mocked; no browser is launched.
        actor = invented_actor("founder_viewer")
        for section, name in (("sources", "list_sources"), ("ideas", "list_ideas")):
            item = invented_selection(section)["results"][0]
            version = {"version": 2, "title": item["title"], "created_by": "Invented editor", "created_at": "2026-10-03T12:00:00Z", "correction_reason": "Invented correction"}
            with patch.object(selection, name, return_value=invented_selection(section)):
                links = [link["href"] for link in LinkStructure(self.render(self.page(section, actor=actor))).links]
            selected_link = item["links"]["selected_version"]
            self.assertIn(selected_link, links)
            parsed = urlsplit(selected_link)
            matched = resolve(parsed.path, urlconf="rms_project.urls")
            with ExitStack() as stack:
                if section == "sources":
                    version["source_version_id"] = item["latest_version_id"]
                    source = SimpleNamespace(source_id=item["stable_id"])
                    stack.enter_context(patch("rms.views.get_source", return_value=source))
                    stack.enter_context(patch("rms.views.source_detail", return_value={"source_id": item["stable_id"], "synthetic": True, "latest_version": 2, "latest": version}))
                    stack.enter_context(patch("rms.views.source_history", return_value={"versions": [version]}))
                    stack.enter_context(patch("rms.views.latest_manifest", return_value={}))
                else:
                    version.update(idea_version_id=item["latest_version_id"], workflow_status="rejected", contributions=[])
                    stack.enter_context(patch("rms.views.get_idea"))
                    stack.enter_context(patch("rms.views.idea_history", return_value={"versions": [version]}))
                response = matched.func(self.request(parsed.path, actor), *matched.args, **matched.kwargs)
                html = self.render(response)
            self.assertEqual(response.status_code, 200)
            self.assertIn(f'id="{parsed.fragment}"', html)
            self.assertIn(item["latest_version_id"], html)
            self.assertNotIn("/correct", html)
            if section == "sources":
                self.assertIn(f'/api/v1/sources/{item["stable_id"]}/manifest?through_version=2', html)

    def test_active_editor_retains_existing_source_and_idea_forms(self):
        with patch("rms.views._source_version_options", return_value=[]):
            for view, url in ((SourceCreatePage, "/sources/new"), (IdeaCreatePage, "/ideas/new")):
                with self.subTest(view=view):
                    response = view.as_view()(self.request(url))
                    html = self.render(response)
                    self.assertEqual(response.status_code, 200)
                    self.assertIn('name="title"', html)
                    self.assertIn("Role: Editor", html)

    def test_shared_service_and_browser_predicates_match_role_matrix(self):
        for actor, read, write in ((invented_actor(), True, True), (invented_actor("founder_viewer"), True, False), (invented_actor("unassigned"), False, False), (invented_actor(active=False), False, False)):
            with self.subTest(actor=actor):
                self.assertEqual(has_rms_read_access(actor), read)
                self.assertEqual(has_rms_write_access(actor), write)
                for is_write, allowed in ((False, read), (True, write)):
                    if allowed:
                        require_actor(actor, write=is_write)
                    else:
                        with self.assertRaises(Forbidden):
                            require_actor(actor, write=is_write)

    def test_rendered_lists_have_semantic_navigation_unique_ids_and_private_caching(self):
        with patch.object(selection, "list_sources", return_value=invented_selection(count=31)):
            response = self.page("sources")
        html = self.render(response)
        structure = LinkStructure(html)
        self.assertEqual(len(structure.ids), len(set(structure.ids)))
        self.assertIn('<h1>Sources</h1>', html)
        self.assertIn('aria-label="Sources pages"', html)
        self.assertIn('href="#main-content"', html)
        self.assertEqual(sum(link.get("aria-current") == "page" for link in structure.links), 1)
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertIn("Authorization", response["Vary"])
        self.assertIn("Cookie", response["Vary"])
