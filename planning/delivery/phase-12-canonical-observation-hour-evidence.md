# Phase 12 — Canonical observation-hour evidence

Status: complete.

Primary outcome: future CryptoPulse source snapshots now retain the actual generation/fetch timestamps while carrying a separately validated canonical UTC observation-hour identity that can serve as explicit cadence evidence for later, separately governed consumers.

## Governance

```text
Discovery issue: #430
Shaping/design issue: #431
Exact design: #431 comment 5305448538
Substantive design approval: #431 comment 5305450450
Roadmap promotion: #432 / PR #435
Roadmap merge: f616f1721ad2a5f93e9deb741ef82583665d1341
Parent delivery-control issue: #436
Approved implementation plan: #436 comment 5305485934
Close-out issue: #441
Contract: phase12-observation-hour/v1
```

The design was frozen before implementation. Delivery remained additive: historical snapshots, the pinned Phase 10 snapshot validator/config and all Phase 10/11 comparison/temporal semantics were left unchanged.

## Delivered slices

```text
Slice 1 issue: #437
Slice 1 PR: #438
Slice 1 reviewed head: b452882ae9a435a7b5e8f6e15aa35c25e41dcf0e
Slice 1 validation: 31924056018
Slice 1 substantive approval: #437 comment 5305522624
Slice 1 merge authority: #437 comment 5305523149
Slice 1 merge: 188d2c824e7bca30fdfd2ee6e1ab36006d314a6c

Slice 2 issue: #439
Slice 2 PR: #440
Slice 2 reviewed head: 15168bafd5b777ad3c33988cad85620fbc5b99d9
Slice 2 validation: 31924356028
Slice 2 substantive approval: #439 comment 5305545914
Slice 2 merge authority: #439 comment 5305546386
Slice 2 merge: cb251970eb671d39cfcb8650b03b8fa55f6dfa23
```

Both implementation candidates passed repository-wide integration tests, full unit tests, documentation validation, `_site/` exclusion, static-site build and expected artefact verification before merge.

## Shipped observation-hour contract

New future snapshots keep source schema `0.2` and add:

```text
run.observation_hour_utc
```

under the versioned boundary:

```text
phase12-observation-hour/v1
```

The field is exactly the UTC hour containing the actual `run.generated_at_utc`:

```text
actual generated_at_utc -> UTC -> minute/second/microsecond = 0 -> YYYY-MM-DDTHH:00:00Z
```

There is no nearest-hour rounding, schedule-time inference, tolerance, filesystem-time input or backfill. `run.generated_at_utc` remains the actual generation timestamp and source `fetched_at_utc` evidence remains unchanged.

The ingestion implementation adds only one pure containing-hour helper and one `run.observation_hour_utc` field to new snapshots. Snapshot path naming, local generation metadata, source fetching, source status, quality classification and schema version remain unchanged.

## Separate fail-closed validation

`scripts/validate_crypto_observation_hour.py` owns the new Phase 12 semantics separately from the frozen snapshot validator.

It first requires the snapshot to pass the existing `scripts/validate_crypto_snapshot.py` path, then requires:

- `run.observation_hour_utc` to be present;
- exact canonical `YYYY-MM-DDTHH:00:00Z` syntax;
- a valid timestamp;
- exact equality with the containing UTC hour recomputed only from `run.generated_at_utc`.

Missing, malformed, non-canonical or mismatched identity fails closed. Validation is deterministic and network-free.

Legacy schema-`0.2` snapshots without the field remain valid under the frozen snapshot validator but are not Phase-12 slot-ready evidence.

Regression proof pins the frozen identities unchanged:

```text
scripts/validate_crypto_snapshot.py blob: b8c7fcc850bf0f5076f7d084bb6be9c24a9b7d3a
config/crypto_sources.yml blob:          73c5a3f3db81954951801c7d348d09a4c6296d73
```

## Rolling-ingestion enforcement

The existing scheduled/manual ingestion workflow now requires this order:

```text
Fetch source data
Validate source snapshot
Validate observation hour
Build PR evidence
Inspect generated snapshot changes
Create rolling automation branch
Commit generated snapshot
Push rolling automation branch
Create or update rolling snapshot PR
```

The Phase 12 validator therefore runs before reviewer evidence and before any branch, commit, push or pull-request mutation.

Rolling PR evidence exposes both:

```text
actual generated_at_utc
containing observation_hour_utc
```

and explicitly states that the observation hour is the canonical containing evidence bucket, not the exact capture time.

The existing `17 * * * *` schedule, `workflow_dispatch`, stable rolling branch/PR, force-with-lease update model, snapshot-only commit scope, no-auto-merge, no-report and no-LLM boundaries are preserved.

## Missing, duplicate and delayed observations

Phase 12 establishes identity only. It does not choose or repair observations.

```text
no slot-ready observation in an hour -> future consumer must expose missing evidence
multiple observations in one hour   -> future consumer must expose ambiguity unless separately governed
delayed execution into later hour   -> observation belongs to the later actual execution hour
```

No winner, fallback, carry-forward, interpolation, backfill or historical timestamp rewrite is introduced.

## Frozen Phase 10/11 boundary

Phase 12 does not alter or reinterpret:

```text
phase10-predecessor-exact-hour/v1
crypto-snapshot-comparison/v1
crypto-temporal-series/v1
phase11-temporal-visualisation/v1
```

Phase 10 still orders and measures predecessors using actual `run.generated_at_utc` and requires exactly `3,600` elapsed seconds. Phase 11 still consumes that frozen comparison evidence under its exact-hour contract.

Consequently, `phase12-observation-hour/v1` does not itself create a live hourly comparison or temporal pipeline. A later consumer that uses observation-hour identity requires a new separately reviewed versioned contract.

## Boundaries preserved

Phase 12 did not change or authorise:

- historical snapshot paths or bytes;
- the frozen Phase 10 snapshot validator/config blobs;
- Phase 10 predecessor/comparison semantics;
- Phase 11 series/renderer semantics;
- deterministic selector behaviour;
- provider/model or credential behaviour;
- report generation or report/site rendering;
- automatic report generation or publication;
- auto-merge;
- public temporal charts or visual market cards;
- generated `_site/` output;
- sentiment, forecasting, causality, technical levels, targets, watchlists or trading guidance.

## Delivery graph disposition

Phase 12 changes the active source-evidence ingestion path and establishes an enduring observation-hour evidence boundary that future phases may depend on. Under `planning/delivery/graph-modelling-rules.md`, the compact causal graph is therefore updated rather than marked N/A.

The graph adds only the Phase 12 phase, its governing parent issue, one representative proof PR, the committed observation-hour validator artefact and the enduring observation-hour boundary. It does not inventory every implementation issue, PR, CI run or future generated snapshot.

## Carry-forward

Phase 12 is complete as an operational evidence prerequisite only.

A future shaping gate may decide whether to define a new observation-hour comparison/temporal consumer. Public/site integration of the proven Phase 11 renderer remains parked until such a consumer is independently specified, proved and authorised.

No successor phase is selected or authorised by this close-out.
