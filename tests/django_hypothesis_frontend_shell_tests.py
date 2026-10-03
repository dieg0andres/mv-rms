from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.template.loader import render_to_string
from django.test import RequestFactory, SimpleTestCase
from django.urls import resolve
from rest_framework.test import force_authenticate

from rms.navigation_views import NavigationPage, navigation_context


class NavigationShellTests(SimpleTestCase):
    def render_page(self, section="home", role="founder_viewer"):
        return render_to_string(
            "rms/navigation.html", {
                **navigation_context(section=section, role=role),
                "heading": "Home" if section == "home" else "Research context",
            },
        )

    def test_primary_navigation_and_current_location(self):
        html = self.render_page()
        for label in ("Home", "Sources", "Ideas", "Hypotheses", "Research context"):
            self.assertIn(label, html)
        self.assertIn("Skip to main content", html)
        self.assertIn("id=\"main-content\"", html)
        self.assertEqual(html.count("aria-current=\"page\""), 1)
        self.assertIn("Synthetic software prototype only", html)
        self.assertIn("not a deployed release", html)

    def test_viewer_has_no_create_actions(self):
        html = self.render_page()
        self.assertIn("Viewer (read-only)", html)
        self.assertNotIn("href=\"/sources/new\"", html)
        self.assertNotIn("href=\"/ideas/new\"", html)

    def test_editor_existing_screen_links(self):
        html = self.render_page(role="editor")
        self.assertIn("href=\"/sources/new\"", html)
        self.assertIn("href=\"/ideas/new\"", html)

    def test_proposed_context_has_no_inferred_assessment(self):
        html = self.render_page(section="context")
        self.assertIn("State: proposed", html)
        self.assertIn("No assessment or family assignment is inferred", html)
        self.assertNotIn("Draft complete", html)

    def test_unknown_role_and_build_are_not_guessed(self):
        context = navigation_context(build="<script>invented</script>")
        html = render_to_string("rms/navigation.html", {**context, "heading": "Home"})
        self.assertFalse(context["can_edit"])
        self.assertIn("Role: Not supplied", html)
        self.assertIn("&lt;script&gt;invented&lt;/script&gt;", html)

    def test_prepared_routes_resolve_without_project_registration(self):
        for route in ("/", "/sources", "/ideas", "/hypotheses", "/research-context"):
            self.assertIs(resolve(route, urlconf="rms.navigation_urls").func.view_class, NavigationPage)

    def test_page_authorizes_before_rendering_without_database(self):
        for roles, expected in (({"editor"}, 200), ({"founder_viewer"}, 200), (set(), 403)):
            with self.subTest(roles=roles):
                groups = Mock()
                groups.filter.side_effect = lambda **query: SimpleNamespace(
                    exists=lambda: bool(roles.intersection(query.get("name__in", [query.get("name")])))
                )
                user = SimpleNamespace(is_authenticated=True, is_active=True, groups=groups)
                request = RequestFactory().get("/")
                force_authenticate(request, user=user)
                with patch("rms.navigation_views.shared_service", return_value={"count": 0}) as reader:
                    response = NavigationPage.as_view()(request)
                if expected == 403:
                    reader.assert_not_called()
                self.assertEqual(response.status_code, expected)
                response.render()
                if expected == 403:
                    self.assertNotIn(b"Research case", response.content)

    def test_anonymous_page_is_denied(self):
        response = NavigationPage.as_view()(RequestFactory().get("/"))
        self.assertEqual(response.status_code, 401)
