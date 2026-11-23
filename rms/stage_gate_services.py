"""Fixture-only freeze/release recording; no grant, usable release, or dispatch."""

import re

from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from . import test_plan_models as plans
from .intake_models import IntakeHypothesisBinding
from .intake_services import authorize_hypothesis_intake
from .research_context_common import Forbidden, StaleVersion, execute_write, field_error, require_actor, wire
from .research_context_services import edge
from .services import ResourceNotFound
from .stage_gate_models import SyntheticGateEvent
from .test_plan_services import digest

POLICY = "fixture:MAU-168:v1"
TRANSITIONS = {"freeze": ((None,), "frozen"), "release": (("frozen",), "released"),
               "invalidate": (("frozen", "released"), "invalidated")}
TOKEN = re.compile(r"fixture:[a-zA-Z0-9._:-]{1,110}")
SHA256 = re.compile(r"[a-f0-9]{64}")


def _matches(pattern, value):
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def _validate(_name, payload):
    if not isinstance(payload, dict):
        field_error("/", "invalid_input")
    operation, sequence = payload.get("operation"), payload.get("expected_sequence")
    if not isinstance(operation, str) or operation not in TRANSITIONS:
        field_error("/operation", "invalid_input")
    if type(sequence) is not int or not 0 <= sequence <= 3:
        field_error("/expected_sequence", "invalid_input")
    keys = {"operation", "expected_sequence"}
    if operation == "invalidate":
        reason = payload.get("reason")
        if (set(payload) != keys | {"reason"} or not isinstance(reason, str)
                or not reason.strip() or len(reason) > 500 or "\x00" in reason):
            field_error("/reason", "invalid_input")
        return payload | {"reason": reason.strip()}
    claim = payload.get("authority")
    if (set(payload) != keys | {"authority"} or not isinstance(claim, dict)
            or set(claim) != {"reference", "revision", "digest"} or not _matches(TOKEN, claim["reference"])
            or type(claim["revision"]) is not int or claim["revision"] < 1 or not _matches(SHA256, claim["digest"])):
        field_error("/authority", "invalid_input")
    return payload


def _mapping(value):
    return value if isinstance(value, dict) else {}


def _access(*, actor, plan_id, write=False):
    require_actor(actor, write=write)
    fixture = _mapping(_mapping(getattr(settings, "RMS_SYNTHETIC_STAGE_GATES", None)).get(plan_id))
    actor_id = str(actor.pk)
    operators = fixture.get("operators")
    readers = fixture.get("readers")
    can_write = (isinstance(operators, list) and actor_id in operators
                 and not actor.groups.filter(name="founder_viewer").exists())
    if not can_write and not (isinstance(readers, list) and actor_id in readers):
        raise ResourceNotFound
    if write and not can_write:
        raise Forbidden
    return fixture


def can_view_gate(*, actor, plan_id):
    try:
        _access(actor=actor, plan_id=plan_id)
    except (Forbidden, ResourceNotFound):
        return False
    return True


def can_write_gate(*, actor, plan_id):
    try:
        _access(actor=actor, plan_id=plan_id, write=True)
    except (Forbidden, ResourceNotFound):
        return False
    return True


def _plan(plan_id, version_id):
    try:
        return plans.TestPlanVersion.objects.select_related("record").get(
            public_id=version_id, record__public_id=plan_id, record__synthetic=True,
            classification="synthetic", authority_reference=plans.AUTHORITY_REFERENCE,
        )
    except plans.TestPlanVersion.DoesNotExist as error:
        raise ResourceNotFound from error


def _intake(actor, plan):
    if plan.version != plan.record.latest_version:
        raise StaleVersion
    hypothesis = plan.associations.get(kind="HypothesisPlan").hypothesis_version
    if hypothesis.version != hypothesis.record.latest_version:
        raise StaleVersion
    pinned = IntakeHypothesisBinding.objects.filter(hypothesis_version=hypothesis).first()
    if pinned is None:
        field_error("/intake", "missing_or_stale_intake")
    origin = edge(hypothesis, "IdeaHypothesis")
    case = edge(hypothesis, "HypothesisInvestigation").investigation_version
    intake = authorize_hypothesis_intake(actor=actor, version_id=pinned.intake_version.public_id,
                                         idea=origin.idea_version, case=case, binding=origin.idea_family_version)
    if intake.fields.get("distinctness") != "candidate":
        field_error("/intake", "not_a_distinct_candidate")
    return hypothesis, case, intake


def _scope(plan, hypothesis, case, intake, artifacts):
    return {"plan_version_id": plan.public_id, "plan_digest": plan.row_digest,
            "hypothesis_version_id": hypothesis.public_id, "case_version_id": case.public_id,
            "intake_version_id": intake.public_id, "intake_digest": intake.row_digest,
            "config_digest": plan.config_digest, "profile_link_digest": plan.link_digest, **artifacts}


def _active_interval(record, now):
    try:
        start, end = (parse_datetime(record[key]) for key in ("effective_at", "expires_at"))
        return (start is not None and end is not None and timezone.is_aware(start)
                and timezone.is_aware(end) and start <= now < end)
    except (KeyError, TypeError, ValueError, OverflowError):
        return False


def _current_record(record, *, operation, scope, now, status, extra, error):
    required = {"reference", "revision", "policy", "status", "operation", "scope", "effective_at", "expires_at"}
    if (set(record) != required | set(extra) or record.get("scope") != scope or record.get("operation") != operation
            or record.get("policy") != POLICY or record.get("status") != status
            or not _matches(TOKEN, record.get("reference")) or type(record.get("revision")) is not int
            or record["revision"] < 1 or not _active_interval(record, now)
            or any(record[key] != value for key, value in extra.items())):
        field_error("/" + error, "missing_or_stale_" + error)
    return record | {"digest": digest(record)}


def _bindings(fixture, *, actor_id, operation, scope, now):
    authority = _current_record(_mapping(_mapping(fixture.get("authority")).get(operation)),
                                operation=operation, scope=scope, now=now, status="approved", extra={}, error="authority")
    rights = _current_record(_mapping(_mapping(fixture.get("rights")).get(operation)),
                             operation=operation, scope=scope, now=now, status="allowed",
                             extra={"principal": actor_id, "purpose": "synthetic_gate_only"}, error="rights")
    return authority, rights


def _serialize(event):
    return {"event_id": event.public_id, "sequence": event.sequence, "operation": event.operation,
            "recorded_state": event.recorded_state, "predecessor_event_id": event.predecessor.public_id if event.predecessor_id else None,
            "intake_version_id": event.intake_version.public_id, "recorded_at": wire(event.recorded_at),
            "actor_id": event.actor_id, "authority": event.authority, "rights": event.rights,
            "impact_reason": event.impact_reason}


def read_gate(*, actor, plan_id, version_id):
    _access(actor=actor, plan_id=plan_id)
    plan = _plan(plan_id, version_id)
    events = list(SyntheticGateEvent.objects.filter(plan_version=plan).select_related("predecessor", "intake_version").order_by("sequence"))
    last = events[-1] if events else None
    return {"plan_version_id": plan.public_id, "sequence": last.sequence if last else 0,
            "recorded_state": last.recorded_state if last else "unrecorded", "events": [_serialize(event) for event in events]}


def record_gate(*, actor, plan_id, version_id, idempotency_key, payload):
    _access(actor=actor, plan_id=plan_id, write=True)
    _plan(plan_id, version_id)

    def operation(values):
        fixture = _access(actor=actor, plan_id=plan_id, write=True)
        plan = _plan(plan_id, version_id)
        last = SyntheticGateEvent.objects.filter(plan_version=plan).order_by("-sequence").first()
        sequence = last.sequence if last else 0
        if sequence != values["expected_sequence"]:
            raise StaleVersion
        action = values["operation"]
        state = last.recorded_state if last else None
        before, after = TRANSITIONS[action]
        if state not in before:
            field_error("/operation", "invalid_transition")
        now = timezone.now()
        authority = rights = None
        if action == "invalidate":
            intake = last.intake_version
        else:
            hypothesis, case, intake = _intake(actor, plan)
            if case.fields.get("blocker_text") is not None or fixture.get("blockers") != []:
                field_error("/blockers", "unresolved_blockers")
            artifacts = _mapping(fixture.get("artifacts"))
            if set(artifacts) != {"code_sha256", "data_sha256"} or not all(_matches(SHA256, value) for value in artifacts.values()):
                field_error("/artifacts", "missing_exact_artifacts")
            scope = _scope(plan, hypothesis, case, intake, artifacts)
            authority, rights = _bindings(fixture, actor_id=str(actor.pk), operation=action, scope=scope, now=now)
            if any(authority[key] != value for key, value in values["authority"].items()):
                field_error("/authority", "missing_or_stale_authority")
            if action == "release":
                frozen = _bindings(fixture, actor_id=last.actor_id, operation="freeze", scope=scope, now=now)
                if frozen != (last.authority, last.rights):
                    field_error("/freeze", "invalidated_freeze")
        event = SyntheticGateEvent.objects.create(
            plan_version=plan, intake_version=intake, predecessor=last, sequence=sequence + 1, operation=action,
            recorded_state=after, authority=authority, rights=rights, impact_reason=values.get("reason", ""),
            actor_id=str(actor.pk), recorded_at=now,
        )
        return 201, {"stable_id": plan.public_id, "event_id": event.public_id, "sequence": event.sequence,
                     "recorded_state": event.recorded_state}

    return execute_write(actor=actor, idempotency_key=idempotency_key, payload=payload, request_name="SyntheticGate",
                         path=f"/api/v1/test-plans/{plan_id}/versions/{version_id}/synthetic-gates",
                         operation=operation, validate=_validate)
