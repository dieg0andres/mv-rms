# MAU-145 G05 corrective successor receipt

October 3, 2026. Builder: Backend Engineer; receiving run
`7ed3b0cc-e57d-4c46-9152-c173594de705`, task
`8134410a-0e03-47c1-8dae-dd76e7bbe78a` (MAU-145). Exact successor commit/tree,
changed-path hashes and preserved logs belong in the external issue packet,
not a self-referential commit field. This receipt is not independent acceptance.

## Authority and preserved review

Human source-only delegation `506673c1-71c4-4ed4-8962-4451a445bdb0`, October 3,
09:14:56.033 UTC, read back unchanged. Current Test changes-requested comment
`56247a58-8cbc-455a-bd89-77ce7b8a126c` and report revision
`d2d0e8e6-0662-4b54-a3b0-66eaa8fc92c0` authorize this bounded same-task G05
source correction. The independent 49-helper PASS and BASELINE-ALIAS-01 FAIL
remain attributed to Test and unaltered; this builder result does not replace them.
Accepted predecessor `1a306f24b030da1e3ee2df7d6e439849959ca616`, approval
`29b2a559-56aa-4f4f-8fa1-6c5a3189e20b`, and reviewed corrective predecessor
`e3c0dd8b25fc102cfae5b11f7b99e66f1e44b1c7` / tree
`688973cab04354d3114fde9e2a864108234ba927` remain preserved.

Native checkout and one GET readback confirmed Backend ownership and this run.
Completed Director stage `682931de-55ec-4b92-affb-0de26a778f6b` and actual
native Test stage `e4afa17f-318e-4e27-9ed2-916668ea31d5` remain unchanged.
Director `86f5fae2-e9e7-4c89-8f78-157f4d41b572` receives the exact packet for
source reconciliation; Test `a61c51d8-fd54-42db-927c-106e82cde751` is the retained
native successor reviewer. No policy, participant, decision or assignment reset.

## Receiving workspace and startup

- Cwd remains the existing MAU-142 worktree and branch
  `MAU-142-hypothesis-navigation-backend-records-lineage-and-draft-api`.
  Initial HEAD/tree match the reviewed predecessor above; initial dirty work none.
  No branch switch, rename/repoint, reset, repository creation or unrelated edit.
- API execution workspace `749e45e0-42a8-4bb7-a3b8-cb93c3fa220f` and injected
  workspace `8258fcbb-78e0-44f2-bbf2-59e619b24920` reuse the approved cwd.
  API `executionEnvironmentId` is null; manifest pin
  `c3931944-3432-4b78-ad1d-ff7e39cc78c0` is not observed installed DB evidence.
- Remote `dieg0andres/mv-rms`; locally observed `origin/master`
  `bd0e6b82634349ac2cbb75e91989e37dbb925014`. No fetch, provisioning or DB probe.
  Run uid 1000/node; no root/sudo, host configuration or access changes.
- Preserved contract Git-object SHA-256 matches
  `f9a7ebe54e329d1a994b7f37e5fd5bc62413c215e0f58acae1c8c7d4f604b0c9`.
  API/schema/validator/requirements.lock/manifest/model/migration/service source
  is unchanged. No Frontend or `rms_project/urls.py` edits.
- Minimal DB-free startup: `python3 -I -B -c 'import sys, django, rest_framework,
  psycopg; print(sys.version.split()[0], django.get_version(),
  rest_framework.VERSION, psycopg.__version__)'`, exit 0: Python 3.13.15,
  Django 5.2.17, DRF 3.18.1, psycopg 3.3.6. Existing pinned PATH reused;
  no DB environment sourced or settings/credential binding created.
- Namespace sandbox failed before its command ran. Approved escalated commands
  remain uid 1000. Initial `apply_patch` command lookup failed; the premature test
  selector reported missing `FrozenPreservationBaselineTests`, not a product
  assertion failure. Both errors remain in the run transcript. Subsequent edits
  use the bundled Codex `apply_patch` implementation. No sandbox/host-policy edit.

## Corrective boundary and verification

G05: freeze the full original inventory into canonical immutable owned bytes before
any persistence/verifier callback; derive the acknowledged digest from those bytes;
persist only a detached decoded view; compare final observations with a new view
decoded from the frozen original. Adapter and callback aliases never become the
original oracle. Existing exact-addition, projections, account/role/sequence,
volume/private-route/watermark and original row/FK/association assertions remain.
Durability acknowledgement authentication remains the independent verifier's duty.

Builder commands, on invented dictionaries and callbacks only:

```bash
python3 -B -m unittest tests.django_hypothesis_backend_preservation_helper_tests.FrozenPreservationBaselineTests -v
python3 -B -m unittest tests.django_hypothesis_backend_runner_guard_tests tests.django_hypothesis_backend_preservation_helper_tests -v
git diff --check
```

Observed: nine G05 tests PASS (exit 0, 0.013 seconds reported); 58 focused adjacent
guard/preservation-helper checks PASS (exit 0, 3.152 seconds reported).
The regression subprocess wrapper measured 3.288099 seconds wall, 1.593738 seconds
child user CPU, 1.414308 seconds child system CPU and 27964 KiB child peak RSS;
12308 log bytes. These are local test-only measurements, not target capacity or
whole-heartbeat/provider cost. Provider cost is not exposed. No new resource,
access or paid service was requested. Whitespace check exits 0.

New negatives cover retained persistence callbacks across all protected original
inventory categories, in-callback rewriting, changed-byte acknowledgements and
reused adapter snapshots. Positives cover exact approved additions and unchanged
reused snapshots. Full inventory and nested callback views remain detached;
missing/incomplete inventory fails before callbacks. AST checks pin the actual
freeze/persist/final comparison wiring without invoking orchestration. Existing
G01-G04 focused cases retain builder PASS, not operational closure.

## Handoff, impact and remaining holds

Four-file source/test/document change only; no API/schema/migration/manifest/lock
change, no runner/harness entrypoint, DB/session/SQL contact, fixture/service writer,
install, browser, cleanup or deployment. Source rollback is Director-reviewed
decline/revert only, preserving prior commits/evidence; there are no DB effects.
The exact successor must be independently reviewed; G05 MEDIUM/open is not closed
by this builder receipt. Completed stage/history is not rewritten.

The historical proposed preserving command remains NOT ADOPTABLE. This successor
does not reconcile `rms_synthetic`/null bindings into observed `rms_staging` approval
or make any installed source/schema claim. Operations MAU-141 owns exact ordinary
role, target/schema, sequence, coordinated session, stop and restricted sink proof;
Test MAU-144 owns later independent command adoption, and MAU-140 owns concrete
execution approval. No new readiness round or additional task is requested.

H01-H20/P01-P06 NOT RUN; integrated Test INCONCLUSIVE/NOT ADOPTABLE; Risk
INCONCLUSIVE/NOT ACCEPTED (HIGH); 34 Stage 1 cases, restricted OPEN incident,
DB/install/access/release/research holds remain unchanged. No H/P pass or research
credit, self-acceptance, merge, deployment, publication of research or authority
expansion is claimed.
