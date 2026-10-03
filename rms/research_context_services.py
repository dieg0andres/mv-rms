"""Versioned minimum research context, shared by authenticated APIs and pages."""

from .hypothesis_models import (
    AssessmentExternalReference, Investigation, InvestigationVersion,
    PriorResearchAssessment, PriorResearchAssessmentVersion,
    ResearchAssociation, ResearchAssociationIdentity, ResearchFamily,
    ResearchFamilyVersion, identifier,
)
from .models import IdeaVersion, SourceVersion
from .hypothesis_assessment_links import assessment_link_seal
from .hypothesis_validation import validate_request
from .research_context_common import (
    append, change_paths, check_expected, endpoint, envelope, execute_write,
    field_error, latest, paginated, record_links, require_actor, resolve, visible,
)
from .services import ResourceNotFound, ServiceError


class AssessmentIntegrityError(ServiceError):
    code = "history_integrity_error"
    safe_message = "The saved history could not be verified."
    http_status = 503


def association(kind, *, actor, predecessor=None, rationale=None, **endpoints):
    record = predecessor.record if predecessor else ResearchAssociationIdentity.objects.create(
        public_id=identifier("IFA" if kind == "IdeaFamily" else "RAS"),
        idea_version=endpoints.get("idea_version") if kind == "IdeaFamily" else None,
    )
    return append(
        ResearchAssociation, actor=actor, record=record, predecessor=predecessor,
        public_id=identifier("IFAV" if kind == "IdeaFamily" else "RASV"),
        correction_reason=endpoints.pop("correction_reason", None),
        changed_fields=[] if predecessor is None else ["endpoints", "rationale"],
        kind=kind, rationale=rationale, origin_type="direct" if kind == "IdeaHypothesis" else None,
        **endpoints,
    )


def edge(item, kind):
    try:
        return item.research_associations.get(kind=kind)
    except ResearchAssociation.DoesNotExist as error:
        raise ResourceNotFound from error


def association_read(item):
    pairs = {
        "IdeaFamily": ("idea", "family"), "InvestigationFamily": ("investigation", "family"),
        "PriorResearchInvestigation": ("assessment", "investigation"),
        "HypothesisInvestigation": ("hypothesis", "investigation"), "IdeaHypothesis": ("idea", "hypothesis"),
    }
    if item.kind == "AssessmentRecord":
        target = next(name for name in ("idea", "source", "family", "investigation") if getattr(item, name + "_version_id"))
        first, second = "assessment", target
    else:
        first, second = pairs[item.kind]
    result = {**envelope(item), "kind": item.kind, "from": endpoint(getattr(item, first + "_version")),
              "to": endpoint(getattr(item, second + "_version")), "rationale": item.rationale}
    if item.kind == "IdeaHypothesis":
        result["origin_type"] = "direct"
    return result


def family_read(item):
    return {**envelope(item), "family_id": item.record.public_id, "family_version_id": item.public_id,
            "fields": item.fields, "links": record_links("research-families", item)}


def assessment_read(item):
    associations = list(item.research_associations.filter(kind="AssessmentRecord").order_by("position"))
    ordered_links = []
    for association_item in associations:
        for name, kind in (("source", "source"), ("idea", "idea"), ("family", "research_family"), ("investigation", "investigation")):
            target = getattr(association_item, name + "_version")
            if target is not None:
                ordered_links.append((association_item.position, {"kind": kind, "version_id": endpoint(target)["version_id"]}))
    ordered_links.extend((ref.position, {"kind": "external_document", "reference": ref.reference}) for ref in item.external_references.order_by("position"))
    ordered_links.sort(key=lambda pair: pair[0])
    links = [link for _, link in ordered_links]
    # Fail closed before returning any reconstructed history. This also checks
    # cross-table duplicates/gaps, not merely the list's recomputed hash.
    if ([position for position, _ in ordered_links] != list(range(1, item.link_count + 1))
            or assessment_link_seal(links) != {"link_count": item.link_count, "link_digest": item.link_digest}):
        raise AssessmentIntegrityError
    return {**envelope(item), "assessment_id": item.record.public_id, "assessment_version_id": item.public_id,
            "fields": {**item.fields, "record_links": links},
            "record_associations": [association_read(a) for a in associations],
            "links": {"self": f"/api/v1/prior-research-assessments/{item.record.public_id}/versions/{item.version}"}}


def investigation_read(item):
    family = edge(item, "InvestigationFamily")
    assessment = edge(item, "PriorResearchInvestigation")
    return {**envelope(item), "investigation_id": item.record.public_id, "investigation_version_id": item.public_id,
            "status": "proposed", "fields": item.fields, "family": endpoint(family.family_version),
            "prior_research_assessment": assessment_read(assessment.assessment_version),
            "family_association": association_read(family), "assessment_association": association_read(assessment),
            "links": record_links("investigations", item)}


def resolve_assessment_links(fields):
    models = {"source": (SourceVersion, "source_version"), "idea": (IdeaVersion, "idea_version"),
              "research_family": (ResearchFamilyVersion, "family_version"), "investigation": (InvestigationVersion, "investigation_version")}
    result = []
    for link in fields["record_links"]:
        if link["kind"] == "external_document":
            result.append(("external", link["reference"]))
        else:
            model, key = models[link["kind"]]
            result.append((key, resolve(model, link["version_id"])))
    return result


def save_assessment(*, actor, fields, resolved, predecessor=None, reason=None):
    record = predecessor.record if predecessor else PriorResearchAssessment.objects.create()
    scalar = {key: value for key, value in fields.items() if key != "record_links"}
    changed = change_paths(assessment_read(predecessor)["fields"], fields, "/fields/") if predecessor else []
    item = append(PriorResearchAssessmentVersion, actor=actor, record=record, predecessor=predecessor,
                  correction_reason=reason, changed_fields=changed, fields=scalar,
                  **assessment_link_seal(fields["record_links"]))
    for position, (key, target) in enumerate(resolved, 1):
        if key == "external":
            identity = ResearchAssociationIdentity.objects.create()
            append(AssessmentExternalReference, actor=actor, record=identity, assessment_version=item, reference=target, position=position)
        else:
            association("AssessmentRecord", actor=actor, assessment_version=item, position=position, **{key: target})
    return item


def create_research_family(*, actor, idempotency_key, payload):
    def operation(p):
        record = ResearchFamily.objects.create()
        item = append(ResearchFamilyVersion, actor=actor, record=record, fields={**p["fields"], "risk_review_reference": p["fields"].get("risk_review_reference")})
        return 201, family_read(item)
    return execute_write(actor=actor, idempotency_key=idempotency_key, payload=payload, request_name="FamilyCreate", path="/api/v1/research-families", operation=operation)


def correct_research_family(*, actor, family_id, idempotency_key, payload):
    def operation(p):
        record, old = latest(ResearchFamily, family_id, lock=True)
        check_expected(record, p)
        changed = change_paths(old.fields, p["fields"], "/fields/")
        if not changed:
            return 200, family_read(old)
        item = append(ResearchFamilyVersion, actor=actor, record=record, predecessor=old, fields=p["fields"], correction_reason=p["correction_reason"], changed_fields=changed)
        from .hypothesis_services import record_upstream_impacts
        record_upstream_impacts("family", item, actor=actor)
        return 201, family_read(item)
    return execute_write(actor=actor, idempotency_key=idempotency_key, payload=payload, request_name="FamilyCorrection", path=f"/api/v1/research-families/{family_id}/corrections", operation=operation)


def create_investigation(*, actor, idempotency_key, payload):
    def operation(p):
        family = resolve(ResearchFamilyVersion, p["family_version_id"])
        resolved = resolve_assessment_links(p["prior_research_assessment"])
        assessment = save_assessment(actor=actor, fields=p["prior_research_assessment"], resolved=resolved)
        record = Investigation.objects.create()
        item = append(InvestigationVersion, actor=actor, record=record, fields={**p["fields"], "blocker_text": p["fields"].get("blocker_text")})
        association("InvestigationFamily", actor=actor, investigation_version=item, family_version=family)
        association("PriorResearchInvestigation", actor=actor, investigation_version=item, assessment_version=assessment)
        return 201, investigation_read(item)
    return execute_write(actor=actor, idempotency_key=idempotency_key, payload=payload, request_name="InvestigationCreate", path="/api/v1/investigations", operation=operation)


def correct_investigation(*, actor, investigation_id, idempotency_key, payload):
    def operation(p):
        record, old = latest(Investigation, investigation_id, lock=True)
        check_expected(record, p)
        family = resolve(ResearchFamilyVersion, p["family_version_id"])
        old_family = edge(old, "InvestigationFamily")
        old_assessment_edge = edge(old, "PriorResearchInvestigation")
        old_assessment = old_assessment_edge.assessment_version
        binding = p["prior_research_assessment"]
        assessment = old_assessment
        if binding["mode"] == "existing":
            assessment = resolve(PriorResearchAssessmentVersion, binding["assessment_version_id"])
            if assessment.record_id != old_assessment.record_id:
                field_error("/prior_research_assessment/assessment_version_id")
        else:
            if binding["corrects_assessment_version_id"] != old_assessment.public_id:
                field_error("/prior_research_assessment/corrects_assessment_version_id")
            assessment_record, current_assessment = latest(PriorResearchAssessment, old_assessment.record.public_id, lock=True)
            check_expected(assessment_record, {"expected_latest_version": binding["expected_latest_assessment_version"]})
            if current_assessment.pk != old_assessment.pk:
                field_error("/prior_research_assessment/corrects_assessment_version_id")
            resolved = resolve_assessment_links(binding["fields"])
            if change_paths(assessment_read(old_assessment)["fields"], binding["fields"]):
                assessment = save_assessment(actor=actor, fields=binding["fields"], resolved=resolved, predecessor=old_assessment, reason=binding["correction_reason"])
                from .hypothesis_services import record_upstream_impacts
                record_upstream_impacts("assessment", assessment, actor=actor)
        changed = change_paths(old.fields, p["fields"], "/fields/")
        if old_family.family_version_id != family.pk:
            changed.append("/family_version_id")
        if old_assessment.pk != assessment.pk:
            changed.append("/prior_research_assessment")
        if not changed:
            return 200, investigation_read(old)
        item = append(InvestigationVersion, actor=actor, record=record, predecessor=old, fields=p["fields"], correction_reason=p["correction_reason"], changed_fields=sorted(changed))
        association("InvestigationFamily", actor=actor, predecessor=old_family, correction_reason=p["correction_reason"], investigation_version=item, family_version=family)
        association("PriorResearchInvestigation", actor=actor, predecessor=old_assessment_edge, correction_reason=p["correction_reason"], investigation_version=item, assessment_version=assessment)
        from .hypothesis_services import record_upstream_impacts
        record_upstream_impacts("investigation", item, actor=actor)
        return 201, investigation_read(item)
    return execute_write(actor=actor, idempotency_key=idempotency_key, payload=payload, request_name="InvestigationCorrection", path=f"/api/v1/investigations/{investigation_id}/corrections", operation=operation)


def correct_idea_family_association(*, actor, association_id, idempotency_key, payload):
    def operation(p):
        record, old = latest(ResearchAssociationIdentity, association_id, lock=True)
        check_expected(record, p)
        if old.kind != "IdeaFamily" or old.public_id != p["prior_association_version_id"]:
            field_error("/prior_association_version_id")
        family = resolve(ResearchFamilyVersion, p["family_version_id"])
        if family.pk == old.family_version_id and p["rationale"] == old.rationale:
            return 200, association_read(old)
        item = association("IdeaFamily", actor=actor, predecessor=old, correction_reason=p["correction_reason"], idea_version=old.idea_version, family_version=family, rationale=p["rationale"])
        from .hypothesis_services import record_upstream_impacts
        record_upstream_impacts("association", item, actor=actor)
        return 201, association_read(item)
    return execute_write(actor=actor, idempotency_key=idempotency_key, payload=payload, request_name="IdeaFamilyCorrection", path=f"/api/v1/idea-family-associations/{association_id}/corrections", operation=operation)


def idea_family_read(item):
    if item.kind != "IdeaFamily" or item.record.idea_version_id != item.idea_version_id:
        raise ResourceNotFound
    # Apply endpoint visibility before producing metadata or navigation links.
    resolve(IdeaVersion, item.idea_version.idea_version_id)
    resolve(ResearchFamilyVersion, item.family_version.public_id)
    return {**association_read(item), "links": record_links("idea-family-associations", item)}


def get_idea_family_association(*, actor, association_id, version=None):
    require_actor(actor)
    return idea_family_read(latest(ResearchAssociationIdentity, association_id, version=version)[1])


def get_idea_family_association_history(*, actor, association_id):
    require_actor(actor)
    record, item = latest(ResearchAssociationIdentity, association_id)
    idea_family_read(item)
    return {"results": [idea_family_read(v) for v in visible(ResearchAssociation).filter(record=record).order_by("version")]}


def get_idea_family_for_idea(*, actor, idea_version_id):
    require_actor(actor)
    query = validate_request("IdeaFamilyQuery", {"idea_version_id": idea_version_id})
    idea = resolve(IdeaVersion, query["idea_version_id"])
    try:
        record = visible(ResearchAssociationIdentity).get(idea_version=idea)
    except ResearchAssociationIdentity.DoesNotExist as error:
        raise ResourceNotFound from error
    return get_idea_family_association(actor=actor, association_id=record.public_id)


def get_research_family(*, actor, family_id, version=None):
    require_actor(actor)
    return family_read(latest(ResearchFamily, family_id, version=version)[1])


def get_investigation(*, actor, investigation_id, version=None):
    require_actor(actor)
    return investigation_read(latest(Investigation, investigation_id, version=version)[1])


def get_prior_research_assessment(*, actor, assessment_id, version):
    require_actor(actor)
    return assessment_read(latest(PriorResearchAssessment, assessment_id, version=version)[1])


def get_research_family_history(*, actor, family_id):
    require_actor(actor)
    record, _ = latest(ResearchFamily, family_id)
    return {"results": [family_read(v) for v in record.versions.order_by("version")]}


def get_investigation_history(*, actor, investigation_id):
    require_actor(actor)
    record, _ = latest(Investigation, investigation_id)
    return {"results": [investigation_read(v) for v in record.versions.order_by("version")]}


def list_research_families(*, actor, query):
    return paginated(actor=actor, model=ResearchFamily, query=query, route="research-families", render=family_read)


def list_investigations(*, actor, query):
    return paginated(actor=actor, model=Investigation, query=query, route="investigations", render=investigation_read)
