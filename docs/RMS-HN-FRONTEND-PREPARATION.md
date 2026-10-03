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

## Reproduce database-free checks

Use the approved existing toolchain shell-env.sh as BASH_ENV, then:

```bash
python3 -B manage.py test tests.django_hypothesis_frontend_shell_tests tests.django_rms_si_frontend_template_tests -v 2
```

SimpleTestCase denies database access. Role tests use invented in-memory
principals and group objects, not real accounts. Rendering and URL resolution
are local checks, not actual browser observations or independent H01–H20 passes.
First navigation validation: 8 new shell checks plus 3 existing template
regressions, 11/11 PASS, exit 0; unused default DB skipped. git diff --check
PASS. Rendered HTML was inspected through exact content/escaping/link assertions.
Research review is bounded to labels and uncertainty language; native Director
review is source-only. Test INCONCLUSIVE, Risk INCONCLUSIVE / NOT ACCEPTED
(HIGH), 34 unexecuted Stage 1 cases and restricted OPEN incident are unchanged.
