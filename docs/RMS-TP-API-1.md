# RMS-TP-API-1 — candidate revision 1.1

Contract: RMS Strategy Specification and Test Plan 1.0, Paperclip document revision `dec62ed2-adab-4ab3-bbfd-8dffbcee897d`, source SHA-256 `9236d104249fc796d3b5fbe214a5be92c4d4f95812ee17ba0f0fb99d1cb1a240`.

Schema: `rms/test_plan_schema.json`, schema version `1.0`, interface `RMS-TP-API-1`. SHA-256 `17e17d366e89fb0e69c3d992dd06da7b2345bcef6193170015b7b733e26df82e`. The schema is the shared field/type/enum/endpoint source. This candidate includes persistent services and additive migrations; PostgreSQL execution is a separate, coordinated check.

Director registers `path("api/v1/", include("rms.test_plan_api_urls"))` in the root URLconf. Paths have no trailing slash, matching existing API routes. Frontend calls `rms.test_plan_services` directly with its authenticated actor. No view or client should implement its own domain rules.

## Write and read shapes

All plan definition fields are under `fields`. Ordered `criteria` and `data_requirements` are top-level. `parameters` and `variations` are under `fields`. `implementation_target=quantconnect_lean`, `status=draft`, classification, actors, authority and digests are server-owned and forbidden in requests.

Creation may omit nullable fields and child arrays. A minimal syntactically valid invented fixture is:

```json
{"hypothesis_version_id":"HYPV-00000000-0000-4000-8000-000000000001","fields":{"title":"Invented first plan"},"criteria":[],"data_requirements":[]}
```

The invented ID must be replaced with an existing authorized exact Hypothesis version for persistence. A new child has null identity and version IDs:

```json
{"criterion_id":null,"criterion_version_id":null,"fields":{"name":"Invented criterion"}}
```

Data items use `data_requirement_id`, `data_requirement_version_id`, and `fields` (including a required parameter-style `key`). Child field schemas specify optional draft content. Read snapshots fill every declared scalar with null and collections with `[]`; no research values or thresholds are defaulted.

Corrections add `expected_latest_version` (integer) and nonblank `correction_reason`. Send the complete `fields` snapshot, exact Hypothesis version, and both child arrays. Every plan and child field must be present; empty arrays/nulls explicitly clear content. Reuse child IDs/version IDs from the immediately preceding snapshot. Changed content appends a child successor; unchanged content reuses its exact version. New null IDs create new children. Removing/reordering affects only the successor. Another plan's children or removed historical children cannot be adopted. A plan cannot switch Hypothesis identity or adopt an older Hypothesis version.

Reads include `plan_id`, `plan_version_id`, `stable_id`, `version_id`, `version`, `schema_version`, `status`, `classification`, `authority_reference`, `created_at`, `recorded_at`, `created_by`, `row_digest`, `fields`, child arrays, exact `associations`, `config_digest`, `configurations` (`key`, resolved `parameters`, `digest`), `configuration_count`, correction lineage/reason/changed paths, `implementation_target`, and `links`. `hypothesis` is the existing exact Hypothesis representation; `research_context` preserves its exact context. Intended benchmark remains in `hypothesis.fields`; the evaluation benchmark remains in plan `fields`.

Completeness uses `draft_completeness=complete|incomplete` and ordered RFC 6901 `missing_fields` with code `required_for_completeness`. Completeness is not approval, a result, or data qualification. Hypothesis completeness remains separate and unchanged. `current_indicators={as_of, upstream_notices, check_summary}` holds live notices/check context, excluded from immutable digests. Check summary statuses are `not_checked`, `partially_checked`, `checks_reported_passed`, `issues_reported`; counts are required pairs, reported pairs, and historical report count.

Services: `create_test_plan`, `correct_test_plan`, `read_test_plan`, `read_test_plan_version`, `read_test_plan_history`, `list_test_plans`, `read_criterion_version`, `read_data_requirement_version`, `record_data_access_check`, `list_data_access_checks`, `read_data_access_check`, and authorized `read_hypothesis_version(actor, version_id)` for creation preview. See schema `x-endpoints` and service signatures. Writes return `StoredResponse(status, body)`; reads return dictionaries. History is ordered by version. Version URLs use exact public version IDs, not integers.

## Cross-field validation

Supplied content must be structurally valid even when incomplete. Reject unknown/duplicate JSON fields, bodies over 512 KiB, invalid types, malformed dates/time zones/URLs, nonfinite decimals and incompatible conditionals. Decimal strings use plain base-ten syntax (no exponent); semantic decimal equality rejects duplicate configurations. Names/keys match `[a-z][a-z0-9_]{0,63}`. Parameters have matching typed values; variation overrides are a nonempty map of declared parameters. `baseline` is reserved. No generated combinations. Supplied trial budget covers baseline plus variations.

Missing date endpoints are incomplete, not guessed. Supplied date ranges are ordered; evaluation starts after development ends. Development-only clears evaluation dates. Same benchmark alignment clears difference reason. A benchmark defined without external input clears data keys; supplied keys must name retained requirements.

Objective criteria clear operator and numeric thresholds; numeric criteria clear objective-rule text. Upper threshold is allowed only for `between_inclusive`, and must be at least the lower threshold. Missing conditional content is incomplete. Numerical parameter units may be omitted only when meaning explicitly states dimensionless.

Data `used_by_configurations` refers only to declared keys and contains no duplicates. Empty draft applicability remains incomplete. All supplied method fields from another known method must be cleared. Method-specific names are in `DataFields.x-method-fields`: LEAN uses `configuration_arguments`; REST uses `request_parameters` (inert plain text defining non-secret path/query/body/headers); files use `file_location`, `file_format`, `file_schema`, `partition_pattern`, `parser_instructions`, `release_identifier`. `field_schema` items use `name`, `data_type`, `units_meaning`, `nullable`, `use`. `execution_tool` is required for `other_existing_tool`; `credential_alias` for `existing_alias`, otherwise they are cleared. All URLs/snippets are inert. Obvious credential patterns and signed/credential URLs are rejected; this is not comprehensive data-loss prevention.

Invalid examples: `trial_budget: true`; undeclared override; identical baseline/variant values; `rule_type: objective_rule` with a numeric threshold; `access_method: lean_sdk` with a REST base URL; `classification: real`; mismatched child IDs; correction missing explicit fields. These fail safely without partial writes.

## External reports and retries

Check requests contain every property in `CheckCreate`. A report names exact plan and requirement versions, one applicable configuration, performed time/identity/tool, explicit outcome, scope/observations, nonempty evidence references, limitations, and `sanitized_evidence_confirmed: true`. Evidence references are `{label, uri, revision, sha256}`; revision/hash may be null. URI is HTTPS or an inert URN, never dereferenced. No attachments/provider calls/code execution. Server separately records entering actor/time and binds requirement/configuration digests.

First report uses null `expected_current_check_id`, `supersedes_check_id`, `correction_reason`. A successor names the observed current check in both ID fields and supplies a nonblank reason, at the identical binding. History preserves originals. Earlier plan-version reports are historical and do not count as checks of a successor.

Every write requires `Idempotency-Key` matching `[A-Za-z0-9._:-]{1,128}`. Actor, POST route, key and canonical original payload bind storage. Current authorization is checked before replay. Replay returns original status and exact response bytes. A changed payload with the same key yields 409. Identical full correction under a new key yields 200 with `no_change: true`, without a new version. Expected plan/check heads serialize; stale requests yield 409 before any child write.

201: new plan/version/report; 200: read/no-change; 400: validation; 401/403: established active reader/editor predicates (no staff bypass); uniform 404: missing/unavailable exact reference; 409: stale head or incompatible key reuse. Safe errors retain existing `{error:{code,message,request_id,fields?}}` shape. Permission checks precede lookup/count and parsing. Session/CSRF remains provided by existing staging settings.

## Migrations and recovery

`0006_test_plan_records` adds plan/child identities, versions, associations and report tables with protected foreign keys. `0007_test_plan_history_guards` reuses existing identity append/watermark/immutable guards, adds deferred ordered count/digest seals (including initially empty child sets), same-plan ownership and Hypothesis identity rules, plus report binding/supersession guards. Association commitment format is UTF-8 lines sorted by kind and position: `kind:position:endpoint_public_id:required(1|0|-):association_public_id\n`. Immutable row digests cover association audit metadata. Child `content_digest` covers schema version and normalized fields only, excluding audit timestamps; `row_digest` covers the whole row. Report `requirement_digest` binds the child content digest.

The definition digest covers schema version, exact Hypothesis ID, normalized fields, ordered child version IDs/content digests and link count/digest. Configuration digests cover schema version, definition digest, key and resolved parameters. Audit save timestamps, links, upstream notices and check reports are excluded. These hashes are neither approval nor independent custody proof.

Both migrations are atomic PostgreSQL operations. If either fails, its transaction rolls back; inspect the migration ledger before retrying. Apply only to a coordinated authorized existing `rms_staging` slot. No new database, flush/reset/auth mutation is needed. Application rollback keeps additive tables and history guards; removing them is intentionally irreversible through ordinary migration reversal and requires separate review. Candidate tests must name the SQL role; schema-owner results do not prove administrator-resistant history.

## Revision 1.1 and reproducible checks

Supersedes the first unpublished candidate hash `81b351f0b9c31af9f3b3b09fa6c325e6f9405b6abd6f066a2828c50403e2d129`; its receipt and independent failures remain historical. Independent TP-SRC-01 identified context rounding in decimal duplicate detection; comparison now uses exact Decimal identity. TP-SRC-02 identified out-of-order completeness; missing paths now follow Purpose, Strategy, Data, Test design and Evaluation, preserving child order. This revision publishes the read envelope and pin-preview service, and separates child content hashes from audit row hashes.

TP-SRC-03 implementation correction keeps this exact revision 1.1 schema/hash. A structurally valid criterion may contain objective-rule text while its `rule_type` is null or omitted. Completeness now reports `/criteria/<position>/fields/rule_type` as `required_for_completeness`, preserves the supplied text and snapshot, and does not infer a type or raise an exception. Selecting `objective_rule` can make the definition complete when every other requirement is satisfied. Structural validation still rejects numeric-only content mixed with objective text. The fix removes a duplicate validation branch from completeness; it changes no endpoint, request/response schema, stored field, digest recipe or migration. Regression coverage exercises create and correction snapshots, null/omitted types, unchanged input and incompatible numeric content. These are source checks; independent retest and staging persistence remain separate.

Builder source checks (no DB):

```sh
.venv/bin/python -B -m unittest tests.test_test_plan_backend_validation tests.django_hypothesis_backend_validation_tests tests.test_hypothesis_staging_package -v
.venv/bin/python -B manage.py check
.venv/bin/python -B manage.py makemigrations --check --dry-run --skip-checks
```

Existing-staging builder checks, **not yet executed**: Director coordinates exclusive mutation slot and exact candidate integration/migration. Operations uses the existing authorized connection and actor bindings; do not create a database or change users. With `RMS_DB_NAME=rms_staging` and other connection settings injected, invoke:

```sh
.venv/bin/python -B -m tests.django_test_plan_backend_staging_checks \
  --hypothesis-version-id HYPV-<existing-authorized-version> \
  --editor-username <existing-active-editor> \
  --run-label <Paperclip-run-id> \
  --expected-sql-role <coordinated-existing-role>
```

This explicit module does not use Django's database-creating test runner. It checks title-only persistence/replay/revision/history, full fixture completeness and child reuse/change, denied cross-plan/stale writes, report supersession/historical attribution, committed two-session revision/report conflicts, ordinary UPDATE/DELETE/late association INSERT denial, and unchanged auth fingerprints. Invented committed records remain for inspection; there is no reset/cleanup. It requires installed migrations through 0007 and refuses another target/role. A compiled script is not execution evidence. Independent Test still owns TP01–TP24, including browser parity, upstream adoption, ordinary SQL-role limitations and installed-build claims.
