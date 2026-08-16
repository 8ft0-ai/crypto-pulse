# Phase 13 — Deterministic observation-hour comparison and temporal evidence

Status: complete.

Primary outcome: CryptoPulse now has a separately versioned, deterministic and repository-bound observation-hour comparison/temporal evidence family that consumes Phase-12 slot identity without reinterpreting frozen Phase 10/11 timing or rendering semantics.

## Governance

```text
Shaping issue: #443
Exact design: #443 comments 5305763171, 5305764744, 5305765770
Substantive design approval: #443 comment 5305767217
Roadmap-promotion authority: #443 comment 5305767801
Roadmap promotion: #444 / PR #445
Roadmap merge: 950fae81ee7ccbd01c6be3c913fc9ec979b2a03f
Parent delivery-control issue: #446
Approved implementation plan: #446 comment 5305791766
Fresh plan approval: #446 comment 5305792477
Close-out issue: #453
Contracts: phase13-observation-hour-adjacency/v1, crypto-observation-hour-comparison/v1, crypto-observation-hour-series/v1
```

The accepted design and implementation plan were reviewed before delivery. Phase 13 remained a new consumer boundary: no frozen Phase 10/11/12 contract was changed or reinterpreted.

## Delivered slices

```text
Slice 1 issue: #447
Slice 1 PR: #448
Slice 1 reviewed head: f3f59edd72354552ce321b447e91d48e0d609324
Slice 1 validation: 31928211032
Slice 1 substantive approval: #447 comment 5305999000
Slice 1 merge authority: #447 comment 5305999305
Slice 1 merge: 4e67918ba9e9be05689d3976e08d9230844263df

Slice 2 issue: #449
Slice 2 PR: #450
Slice 2 reviewed head: 7af3afbc8fd4db8a26a8ac487484270ce82da99b
Slice 2 validation: 31935983698
Slice 2 substantive approval: #449 comment 5306523750
Slice 2 merge authority: #449 comment 5306524990
Slice 2 merge: 07385273c48ad4d4ead26b75797d704119bbcaf5

Slice 3 issue: #451
Slice 3 PR: #452
Slice 3 reviewed head: 088410f07a36698560d1d36dfe89d1f1c7aa17ac
Slice 3 validation: 31937233333
Slice 3 substantive approval: PR #452 comment 5306629389
Slice 3 merge authority: PR #452 comment 5306630502
Slice 3 merge: 43cbf6a62afbc83d97f6f677795b0fe61c50738a
```

All accepted candidates passed full repository exact-head validation before merge. Bounded proof-only deficiencies found during Slice 1 and Slice 2 review were remediated without changing inherited contracts or weakening expected evidence.

## Observation-hour adjacency

`phase13-observation-hour-adjacency/v1` enumerates immutable repository-tree snapshot candidates and treats snapshots without `run.observation_hour_utc` as legacy/non-participating evidence.

Every participating asserted slot must be canonical and parseable. A malformed participating candidate fails the population as `candidate-set-unorderable`; it is never silently skipped.

For requested current hour `H`, selection is exact:

```text
current:     H
predecessor: H - 1 hour
```

Cardinality is evaluated before side validity. Zero candidates is missing, more than one is ambiguous, and a unique candidate must then pass immutable path/actual-time/timezone identity and Phase-12 observation-hour validation. There is no greatest-prior search, older fallback or invalid-duplicate discard.

## Canonical comparison evidence

`crypto-observation-hour-comparison/v1` preserves actual generation timing as evidence rather than as the cadence gate. A successful adjacent-slot pair may have actual elapsed time below, equal to or above 3,600 seconds; deterministic `actual_elapsed_seconds` records that fact without changing slot adjacency.

The comparison keeps the accepted closed status precedence, exact inherited dependency pins, side-specific `valid-ok` / `valid-degraded` quality and warnings, and fixed-order evidence comprising:

```text
26 metric records
8 source-status records
```

Missing or invalid metrics are never coerced to zero. Source availability remains categorical and separate from market movement. Canonical records have deterministic `comparison_id` values and repository-bound validation reconstructs enumeration, selection, identity, validation and evidence rather than trusting asserted output.

## Canonical temporal series

`crypto-observation-hour-series/v1` accepts an exact inclusive canonical UTC-hour window capped at 168 slots and replays the Phase 13 comparison contract for every slot.

The only value-producing numeric path is `comparison-available` plus `comparable` current-side evidence. The series exposes only the frozen 12 numeric metric keys and eight categorical source-status keys. Missing, ambiguity, identity, validation, semantic and metric failures remain explicit closed gaps.

Current/predecessor identities, quality, warnings, timing and provenance remain attributable. Continuity exists only when the later predecessor identity is field-for-field identical to the earlier current identity; unavailable or different identity breaks continuity explicitly.

There is no raw-snapshot success bypass, interpolation, aggregation, smoothing, normalisation, rebasing, carry-forward, backfill or inferred value path. Canonical series bytes and `series_id` are deterministic and repository-bound replay validation rejects tampering and unknown vocabulary.

## Closed offline proof corpus

`tests/fixtures/phase13_observation_hour_temporal_proof_v1.json` and `tests/test_crypto_observation_hour_temporal_proof_corpus.py` form the accepted Phase 13 offline proof corpus.

The corpus independently materialises immutable synthetic Git repositories and covers the accepted design matrix, including:

- below/above-3,600-second actual elapsed evidence and legacy exclusion;
- malformed participating evidence and every closed current/predecessor missing, ambiguity, identity and validation failure;
- both side-specific `valid-degraded` cases and schema/semantic incompatibility;
- all metric unavailable/invalid gap states and categorical source-status evidence;
- continuity, discontinuity and unavailable identity states;
- unknown-vocabulary and repository-bound tamper rejection.

Two independent materialisations must produce byte-identical canonical outputs and stable IDs. Representative frozen evidence is:

```text
comparison canonical bytes: 9,459
comparison SHA-256: 046f1f65e5a90d5138068791e5a0b1d6da2b1ec58e45e5aef7f222dac471f3e7
comparison_id: b2e16c6e3a27d50d4a4429292c1cf962b718132af5cb20e68bdd2010019624a8

series canonical bytes: 21,626
series SHA-256: 70495c03030003d6082774a22fc11ccc895aaf403c97f6e0033af2d0683839be
series_id: 9508741e0cd75d226f93896b9e8405fad6e316f406e847420b77adb4765aa463
```

Exact-head validation `31937233333` independently reproduced those values while passing the full test suite.

## Frozen inherited boundaries

Phase 13 does not alter or reinterpret:

```text
phase10-predecessor-exact-hour/v1
crypto-snapshot-comparison/v1
crypto-temporal-series/v1
phase11-temporal-visualisation/v1
phase12-observation-hour/v1
```

Historical snapshot paths/bytes, acquisition schedules/workflows, selectors, reports/site, the Phase 11 renderer, providers/models, credentials and publication behaviour remain unchanged.

Phase 13 adds no auto-merge, committed `_site/`, forecasting, causality, sentiment taxonomy, technical levels, targets, watchlists or trading guidance.

## Delivery graph disposition

The compact graph is updated under `planning/delivery/graph-modelling-rules.md` because Phase 13 turns the Phase-12 observation-hour boundary into an enduring canonical comparison/series evidence dependency for any later separately governed rendering or public integration.

The graph models only the Phase 13 phase, governing parent issue, representative proof PR, canonical series artefact and preserved public-integration boundary needed to explain that causal transition. It does not inventory every implementation issue, PR, test or workflow run.

## Carry-forward

Phase 13 is complete as an offline deterministic observation-hour comparison/temporal evidence capability.

Public/site integration of temporal evidence remains parked. A later phase may choose to connect the proven Phase 13 series to rendering or publication only through a new separately reviewed design, plan and implementation authority.

No successor phase is selected or authorised by this close-out.
