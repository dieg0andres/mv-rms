"""Server-rendered browser adapters for Backend-owned record services."""

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from urllib.parse import urlencode, urlsplit
from importlib import import_module
from uuid import uuid4

from django.http import HttpResponseRedirect
from django.db import DatabaseError
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect

from .services import ServiceError, ResourceNotFound, get_idea, idea_history, idea_detail
from .permissions import has_rms_write_access

from django.conf import settings

from django.template.response import TemplateResponse

from .views import RmsPage
from .api import PUBLIC_ID_RE, SOURCE_ID_RE


NAVIGATION = (
    ("home", "Home", "/"),
    ("sources", "Sources", "/sources"),
    ("ideas", "Ideas", "/ideas"),
    ("hypotheses", "Hypotheses", "/hypotheses"),
    ("context", "Research context", "/research-context"),
)

SCHEMA_COMMIT = "aab6d6dfde13fe03f184292f197ed3a56ce00b9d"
SCHEMA_PATH = "rms/hypothesis_schema.json"
SCHEMA_SHA256 = "8a2ee1204b3d54647010254939bee3fabf49d5c2a1edae25a7e6be010726aaea"

HYPOTHESIS_GROUPS = (
    ("Claim and rationale", ("title", "claim", "claim_basis", "economic_rationale", "expected_opportunity", "persistence_argument", "competing_explanations", "falsification_condition")),
    ("Universe and signal", ("market", "universe", "direction", "signal", "information_availability", "decision_schedule")),
    ("Entry and exit", ("entry_conditions", "execution_timing", "exit_conditions", "exit_precedence")),
    ("Duration", ("effect_horizon", "maximum_holding_period")),
    ("Sizing", ("sizing_method", "sizing_basis", "sizing_rule", "exposure_limits")),
    ("Benchmark and limitations", ("implementation_assumptions", "intended_benchmark_name", "intended_benchmark_definition", "intended_benchmark_rationale", "research_limitations")),
)

FIELD_HELP = {
    "claim": "A measurable proposition, not an observed research result. Name units for another measure.",
    "claim_basis": "Choose gross return, net return, or another measure explicitly. Net-return costs belong in implementation assumptions.",
    "economic_rationale": "Describe the economic mechanism without claiming that it has been validated.",
    "expected_opportunity": "Describe the proposed opportunity and practical constraints, not observed benefit.",
    "persistence_argument": "Explain why the effect might persist and what could eliminate it.",
    "competing_explanations": "Identify alternatives and confounds; state the limits of the review.",
    "falsification_condition": "Describe evidence that would undermine the claim and what would remain inconclusive. A losing exit is not itself falsification.",
    "universe": "Specify coverage, instruments, exclusions and when membership is determined.",
    "signal": "Define the observation, inputs, lookback, units and frequency. This description is not executed.",
    "information_availability": "Distinguish event time from when inputs become knowable, including delays and revisions.",
    "decision_schedule": "Specify evaluation timing, time zone and calendar or session convention.",
    "entry_conditions": "Describe triggers, eligibility, re-entry, repeated signals and position-state filters.",
    "execution_timing": "State intended timing relative to decisions and available information; no fill is assumed.",
    "exit_conditions": "Describe closing rules and explicitly explain unused categories; no default stop is inserted.",
    "exit_precedence": "Explain coincident exits and the holding limit; unknown ordering remains a limitation.",
    "quantity": "Positive finite decimal text, not a floating-point measurement. No numerical default.",
    "unit": "Read the duration unit together with its counting convention; do not assume a session or bar calendar.",
    "start_anchor": "Specify the starting event independently for effect horizon and holding period.",
    "counting_convention": "Explain how the entry session or bar is counted.",
    "calendar": "For trading sessions, explicitly identify the calendar. No exchange calendar is supplied.",
    "bar_definition": "For bars, specify bar construction and duration.",
    "event_condition": "Describe the event; RMS does not execute the expression.",
    "if_event_never_occurs": "Explain what happens if the holding-exit event never occurs.",
    "sizing_method": "A proposed method description, not an implemented calculator.",
    "sizing_basis": "Name the quantity, denominator, measurement time and currency where relevant.",
    "sizing_rule": "Specify parameters, units, rounding, rebalancing and simultaneous signals.",
    "exposure_limits": "State proposed position and portfolio constraints; no universal limit is supplied.",
    "implementation_assumptions": "Record unresolved costs, liquidity, execution, borrow, funding and data assumptions. Final models await a Test Plan.",
    "intended_benchmark_name": "Intended benchmark only; a future Test Plan fixes the evaluation benchmark.",
    "intended_benchmark_definition": "Specify comparison window, exposure, basis, currency and rebalancing; a ticker alone is insufficient.",
    "intended_benchmark_rationale": "Explain why the intended comparison fits and what it does not control for.",
    "research_limitations": "Record uncertainty. Draft complete does not mean approved, validated, qualified or ready to trade.",
    "originating_idea_version_id": "Choose an authorized exact Idea version. Its content remains a read-only reference, not an automatic copy.",
    "investigation_version_id": "Explicitly select an exact Research case version. Its state remains proposed.",
    "origin_rationale": "Explain this origin, including use of rejected or superseded Ideas. No research progression is approved.",
    "association_version_id": "Select the exact existing Idea-family association; never silently replace it.",
    "family_version_id": "Explicitly choose an exact Research family version; no grouping is inferred.",
    "owner_role": "A descriptive role label, not a grant of system access.",
    "query_scope": "What did you actually check? State the bounded synthetic scope.",
    "query_time": "Actual reviewer-entered review time in UTC, separate from server save time.",
    "policy_version": "Accepted section-5 procedure reference only, not a successful review or exception.",
    "result_watermark": "Identify the exact records or dated review boundary actually inspected.",
    "finding": "Choose a finding explicitly. No relevant work found applies only to the checked scope.",
    "limitations": "State the limitations of the manual prior-research review; an exhaustive search is not implied.",
    "record_links": "Exact inspected-version references as JSON, or an explicit [] if none were available. External documents are labeled references. This preview does not parse or save links.",
    "expected_latest_version": "Server-confirmed version on which this proposed correction is based; no silent stale overwrite.",
    "correction_reason": "Explain the revision. Older content and exact associations must remain distinct.",
}


class SchemaUnavailable(ValueError):
    pass


def read_navigation_schema(path=None):
    source = Path(path) if path is not None else Path(settings.BASE_DIR) / SCHEMA_PATH
    try:
        content = source.read_bytes()
    except OSError as error:
        raise SchemaUnavailable("The pinned schema is not present in this checkout.") from error
    if sha256(content).hexdigest() != SCHEMA_SHA256:
        raise SchemaUnavailable("The schema does not match the receipted identity.")
    return json.loads(content)


def _schema_shape(schema, definition):
    if "$ref" in definition:
        return _schema_shape(schema, schema["$defs"][definition["$ref"].split("/")[-1]])
    variants = definition.get("allOf") or definition.get("oneOf")
    if not variants:
        return definition
    shapes = [_schema_shape(schema, variant) for variant in variants]
    properties = {}
    required = set(shapes[0].get("required", ()))
    for shape in shapes:
        properties.update(shape.get("properties", {}))
        if "oneOf" in definition:
            required.intersection_update(shape.get("required", ()))
        else:
            required.update(shape.get("required", ()))
    modes = [shape.get("properties", {}).get("mode", {}).get("const") for shape in shapes]
    if "oneOf" in definition and all(mode is not None for mode in modes):
        properties["mode"] = {"enum": modes}
    return {"type": "object", "properties": properties, "required": required}


def _schema_controls(schema, definition, prefix="", *, required=False):
    shape = _schema_shape(schema, definition)
    if "properties" in shape:
        controls = []
        for name, field in shape["properties"].items():
            controls.extend(_schema_controls(
                schema, field, f"{prefix}/{name}",
                required=required and name in shape.get("required", ()),
            ))
        return controls
    name = prefix.split("/")[-1]
    choices = [(value, value.replace("_", " ").title()) for value in shape.get("enum", ()) if value is not None]
    kind = "select" if choices else "text" if (
        name.endswith("_version_id") or name in ("title", "name", "quantity", "query_time")
        or shape.get("type") == "integer" or "const" in shape
    ) else "textarea"
    label = name.replace("_", " ").capitalize()
    if "/effect_horizon/" in prefix:
        label = f"Expected effect horizon — {label.lower()}"
    elif "/maximum_holding_period/" in prefix:
        label = f"Maximum holding period — {label.lower()}"
    help_text = FIELD_HELP.get(name, "Enter an explicit research description; no value or authority is inferred.")
    if name == "mode" and "idea_family_binding" in prefix:
        help_text = "Choose an existing exact association or explicitly request first family assignment with a grouping reason. Nothing is assigned in this preview."
    elif name == "mode":
        help_text = "Explicitly retain the exact assessment version or propose a reasoned successor. No assessment is rewritten in this preview."
    if name == "kind":
        help_text = "Select explicitly. All duration inputs remain visible; clear incompatible kind/unit fields explicitly. No fixed time limit requires a reason and defined exits; absence is not unlimited holding."
    return [{
        "id": "draft" + prefix.replace("/", "-"), "path": prefix,
        "label": label, "help": help_text, "kind": kind, "choices": choices,
        "required": required and "null" not in shape.get("type", ()), "maxlength": shape.get("maxLength"),
        "readonly": "const" in shape, "value": shape.get("const", ""),
    }]


def hypothesis_draft_groups(schema, *, correction=False):
    request_name = "HypothesisCorrection" if correction else "HypothesisCreate"
    controls = _schema_controls(schema, schema["$defs"][request_name], required=True)
    origin = [control for control in controls if not control["path"].startswith("/fields/")]
    groups = [{"label": "Exact origin and Research context binding", "controls": origin}]
    for label, names in HYPOTHESIS_GROUPS:
        groups.append({"label": label, "controls": [
            control for control in controls
            if control["path"].startswith("/fields/") and control["path"].split("/")[2] in names
        ]})
    return groups


def research_context_groups(schema, *, correction=False):
    return [
        {"label": label, "controls": _schema_controls(schema, schema["$defs"][name], prefix, required=True)}
        for label, name, prefix in (
            ("Research family — proposed setup", "FamilyCorrection" if correction else "FamilyCreate", "/context/family"),
            ("Research case — proposed, with manual assessment", "InvestigationCorrection" if correction else "InvestigationCreate", "/context/case"),
            ("Explicit Idea-family reclassification proposal", "IdeaFamilyCorrection", "/context/idea-family"),
        )
    ]


def hypothesis_draft_context(schema, *, submitted=None, issues=(), conflict=False, correction=False, latest_url=None):
    groups = hypothesis_draft_groups(schema, correction=correction)
    context_groups = research_context_groups(schema, correction=correction)
    presentation = draft_presentation(groups + context_groups, submitted=submitted, issues=issues, conflict=conflict, latest_url=latest_url)
    presentation["context_groups"] = presentation["field_groups"][len(groups):]
    presentation["field_groups"] = presentation["field_groups"][:len(groups)]
    presentation["schema_version"] = schema["x-schema-version"]
    return presentation


def _local_url(url):
    if not isinstance(url, str) or not url.startswith("/") or url.startswith("//"):
        return None
    if any(character.isspace() or character == "\\" or ord(character) < 32 for character in url):
        return None
    parsed = urlsplit(url)
    return url if not parsed.scheme and not parsed.netloc else None


def _pinned_reference(label, endpoint, *, kind=None):
    reference = {"label": label, **deepcopy(endpoint), "url": None}
    identity = endpoint.get("stable_id", "")
    version = endpoint.get("version")
    if isinstance(identity, str) and type(version) is int and version > 0:
        if kind == "idea" and identity.startswith("IDE-") and PUBLIC_ID_RE.fullmatch(identity):
            reference["url"] = f"/ideas/{identity}/history#idea-version-{version}"
        elif kind == "source" and SOURCE_ID_RE.fullmatch(identity) and identity not in (".", ".."):
            reference["url"] = f"/sources/{identity}/history#source-version-{version}"
    return reference


def hypothesis_record_presentation(record):
    origin = record["origin"]
    context = record["research_context"]
    references = [_pinned_reference("Originating Idea", origin["idea"], kind="idea")]
    for contribution in origin["sources"]:
        reference = _pinned_reference("Supporting Source", contribution["source"], kind="source")
        reference["association_version_id"] = contribution["contribution_version_id"]
        references.append(reference)
    for key, label in (("family", "Research family"), ("investigation", "Research case (proposed)"), ("assessment", "Manual prior-research assessment")):
        references.append(_pinned_reference(label, context[key]))
    associations = [origin["association"]] + [
        context[key] for key in (
            "idea_family_association", "investigation_family_association",
            "investigation_assessment_association", "hypothesis_investigation_association",
        )
    ]
    return {"record": deepcopy(record), "pinned_references": references, "pinned_associations": deepcopy(associations)}


def navigation_context(*, section="home", role=None, build=None):
    return {
        "navigation": [
            {"key": key, "label": label, "url": url, "current": key == section}
            for key, label, url in NAVIGATION
        ],
        "role_label": {"editor": "Editor", "founder_viewer": "Viewer (read-only)"}.get(
            role, "Not supplied"
        ),
        "can_edit": role == "editor",
        "build_label": build or getattr(settings, "RMS_DEPLOYED_COMMIT", None) or "Not supplied — not a deployed release",
        "repository_preview": True,
    }


def draft_presentation(groups, *, submitted=None, issues=(), conflict=False, latest_url=None):
    bound_groups = deepcopy(groups)
    submitted = submitted if submitted is not None else {}
    controls = {}
    for group in bound_groups:
        for control in group["controls"]:
            path = control["path"]
            control["value"] = submitted.get(path, control.get("value", ""))
            control["errors"] = []
            control["submitted_choice"] = bool(
                control.get("kind") == "select"
                and control["value"]
                and control["value"] not in [choice[0] for choice in control["choices"]]
            )
            controls[path] = control
    errors = []
    for issue in issues:
        control = controls.get(issue.get("path"))
        message = issue["message"]
        if control is not None:
            control["errors"].append(message)
        errors.append({"target": control["id"] if control else None, "message": message})
    return {"field_groups": bound_groups, "errors": errors, "conflict": conflict, "latest_url": _local_url(latest_url)}


class NavigationPage(RmsPage):
    section = "home"

    def get(self, request):
        self._require_reader(request)
        role = "editor" if has_rms_write_access(request.user) else "founder_viewer"
        context = navigation_context(section=self.section, role=role)
        context["repository_preview"] = False
        context["heading"] = dict(
            (key, label) for key, label, url in NAVIGATION
        )[self.section]
        if self.section in ("sources", "ideas", "hypotheses", "context"):
            return connected_selection(self, request, context)
        context["home_counts"] = []
        for kind in ("source", "idea", "hypothesis", "family", "case"):
            config = RESOURCES[kind]
            item = {"label": config["label"], "url": "/" + config["route"], "count": None}
            if kind in ("family", "case"):
                item["url"] = "/research-context#collection-" + kind
            try:
                item["count"] = shared_service(kind, "list", actor=request.user, query={"page": 1, "page_size": 1})["count"]
            except (SchemaUnavailable, DatabaseError):
                pass
            except ServiceError as error:
                if getattr(error, "http_status", None) in (401, 403):
                    return service_failure(self, request, error)
            context["home_counts"].append(item)
        return TemplateResponse(request._request, "rms/navigation.html", context)


class HypothesisDraftPreviewPage(RmsPage):
    def get(self, request):
        self._require_editor(request)
        context = navigation_context(section="hypotheses", role="editor")
        try:
            schema = read_navigation_schema()
        except SchemaUnavailable:
            context["schema_unavailable"] = True
            return TemplateResponse(request._request, "rms/hypothesis_draft_shell.html", context, status=503)
        context.update(hypothesis_draft_context(schema))
        return TemplateResponse(request._request, "rms/hypothesis_draft_shell.html", context)


# Browser adapters consume Backend-owned projections, never authoritative models.
RESOURCES = {
    "source": {"label": "Sources", "route": "sources", "section": "sources", "module": "record_selection_services", "list": "list_sources"},
    "idea": {"label": "Ideas", "route": "ideas", "section": "ideas", "module": "record_selection_services", "list": "list_ideas"},
    "hypothesis": {"label": "Hypothesis", "route": "hypotheses", "section": "hypotheses", "module": "hypothesis_services", "get": "get_hypothesis", "list": "list_hypotheses", "history": "get_hypothesis_history", "create": "create_hypothesis", "correct": "correct_hypothesis", "id": "hypothesis_id", "create_schema": "HypothesisCreate", "correct_schema": "HypothesisCorrection"},
    "family": {"label": "Research family", "route": "research-families", "section": "context", "module": "research_context_services", "get": "get_research_family", "list": "list_research_families", "history": "get_research_family_history", "create": "create_research_family", "correct": "correct_research_family", "id": "family_id", "create_schema": "FamilyCreate", "correct_schema": "FamilyCorrection"},
    "case": {"label": "Research case", "route": "investigations", "section": "context", "module": "research_context_services", "get": "get_investigation", "list": "list_investigations", "history": "get_investigation_history", "create": "create_investigation", "correct": "correct_investigation", "id": "investigation_id", "create_schema": "InvestigationCreate", "correct_schema": "InvestigationCorrection"},
    "assessment": {"label": "Manual prior-research assessment", "route": "prior-research-assessments", "section": "context", "module": "research_context_services", "get": "get_prior_research_assessment", "id": "assessment_id"},
    "classification": {"label": "Idea-family classification", "route": "idea-family-associations", "section": "context", "module": "research_context_services", "lookup": "get_idea_family_for_idea", "get": "get_idea_family_association", "history": "get_idea_family_association_history", "correct": "correct_idea_family_association", "id": "association_id", "result_id": "stable_id", "correct_schema": "IdeaFamilyCorrection"},
}


def shared_service(kind, operation, **kwargs):
    config = RESOURCES[kind]
    module_name = "rms." + config["module"]
    try:
        module = import_module(module_name)
    except ModuleNotFoundError as error:
        if error.name != module_name:
            raise
        raise SchemaUnavailable("The adopted Backend services are not available.") from error
    return getattr(module, config[operation])(**kwargs)


def browser_url(kind, identity, version=None):
    route = RESOURCES[kind]["route"]
    return f"/{route}/{identity}" + (f"/versions/{version}" if version is not None else "")


def result_identity(kind, record):
    config = RESOURCES[kind]
    return record[config.get("result_id", config["id"])]


def live_context(page, request):
    role = "editor" if has_rms_write_access(request.user) else "founder_viewer"
    return {**navigation_context(section=RESOURCES[page.kind]["section"], role=role), "repository_preview": False, "resource": RESOURCES[page.kind], "kind": page.kind}


def selection_query(request):
    try:
        parser = import_module("rms.hypothesis_api").query_payload
    except ModuleNotFoundError as error:
        if error.name != "rms.hypothesis_api":
            raise
        raise SchemaUnavailable("The adopted query adapter is not available.") from error
    return parser(request.query_params)


def selection_projection(kind, result):
    result = deepcopy(result)
    for record in result["results"]:
        if kind in ("source", "idea"):
            record["links"] = {key: _local_url(value) for key, value in record["links"].items()}
        else:
            record["browser_url"] = browser_url(kind, record[RESOURCES[kind]["id"]])
    base = "/research-context" if kind in ("family", "case") else "/" + RESOURCES[kind]["route"]
    for key in ("next", "previous"):
        if kind in ("source", "idea"):
            number = result["page"] + (1 if key == "next" else -1)
            # Presence comes from the authorized envelope. Ignore API URLs and
            # keep its page size when producing browser navigation.
            result[key] = base + "?" + urlencode({"page": number, "page_size": result["page_size"]}) if result.get(key) else None
        else:
            supplied = _local_url(result.get(key))
            result[key] = base + "?" + urlsplit(supplied).query if supplied else None
    return result


def connected_selection(page, request, context):
    kinds = {"sources": ("source",), "ideas": ("idea",), "hypotheses": ("hypothesis",), "context": ("family", "case")}[page.section]
    context["collections"] = []
    try:
        for kind in kinds:
            collection = shared_service(kind, "list", actor=request.user, query=selection_query(request))
            context["collections"].append({"kind": kind, "resource": RESOURCES[kind], "listing": selection_projection(kind, collection)})
    except (SchemaUnavailable, DatabaseError):
        return TemplateResponse(request._request, "rms/service_unavailable.html", context, status=503)
    except ServiceError as error:
        if getattr(error, "http_status", None) == 503:
            return TemplateResponse(request._request, "rms/service_unavailable.html", context, status=503)
        return service_failure(page, request, error)
    except Exception as error:
        if not hasattr(error, "issues"):
            raise
        context["list_error"] = "The selection query is invalid. Use a positive page and a page size up to 100."
        context["collections"] = []
        return TemplateResponse(request._request, "rms/record_selection.html", context, status=400)
    return TemplateResponse(request._request, "rms/record_selection.html", context)


def service_failure(page, request, error):
    if isinstance(error, ResourceNotFound):
        return page._not_found(request)
    status = getattr(error, "http_status", 409)
    if status in (401, 403):
        response = TemplateResponse(request._request, "rms/denied.html", status=status)
        if status == 401:
            challenge = page.get_authenticate_header(request)
            if challenge:
                response["WWW-Authenticate"] = challenge
        return response
    return TemplateResponse(request._request, "rms/unavailable.html", status=status)


def flatten_input(value, prefix=""):
    result = {}
    if isinstance(value, dict):
        for key, item in value.items():
            result.update(flatten_input(item, prefix + "/" + key))
    else:
        result[prefix] = json.dumps(value, ensure_ascii=False) if isinstance(value, list) else "" if value is None else str(value)
    return result


class FormEncodingError(ValueError):
    def __init__(self, path, message):
        self.issues = [{"path": path, "code": "invalid_format", "message": message}]


_OMIT = object()


def form_payload(schema, definition, submitted, prefix="", *, required=True):
    """Encode HTML strings into schema types; services own all domain checks.

    Nonempty incompatible inputs are retained for authoritative rejection.
    """
    if "$ref" in definition:
        definition = schema["$defs"][definition["$ref"].split("/")[-1]]
    merged = _schema_shape(schema, definition)
    if "properties" in merged:
        if not required:
            leaves = _schema_controls(schema, definition, prefix)
            if not any(submitted.get(control["path"], "") for control in leaves if not control["readonly"]):
                return _OMIT
        shape = merged
        if "oneOf" in definition:
            mode = submitted.get(prefix + "/mode", "")
            selected = next((branch for branch in definition["oneOf"] if _schema_shape(schema, branch).get("properties", {}).get("mode", {}).get("const") == mode), None)
            if selected is not None:
                shape = _schema_shape(schema, selected)
        result = {}
        for name, field in merged["properties"].items():
            item = form_payload(schema, field, submitted, prefix + "/" + name, required=name in shape.get("required", ()))
            if item is not _OMIT:
                result[name] = item
        if "null" in definition.get("type", ()) and all(value is None or value == "" for value in result.values()):
            return None
        return result if required or result else _OMIT
    raw = submitted.get(prefix, "")
    nullable = "null" in definition.get("type", ())
    if raw == "":
        return None if nullable else "" if required else _OMIT
    if definition.get("type") == "integer":
        try:
            return int(raw)
        except ValueError:
            return raw
    if definition.get("type") == "array":
        try:
            return json.loads(raw)
        except (ValueError, TypeError) as error:
            raise FormEncodingError(prefix, "Enter valid JSON for the exact record links, or an explicit [] if none were inspected.") from error
    return raw


def revision_snapshot(kind, record):
    if kind == "classification":
        return {"prior_association_version_id": record["version_id"], "family_version_id": record["to"]["version_id"], "rationale": record["rationale"], "expected_latest_version": record["version"], "correction_reason": ""}
    payload = {"fields": deepcopy(record["fields"]), "expected_latest_version": record["version"], "correction_reason": ""}
    if kind == "hypothesis":
        payload.update({"originating_idea_version_id": record["origin"]["idea"]["version_id"], "origin_rationale": record["origin"]["association"]["rationale"], "investigation_version_id": record["research_context"]["investigation"]["version_id"], "idea_family_binding": {"mode": "existing", "association_version_id": record["research_context"]["idea_family_association"]["version_id"]}})
    elif kind == "case":
        payload.update({"family_version_id": record["family"]["version_id"], "prior_research_assessment": {"mode": "existing", "assessment_version_id": record["prior_research_assessment"]["assessment_version_id"]}})
    return payload


def form_groups(schema, kind, correction=False):
    if kind == "hypothesis":
        return hypothesis_draft_groups(schema, correction=correction)
    name = RESOURCES[kind]["correct_schema" if correction else "create_schema"]
    return [{"label": RESOURCES[kind]["label"], "controls": _schema_controls(schema, schema["$defs"][name], required=True)}]


def selection_controls(groups, families, cases):
    for group in groups:
        for control in group["controls"]:
            path = control["path"]
            if path.endswith("/family_version_id"):
                records, key = families, "family_version_id"
            elif path == "/investigation_version_id":
                records, key = cases, "investigation_version_id"
            else:
                records = None
            if records:
                control["kind"] = "select"
                control["choices"] = [(item[key], f"{item['fields'].get('title', item['fields'].get('name'))} — v{item['version']} — {item[key]}") for item in records]
            if path.endswith("/record_links"):
                control["help"] = "Exact inspected-version links as JSON, or an explicit [] if none were available. External documents are labeled references."
            if path.endswith("/mode"):
                control["help"] = "Choose explicitly. Retain the selected exact association/assessment, or provide a reasoned first assignment or successor. Clear the unused branch inputs."


def exact_idea(identity, version=None):
    if not identity.startswith("IDE-") or not PUBLIC_ID_RE.fullmatch(identity):
        raise ResourceNotFound
    record = get_idea(identity)
    if version is None:
        return idea_detail(record)["latest"]
    return next((item for item in idea_history(record)["versions"] if item["version"] == version), None)


class ConnectedPage(RmsPage):
    kind = "hypothesis"


def record_display(kind, record):
    record = deepcopy(record)
    references = []
    associations = []
    if kind == "hypothesis":
        presentation = hypothesis_record_presentation(record)
        references = presentation["pinned_references"]
        associations = presentation["pinned_associations"]
        for reference, target_kind in zip(references[-3:], ("family", "case", "assessment")):
            reference["url"] = browser_url(target_kind, reference["stable_id"], reference["version"])
        for association in associations:
            if association["kind"] == "IdeaFamily":
                association["browser_url"] = browser_url("classification", association["stable_id"], association["version"])
        for notice in record.get("upstream_notices", []):
            for key in ("pinned", "newer"):
                endpoint = notice[key]
                if endpoint["stable_id"].startswith("IFA-"):
                    endpoint["browser_url"] = browser_url("classification", endpoint["stable_id"], endpoint["version"])
    elif kind == "case":
        family = record["family"]
        assessment = record["prior_research_assessment"]
        references = [{"label": "Research family", **family, "url": browser_url("family", family["stable_id"], family["version"])}, {"label": "Manual prior-research assessment", "version_id": assessment["assessment_version_id"], "version": assessment["version"], "stable_id": assessment["assessment_id"], "url": browser_url("assessment", assessment["assessment_id"], assessment["version"])}]
        associations = [record["family_association"], record["assessment_association"]]
    elif kind == "assessment":
        associations = record.get("record_associations", [])
    elif kind == "classification":
        references = [_pinned_reference("Exact classified Idea", record["from"], kind="idea"), {"label": "Exact Research family", **record["to"], "url": browser_url("family", record["to"]["stable_id"], record["to"]["version"])}]
    return {"record": record, "pinned_references": references, "pinned_associations": associations, "detail_url": browser_url(kind, result_identity(kind, record), record["version"])}


def classification_for_idea(request, query):
    # Reuse the same query definition and validator as the API; no browser rule copy.
    validate = import_module("rms.hypothesis_validation").validate_request
    payload = validate("IdeaFamilyQuery", query)
    return shared_service("classification", "lookup", actor=request.user, idea_version_id=payload["idea_version_id"])


class ClassificationLookupPage(ConnectedPage):
    kind = "classification"

    def get(self, request):
        self._require_reader(request)
        context = live_context(self, request)
        context["idea_version_id"] = request.query_params.get("idea_version_id", "")
        if request.query_params:
            try:
                record = classification_for_idea(request, selection_query(request))
                context.update(record_display(self.kind, record))
                identity = result_identity(self.kind, record)
                context.update({"latest_url": browser_url(self.kind, identity), "history_url": browser_url(self.kind, identity) + "/history", "revision_url": browser_url(self.kind, identity) + "/revise"})
            except (SchemaUnavailable, DatabaseError):
                return TemplateResponse(request._request, "rms/service_unavailable.html", context, status=503)
            except ServiceError as error:
                return service_failure(self, request, error)
            except Exception as error:
                if not hasattr(error, "issues"):
                    raise
                context["lookup_error"] = "Enter one authorized exact Idea version ID; this lookup accepts no other query fields."
                return TemplateResponse(request._request, "rms/classification_lookup.html", context, status=400)
        return TemplateResponse(request._request, "rms/classification_lookup.html", context)


class RecordDetailPage(ConnectedPage):
    def get(self, request, record_id, version=None):
        self._require_reader(request)
        context = live_context(self, request)
        try:
            record = shared_service(self.kind, "get", actor=request.user, **{RESOURCES[self.kind]["id"]: record_id}, version=version)
        except (SchemaUnavailable, DatabaseError):
            return TemplateResponse(request._request, "rms/service_unavailable.html", context, status=503)
        except ServiceError as error:
            return service_failure(self, request, error)
        context.update(record_display(self.kind, record))
        context.update({"historical": version is not None, "latest_url": browser_url(self.kind, record_id), "history_url": browser_url(self.kind, record_id) + "/history", "revision_url": browser_url(self.kind, record_id) + "/revise"})
        return TemplateResponse(request._request, "rms/record_detail.html", context)


class RecordHistoryPage(ConnectedPage):
    def get(self, request, record_id):
        self._require_reader(request)
        context = live_context(self, request)
        try:
            history = shared_service(self.kind, "history", actor=request.user, **{RESOURCES[self.kind]["id"]: record_id})
        except (SchemaUnavailable, DatabaseError):
            return TemplateResponse(request._request, "rms/service_unavailable.html", context, status=503)
        except ServiceError as error:
            return service_failure(self, request, error)
        context["versions"] = [record_display(self.kind, record) for record in history["results"]]
        context["latest_url"] = browser_url(self.kind, record_id)
        return TemplateResponse(request._request, "rms/record_history.html", context)


class RecordEditorPage(ConnectedPage):
    def get(self, request, record_id=None):
        self._require_editor(request)
        try:
            schema = read_navigation_schema()
            submitted = {}
            idea = None
            classification = None
            if record_id is not None:
                record = shared_service(self.kind, "get", actor=request.user, **{RESOURCES[self.kind]["id"]: record_id})
                submitted = flatten_input(revision_snapshot(self.kind, record))
                if self.kind == "classification":
                    classification = record
                if self.kind == "hypothesis":
                    submitted["reference_idea_id"] = record["origin"]["idea"]["stable_id"]
                    submitted["reference_idea_version"] = str(record["origin"]["idea"]["version"])
                    idea = exact_idea(record["origin"]["idea"]["stable_id"], record["origin"]["idea"]["version"])
            elif self.kind == "hypothesis" and request.query_params.get("idea_id"):
                try:
                    version = int(request.query_params["idea_version"]) if "idea_version" in request.query_params else None
                except ValueError:
                    raise ResourceNotFound
                idea = exact_idea(request.query_params["idea_id"], version)
                if idea is None:
                    raise ResourceNotFound
                submitted["/originating_idea_version_id"] = idea["idea_version_id"]
            return self.render_form(request, schema, submitted, record_id=record_id, idea=idea, classification=classification)
        except (SchemaUnavailable, DatabaseError):
            return TemplateResponse(request._request, "rms/service_unavailable.html", live_context(self, request), status=503)
        except ServiceError as error:
            return service_failure(self, request, error)

    def render_form(self, request, schema, submitted, *, record_id=None, idea=None, issues=(), status=200, conflict=False, notice=None, request_key=None, classification=None, read_references=True):
        correction = record_id is not None
        context_groups = research_context_groups(schema)[:2] if self.kind == "hypothesis" else []
        groups = form_groups(schema, self.kind, correction)
        if not read_references:
            families, cases, selection_unavailable = [], [], True
        else:
            try:
                families = shared_service("family", "list", actor=request.user, query={})["results"]
                cases = shared_service("case", "list", actor=request.user, query={})["results"] if self.kind == "hypothesis" else []
                selection_unavailable = False
            except (SchemaUnavailable, ServiceError, DatabaseError):
                families, cases, selection_unavailable = [], [], True
        selection_controls(groups + context_groups, families, cases)
        presentation = draft_presentation(groups + context_groups, submitted=submitted, issues=issues, conflict=conflict, latest_url=browser_url(self.kind, record_id) if correction else None)
        context = live_context(self, request)
        context["selection_unavailable"] = selection_unavailable
        context.update(presentation)
        context["context_groups"] = context["field_groups"][len(groups):]
        context["field_groups"] = context["field_groups"][:len(groups)]
        if read_references and idea is None and submitted.get("reference_idea_id"):
            try:
                selected = exact_idea(submitted["reference_idea_id"], int(submitted.get("reference_idea_version", "")))
                if selected and selected["idea_version_id"] == submitted.get("/originating_idea_version_id"):
                    idea = selected
            except (ValueError, ResourceNotFound, DatabaseError):
                pass
        context.update({"correction": correction, "record_id": record_id, "schema_version": schema["x-schema-version"], "interface_version": schema["x-interface-version"], "idempotency_key": request_key or str(uuid4()), "idea": idea, "notice": notice, "confirm_first_family": submitted.get("confirm_first_family") == "yes", "reference_idea_id": submitted.get("reference_idea_id", request.query_params.get("idea_id", "")), "reference_idea_version": idea["version"] if idea else submitted.get("reference_idea_version", "")})
        if classification is not None:
            context["selected_classification"] = record_display("classification", classification)
            context["classification_history_url"] = browser_url("classification", classification["stable_id"]) + "/history"
            context["classification_revision_url"] = browser_url("classification", classification["stable_id"]) + "/revise"
        return TemplateResponse(request._request, "rms/record_form.html", context, status=status)

    def select_classification(self, request, schema, submitted, record_id, operation):
        try:
            if operation == "lookup_classification":
                record = classification_for_idea(request, {"idea_version_id": submitted.get("/originating_idea_version_id", "")})
                notice = "Current classification inspected. The draft binding has not changed; selection requires an explicit action."
            else:
                try:
                    version = int(submitted.get("classification_version", ""))
                except ValueError as error:
                    raise FormEncodingError("/idea_family_binding/association_version_id", "Inspect a classification and explicitly select an exact version.") from error
                record = shared_service("classification", "get", actor=request.user, association_id=submitted.get("classification_id", ""), version=version)
                # Only this explicit action changes the proposal. The save service
                # later validates the association against the Idea and case.
                submitted["/idea_family_binding/mode"] = "existing"
                submitted["/idea_family_binding/association_version_id"] = record["version_id"]
                submitted.pop("/idea_family_binding/family_version_id", None)
                submitted.pop("/idea_family_binding/rationale", None)
                submitted.pop("confirm_first_family", None)
                notice = "Exact classification selected in the unfinished draft. No Hypothesis save is confirmed; review the binding before saving."
            return self.render_form(request, schema, submitted, record_id=record_id, classification=record, notice=notice, request_key=submitted.get("idempotency_key"))
        except (SchemaUnavailable, DatabaseError):
            return self.render_form(request, schema, submitted, record_id=record_id, status=503, issues=[{"path": "", "message": "Classification could not be read. The draft binding and unfinished input remain unchanged."}], request_key=submitted.get("idempotency_key"))
        except ServiceError as error:
            if getattr(error, "http_status", None) in (401, 403):
                return service_failure(self, request, error)
            status = 404 if isinstance(error, ResourceNotFound) else getattr(error, "http_status", 409)
            return self.render_form(request, schema, submitted, record_id=record_id, status=status, issues=[{"path": "", "message": "Classification unavailable. Missing and restricted records use the same response; the draft binding remains unchanged."}], request_key=submitted.get("idempotency_key"))
        except Exception as error:
            if not hasattr(error, "issues"):
                raise
            return self.render_form(request, schema, submitted, record_id=record_id, status=400, issues=error.issues, request_key=submitted.get("idempotency_key"))

    @method_decorator(csrf_protect)
    def post(self, request, record_id=None):
        self._require_editor(request)
        submitted = {key: request.data.get(key, "") for key in request.data}
        try:
            schema = read_navigation_schema()
        except SchemaUnavailable:
            context = live_context(self, request)
            context["unsaved_input"] = json.dumps({key: value for key, value in submitted.items() if key.startswith("/")}, ensure_ascii=False, indent=2)
            return TemplateResponse(request._request, "rms/service_unavailable.html", context, status=503)
        operation = submitted.get("operation", "save")
        if self.kind == "hypothesis" and operation in ("lookup_classification", "adopt_classification"):
            return self.select_classification(request, schema, submitted, record_id, operation)
        target = self.kind
        correction = record_id is not None
        prefix = ""
        if self.kind == "hypothesis" and operation in ("create_family", "create_case"):
            target = "family" if operation == "create_family" else "case"
            correction = False
            prefix = "/context/" + target
        elif operation != "save":
            return self.render_form(request, schema, submitted, record_id=record_id, status=400, issues=[{"path": "", "message": "Choose a supported save action."}])
        name = RESOURCES[target]["correct_schema" if correction else "create_schema"]
        try:
            payload = form_payload(schema, schema["$defs"][name], submitted, prefix)
            if target == "hypothesis" and payload.get("idea_family_binding", {}).get("mode") == "create" and submitted.get("confirm_first_family") != "yes":
                raise FormEncodingError("/idea_family_binding/mode", "Confirm first family assignment explicitly and provide its grouping reason.")
            kwargs = {"actor": request.user, "idempotency_key": request.headers.get("Idempotency-Key") or submitted.get("idempotency_key", ""), "payload": payload}
            if correction:
                kwargs[RESOURCES[target]["id"]] = record_id
            stored = shared_service(target, "correct" if correction else "create", **kwargs)
        except SchemaUnavailable:
            return self.render_form(request, schema, submitted, record_id=record_id, status=503, request_key=submitted.get("idempotency_key"), issues=[{"path": "", "message": "Record services are unavailable. Your input remains below; no save was confirmed."}])
        except DatabaseError:
            return self.render_form(request, schema, submitted, record_id=record_id, status=503, request_key=submitted.get("idempotency_key"), issues=[{"path": "", "message": "The save outcome could not be confirmed. Input and the original request key remain below. Retry the unchanged request before editing to retrieve its server result."}])
        except ServiceError as error:
            if isinstance(error, ResourceNotFound):
                return self.render_form(request, schema, submitted, record_id=record_id, status=404,
                    request_key=kwargs["idempotency_key"], read_references=False,
                    issues=[{"path": "", "message": "A referenced record could not be used. Missing and restricted records use the same response. Your input and original request key remain below; no save was confirmed."}])
            if getattr(error, "http_status", None) in (401, 403):
                return service_failure(self, request, error)
            status = getattr(error, "http_status", 409)
            if status != 409:
                return self.render_form(request, schema, submitted, record_id=record_id, status=status, request_key=submitted.get("idempotency_key"), issues=[{"path": "", "message": "The server could not confirm a save. Input and the original request key remain below; inspect the record before editing or retrying."}])
            return self.render_form(request, schema, submitted, record_id=record_id, conflict=True, status=409)
        except Exception as error:
            if not hasattr(error, "issues"):
                raise
            issues = [{**issue, "path": prefix + issue["path"] if prefix and not issue["path"].startswith(prefix + "/") else issue["path"]} for issue in error.issues]
            return self.render_form(request, schema, submitted, record_id=record_id, issues=issues, status=400)
        saved = json.loads(stored.body)
        if operation == "create_family":
            submitted["/context/case/family_version_id"] = saved["family_version_id"]
            submitted["/idea_family_binding/family_version_id"] = saved["family_version_id"]
        elif operation == "create_case":
            submitted["/investigation_version_id"] = saved["investigation_version_id"]
        else:
            response = HttpResponseRedirect(browser_url(target, result_identity(target, saved), saved["version"]))
            response.status_code = 303
            return response
        return self.render_form(request, schema, submitted, record_id=record_id, notice=f"{RESOURCES[target]['label']} version {saved['version']} saved and selected. Hypothesis input remains unsaved.")
