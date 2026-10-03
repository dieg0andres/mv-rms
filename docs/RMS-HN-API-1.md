# RMS-HN-API-1 — pinned source-only interface 1.0

The sole machine-readable contract is `rms/hypothesis_schema.json`. Its `$defs`
contain the request/context/error/completeness/read/history/list shapes;
`x-endpoints` binds routes to schemas. Hash the actual bytes and use the published
immutable commit, not a copied or guessed parallel schema. Frontend/Test receipt
commit/path/hash in MAU-140 before dependent integration; Director adopts it.

Authority: contract revision `3982eccc-e180-4ac9-bc70-9c4e16aa47f1`, preserved
source `de6b971b8b1ef8b5ab6d230641aaec0daeb7e374`, bounded-source confirmation
`b963d661-71bf-4a56-a591-0a42e31d843a`. MAU-145 prepares repository source, not
reactivation of MAU-142/143/144, DB/API integration or release. No migrations are
supplied/applied. The accepted source and recipe remain unchanged.
`effect_horizon` maps baseline `horizon`; the four separate sizing fields map
baseline `sizing`. No duplicate editable legacy fields are introduced.

## Available pure helpers

```python
from rms.hypothesis_validation import (
    HypothesisValidationError, SCHEMA_SHA256, SCHEMA_VERSION,
    draft_completeness, validate_request,
)

validate_request(request_name: str, payload: dict) -> dict
draft_completeness(fields: dict) -> dict
```

Both functions are database-free and copy their inputs. Success is normalized
JSON shape, NEVER a saved record or authorization. Existence, visibility, context
compatibility, state/role/current authority, freshness and persistent idempotency
remain mandatory later shared-service checks and are HOLD here. Do not wire pure
helpers directly to live routes or bypass those checks. No expression is executed.
The helper implements only the schema's request subset, not a general JSON Schema
engine. Standard JSON Schema plus `x-trim`, `x-positive-finite-decimal`, and
`x-kind-fields`/`x-unit-fields` semantic checks define the full validation contract.
Record-link kind must match its version-ID prefix as well as later authorized
existence; a JSON Schema shape check alone is insufficient for semantic validity.

Request names are `request`/`query` entries in `x-endpoints`. Creation may omit
nullable Hypothesis fields; output expands them to null. Correction requires
every field (including explicit nulls), every binding, positive expected version
and nonblank reason. Nested durations replace the whole object, never merge.
Quantities are positive finite decimal strings, no exponents/floats. Supplied
incompatible duration fields must be explicitly cleared. `if_event_never_occurs`
names the holding event-nonoccurrence explanation. Empty optional text becomes
null; required text is rejected as missing. Research enums/fields have no defaults.
Only pagination defaults to page 1/size 25; size is at most 100.

Completeness returns `{schema_version, draft_completeness, missing_fields}`.
Each ordered missing item is `{path, code, message}` with an RFC 6901 JSON Pointer,
e.g. `/fields/effect_horizon/calendar`. Presence/shape only: net-return costs belong
in `implementation_assumptions`, other-measure units in `claim`; parsing prose
cannot prove substantive adequacy. **Draft complete** never means approved,
validated, qualified or ready to trade. Upstream review-needed is separate.

`HypothesisValidationError.issues` contains safe field errors without echoing
payload values. Future adapters extend the existing 400 envelope as
`{error: {code: validation_error, message, request_id, fields: [...]}}`.
Preserve authentication/challenge, 403, uniform hidden/nonexistent 404, and 409
`stale_version`/`idempotency_conflict`. Idempotency-Key binds actor/method/route/
canonical payload; replay retains original status/body/identity. New-key identical
snapshots return 200 without a version. These rules are specified, NOT executed.

## Minimum context wrappers

- Family: `{fields: {name, mechanism_boundary, distinctness_rule,
  risk_review_reference?}}`; correction adds expected version/reason and includes
  nullable reference. New identity prefixes: `RFAM-`/`RFAMV-` UUIDs.
- Case: `{family_version_id, fields: {title, owner_role, priority, next_action,
  blocker_text?}, prior_research_assessment: AssessmentFields}`. Case and separate
  versioned assessment must later commit atomically. `INV-`/`INVV-` UUIDs; workflow
  stays proposed; owner_role is descriptive, not a rights grant.
- Assessment: explicit scope/time/policy/watermark/finding/rationale/limitations
  and record_links, including explicit `[]` if none available. The accepted
  section-5 policy reference is pinned in the schema; no fabricated search or
  exception. Reviewer-entered query_time is UTC, separate from server save time.
  `PRA-`/`PRAV-` UUIDs; read-only exact-version route is schema-declared.
- Case correction restates full fields/family plus assessment binding
  `{mode: existing, assessment_version_id}` or `{mode: correct,
  corrects_assessment_version_id, expected_latest_assessment_version,
  correction_reason, fields: AssessmentFields}`. No hidden assessment rewrite.
- Idea-family correction names prior association version, target family version,
  rationale, expected latest version and reason. `IFA-`/`IFAV-` UUIDs. First
  assignment occurs only through the explicit Hypothesis create instruction.

Record-link arrays are transport descriptions: semantic links later persist as
first-class immutable endpoint associations, never authoritative JSON ID arrays.
External documents are labeled references, not fabricated future entities.

## Future shared browser-service signatures — NOT IMPLEMENTED

```python
create_hypothesis(*, actor, idempotency_key, payload) -> StoredResponse
correct_hypothesis(*, actor, hypothesis_id, idempotency_key, payload) -> StoredResponse
get_hypothesis(*, actor, hypothesis_id, version=None) -> dict
list_hypotheses(*, actor, query) -> dict
get_hypothesis_history(*, actor, hypothesis_id) -> dict
create_research_family(*, actor, idempotency_key, payload) -> StoredResponse
correct_research_family(*, actor, family_id, idempotency_key, payload) -> StoredResponse
get_research_family(*, actor, family_id, version=None) -> dict
list_research_families(*, actor, query) -> dict
get_research_family_history(*, actor, family_id) -> dict
create_investigation(*, actor, idempotency_key, payload) -> StoredResponse
correct_investigation(*, actor, investigation_id, idempotency_key, payload) -> StoredResponse
get_investigation(*, actor, investigation_id, version=None) -> dict
list_investigations(*, actor, query) -> dict
get_investigation_history(*, actor, investigation_id) -> dict
get_prior_research_assessment(*, actor, assessment_id, version) -> dict
correct_idea_family_association(*, actor, association_id, idempotency_key, payload) -> StoredResponse
```

These frozen signatures are later Backend-owned shared persistence services;
no callable stubs/in-memory substitute pretend to implement them. API/browser
will share domain rules. Writes will commit record/version/associations/impact/
idempotency together after authorized reference checks. StoredResponse preserves
status/serialized body. Lists authorize before counts/links/notices, newest-created
first with stable-ID tie-break. Historical reads never substitute latest endpoints.
Read schemas contain the common audit envelope and exact association endpoints.

H01–H20, independent Test/Risk, 34 unexecuted Stage 1 cases, restricted OPEN incident,
preserving DB procedure adoption/ordinary-role protection, integration, merge and
deployment remain separate unresolved gates. Builder pure checks earn no credit.
