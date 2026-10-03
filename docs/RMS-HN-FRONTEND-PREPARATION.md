# RMS-HN Frontend repository-only preparation

Assignment MAU-146, October 3, 2026. Director of Engineering is the named
native reviewer. This is source preparation, not an integrated feature or a
new Stage 1 acceptance result. MAU-142/143/144 remain blocked.

## Exact source and startup receipt

- Receiving run: af603d20-2710-43d7-818b-ad6df399e822; task
  79bf85a6-6d03-4beb-b5a7-511405eff0ee.
- Execution workspace: 3826d146-3403-4a1d-a51d-aa491b6d1918; existing environment
  c3931944-3432-4b78-ad1d-ff7e39cc78c0. Project workspace injection
  8258fcbb-78e0-44f2-bbf2-59e619b24920 is not the execution-workspace identity.
- Remote: dieg0andres/mv-rms. Fetched origin/master and initial HEAD:
  bd0e6b82634349ac2cbb75e91989e37dbb925014. Existing MAU-143 feature branch
  remains unchanged; initial dirty work: none. Non-root node, uid/gid 1000.
- Read all 12 sections, H01–H20 and section 11.2 of contract revision
  3982eccc-e180-4ac9-bc70-9c4e16aa47f1. Preserved source commit:
  de6b971b8b1ef8b5ab6d230641aaec0daeb7e374. Contract SHA-256:
  f9a7ebe54e329d1a994b7f37e5fd5bc62413c215e0f58acae1c8c7d4f604b0c9;
  startup recipe SHA-256:
  44c10594afef88ea3629c3a464157b35b359b9935960de763c901810af2cfbdb.
- RMS-HN-API-1 document revision 65b59da4-c7d3-4890-a4a5-8cd0f27f52ba
  fixes disjoint paths. Director preserves approved source and owns
  rms_project/urls.py; this change does not register its prepared URLconf.
- Existing toolchain provisioner verify-only: exit 0. Live SHA-256:
  fb0bc792212cccbde8f73556b5b17a11678bc741e200627382fd8c4fab341285;
  repository provisioner revision 95aa37b717eff21a76091ecf2c7b1ee2c6c3de69;
  approved recipe bootstrap revision 5e4105e0546c976ed86254cbfb10537180d210b7.
- Task-local imports: Python 3.13.15, Django 5.2.17, DRF 3.18.1,
  psycopg 3.3.6. Existing startup module: 3/3 PASS, exit 0, unused
  default database explicitly skipped. No DB environment or probe used.
- Default sandbox failed user-namespace creation; narrowly approved external
  commands ran non-root without any host-policy change. An empty installed
  apply_patch invocation returned 1 (no files modified); the actual source
  patch is the separate capability check, not an empty-patch PASS.

## Navigation slice and boundaries

Persistent semantic navigation, synthetic notice, role/build uncertainty,
skip link, current location, narrow layout, and proposed family/case labels
are reusable presentation components. The prepared URLconf requires Director
registration. New page controllers reuse existing server reader authorization;
they contain no record query or API call. Static screens honestly state that
record selection and Hypothesis saves are not connected, and counts are unknown.
Editor links reach existing Source/Idea creation routes only. Existing screens
inherit the shell; they do not yet supply role/current-location/build context.

No Backend schema is consumed in the first independent navigation slice.
Before schema-dependent controls, Backend must publish the exact commit, path,
SHA-256 and service signatures; Frontend explicitly receipts them on MAU-140.
No competing schema, payload inference, completeness calculation, record
mutation, migration, fixture write, browser storage, or live integration is added.

The generic draft presentation helper consumes frontend control descriptors,
not a transport payload/schema. It echoes submitted values without trimming,
replacing unknown selections or mutating the caller, and renders supplied field
errors/conflict text. Error summaries receive focus; context links stay in the
same document, keeping controls alive. No context selection or save is confirmed.
No reload persistence is claimed; no local/session storage or network transport
is used. Save remains disabled. Backend-derived descriptors remain gated.

## Reproduce database-free checks

Use the approved existing toolchain shell-env.sh as BASH_ENV, then:

```bash
python3 -B manage.py test tests.django_hypothesis_frontend_shell_tests tests.django_rms_si_frontend_template_tests -v 2
python3 -B manage.py test tests.django_hypothesis_frontend_draft_tests -v 2
node --test tests/django_hypothesis_frontend_draft.test.js
```

SimpleTestCase denies database access. Role tests use invented in-memory
principals and group objects, not real accounts. Rendering and URL resolution
are local checks, not actual browser observations or independent H01–H20 passes.
First navigation validation: 8 new shell checks plus 3 existing template
regressions, 11/11 PASS, exit 0; unused default DB skipped. git diff --check
PASS. Rendered HTML was inspected through exact content/escaping/link assertions.
First navigation commit: 7e9e6a2ba2807cc2d9ffb6f0fc54137af870938c, published
on the existing feature branch; remote SHA readback matched. An initial git
push had no HTTPS helper; the existing authorized gh account supplied a
process-local helper, with no saved credential/configuration changes.

Combined component validation: 18 Django checks (8 shell, 7 generic draft,
3 existing regressions) PASS, exit 0, unused default database skipped;
2 Node VM interaction checks PASS, exit 0. Node checks execute the actual focus
and preview-submit script against minimal invented document objects: they do
not establish real-browser keyboard, history, reload or narrow-viewport behavior.
git diff --check PASS. No real API call, database access, migration, fixture
runner, deployed screen or browser acceptance was exercised.

Historical schema-publication dependency was resolved by the Director on
October 3, 2026. The receiving schema agreement and completed bounded components
below supersede that remaining-source statement. MAU-145 remains open for its
separate runner-source deliverable. Do not remove original DB/integration blockers.
Research review is bounded to labels and uncertainty language; native Director
review is source-only. Test INCONCLUSIVE, Risk INCONCLUSIVE / NOT ACCEPTED
(HIGH), 34 unexecuted Stage 1 cases and restricted OPEN incident are unchanged.

## Schema-dependent source handoff — October 3, 2026

Receiving run: `b9b38c3d-cc4f-40b8-b1ef-324ee11c0b26`, MAU-146. Director wake
`b2942ec5-dbf0-4d20-8e0c-4c330649958e` resolves only schema publication.
BEFORE dependent edits, Frontend recorded agreement on MAU-140 comment
`1bbcadd8-0861-4e1b-85ff-b181bb51c0b8`, with exact response/readback match:

- Backend commit `57ac0a3efeb7e10738e3bfb0e788d5f85edec002`, RMS-HN-API-1 / 1.0.
- `rms/hypothesis_schema.json` SHA-256
  `ef2fe7d0e71d644ca978d7a3878f9ced4338212969cb6cdbc34a46550b73c5bc`.
- `docs/RMS-HN-API-1.md` SHA-256
  `10f0b286eb290fba60ed4c63e8d2af10f6febd579cd6d7a1899c1dc048bce4c7`.
- All 12 contract sections/H01–H20 and the accepted source/recipe identities
  above remain receipted; no source, schema or signature is replaced or copied
  into a competing frontend contract. Future shared persistence signatures were
  read, not invoked or implemented here.

### Actual continuation startup

API task binding remains execution workspace
`3826d146-3403-4a1d-a51d-aa491b6d1918`; injected workspace ID
`8258fcbb-78e0-44f2-bbf2-59e619b24920` is the primary project workspace, not
the task execution binding. Existing Local environment
`c3931944-3432-4b78-ad1d-ff7e39cc78c0` and toolchain are unchanged. UID 1000.
Actual cwd/top-level/branch guards passed. Remote is
`https://github.com/dieg0andres/mv-rms.git`; an actual no-tags master fetch
returned `bd0e6b82634349ac2cbb75e91989e37dbb925014`. Runtime-bound branch remains
`MAU-143-hypothesis-navigation-frontend-navigation-and-draft-workflow`;
starting HEAD `684e52a837b627c98f68823c333f8a4988efcbbc`. Initially clean; no
shared or dirty work removed and no branch switch/repoint occurred.

Existing provisioner verify-only EXIT 0, same provisioner revision/hash and
lock hash as the startup receipt above. Imports confirmed Python 3.13.15,
Django 5.2.17, DRF 3.18.1, psycopg 3.3.6, asgiref 3.12.1, sqlparse 0.6.0.
Minimal receiving command again passed 3/3, EXIT 0:
`python3 -B manage.py test tests.django_rms_si_frontend_template_tests -v 2`.
Default database explicitly unused/skipped. No DB environment, probe or contact.
The initial sandbox namespace failure was preserved; supported narrow escalation
worked without host/runtime/access changes. Installed native `apply_patch`
dispatch performed all source edits; no tool installation.

### Changed behavior and presentation boundary

- `rms/navigation_views.py` derives all 29 field controls, exact enum choices,
  duration scalar fields and context wrappers from the single receipted schema.
  Labels/help are presentation metadata, not duplicated domain validation.
  The schema reader verifies bytes and fails closed on missing/mismatched input.
  This feature branch does not import Backend files: Director must integrate
  the receipted source before the preview can successfully render normally.
- Hypothesis controls separate six accepted groups, exact origin/context binding,
  and correction reason/expected version. Nullable content is not falsely labeled
  mandatory merely because correction transport requires full snapshot keys.
  Durations retain all inputs visibly; changing kind/unit never silently clears
  a value, converts a decimal or hides conflicting input. No enum is preselected.
- Inline Research family, proposed Research case/manual assessment, and explicit
  Idea-family correction controls preserve their input in the same document.
  Correction descriptors distinguish retained assessment from a reasoned
  successor. Section-5 policy is a readonly procedure reference, not a completed
  review. A finding, empty link array or successful assessment is not invented.
- Hypothesis control names use exact RFC 6901 request paths. Supporting controls
  use presentation-only `/context/family`, `/context/case`, and
  `/context/idea-family` namespaces followed by the exact operation-local path.
  These namespaces are NOT API payload properties. Later authorized adapters
  must bind each operation separately and map its server field errors to the
  corresponding namespace; this preview does not serialize any request.
- Raw submitted strings, invalid selections, decimal text, context values and
  supplied errors survive local validation/conflict rendering. Supplied safe
  same-origin latest links can open a separate comparison tab without replacing
  this document. No automatic retry, overwrite, browser storage or reload
  persistence. Error summaries and inline-return targets retain focus hooks.
- The disconnected preview has no native form submission and a disabled Save
  button, so disabling JavaScript does not turn it into a GET-payload submission.
  No network transport or pure validator is bound to a live write route.
- Prepared editor-only `/hypotheses/draft-preview` authorizes before schema
  access; viewer/unassigned/anonymous roles are denied without preview content.
  Missing/mismatched schema yields an honest 503 without private path/error
  diagnostics. Director still exclusively owns root URL registration; no route
  here is deployed, and links identify the source-only preview as unreleased.
- `hypothesis_record_presentation` and the record-preview include accept only
  already-authorized supplied read projections; they do not query records.
  They distinguish version/correction/actor/time, missing values, upstream review,
  and supplied completeness without computing it. Exact Idea/Source references
  point to visibly anchored versions on existing history pages, not latest detail.
  Context pages not yet connected remain text with immutable IDs, not guessed URLs.
  All pinned association endpoints stay visible. Existing history templates now
  contain the matching version anchors. A supplied notice never retargets citations.

### Checks, fixtures and reproducible receiving step

With the existing approved toolchain `shell-env.sh` as BASH_ENV:

```bash
python3 -B manage.py test tests.django_hypothesis_frontend_schema_tests tests.django_hypothesis_frontend_shell_tests tests.django_hypothesis_frontend_draft_tests tests.django_rms_si_frontend_template_tests -v 2
node --test tests/django_hypothesis_frontend_draft.test.js
git diff --check
```

Result: 37/37 Django checks PASS, EXIT 0; unused default DB explicitly skipped.
Nineteen new schema checks plus the existing 18 shell/generic/template checks.
Two existing Node VM interaction checks PASS, EXIT 0. Whitespace check PASS.
Initial new-module run was 17 PASS/1 ERROR: an invented Source template input
omitted its required `detail.latest` projection. Fixed that fixture, not production
domain code; subsequent new-module run 19/19 and combined run 37/37 PASS.

Test schema input is the exact single Backend file, verified by hash: from its
integrated path when present, otherwise the already-fetched immutable Git object
at `57ac0a3:rms/hypothesis_schema.json`. No network is used by tests; no copied
schema fixture lives in Git. A receiving checkout lacking that Git object must
first obtain the named Backend source through the existing authorized source
handoff rather than substitute a schema or report these checks passed.

Fixtures in `tests/django_hypothesis_frontend_schema_tests.py` are visibly invented,
in-memory presentation subsets, NOT valid service writes, persisted rows or a
runner fixture. Fake editor/viewer/denied principals have in-memory group objects;
SimpleTestCase disallows database access. Exact Source/Idea anchors, raw-input
escaping, schema coverage, no defaults, distinct durations, explicit context,
correction controls, safe compare URLs and pre-render denials are asserted.
Actual Django HTML was rendered and inspected through those checks; Node uses
minimal invented document objects, not a real browser.
An additional invented validation/conflict draft was rendered to run-local HTML
and inspected with HTMLParser: 75 controls have associated labels, all IDs are
unique, and no native form exists. This structural source inspection is not an
observed screen, keyboard, narrow-layout or browser-acceptance result.

Director of Engineering is the named reviewer through MAU-146 native review.
Next receiving action: inspect this exact published Frontend commit and adopted
Backend bytes, run only the DB-free commands above, and record the bounded source
verdict. Test Engineering may reproduce this builder source packet only within
its existing authorization; no independent result is inferred. Research usability
review is bounded to labels, manual-review uncertainty and intended-benchmark
wording, routed by the Director without a new assignment here.

### Unexecuted and preserved holds

This completes the authorized source-preparation slice, NOT the product workflow.
No saved context return, reload/back-forward persistence, browser keyboard/focus/
narrow-viewport observation, real API/page parity, DB integration, record selection,
concurrency/idempotency persistence, migration or fixture execution occurred.
Existing database-dependent page/history regressions are NOT RUN. H01–H20 and
P01–P06 remain NOT RUN; original MAU-142/143/144 stay blocked. Test INCONCLUSIVE,
Risk INCONCLUSIVE / NOT ACCEPTED (HIGH), 34 unexecuted Stage 1 cases, restricted
OPEN incident, ordinary-role/preserving-procedure/sequence/concurrency/coordinated-
use prerequisites and all independent/release gates remain unchanged.
No merge, deploy, service/resource/access/credential expansion or research work.
