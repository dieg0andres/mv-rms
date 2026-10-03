# R4/R5 Backend source handoff — October 3, 2026

Ready for **Director of Engineering** source review on
[MAU-142](/MAU/issues/MAU-142). Receiving Backend run:
`2ba615a6-6532-4627-a229-c3eaf01aa68e`.
Authority is the current task's bounded source release and Director handoff
`c9666c52-7418-48ba-8f43-5fc57c6880a5`, read in full with its adjacent
evidence JSON/probe from the existing [MAU-140](/MAU/issues/MAU-140) worktree.
The harness already owns this checkout. No checkout was repeated.

## Candidate and preservation

Base/unchanged HEAD: `ac5b0291d6f12d75c54175a54cc224abc4876081`.
Branch: `MAU-142-hypothesis-navigation-backend-records-lineage-and-draft-api`.
There is **no new commit**: Git staging was denied once. This is an exact
working-source handoff, not a claim of committed/pushed publication.

Ten changed product/test/interface paths are bound by
`RMS-HN-API-1-R4-R5-2ba615a6-source.json`:
source-manifest SHA256
`df2500731f0a22750aa1ba34dd70209d3c6fd088b9e591b59120de7738ff1997`.
The manifest explains the canonical JSON binding and supplies each file's
length/full SHA256. `RMS-HN-API-1-R4-R5-2ba615a6-source.diff` includes both
tracked modifications and new files; 56,260 bytes, SHA256
`12c49ec359e6cde518ebcf4fe2b2c6fa542f5d010e856f015b3fd2893a5c76f8`.
The receipt, JSON, diff and test output are additional evidence files.

Accepted founder contract remains 58,395 bytes, SHA256
`f9a7ebe54e329d1a994b7f37e5fd5bc62413c215e0f58acae1c8c7d4f604b0c9`.
The four previously approved corrections and their review evidence remain in
place; their correction suite/review was not repeated. Existing `.paperclip`,
editor canaries and prior untracked handoff/review files are preserved.

## Behavior and interface impact

- `rms/permissions.py` supplies shared `has_rms_read_access(actor)` and
  `has_rms_write_access(actor)`. Active authenticated editors/founder viewers
  read; editors write. No-role/inactive/staff-only/superuser-only principals are
  denied. Anonymous API requests retain 401. `IsEditor` delegates to these
  predicates; new services retain the `require_actor(actor, *, write=False)`
  signature and HN 401/403 envelope. Existing Source/Idea detail/history and
  Source manifest gain the same read boundary before lookup. Readiness retains
  its separate policy.
- `rms/record_selection_services.py` supplies exactly the shared
  `list_sources(*, actor, query)` / `list_ideas(*, actor, query)` entry points.
  Count/slice/links use the same permitted synthetic identity queryset,
  identity-created-at descending then Source/Idea stable ID ascending. Only
  selected latest-version metadata is loaded; Source bytes/digests are deferred.
  Missing/inaccessible latest data and database failures return safe 503
  `selection_unavailable`, never a fabricated zero or dropped counted row.
- `rms/api.py` adds GET on existing SourceCreateView/IdeaCreateView; POST,
  paths/names and old detail/history/manifest payloads remain intact. Pagination
  defaults 1/25, maximum size 100; only canonical, unrepeated page/page_size
  fields are accepted. No new URL patterns/root edits/search are introduced.
- The single schema/prose successor is interface **1.2**, record/completeness
  schema **1.0**. It has 26 operations: existing HN module's 24 plus two existing
  collection-route GETs. Six selection/query/list definitions are added; the
  error-code enum gains `selection_unavailable`. Existing research request/read
  definitions and all prior endpoint declarations remain otherwise identical.
- Existing test helpers now represent founder viewers with actual mocked
  `founder_viewer` membership; route/schema expectations include the successor.
  `tests/django_record_selection_backend_tests.py` adds the focused verification.

Exact successor hashes for Director, then Frontend/Test receipt:

| File | Bytes | SHA256 |
| --- | --- | --- |
| `rms/hypothesis_schema.json` | 29,915 | `8a2ee1204b3d54647010254939bee3fabf49d5c2a1edae25a7e6be010726aaea` |
| `docs/RMS-HN-API-1.md` | 16,513 | `c03f57baf0386876caee9fd80ba2bc9ab3a7fecd7b9e796bb65ca5bef8530471` |

Reviewed 1.1 remains at the base commit with its historical hashes; successor
hashes intentionally differ. The preserving runner/manifest remain untouched
and HOLD. No migration is needed or authored for R4/R5; previous 0004/0005
remain unexecuted under the existing separate procedure/adoption gates.

## Reproducible DB-free verification

All commands used `login=false` and the existing `.venv/bin/python`.
Final output: `RMS-HN-API-1-R4-R5-2ba615a6-tests.txt`.
Run from this task worktree, without invoking Django's database test runner:

```bash
.venv/bin/python - <<'PY'
from unittest.mock import patch
from django.db.backends.base.base import BaseDatabaseWrapper
import unittest
names = [
    'tests.django_record_selection_backend_tests',
    'tests.django_hypothesis_backend_source_tests.APIBoundaryTests',
    'tests.django_hypothesis_backend_source_tests.SharedRequestBoundaryTests',
    'tests.django_hypothesis_backend_source_tests.ModelAndRouteSourceTests.test_all_declared_endpoint_routes_resolve',
    'tests.django_hypothesis_backend_validation_tests.SchemaContractTests.test_schema_identity_and_all_local_refs_resolve',
]
with patch.object(BaseDatabaseWrapper, 'ensure_connection',
                  side_effect=AssertionError('No DB authorized')) as guard:
    suite = unittest.defaultTestLoader.loadTestsFromNames(names)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    guard.assert_not_called()
    print('database_connection_attempts:', guard.call_count)
    raise SystemExit(not result.wasSuccessful())
PY
git diff --check
```

Observed final result: **30 tests PASS**, exit 0, zero database connection
attempts; `git diff --check` exit 0. Includes roles before adapter dispatch and
shared-service lookup/count, both permitted roles, legacy operations/readiness,
uniform 404, query validation, scoped counts/order/latest links, pagination,
empty/unavailable behavior, byte deferral and exact schema compatibility.
Existing affected boundary checks retain idempotency/replay/stale behavior.

Earlier verification was not additional credit: first 23-test run had seven
subcase errors because a new assertion assumed the legacy handler supplied a
WWW-Authenticate header. That handler already omitted it at the approved base;
the legacy assertion was corrected to test its existing 401/code behavior.
HN's existing Basic challenge regression remains passing. A 29-test run then
passed; the final 30-test run adds permitted HN dispatch and legacy safe-404
coverage. Product source did not change after the final test run.

Measured final Python process (not whole-run billing): wall 0.448898 seconds,
user CPU 0.454014 seconds, system CPU 0.082004 seconds, maximum RSS 66,276 KiB;
30 test bodies took 0.073 seconds. Runtime/pinned manifest unchanged. No
provisioner/setup/canary/network/package/service operations were performed.

## Git checkpoint and next owner

Exactly one metadata-write attempt, exit 128:

```bash
git add docs/RMS-HN-API-1.md rms/api.py rms/hypothesis_schema.json rms/hypothesis_validation.py rms/permissions.py rms/research_context_common.py rms/record_selection_services.py tests/django_hypothesis_backend_source_tests.py tests/django_hypothesis_backend_validation_tests.py tests/django_record_selection_backend_tests.py
```

Git returned `Unable to create` the existing repository's
`.git/worktrees/MAU-142-hypothesis-navigation-backend-records-lineage-and-draft-api/index.lock`:
`Read-only file system`. No commit/push retry or workaround followed.
The operator's existing authorized checkpoint can bind these exact files to a
local commit; include only the intended source/test/interface/evidence files,
preserving unrelated untracked evidence. Director reviews that actual candidate,
then [MAU-143](/MAU/issues/MAU-143) consumes 1.2 and
[MAU-144](/MAU/issues/MAU-144) receives the Director's integrated candidate.
The recipient's actual receipt/run remains to be recorded; none is fabricated.

Rollback is a source revert through normal review; there is no database/schema
recovery action for these changes. Synthetic identity visibility is the existing
shared RMS-role scope, not a newly asserted per-account rights facility. Real
account/DB/role/browser execution, H01–H20 and independent Test/Risk acceptance
remain unverified. No merge/deploy/database execution occurred.

**Intended disposition: in_review, named reviewer Director of Engineering.**
No Paperclip GET/PATCH/artifact write was attempted, following the current
operator no-DNS-retry/final-response-relay instruction. Server status is not
claimed changed. Final response is the authorized operator UI relay for this
review handoff and the read-only Git checkpoint failure.
