# Phase 12 — Canonical observation-hour evidence

Status: shaping; design accepted, implementation separately gated.

Shaping issue: #431

Discovery blocker: #430 comment `5305436569`

Accepted design proposal: #431 comment `5305448538`

Substantive design approval: #431 comment `5305450450`

Roadmap-promotion authority: #431 comment `5305450958`

Trusted design base: `48b027ab8c5d1cff8a30b2ef72236f74c9dff915`

This is a forward-looking roadmap specification. It promotes the reviewed `phase12-observation-hour/v1` design into the roadmap only. It does not authorise implementation, source-snapshot mutation, a new comparison/temporal consumer, public-site integration, publication changes, provider/model use, credentials, auto-merge or generated `_site/` changes.

## Problem statement

CryptoPulse source snapshots preserve the actual execution time in `run.generated_at_utc`. The current scheduled ingestion runs during an hour rather than exactly on the UTC-hour boundary, and real repository snapshots therefore carry timestamps such as `2026-07-10T08:44:26Z`.

The frozen Phase 10 predecessor contract orders and measures snapshots by that actual timestamp and accepts exactly `3,600` elapsed seconds. The frozen Phase 11 temporal-series contract requests exact UTC-hour slots and indexes current candidates by exact `run.generated_at_utc` equality. Those contracts are intentionally strict and must not be weakened or reinterpreted merely to make operational data look hourly.

Before any live temporal consumer or public chart can be designed safely, future snapshots need an explicit cadence-bucket identity that says which UTC observation hour contains the real generation time while retaining the real generation/fetch timestamps unchanged.

## Goal

Prove a small additive operational evidence contract in which future source snapshots can carry:

```text
run.observation_hour_utc
```

under:

```text
phase12-observation-hour/v1
```

The field must be deterministic, independently validated and truthful: it identifies the UTC hour containing the actual `run.generated_at_utc`; it is not a claim that collection occurred at the hour boundary.

Phase 12 is successful when future snapshots can be classified as slot-ready evidence without changing historical snapshots, the pinned Phase 10 validator/config identities, or any frozen Phase 10/11 time/comparison/rendering semantics.

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

Phase 12 must not modify:

```text
scripts/validate_crypto_snapshot.py
config/crypto_sources.yml
```

Their frozen Git blob identities remain part of the Phase 10/11 immutable contract.

A legacy `0.2` snapshot without `run.observation_hour_utc` remains a valid legacy snapshot under the frozen validator, but it is not `phase12-observation-hour/v1` slot-ready evidence.

## Separate fail-closed validation

Phase 12 owns its new semantics in a separate repository validator rather than changing the frozen snapshot validator.

The Phase 12 validator must first require ordinary snapshot validity under the existing validator/config path, then require:

- `run.observation_hour_utc` is present;
- canonical UTC-hour syntax is exact;
- the value equals the containing UTC hour recomputed solely from `run.generated_at_utc`;
- malformed, missing or inconsistent identity fails closed.

Validation is deterministic and network-free. Branch names, wall clock, filesystem metadata, process identity and nominal cron occurrence are not evidence inputs.

## Scheduled and manual execution semantics

Scheduled and manual ingestion derive the observation hour from the same actual generation timestamp used to build the snapshot.

The existing `--now` override remains the deterministic test seam. Offset-aware timestamps are normalised to UTC before deriving the observation hour; existing accepted `--now` behaviour is not silently repurposed into a schedule-time claim.

No cron change is required merely to establish observation-hour evidence. If a delayed execution crosses an hour boundary, it belongs to the later hour in which it actually executed.

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

Accordingly, `phase12-observation-hour/v1` alone does **not** make Phase 10/11 v1 a live hourly temporal pipeline.

Any later comparison or temporal consumer that uses `run.observation_hour_utc` as cadence identity requires a new separately reviewed versioned contract. That future contract may reuse the proven fail-closed, immutable-provenance and explicit-gap principles from Phase 10/11, but it may not silently substitute observation-hour adjacency for frozen actual-time semantics.

Public/site integration remains parked behind that later consumer contract.

## Target workflow

Subject to separate delivery planning and authority, the intended evidence path is:

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
              reviewed source snapshot PR
```

A later separately governed consumer may use only validated slot-ready evidence under its own versioned semantics.

## Acceptance gates

- [ ] Future ingestion deterministically emits canonical `run.observation_hour_utc` from the actual generation timestamp.
- [ ] Actual `run.generated_at_utc` remains unrounded and independently visible.
- [ ] Existing source fetch timestamps remain unchanged.
- [ ] A separate Phase 12 validator rejects missing, malformed, non-canonical or mismatched observation-hour identity.
- [ ] Legacy snapshots continue to pass the frozen snapshot validator but are not classified as Phase-12 slot-ready.
- [ ] The frozen Phase 10 snapshot-validator and config Git blob identities remain unchanged.
- [ ] Exact boundary, mid-hour, end-of-hour and offset-normalisation cases are proved deterministically.
- [ ] Duplicate/missing/delayed observation semantics remain explicit with no winner/fallback rule.
- [ ] No historical snapshot path or byte is changed.
- [ ] Rolling workflow evidence exposes both actual generation time and observation hour before a slot-ready snapshot PR can proceed.
- [ ] Repository-wide exact-head validation succeeds for every implementation candidate.
- [ ] No Phase 10/11 semantic, site/publication, model/provider, credential or `_site/` change occurs.

## Anticipated bounded implementation surface

This roadmap does not authorise implementation. Subject to a separately reviewed delivery plan, the minimal expected files are:

```text
scripts/ingest_crypto_sources.py
scripts/validate_crypto_observation_hour.py
.github/workflows/ingest-crypto-sources.yml
tests/test_ingest_crypto_sources.py
tests/test_validate_crypto_observation_hour.py
tests/test_ingest_crypto_sources_workflow.py
```

If implementation requires changing a frozen Phase 10/11 file, historical snapshot, report/site path or a wider workflow surface, stop and return to governance rather than widening the phase opportunistically.

## Proposed delivery shape

After roadmap promotion, a separately authorised delivery-control issue should first produce an exact implementation plan. A likely bounded shape is:

```text
1. observation-hour derivation + separate validator
2. rolling-ingestion workflow evidence and deterministic proof
3. Phase 12 close-out and roadmap reconciliation
```

Each implementation candidate requires exact-head repository validation, fresh substantive review and separate merge authority.

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

Phase 12 is complete only when:

- [ ] a separately authorised delivery-control issue adopts the accepted `phase12-observation-hour/v1` design without relaxation;
- [ ] bounded implementation work is merged after exact-head validation and fresh review;
- [ ] deterministic proof covers the accepted derivation and fail-closed validation cases;
- [ ] actual timing evidence and historical snapshots remain unchanged;
- [ ] frozen Phase 10/11 validator/config and evidence contracts remain unchanged;
- [ ] rolling workflow evidence proves slot-ready snapshots before PR publication;
- [ ] public/site temporal integration remains unimplemented and separately governed;
- [ ] close-out delivery records and roadmap state are reconciled;
- [ ] delivery-graph disposition is reviewed against the final active ingestion dependency rather than assumed in advance;
- [ ] generated `_site/` output is not committed.

## Follow-on boundary

After Phase 12 proof, a separate shaping gate may decide whether a new observation-hour comparison/temporal contract is justified. Only after that consumer is independently proven may public/site temporal integration be reconsidered.
