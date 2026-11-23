"""Exact screening, manual prior research and fail-closed synthetic intake."""

import re

from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .hypothesis_models import InvestigationVersion, ResearchAssociationIdentity, ResearchFamilyVersion
from .intake_models import IntakeHypothesisBinding, IntakeSourceAssessment, ResearchIntake, ResearchIntakeVersion
from .models import Idea, IdeaVersion, SourceVersion
from .research_context_common import Forbidden, StaleVersion, append, endpoint, envelope, execute_write, field_error, require_actor, resolve, visible
from .research_context_services import assessment_read, association, edge
from .services import ResourceNotFound

PRIORITY = (
    "economic_rationale", "falsifiability", "material_distinctness", "information_value",
    "data_feasibility", "reproducibility", "implementation_realism", "effort_cost",
    "december_relevance", "rationale",
)
SOURCE_ASSESSMENT = ("methodology_quality", "claim_used", "contrary_evidence", "limitations")
CLOSURE = ("reason", "gate_reached", "evidence_completeness", "unresolved_mechanism", "reusable_lesson")
INPUT_FIELDS = (
    "idea_version_id", "family_version_id", "distinctness", "family_rationale", "outcome",
    "investigation_version_id", "expected_latest_version", "correction_reason",
)


def _text(value, path, limit=2000):
    if not isinstance(value, str) or not value.strip() or len(value) > limit or "\x00" in value:
        field_error(path, "invalid_input")
    return value.strip()


def _fields(values, keys, path):
    if not isinstance(values, dict) or set(values) != set(keys):
        field_error(path, "invalid_input")
    return {key: _text(values[key], f"{path}/{key}") for key in keys}


def validate_intake(_name, payload):
    if not isinstance(payload, dict) or set(payload) - {*INPUT_FIELDS, "priority", "source_assessments", "closure"}:
        field_error("/", "invalid_input")
    for key in ("idea_version_id", "family_version_id", "distinctness", "family_rationale", "outcome"):
        _text(payload.get(key), f"/{key}")
    expected = payload.get("expected_latest_version")
    if type(expected) is not int or expected < 0:
        field_error("/expected_latest_version", "invalid_input")
    if expected:
        _text(payload.get("correction_reason"), "/correction_reason")
    elif payload.get("correction_reason") is not None:
        field_error("/correction_reason", "invalid_input")
    if payload["distinctness"] not in {"candidate", "related_variant"}:
        field_error("/distinctness", "invalid_input")
    if payload["outcome"] == "early_closed":
        _fields(payload.get("closure"), CLOSURE, "/closure")
        if {"investigation_version_id", "source_assessments", "priority"} & payload.keys():
            field_error("/outcome", "invalid_input")
    elif payload["outcome"] == "ready":
        _text(payload.get("investigation_version_id"), "/investigation_version_id", 42)
        _fields(payload.get("priority"), PRIORITY, "/priority")
        sources = payload.get("source_assessments")
        if not isinstance(sources, dict) or not 1 <= len(sources) <= 100 or "closure" in payload:
            field_error("/source_assessments", "invalid_input")
        for key, values in sources.items():
            _text(key, "/source_assessments", 40)
            _fields(values, SOURCE_ASSESSMENT, "/source_assessments")
    else:
        field_error("/outcome", "invalid_input")
    return payload


def _rights(source):
    grants = getattr(settings, "RMS_INTAKE_SYNTHETIC_RIGHTS", {})
    grant = grants.get(source.source_version_id) if isinstance(grants, dict) else None
    if not isinstance(grant, dict):
        return None
    reference = grant.get("reference")
    expiry = grant.get("expires_at")
    try:
        expiry = parse_datetime(expiry) if isinstance(expiry, str) else None
    except (ValueError, OverflowError):
        return None
    if (not isinstance(reference, str) or not re.fullmatch(r"fixture:[A-Za-z0-9._:-]{1,110}", reference)
            or not expiry or timezone.is_naive(expiry) or expiry <= timezone.now()
            or grant.get("operation") != "synthetic_intake_assessment"
            or grant.get("sha256") != source.content_sha256):
        return None
    return reference, expiry


def _head(instance):
    owner = instance.idea if isinstance(instance, IdeaVersion) else getattr(instance, "source", None) or instance.record
    return instance.version == owner.latest_version


def _prior(case, family):
    if not _head(case) or edge(case, "InvestigationFamily").family_version_id != family.pk:
        field_error("/investigation_version_id", "stale_or_mismatched")
    if case.fields.get("blocker_text"):
        field_error("/investigation_version_id", "unresolved_case_blocker")
    prior = edge(case, "PriorResearchInvestigation").assessment_version
    if not _head(prior):
        field_error("/investigation_version_id", "stale_prior_research")
    manual = assessment_read(prior)["fields"]
    query_time = parse_datetime(manual["query_time"])
    if (not query_time or timezone.is_naive(query_time) or query_time > timezone.now()
            or (manual["finding"] != "no_relevant_work_found" and not manual["record_links"])):
        field_error("/investigation_version_id", "incomplete_prior_research")
    for link in prior.research_associations.filter(kind="AssessmentRecord"):
        target = next(getattr(link, name) for name in ("idea_version", "source_version", "family_version", "investigation_version") if getattr(link, name + "_id"))
        if not _head(target):
            field_error("/investigation_version_id", "stale_prior_research")
        if isinstance(target, SourceVersion) and not _rights(target):
            field_error("/investigation_version_id", "missing_or_stale_rights")
    return prior


def _idea(stable_id):
    try:
        return visible(Idea).get(idea_id=stable_id)
    except Idea.DoesNotExist as error:
        raise ResourceNotFound from error


def save_intake(*, actor, idea_id, idempotency_key, payload):
    require_actor(actor, write=True)
    if actor.groups.filter(name="founder_viewer").exists():
        raise Forbidden

    def operation(values):
        idea = _idea(idea_id)
        item = resolve(IdeaVersion, values["idea_version_id"])
        if item.idea_id != idea.pk or not _head(item):
            field_error("/idea_version_id", "stale_or_mismatched")
        identity = visible(ResearchIntake).filter(idea=idea).first()
        if (identity.latest_version if identity else 0) != values["expected_latest_version"]:
            raise StaleVersion
        previous = identity.versions.get(version=identity.latest_version) if identity else None
        family = resolve(ResearchFamilyVersion, values["family_version_id"])
        if not _head(family):
            field_error("/family_version_id", "stale_or_mismatched")
        if previous and previous.fields["distinctness"] == "related_variant" and (
            previous.family_binding.family_version.record_id != family.record_id or values["distinctness"] != "related_variant"
        ):
            field_error("/distinctness", "related_variant_required")
        if values["distinctness"] != "related_variant" and visible(ResearchAssociationIdentity).filter(
            versions__kind="IdeaFamily", versions__family_version__record_id=family.record_id,
        ).exclude(idea_version__idea=idea).exists():
            if not previous or previous.fields["distinctness"] != "candidate" or previous.family_binding.family_version.record_id != family.record_id:
                field_error("/distinctness", "related_variant_required")
        family_identity = visible(ResearchAssociationIdentity).filter(idea_version=item).first()
        binding = family_identity.versions.get(version=family_identity.latest_version) if family_identity else None
        if binding and binding.family_version_id != family.pk:
            field_error("/family_version_id", "revise_exact_classification_first")
        case, assessments = None, []
        fields = {key: values[key] for key in ("distinctness", "family_rationale")}
        if values["outcome"] == "ready":
            if item.workflow_status == "rejected":
                field_error("/idea_version_id", "idea_rejected")
            case = resolve(InvestigationVersion, values["investigation_version_id"])
            _prior(case, family)
            if visible(ResearchIntakeVersion).filter(investigation_version__record=case.record).exclude(record__idea=idea).exists():
                field_error("/investigation_version_id", "stale_or_mismatched")
            contributions = list(item.contributions.select_related("source_version__source"))
            supplied = values["source_assessments"]
            if {row.contribution_id for row in contributions} != set(supplied):
                field_error("/source_assessments", "exact_contributions_required")
            for row in contributions:
                rights = _rights(row.source_version) if _head(row.source_version) else None
                if not rights:
                    field_error("/source_assessments", "missing_or_stale_rights")
                assessments.append((row, supplied[row.contribution_id], rights))
            fields["priority"] = values["priority"]
        else:
            fields["closure"] = values["closure"]
        if not identity:
            identity = ResearchIntake.objects.create(idea=idea)
        if not binding:
            binding = association("IdeaFamily", actor=actor, idea_version=item, family_version=family, rationale=values["family_rationale"])
        saved = append(
            ResearchIntakeVersion, actor=actor, record=identity, predecessor=previous,
            correction_reason=values.get("correction_reason"),
            changed_fields=["/screening"] if previous else [], state=values["outcome"],
            idea_version=item, family_binding=binding, investigation_version=case, fields=fields,
            assessment_count=len(assessments),
        )
        for contribution, narrative, rights in assessments:
            IntakeSourceAssessment.objects.create(intake_version=saved, contribution=contribution,
                                                  fields=narrative, rights_reference=rights[0], rights_expires_at=rights[1])
        return 201, {"stable_id": identity.public_id, "version_id": saved.public_id, "version": saved.version}
    return execute_write(actor=actor, idempotency_key=idempotency_key, payload=payload, request_name="Intake",
                         path=f"/api/v1/ideas/{idea_id}/intake", operation=operation, validate=validate_intake)


def _check_progress(item):
    case = item.investigation_version
    binding = item.family_binding
    if (item.state != "ready" or not _head(item) or not _head(item.idea_version)
            or not _head(binding) or not _head(binding.family_version)):
        field_error("/intake_version_id", "missing_or_stale_intake")
    _prior(case, binding.family_version)
    rows = list(item.source_assessments.select_related("contribution__source_version__source"))
    if not rows or len(rows) != item.assessment_count:
        field_error("/intake_version_id", "missing_source_assessments")
    for row in rows:
        source = row.contribution.source_version
        if not _head(source) or _rights(source) != (row.rights_reference, row.rights_expires_at):
            field_error("/intake_version_id", "missing_or_stale_rights")


def authorize_hypothesis_intake(*, actor, version_id, idea, case, binding, predecessor=None):
    require_actor(actor, write=True)
    if version_id is None:
        if (visible(ResearchIntake).filter(idea_id=idea.idea_id).exists()
                or visible(ResearchIntakeVersion).filter(investigation_version__record=case.record).exists()
                or (predecessor and IntakeHypothesisBinding.objects.filter(hypothesis_version=predecessor).exists())):
            field_error("/intake_version_id", "missing_or_stale_intake")
        return None
    if actor.groups.filter(name="founder_viewer").exists():
        raise Forbidden
    item = resolve(ResearchIntakeVersion, version_id)
    if item.idea_version_id != idea.pk or item.investigation_version_id != case.pk or not binding or item.family_binding_id != binding.pk:
        field_error("/intake_version_id", "stale_or_mismatched")
    if predecessor:
        old = IntakeHypothesisBinding.objects.filter(hypothesis_version=predecessor).first()
        if old and old.intake_version.record_id != item.record_id:
            field_error("/intake_version_id", "stale_or_mismatched")
    _check_progress(item)
    return item


def check_plan_intake(*, actor, hypothesis):
    require_actor(actor, write=True)
    linked = IntakeHypothesisBinding.objects.filter(hypothesis_version=hypothesis).first()
    origin = edge(hypothesis, "IdeaHypothesis")
    case = edge(hypothesis, "HypothesisInvestigation").investigation_version
    authorize_hypothesis_intake(actor=actor, version_id=linked.intake_version.public_id if linked else None,
                                idea=origin.idea_version, case=case, binding=origin.idea_family_version)


def read_intake(*, actor, idea_id):
    require_actor(actor)
    idea = _idea(idea_id)
    identity = visible(ResearchIntake).filter(idea=idea).first()
    if identity is None:
        return {"results": [], "latest_version": 0}
    results = []
    versions = list(visible(ResearchIntakeVersion).filter(record=identity).order_by("version"))
    for index, item in enumerate(versions):
        case = item.investigation_version
        sources = []
        for row in item.source_assessments.select_related("contribution__source_version").order_by("contribution__position"):
            source = row.contribution.source_version
            if _rights(source) == (row.rights_reference, row.rights_expires_at):
                sources.append({"assessment_version_id": row.public_id, "source": endpoint(source),
                                "contribution_id": row.contribution.contribution_id, "fields": row.fields,
                                "rights_reference": row.rights_reference, "rights_expires_at": row.rights_expires_at.isoformat()})
        results.append({**envelope(item), "idea": endpoint(item.idea_version), "family": endpoint(item.family_binding.family_version),
                        "family_binding": endpoint(item.family_binding), "investigation": endpoint(case) if case else None,
                        "prior_research": endpoint(edge(case, "PriorResearchInvestigation").assessment_version) if case else None,
                        "fields": item.fields, "source_assessments": sources, "credit": False,
                        "superseded_by": versions[index + 1].public_id if index + 1 < len(versions) else None,
                        "downstream_hypotheses": [endpoint(row.hypothesis_version) for row in item.hypothesis_bindings.select_related("hypothesis_version__record")]})
    return {"results": results, "latest_version": identity.latest_version}


def form_context(*, actor, idea_id):
    require_actor(actor)
    if not actor.groups.filter(name="editor").exists() or actor.groups.filter(name="founder_viewer").exists():
        return None
    idea = _idea(idea_id)
    item = idea.versions.get(version=idea.latest_version)
    rows = list(item.contributions.select_related("source_version__source"))
    contributions = [{"id": row.contribution_id, "source": row.source_version.source_version_id} for row in rows
                     if _head(row.source_version) and _rights(row.source_version)]
    return {"idea_version_id": item.idea_version_id, "contributions": contributions if len(contributions) == len(rows) else []}
