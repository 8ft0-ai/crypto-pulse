# Reliable hourly source ingestion — proposed design (#564)

**Status:** proposed; documentation only. **Owner:** [Crypto Pulse #564](https://github.com/8ft0-ai/crypto-pulse/issues/564). **Publication authority:** [#561](https://github.com/8ft0-ai/crypto-pulse/issues/561).

## Outcome and decision

Deliver dependable source ingestion for each UTC hour, without a permanent host, duplicate data-collection implementation, automatic report publication or additional tracking issues. **Preferred design:** one Cloudflare Workers Cron Trigger at **minute 07 UTC** (`7 * * * *`) invokes the existing GitHub Actions `Ingest Crypto Sources` workflow using a repository-restricted credential. GitHub remains responsible for fetching, source validation and immutable evidence. Report generation, protected-main merges and GitHub Pages deployment remain separately controlled under #561.

This is a design proposal, not a claim that Cloudflare or a seven-day reliability target has been proved, and it does not authorise provisioning, changing credentials, changing workflows, cutover or publication.

## Observed baseline and limits

- On 3 November 2026, 24 successful **scheduled** ingestions spanned approximately 134.8 hours; consecutive observed gaps ranged from 3.58 to 9.82 hours, median 5.95 hours. These are intervals **between successful runs**, not a measured per-trigger failure rate. The reason individual schedule events were absent is unproven.
- Current `.github/workflows/ingest-crypto-sources.yml` has `schedule: "17 * * * *"` and `workflow_dispatch`, and the `crypto-source-ingestion` concurrency group with `cancel-in-progress: false`. It generates timestamped snapshots under `data/crypto/hourly`, validates snapshot quality and the canonical UTC hour, creates an immutable source-intent artifact, and updates rolling snapshot PR [#178](https://github.com/8ft0-ai/crypto-pulse/pull/178).
- Successful genuine scheduled ingestion [#1111](https://github.com/8ft0-ai/crypto-pulse/actions/runs/41661049245) triggered deterministic-publication generation [#617](https://github.com/8ft0-ai/crypto-pulse/actions/runs/41661126040), which led to merged [PR #563](https://github.com/8ft0-ai/crypto-pulse/pull/563) and a successful Pages workflow. This does **not** itself conclude all of #561's operational acceptance checks.
- One authorised smoke-test `workflow_dispatch`, [ingestion #1113](https://github.com/8ft0-ai/crypto-pulse/actions/runs/41724015748) on protected main `6b73f1d6592547c46189df37bd9f0af0f293bbef`, completed successfully: source fetch, snapshot validation (`valid-ok`), observation-hour validation, immutable artifact upload and rolling PR update. Its publication follower [#619](https://github.com/8ft0-ai/crypto-pulse/actions/runs/41724133040) was skipped, and protected main did not change. This proves the dispatch execution path **once**, not reliable scheduling or duplicate-hour prevention.
- #1112 and #1113 both ran in the **21:00 UTC observation hour on 3 November**. The present implementation validates that the observation hour matches the **actual** capture timestamp; it does not yet prove unique accepted hours across workflow runs. No acceptance criterion may treat these two executions as two successful hourly slots.
- Rolling PR #178 is a mutable inspection surface, **not** trusted publication authority or a substitute for immutable source intent. Its update currently contributes to overall job success; decoupling it must not remove the snapshot commit and source-intent provenance needed by deterministic publication.

## Options considered

| Option | Change | Assessment |
| --- | --- | --- |
| Retain GitHub `17 * * * *` | None | Already demonstrates unacceptable multi-hour intervals; no dependable delivery claim. |
| Move the GitHub schedule minute | One-line edit | A useful cheap experiment but does not eliminate GitHub's best-effort scheduled-event dependency. |
| Independent hourly trigger | Small Cloudflare Worker, authenticated GitHub dispatch, focused workflow changes | **Preferred**: separates clock delivery from ingestion while reusing validated source collection. Adds a credential, an external service and a new correlation boundary; must be tested. |

Cloudflare's scheduled handler exposes `scheduledTime` (UTC milliseconds). Use that value, **not Worker start time**, to identify the requested slot. Free-tier operation is expected to cost approximately A$0 at 24 dispatches/day if account quotas allow; check actual account capacity, GitHub Actions usage, logging retention and any pricing changes before activation. A Google Cloud Scheduler direct-HTTP design remains a fallback if the Cloudflare credential/operations model proves unsuitable. Neither removes GitHub Actions execution or third-party API failure risk.

## Proposed execution path

```text
Cloudflare scheduled()  [UTC: 7 * * * *]
  -> derive intended_hour_utc from controller.scheduledTime (e.g. 10:00Z)
  -> authenticated dispatch of the existing GitHub ingestion workflow on main
  -> resolve dispatch to GitHub run ID and run attempt
  -> validate intended hour, actual capture time, source quality, uniqueness
  -> retain snapshot commit, validated source-intent artifact and receipts
  -> optional best-effort rolling PR #178 refresh (non-authoritative)
  -> separately governed #561 publication eligibility (not enabled by #564)
  -> only eligible report merge to protected main triggers Pages
```

**Proposed minimal change set (future authorisation required):**

1. **Cloudflare:** one small JavaScript Worker with only a `scheduled()` handler and one UTC Cron Trigger `7 * * * *`. It holds a secret GitHub credential and hard-codes the repository, target workflow and `main` ref; it must not accept an arbitrary workflow, branch or URL from external input. Log intended slot, attempt, dispatch outcome and non-secret correlation ID. No permanent host, database or secondary ingester.
2. **Existing workflow:** add validated `workflow_dispatch` inputs such as `intended_hour_utc` and `dispatch_correlation_id`. Preserve existing `schedule` compatibility until controlled cutover. For externally dispatched runs require canonical `YYYY-MM-DDTHH:00:00Z`, UTC, expected schedule alignment and a capture timestamp truly inside that intended hour; never backdate or substitute data from another hour. Validate source quality and observation hour through the existing scripts.
3. **Authoritative acceptance:** use the existing serialised ingestion execution and receipt/artifact evidence to enforce one **accepted** result per intended UTC hour. Before marking an hour accepted, reconcile prior runs and retained acceptance evidence for that hour; make the acceptance action race-safe within the serialised workflow. The existing per-run intent artifact is not by itself a per-hour uniqueness lock. Define and test the exact receipt/locking implementation before activation, including rejected duplicate attempts, pending-run cancellation and same-hour retries; do not add a database merely for a ledger.
4. **Preserve publication provenance:** retain the real snapshot bytes, their commit SHA, source validation and immutable source-intent artifact. Make rolling-PR update a **non-critical inspection step only after** success evidence is durable, so a PR API failure does not turn valid ingestion into failure. Keep the rolling branch and PR until equivalence of the publication source contract is verified; its force-updated history is not an archive.
5. **Publication isolation:** an externally dispatched ingestion is not automatically eligible for report publication. #561 must explicitly verify that `workflow_run` event provenance, pilot selector and future `recurring` mode cannot authorise a dispatched run inadvertently. The current publication-generation flow includes `schedule|workflow_dispatch` as recognised source-event types, and its recurring path needs separate policy review before being enabled. No changes to App permissions, protected-main gates, exact-head CI, v3 attestation, source quality refusal, Pages or demo/non-advice wording under #564.

## Authentication, retries and failure modes

Use a dedicated fine-grained GitHub credential restricted to this repository with the minimum Actions write access required for workflow dispatch. Do **not** repurpose the publication GitHub App token or grant new App permissions. Store the credential in Cloudflare's encrypted secret facility, omit it from all logs, apply expiry/rotation and scope checks, and ensure the Worker can invoke **only** the intended workflow/ref in its own code. GitHub's Actions write permission is not restricted to a single workflow; account for that residual privilege explicitly.

A successful HTTP dispatch means **accepted for execution**, not validated ingestion. Link it to an actual GitHub run (using a returned run ID when available, otherwise the correlation input and run evidence) and follow through to the immutable source artifact, quality, accepted hour and PR/publication state.

Use at most **one bounded retry** after confirmed non-acceptance or a retriable failure, within the intended-hour deadline. If a timeout/HTTP error leaves dispatch acceptance ambiguous, query GitHub and reconcile the correlation ID before retrying. Never use an unbounded loop, duplicate `workflow_dispatch` to compensate for unavailable receipts, or hidden historical catch-up. Missing, delayed, failed, skipped and duplicate-rejected hours must remain visible.

Expected failure classes include Cloudflare missed/delayed trigger, expired or over-privileged credentials, GitHub API throttling/ambiguous acceptance, runner queue delays, upstream source API errors, insufficient source quality, per-hour collision, rolling-PR write failure and publication-policy drift. Each requires a distinct non-secret receipt and a fail-closed outcome.

## Seven-day operational acceptance

Freeze the first intended UTC slot **before** testing. Observe **168 consecutive hourly slots**. Trigger at `:07`; count a slot as successful only when its validated `valid-ok` source evidence and unique accepted UTC hour are complete by `:30` of that hour (23 minutes from the nominal trigger), with no synthetic timestamp or backfill.

| Gate | Required proof |
| --- | --- |
| Delivery | At least **160 of 168** distinct expected slots (at least 95%) have a validated, accepted ingestion within the frozen deadline. |
| Identity | Exactly one accepted snapshot per intended hour; zero duplicate accepted hours, including after retries. |
| Correlation | Per-slot evidence links intended UTC hour, scheduler receipt, dispatch result, GitHub run ID/attempt, snapshot identity, validation/quality and final acceptance. |
| Failures | Missed, delayed, queued, failed, refused and duplicate-rejected outcomes are distinguishable; count timeouts as failures unless reconciled. |
| Security | Repository-scoped secret, no credential exposure, bounded retry, independent account/permission check and credential revocation plan. |
| Publication | No unintended report PR, protected-main merge, Pages deployment or recurring-publication activation; preserve #561's separate authority. |
| Rollback | Demonstrated ability to disable Cloudflare, reconcile in-flight runs and restore **only one** scheduling mechanism. |
| Costs | Record actual Cloudflare requests and GitHub Actions usage; verify within owner-approved cost boundary. |

Cloudflare Free Worker logs are presently retained for about **three days**; export or independently capture relevant receipts during the seven-day test (e.g. on days 2, 4, 6 and 7), then reconcile against GitHub runs/artifacts. No additional always-on monitoring service is required for the trial. Monitor the success of **validated ingestion**, not merely Cron trigger or HTTP invocation status.

## Cutover and rollback sequence (not authorised by this document)

1. Reconcile #561's genuine scheduled pilot #1111, resulting publication and Pages checks to a documented terminal state; verify current publication variables and all in-flight candidates. Do **not** modify or reselect the pilot as part of #564.
2. Separately approve and review the focused repository safeguards, credential boundary and Cloudflare configuration. Test offline and in a bounded no-publication preflight before live activation.
3. Confirm an off-switch, receipt capture and unique accepted-hour handling. Disable GitHub's `17 * * * *` schedule and activate exactly one Cloudflare `:07` trigger in a controlled change window; avoid competing primary schedulers.
4. Run the seven-day acceptance, refuse the operational GO if any mandatory hard gate fails, and record the actual evidence in #564. Retain the disabled mechanism as a rollback option.
5. If cutover fails: disable Cloudflare, reconcile pending/ambiguous GitHub work, restore the original GitHub schedule and verify no duplicate primary trigger remains. Do not silently enable report publication.

## Scope and completion boundary

This design does **not** include implementation, scheduler activation, secrets, historical ingestion, backfill, public report publication, automatic recurring mode, new infrastructure beyond the proposed serverless trigger, new tracking issues, Phase 18 revival, model/LLM work, or a merger of #561 and #564.

Issue #564 remains **open** until seven-day reliability and rollback acceptance are actually verified. This document may be merged independently as a design record; merging it is **not** permission to deploy or close #564.

## Evidence and documentation

- [Governing scheduling issue #564](https://github.com/8ft0-ai/crypto-pulse/issues/564)
- [Separate publication authority #561](https://github.com/8ft0-ai/crypto-pulse/issues/561)
- [Successful external-dispatch smoke test #1113](https://github.com/8ft0-ai/crypto-pulse/actions/runs/41724015748)
- [Real scheduled ingestion #1111](https://github.com/8ft0-ai/crypto-pulse/actions/runs/41661049245)
- [Existing ingestion workflow](../../.github/workflows/ingest-crypto-sources.yml)
- [Observation-hour validator](../../scripts/validate_crypto_observation_hour.py)
- [Cloudflare Cron Triggers documentation](https://developers.cloudflare.com/workers/configuration/cron-triggers/)
- [Cloudflare scheduled-handler event properties](https://developers.cloudflare.com/workers/runtime-apis/handlers/scheduled/)
