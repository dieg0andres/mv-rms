# RMS Hypothesis and Navigation Design Contract

**Version:** 1.0 — final design for handoff  
**Date:** October 3, 2026  
**Prepared for:** Diego Galindo, Director of Engineering, Backend Engineer, Frontend Engineer, and Test Engineer  
**Purpose:** Shared design criteria for the next synthetic RMS development increment.  
**Decision status:** Finalized at the founder's request for handoff. This document becomes the implementation contract when its exact saved revision is accepted in Paperclip. Record the current increment's closeout first, then start this increment under that acceptance. Merge and staging update follow the existing separate decisions.

### Handoff summary

- **Build:** Hypothesis drafts with clear research fields, immutable revisions, exact Idea/Source lineage, minimum research context, and navigation across the delivered application.
- **Reuse:** the existing Django application, permissions, repository, staging app, database, persistent volume, and private browser access.
- **Delivery owner:** Director of Engineering, from scope acceptance through independent verification, review, and the staging handoff.
- **Startup:** Operations verifies the task workspace bindings and existing runtime; Backend, Frontend, and Test each prove startup from their actual assigned task. Record this once using section 11.2.
- **Finish:** H01–H20 pass, the authorized merge and staging update are recorded, and Diego completes the browser walkthrough.

This is one bounded feature increment. Its small family/case setup supports the Hypothesis; it does not expand into a general research library or case-management product. The original draft is retained only as a superseded working record.

## 1 Product outcome

RMS supports an institutional-quality algorithmic trading research firm by preserving what was proposed, why it was plausible, how it was specified, which evidence informed it, and how it changed. A useful research record makes assumptions and uncertainty visible before testing.

This increment extends the existing Source and Idea features to **draft Hypotheses**, and makes every delivered screen reachable through normal navigation. A user starts at Home, opens an Idea, creates a Hypothesis, inspects its exact supporting records, revises it, and returns later to either version without typing a URL.

The same application services and validation rules serve the browser interface and authenticated API. Agents will eventually use those APIs to prepare research records. This increment provides recordkeeping and software verification using invented data; it does not perform research experiments or establish that a strategy works.

### Included

- Hypothesis creation, detail, exact-version retrieval, history, and revision.
- Explicit research and trading-rule fields, including entry, exit, holding period, sizing, universe, and intended benchmark.
- Exact originating Idea-version linkage and navigation through that Idea's existing Source-version links.
- Visible draft completeness, shared validation, existing viewer/editor permissions, concurrency protection, and duplicate-request handling.
- Home and persistent navigation to Sources, Ideas, Hypotheses, their existing records, forms, detail pages, and history.
- Minimum supporting research context as defined in section 5.
- Independent software verification and a browser demonstration on the existing staging stack after the normal review, merge, and deployment decisions.

### Later increments

Research recommendation and approval transitions; Test Plans and their finalized benchmarks, costs, samples, thresholds, budgets, and stopping rules; data qualification; strategy code generation; backtests; external connectors; research execution; protected final validation; automated family classification; and broad search or dashboard analytics remain separate increments. Current Source and Idea capabilities and saved data must continue to work.

## 2 Governing sources and design decisions

The approved baseline is [MAU-25 plan revision 3](https://paperclip-6vpg.srv1986614.hstgr.cloud/MAU/issues/MAU-25), document revision `6d1abb4f-4e3c-4bbf-8e1a-8c37dd0b3f2d`, especially sections 6–8 and 14.1–14.2 and its incorporated Research findings. The [MAU-37 architecture contract](https://paperclip-6vpg.srv1986614.hstgr.cloud/MAU/issues/MAU-37) and [MAU-38 data contract](https://paperclip-6vpg.srv1986614.hstgr.cloud/MAU/issues/MAU-38) supply implementation and preservation rules. The [founder firm brief](CEO_RESEARCH_FIRM_BRIEF.md) sections 4, 6, and 8 supply research purpose, role independence, and the broad market mandate. The [founder RMS direction](CEO_RMS_DIRECTION_FINAL_V1_0.md) supplies the application architecture and Paperclip authority boundary.

| Topic | Existing baseline | Resolution in this contract |
| --- | --- | --- |
| Entry and exit | Required in the section 14.2 amendment but absent as distinct named fields in the section 7 table. | Separate named fields for entry rules, exit rules, evaluation timing, intended execution timing, and exit precedence. |
| Horizon | A required duration with ambiguous meaning. | Separate expected effect horizon from maximum holding period. Both carry explicit units and timing conventions. |
| Sizing | Required text field. | Separate method, calculation basis, sizing rule, and exposure limits. |
| Benchmark | Required on the Test Plan. | Add an intended benchmark and rationale to the Hypothesis. A future Test Plan fixes the actual evaluation benchmark and references the Hypothesis version. |
| Drafts | Missing mandatory content blocks recommendation. | Permit incomplete draft saves, with explicit missing-field output. Completeness never grants research approval. |
| Evidence lineage | First-class versioned associations; immutable endpoint version IDs. | One originating Idea version per Hypothesis version in this increment; explicit revision is required to change that link. |
| Research context | Hypotheses belong to Investigations and families; opening a case requires a prior-research assessment or an approved exception. | Founder selected minimal real family/case setup. Include a short manual assessment, without an automatic exception or invented prior-work search. |
| Navigation | Individual forms and record screens exist. | Add a consistent navigation shell, simple record selection, and links between all delivered screens. |

These resolutions consolidate and refine the design. They are not claims about fields already implemented. Engineering must map each requirement below to its schema, API, UI, and test evidence; it must not implement only the older section 7 shorthand.

## 3 Meaning of a Hypothesis

An **Idea** describes a possible economic mechanism or opportunity. A **Hypothesis** turns it into a specific, falsifiable claim for a defined universe, direction, signal, timing, and trading expression. A future **Test Plan** defines how that exact hypothesis will be evaluated.

Keep these concepts distinct in labels and help text:

- **Signal:** the observation or calculation being measured.
- **Entry conditions:** the rules that turn the signal and other conditions into an intended position.
- **Exit conditions:** the rules for closing that position.
- **Expected effect horizon:** when the hypothesized economic or statistical effect should occur.
- **Maximum holding period:** the longest intended time a position remains open under the specified rules.
- **Falsification condition:** research evidence that would undermine the claim. A trade exiting at a loss does not by itself falsify a statistical hypothesis.
- **Intended benchmark:** the proposed comparison and why it fits this claim. It is a research assumption awaiting a Test Plan.

Support equities, ETFs, options, crypto, forex, and multi-asset proposals. Support long, short, and long/short directions without a default. Do not impose a universal geography, holding period, benchmark, return threshold, or risk limit. Specific research records must supply and justify their choices.

## 4 Hypothesis field dictionary

The field names below are the public contract for the new feature. Backend may select appropriate internal storage, while preserving these meanings and providing distinct, addressable fields. Do not combine the research specification into one notes field or store authoritative relationships as JSON ID arrays.

The new `effect_horizon` is the clarified implementation of baseline `horizon`; do not create two editable copies. The new sizing fields collectively implement baseline `sizing`. Document these mappings in the migration/schema notes. A structured duration in an API response represents named scalar research fields; it is not an authoritative relationship encoded as a JSON array.

### Save and completeness rules

**Required to save:** a nonblank title, an authorized exact originating Idea version, valid research context from section 5, and a nonblank origin rationale. Revision also requires the expected latest version and change reason. Identity, authorship, timestamps, classification, and status are assigned or validated by the server.

**Required for a complete draft:** all applicable research fields below. Missing values remain null or empty and produce a visible missing-field list. Provided values must always be valid: incomplete drafting does not permit a negative duration, an invalid enum, an inaccessible reference, or malformed data.

For text, trim outer whitespace for presence checks and reject whitespace-only values as missing. Optional values use null rather than placeholder text inserted by the application. A researcher may explicitly explain that an item is inapplicable inside its dedicated field; that explanation is reviewable content, not an automatically accepted scientific exemption. Unknown enum values are rejected. Changing a duration kind must explicitly clear or replace incompatible fields; never silently retain hidden conflicting values.

The server returns `draft_completeness` as `incomplete` or `complete`, plus field-level reasons. The calculation is schema-versioned and applies to the requested version. The workflow `status` stays `draft` in this increment. The UI calls a complete record **Draft complete**, never approved, validated, qualified, or ready to trade.

### Claim and rationale

This is a form section, not a separate ResearchClaim entity. Its title, claim, rationale, and related fields belong directly to each immutable Hypothesis version. The same applies to the other field groupings below.

| Field | Type | Definition and validation |
| --- | --- | --- |
| `title` | Text, 1–500 characters | Human-readable name. Renaming creates a revision and keeps the stable ID. |
| `claim` | Text, up to 4,000 characters | Measurable proposition: what is expected, under which conditions, over which horizon, and relative to what comparison. Numerical thresholds may be specified by Research; the application supplies none. |
| `claim_basis` | Enum | `gross_return`, `net_return`, or `other_measure`. For another measure, name its units in the claim. A net-return claim must identify its cost assumptions; final costs remain Test Plan responsibilities. |
| `economic_rationale` | Text, up to 4,000 characters | Mechanism explaining why the effect may exist. This field implements the baseline mechanism/economic-rationale requirement without a duplicate editable copy. |
| `expected_opportunity` | Text, up to 4,000 characters | Where the economic opportunity could arise, its practical relevance, and material constraints. Expected benefit is a proposition, not an observed result. |
| `persistence_argument` | Text, up to 4,000 characters | Why the opportunity might persist and what could weaken or eliminate it. |
| `competing_explanations` | Text, up to 4,000 characters | Plausible alternatives, known exposures, and confounds. If none have been identified, record that limitation and the reasoning; never imply an exhaustive review. |
| `falsification_condition` | Text, up to 4,000 characters | Observable findings that would undermine the claim. State what would remain inconclusive or reflect data/implementation failure. Later Test Plan criteria make evaluation operational. |

### Universe and signal

| Field | Type | Definition and validation |
| --- | --- | --- |
| `market` | Enum | Existing RMS choices: `equities`, `etfs`, `options`, `crypto`, `forex`, `multi_asset`. No preselected answer. |
| `universe` | Text, up to 4,000 characters | Geographic/venue coverage, eligible instruments, inclusion/exclusion rules, and how and when membership is determined. A fixed fictional list is acceptable for this increment. Real historical membership later requires the qualified Data records. |
| `direction` | Enum | `long`, `short`, or `long_short`. For long/short, describe each leg's rules in the signal, entry, exit, and sizing fields. |
| `signal` | Text, up to 4,000 characters | Formula or event, required inputs, lookback, units, thresholds where chosen, and observation frequency. Define terms so another researcher can reproduce the intended calculation. |
| `information_availability` | Text, up to 4,000 characters | When the inputs are assumed to become knowable, publication/processing delays, and how later revisions are treated. Distinguish the event's time from its availability to a decision-maker. |
| `decision_schedule` | Text, up to 2,000 characters | When the signal and entry/exit conditions are evaluated: frequency or event, time zone, and calendar/session convention. |

### Entry exit and duration

| Field | Type | Definition and validation |
| --- | --- | --- |
| `entry_conditions` | Text, up to 4,000 characters | Explicit trigger plus eligibility/position-state filters. Define equality boundaries, repeated signals, re-entry, and whether adding to an existing position is permitted. |
| `execution_timing` | Text, up to 2,000 characters | Intended entry/exit timing relative to the decision and available information. A closing observation cannot silently imply an already-known same-close fill. Detailed order/fill simulation belongs to a future Test Plan and implementation. |
| `exit_conditions` | Text, up to 4,000 characters | Signal reversal, scheduled exit, price/risk rules, or other closing conditions that apply. Explicitly state when a category is unused; do not insert default stops or profit targets. |
| `exit_precedence` | Text, up to 2,000 characters | Which rule wins when exits coincide; how the maximum holding limit interacts with other exits. If only one exit exists, state that. Unknown within-bar ordering must remain a limitation for the future Test Plan, not an assumed favorable fill. |
| `effect_horizon` | Duration specification | Expected time for the claimed effect to appear, with its own start anchor. This is not the trade's time limit. |
| `maximum_holding_period` | Holding specification | Mandatory explicit policy: fixed duration, event-based closure, or no fixed time limit with a reason and defined exit rules. Absence is not equivalent to unlimited holding. |

**Duration specification:** `kind` is `fixed` or `event_based`. To be complete, a fixed duration has positive decimal `quantity`, `unit`, `start_anchor`, and `counting_convention`. Units are `seconds`, `minutes`, `hours`, `calendar_days`, `trading_sessions`, or `bars`. Trading sessions require `calendar`; bars require `bar_definition`. Event-based duration has an `event_condition` and `start_anchor`. Partially specified objects may be saved as incomplete drafts if every supplied value is valid and no incompatible fields coexist. All conditions are stored as explicit research descriptions; no expression is executed by RMS.

**Holding specification:** uses the duration structure above, or `kind=no_fixed_time_limit` with `rationale`. An event-based policy also states what happens if the event never occurs. A no-fixed-limit policy explicitly acknowledges potentially open-ended holding; it is neither a system default nor approval of its risk. Quantitative Research and subsequent Risk review determine whether the proposed policy is acceptable.

Decimal quantities are represented as decimal strings in the API, not binary floating-point measurements. Reject zero, negative, non-finite, inconsistent, or unknown duration values. Whole-session/bar counting must state how the entry session/bar is counted; the UI must show the unit and convention together.

### Sizing and economic comparison

| Field | Type | Definition and validation |
| --- | --- | --- |
| `sizing_method` | Enum | `fixed_units`, `fixed_notional`, `equity_fraction`, `risk_budget`, `volatility_target`, `equal_weight`, or `custom`. These are descriptions of intended methods, not implemented calculators. |
| `sizing_basis` | Text, up to 2,000 characters | Quantity or portfolio measure used, when it is measured, currency where relevant, and whether exposure is notional, capital, risk, or another defined measure. |
| `sizing_rule` | Text, up to 4,000 characters | Formula/parameters, units, rounding, rebalancing, multiple simultaneous signals, and any instrument-specific conversion needed. A percentage must identify its denominator. |
| `exposure_limits` | Text, up to 4,000 characters | Proposed per-position and portfolio constraints, concurrent positions, gross/net exposure and leverage/margin/borrow assumptions where applicable. Explain inapplicable items. No application-wide numerical defaults. |
| `implementation_assumptions` | Text, up to 4,000 characters | Known liquidity, spread, fees, slippage, borrow, funding, settlement, contract, and data constraints. State relevant unresolved assumptions. This anticipates the later Test Plan's exact models without claiming they have been established. |
| `intended_benchmark_name` | Text, up to 500 characters | Proposed named comparison, such as specified cash, an index, a matched exposure, or another research baseline. No universal default. |
| `intended_benchmark_definition` | Text, up to 4,000 characters | What is compared, matching time window and exposure where applicable, return/measurement basis, currency, and rebalancing assumptions if relevant. A ticker alone is insufficient. |
| `intended_benchmark_rationale` | Text, up to 4,000 characters | Why this comparison tests the claim and what it does not control for. |
| `research_limitations` | Text, up to 4,000 characters | Known uncertainty and unresolved assumptions. Optional to save; required for completeness, including an explicit statement when none are currently identified. |

All non-title text fields above may be absent in an incomplete draft. The completeness indicator checks required presence and valid shape; substantive scientific adequacy remains a Research responsibility, with independent Risk challenge. Plain text is escaped on display and never evaluated as code or rendered as user-provided HTML. This feature has no attachment or credential-entry capability; help text tells users to keep secrets out of research descriptions.

### Benchmark ownership

The Hypothesis stores the **intended** benchmark because the comparison helps define the claim. When Test Plans are implemented, each plan references an exact Hypothesis version and stores its **final evaluation** benchmark. An intentional difference must have a rationale. A difference that changes the scientific claim requires a new Hypothesis version and the applicable later approvals. The Hypothesis screen will display the intended value and linked Test Plan values separately; never maintain two silently synchronized editable authorities.

## 5 Research context and relationships

**Founder choice recorded in this chat:** include the minimum ResearchFamily and Investigation setup in this increment. Use **Research family** and **Research case** as UI labels; `Investigation` remains the backend entity name.

A family groups related mechanisms and variants. A case organizes one coherent investigation within that family. Each Hypothesis belongs to one case. A case can contain several Hypotheses; a Hypothesis version has one originating Idea version. Its supporting Sources are reached through that exact Idea version's existing contributions.

### Minimum supporting records

| Record | Required content for creation | Behavior in this increment |
| --- | --- | --- |
| ResearchFamily | `name`, `mechanism_boundary`, `distinctness_rule`; optional existing Risk review reference | Create, select, read, and revise with history. The distinctness rule is a proposed grouping rationale; it does not certify that a new research cycle is materially distinct. |
| Investigation | `title`, exact family-version reference, `owner_role`, `priority`, `next_action`, and prior-research assessment reference | UI calls this a Research case. State stays `proposed`; opened-at, author, and identity are server-assigned. Optional blocker text may describe a limitation but does not implement the later blocker workflow. |
| PriorResearchAssessment | `query_scope`, `query_time`, `policy_version`, `result_watermark`, `finding`, `rationale`, `limitations`, and available exact record links | A brief manual review record before creating a case, consistent with the approved design. It documents what was actually checked and the limitations of that check. |

Supporting text is limited to 4,000 characters per explanatory field and 500 per title/name. Priority is `low`, `normal`, or `high`, selected explicitly. For the synthetic prototype, `owner_role` is a role label, not a grant of system access. A case correction appends a new version with reason, expected-version validation, and preserved history; it does not activate research.

The prior-research form asks **What did you check? When? What did you find? How does this case relate?** `finding` uses `extends`, `contradicts`, `replicates`, `repeats`, `unrelated`, or the proposed addition `no_relevant_work_found`. The last choice requires the checked scope and a limitation statement; it never means the entire firm has no relevant work. `result_watermark` identifies the records/versions or dated external review boundary actually examined. `policy_version` identifies the accepted review procedure. Do not default a successful review, invent returned records, or create a hidden exception.

**Minimum manual procedure for this increment:** inspect the selected synthetic Idea and the available family/case records relevant to its stated mechanism; identify the exact records inspected, or explicitly record that none were available within the stated scope; record the time, finding, rationale, and limits of the review. On contract acceptance, section 5 and that accepted document revision supply the procedure reference for `policy_version`. This records a bounded manual review, not an automated search or scientific novelty approval. `query_time` is the actual review time entered by the reviewer; the server separately records when the assessment was saved. Supply a dedicated `limitations` field, required for every assessment.

Keep semantic links as versioned association rows: Idea-to-family, case-to-family, case-to-prior-assessment, Hypothesis-to-case, and Idea-to-Hypothesis. Reuse accepted equivalents if Engineering already has them; these are logical contracts, not instructions to create duplicate tables. Each carries the common envelope from section 6 and immutable endpoint versions. Prior-assessment links to existing cases use the established PriorResearchInvestigation semantics; links to unavailable future entity types are not fabricated. An external document reference is labeled as such.

### Binding and revision rules

- Every new Hypothesis version pins one case version and one originating Idea version through first-class associations. The IdeaHypothesis association also records `origin_type=direct` and a nonblank `rationale` in this increment. Composite origins are deferred.
- That Idea must have one explicit family association consistent with the case's family identity. Existing Ideas currently lacking family metadata receive an explicit, attributable association when first used here; their original version content is not rewritten. The Hypothesis pins the family-context association versions it relies on.
- When first assigning an unclassified Idea version, the form explicitly asks the editor to confirm the chosen family and give a grouping reason. The server may create that versioned association in the same transaction as the Hypothesis only with this explicit instruction. Existing associations are selected by exact version; they are not silently replaced. Conflicting family assignments return a field error and no partial writes. Reclassification uses an explicit versioned correction in the context interface, with the same permissions, reason, conflict, and history rules.
- An Idea version cannot simultaneously belong to conflicting families. A later reclassification requires explicit versioned changes and reasons. A materially different mechanism is proposed as a new family/case; the system does not automatically certify its novelty or count credit.
- Corrections to family/case context preserve all older Hypothesis bindings. To adopt revised context, append a Hypothesis version with reason. Never substitute whichever parent is latest during historical retrieval.
- Do not require the Idea's display status `accepted` as a research approval. Authorized editors may draft from a permitted synthetic Idea. Show rejected or superseded origins clearly, and require a specific origin rationale explaining their use; creation does not reactivate the Idea or approve progression.
- The user explicitly selects a suitable existing case or creates one through the compact context form. Do not auto-create an unnamed family, empty case, fabricated assessment, or preapproved parent to satisfy a foreign key.

Add **Research context** under the main navigation for simple family/case selection, creation, detail, revision, and history. The Hypothesis form links directly to this setup and returns with the chosen case. An additive migration must allow existing Source/Idea data to remain as it is; the new binding requirements apply when those Ideas are used in this feature.

The supporting records follow the same permissions, exact-version access, idempotency, stale-write protection, and preservation rules as Hypotheses. Their route and payload schemas must be included in the shared API contract before Frontend integrates them. This is minimal context and manual prior-work recording; family analytics, automated novelty classification, and a full case lifecycle remain later work.

## 6 Identity history and corrections

Use a stable Hypothesis identity `HYP-{uuid}` and an immutable version identity `HYPV-{uuid}`. Each substantive save appends a sequential version under that identity. A newly intended variant is a separate Hypothesis linked to its family and originating Idea; it must never count automatically as a distinct research cycle.

Every Hypothesis version and material association carries the baseline common envelope: stable ID, immutable version ID, schema version, created-at/by, recorded-at, classification, authority reference, state, row digest, impact status, and optional superseded-version/correction references. Effective dates are present where applicable, not fabricated. Times are UTC. Synthetic classification and the Hypothesis workflow `status=draft` are enforced on the server and in persistence constraints. Association lifecycle states retain their separate meanings from the baseline; a relationship's effective state does not approve its Hypothesis.

The authority reference identifies the accepted software/synthetic-use scope. It is not a hypothesis research approval. Clients cannot supply their own author, approve a record, change classification, set a digest, or override server-owned metadata.

A revision requires a reason and an expected latest version. It records changed fields and preserves every prior version and association. Changing title, claim, rule, benchmark intention, context, or originating Idea creates a new version. Submitting an identical payload under a new request key returns a no-change response and creates no empty version; retrying the original key returns its original result.

Corrections to a Source or Idea never retarget existing Hypothesis links. The current view indicates when a newer upstream version exists, while the historical view continues to show the exact version used. An explicit Hypothesis revision may adopt a newer Idea version and must state why. It must not automatically copy changed thesis text into the Hypothesis.

Create a versioned correction-impact record for directly affected linked Hypothesis versions when an upstream version changes. Record a visible review-needed state, preserving historical meaning. This increment records impacts; it does not determine scientific materiality automatically or build the later review/approval workflow. Distinguish revision supersession from the Hypothesis workflow status: old draft versions remain historically draft.

Impact coverage includes the existing Source → Idea → Hypothesis path: a corrected Source can affect a Hypothesis through its pinned Idea contribution even if that Idea has not itself been revised. Identify impacted versions, not only their logical IDs. Preserve the completed record and show the unresolved upstream review separately from field completeness. The integration tests must verify that affected version links are neither omitted nor retargeted.

Historical research rows and associations are protected against ordinary update or deletion through UI, API, and the application database role. Reuse the existing preservation mechanism and verify it for new records. Server-derived latest-version pointers and display projections may be updated. A digest detects content changes; it does not establish protection against a privileged database administrator or independent evidence custody.

## 7 Backend service and API criteria

The routes below are **proposed new routes**, to be delivered with the shared schema. Keep existing Source and Idea routes working.

| Method and route | Behavior |
| --- | --- |
| `POST /api/v1/hypotheses` | Create a draft identity, version 1, and required context/Idea associations atomically. |
| `GET /api/v1/hypotheses` | Authorized, paginated latest-version summaries for navigation; optionally filter by originating Idea. |
| `GET /api/v1/hypotheses/{hypothesis_id}` | Latest version, draft completeness, exact origin/context links, and newer-upstream notices. |
| `GET /api/v1/hypotheses/{hypothesis_id}/versions/{version}` | Exact immutable version and the endpoint versions it actually cites. |
| `GET /api/v1/hypotheses/{hypothesis_id}/history` | Ordered versions, changed fields, reason, actor, timestamp, and version links. |
| `POST /api/v1/hypotheses/{hypothesis_id}/corrections` | Append a new draft version with required `expected_latest_version` and `correction_reason`. |

New write operations reuse the established idempotency mechanism, with request identity bound to the authenticated principal, method, route, and canonical payload. Repeating a key with identical content returns the original result; changing its content returns conflict. One transaction commits the record, version, relationships, correction/impact facts, and idempotency result. Concurrent identical requests create one result; two revisions from the same expected version cannot both succeed.

**Write envelope:** the new Hypothesis request contains `originating_idea_version_id`, `origin_rationale`, `investigation_version_id`, `idea_family_binding`, and `fields`, where `fields` contains the exact field keys in section 4. The family binding is either `{mode: existing, association_version_id: ...}` or, for a currently unclassified Idea version, `{mode: create, family_version_id: ..., rationale: ...}`. The create form is an explicit instruction, not a default. Its family version must be the case's selected family version; an existing association must identify the same family identity. The server validates and freezes the exact compatible family associations from section 5 in the same transaction. `origin_type` is server-fixed to `direct` for this increment. The idempotency key uses the existing API's transport convention. A correction additionally contains `expected_latest_version` and `correction_reason` and sends the complete proposed `fields` snapshot, including explicit nulls for fields intentionally left empty; it also restates the origin, case, and family binding. Do not interpret a correction as an ambiguous partial patch. Creation may omit nullable fields; detail responses expand them consistently to null. The shared machine-readable schema defines the precise JSON types for this envelope.

**Read envelope:** return `hypothesis_id`, `hypothesis_version_id`, `version`, `schema_version`, `status`, `classification`, `fields`, `origin`, `research_context`, `created_at`, `created_by`, `draft_completeness`, `missing_fields`, `upstream_notices`, and navigation `links`. History/version responses also include `corrects_version`, `correction_reason`, and `changed_fields`. `origin` and `research_context` display the actual pinned entity and association versions. Links are derived navigational aids; the stored versioned associations remain authoritative. Existing application conventions can supply additional audit fields from section 6.

For minimal context, provide create/list/detail/exact-version/history/correction operations under `/api/v1/research-families` and `/api/v1/investigations`, following the same endpoint pattern as Hypotheses. A new case references an exact family version and submits the manual prior-research assessment in the same case-creation transaction; persist that assessment as its own versioned record and return its ID and read-only detail. It is not an unstructured field inside the case. A corrected assessment appends its successor with the case correction and preserves previous case/assessment bindings; unchanged assessments retain their existing version. Parent mutations use the same full-snapshot and conflict rules. Include an explicit family-association correction operation for an Idea version in the shared API schema, reusing the existing association service if present. A correction names the exact prior association version, the target family version, and a reason. Frontend and Backend must agree the resulting context payload schema before integration; the required content is fixed in section 5. Route naming for supporting operations is an Engineering implementation choice recorded once in that schema, not a new founder approval.

Use 201 for a new record/version; 200 for a read or a successful no-change response; 409 for a stale version or incompatible idempotency reuse; and the established API's 400 validation response for invalid fields. Replays preserve the original response status and identity. Return stable machine-readable error codes and field paths for the UI. Follow the existing authentication challenge and 401/403 behavior. A hidden or inaccessible record uses the established uniform not-found/denial policy without leaking its title or contents.

Validate reference existence, exact version, classification, allowed context, and access before mutation. Reject cross-context inconsistencies, a second originating Idea association for the same version, and illegal status values. Do not allow partial rows after validation failure. All writes use the same service layer from API and browser submission.

Navigation lists use bounded pagination, default 25 and maximum 100, with deterministic newest-created-first ordering and stable-ID tie-breaker. Record counts and links are permission-scoped. Basic title/ID selection may be provided to make navigation workable; advanced search, ranking, and analytics are outside this increment.

Publish the field and response schema, including enum values, null handling, duration shape, error codes, metadata, and completeness paths, in `mv-rms` with the implementation. Provide additive migrations and one idempotent invented fixture. Preserve existing records, application identities, and authentication. No new database, container, queue, or external service is required by this design.

## 8 Frontend navigation and interaction criteria

Use Django templates, reusable HTML/CSS components, and plain JavaScript within the existing application. Provide persistent **Home, Sources, Ideas, Hypotheses, Research context** navigation, a visible viewer/editor role indication, and a synthetic-data notice. Show a safe deployed version identifier through the existing staging version information.

| Screen or action | Required behavior |
| --- | --- |
| Home | Clear links into each implemented record type and available create actions. All delivered screens are reachable without typing endpoints. |
| Record selection | Simple paginated Source, Idea, and Hypothesis records showing title, stable ID, latest version, and applicable status. Enough to reopen previously saved work. |
| Source pages | Reach existing detail/history, manifest download, creation, and correction from normal links; preserve current permissions. |
| Idea detail/history | Show exact Source-version contributions and linked Hypotheses; provide Create Hypothesis for editors. |
| Hypothesis creation | Begin from an Idea or select an Idea from the Hypotheses page. Display and pin its selected version. Select or set up the required context from section 5. |
| Hypothesis form | Group fields into Claim and rationale, Universe and signal, Entry and exit, Duration, Sizing, and Benchmark and limitations. Field labels, help, units, and enum choices match section 4. |
| Research context | Select, create, read, revise, and inspect family/case history. Record the manual assessment as part of case setup. Show and explicitly correct an Idea's family association, including its reason and preserved history. Return to the unfinished Hypothesis form with its input intact. |
| Hypothesis detail | Display draft status/completeness, exact originating Idea version, supporting Source links, research context, author/time/version, and all entered fields. Missing fields are visible. |
| Revision | Load the selected latest version, require a change reason, show the changed fields after save, and preserve all original versions. Label the action Revise hypothesis. |
| History | Open either version; display correction reasons, actors, times, and exact upstream links. Distinguish latest view from historical view. |
| Conflicts and failures | Preserve unsaved form input, explain field errors, and offer a link to the latest record on conflict. Never retry a stale save by silently overwriting another person's revision. |

Success navigates to the saved record and confirms the saved version. Double-clicking Save or retrying after a lost response must not create a duplicate. Browser refresh and back/forward navigation must behave predictably. A user must be able to return to Home from every page, including error, history, and form pages.

Viewer accounts can navigate and read permitted records/history but cannot create or revise them. Editor actions are hidden or disabled with clear explanatory text for viewers; server enforcement is mandatory. The founder's existing editor account can be used for the demonstration without changing the founder viewer account's role.

Provide keyboard-accessible controls, associated labels, focus on validation summaries, readable layout on a laptop and narrow viewport, and text conveying state without relying on color. The sidebar/menu and record links must cover existing Source and Idea screens as well as the new Hypothesis screens.

Links labeled with a particular Source or Idea version must open that version visibly, using an exact-version page or an anchored/selected history entry. They must not land on an unlabeled latest record. On the hypothesis form, show the originating Idea as read-only reference content; an explicit Copy from Idea action may help populate relevant fields, but copied text becomes part of the saved Hypothesis version and does not update automatically.

## 9 Fictional acceptance example

**Everything in this example is invented for software verification. Values are not company defaults, investment recommendations, observed evidence, or approval to execute a strategy.**

| Element | Fictional value |
| --- | --- |
| Source and Idea | An existing synthetic Source supports Idea version 1, Transient selling pressure. Record their actual fixture version IDs. |
| Title and claim | Next-session reversal after a large down day. Conditional on the stated signal, mean next-session open-to-close gross total return is expected to exceed matched-window zero-yield cash. |
| Mechanism and opportunity | Temporary selling pressure may depress prices; a following-session reversal may create an opportunity. Trading costs and capacity could remove it. |
| Persistence | Episodic liquidity needs could recur; competition could reduce the effect. |
| Competing explanations | Broad market rebound, risk exposure, fixture construction, and unavailable entry prices could explain apparent results. |
| Falsification | A later valid preregistered test finding no predicted directional advantage under its specified criteria would undermine this claim. Insufficient observations or unavailable data would remain inconclusive. |
| Market universe direction | ETFs; fixed fictional members SYNTH-ETF-A, B, and C; long. Membership is fixed before the fictional observation window. |
| Signal and information | Prior session close-to-close total return at or below -2%. Observe after the close, with an explicitly assumed five-minute availability delay. |
| Decision and entry | Evaluate after that delay using the explicitly enumerated SYNTH-NY session calendar in America/New_York, with fixture opens at 09:30 and closes at 16:00. Enter at the next session open only if flat. If several members qualify, select the most negative return; break ties alphabetically by fixture symbol. Repeated signals while invested do not add to the position. |
| Exit | Close at that session's close. No price stop or profit target is used. The scheduled exit and maximum-holding rule refer to the same close. |
| Effect horizon | One trading session, anchored to the next session's open. |
| Maximum holding | One trading session from entry; the session containing the fill counts as session one and ends at its scheduled close. |
| Sizing | Equity-fraction method; target 10% of pre-entry portfolio equity, based on a price available before submission, rounded down to whole units. Maximum one open position and 10% intended gross exposure; no leverage or short borrowing. Actual fill and exposure handling await the Test Plan. |
| Intended benchmark | Fictional zero-yield USD cash over the same open-to-close windows. It compares taking the proposed position with remaining in cash; it does not control market beta. |
| Limitations | No qualified data, final cost model, execution model, statistical threshold, sample requirement, independent research verdict, or research result exists. |

Create a fictional family named Temporary liquidity pressure, a proposed case named Synthetic next-session reversal, and a manual prior-research assessment describing the fixture records actually inspected. Use the real saved version IDs in associations; do not place the illustrative names where foreign keys are required. The session calendar is part of the deterministic invented fixture and makes no claim about any real exchange schedule.

The walkthrough creates Hypothesis v1 from Idea v1, then revises the Idea to v2. Hypothesis v1 must still cite Idea v1 and its Source versions. The user then creates Hypothesis v2 with a reason, explicitly adopting Idea v2 and changing one rule. Both Hypothesis versions remain accessible with their different origins. A separate sibling Hypothesis proves that one Idea can support more than one Hypothesis identity without changing family or research-cycle accounting automatically.

## 10 Independent software acceptance

Test Engineer verifies the integrated frontend/backend candidate at one named commit. Evidence must distinguish automated software checks, actual browser observations, and any unexecuted case. Assertions about scientific quality or independent Risk acceptance require their own research process.

| ID | Observable acceptance criterion |
| --- | --- |
| H01 | From Home, an editor opens an existing Idea and creates Hypothesis v1 using the fictional example; the saved record reopens after refresh. |
| H02 | The Hypothesis displays the exact originating Idea version and its exact Source-version links; links work in both directions where provided. |
| H03 | Saving an incomplete draft succeeds with a precise missing-field list. Completing it changes only draft completeness, not workflow authority. |
| H04 | Provided invalid enum, duration, decimal, inaccessible ID, or contradictory duration fields are rejected with field errors and no partial rows. |
| H05 | An expected horizon and maximum holding period with different anchors/units remain distinct through save, read, edit, and history. |
| H06 | Entry, exit, signal, execution timing, and exit precedence round-trip independently. No values are silently invented. |
| H07 | Intended benchmark and rationale round-trip with the intended label; no Test Plan or research approval is created. |
| H08 | Revising a Hypothesis produces v2 with reason, changed fields, actor, and timestamp; v1 content and associations remain identical. |
| H09 | Revising a Source or Idea leaves existing Hypothesis citations pinned, records the applicable impact, and shows a newer-version notice. Explicit adoption creates a new Hypothesis version. |
| H10 | Same request key/content, including concurrent retries and browser double submission, creates one result. Changed content under the same key fails. |
| H11 | Two edits based on the same latest version yield one accepted revision and one conflict, preserving the losing form's input. A genuine no-change save adds no version. |
| H12 | Viewer read/history succeeds; viewer writes and anonymous access fail consistently through both browser and direct API. Server-owned metadata cannot be forged. |
| H13 | Invalid/missing context and a second origin association fail atomically; one Idea can legitimately have multiple separate Hypotheses. |
| H14 | Original research/version/association rows cannot be updated or deleted by ordinary API or the application database role. Derived pointers can be maintained without rewriting history. |
| H15 | Every existing and new screen in section 8 is reachable by clicks; users can reopen saved records without knowing an endpoint. Pagination is deterministic and permissions apply to links and counts. |
| H16 | Keyboard navigation, labels, error focus, duration controls, and narrow layout work. Untrusted field text renders safely as text. |
| H17 | Existing Source/Idea create, revision, manifests, history, permissions, idempotency, and conflict behavior pass relevant regression tests. |
| H18 | Additive migrations and the idempotent fixture preserve existing staging data. The release records the deployed commit; operator procedure identifies rollback compatibility and preserves existing app/database/volume. |
| H19 | Create a truthful fictional family, manual prior-research assessment with its scope and limitations, and proposed case through the context setup. A missing assessment or inconsistent family link prevents case/Hypothesis creation. First family assignment requires explicit confirmation and a reason; no empty parent, automatic grouping, or hidden exception is inserted. |
| H20 | Correct a family, case, assessment, or Idea-family association with a reason; old Hypotheses retain their exact context versions. Viewer denials, idempotency, and stale-write behavior also apply to supporting-record routes. Return from context setup with unsaved Hypothesis input preserved. |

**Founder demonstration:** open Home → select Idea → create draft Hypothesis → inspect supporting records → revise → compare v1 and v2 → return Home and reopen it. Observe using an editor account, then confirm viewer read-only behavior. A failed or unexecuted mandatory case remains visible and prevents this increment being described as complete.

## 11 Delivery ownership and handoff

### 11.1 Accountable owners and the delivery sequence

| Owner | Deliverable |
| --- | --- |
| Director of Engineering | One integrated scope and candidate release; own successful task startup and handoff receipt, resolve concrete dependencies, maintain the requirement mapping, review implementation, and drive the feature through independent verification and the normal merge/staging handoff. |
| VP of Data & Engineering | Resolve cross-role assignment or resource conflicts that the Director cannot resolve; ensure addressed questions reach an agent who actually starts. Consolidate only decisions that need founder authority. |
| Backend Engineer | Models/associations, migrations, service rules, API schema, validation, completeness calculation, preservation/concurrency behavior, and an idempotent synthetic fixture. |
| Frontend Engineer | Shared navigation, forms, record selection/detail/history, exact-version links, completeness/error/conflict handling, accessibility, and the browser walkthrough. |
| Research and Data | Confirm scientific field meanings and truthful fictional parent context; verify lineage/cardinality. Supply bounded corrections to this contract rather than a new architecture exercise. |
| Test Engineer | Independently execute H01–H20 against the named candidate; report evidence, defects, and unexecuted cases. |
| Operations | Own execution-workspace provisioning, runtime/bootstrap compatibility, and approved task bindings. Use the existing staging stack and completed lifecycle procedure for the separately authorized update. Preserve the existing database, volume, accounts, and private access; identify actual migration/rollback implications. |
| Diego | Accept the bounded design/scope, retain the current merge authority unless expressly delegated, and inspect the staged result in the browser. |

Follow the established flow: founder accepts scope → Backend/Frontend implement on a feature branch and open a PR → Test independently verifies → Director reviews and resolves findings → authorized operator merges to `master` → Operations coordinates staging → founder inspects. Routine fixes within the accepted increment belong to its delivery work. A material design/scope change requires an explicit decision.

Store the accepted contract, API schema, migrations, tests, fixtures, and release/update instructions in `mv-rms` with the change. Paperclip records the accepted document revision, assignments, review evidence, and decisions. Secrets and database contents remain outside GitHub. Update staging packaging to serve the reviewed release rather than retaining a hardcoded prior product identity.

First record a concise closeout of the current Source/Idea and staging milestone: completed work, applicable acceptance evidence, and explicit remaining limitations with owners. If MAU-44 stays open as a larger umbrella, close the bounded milestone under it rather than waiting for every future Stage 1 capability. An unresolved item blocks this increment only when the Director identifies the specific requirement or existing authority boundary it prevents satisfying; it must not be silently dismissed or converted into full acceptance. Create a separately identified Hypothesis/navigation increment with this contract as its accepted scope.

### 11.2 One startup record before implementation

Use **one shared readiness table on the new increment**, with one row each for Backend, Frontend, and Test. Update it in place; do not create repeated readiness approval cards. Operations supplies the setup, each receiving agent runs its checks, and the Director owns the result.

| Required entry per role | Evidence to record |
| --- | --- |
| Actual task and owner | Task ID, assigned agent, and the Paperclip execution-workspace binding visible on that task. An agent's default working directory alone is insufficient. |
| Repository and code | Remote repository, fetched `master` base commit, unique working branch or independent review checkout, and current HEAD. Preserve unrelated shared work and existing changes. |
| Runtime | Bootstrap/provisioner revision, environment path, successful provisioner/metadata check, and imports using the approved pinned runtime and dependencies from the repository. |
| Data and permissions | Existing approved data target and permitted test procedure, identified without passwords or connection strings. Confirm required access from that task's runtime. Do not grant new privileges as part of a check. |
| Baseline result | One small existing check appropriate to that role: Backend service/test startup, Frontend application/template startup, and Test's independent test-command startup. Record the command, exit result, and actual run reference. |
| Receipt | The receiving agent has actually started in the bound workspace and reported the result. A saved configuration, queued run, or acknowledgment is not startup evidence. |

Use the existing approved provisioning mechanism; do not have each engineer independently invent a Python installation or repair the shared virtual environment. Keep non-secret bootstrap instructions and compatibility checks in GitHub. A runtime version change or provisioner metadata migration must be explicit and verified before it becomes the default for subsequent tasks.

If a workspace fails the provisioner's checks, preserve it and its uncommitted work. Operations prepares or selects a verified clean task-specific checkout using existing authority, then rebinds only the affected task and verifies its actual startup. The Director proceeds with unaffected work. Do not repeatedly retry an unchanged failure or treat a model metadata warning alone as a root cause; record the failing command and evidence of its effect.

Check test startup early. Use an existing approved software-test facility and its documented safe command; no new database or service is authorized by this contract. When the existing staging database is an approved test target, use only the allowed synthetic-fixture/transaction procedure that preserves other records. A test command that flushes or recreates that database is not an acceptable substitute. If the required test cannot run safely with existing facilities, report the exact missing capability and one proposed remedy to the Director before running it.

This table is a startup check, not another founder approval. Routine setup and recovery within existing permissions belong to Operations and the Director. A need for new access, a privileged host change, a new service, or expanded scope returns as one specific decision. Do not assume those permissions have been granted by this document.

### 11.3 A handoff ends when the recipient starts

Each implementation-to-test, test-to-review, and review-to-Operations handoff carries a short reusable record:

1. **What:** task, saved contract/API revision, PR or branch, exact candidate commit, and remaining acceptance criteria or findings.
2. **Where:** receiving task's verified workspace and existing test or staging target; reference secure bindings by name only.
3. **How:** the next command or concrete action, required fixtures, and the evidence/output expected.
4. **Who:** one receiving owner and the Director as delivery coordinator.
5. **Receipt:** the actual receiving run started successfully, or one explicit failure with its owner and next action.

Do not close a handoff merely because a comment was posted or a wake was queued. If reassignment cancels a queued run, the Director or VP verifies the final assignee and initiates the appropriate run through the supported controls. If permissions prevent that action, escalate the single routing problem instead of sending the same request through several agents.

The Director maintains one authoritative candidate commit. Backend and Frontend may develop separately, but Test reviews their integrated result. If relevant code changes after verification, identify the changed areas and run the affected tests before the final recommendation; results from an older commit are not evidence for new code. Document whether each earlier review result still applies.

### 11.4 Reusable setup and release record

Before marking this increment complete, retain the verified workspace/bootstrap procedure and handoff template in GitHub, and record the corresponding Paperclip workspace-template/default configuration references. Reuse a working template for subsequent tasks. If a recurring template defect remains, give its repair one owner and a specific issue; apply and verify a durable default fix through the existing permissions instead of relying on undocumented one-off rebindings. A configuration change that requires additional privileges must have its own exact authorization.

Keep the release record short: accepted contract revision, integrated PR/commit, independent H01–H20 results, Director verdict, merge decision and resulting `master` commit, authorized staging update and deployed commit, migration/rollback notes, and founder browser result. GitHub remains the source for rebuilding the application; Paperclip remains the source for task ownership and decisions.

## 12 Definition of done

The increment is complete when the agreed fields and parent relationships are implemented, every delivered screen is navigable, the exact-version and permission rules pass independent software verification, the normal review/merge/staging process is recorded, and Diego can complete the browser walkthrough. Preserve a concise list of remaining research-system capabilities; completion of this increment does not imply full Stage 1, automated research, strategy validation, or Risk acceptance.
