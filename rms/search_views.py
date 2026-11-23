"""Authenticated, server-rendered research record search."""

from django import forms
from django.db import DatabaseError
from django.template.response import TemplateResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from rest_framework.parsers import FormParser

from .record_search import COLLECTIONS, search_versions
from .views import RmsPage


class SearchForm(forms.Form):
    term = forms.CharField(label="Search terms or record ID", min_length=2, max_length=128,
                           widget=forms.TextInput(attrs={"type": "search", "autocomplete": "off"}))
    collection = forms.ChoiceField(required=False, choices=[("", "All collections")] +
                                   [(key, info.label) for key, info in COLLECTIONS.items()])
    include_history = forms.BooleanField(label="Include earlier versions", required=False)
    page = forms.IntegerField(required=False, min_value=1, max_value=10000)


class RecordSearchPage(RmsPage):
    parser_classes = [FormParser]

    def render(self, request, form, *, status=200, **context):
        response = TemplateResponse(request._request, "rms/record_search.html", {"form": form, **context}, status=status)
        response["Referrer-Policy"] = "same-origin"
        return response

    @method_decorator(ensure_csrf_cookie)
    def get(self, request):
        self._require_reader(request)
        return self.render(request, SearchForm())

    @method_decorator(csrf_protect)
    def post(self, request):
        self._require_reader(request)
        form = SearchForm(request.data)
        if not form.is_valid():
            return self.render(request, form, status=400)
        values = form.cleaned_data
        page = values["page"] or 1
        try:
            rows, more = search_versions(actor=request.user, term=values["term"], collection=values["collection"],
                                         include_history=values["include_history"], page=page)
        except DatabaseError:
            return self.render(request, form, status=503, unavailable=True)
        return self.render(request, form, results=rows, searched=True, page=page,
                           previous=page - 1 if page > 1 else None, following=page + 1 if more and page < 10000 else None)
