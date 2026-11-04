# CryptoPulse hourly ingestion trigger (#564)

**Status: repository implementation only — NOT DEPLOYED.** This directory does not authorise
Cloudflare provisioning, a GitHub credential, disabling the existing GitHub schedule, or
changing publication activation. Issue #561 independently governs recurring public reports.

## Runtime contract

- One Worker, **scheduled handler only**; `wrangler.toml` declares `7 * * * *` UTC.
- The slot derives from Cloudflare's `scheduledTime`, not handler arrival time. Expired
  (`>= :30`), early or malformed events do not dispatch.
- `GITHUB_DISPATCH_TOKEN` must be a dedicated, repository-restricted GitHub credential
  with only the minimum Actions-write access needed for workflow dispatch. It is an
  encrypted Cloudflare secret; it must never be committed, displayed or logged.
- Requests are hard-coded to `8ft0-ai/crypto-pulse`,
  `ingest-crypto-sources.yml`, ref `main`, and exact two-input payload.
- One POST only. Timeout or uncertain acceptance is **not retried**; this is deliberate
  fail-closed behaviour and may reduce measured delivery reliability. A successful HTTP
  204 proves dispatch acceptance only, not validated ingestion.
- A bounded run-list lookup can attach a unique contemporary run ID. Otherwise the receipt
  remains `dispatch-accepted-run-pending`, to be reconciled after the event. It must never
  trigger a second dispatch.
- Existing workflow concurrency serialises hour checks; a per-hour Actions artifact named
  `crypto-hour-accepted-YYYYMMDDTHH` is emitted **only after** `valid-ok` validation,
  matching capture time, snapshot commit, immutable publication-intent upload and successful
  rolling-branch push. A duplicate, ambiguous or incomplete artifact read fails closed.
- Rolling PR editing is best-effort after source provenance is durable; its outcome is
  recorded in the acceptance receipt. It is **not** publication authority.
- Externally dispatched ingestion is explicitly excluded by the deterministic-publication
  workflow's source-event gate. The former one-shot pilot and GitHub schedule remain
  unchanged until separately authorised.

## Pre-activation verification

```sh
node --test workers/hourly-ingestion/worker.test.mjs
./tools/dev/cp-dev check
```

Verify current #561 pilot state, one primary scheduler, the dedicated GitHub token's
repository scope, Cloudflare account/Free quota, log retention, GitHub Actions usage, off-switch
and no secret exposure before separately authorising deployment or cutover. Do not run a live
dispatch just to test a source-only PR.

## Seven-day operational acceptance — not started

Freeze the **first** intended UTC hour before enabling the trigger; observe the next **168
consecutive slots**. Every slot begins at `:07`; count it on time only if a **unique**
`valid-ok` acceptance artifact has been uploaded by **:30** UTC of that hour. Use the
GitHub artifact's server `created_at` timestamp as the final acceptance time, **not** the
receipt's earlier `receipt_prepared_at_utc` value.

For each slot, reconcile the Cloudflare log record (`intended_hour_utc`,
`correlation_id`, outcome), a GitHub workflow run ID and attempt (including failed,
cancelled and queued runs), its immutable source-intent identity and the accepted-hour
artifact's JSON and server timestamp. Verify the snapshot bytes' SHA-256, snapshot commit,
source quality and source observation hour. Do not count HTTP 204, an unreconciled run,
a retry, a rolling PR, a degraded snapshot or later backfill as an on-time accepted hour.

Pass criteria: **at least 160 of 168** expected hours accepted by the deadline, **zero**
duplicate accepted hours; distinguish missed, delayed, refused, failed, cancelled and
ambiguous outcomes. Preserve and export Cloudflare logs before they expire (target days 2,
4, 6 and 7), reconcile GitHub workflow/artifact receipts, verify no unintended publication,
and record actual cost, permissions and failure receipts.

Rollback only with separate authority: stop Cloudflare Cron, reconcile ambiguous/in-flight
runs, restore the original GitHub schedule if needed, and verify only one primary scheduler.
Keep #564 open until all seven-day and rollback gates have actual evidence. This repository
change alone is neither a successful cutover nor an accepted publication service.
