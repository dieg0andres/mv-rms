# RMS-HN-API-1 — source implementation interface 1.2

The sole machine-readable contract is `rms/hypothesis_schema.json`. Its `$defs`
contain the request/context/error/completeness/read/history/list shapes;
`x-endpoints` binds routes to schemas. Hash the actual bytes and use the published
immutable commit, not a copied or guessed parallel schema. Frontend/Test receipt
commit/path/hash in MAU-140 before dependent integration; Director adopts it.

Authority: contract revision `3982eccc-e180-4ac9-bc70-9c4e16aa47f1`, preserved
source `de6b971b8b1ef8b5ab6d230641aaec0daeb7e374`, bounded-source confirmation
`b963d661-71bf-4a56-a591-0a42e31d843a`. The October 3 operator release in
MAU-142 comment `f44b4a69-5572-44eb-acbe-08a96e41cedc` supersedes the source
implementation hold. Migration and persistence/API source are now supplied;
no database execution, integration, merge, deployment or acceptance is claimed.
The accepted source contract remains unchanged. Director's recorded four-item
change request, relayed in MAU-142 comment
`651f6838-1212-4ad7-a18c-6f28ccce8083`, authorizes interface revision 1.1.
It adds classification readers; research fields, write payloads and record schema
version 1.0 remain unchanged. The original interface 1.0 is preserved at
`f633d6faba574603b929d3521b7f46c3990502dd:rms/hypothesis_schema.json`, SHA256
`ef2fe7d0e71d644ca978d7a3878f9ced4338212969cb6cdbc34a46550b73c5bc`.
Director handoff `c9666c52-7418-48ba-8f43-5fc57c6880a5` releases R4 role
reconciliation and R5 selection readers as interface 1.2. Reviewed interface 1.1
remains at `ac5b0291d6f12d75c54175a54cc224abc4876081`; its schema SHA256 is
`ad9042c79467ecf62adb29bde0781ec2cfd434f25233275adda1a80d59643049` and prose
SHA256 is `5c088e797544bbd706d4c24d332adb518c043876126749ee9a340c58bceb0b3d`.
The four approved corrections remain in place. Selection needs no migration.
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
JSON shape, NEVER a saved record or authorization. The authored shared services
add existence, synthetic visibility, compatible exact context, viewer/editor
rights, draft/proposed state, the exact software-scope reference, freshness and
persistent idempotency checks. Their database behavior remains unexecuted.
Do not wire pure helpers directly to routes or bypass those checks. No expression
is executed; this feature adds no research approval or authority-dispatch workflow.
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
payload values. The new adapters extend the existing 400 envelope as
`{error: {code: validation_error, message, request_id, fields: [...]}}`.
Preserve authentication/challenge, 403, uniform hidden/nonexistent 404, and 409
`stale_version`/`idempotency_conflict`. Idempotency-Key binds actor/method/route/
canonical payload; replay retains original status/body/identity. New-key identical
snapshots return 200 without a version. Persistence source implements these rules;
concurrent/PostgreSQL behavior still requires separately authorized verification.
JSON parsing accepts `application/json` with charset parameters, including
`application/json; charset=utf-8`. Malformed JSON and unsupported bodies retain
the safe 400 envelope; permission checks precede parsing. A mismatched saved
assessment link commitment fails closed with 503 `history_integrity_error`,
without returning the inconsistent history or rewriting its original rows.

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

Record-link arrays are transport descriptions: persistence source writes them as
first-class immutable endpoint associations, never authoritative JSON ID arrays.
External documents are labeled references, not fabricated future entities.

## Shared browser-service signatures — authored, DB execution unverified

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
get_idea_family_for_idea(*, actor, idea_version_id) -> dict
get_idea_family_association(*, actor, association_id, version=None) -> dict
get_idea_family_association_history(*, actor, association_id) -> dict
list_sources(*, actor, query) -> dict
list_ideas(*, actor, query) -> dict
```

Import Hypothesis functions from `rms.hypothesis_services`, and supporting
functions from `rms.research_context_services`. These are transactional Django
persistence services. API/browser share domain rules. Writes commit
record/version/associations/impact/
idempotency together after authorized reference checks. StoredResponse preserves
status/serialized body. Lists authorize before counts/links/notices, newest-created
first with stable-ID tie-break. Historical reads never substitute latest endpoints.
Read schemas contain the common audit envelope and exact association endpoints.

Mount `rms.hypothesis_api_urls` at the root URLConf using `include`; it contains
all 24 declared operations (21 patterns, three combined collection routes).
This source change intentionally leaves Director/Frontend-owned root URLs,
views and templates for their integration. The Basic authentication challenge
and safe error envelope are preserved by the new adapters.

Interface 1.2 declares 26 operations: the existing HN URL module still supplies
24 operations in 21 patterns, and the two selection GETs reuse the registered
SourceCreateView/IdeaCreateView collection routes. Their POSTs and URL names
`source-create` / `idea-create` remain intact; no duplicate routes are added.

## Shared access policy and selection readers — interface 1.2

Import `has_rms_read_access(actor)` and `has_rms_write_access(actor)` from
`rms.permissions`; import `list_sources` and `list_ideas` from
`rms.record_selection_services`. API and shared services enforce this policy
before record/count/link lookup, and Frontend consumes the same predicates:

| Principal | Permitted record reads/history/selection/counts | Create/correct |
| --- | --- | --- |
| Active authenticated editor | Allow | Allow |
| Active authenticated founder_viewer without editor | Allow | 403 |
| Active authenticated principal with neither group | 403 | 403 |
| Anonymous | 401 | 401 |
| Inactive principal | Deny | Deny |

Staff/superuser flags confer no bypass. Successful role authorization is still
followed by synthetic record visibility checks; hidden/nonexistent records keep
uniform 404. Legacy Source/Idea detail/history and Source manifest use the read
predicate too. The technical readiness endpoint retains its separate behavior.

`GET /api/v1/sources` and `GET /api/v1/ideas` accept only `page` and `page_size`,
as `SelectionQuery`. Defaults are 1/25; both are positive integers, maximum size
100. HTTP query fields must appear once with canonical ASCII decimal values;
unknown/repeated/noncanonical/zero/negative/over-limit values use the existing
safe 400 envelope. Shared browser services receive a validated integer mapping.
This adds selection only: no search, ranking, filters or library expansion.

`SourceSelectionList` / `IdeaSelectionList` reuse Pagination:
`{page, page_size, count, next, previous, results}`. Count and items use the same
synthetic identity queryset, ordered by identity `created_at` descending then
Source `source_id` / Idea `idea_id` ascending, irrespective of revision time.
No visibility filtering happens after counts/slicing. Each selected identity
must have its permitted exact latest version; missing/inaccessible latest data
or database unavailability fails safely as 503 `selection_unavailable`, never
as a reduced count or fabricated zero. No evidence bytes are loaded or returned.
Empty collections return count 0 and no pagination links; positive out-of-range
pages return empty results with the actual scoped count. Next links are null
after the last page; previous is null on page 1 or an empty collection, otherwise
it points to page minus one. Links use collection API paths and retain page_size.

Source items contain exactly `{stable_id, title, latest_version,
latest_version_id, links}`. Idea items add `status` from `workflow_status`.
Source latest IDs are `SRCV-` IDs; Idea stable/latest IDs are `IDE-` / `IDEV-`.
The derived links are:

| Item | detail | history | selected_version |
| --- | --- | --- | --- |
| Source | `/sources/{id}/history` | `/sources/{id}/history` | `/sources/{id}/history#source-version-{latest_version}` |
| Idea | `/ideas/{id}` | `/ideas/{id}/history` | `/ideas/{id}/history#idea-version-{latest_version}` |

These browser links grant no association authority. Existing detail/history
payloads remain intact. Frontend renders browser pagination from page/page_size,
not by navigating to API JSON; Home can request page 1/size 1 for scoped counts.
Distinguish a real zero from a service failure. Frontend/Test must receipt the
exact 1.2 schema/prose hashes supplied with the new candidate before consuming it.

## Classification reader handoff — interface 1.1

| GET route | Shared browser service | Response schema |
| --- | --- | --- |
| `/api/v1/idea-family-associations?idea_version_id={IDEV-uuid}` | `get_idea_family_for_idea` | `IdeaFamilyRead` |
| `/api/v1/idea-family-associations/{IFA-uuid}` | `get_idea_family_association` | `IdeaFamilyRead` |
| `/api/v1/idea-family-associations/{IFA-uuid}/versions/{positive_integer}` | `get_idea_family_association(version=...)` | `IdeaFamilyRead` |
| `/api/v1/idea-family-associations/{IFA-uuid}/history` | `get_idea_family_association_history` | `AssociationHistory` |

The lookup takes exactly one required `idea_version_id` query field, described
by `IdeaFamilyQuery`. It returns one current classification, not a paginated list.
An unclassified, nonexistent or inaccessible reference produces the uniform 404.
Other read routes accept no query fields. Viewer access is allowed; anonymous
and inactive/no-role principals are rejected before retrieval. Nested Idea/family
endpoints are authorized before serializing audit metadata or navigation links.

`IdeaFamilyRead` extends `AssociationRead` with `kind=IdeaFamily` and `links`.
Use `stable_id` (`IFA-uuid`) for the association identity, and `version_id`
(`IFAV-uuid`) for the exact existing family binding. `from` pins the Idea;
`to` pins the family. History returns `{results: [...]}` in ascending version
order with reasons, actors and predecessor IDs. The existing correction writer
retains its original request/response shape. Reading or discovering a current
classification does not adopt it: existing Hypotheses keep their pinned exact
association until an explicit full-snapshot Hypothesis correction is saved.

The originating-Idea history link uses the registered `idea-history` URL name,
which resolves to `/api/v1/ideas/{idea_id}/versions` on the existing application.

Assessment persistence now stores server-derived `link_count` and `link_digest`
before inserting its declared typed associations and external references. Both
are immutable and included in the version's row digest. No relationship IDs
are stored as authoritative parent JSON. Deferred guards validate the complete
ordered union, including an explicit empty set, at commit; extra, missing,
duplicate-position or changed links fail. Explicit case correction creates a
successor assessment when its links change. Readers verify the commitment too.

The unadopted preserving-runner manifest retains its original schema hash and
HOLD. It cannot authorize this changed schema: Director/Test/Operations must
review a newly bound procedure/candidate before any separately released DB work.
No runner execution or manifest adoption is claimed by this interface update.

See `docs/RMS-HN-API-1-IMPLEMENTATION.md` for model mapping, migration/rollback,
fixture source, DB-free commands and the remaining verification limits.

H01–H20, independent Test/Risk, 34 unexecuted Stage 1 cases, restricted OPEN incident,
preserving DB procedure adoption/ordinary-role protection, integration, merge and
deployment remain separate unresolved gates. Builder pure checks earn no credit.
