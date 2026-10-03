"""Repository-only navigation preparation; no record or API queries."""

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
from urllib.parse import urlsplit

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

SCHEMA_COMMIT = "57ac0a3efeb7e10738e3bfb0e788d5f85edec002"
SCHEMA_PATH = "rms/hypothesis_schema.json"
SCHEMA_SHA256 = "ef2fe7d0e71d644ca978d7a3878f9ced4338212969cb6cdbc34a46550b73c5bc"

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
        "build_label": build or "Not supplied — not a deployed release",
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
        role = "editor" if self._has_role(request, "editor") else "founder_viewer"
        context = navigation_context(section=self.section, role=role)
        context["heading"] = dict(
            (key, label) for key, label, url in NAVIGATION
        )[self.section]
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
