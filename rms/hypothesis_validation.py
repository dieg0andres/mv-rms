"""Database-free request shape and draft completeness; never write authority."""

from copy import deepcopy
from datetime import datetime
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import re


SCHEMA_PATH = Path(__file__).with_name("hypothesis_schema.json")
SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
SCHEMA_VERSION = SCHEMA["x-schema-version"]
SCHEMA_SHA256 = hashlib.sha256(SCHEMA_PATH.read_bytes()).hexdigest()
REQUEST_NAMES = frozenset(
    endpoint[key]
    for endpoint in SCHEMA["x-endpoints"]
    for key in ("request", "query")
    if key in endpoint
)


class HypothesisValidationError(ValueError):
    code = "validation_error"

    def __init__(self, issues):
        self.issues = tuple(issues)
        super().__init__("The request is invalid.")


def _issue(path, code, message):
    return {"path": path, "code": code, "message": message}


def _path(parent, key):
    escaped = str(key).replace("~", "~0").replace("/", "~1")
    return f"{parent}/{escaped}"


def _definition(name):
    return SCHEMA["$defs"][name]


def _validate(value, definition, path, issues):
    if "$ref" in definition:
        return _validate(value, _definition(definition["$ref"].split("/")[-1]), path, issues)
    if "allOf" in definition:
        for option in definition["allOf"]:
            value = _validate(value, option, path, issues)
        return value
    if "oneOf" in definition:
        attempts = []
        for option in definition["oneOf"]:
            option_issues = []
            normalized = _validate(value, option, path, option_issues)
            attempts.append((option, normalized, option_issues))
        matches = [attempt for attempt in attempts if not attempt[2]]
        if len(matches) == 1:
            return matches[0][1]
        if isinstance(value, dict):
            for option, normalized, option_issues in attempts:
                selectors = {
                    key: rule["const"]
                    for key, rule in option.get("properties", {}).items()
                    if "const" in rule
                }
                if selectors and all(value.get(key) == expected for key, expected in selectors.items()):
                    issues.extend(option_issues)
                    return normalized
        issues.append(_issue(path, "invalid_variant", "Choose exactly one valid binding variant."))
        return value

    types = definition.get("type", [])
    types = [types] if isinstance(types, str) else types
    if isinstance(value, str) and definition.get("x-trim"):
        value = value.strip()
        if not value and "null" in types:
            value = None
    type_checks = {
        "null": value is None,
        "string": isinstance(value, str),
        "object": isinstance(value, dict) and all(isinstance(key, str) for key in value),
        "array": isinstance(value, list),
        "integer": type(value) is int,
    }
    if types and not any(type_checks.get(kind, False) for kind in types):
        issues.append(_issue(path, "invalid_type", "Value has an invalid JSON type."))
        return value
    if "const" in definition and value != definition["const"]:
        issues.append(_issue(path, "invalid_value", "Value does not match the contract."))
    if "enum" in definition and value not in definition["enum"]:
        issues.append(_issue(path, "invalid_enum", "Choose an explicitly supported value."))
    if value is None:
        return None
    if isinstance(value, str):
        if len(value) < definition.get("minLength", 0):
            issues.append(_issue(path, "required", "A nonblank value is required."))
        if len(value) > definition.get("maxLength", len(value)):
            issues.append(_issue(path, "too_long", "Value exceeds the field limit."))
        if "pattern" in definition:
            pattern = definition["pattern"]
            matcher = re.fullmatch if pattern.startswith("^") else re.search
            if matcher(pattern, value) is None:
                issues.append(_issue(path, "invalid_format", "Value has an invalid format."))
        if definition.get("x-positive-finite-decimal"):
            try:
                quantity = Decimal(value)
                valid = quantity.is_finite() and quantity > 0
            except InvalidOperation:
                valid = False
            if not valid:
                issues.append(_issue(path, "invalid_decimal", "Provide a positive finite decimal string."))
        if definition.get("format") == "date-time":
            try:
                parsed = datetime.fromisoformat(value)
                valid = parsed.tzinfo is not None and value.endswith("Z")
            except ValueError:
                valid = False
            if not valid:
                issues.append(_issue(path, "invalid_datetime", "Provide an actual UTC time ending in Z."))
    if type(value) is int:
        if value < definition.get("minimum", value) or value > definition.get("maximum", value):
            issues.append(_issue(path, "out_of_range", "Value is outside the permitted range."))
    if isinstance(value, list):
        if len(value) > definition.get("maxItems", len(value)):
            issues.append(_issue(path, "too_many", "Too many values."))
        return [
            _validate(item, definition.get("items", {}), _path(path, index), issues)
            for index, item in enumerate(value)
        ]
    if isinstance(value, dict):
        normalized = {}
        properties = definition.get("properties", {})
        for key in definition.get("required", []):
            if key not in value:
                issues.append(_issue(_path(path, key), "required", "This field is required."))
        for key, item in value.items():
            if key not in properties and definition.get("additionalProperties") is False:
                issues.append(_issue(_path(path, key), "unknown_field", "This field is not accepted."))
            else:
                normalized[key] = _validate(item, properties.get(key, {}), _path(path, key), issues)
        return normalized
    return value


def _duration_checks(value, definition, path, issues):
    if value is None:
        return
    present = {key for key, item in value.items() if item is not None and key != "kind"}
    kind = value.get("kind")
    kind_fields = definition["x-kind-fields"]
    unit_fields = definition["x-unit-fields"]
    if kind is not None:
        allowed = set(kind_fields[kind])
        if kind == "fixed":
            if value.get("unit") is None:
                allowed.update(unit_fields.values())
            elif value["unit"] in unit_fields:
                allowed.add(unit_fields[value["unit"]])
        incompatible = present - allowed
    else:
        alternatives = [
            set(fields) | (set(unit_fields.values()) if choice == "fixed" else set())
            for choice, fields in kind_fields.items()
        ]
        incompatible = present if not any(present <= allowed for allowed in alternatives) else set()
        for unit, field in unit_fields.items():
            if field in present and value.get("unit") is not None and value["unit"] != unit:
                incompatible.add(field)
    if set(unit_fields.values()) <= present:
        incompatible.update(unit_fields.values())
    for key in sorted(incompatible):
        issues.append(_issue(_path(path, key), "incompatible_field", "Explicitly clear or replace fields incompatible with this duration."))


def _research_checks(fields, issues):
    for name, definition_name in (
        ("effect_horizon", "Duration"),
        ("maximum_holding_period", "HoldingDuration"),
    ):
        _duration_checks(fields.get(name), _definition(definition_name), f"/fields/{name}", issues)


def _assessment_links(assessment, path, issues):
    prefixes = {"source": "SRCV-", "idea": "IDEV-", "research_family": "RFAMV-", "investigation": "INVV-"}
    for index, link in enumerate(assessment["record_links"]):
        if link["kind"] != "external_document" and not link["version_id"].startswith(prefixes[link["kind"]]):
            issues.append(_issue(f"{path}/record_links/{index}/version_id", "invalid_reference_kind", "Version type does not match the referenced record kind."))


def validate_request(request_name, payload):
    """Validate/normalize JSON shape only; no reference, actor, or authority lookup."""
    if request_name not in REQUEST_NAMES:
        raise ValueError("Unknown request schema.")
    issues = []
    normalized = _validate(deepcopy(payload), _definition(request_name), "", issues)
    if not issues:
        if request_name.startswith("Hypothesis"):
            _research_checks(normalized["fields"], issues)
        if request_name == "InvestigationCreate":
            _assessment_links(normalized["prior_research_assessment"], "/prior_research_assessment", issues)
        if request_name == "InvestigationCorrection" and normalized["prior_research_assessment"]["mode"] == "correct":
            _assessment_links(normalized["prior_research_assessment"]["fields"], "/prior_research_assessment/fields", issues)
    if issues:
        raise HypothesisValidationError(issues)
    if request_name.startswith("Hypothesis"):
        normalized["fields"] = {
            name: normalized["fields"].get(name)
            for name in _definition("HypothesisFields")["properties"]
        }
    if request_name == "ListQuery":
        normalized.setdefault("page", 1)
        normalized.setdefault("page_size", 25)
    return normalized


def draft_completeness(fields):
    """Validate a requested snapshot and report missing research paths, not approval."""
    issues = []
    normalized = _validate(deepcopy(fields), _definition("HypothesisFields"), "/fields", issues)
    if not issues:
        _research_checks(normalized, issues)
    if issues:
        raise HypothesisValidationError(issues)
    missing = []
    for name in _definition("HypothesisFields")["properties"]:
        value = normalized.get(name)
        path = f"/fields/{name}"
        if value is None:
            missing.append(_issue(path, "missing", "Required for draft completeness."))
        elif name in ("effect_horizon", "maximum_holding_period"):
            definition = _definition("Duration" if name == "effect_horizon" else "HoldingDuration")
            if not value.get("kind"):
                missing.append(_issue(f"{path}/kind", "missing", "Choose an explicit duration policy."))
            else:
                required = list(definition["x-kind-fields"][value["kind"]])
                extra = definition["x-unit-fields"].get(value.get("unit"))
                if extra:
                    required.append(extra)
                for key in required:
                    if value.get(key) is None:
                        missing.append(_issue(f"{path}/{key}", "missing", "Required for this duration policy."))
    return {
        "schema_version": SCHEMA_VERSION,
        "draft_completeness": "incomplete" if missing else "complete",
        "missing_fields": missing,
    }
