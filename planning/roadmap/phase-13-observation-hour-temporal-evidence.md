# Phase 13 — Deterministic observation-hour comparison and temporal evidence

Status: complete.

This retained roadmap spec records the accepted Phase 13 contract that has now been delivered and proved. Completed delivery evidence is recorded in `planning/delivery/phase-13-observation-hour-temporal-evidence.md`.

## Governance

```text
Shaping issue: #443
Exact design: #443 comments 5305763171, 5305764744, 5305765770
Substantive design approval: #443 comment 5305767217
Roadmap-promotion authority: #443 comment 5305767801
Roadmap-promotion issue: #444
Trusted promotion baseline: d74d565ba8d223fcb346a1c43c0f4738b38ce5d4
Roadmap-promotion PR: #445
Roadmap merge: 950fae81ee7ccbd01c6be3c913fc9ec979b2a03f
Delivery control: #446
Approved implementation plan: #446 comment 5305791766
Fresh plan approval: #446 comment 5305792477
Close-out issue: #453
```

## Problem statement

Phase 12 gives future snapshots a truthful canonical `run.observation_hour_utc` containing-hour identity, but the repository has no operational contract for comparing adjacent observation hours or building temporal evidence from those snapshots.

Phase 10 cannot fill that role because its frozen predecessor rule orders by actual `run.generated_at_utc` and accepts only exactly 3,600 elapsed seconds. Phase 11 is likewise frozen to replay Phase 10. Using either contract directly for Phase-12-ready operational evidence would silently change its semantics.

## Goal

Deliver and prove a new cadence-slot evidence family that:

- compares exactly one current observation hour with exactly the immediately preceding observation hour;
- preserves actual generation/fetch timing as evidence without using exact actual elapsed time as the cadence gate;
- fails closed for missing, duplicate, invalid or identity-invalid slot evidence;
- builds deterministic canonical temporal series only from replayed Phase 13 comparison evidence;
- preserves immutable provenance, side-specific quality/warnings and closed metric/source vocabularies;
- is proved entirely offline and remains separate from public/site integration.

## Frozen contract family

```text
phase13-observation-hour-adjacency/v1
crypto-observation-hour-comparison/v1
crypto-observation-hour-series/v1
```

Required inherited input/evidence contracts remain:

```text
phase12-observation-hour/v1
phase10-snapshot-semantics-0.2/v1
```

The following frozen contracts are not changed or reinterpreted:

```text
phase10-predecessor-exact-hour/v1
crypto-snapshot-comparison/v1
crypto-temporal-series/v1
phase11-temporal-visualisation/v1
```

## Target evidence flow

```text
immutable repository commit/tree
  -> enumerate snapshot paths
  -> ignore legacy snapshots with no observation_hour_utc key
  -> fail globally if a participating asserted slot is malformed/unorderable
  -> resolve exact current observation hour H
  -> resolve exact predecessor observation hour H-1h
  -> validate immutable path/bytes/timezone identity
  -> validate phase12-observation-hour/v1 on each unique side
  -> require frozen semantic profile compatibility
  -> produce crypto-observation-hour-comparison/v1
  -> replay comparison records across an exact bounded UTC-hour window
  -> produce crypto-observation-hour-series/v1
  -> repository-bound replay validation and offline repeatability proof
```

There is no greatest-prior search, older fallback, interpolation, carry-forward, backfill or inferred value path.

## Candidate and adjacency rules

Only snapshots whose exact bytes contain the `run.observation_hour_utc` key participate. Legacy snapshots without the key remain intentionally non-slot-ready.

Every participating candidate must expose a canonical parseable `YYYY-MM-DDTHH:00:00Z` asserted slot before indexing. If any participating candidate cannot be deterministically indexed, the candidate population fails `candidate-set-unorderable` rather than silently skipping it.

For current slot `H` and predecessor slot exactly `H - 1 hour`:

```text
0 candidates  -> missing
1 candidate   -> validate identity and Phase 12 evidence
>1 candidates -> ambiguous with complete deterministic candidate identities
```

A duplicate slot is never repaired by discarding an invalid duplicate. A unique invalid candidate is not replaced by another hour.

## Actual-time and immutable identity

`run.generated_at_utc` remains actual generation time. Source `fetched_at_utc` evidence remains unchanged. Successful adjacent-slot comparison may have actual elapsed time below, equal to or above 3,600 seconds.

The comparison record retains deterministic `actual_elapsed_seconds` as evidence only.

Every participating side must retain the existing immutable repository-path identity invariant: actual UTC/local timestamps, declared timezone and optional abbreviation must reconstruct the exact repository path. Observation-hour identity never substitutes for actual-time path identity.

## Exact dependency pins for v1

```text
scripts/validate_crypto_snapshot.py
  b8c7fcc850bf0f5076f7d084bb6be9c24a9b7d3a

config/crypto_sources.yml
  73c5a3f3db81954951801c7d348d09a4c6296d73

scripts/validate_crypto_observation_hour.py
  21e18835c1047243ebda4b5ec7760fd9df793356

scripts/compare_crypto_snapshot_fields.py
  7a721cda7ab3d77b3c9291ff8373e5300bf00643

scripts/build_crypto_snapshot_comparison_record.py
  8fe3347ed0574e40e564e6fc3e1842ada2be4c81
```

A dependency change requires a separately reviewed contract revision rather than silent v1 drift.

## Closed comparison states

`crypto-observation-hour-comparison/v1` permits exactly:

```text
validation-contract-mismatch
candidate-set-unorderable
current-missing
current-ambiguous
current-identity-invalid
current-invalid
predecessor-missing
predecessor-ambiguous
predecessor-identity-invalid
predecessor-invalid
pair-schema-incompatible
pair-semantics-incompatible
comparison-available
```

Failure precedence is frozen by the accepted #443 design. No Phase 10 `predecessor-out-of-window` timing state exists in Phase 13.

## Evidence vocabularies

The comparison record retains the existing fixed-order pure-adapter evidence set:

```text
26 metric records
8 source-status records
```

The temporal-series key space remains deliberately bounded to the Phase 11-proven set:

```text
12 numeric metrics:
BTC.price_usd
BTC.market_cap_usd
BTC.volume_24h_usd
ETH.price_usd
ETH.market_cap_usd
ETH.volume_24h_usd
SOL.price_usd
SOL.market_cap_usd
SOL.volume_24h_usd
defi.total_tvl_usd
USDT.circulating_usd
USDC.circulating_usd

8 categorical sources:
coingecko
defillama
coinbase_exchange
kraken
okx
binance
bybit
cryptocompare
```

Missing or invalid numeric evidence is never coerced to zero. Source status remains categorical and separate from market movement.

## Temporal-series rules

`crypto-observation-hour-series/v1` accepts an exact inclusive UTC-hour window with at most 168 slots and replays the Phase 13 comparison contract for each slot.

Successful numeric values come only from `comparison-available` plus `comparable` current-side evidence. Missing, ambiguity, identity, validation, semantic and metric failures remain explicit gaps with a closed vocabulary.

Continuity requires the later retained predecessor identity to be field-for-field identical to the earlier retained current identity. Otherwise the series breaks continuity explicitly.

No interpolation, aggregation, smoothing, moving averages, normalisation, rebasing, percentage conversion, carry-forward, backfill or inferred values are allowed.

## Acceptance gates

- [x] Immutable commit/tree candidate enumeration is deterministic and legacy snapshots without observation-hour identity remain non-participating.
- [x] Malformed participating slot metadata fails `candidate-set-unorderable` rather than being skipped.
- [x] Exact current/predecessor slot cardinality, identity and Phase 12 validation fail closed with the frozen status precedence.
- [x] Adjacent-slot success works with actual elapsed times both below and above 3,600 seconds while preserving those actual timestamps as evidence.
- [x] No older-slot fallback exists.
- [x] Frozen validator/config/Phase-12-validator/adapter/semantic dependency identities are mechanically bound.
- [x] Pair semantics and full 26-metric/8-source comparison evidence remain closed and deterministic.
- [x] `crypto-observation-hour-comparison/v1` canonical records and `comparison_id` are deterministic and repository-bound.
- [x] `crypto-observation-hour-series/v1` exposes only the frozen 12-metric/8-source series vocabulary and replays comparison evidence without raw-value bypass.
- [x] Missing, duplicate, degraded, invalid and semantic failure evidence remains explicit and side-specific.
- [x] Continuity, gaps, tamper rejection and unknown-vocabulary rejection are proved offline.
- [x] Two independently materialised repositories produce byte-identical canonical comparison/series outputs and stable IDs.
- [x] Full repository validation passes on every implementation/proof slice.
- [x] No excluded public/site/workflow/provider/model/historical-snapshot behaviour changes.

## Delivered implementation slices

The accepted bounded delivery order was completed as:

```text
1. Observation-hour adjacency resolver + canonical comparison record/validator — #447 / PR #448
2. Canonical observation-hour temporal-series builder/validator — #449 / PR #450
3. Closed offline proof corpus and repeatability/tamper evidence — #451 / PR #452
4. Phase close-out and causal delivery reconciliation — #453
```

Public/site rendering was not a Phase 13 implementation slice.

## Non-goals

Phase 13 does not authorise:

- Phase 10 predecessor/comparison changes;
- Phase 11 series/renderer changes;
- Phase 12 ingestion/slot-identity changes;
- historical snapshot edits, renames or backfill;
- acquisition schedule/source/provider changes;
- deterministic selector changes;
- report generation or public/site temporal integration;
- workflow publication or auto-merge changes;
- provider/model/credential use;
- committed `_site/` output;
- forecasting, causality, sentiment taxonomy, technical levels, targets, watchlists or trading guidance.

## Risks and mitigations

### Risk: observation-hour adjacency is mistaken for Phase 10 timing semantics

Mitigation: separate contract names, separate status vocabulary and explicit preservation of actual elapsed time as non-gating evidence.

### Risk: invalid duplicate evidence is silently skipped

Mitigation: cardinality ambiguity is evaluated before side validity and complete deterministic candidate identities are retained.

### Risk: legacy snapshots poison the new consumer

Mitigation: absence of the Phase 12 field is the explicit non-participation boundary; only asserted Phase 12 evidence participates.

### Risk: dependency drift silently changes evidence

Mitigation: exact inherited Git blob identities are bound by v1 and changed dependencies require a new reviewed contract revision.

## Definition of done

Phase 13 is complete: the accepted contract family is implemented, repository-bound validation exists, the closed offline proof corpus passes, repeatability/tamper evidence is recorded, planning/delivery records are reconciled, the compact delivery graph records the enduring Phase 13 dependency boundary, and generated `_site/` output is not committed.

Public/site integration remains a separately governed successor decision after Phase 13 proof. No successor phase is selected by this close-out.
