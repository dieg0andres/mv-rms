"""Version-pinned search over the metadata the current synthetic readers can see."""

from typing import NamedTuple
from django.db.models import F, Model, Q, Value
from django.db.models.fields.json import KT
from django.urls import reverse

from .hypothesis_models import HypothesisVersion, InvestigationVersion, ResearchFamilyVersion
from .models import IdeaVersion, SourceVersion
from .research_context_common import require_actor, visible
from .rr14_scope import ReadScope
from .test_plan_models import TestPlanVersion
from .test_plan_services import _visible as visible_plan_records


class Collection(NamedTuple):
    label: str
    model: type[Model]
    parent: str = "record"
    record_id: str = "record__public_id"
    version_id: str = "public_id"
    title: str = "fields__title"
    descriptions: tuple = ()


COLLECTIONS = {
    "source": Collection("Sources", SourceVersion, "source", "source__source_id", "source_version_id", "title", ("citation",)),
    "idea": Collection("Ideas", IdeaVersion, "idea", "idea__idea_id", "idea_version_id", "title", ("mechanism", "testable_claim")),
    "family": Collection("Research families", ResearchFamilyVersion, title="fields__name", descriptions=("fields__mechanism_boundary",)),
    "case": Collection("Research cases", InvestigationVersion, descriptions=("fields__next_action", "fields__blocker_text")),
    "hypothesis": Collection("Hypotheses", HypothesisVersion, descriptions=("fields__claim",)),
    "plan": Collection("Test plans", TestPlanVersion),
}
PAGE_SIZE = 25


def _matches(scope, kind, term, include_history):
    source = COLLECTIONS[kind]
    qs = visible_plan_records(source.model) if source.model is TestPlanVersion else visible(source.model)
    qs = scope.versions(qs)
    qs = qs.filter(**{source.parent + "__synthetic": True})
    if not include_history:
        qs = qs.filter(version=F(source.parent + "__latest_version"))
    title_field = KT(source.title) if source.title.startswith("fields__") else F(source.title)
    qs = qs.annotate(result_title=title_field, stable_id=F(source.record_id), exact_id=F(source.version_id), kind=Value(kind))
    match = Q(result_title__icontains=term) | Q(stable_id__icontains=term) | Q(exact_id__icontains=term)
    for field in source.descriptions:
        match |= Q(**{field + "__icontains": term})
    return qs.filter(match).order_by().values("kind", "stable_id", "exact_id", "result_title", "version", "created_at")


def _version_url(row):
    kind, identity, version = row["kind"], row["stable_id"], row["version"]
    if kind in ("source", "idea"):
        return reverse(kind + "-history-page", args=[identity]) + f"#{kind}-version-{version}"
    if kind == "plan":
        return reverse("rms-test-plan-version", args=[identity, row["exact_id"]])
    return reverse(f"rms-{kind}-version", args=[identity, version])


def search_versions(*, actor, term, collection, include_history, page):
    require_actor(actor)
    if not isinstance(term, str) or not 2 <= len(term.strip()) <= 128:
        raise ValueError("Enter a search between 2 and 128 characters.")
    if collection not in ("", *COLLECTIONS) or type(page) is not int or not 1 <= page <= 10000:
        raise ValueError("Choose a valid collection and page.")
    kinds = [collection] if collection else COLLECTIONS
    scope = ReadScope(actor)
    first, *others = [_matches(scope, kind, term.strip(), include_history) for kind in kinds]
    matches = first.union(*others, all=True) if others else first
    offset = (page - 1) * PAGE_SIZE
    rows = list(matches.order_by("-created_at", "kind", "stable_id", "-version")[offset:offset + PAGE_SIZE + 1])
    for row in rows[:PAGE_SIZE]:
        row["collection"] = COLLECTIONS[row["kind"]].label
        row["url"] = _version_url(row)
    return rows[:PAGE_SIZE], len(rows) > PAGE_SIZE
