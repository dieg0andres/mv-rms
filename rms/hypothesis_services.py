"""Draft persistence and immutable lineage shared by browser and API callers."""

from types import SimpleNamespace

from django.urls import reverse

from .hypothesis_models import (
    Hypothesis, HypothesisVersion, HypothesisCorrectionImpact, InvestigationVersion,
    ResearchAssociation, ResearchAssociationIdentity, ResearchFamilyVersion,
)
from .hypothesis_validation import draft_completeness
from .models import IdeaVersion
from .research_context_common import (
    append, change_paths, check_expected, endpoint, envelope, execute_write,
    field_error, latest, paginated, record_links, require_actor, resolve, visible,
)
from .research_context_services import association, association_read, edge


def resolve_context(payload):
    idea = resolve(IdeaVersion, payload["originating_idea_version_id"])
    case = resolve(InvestigationVersion, payload["investigation_version_id"])
    case_family = edge(case, "InvestigationFamily")
    binding = payload["idea_family_binding"]
    if binding["mode"] == "existing":
        classified = resolve(ResearchAssociation, binding["association_version_id"])
        if classified.kind != "IdeaFamily" or classified.idea_version_id != idea.pk:
            field_error("/idea_family_binding/association_version_id")
        # The API permits explicit historical context. Never substitute latest;
        # initial impacts separately show a superseding classification, if any.
        if classified.family_version.record_id != case_family.family_version.record_id:
            field_error("/idea_family_binding/association_version_id")
    else:
        family = resolve(ResearchFamilyVersion, binding["family_version_id"])
        if family.pk != case_family.family_version_id:
            field_error("/idea_family_binding/family_version_id")
        if ResearchAssociationIdentity.objects.filter(idea_version=idea).exists():
            field_error("/idea_family_binding", "already_classified")
        classified = None
    # No partial writes before every supplied reference has been resolved.
    edge(case, "PriorResearchInvestigation")
    return idea, case, classified


def bind_context(*, actor, payload, idea, case, classified, item, predecessor=None):
    if classified is None:
        binding = payload["idea_family_binding"]
        classified = association("IdeaFamily", actor=actor, idea_version=idea,
                                 family_version=resolve(ResearchFamilyVersion, binding["family_version_id"]), rationale=binding["rationale"])
    old_origin = edge(predecessor, "IdeaHypothesis") if predecessor else None
    old_case = edge(predecessor, "HypothesisInvestigation") if predecessor else None
    reason = payload.get("correction_reason")
    association("IdeaHypothesis", actor=actor, predecessor=old_origin, correction_reason=reason,
                idea_version=idea, hypothesis_version=item, idea_family_version=classified, rationale=payload["origin_rationale"])
    association("HypothesisInvestigation", actor=actor, predecessor=old_case, correction_reason=reason,
                hypothesis_version=item, investigation_version=case)


def pinned_upstream(item):
    origin = edge(item, "IdeaHypothesis")
    case = edge(item, "HypothesisInvestigation").investigation_version
    result = [("idea", origin.idea_version), ("association", origin.idea_family_version),
              ("investigation", case), ("family", edge(case, "InvestigationFamily").family_version),
              ("assessment", edge(case, "PriorResearchInvestigation").assessment_version)]
    # Both case and Idea-family context versions are exact and independently pinned.
    result.append(("family", origin.idea_family_version.family_version))
    result.extend(("source", contribution.source_version) for contribution in origin.idea_version.contributions.select_related("source_version", "source_version__source").order_by("position"))
    seen = set()
    unique = []
    for kind, version in result:
        key = (kind, version.pk)
        if key not in seen:
            seen.add(key)
            unique.append((kind, version))
    return unique


def parent_of(kind, version):
    return version.source if kind == "source" else version.idea if kind == "idea" else version.record


def add_impact(item, kind, pinned, newer, *, actor):
    if pinned.pk == newer.pk:
        return
    # Multiple pinned contexts may cite the same logical family. Keep one notice
    # per new endpoint per Hypothesis; the case's actual selected family comes first.
    if item.correction_impacts.filter(**{f"newer_{kind}": newer}).exists():
        return
    record = ResearchAssociationIdentity.objects.create()
    append(HypothesisCorrectionImpact, actor=actor, record=record,
           hypothesis_version=item, **{f"pinned_{kind}": pinned, f"newer_{kind}": newer})


def record_initial_impacts(item, *, actor):
    for kind, pinned in pinned_upstream(item):
        parent = parent_of(kind, pinned)
        newer = type(pinned).objects.get(**{
            "source" if kind == "source" else "idea" if kind == "idea" else "record": parent,
            "version": parent.latest_version,
        })
        add_impact(item, kind, pinned, newer, actor=actor)


def record_upstream_impacts(kind, newer, *, actor):
    """Called inside an upstream correction transaction under lock_lineage()."""
    # Existing Source/Idea services have a validated username audit argument.
    if isinstance(actor, str):
        username = actor
        actor = SimpleNamespace(get_username=lambda: username)
    new_parent = parent_of(kind, newer)
    for item in visible(HypothesisVersion).order_by("public_id"):
        for pinned_kind, pinned in pinned_upstream(item):
            if pinned_kind == kind and parent_of(kind, pinned).pk == new_parent.pk and pinned.version < newer.version:
                add_impact(item, kind, pinned, newer, actor=actor)


def hypothesis_read(item):
    origin = edge(item, "IdeaHypothesis")
    case_edge = edge(item, "HypothesisInvestigation")
    case = case_edge.investigation_version
    family_edge = edge(case, "InvestigationFamily")
    assessment_edge = edge(case, "PriorResearchInvestigation")
    notices = []
    for impact in item.correction_impacts.order_by("created_at", "public_id"):
        for kind in ("source", "idea", "family", "investigation", "assessment", "association"):
            if getattr(impact, f"newer_{kind}_id") is not None:
                notices.append({"code": "review_needed", "pinned": endpoint(getattr(impact, f"pinned_{kind}")),
                                "newer": endpoint(getattr(impact, f"newer_{kind}")), "impact_version_id": impact.public_id})
    return {
        **envelope(item), "hypothesis_id": item.record.public_id, "hypothesis_version_id": item.public_id,
        "status": "draft", "fields": item.fields, **draft_completeness(item.fields),
        "origin": {"idea": endpoint(origin.idea_version), "association": association_read(origin),
                   "sources": [{"source": endpoint(c.source_version), "contribution_version_id": c.contribution_id}
                               for c in origin.idea_version.contributions.select_related("source_version", "source_version__source").order_by("position")]},
        "research_context": {
            "investigation": endpoint(case), "family": endpoint(family_edge.family_version),
            "assessment": endpoint(assessment_edge.assessment_version),
            "idea_family_association": association_read(origin.idea_family_version),
            "investigation_family_association": association_read(family_edge),
            "investigation_assessment_association": association_read(assessment_edge),
            "hypothesis_investigation_association": association_read(case_edge),
        },
        "upstream_notices": notices, "links": {
            **record_links("hypotheses", item),
            "origin_idea_history": reverse("idea-history", kwargs={"idea_id": origin.idea_version.idea.idea_id}),
            "investigation": record_links("investigations", case)["self"],
            "family": record_links("research-families", family_edge.family_version)["self"],
            "assessment": f"/api/v1/prior-research-assessments/{assessment_edge.assessment_version.record.public_id}/versions/{assessment_edge.assessment_version.version}",
        },
    }


def create_hypothesis(*, actor, idempotency_key, payload):
    def operation(p):
        idea, case, classified = resolve_context(p)
        record = Hypothesis.objects.create()
        item = append(HypothesisVersion, actor=actor, record=record, fields=p["fields"])
        bind_context(actor=actor, payload=p, idea=idea, case=case, classified=classified, item=item)
        record_initial_impacts(item, actor=actor)
        return 201, hypothesis_read(item)
    return execute_write(actor=actor, idempotency_key=idempotency_key, payload=payload, request_name="HypothesisCreate", path="/api/v1/hypotheses", operation=operation)


def correct_hypothesis(*, actor, hypothesis_id, idempotency_key, payload):
    def operation(p):
        record, old = latest(Hypothesis, hypothesis_id, lock=True)
        check_expected(record, p)
        idea, case, classified = resolve_context(p)
        old_origin = edge(old, "IdeaHypothesis")
        old_case = edge(old, "HypothesisInvestigation")
        changed = change_paths(old.fields, p["fields"], "/fields/")
        for key, before, after in (
            ("originating_idea_version_id", old_origin.idea_version_id, idea.pk),
            ("origin_rationale", old_origin.rationale, p["origin_rationale"]),
            ("investigation_version_id", old_case.investigation_version_id, case.pk),
            ("idea_family_binding", old_origin.idea_family_version_id, classified.pk if classified else None),
        ):
            if before != after:
                changed.append("/" + key)
        if not changed:
            return 200, hypothesis_read(old)
        item = append(HypothesisVersion, actor=actor, record=record, predecessor=old, fields=p["fields"],
                      correction_reason=p["correction_reason"], changed_fields=sorted(changed))
        bind_context(actor=actor, payload=p, idea=idea, case=case, classified=classified, item=item, predecessor=old)
        record_initial_impacts(item, actor=actor)
        return 201, hypothesis_read(item)
    return execute_write(actor=actor, idempotency_key=idempotency_key, payload=payload, request_name="HypothesisCorrection", path=f"/api/v1/hypotheses/{hypothesis_id}/corrections", operation=operation)


def get_hypothesis(*, actor, hypothesis_id, version=None):
    require_actor(actor)
    return hypothesis_read(latest(Hypothesis, hypothesis_id, version=version)[1])


def get_hypothesis_history(*, actor, hypothesis_id):
    require_actor(actor)
    record, _ = latest(Hypothesis, hypothesis_id)
    return {"results": [hypothesis_read(item) for item in record.versions.order_by("version")]}


def list_hypotheses(*, actor, query):
    def filter_queryset(qs, q):
        if "originating_idea_id" not in q:
            return qs
        from django.db.models import F
        return qs.filter(versions__version=F("latest_version"), versions__research_associations__kind="IdeaHypothesis",
                         versions__research_associations__idea_version__idea__idea_id=q["originating_idea_id"])
    return paginated(actor=actor, model=Hypothesis, query=query, route="hypotheses", render=hypothesis_read, filter_queryset=filter_queryset)
