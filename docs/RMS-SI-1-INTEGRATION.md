# RMS-SI-1 integrated demonstration candidate

**Contract:** RMS-SI-1.0, Paperclip document revision `13eb82e2-9762-4d96-83cc-30e6aa8b6f3e`
**Scope:** fictional/synthetic Source completion and Source-to-Idea only
**Candidate:** resolve with `git rev-parse HEAD` from the exact handed-off commit; a branch name is not a candidate identity

## Recommendation

Submit this exact integrated commit to independent Test Engineering. It retains the Backend candidate and corrected Frontend candidate in one linear history, repairs their missing page-route/context boundary, and adds executable route-level acceptance coverage. Do not deploy it or treat software verification as Risk acceptance, research approval, evidence immutability, or authority to use real/protected data.

## Evidence index

- Frozen interface: RMS-SI-1.0 revision `13eb82e2-9762-4d96-83cc-30e6aa8b6f3e`, September 22, 2026.
- Corrected Frontend handoff: commit `5d22886170c3dac95dac37d5e7aa2d12f45fb5ae`; it is an ancestor of the integrated tree.
- Backend handoff: commit `5bd23cfc64627ff7e72c6ac4788c55544b573adb`; it includes the Frontend commit in its ancestry.
- Predeclared independent checklist: `docs/verification/rms-si-1-predeclared-checklist.md`.
- Executable API demonstration: `tests/django_source_idea_tests.py`.
- Executable page/permission demonstration: `tests/django_rms_si_frontend_page_tests.py`.
- Legacy VS1 regression evidence: `tests/test_source_manifests.py`, `tests/test_source_versions.py`, and the delivered Django Source tests.

## Integration failures and repairs

1. **Missing route/context integration.** The Frontend handoff supplied templates and browser binding, but the Backend tip routed only the legacy Source history page. Source/Idea editors and Idea detail/history were unreachable. Repair: add authenticated server routes and safe page contexts for Source create/correct/history and Idea create/correct/detail/history.
2. **Incorrect page permission composition.** The legacy Source history page admitted `founder_viewer` only, while RMS-SI-1.0 requires readable pages for both `editor` and `founder_viewer`. Repair: authorize those two groups for reads, only `editor` for editing pages, and perform the role check before object lookup.
3. **Incomplete correction form state.** The raw templates did not restore Idea contribution rows or select-valued fields from the latest immutable version. Repair: prefill the full latest snapshot, retain exact `source_version_id` contribution edges/text, and place the current enum value first without exposing raw bytes.
4. **Historical manifest discoverability.** The Source history page linked only the latest manifest. Repair: give every displayed immutable Source version a `through_version` manifest link while retaining the latest manifest integrity summary.
5. **Over-specific safe error pages.** Shared denial/not-found templates named Source history even on Idea routes. Repair: use generic RMS wording so equivalent missing/invalid records do not disclose object existence.

No tests or acceptance criteria were removed, skipped, or weakened.

## Reproducible fictional demonstration

Use an isolated PostgreSQL 17 database and the pinned Python environment documented in `docs/RMS-VS-1-BACKEND.md`. Do not use a shared or protected database.

```console
export RMS_DB_NAME=<isolated_database>
export RMS_DB_USER=<task_local_role>
export RMS_DB_HOST=127.0.0.1
export RMS_DB_PORT=<task_local_port>

.paperclip-runtime/venv/bin/python manage.py migrate --noinput
.paperclip-runtime/venv/bin/python manage.py test \
  tests.django_source_api_tests \
  tests.django_source_history_page_tests \
  tests.django_fixture_tests \
  tests.django_contract_tests \
  tests.django_source_idea_tests \
  tests.django_rms_si_frontend_template_tests \
  tests.django_rms_si_frontend_page_tests -v 2
```

The executable demonstration performs this fixed sequence:

1. Create a fully described fictional Source v1 with invented bytes, citation, authors, publisher, publication/availability timestamps, URL, and rights note.
2. Inspect Source v1 and its canonical `through_version=1` manifest.
3. Create a fictional Idea v1 whose contribution binds the exact immutable Source v1 ID and records contribution text.
4. Correct only the Source publication timestamp, producing v2 and a distinct `through_version=2` manifest while preserving v1.
5. Read the Idea again and prove its contribution and immutable Source summary still bind v1; prove neither Source v2 nor raw Source bytes appear.
6. Correct the Idea claim with a reason, then inspect both immutable Idea versions and their predecessor links.
7. Exercise editor, founder-viewer, other-authenticated, and anonymous boundaries with role checks preceding lookup.
8. Exercise byte-identical idempotent replay, cross-endpoint key conflict, atomic stale rejection, and one-winner concurrent correction in the Backend suite.

For a manual local rendering after creating the fictional fixture through the API:

```text
GET /sources/<source_id>/history
GET /sources/<source_id>/correct
GET /ideas/<idea_id>
GET /ideas/<idea_id>/history
GET /ideas/<idea_id>/correct
```

The page responses display metadata only. Source content bytes are intentionally absent.

## Verification acceptance matrix

| Acceptance item | Executable evidence | Required result |
|---|---|---|
| Fully described Source plus publication-date correction | `test_source_metadata_timezones_correction_and_historical_manifest` | Both immutable versions and both canonical manifests preserved |
| Idea cites exact Source v1 across Source correction | `test_idea_binds_exact_source_version_across_source_correction_without_bytes` | v1 edge/summary unchanged; v2 and raw bytes absent |
| Idea correction and two-version inspection | API demonstration plus `test_reader_pages_show_versions_manifests_and_exact_v1_citation_without_bytes` | Both Idea version IDs, predecessor/reason, and contribution text visible |
| Editor/viewer/anonymous boundaries | Backend authorization tests plus `test_editor_viewer_other_and_anonymous_boundaries_are_server_enforced` | Editor-only forms; editor/viewer reads; generic denials |
| Atomic stale rejection and idempotent replay | Source and Idea API tests | No partial rows; exact stored replay |
| Existing VS1 behavior | public and delivered Django regression suites | All tests remain active and pass |
| Migration/system readiness | fresh `migrate`, `makemigrations --check --dry-run`, and `manage.py check` | Apply cleanly; no model drift; no system issues |

## Alternatives considered

- **Ship the Backend tip without page integration:** rejected because the accepted Frontend was unreachable and the requested editor/viewer demonstration could not be reproduced.
- **Duplicate mutation logic in page views:** rejected because pages must submit the frozen API contract and Backend must remain the sole mutation/authorization authority.
- **Bind Idea citations to the latest Source:** rejected because it violates the exact immutable Source-version contract and point-in-time correction history.

## Assumptions, risks, dissent, and dependencies

- Assumption: the task-local pinned PostgreSQL/Python stack is available to independent Test; general product documentation is not treated as observed account evidence.
- Risk: HTTP Basic authentication is loopback development behavior only. This candidate makes no deployment or production-security claim.
- Risk: application-level immutable versions and database guards do not by themselves satisfy the later sealed-evidence, backup, recovery, or restricted-test requirements.
- Dissent: none recorded during integration. Independent Test retains authority to reject the exact candidate and must preserve adverse findings unedited.
- Dependency: independent software verification remains owned by the designated Test Engineering issue. Any defect returns to Engineering; criteria must not be weakened.

## Decisions and handoff

No new founder decision is requested. The accepted scope and frozen contract already govern this increment. Independent Test must verify the exact commit named in the handoff before the parent can treat Increment 1 as software-verified. Deployment, service operation, real/protected data, research testing, Risk acceptance, purchases, and access changes remain outside scope.
