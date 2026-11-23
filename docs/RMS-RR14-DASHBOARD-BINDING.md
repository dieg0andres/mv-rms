# RR14 dashboard binding (disposable synthetic walkthrough only)

Apply this overlay after the PR #9 scaffold (including the additive plain-text
MAU-33 reference) and the Director-approved MAU-179 backend replacement. Keep
the retained search route when reconciling navigation. No settings, schema,
database rights, fixtures, or backup format are added by the dashboard overlay.
Only the disposable candidate's existing `RMS_RR14_SCOPE_FILE` configuration
enables the link and reader. Removing the configuration disables them without
changing saved history. Do not enable it on installed accounts.

From an authorized Test Plan detail or exact-version page, follow **Founder
dashboard for this exact Plan version**. The server calls the shared projection
with the authenticated request actor and the exact route tuple. The link does
not grant access. The scoped dashboard never uses the fixture provider, falls
back to another version, or returns source payloads. Unavailable, denied and
integrity-failed reads display a generic unavailable state; a verified empty
synthetic scope can display zero. The observation time is the read time, not a
freshness guarantee. Real ledger totals remain unavailable; zero real credit
from these synthetic records is shown separately.

Frontend request tests (invented authenticated actors; reader mocked):

```sh
.venv/bin/python manage.py test tests.django_rr14_dashboard_tests tests.django_dashboard_tests tests.django_test_plan_frontend_render_tests
```

On the exact combined disposable candidate, at quiescent fixture checkpoints,
compare the normal session dashboard to the canonical exact-version JSON
projection before and after saving two distinct attempts and one original
synthetic early closure. Confirm the +2/+1 deltas and zero real credit from
those records, not zero overall totals. Replay and correction do not add
closure credit. Confirm the exact Plan link, keyboard focus and 360 px layout.
Repeat with unrelated editor on the valid tuple, revoked editor and outsider;
compare withheld and nonexistent responses for identity/count/time leakage and
correct private/no-store headers. Changing a hidden record must not affect
visible counts. Neither mocked requests nor scaffold browser checks prove
saved-source parity. Independent Test Engineering records the frozen SHA/tree
and browser/API evidence separately; no release or real-use acceptance follows.
