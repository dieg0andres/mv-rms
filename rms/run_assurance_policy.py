"""Default-off policy backed only by trusted, invented fixture configuration."""

from collections.abc import Mapping
from datetime import datetime

from django.conf import settings
from django.utils.timezone import is_aware, now

from .research_context_common import Forbidden, wire
from .research_context_services import edge
from .run_result_models import RunRetry
from .services import ResourceNotFound
from .test_plan_models import TestPlanAssociation


def grant_key(actor, result, action):
    return (str(actor.pk), str(result.pk), result.row_digest, action)


def provenance_key(record):
    return (record._meta.label_lower, str(record.pk), wire(record.created_at),
            getattr(record, 'row_digest', getattr(record, 'content_sha256', None)), record.created_by)


def design_records(result):
    """Only pinned evidence/design rows; do not traverse logical latest pointers."""
    plan = result.run.plan_version
    yield plan
    for association in plan.associations.select_related('hypothesis_version', 'criterion_version', 'data_requirement_version'):
        yield association
        if association.criterion_version_id:
            yield association.criterion_version
        if association.data_requirement_version_id:
            yield association.data_requirement_version
    yield from plan.data_checks.filter(created_at__lte=result.recorded_at)
    hypothesis = plan.associations.get(kind='HypothesisPlan').hypothesis_version
    yield hypothesis
    origin = edge(hypothesis, 'IdeaHypothesis')
    idea = origin.idea_version
    idea_family = origin.idea_family_version
    case_edge = edge(hypothesis, 'HypothesisInvestigation')
    case = case_edge.investigation_version
    family_edge = edge(case, 'InvestigationFamily')
    assessment_edge = edge(case, 'PriorResearchInvestigation')
    assessment = assessment_edge.assessment_version
    yield from (origin, idea, idea_family, idea_family.family_version, case_edge, case,
                family_edge, family_edge.family_version, assessment_edge, assessment)
    yield from (item.source_version for item in idea.contributions.select_related('source_version'))
    yield from assessment.external_references.all()
    for reference in assessment.research_associations.filter(kind='AssessmentRecord').select_related(
            'source_version', 'idea_version', 'family_version', 'investigation_version'):
        yield reference
        yield (reference.source_version or reference.idea_version or reference.family_version or reference.investigation_version)


def _independent(actor_id, result):
    bindings = getattr(settings, 'RMS_SYNTHETIC_ASSURANCE_PROVENANCE', {})
    if not isinstance(bindings, Mapping):
        return False
    try:
        for record in design_records(result):
            bound_actor = bindings.get(provenance_key(record))
            if not isinstance(bound_actor, str) or not bound_actor or bound_actor == actor_id:
                return False
    except (ResourceNotFound, TestPlanAssociation.DoesNotExist):
        return False
    run = result.run
    seen = set()
    while run.pk not in seen:
        seen.add(run.pk)
        existing_results = run.result_versions.filter(version__lte=result.version) if run.pk == result.run_id else run.result_versions.all()
        if (not run.reporter_id or run.reporter_id == actor_id or
                run.lifecycle_events.filter(actor_id__in=('', actor_id)).exists() or
                existing_results.filter(actor_id__in=('', actor_id)).exists()):
            return False
        retry = RunRetry.objects.filter(successor=run).select_related('predecessor').first()
        if retry is None:
            return True
        if (not retry.actor_id or retry.actor_id == actor_id or
                retry.predecessor.plan_version_id != result.run.plan_version_id):
            return False
        run = retry.predecessor
    return False


def require_capability(action, actor, result):
    grants = getattr(settings, 'RMS_SYNTHETIC_ASSURANCE_GRANTS', {})
    expires_at = grants.get(grant_key(actor, result, action)) if isinstance(grants, Mapping) else None
    if not isinstance(expires_at, datetime) or not is_aware(expires_at) or expires_at <= now():
        raise Forbidden
    if actor.groups.filter(name='founder_viewer').exists():
        raise Forbidden
    if action == 'review' and not _independent(str(actor.pk), result):
        raise Forbidden
