# Hypothesis and Navigation: development closeout

Date: 2026-10-03. Delivery: MAU-140; implementation: MAU-142/143; independent verification: MAU-144.

## Tested product and release

- Product commit: `529e6382e0fc1ca212b20f2400bb83e9de7b5efc`.
- Product tree: `5b98b0b2e7de1cd27009b754089f801c770eb745`.
- GitHub: [PR #4](https://github.com/dieg0andres/mv-rms/pull/4), `codex/rms-hypothesis-navigation` into `master`.
- This product is installed and healthy on the existing private development staging application. The app-only update completed at 21:30 UTC. Database identity/start/volume, three existing users, all seven protected auth/content-type tables and application configuration/security were unchanged. No migration or data reset was needed for this update.
- The accepted design contract remains byte-exact, SHA-256 `f9a7ebe54e329d1a994b7f37e5fd5bc62413c215e0f58acae1c8c7d4f604b0c9`. Later founder decisions are recorded separately.

## Founder scope decisions

Diego requested finishing to reasonable development confidence, publishing the final work, merging into `master`, and proposing the next small increment. Director narrowed the remaining execution to an editor browser flow and rollback-only history-protection probes. This is a development merge decision; it does not assert complete original H01–H20, production, research, Risk, or Stage 1 acceptance.

All remaining Viewer checks are **WAIVED BY FOUNDER / NOT EXECUTED**, not PASS. The existing user accounts and permissions remain protected. Staging research/test records are disposable under [the separate data-policy addendum](RMS-HN-DISPOSABLE-STAGING-ADDENDUM.md).

## Evidence completed

| Evidence | Actual outcome | Limits |
| --- | --- | --- |
| Editor-only HTTP execution | 29 passing assertion entries, 17 requests; one Hypothesis and two versions | 27 unique labels, not 29 acceptance criteria. Two Viewer cases not executed and now waived. |
| Scoped lineage row readback | Eight assertions passed; two stable relationship identities plus two impact identities explain the four identity rows | Read-only check of the test-created Hypothesis. |
| Independent history guard evaluation | 22 exact UPDATE/DELETE trigger denials across 11 populated tables; rollback, sampled rows unchanged | External-reference table empty and unexecuted. Actual application SQL role is privileged; no least-privilege or administrator-bypass claim. |
| Fresh-session CSRF correction | Four unchanged independent affected-source checks passed on `529e638`, with zero database connections. Existing missing-token/foreign-origin protections remain. | Earlier `aead8ff` fresh-session save failure is preserved. |
| Editor browser flow | Native create saved v1. The bounded continuation completed reopen, refresh, full scientific-field revision, winning revision, stale 409, missing-reference 404, exact history/pins, escaping, 375px layout and Home return. Four continuation POSTs returned 303/303/409/404, appending only v2/v3 to the owned record. | Raw continuation result remains **12 PASS / 1 FAIL, exit 1**. Only the hidden idempotency key changed after the confirmed 409; required owned input remained. Test and Director accepted the required behavior under the pre-execution contract interpretation. Unknown-outcome replay still requires the original key. |

The bounded HTTP evidence is preserved in `verification/rms-hn-live-editor-only-df53c2bb-operator/result/summary.json`. Test's original independent report and case matrix are in `verification/rms-hn-live-review-cee6b6e9/`. The rollback probe source, exact output, receipt and original manifest are in `verification/rms-hn-history-guard-20261003/`; its independent review is in `verification/rms-hn-guard-independent-5851e91e/`.

Original reports are historical and unedited. Their earlier pending prerequisites must be read together with these later executed results and attributed scope decisions. Complete source packets and receiving receipts also remain attached to MAU-140/144 in Paperclip.

The original 529 checker timeout is preserved in `verification/rms-hn-browser-529e638-operator/`. It did not mean that no save occurred. The continuation used the exact saved v1 and did not recreate it. Actual continuation evidence, including five screenshots, is in `verification/rms-hn-browser-continuation-63e82628/`.

## Independent recommendation and Director verdict

- **Independent Test**, run `5b545015-2b23-4b2a-af16-4fd9d85ac50d`: reasonable confidence for the founder-narrowed development merge; no demonstrated blocking product defect in the focused evidence. [Original final report](verification/rms-hn-final-closeout-5b545015/report.md) and its complete 71-file packet are preserved with all 70 indexed file sizes/hashes verified. The raw failure and broader incomplete acceptance remain unchanged.
- **Director**, run `4d6948c7-1455-4c5a-a201-b5072c043126`: **ACCEPTED FOR THE FOUNDER-NARROWED DEVELOPMENT MERGE**, exact product `529e638` / tree `5b98b0b2`. [Original named-build verdict](verification/RMS-HN-DEVELOPMENT-MERGE-VERDICT-529e638-4d6948c7.md). No additional tests, readiness approval or deployment requested.
- Backend MAU-142 and Frontend MAU-143 source deliverables were reconciled to native Approved/Done using their existing reviews. Operations MAU-141 remains Done. No builder or completed Source/Idea milestone was restarted.
- The publication successor adds only documentation and preserved verification artifacts. Every path tracked in tested product 529 is unchanged; staging keeps identifying 529 as the installed product. Actual GitHub merge identity is recorded after the merge in the PR and Paperclip closeout.

## Explicit development limitations

- True simultaneous database transaction overlap was not demonstrated by the observer, despite overlapping HTTP requests and correct winner/loser responses.
- Database least privilege and privileged-administrator resistance were not established.
- The empty external-reference table could not supply an existing row for the rollback-only probe.
- Broader original acceptance permutations remain incomplete as recorded by independent Test. No PASS replaces an unexecuted case or an original dissent.
- GitHub merge and application deployment remain distinct. Staging continues to identify the actual deployed product commit.

## Proposed next increment — definition only

Consider versioned **Test Plan drafts**, each pinned to an exact Hypothesis version. A small scope would cover the planned sample/universe/time period, evaluation benchmark, cost assumptions, metrics, and success/failure/stopping criteria, with create, revise, history and navigation.

This proposal does not authorize implementation, market-data connections, backtests, strategy execution or research approval. Agree on a short design contract and a focused acceptance list before starting.
