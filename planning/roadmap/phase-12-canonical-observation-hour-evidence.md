# Phase 12 — Canonical observation-hour evidence

Status: complete.

Shaping issue: #431

Discovery blocker: #430 comment `5305436569`

Accepted design proposal: #431 comment `5305448538`

Substantive design approval: #431 comment `5305450450`

Roadmap-promotion authority: #431 comment `5305450958`

Trusted design base: `48b027ab8c5d1cff8a30b2ef72236f74c9dff915`

Delivery control: #436

Close-out issue: #441

Delivery record: `planning/delivery/phase-12-canonical-observation-hour-evidence.md`

This roadmap specification records the completed `phase12-observation-hour/v1` direction. Implementation was delivered under the separately reviewed three-slice plan on #436. Phase 12 establishes truthful future-snapshot observation-hour identity only; it does not reinterpret frozen Phase 10/11 semantics or authorise a comparison/temporal consumer, public-site integration, provider/model use, credentials, auto-merge or generated `_site/` changes.

## Problem statement

CryptoPulse source snapshots preserve the actual execution time in `run.generated_at_utc`. The current scheduled ingestion runs during an hour rather than exactly on the UTC-hour boundary, and real repository snapshots therefore carry timestamps such as `2026-07-10T08:44:26Z`.

The frozen Phase 10 predecessor contract orders and measures snapshots by that actual timestamp and accepts exactly `3,600` elapsed seconds. The frozen Phase 11 temporal-series contract requests exact UTC-hour slots and indexes current candidates by exact `run.generated_at_utc` equality. Those contracts are intentionally strict and were not weakened or reinterpreted merely to make operational data look hourly.

Phase 12 therefore adds an explicit cadence-bucket identity for future snapshots that says which UTC observation hour contains the real generation time while retaining the real generation/fetch timestamps unchanged.

## Goal

Phase 12 delivers a small additive operational evidence contract in which future source snapshots can carry:

```text
run.observation_hour_utc
```

under:

```text
phase12-observation-hour/v1
```

The field is deterministic, independently validated and truthful: it identifies the UTC hour containing the actual `run.generated_at_utc`; it is not a claim that collection occurred at the hour boundary.

Future snapshots can now be classified as slot-ready evidence without changing historical snapshots, the pinned Phase 10 validator/config identities, or any frozen Phase 10/11 time/comparison/rendering semantics.

## Non-goals

Phase 12 does not authorise or deliver:

- reinterpretation of `run.generated_at_utc`;
- rounding or rewriting historical timestamps;
- historical snapshot backfill, rename or regeneration;
- changes to `phase10-predecessor-exact-hour/v1`;
- changes to `crypto-snapshot-comparison/v1`;
- changes to `crypto-temporal-series/v1` or `phase11-temporal-visualisation/v1`;
- a winner-selection rule for duplicate observations in one hour;
- tolerance-based predecessor matching, fallback, carry-forward or interpolation;
- public/site temporal charts or visual market cards;
- report-generation or publication changes;
- model/provider selection or invocation;
- credentials or paid API use;
- auto-merge or automatic report generation;
- committed generated `_site/` output;
- sentiment, forecasting, causality, technical levels, targets, watchlists or trading guidance.

## Frozen observation-hour contract

### Identity

`run.observation_hour_utc` uses exactly this canonical representation:

```text
YYYY-MM-DDTHH:00:00Z
```

It is the UTC hour containing the actual snapshot generation time.

### Derivation

For the already-determined snapshot generation timestamp:

1. parse the timezone-aware `run.generated_at_utc`;
2. convert it to UTC;
3. set minute, second and microsecond to zero;
4. serialise using the canonical `Z` form.

Examples:

```text
2026-07-10T08:00:00Z       -> 2026-07-10T08:00:00Z
2026-07-10T08:17:45Z       -> 2026-07-10T08:00:00Z
2026-07-10T08:59:59Z       -> 2026-07-10T08:00:00Z
2026-07-10T09:00:00Z       -> 2026-07-10T09:00:00Z
2026-07-10T19:17:45+10:00  -> 2026-07-10T09:00:00Z
```

There is no nearest-hour rounding, tolerance, intended-schedule inference, filesystem-time input or workflow-event-time input.

`run.generated_at_utc` remains the exact actual generation time. Existing source `fetched_at_utc` evidence remains unchanged.

## Snapshot compatibility and frozen Phase 10 binding

The new field is an additive metadata extension to source snapshot schema `0.2`.

The existing frozen snapshot validator requires a defined subset of `run` keys and permits additional metadata. The Phase 10 semantic gate continues to require schema `0.2`, cadence `hourly`, the existing producer and closed asset/stablecoin/source identities; it does not assign new meaning to additional `run` metadata.

Phase 12 did not modify:

```text
scripts/validate_crypto_snapshot.py
config/crypto_sources.yml
```

Their frozen Git blob identities remain part of the Phase 10/11 immutable contract.

A legacy `0.2` snapshot without `run.observation_hour_utc` remains a valid legacy snapshot under the frozen validator, but it is not `phase12-observation-hour/v1` slot-ready evidence.

## Separate fail-closed validation

Phase 12 owns its new semantics in `scripts/validate_crypto_observation_hour.py` rather than changing the frozen snapshot validator.

The Phase 12 validator first requires ordinary snapshot validity under the existing validator/config path, then requires:

- `run.observation_hour_utc` is present;
- canonical UTC-hour syntax is exact;
- the value equals the containing UTC hour recomputed solely from `run.generated_at_utc`;
- malformed, missing or inconsistent identity fails closed.

Validation is deterministic and network-free. Branch names, wall clock, filesystem metadata, process identity and nominal cron occurrence are not evidence inputs.

## Scheduled and manual execution semantics

Scheduled and manual ingestion derive the observation hour from the same actual generation timestamp used to build the snapshot.

The existing `--now` override remains the deterministic test seam. Offset-aware timestamps are normalised to UTC before deriving the observation hour; accepted `--now` behaviour is not repurposed into a schedule-time claim.

The existing cron remains unchanged. If a delayed execution crosses an hour boundary, it belongs to the later hour in which it actually executed.

## Missing, duplicate and delayed observations

This phase establishes identity only; it does not select or repair observations.

```text
no slot-ready snapshot for an hour -> missing evidence for a future consumer
multiple snapshots in one hour     -> ambiguous evidence for a future consumer
delayed execution into later hour  -> belongs to later actual execution hour
```

There is no fallback to an older observation and no silent winner selection.

## Boundary with Phase 10 and Phase 11

Phase 10 v1 continues to use actual `run.generated_at_utc` and still requires exactly `3,600` elapsed seconds. Runtime jitter can therefore make two consecutive observation-hour snapshots fail the frozen Phase 10 predecessor interval even when their observation-hour identities are adjacent.

Accordingly, `phase12-observation-hour/v1` does **not** make Phase 10/11 v1 a live hourly temporal pipeline.

Any later comparison or temporal consumer that uses `run.observation_hour_utc` as cadence identity requires a new separately reviewed versioned contract. That future contract may reuse the proven fail-closed, immutable-provenance and explicit-gap principles from Phase 10/11, but it may not silently substitute observation-hour adjacency for frozen actual-time semantics.

Public/site integration remains parked behind that later consumer contract.

## Delivered workflow

The completed evidence path is:

```text
actual generation timestamp
        |
        +-> ordinary source snapshot fields and fetched_at evidence
        |
        +-> deterministic containing observation_hour_utc
                       |
                       v
             frozen snapshot validation
                       |
                       v
             Phase 12 slot validator
                       |
                       v
                PR evidence
                       |
                       v
              rolling snapshot PR
```

The Phase 12 validator runs before PR evidence and before branch, commit, push or PR mutation.

A later separately governed consumer may use only validated slot-ready evidence under its own versioned semantics.

## Acceptance gates

- [x] Future ingestion deterministically emits canonical `run.observation_hour_utc` from the actual generation timestamp.
- [x] Actual `run.generated_at_utc` remains unrounded and independently visible.
- [x] Existing source fetch timestamps remain unchanged.
- [x] A separate Phase 12 validator rejects missing, malformed, non-canonical or mismatched observation-hour identity.
- [x] Legacy snapshots continue to pass the frozen snapshot validator but are not classified as Phase-12 slot-ready.
- [x] The frozen Phase 10 snapshot-validator and config Git blob identities remain unchanged.
- [x] Exact boundary, mid-hour, end-of-hour and offset-normalisation cases are proved deterministically.
- [x] Duplicate/missing/delayed observation semantics remain explicit with no winner/fallback rule.
- [x] No historical snapshot path or byte is changed.
- [x] Rolling workflow evidence exposes both actual generation time and observation hour before a slot-ready snapshot PR can proceed.
- [x] Repository-wide exact-head validation succeeded for every implementation candidate.
- [x] No Phase 10/11 semantic, site/publication, model/provider, credential or `_site/` change occurred.

## Delivered implementation surface

Phase 12 implementation changed only:

```text
scripts/ingest_crypto_sources.py
scripts/validate_crypto_observation_hour.py
.github/workflows/ingest-crypto-sources.yml
tests/test_ingest_crypto_sources.py
tests/test_validate_crypto_observation_hour.py
tests/test_ingest_crypto_sources_workflow.py
```

No frozen Phase 10/11 file, historical snapshot, report/site path or broader workflow surface was changed.

## Delivered slices

The accepted three-slice plan in #436 comment `5305485934` delivered:

```text
1. observation-hour derivation + separate validator
   PR #438
   validation 31924056018
   merge 188d2c824e7bca30fdfd2ee6e1ab36006d314a6c

2. rolling-ingestion workflow evidence and enforcement
   PR #440
   validation 31924356028
   merge cb251970eb671d39cfcb8650b03b8fa55f6dfa23

3. Phase 12 close-out and causal-graph reconciliation
   close-out issue #441
```

Each implementation candidate passed exact-head repository validation and fresh substantive review before separate merge authority.

## Risks and mitigations

### Risk: bucket identity is mistaken for capture time

Mitigation: preserve actual `generated_at_utc` and fetched timestamps, use explicit `observation_hour_utc` naming, and require workflow evidence to display both.

### Risk: Phase 12 silently changes Phase 10/11 semantics

Mitigation: leave the frozen validator/config and Phase 10/11 implementation untouched; require a separate versioned future consumer for observation-hour semantics.

### Risk: delayed or duplicate runs are hidden

Mitigation: derive from actual execution time and define no winner, fallback or repair rule in Phase 12.

### Risk: historical evidence is normalised retrospectively

Mitigation: prohibit historical snapshot edits/backfill. Only newly generated slot-ready snapshots carry the new field.

### Risk: Phase 12 expands into public charts

Mitigation: keep site/publication integration explicitly parked until a later consumer contract proves operational observation-hour comparison semantics.

## Definition of done

Phase 12 is complete:

- [x] a separately authorised delivery-control issue adopted the accepted `phase12-observation-hour/v1` design without relaxation;
- [x] bounded implementation work merged after exact-head validation and fresh review;
- [x] deterministic proof covers the accepted derivation and fail-closed validation cases;
- [x] actual timing evidence and historical snapshots remain unchanged;
- [x] frozen Phase 10/11 validator/config and evidence contracts remain unchanged;
- [x] rolling workflow evidence proves slot-ready snapshots before PR publication;
- [x] public/site temporal integration remains unimplemented and separately governed;
- [x] close-out delivery records and roadmap state are reconciled;
- [x] the delivery graph is updated because Phase 12 changes the active source-evidence dependency story;
- [x] generated `_site/` output is not committed.

## Follow-on boundary

A separate shaping gate may decide whether a new observation-hour comparison/temporal contract is justified. Only after that consumer is independently proven may public/site temporal integration be reconsidered.

No successor phase is selected or authorised by Phase 12 close-out.
