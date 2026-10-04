# RMS Strategy Specification and Test Plan Design Contract

**Version:** 1.0 Final design for implementation handoff  
**Date:** October 3, 2026  
**Prepared for:** Diego Galindo, Director of Engineering, Backend Engineer, Frontend Engineer, and Test Engineer  
**Purpose:** Specify the next bounded RMS increment so an exact Hypothesis can become a precise strategy specification and test plan for its first backtest.  
**Decision status:** Finalized at Diego's request on October 3, 2026, including the approved phase name and unchanged increment scope. This is the canonical successor to the version 0.1 review draft. Section 15 defines the implementation handoff; saving this file does not itself dispatch Paperclip work or authorize research execution, merge, or deployment.

## 1 Implementation summary

Build one coherent **Strategy Specification and Test Plan** feature in the existing RMS. An editor starts from an exact Hypothesis version, defines the strategy rules and experiment, writes precise pseudocode, identifies each required dataset down to its retrieval interface, specifies the evaluation criteria, and saves or revises the plan. A reader can follow the plan back to its Hypothesis, research case, Idea, and Sources.

The package has two conceptual parts: **Strategy specification** explains exactly what the strategy would do; **Test design** explains how those rules will be evaluated. They share the same data specifications, save action, version history, and Hypothesis pin. Retain the roadmap's `TestPlan` and `TestPlanVersion` record names underneath. This naming clarification creates no separate Strategy entity, workflow, or approval step.

The deliverable is an implementation specification that the next engineering stage can use with little research-design clarification. The feature records data-access checks performed in existing tools. It does not execute pasted code, contact data providers, or run backtests.

### Founder decisions incorporated

| Decision | Required treatment |
| --- | --- |
| Name the phase Strategy Specification and Test Plan | Make strategy rules explicit within the same versioned preparation package. Preserve the agreed scope and existing TestPlan record meanings. |
| Simplicity and progress toward a first backtest | One plan editing workflow, existing infrastructure, and a limited set of records and actions. |
| Exclude costs at this stage | No transaction-cost, commission, slippage, spread-cost, borrow-cost, funding-cost, or fee-model fields, calculators, required assumptions, or completeness gates in this increment. |
| Include implementation detail | Precise formulas, rules, pseudocode, parameters, expected outputs, and API-level data specifications belong in the plan. |
| Defer executable strategy code | Strategy implementation, full data preparation, and the first backtest belong to the following increment. Retrieval examples are inert documentation here. |
| Permit incomplete drafts | Save incomplete plans; show exactly what is missing. Draft completeness never means approval or a successful experiment. |
| One baseline plus listed variations | Each plan defines one baseline and an optional finite list of individually named variations. No automatic parameter search. Confirmed in this chat. |
| Record external data checks | Store the outcome and evidence of small checks performed in QuantConnect or another existing tool. Provider connections inside RMS are deferred. Confirmed in this chat. |
| Reuse development staging | Reuse the existing staging application and `rms_staging` database. Disposable RMS test records may be cleared when needed; users, password hashes, memberships, permissions, and login access must survive. |

### Design decisions

The following choices make the agreed scope concrete for implementation:

- Criteria and data specifications are edited inline on the plan but retain their own immutable versions underneath, matching the existing roadmap.
- Completeness, upstream changes, and reported data-access results appear as separate indicators.
- An existing Hypothesis identity cannot be replaced by a different Hypothesis when revising a plan. Selecting another version of the same Hypothesis requires an explicit reason; another Hypothesis gets a new plan.
- Technical size limits, route names, and field shapes below define the implementation interface. Director may resolve internal naming without a new scope decision, while maintaining one published interface and the behavior specified here.

### Reading guide

Sections 2–6 explain scope, relationships, and the browser experience. Sections 7–11 define fields, completeness, API behavior, and preservation. Sections 12–15 contain an invented example, acceptance cases, delivery responsibilities, and the implementation handoff. Appendix A maps the design to its sources; Appendix B is the later backtest coding handoff checklist.

## 2 Governing sources and explicit amendments

This contract consolidates the following sources. They supply the baseline; the founder's later decisions above narrow this particular increment.

| Source | Relevant content |
| --- | --- |
| [MAU-25 revision 3](https://paperclip-6vpg.srv1986614.hstgr.cloud/MAU/issues/MAU-25), document revision `6d1abb4f-4e3c-4bbf-8e1a-8c37dd0b3f2d` | TestPlan, CriterionProfile, DataRequirement, immutable version associations, research roles, and missing-content rules; sections 6–8 and 14.1–14.2. |
| [MAU-140 next increment proposal](https://paperclip-6vpg.srv1986614.hstgr.cloud/MAU/issues/MAU-140#document-next-increment-proposal), revision 1 | Draft plan creation, exact Hypothesis pin, revision/history, separate benchmark, missing items, and definition-only scope. Read in Paperclip during preparation of this contract. |
| [Hypothesis design contract version 1.0](RMS_HYPOTHESIS_DESIGN_CONTRACT_V1_0.md) | Existing research fields, context relationships, intended versus evaluation benchmark, immutable history, page/API parity, permissions, and safe input preservation. |
| [Founder research brief](CEO_RESEARCH_FIRM_BRIEF.md), sections 4 and 9 | Planning precedes data qualification, implementation, backtesting, and later validation; use QuantConnect/LEAN; Paperclip owns company authority. |
| [Founder RMS direction](CEO_RMS_DIRECTION_FINAL_V1_0.md), sections 2–4 | Django/DRF/PostgreSQL, Django templates, shared services, existing hosting, and deferred external connectors. |
| Founder decisions in this chat on October 3, 2026 | Phase naming, cost exclusion, pseudocode and API detail, incomplete drafts, baseline plus listed variations, external check recording, and development-data policy. |

### Resolution of differences

1. **Costs:** The earlier MAU-25 dictionary and MAU-140 proposal include cost assumptions. That requirement is explicitly deferred for this increment. Do not retain a hidden mandatory cost field or default it to zero to satisfy an old schema. Existing Hypothesis text remains unchanged. A gross-return or other preliminary test must accurately state what part of its pinned claim it evaluates; it cannot establish an untested net-return claim.
2. **Data depth:** Replace the proposal's general unresolved-data-needs text with the detailed versioned DataRequirement specification in section 8. Unknown items remain visible while drafting.
3. **Code depth:** Add precise pseudocode and retrieval instructions. No runnable strategy generator, code execution, provider connector, or backtest button is included.
4. **Check evidence:** The old proposal excludes data samples. Retain that boundary: store field schemas, invented response examples, and sanitized evidence references. Do not upload real market-data samples, reserved data, or credentials through this feature.
5. **Drafts:** The roadmap's required research content is required for a complete definition, not for the initial draft save. Formal research recommendation, approval, execution eligibility, and result decisions remain later workflows.
6. **Development data:** The later founder policy permits scoped clearing of disposable RMS staging records. It does not permit rewriting saved version history through ordinary product actions, altering authentication data, or clearing Paperclip or Git history.
7. **Phase naming:** Strategy specification and test design are two parts of the same TestPlan package. The new phase name clarifies the existing rules/pseudocode content; it adds no separate Strategy record or executable strategy scope.

Preserve the original source documents. Record this finalized scope as an additive successor decision in the implementation handoff. Acceptance of this bounded design does not declare the broader Stage 1 roadmap or independent research assurance complete.

## 3 Product outcome and boundaries

### Included

- Create a plan from a visible exact Hypothesis version, including an incomplete Hypothesis draft.
- Save, reopen, list, inspect, revise, and view exact plan versions and history.
- Define one baseline, finite optional variations, an experiment-count limit, and stopping rules.
- Record formulas, timing, sizing, pseudocode, data requirements, benchmark, and evaluation criteria.
- Add attributable external data-check reports bound to the exact plan, data requirement, and configuration checked.
- Show completeness, unresolved data issues, upstream review notices, and the exact source of inherited research context.
- Navigate from Home, Hypothesis, and research case to plans, and back through existing lineage.
- Provide authenticated API operations with the same services and rules as the browser.
- Demonstrate the complete software workflow with clearly invented records on the existing staging stack after its release decision.

### Deferred

Executable strategy/backtest code; live provider access from RMS; bulk acquisition or storage of market data; dataset qualification and RightsDecision workflows; cloud project/compile/run automation; experiment dispatch or result ingestion; automatic parameter search; research recommendation/approval transitions; protected final-validation data; trading; and a reusable global criterion/data catalog.

There is no new database, service, queue, SPA, editor runtime, credential store, or approval dashboard in this design. Use the existing application and working procedures.

### Place in the research process

**Source → Idea → Hypothesis → Strategy specification and Test Plan → Code → Backtest → Evaluate results → later robustness and independent validation.**

The Hypothesis states the claim and why it may hold. The strategy specification translates that claim into exact rules, formulas, parameters, timing, and pseudocode. The test design specifies the data, comparison, periods, variations, and criteria used to examine it. Code implements those definitions; a backtest executes the implementation; evaluation interprets the results against the predeclared criteria.

This increment supplies the last major specification package before implementation. Small data-access checks may establish feasibility during preparation, using existing tools and applicable authority. A sample check is neither full data qualification nor a strategy experiment. The following increment implements the plan in QuantConnect/LEAN and links its actual code and results.

## 4 Record meanings and relationships

| Record | Meaning and relationship |
| --- | --- |
| Source and Idea | Existing evidence and the originating research idea; reached through the exact Hypothesis lineage. No new editable copies. |
| Research family | Existing grouping of related mechanisms. Inherited through the pinned Hypothesis context. |
| Research case | Existing `Investigation`; organizes related Hypotheses and their plans. No independent editable case selector on a plan. |
| Hypothesis version | The exact claim being evaluated. Every plan version has exactly one immutable Hypothesis-version binding. |
| TestPlan | Stable identity for one combined strategy specification and experiment definition. One Hypothesis may have several plans. |
| TestPlanVersion | One immutable complete snapshot of both parts, including strategy rules, parameters, variation definitions, and exact criterion/data associations. |
| Strategy specification | A visible section within TestPlanVersion containing the implementable rules and pseudocode. It has no separate entity, independent save, or version lifecycle in this increment. |
| CriterionProfile version | One operational evaluation rule. Edited inline within this increment; separate version identity preserves what was specified. |
| DataRequirement version | One logical input and its acquisition/use specification, including the selected primary source. Edited inline within the plan. |
| DataAccessCheck | Append-only report of an externally performed check against exact versions and one named configuration. It is evidence of the stated check only. |

Logical relationship outline:

```text
Research family
  Research case
    Hypothesis
      Hypothesis version ── exact originating Idea and Source versions
        Strategy Specification and Test Plan version
          Strategy rules, formulas, timing, sizing, and pseudocode
          Test design, evaluation benchmark, and interpretation rules
          HypothesisPlan association ── exact Hypothesis version
          PlanCriterion associations ── exact CriterionProfile versions
          PlanDataRequirement associations ── exact DataRequirement versions
          One baseline and zero or more listed variations
          External data-check reports ── exact requirement and configuration
```

Use the existing baseline association meanings `HypothesisPlan`, `PlanCriterion`, and `PlanDataRequirement`. Reuse equivalent existing primitives rather than creating duplicate tables. Each association is an immutable, attributable row with exact endpoint versions and deterministic ordering where relevant.

Criteria and requirements are owned by one plan identity in this increment. There is no cross-plan editing or global reuse interface. Unchanged child versions may be reused by later versions of the same plan; changing a child creates its successor. Removing a child from a new plan version leaves all older versions and associations intact.

## 5 Version behavior and upstream changes

- The stable plan ID is `TPL-{uuid}`; its version ID is `TPLV-{uuid}`. Use `CRT-`/`CRTV-`, `DREQ-`/`DREQV-`, and `DCHK-` for the new logical record identities, subject to the single published interface's existing conventions.
- Status remains `draft`. A valid substantive save creates an immutable sequential version. A title-only initial draft is permitted with a valid authorized Hypothesis pin.
- Every revision supplies the expected latest plan version and a nonblank reason. The transaction creates all changed children, associations, and the plan version atomically.
- Identical content under a new request key returns a no-change result. It does not create a new plan version or duplicate child versions.
- A new Hypothesis version never silently changes a saved plan. Current screens show the original pin and an upstream notice. Exact-version content remains unchanged.
- An editor may explicitly select a newer version of the same Hypothesis and revise the plan with a reason. The server verifies the target and records the changed binding. A different Hypothesis identity requires a new plan.
- Existing Idea, Source, case, and family corrections remain visible through the established upstream-impact mechanism. Reading history must not substitute their latest records for pinned versions.
- Version-owned content and association sets are sealed when saved. Late association insertion, deletion, or replacement must not change the apparent content of a historical version.
- A data-check report does not rewrite a plan or silently make it complete. A correction is a new report that identifies the superseded report and preserves its contents.
- Check evidence from an earlier plan version may be shown as historical evidence. It is never silently relabeled as a successful check of the current version, even when a particular data requirement was reused.

No in-place update/delete operations for historical content are exposed through the application. A permitted staging reset is an operator development procedure, outside the plan UI/API.

## 6 Browser experience

### Navigation

Use **Strategy Specification and Test Plan** as the phase and page heading. Keep **Test Plans** as the compact persistent navigation label, Home count label, and list name. A plan list has title, current version, linked Hypothesis, case, completeness, upstream notice, and last saved time. Use permission-scoped counts and deterministic pagination: 25 by default, maximum 100; newest creation first with stable-ID tie-breaker.

Hypothesis detail and exact-version screens show related plans and **Create Test Plan from this version** for an editor. Research case detail links to its plans through their pinned Hypotheses. An exact Hypothesis-version view distinguishes plans pinned to that version from plans associated with other versions of the same Hypothesis. Users can reach every delivered screen by clicking links.

### Single editing workflow

Use one form with these sections, ordinary Django templates, and modest JavaScript for repeatable items:

1. **Purpose and Hypothesis** — exact pin, inherited claim/context, title, objective, scope limitations.
2. **Strategy specification** — exact rules, formulas, timing, sizing, parameters, pseudocode, and expected outputs.
3. **Data** — repeatable named inputs with acquisition specifications; links to recorded checks.
4. **Test design** — periods, baseline, optional variations, benchmark, trial limit, stopping rule.
5. **Evaluation** — inline criteria and overall interpretation rules.
6. **Review** — missing items, unresolved checks, upstream changes, reason for revision, Save draft.

Do not build a visual programming editor, separate data-catalog application, or multi-screen approval wizard. Render pseudocode and retrieval snippets as escaped monospaced text. Do not execute, lint against a live service, or render user-supplied HTML.

### Interaction requirements

- Creation shows the selected Hypothesis version before the user saves. Read-only inherited fields never become a second editable copy of the claim.
- Every save is explicit. No silent server-side autosave or automatic version creation while typing.
- An incomplete save succeeds if its supplied content is structurally valid. Show **Draft saved** and the missing items.
- Inline validation identifies the section and item. Retain all submitted text, lists, ordering, and references when a save fails.
- A hidden/missing reference may still return the established uniform 404, but must retain the editor's own escaped unsaved input without revealing referenced content or implying success.
- A confirmed stale-version 409 preserves the proposal, identifies the conflict safely, and offers an explicit comparison/reload-and-reapply path. Never overwrite the other editor's revision.
- Unknown save outcome retains the original idempotency key and exact payload for a safe retry. After a confirmed rejection and explicit changed submission, create a new key while retaining the user's content.
- Warn on navigation away from unsaved changes. Reuse the existing scoped draft helper where suitable; do not introduce a new persistent browser store of credentials or check evidence.
- Current detail, version detail, and history distinguish **Draft incomplete**, **Draft complete**, **Upstream review needed**, and **Data check not recorded/issues reported**. None is labeled approved, validated, qualified, or ready to trade.
- Viewer screens show the same authorized definitions and history with write controls absent. Keep existing viewer/editor policy; no new role-management UI.

## 7 Plan and criterion field dictionary

### 7.1 Shared representation rules

**Required to save:** an authorized exact Hypothesis pin and a nonblank title. Revisions additionally require the expected latest version and correction reason. All other definition content may be missing in a draft. A supplied value must have the correct type and satisfy structural validation even when the draft is incomplete.

**Required for completeness:** the items marked C below. Conditional items are required only under their stated condition. Shape validation can verify fields, enums, dates, types, and cross-references; it cannot certify the scientific adequacy of prose or pseudocode.

Use UTF-8 plain text, UTC audit timestamps, ISO dates, IANA time-zone names, booleans, integers, and finite decimal strings. No NaN, infinity, expression evaluation, or implicit numeric conversion. Whitespace-only optional text becomes null. Creation may omit nullable content; read responses return explicit nulls and empty collections. Revisions send the complete proposed snapshot, with explicit nulls and empty lists to clear content. Reject unknown fields and duplicate JSON keys through the shared request validator.

Technical limits: 500 characters for titles/names, 4,000 for normal explanatory fields, 20,000 for pseudocode or retrieval instructions, 2,000 for URLs, 20 criteria, 20 data requirements, 50 parameters, 20 variations, and a 512 KiB request body. These are application resource limits, not recommended experiment sizes. Oversize submissions return safe field errors without truncating or partially saving content.

Server-owned metadata includes stable/version IDs, version number, schema version, actor, recorded time, classification, accepted software-scope reference, digests, and correction lineage. This increment uses the existing enforced `synthetic` classification under the accepted software scope. Clients cannot assert research approval, change classification, set authorship, or supply a trusted digest.

### 7.2 Purpose and strategy specification

| Field | Type | Meaning and completeness rule |
| --- | --- | --- |
| `title` | Text 1–500 | Required to save. Human name for this experiment definition. |
| `objective` | Text | C. What this particular test will establish or falsify about the pinned Hypothesis. |
| `scope_limitations` | Text | C. What the first test will not establish and any approximation to the full claim. Explicitly record when no additional limitation is identified. |
| `measurement_basis` | Enum | C. `gross_return` or `other_measure`. No net-performance claim is established by this preliminary scope. |
| `measure_definition` | Text | C. Exact output being measured, units, aggregation, and relevant comparison. |
| `universe_definition` | Text | C. Precise eligible instruments and membership rule for this test, consistent with the pinned Hypothesis. |
| `hypothesis_alignment` | Text | C. Explain how implementation choices test the pinned claim. A material claim change requires a Hypothesis revision, not an unexplained override. |
| `signal_definition` | Text | C. Formula/event, input aliases, lookback, units, and signal boundaries. References named parameters and data requirements. |
| `entry_rules` | Text | C. Trigger, eligibility, current-position constraints, equality boundaries, repeated signals, and re-entry. |
| `exit_rules` | Text | C. Exit conditions, precedence, holding-period counting, and treatment of simultaneous triggers. |
| `position_rules` | Text | C. Position sizing, denominator/units, rounding, rebalancing, simultaneous positions, and exposure restrictions necessary to reproduce the test. |
| `decision_timing` | Text | C. When the inputs are read and decisions made, including session/calendar and order of operations. |
| `execution_timing` | Text | C. Intended entry/exit observation or bar relative to the decision. Future implementation must not use information unavailable at that decision time. No detailed execution-cost model is required. |
| `time_zone` | IANA zone | C. Time zone used for plan dates and schedules. Data-source time zones are recorded separately. |
| `pseudocode` | Plain code text | C. Ordered, deterministic algorithm covering initialization, data use, signal, entry/exit, position state, and output. No code execution in RMS. |
| `edge_case_policy` | Text | C. Missing/duplicate/stale observations, warmup, simultaneous rules, no eligible instrument, end-of-test open positions, and incomplete calculations. Explicit inapplicability is allowed where explained. |
| `expected_outputs` | Ordered list of text | C, at least one. Named series/tables/metrics to retain for later review, such as signals, positions, trades, comparison returns, and diagnostics. No actual results are recorded here. |
| `implementation_target` | Fixed value | Server-owned `quantconnect_lean`. Reuse the selected stack. Runtime version and cloud/local choice may be noted without pretending they have been provisioned. |
| `implementation_notes` | Text | Optional. Relevant libraries, module outline, or known platform limitations. No credentials. |
| `reviewer_roles` | List of role labels | C, at least one. Intended research/data/implementation reviewers as appropriate. Descriptive responsibility only; this list creates no role or approval right. |

The form displays inherited Hypothesis content beside the test-specific definition. It may offer an explicit **Use this Hypothesis text as a starting point** action; copied text is then plan content and cannot be silently synchronized later. The Hypothesis remains the claim authority; the plan supplies implementation choices and operational evaluation rules.

### 7.3 Test periods and baseline

| Field | Type | Meaning and completeness rule |
| --- | --- | --- |
| `evaluation_design` | Enum | C. `development_only` or `development_and_initial_evaluation`. The latter is an ordinary development comparison, not protected final validation. |
| `development_start`, `development_end` | Date | C. Inclusive intended decision-date range; end must be on or after start. Retrieval endpoint inclusivity must be specified separately. |
| `initial_evaluation_start`, `initial_evaluation_end` | Date | C only for the second design. Both required together; start must be after development end. Otherwise both null. |
| `split_policy` | Text | C. How the named periods are used and what adaptation, if any, is allowed before initial evaluation. For development-only, say that no separate evaluation period is claimed. |
| `reserve_boundary` | Text | C. Describe the conceptual boundary to later independent validation without reserved dates, identities, rows, or results. A statement that no protected final test is included is valid. |
| `sample_rule` | Text | C. Which observations/trades count, exclusion rules, independence limitations, and how insufficient evidence is identified. |
| `warmup_rule` | Text | C. Required pre-period history and when evaluation can begin. Explicitly state if none is needed. |
| `parameters` | Ordered list | Each item has unique `name`, `type`, `baseline_value`, `units` where relevant, and `meaning`. See below. Empty list is allowed only with `parameter_policy` explaining that rules contain no variable parameters. |
| `parameter_policy` | Text | C. Which values are fixed and the limits of permitted exploration. |
| `trial_budget` | Positive integer | C. Maximum planned result-producing configurations for this plan. It must cover one baseline plus every listed variation. No default research budget. |
| `related_trial_treatment` | Text | C. Explain that related variations belong to this investigation and how their results will be reported together. No automatic new-cycle credit. |
| `stopping_rule` | Text | C. When to stop, including completion of the listed work and data/implementation problems that require review. No performance-driven extension beyond the stated work. |

Parameter types are `integer`, `decimal`, `boolean`, or `string`. Decimal values use finite decimal strings; others use their matching JSON scalar. Names match `[a-z][a-z0-9_]{0,63}`. Units are required for numerical quantities unless `meaning` explicitly establishes a dimensionless value. Pseudocode must identify how parameters are used; the application does not parse code to prove this.

The baseline is the plan's full definition plus every `baseline_value`. Its configuration key is `baseline`. It is not a duplicate TestPlan record.

### 7.4 Explicit variations

Each optional variation contains:

- `key`: unique parameter-name-style identifier, other than `baseline`.
- `name`: human label, required for completeness.
- `rationale`: why this bounded change is informative, required for completeness.
- `parameter_overrides`: a nonempty map of already declared parameter names to correctly typed values.

A variation inherits the same Hypothesis pin, data specifications, periods, rules, benchmark, and criteria. Its resolved configuration replaces only the named parameter values. No Cartesian product, range expansion, random sweep, or hidden combinations occur. Identical resolved configurations are rejected as duplicates. A different signal rule, universe, data source, period, or criterion requires an explicit plan revision or another plan; it cannot be smuggled into a parameter name or arbitrary executable expression.

The UI shows the baseline values beside every override and the total configuration count. The following increment will handle execution attempts and retries. This increment records the intended experiment limit; it does not implement counters, scheduling, or retry accounting.

### 7.5 Evaluation benchmark

| Field | Type | Meaning and completeness rule |
| --- | --- | --- |
| `benchmark_name` | Text 1–500 | C. Name of the actual comparison for this plan. No application-wide default. |
| `benchmark_definition` | Text | C. Calculation, measurement basis, currency/units, timing, exposure, and rebalancing where relevant. A ticker alone is insufficient. |
| `benchmark_rationale` | Text | C. Why this comparison evaluates the objective. |
| `benchmark_alignment` | Enum | C. `same_as_hypothesis` or `different`. Display the original intended benchmark separately. |
| `benchmark_difference_reason` | Text | C when different; otherwise null. A scientific-claim change requires a Hypothesis revision. |
| `benchmark_input_mode` | Enum | C. `data_requirements` or `defined_without_external_input`. |
| `benchmark_data_keys` | List of requirement keys | At least one existing key for `data_requirements`; otherwise empty. The full computation remains in the benchmark definition. |

These fields fix the proposed evaluation benchmark for this plan version. They do not imply that the plan has received research approval.

### 7.6 Criteria

Each CriterionProfile version carries the following fields. At least one complete mandatory criterion is required for a complete plan.

| Field | Type | Meaning and completeness rule |
| --- | --- | --- |
| `name` | Text 1–500 | C. Human-readable evaluation rule. |
| `metric` | Text | C. Precisely defined output, computation, and aggregation. |
| `units` | Text | C for a numerical rule; specify ratio/dimensionless explicitly where appropriate. |
| `rule_type` | Enum | C. `numeric` or `objective_rule`. |
| `operator` | Enum | Numeric only: `gt`, `gte`, `lt`, `lte`, `eq`, or `between_inclusive`. |
| `threshold`, `upper_threshold` | Decimal string | Numeric threshold required; upper required only for between, with lower ≤ upper. Irrelevant fields must be null. |
| `objective_rule` | Text | Required for objective-rule type; numeric fields null. Must describe an observable decision rule rather than an aspiration. |
| `sample_requirement` | Text | C. Minimum usable evidence and treatment of insufficient or invalid samples. Human supplied. |
| `evaluator_role` | Text | C. Intended evaluator; not an access grant. |
| `mandatory` | Boolean | C. Whether this rule is necessary for the proposed continuation decision. No implicit true/false. |
| `applies_to` | Enum | C. `baseline` or `all_configurations`. No selective choice after results. |

The plan also contains C fields `overall_interpretation` and `inconclusive_rule`: how the criteria combine, what a mandatory failure means, and what makes evidence inconclusive. A recommended convention is that all mandatory criteria must pass, a valid mandatory failure does not qualify for continuation, and missing/invalid evidence remains inconclusive. Researchers specify the actual rules; RMS stores them without evaluating results in this increment.

Optional criteria must also be fully specified if retained in a complete plan. Do not generate default Sharpe, return, drawdown, significance, or sample thresholds. Do not label a successful software test or a passing data-access check as a research criterion result.

## 8 Data specification and external check evidence

### 8.1 One named specification per logical input

Each DataRequirement has a unique `key` within the plan. Pseudocode and benchmark definitions refer to these keys. One requirement selects one primary dataset/source; an alternative provider needs an explicit revision. A source accessed through several required API calls may document those ordered calls within the same retrieval instructions. Do not fail over silently to a different provider or dataset.

The following fields define what “API-level detail” means. All are required for completeness unless conditional or optional is stated. Applicability is recorded explicitly; an unexplained blank or generic “N/A” does not satisfy a required explanation.

| Field or group | Required definition |
| --- | --- |
| `key`, `name`, `purpose` | Stable local key, readable input name, and exact signal/rule/benchmark use. |
| `used_by_configurations` | Nonempty list drawn from `baseline` and the listed variation keys. |
| `provider`, `dataset_name` | Actual provider and named data product; “market data” or “QuantConnect” alone is insufficient as a human review standard. |
| `documentation_url`, `documentation_checked_at` | HTTPS documentation reference and time when the author checked it. This is an authored statement, not an automatic fetch. |
| `provider_version_policy` | Dataset/API version or source-release identifier where available; otherwise explicitly document that the source is unversioned and the replay limitation. |
| `access_method` | `lean_sdk`, `rest_api`, or `existing_file`. No credentials are stored for any method. |
| `execution_location` | `quantconnect_cloud`, `existing_local_lean`, or `other_existing_tool`; the last needs a descriptive tool name. This is intended use, not proof of access. |
| `symbols_and_mapping` | Provider identifiers, market/venue, stable identity mapping, and symbol-change treatment. |
| `historical_universe_rule` | How eligible membership is determined at each historical date; explicitly identify a fixed universe if that is the design. |
| `coverage_start`, `coverage_end` | Required date range, including necessary warmup. Both required for completeness and ordered. Distinguish requested coverage from coverage actually checked. |
| `resolution`, `session_rule`, `source_time_zone` | Bar/event granularity, calendar/trading session, and timestamp zone. |
| `field_schema` | Nonempty ordered list of field name, data type, units/meaning, nullable flag, and use. Include identifiers and timestamps, not only signal fields. |
| `availability_rule` | Observation/event timestamp, when the information became available to a historical decision, publication delay, and the rule preventing later information from entering an earlier decision. |
| `revision_rule` | How revised historical values are treated and any point-in-time limitation. |
| `normalization_rule` | Price/value adjustment convention, including corporate actions, delistings, currency conversion, or contract mapping when relevant; otherwise explain inapplicability. |
| `transformations_and_joins` | Ordered conversions, resampling, formulas, join keys, timing alignment, and lag/warmup treatment. “Use as returned” is valid if explicit. |
| `quality_rules` | Checkable expectations for coverage, nulls, duplicates, ordering, stale observations, and invalid values; what to do on failure. Use only requirements relevant to this input. |
| `retrieval_instructions` | Exact ordered calls or file-read steps, with parameter values or explicit references to named plan parameters. Include inclusivity, pagination/limits where applicable, and expected output. |
| `response_example` | An invented, labeled response or schema example showing shape and units. No real or protected data sample. |
| `access_requirements` | Account entitlement or existing access needed, intended-use restrictions known to the author, and cloud/local distinctions. Unknowns stay explicit. No purchase flow or rights approval is implemented. |
| `credential_requirement` | `none`, `platform_managed`, or `existing_alias`. Only the last accepts a non-secret alias/reference. No token, password, connection string, signed URL, or private key. |
| `known_limitations` | Explicit limitations; if none have been identified, state the scope of that conclusion. |

Conditional method fields:

- **LEAN SDK:** `sdk_namespace`, `subscription_call`, `history_or_data_call`, and relevant configuration arguments. Name the dataset as well as the SDK method. Code snippets are displayed only.
- **REST API:** `base_url`, `http_method` limited here to retrieval `GET`/`POST`, `endpoint_path`, non-secret path/query/body/header parameter definitions, response selector, pagination rule, and documented request limits or explicit unknowns. Authentication header values never appear in this record.
- **Existing file:** non-secret approved logical location/reference, format, schema, partition/naming pattern, parser instructions, and available release/checksum identifier or an explicit limitation. Do not store workstation secrets or require a new file-upload feature.

An SDK source is not required to invent a REST endpoint. QuantConnect documents equity subscriptions through `add_equity` and data retrieval through `history`; the actual plan supplies the selected dataset, symbols, dates, resolution, normalization, and timestamp semantics. See [official US equity retrieval documentation](https://www.quantconnect.com/docs/v2/research-environment/datasets/us-equity) and [history-response documentation](https://www.quantconnect.com/docs/v2/writing-algorithms/historical-data/history-responses). These references explain interface options; they do not prove account entitlement or a particular dataset's adequacy.

### 8.2 External data check record

The action is labeled **Record external data check**. It records what someone already did in an existing tool. No Run, Connect, Fetch, Verify provider, or Test credentials button is added to RMS.

| Field | Requirement |
| --- | --- |
| `plan_version_id`, `data_requirement_version_id` | Exact authorized versions. The requirement must belong to that plan version. |
| `configuration_key` | Exactly one baseline/variation key from that plan version. The server binds its resolved configuration digest. A baseline-only check does not claim coverage of variants. |
| `performed_at`, `performed_by`, `tool` | Actual reported time, human/agent/tool identity, and environment. Server separately records who entered the report and when. |
| `outcome` | `passed`, `failed`, or `inconclusive`. No default. “Not checked” means there is no current applicable report. |
| `check_scope` | Actual symbols/dates, fields, API call or file operation, observed row count where relevant, and what was examined. Do not imply complete historical coverage from a small sample. |
| `observations` | Sanitized observed facts and failure details. No credentials, raw response bodies with real data, or unsupported success claims. |
| `evidence_references` | At least one non-secret reference to the notebook, log, source commit, or existing evidence artifact, with an exact revision/hash where available. No server-side dereference. |
| `limitations` | What the check did not establish; always nonblank. |
| `supersedes_check_id`, `correction_reason` | Both required only when correcting a report. Same plan/requirement/configuration binding; the previous report remains visible. |

The reporter explicitly confirms that the evidence contains no credentials or restricted/real data sample. Automated secret-pattern rejection may catch obvious mistakes, but must not be represented as complete data-loss prevention. Evidence links and text receive the existing authorization and safe-rendering controls.

Checks form a visible chronological history per exact plan/requirement/configuration. There is one current report per such binding; recording another explicitly supersedes the observed current report. Use expected-current-report validation to prevent concurrent corrections silently winning. A newly added check has the same request-idempotency guarantees as other writes.

The current plan summary distinguishes **Not checked**, **Partially checked**, **Checks reported passed**, and **Issues reported**. Derive these from required requirement/configuration pairs and their current reports. Any failed or inconclusive current report yields Issues reported; all required pairs with passed reports yields Checks reported passed. These labels describe submitted evidence, not an independent certification or execution approval.

### 8.3 Completeness versus data feasibility

A definition may be **Draft complete** while its data checks are **Not checked**. Structural completeness requires a precise acquisition specification; it does not fabricate proof that the source is accessible. An unresolved API version, entitlement, or coverage issue must remain visible in the specification/check summary and in the next-stage handoff.

Before implementing an actual research backtest, Data and Engineering should resolve material access and feasibility issues against the specific plan. That future readiness judgment is not an automatic state transition introduced here. The software increment's acceptance uses invented records and does not require purchasing a dataset or executing a real provider call.

## 9 Validation and completeness contract

### 9.1 Validation on every write

Apply existing authentication and active viewer/editor predicates before lookups, counts, parsing that could reveal data, or mutation. Shared services then validate:

1. Exact reference existence, access, synthetic classification, matching record types, and plan ownership.
2. Valid JSON shape, enums, sizes, dates, finite numeric values, URLs, and conditional field combinations.
3. Unique parameter names, variation keys, data keys, and child identities within the snapshot.
4. Variant overrides refer only to declared parameters and match their types; resolved duplicates are rejected.
5. Referenced data keys and configuration keys exist. A retained requirement must have a valid applicable configuration selection when one is supplied.
6. Ordered date pairs are internally valid when supplied; complete plans additionally require the mandatory period fields. Missing endpoints make a draft incomplete rather than being guessed.
7. If a trial budget is supplied, it is positive and at least the declared configuration count.
8. Numeric criterion combinations are coherent; objective-rule and numeric-only fields cannot conflict.
9. Child IDs and exact input child-version IDs belong to the expected preceding plan snapshot. No adopting another plan's child through a guessed ID.
10. Report corrections bind the same exact plan, requirement, and configuration, and name the expected current report.

No partial record or association is saved on failure. An error never creates a success receipt. Unknown or unsupported state/classification fields are rejected; they are not quietly ignored.

### 9.2 Completeness output

Use the established shape:

```json
{
  "schema_version": "1.0",
  "draft_completeness": "incomplete",
  "missing_fields": [
    {"path": "/fields/pseudocode", "code": "required_for_completeness", "message": "Describe the ordered algorithm."},
    {"path": "/data_requirements/0/fields/availability_rule", "code": "required_for_completeness", "message": "Describe when this input becomes available."}
  ]
}
```

The exact enum spelling must match the new published schema and existing client conventions. Every path is an RFC 6901 JSON Pointer into the full submitted/read snapshot. Order missing items by form section, then item order. API and page use the same calculation; no frontend-only checklist can declare completion.

Completeness requires:

- Every C plan field and applicable conditional field in section 7.
- At least one complete mandatory criterion; every retained criterion has its C fields.
- At least one complete DataRequirement and all required data references resolved within the definition.
- A fully described baseline, valid listed variations if present, and sufficient declared trial budget.
- Appropriate period/split, benchmark, sample, stopping, and interpretation definitions.

An incomplete pinned Hypothesis and any upstream notices are reported separately. Do not require legacy Hypothesis cost-related completeness solely to save or complete this narrowed plan definition. Show the actual inherited Hypothesis completeness unchanged, and leave substantive alignment to explicit review.

Pseudocode prose is not mechanically certified as executable or unbiased. “Draft complete” means the definition has all required content in valid form. It does not mean data qualified, reviewers accepted, backtest run, research approved, or criteria passed.

### 9.3 Content digests

Reuse the existing canonical JSON and SHA-256 utilities, with a documented schema version. The plan `config_digest` covers the exact Hypothesis binding, all substantive plan fields, ordered criterion/data child versions and their content digests, and the sealed association set. Exclude server save timestamps, derived links, live upstream notices, and later check reports from this definition digest.

Each resolved baseline/variation has its own digest covering that definition plus the selected resolved parameter map and configuration key. A DataAccessCheck stores the server-derived configuration and requirement digests at its exact binding. Digests detect changes and support later handoff; they are not approval tokens or proof of independent custody.

## 10 Backend and API contract

### 10.1 Shared implementation

Implement validation, completeness, read/list/history, create/correct, and external-check recording in shared services. Browser views and DRF adapters call those services with the authenticated actor. They must not reproduce independent business logic or call a database-free validator as if it persisted or authorized records.

Publish one machine-readable schema in the repository at `rms/test_plan_schema.json`, and one interface note `docs/RMS-TP-API-1.md`. Include all field types, conditional shapes, enum values, null behavior, errors, endpoint bindings, and concrete valid/invalid fixtures. Backend publishes one immutable candidate commit and schema hash; Frontend and Test consume that exact interface. A changed interface gets a successor version and concrete change notes, not a demand to preserve the old output hash.

Logical service capabilities:

- `create_test_plan`, `correct_test_plan`.
- `list_test_plans`, `read_test_plan`, `read_test_plan_version`, `read_test_plan_history`.
- `read_criterion_version`, `read_data_requirement_version`.
- `record_data_access_check`, `list_data_access_checks`, `read_data_access_check`.
- Database-free request validation and completeness helpers for focused source checks.

Director may adapt internal function naming to the codebase. There must be one implemented interface shared by all consumers.

### 10.2 Proposed HTTP operations

| Method and route | Behavior |
| --- | --- |
| `POST /api/v1/test-plans` | Create a draft and its exact Hypothesis association. |
| `GET /api/v1/test-plans` | Permission-scoped list; page/page_size and optional exact hypothesis ID, hypothesis-version ID, or case ID filters. |
| `GET /api/v1/test-plans/{plan_id}` | Current definition and separately labeled current indicators. |
| `GET /api/v1/test-plans/{plan_id}/versions` | Ordered history with exact-version links, reasons, and changed paths. |
| `GET /api/v1/test-plans/{plan_id}/versions/{version_id}` | Exact immutable content; verifies version belongs to the named plan. |
| `POST /api/v1/test-plans/{plan_id}/corrections` | Full proposed successor snapshot with expected latest version and reason. |
| `GET /api/v1/criterion-profiles/versions/{version_id}` | Exact child definition with owning-plan lineage; no independent mutation endpoint. |
| `GET /api/v1/data-requirements/versions/{version_id}` | Exact child definition with owning-plan lineage; no independent mutation endpoint. |
| `POST /api/v1/test-plans/{plan_id}/data-checks` | Record an external check or an explicit superseding report. |
| `GET /api/v1/test-plans/{plan_id}/data-checks` | Bounded history; exact version/requirement/configuration filters. |
| `GET /api/v1/test-plans/{plan_id}/data-checks/{check_id}` | Exact attributable report, including supersession links. |

Use existing trailing-slash and route-name conventions consistently. Do not add PATCH/PUT/DELETE for immutable versions. List queries reject malformed integers, unsupported parameters, duplicate query keys, and inconsistent filter combinations with the established safe 400 response.

### 10.3 Payload envelopes

Creation envelope:

```json
{
  "hypothesis_version_id": "HYPV-00000000-0000-4000-8000-000000000001",
  "fields": {"title": "Invented first backtest plan"},
  "criteria": [],
  "data_requirements": []
}
```

This is a **shape example with an invented ID**. A real write must reference an existing authorized version. Missing content saves as a draft; it does not receive fabricated defaults.

All plan fields in section 7, including `parameters` and `variations`, are under `fields`. Criteria and data requirements are top-level ordered arrays. Each child item has `{criterion_id, criterion_version_id, fields}` or `{data_requirement_id, data_requirement_version_id, fields}`. New children use null IDs; existing children name the exact preceding-snapshot versions. Persist new IDs only on success. The service reuses unchanged child versions and appends successors for changed content. Association `required` metadata derives from criterion `mandatory` or from an included requirement's configuration applicability; it is not a separately editable conflicting answer.

Correction adds `expected_latest_version` and `correction_reason`, restates the exact Hypothesis binding, and supplies the entire fields/criteria/requirements snapshot. Empty lists deliberately remove items from the new version only. The server returns safe changed paths and successor identities.

Read responses include `plan_id`, `plan_version_id`, `version`, `schema_version`, `status`, `classification`, `fields`, exact child and association identities, `hypothesis`, inherited `research_context`, creation metadata, `config_digest`, per-configuration digests, completeness, upstream notices, check summary, and navigation links. Historical content is immutable; separately labeled current notices/check summaries are derived read context with an `as_of` time and are excluded from historical content digests.

Data-check requests follow section 8.2 and include `expected_current_check_id` (null for the first report). Evidence references are `{label, uri, revision, sha256}`; missing revision/hash may be null when the report explains the limitation. Validate supplied SHA-256 values as 64 hexadecimal characters. No attachments or automatic URL fetch occur.

### 10.4 Errors retries and authorization

- 201 for a new plan/version/check; 200 for reads and true no-change responses. Existing-key replay retains the original response status/body and IDs.
- 400 for validation/shape failures; established 401/403 authentication/role behavior; uniform 404 for hidden/missing references; 409 for stale version/report or incompatible key reuse.
- Use the established safe error envelope with request ID, stable error code, and field paths. Do not echo secrets, referenced titles, or request bodies into logs.
- Accept `application/json` with charset parameters. Malformed JSON has a consistent response.
- Idempotency binds authenticated actor, operation/route, key, and canonical payload. Same key and same payload cannot add another record; same key with changed payload must conflict.
- Concurrent revisions serialize against the expected plan head. One wins; the other sees 409 with zero partial child/association writes. Equivalent safeguards apply to report supersession.
- On retries, current authorization is rechecked before returning saved content. Never replay an old response to a now-unauthorized actor.
- Enforce the existing active `editor` write and `editor`/`founder_viewer` read policy. No implicit staff/superuser role bypass in the product. Checks occur before record/count retrieval.
- Keep existing browser session/CSRF handling, including a fresh editor session, login challenges, and safe private-origin behavior.

## 11 Persistence deployment and test environment

Use additive migrations in the existing PostgreSQL database. Reuse immutable-record protections and association commitments from the delivered source where suitable. The new tables must protect version content and sealed link sets from ordinary application DML, including late INSERTs that would alter history. Server-generated current-head pointers and report supersession bookkeeping may change through their validated transactional services.

Do not assert administrator-proof immutability from checksums, application validation, or tests under a database administrator. Tests must name their actual execution role and the property they establish. Existing privilege and broader assurance limitations remain visible without turning this small software delivery into the unfinished institutional-validation project.

Use `mv-rms-staging` and `mv-rms-staging-db-1` with SQL database `rms_staging`. Do not create another database per test or silently use `rms_synthetic`. Extend the existing reusable staging procedure only for the new disposable RMS tables/fixtures. Avoid generic flush, auth deletion, or whole-database drop/recreate. Preserve users, password hashes, group memberships, permissions, login access, Paperclip data, source history, and review evidence.

Fixtures are unmistakably invented and repeatable without duplicate identities. Any explicit reset is confined to disposable RMS development records under the accepted procedure. Product history tests must prove ordinary UI/API changes preserve prior versions; a separate reset procedure is not an excuse to overwrite versions in normal operations.

The build needs no provider credentials or actual market-data account. Existing tools may supply a sanitized external check record later under their applicable authority. The first browser demo uses invented evidence and must label it as such.

Delivery identifies the candidate commit, tests run, deployed build, and database migration level. Merge and staging update remain distinct recorded actions. Successful source checks do not establish database/browser behavior, and a deployment does not itself establish independent acceptance.

## 12 Invented worked example

**All instruments, provider names, thresholds, dates, and check outcomes in this section are invented software fixtures. They are not research recommendations, actual data availability, or an executed backtest.**

### 12.1 Context and objective

An existing fictional family is **Persistent price response**. Its case is **ALFA daily trend investigation**. Hypothesis v1 proposes that fictional instrument ALFA's recent price direction predicts subsequent gross returns under its stated rules. The plan pins that exact Hypothesis v1 and inherits its exact Idea/Source/case lineage.

Plan title: **ALFA baseline trend test**. Objective: examine the defined gross trade return for one fixed signal and a bounded lookback variation. Measurement basis: gross return. Limitation: a first development experiment on fictional data, with no qualification or independent final-validation claim.

Evaluation design: development-only, January 1, 2016 through December 31, 2020, interpreted in America/New_York. Reserve boundary: no protected final-validation data is identified or used. Warmup: the longest permitted lookback of completed trading sessions before the first decision. All dates are fixture inputs, not asserted dataset coverage.

### 12.2 Baseline and variation

| Parameter | Type and units | Baseline | Named variation |
| --- | --- | --- | --- |
| `lookback_sessions` | Integer, completed trading sessions | 20 | `longer_lookback`: 40 |
| `holding_sessions` | Integer, sessions including entry session | 5 | Inherits 5 |

Rules: after an eligible session closes, compare its close with the arithmetic mean of the latest `lookback_sessions` completed closes, including that session. If flat, no entry is pending, and close is strictly greater than the mean, schedule a one-unit entry at the next available regular-session open. Keep at most one position. Exit at the open after five held sessions have completed, with the entry session counted as session one. No entry occurs at the same instant as an exit. Re-entry can be considered at that day's close.

Position rule: one unit of ALFA; no portfolio compounding claim. Missing required bars skip a decision and record a diagnostic; missing next-open observations defer the pending action to the next valid open and record the delay. The design records this as a limitation. Determine the final entry cutoff from the declared session calendar and holding rule, without inspecting future prices or future missing bars. Cancel a deferred entry if it would pass that cutoff. If a held position cannot exit by the end because its observation is missing, report an incomplete trade and an inconclusive configuration; do not invent a terminal fill or silently drop it from a passing result. Relevant rules must also be consistent with the pinned Hypothesis.

Trial budget: two configurations, the baseline and `longer_lookback`. Stop after those two results or a material data/implementation defect. No additional lookbacks are generated from the observed returns. Both configurations remain part of one investigation.

Illustrative pseudocode:

```text
load the declared daily bar input and required warmup
validate ordering, unique instrument/session keys, and required fields
initialize flat position, no pending action, and diagnostic records

for each session in chronological order:
    at the open:
        process a previously scheduled exit, if its required observation exists
        otherwise process a previously scheduled entry when allowed by the rules
        record the actual selected observation and any deferral

    after the close becomes available:
        update the completed-session count for an open position
        schedule an exit after the specified holding sessions have completed
        if flat, eligible, and no action is pending:
            take the required number of completed closes available by this time
            calculate their arithmetic mean
            if today's close is strictly greater and the calendar cutoff allows entry:
                schedule entry at the next regular-session open

retain all signals, skipped decisions, position events, and completed trades
calculate each completed trade's gross return as exit_open / entry_open - 1
produce each configuration's predeclared metrics and diagnostics
```

This example defines intended logic. No RMS parser or executor evaluates it.

### 12.3 Concrete data specification

Requirement key: `daily_bars`. Provider: **Invented Demo Provider**. Dataset: **ALFA Regular Session Daily Bars v1**. Used by both configurations. Documentation: `https://data.example.invalid/docs/daily-bars-v1`; this intentionally nonworking URL is fixture text.

Method: REST retrieval. Base: `https://data.example.invalid`; endpoint: `/v1/daily-bars`; HTTP method: GET. Request fields: `instrument=ALFA`, `start`, `end`, `resolution=1d`, `session=regular`, `adjustment=raw`, and optional `cursor`. Start/end are inclusive session dates for this invented API. Pagination reads `next_cursor` until null. Fixture limit: 500 rows/page. Credentials: none for the invented example; no real network request is permitted.

Response schema:

| Field | Type | Meaning |
| --- | --- | --- |
| `instrument` | String | Fictional stable instrument identifier. |
| `session_date` | ISO date | Exchange session represented by the row. |
| `open` | Decimal string | Fixture opening price in USD. |
| `close` | Decimal string | Fixture closing price in USD. |
| `close_available_at` | UTC timestamp | Earliest time the close may be used for the decision. |
| `source_revision` | String | Fixed fictional source revision `demo-v1`. |

No field is nullable. Rows are unique by instrument/session and sorted ascending. The fixture contains enough preceding sessions for the longest lookback, plus an explicitly fixed session-calendar fixture used for holding counts and the entry cutoff. Count calendar sessions even if a price row is missing. The fixture has no corporate actions, universe changes, or value revisions; that is an explicit invented-data limitation. Availability uses `close_available_at`; next-session open execution cannot use a still-unavailable close. No joins are needed. Reject nonpositive prices, duplicate keys, wrong instruments, or nonmonotonic dates. Record missing required sessions and apply the declared skip/deferral policy.

Response example, invented shape only:

```json
{
  "items": [{
    "instrument": "ALFA",
    "session_date": "2016-01-04",
    "open": "100.00",
    "close": "101.00",
    "close_available_at": "2016-01-04T21:00:00Z",
    "source_revision": "demo-v1"
  }],
  "next_cursor": null
}
```

An invented external-check record may say a fixture test examined three rows and matched their schema. It must identify the fixture/test artifact and limitation that three rows do not establish full-period coverage. Saving that report tests recordkeeping only; it does not make a network call or prove real provider access.

### 12.4 Criteria and later change

The invented benchmark is a defined zero-return comparison for each trade interval, in the same return units, with no external benchmark dataset. Its rationale and relation to the Hypothesis's intended comparison are recorded explicitly.

An invented mandatory criterion for all configurations is mean completed-trade gross return greater than zero, with at least 20 usable completed trades per configuration. Fewer usable trades are inconclusive. These numbers exist only to exercise decimal thresholds and sample-rule display. A second objective rule checks that the required output and diagnostic tables can be reproduced; it describes implementation validity, not strategy merit.

After saving plan v1, revise the lookback variation with a reason to create plan v2. Both versions retain their own complete parameter definitions, child associations, and digests. Next create Hypothesis v2: plan v1 and plan v2 remain pinned to Hypothesis v1 and show an upstream notice. Explicit adoption produces plan v3 with the new Hypothesis pin. Older data checks remain attributed to their original versions. No test result, approval, or new research-cycle credit is created by any of these actions.

## 13 Focused acceptance cases

Independent Test verifies the accepted candidate and reports PASS, FAIL, or NOT EXECUTED for each applicable case. A planned case or builder report is not independent evidence. Use focused new cases and relevant existing regressions; do not rerun unrelated Stage 1 or completed runtime-recovery work.

| ID | Required observable outcome |
| --- | --- |
| TP01 | Create from an exact authorized Hypothesis with only a title; save/reopen succeeds as incomplete with ordered missing-field paths. No fabricated research values. |
| TP02 | Complete the invented baseline and one listed variation; UI/API agree on parameters, resolved configuration count/digests, trial limit, and completeness. No generated extra combinations. |
| TP03 | Invalid types, dates, conditionals, duplicate keys/names, excessive sizes, unknown overrides, and insufficient supplied trial budget return safe errors with zero partial writes. |
| TP04 | Revisions preserve plan identity and all historical content. Explicit adoption of another version of the same Hypothesis creates a reasoned revision; switching Hypothesis identity is rejected. |
| TP05 | Intended Hypothesis benchmark and plan evaluation benchmark remain separately visible. Difference requires explanation; saving never rewrites the Hypothesis. |
| TP06 | Numeric/objective criteria, units, conditional thresholds, sample requirements, optional/mandatory settings, and applicability behave identically in pages and API. No default scientific threshold. |
| TP07 | LEAN, REST, and existing-file data definitions validate only their applicable fields. Exact retrieval instructions, availability, transformations, limitations, and invented examples survive save/read/revision. |
| TP08 | Record external check results against exact plan/requirement/configuration versions. Saving makes zero provider calls, stores no credential values, and does not alter plan completeness or approval state. |
| TP09 | Check supersession preserves original evidence; concurrent report corrections cannot silently overwrite each other. Old-version evidence is visibly historical and is not counted as current-version success. |
| TP10 | Inline edits create/reuse child versions correctly. Removal/reordering changes only the successor's sealed associations. Cross-plan child adoption and late association changes are rejected. |
| TP11 | New Hypothesis and upstream corrections never retarget history. Current review notices and immutable historical content are visibly distinct. |
| TP12 | Lists, Home counts, Hypothesis/case links, and exact-version filters show the correct authorized records with deterministic pagination; empty and unavailable states differ. |
| TP13 | Same valid/invalid snapshots produce matching service behavior, completeness paths, exact references, and safe errors through browser and API. |
| TP14 | Focused new-service tests cover active editor, active viewer, no RMS role, inactive user, and anonymous access, including counts/history/check evidence. Existing role predicates remain unchanged. A new live viewer credential-entry exercise is not required for these focused automated checks. |
| TP15 | Validation errors, uniform missing-reference 404, and confirmed stale 409 retain all user-owned text and repeatable items, escaped safely, without a success claim or referenced-data leak. |
| TP16 | Lost-response retry with the same actor/key/payload returns the original result exactly once; changed-payload reuse conflicts; identical new-key correction creates no empty version. |
| TP17 | Two real overlapping revisions against the same expected plan head yield one successor and one conflict, with no orphan child versions/associations. Equivalent check-report conflict case passes. |
| TP18 | Scoped PostgreSQL tests demonstrate the stated version and sealed-association protections against ordinary DML, including late association INSERT. Report actual SQL role and limitations; do not claim privileged immutability. |
| TP19 | A fresh editor session can create and revise through the private staging origin using existing CSRF/login behavior. No reliance on a previously warmed session. |
| TP20 | Pseudocode, snippets, response examples, and evidence links are inert/escaped. Script text is not executed; URLs are not fetched by the server; secrets are not echoed into errors/logs. |
| TP21 | Home → Hypothesis → create plan → detail → revise → history → old version → pinned lineage is usable through clicks. Unsaved-navigation warning and deliberate recovery from conflict are demonstrated. |
| TP22 | Additive migration and repeatable invented fixtures work in existing staging; relevant prior Source/Idea/Hypothesis flows still work. No new database/service is created. |
| TP23 | Any necessary development reset is RMS-only; before/after checks confirm existing users, password hashes, memberships, permissions, and login access survive. If no reset is needed, report that honestly. |
| TP24 | Independent result names the exact candidate and installed build; founder walkthrough demonstrates the agreed feature with invented data and a clear list of remaining limitations. |

Record each case's command or browser steps, actual result, candidate/build, and evidence reference. Separate definition/software acceptance from data feasibility and research qualification. The founder may narrow an acceptance claim explicitly; the original failing/unexecuted evidence must remain visible.

## 14 Delivery ownership and implementation order

| Owner | Concrete deliverable |
| --- | --- |
| Diego | Finalize the scope and exact document revision; release the increment for implementation and make the later release decisions. |
| VP of Data & Engineering | Accountable for the existing RMS Development delivery program under MAU-32; keep this increment bounded and resolve escalations. |
| Director of Engineering | Own one integrated candidate, interface consistency, correction resolution, independent verification handoff, and browser delivery. |
| Backend | Additive models/associations/migrations, shared validation/services, immutable versions, check evidence, API schema, and focused tests. |
| Frontend | The single plan form, inline criteria/data editing, lists/history/lineage, check recording, safe errors, and navigation using the adopted interface. |
| Test | Independently verify the bounded acceptance cases, report defects against an exact candidate, and retest affected changes. |
| Operations or already authorized operator | Reuse working workspaces/staging and existing auth-preserving reset/fixture procedure; prepare or execute the specifically authorized release. |
| Research and Data | Supply or review substantive plan/data semantics when real plans are prepared. They do not need to supply live research or provider credentials to build this synthetic feature. |

### Sequence after implementation release

1. Record the complete accepted document in Paperclip and the repository. Director defines the disjoint implementation ownership and one interface in the existing increment task, then starts coding work.
2. Backend publishes the schema and a working create/read/revise service slice pinned to an existing Hypothesis version. Frontend builds the corresponding save/reopen/revise form against that exact shape while Backend completes persistence. Test prepares independent TP01–TP24 cases in parallel. Use invented examples immediately.
3. Director integrates that first slice into one runnable candidate: a user clicks an existing Hypothesis, saves an incomplete strategy/test plan, reopens it, revises it, and inspects the unchanged first version. Then extend the same flow with data specifications, inline criteria, listed variations, external check evidence, and completeness. This is implementation order within one increment, not a reduced final scope.
4. Independent Test runs the focused cases against the integrated candidate and returns actionable defects. Fix those defects through one assigned owner per change; rerun affected checks and the needed regression cases.
5. Publish a draft branch/PR early and update it with exact source and evidence as implementation progresses. Director reviews the final candidate, resolves findings, and states the accepted scope and any limitations.
6. Complete the recorded merge and staging update decisions, identify the installed build, and demonstrate the browser flow to Diego.

Use existing working runtimes and credentials. Startup checks should establish only what is actually missing for the current task. Do not repeat passed editor canaries, generic provisioning, or unrelated historical checks. If an agent cannot publish its result, preserve a local receipt and relay it through the authorized operator route once; repair the actual reporting problem without repeating unchanged acknowledgment chains.

Keep scheduling dependencies acyclic. Test needs an integrated candidate; do not block the Director's integration checkout on Test finishing acceptance of that same candidate. Test acceptance remains a completion condition.

## 15 Final document and implementation handoff

### Canonical artifact

The canonical file is `RMS_STRATEGY_SPECIFICATION_AND_TEST_PLAN_DESIGN_CONTRACT_V1_0.md`, version 1.0. Preserve the version 0.1 draft as historical source. Record the final byte length and SHA-256 in the handoff message or receipt after saving; do not insert a self-referential file hash into the contract. Later material changes require an explicit successor revision and change summary.

### Paperclip destination and ownership

Use the existing **RMS Development** project under [MAU-32 — RMS Stage 1 — demo-first incremental delivery](https://paperclip-6vpg.srv1986614.hstgr.cloud/MAU/issues/MAU-32). Create one new increment titled **RMS Increment 3 — Strategy Specification and Test Plan v1.0**, assigned to **Director of Engineering**. VP of Data & Engineering remains accountable for the program. Link [MAU-140](https://paperclip-6vpg.srv1986614.hstgr.cloud/MAU/issues/MAU-140) as the completed predecessor, and keep MAU-140 and MAU-44 closed. Do not repurpose an old task with stale canary, review, or acceptance instructions.

Create three implementation children: Backend, Frontend, and independent Test. Director owns integration and final review in the increment parent. Use an Operations child only for concrete environment or release work that is actually needed. This does not add a new approval ladder or require new staffing/readiness paperwork.

### Concrete handoff procedure

1. **Attach the complete contract.** Store the full file as an attachment on the new increment and as a readable Paperclip document with its revision reference. Put the filename, version, byte length, SHA-256, user objective, exclusions, and implementation authorization in the opening direction. A founder-Mac file path alone is insufficient.
2. **Make the same bytes available to all builders and Test.** Preserve the contract at `docs/RMS_STRATEGY_SPECIFICATION_AND_TEST_PLAN_DESIGN_CONTRACT_V1_0.md` in `mv-rms`, on the new feature branch based on the current merged `master`. Verify the received file's byte length/hash once and link its commit. Do not ask workers to reconstruct the contract from summaries or repeatedly fetch a file already available locally.
3. **Start one concrete deliverable per owner.** Backend supplies the schema and first create/read/revise slice; Frontend supplies the corresponding working browser flow; Test prepares independent cases. Director integrates that slice and resolves interface questions in the parent task. Record file ownership for overlapping root routes, templates, and migrations before simultaneous edits.
4. **Verify real receiving work.** Use supported task-bound assignments. Check that each receiving run sees its current task, exact contract, relevant interface commit, and correct workspace, then changes source or executes a meaningful check. Record the receiving run and first concrete result in the task; do not create a separate acknowledgment task or restart productive runs.
5. **Keep handoffs current.** Each implementation handoff includes the exact branch/commit, interface version/hash, changed paths, executed tests, remaining defect, and one next owner/action. Correct stale opening task instructions when the action changes. An input-contract hash is not a demand that authorized code or API output remain unchanged. Fix an actual reporting/access failure once through the existing authorized route; preserve local receipts if needed, and do not rerun completed implementation merely to repair status.
6. **Verify and release.** Apply TP01–TP24 to the exact integrated candidate, retain dissent and unresolved cases, and fix concrete defects. Director supplies one merge-ready PR and the existing-staging update proposal. Complete the recorded merge/deployment decisions, verify the installed version, and demonstrate the browser workflow.

Implementation release covers routine coding, integration, debugging, and scoped synthetic software tests using existing permissions and resources. The current staging data policy permits targeted clearing/reseeding of disposable RMS records while preserving users/auth. It introduces no standing authority for new security-sensitive access, purchases, new services, research execution, or automatic merge/deployment. These boundaries must not become repeated founder approval requests for ordinary work already covered by the release.

### What proves the handoff is complete

The parent has the full contract and founder direction; Backend, Frontend, and Test reference the same file and published interface; the receiving task runs have begun their concrete deliverables; and Director has a single integration branch and visible next action. Those facts establish implementation startup, not feature completion.

### Completion of this software increment

The feature is complete when the accepted bounded cases are independently resolved, the reviewed source is published and merged under its authorization, the approved version is installed in the existing staging application, and Diego can create/reopen/revise an invented plan with exact lineage and recorded check evidence through the browser.

That completion enables the next increment: implementing a selected plan in QuantConnect/LEAN, qualifying/acquiring its required data under the applicable research authority, running the first backtest, and linking code and results. It does not itself authorize those research actions or declare their criteria passed.

## Appendix A Source traceability

| Design requirement | Baseline or later decision |
| --- | --- |
| Exact Hypothesis pin, one Hypothesis to many plans | MAU-25 sections 6–7 and MAU-140 proposal revision 1. |
| Versioned criteria/data and first-class associations | MAU-25 sections 7 and 14.1; inline editing is this contract's simplifying presentation choice. |
| Strategy Specification and Test Plan phase name | Founder accepted the combined name and unchanged scope; one TestPlan package, no separate Strategy entity. |
| Benchmarks remain separately owned | Hypothesis contract section 4, Benchmark ownership. |
| Missing research content remains explicit | MAU-25 section 14.2; founder agreement to incomplete draft saves. |
| Pseudocode and detailed acquisition interface | Founder scope discussion preceding this contract. |
| Baseline plus enumerated variations | Explicit founder answer during document preparation; no automatic search. |
| External checks recorded without RMS connectors | Explicit founder answer during document preparation; consistent with founder RMS direction section 2. |
| Cost fields and cost completeness excluded | Later founder scope decision supersedes the corresponding field requirements for this increment. |
| Research approval remains distinct | Founder brief section 4 and RMS direction section 1; no authority workflow implemented here. |
| Existing stack and shared services | Founder RMS direction sections 2–3 and delivered Hypothesis interface. |
| Delivery hierarchy and concurrent work | MAU-32 Delivery operating model, checked in Paperclip during finalization: VP accountable, Director owns interfaces/integration, Backend/Frontend/Test run concurrently where dependencies permit. |
| Staging records disposable with auth preserved | Later founder development-data policy in this chat. |
| Existing results and limitations remain historical | Completed Hypothesis delivery; no retroactive claim of full original H01–H20 or institutional research assurance. |

Local source snapshots inspected for this contract:

| File | SHA-256 |
| --- | --- |
| `RMS_HYPOTHESIS_DESIGN_CONTRACT_V1_0.md` | `f9a7ebe54e329d1a994b7f37e5fd5bc62413c215e0f58acae1c8c7d4f604b0c9` |
| `RMS_STAGED_DELIVERY_PROPOSAL_MAU-25_REVISION_3.md` | `b3b3fa46522f8ade753c8ccafd2f917ddb883b398f0aba2d22c43be5f31f4948` |
| `CEO_RESEARCH_FIRM_BRIEF.md` | `c53792d9113cf7d3f2f09bfe377522c107ec3f9e5fba87e64c38f65a9f887ff7` |
| `CEO_RMS_DIRECTION_FINAL_V1_0.md` | `ea6ba04076ae0b89753c55c2040e1e88dc69dba4e238143f7040b72508621a1a` |

The MAU-140 proposal was read in the signed-in Paperclip interface and remains proposal revision 1. Its older cost requirement is explicitly superseded above, and its historical deployed-build reference is not used as a current installation claim.

## Appendix B What the next coding stage receives

For a selected plan, the handoff must provide:

1. Exact plan/Hypothesis/criterion/data version IDs, definition digest, and baseline/variation configuration digests.
2. A precise rule specification and pseudocode, with all named parameter values and permitted variations.
3. Dataset names, method/endpoint signatures, non-secret requests, schemas, timestamps, transforms, and missing-data behavior.
4. Exact requested periods and warmup, along with check evidence and unresolved access/coverage limitations.
5. Benchmark computation, expected output definitions, criteria, sample rules, stopping rules, and overall interpretation.
6. Any required research-authority decision and remaining prerequisites, sourced from their proper workflow rather than inferred from Draft complete.

The next stage should resolve genuine data/platform gaps, implement and verify the specified rules, and capture its actual source/configuration/run evidence. It should not have to invent the signal, select an undocumented dataset, decide an unexplained timestamp convention, or choose success thresholds after seeing results.
