# Phase 10 — Deterministic previous-hour comparison engine

Status: complete.

Primary outcome: CryptoPulse can deterministically compare one repository-owned current snapshot with its uniquely resolved immediate predecessor under the frozen exact-hour contract, producing validated structured comparison evidence with immutable provenance and no provider/model call.

## Governance

```text
Roadmap rebaseline: #398
Parent delivery-control issue: #400
Close-out issue: #412
Frozen design: #400 comment 5301581279
Predecessor policy: phase10-predecessor-exact-hour/v1
Semantic contract: phase10-snapshot-semantics-0.2/v1
Comparison contract: crypto-snapshot-comparison/v1
```

The predecessor/time-gap, semantic-compatibility and comparison-record contracts were frozen and independently accepted before implementation planning began. Phase 10 did not widen those contracts after fixtures or runtime evidence were observed.

## Delivered slices and corrective evidence

```text
Slice 1 planning: #401
Slice 1 implementation: PR #403
Slice 1 merge: 0cd719e2149b17c31183e2de4a7ddc8c08c8c14a

Slice 2 planning: #404
Slice 2 implementation: PR #405
Slice 2 merge: a80e6e735948cf641e8573fe51cd93dc573abc81

Slice 3 planning: #406
Slice 3 implementation: PR #407
Slice 3 merge: a095dc88d918319f39f063316f1d9678d024c321
Slice 3 exact-head validation: 31883721665

Immutable-binding corrective reconciliation: PR #402
Corrective merge: e8673aeb89fa21dda4a809aea378d0e7b24564ef
Corrective exact-head validation: 31882840576

Slice 4 planning: #409
Offline proof PR: #410
Proof merge: 873df207b81afb8c9a0fa2a2410b4683136b1e02
Proof exact-head validation: 31911287479

Close-out semantic blocker: #411
Focused corrective PR: #413
Corrective merge: 47c92d2cb8849bf673763bf31f4caf2406ef49eb
Corrective exact-head validation: 31913953865
```

Issue #408 separately reconciled an intervening history-only housekeeping disturbance. The recovered repository tree was content-identical to the former trusted tree, so that reconciliation did not change the Phase 10 contract or implementation semantics.

A close-out review then exposed one implementation gap: the semantic gate accepted the required BTC/ETH/SOL and USDT/USDC identities but did not reject additional asset or stablecoin identities. #411 and PR #413 corrected that gap by requiring those normalised identity sets to match the frozen sets exactly. Unknown additional identities now fail `pair-semantics-incompatible`. This was enforcement of the already-frozen #400 contract, not a contract expansion or reinterpretation.

## Shipped comparison contract

The implementation preserves the frozen contract:

- `run.generated_at_utc` is the sole ordering timestamp;
- each input is bound to repository-relative path, exact-byte SHA-256, `schema_version` and authoritative generation time;
- comparison execution is bound to one immutable Git commit/tree plus the pinned snapshot-validator and source-config blob identities;
- `valid-ok` and `valid-degraded` inputs remain eligible under the existing snapshot-validity semantics, and degraded quality plus non-blocking warnings remain visible in comparison evidence;
- candidate enumeration comes from the exact immutable repository tree;
- the predecessor is the greatest timestamp strictly earlier than current;
- ties fail closed as ambiguous;
- the immediate prior candidate is never skipped in favour of an older snapshot because it is invalid, incompatible or outside the time rule;
- the accepted elapsed interval is exactly `3,600` seconds with no tolerance or fallback;
- identity, validation, ambiguity, time-window, schema and semantic incompatibility failures remain machine-visible and fail closed;
- supported market-asset identities are exactly BTC, ETH and SOL, and supported stablecoin identities are exactly USDT and USDC; unknown additional identities fail `pair-semantics-incompatible`;
- comparison records use the versioned `crypto-snapshot-comparison/v1` contract and deterministic canonical full-record `comparison_id` hashing.

## Metric and source evidence

For eligible pairs, Phase 10 emits the frozen deterministic evidence set:

```text
26 metric records
8 source-status records
```

Metric records preserve comparable, unavailable-current, unavailable-predecessor, invalid-current and invalid-predecessor distinctions where applicable. Missing numeric evidence is never coerced to zero.

Source status and availability remain a separate evidence family. Source gain, loss, missing state and status transition are not converted into price, market-cap, volume, TVL, stablecoin or other market movement.

`market_cap_rank` remains a generic numerical relation rather than directional market-performance semantics.

## Offline proof and final regression evidence

PR #410 adds the closed ordered `phase10-comparison-proof-corpus/v1` corpus with fourteen reviewer-visible cases. The corpus retains exact input bytes and complete golden outputs and proves independent deterministic seed-repository materialisation, stable commit/tree identity, canonical output bytes and stable `comparison_id` values.

The corpus covers:

- available mixed metric/source evidence;
- available `valid-degraded` evidence;
- validation-contract mismatch;
- invalid and identity-invalid current input;
- unorderable candidate sets;
- missing and ambiguous predecessors;
- invalid and identity-invalid predecessors;
- out-of-window timing;
- schema incompatibility;
- semantic incompatibility;
- pure-adapter missing/invalid side evidence.

Exact-head repository validation `31911287479` succeeded for the proof candidate.

PR #413 adds focused end-to-end regression coverage for the close-out semantic blocker. It proves unknown market-asset and unknown stablecoin identities on either input fail `pair-semantics-incompatible`, while an exact supported pair still reaches `comparison-available`. Exact-head repository validation `31913953865` succeeded.

All proof and corrective regression evidence is offline for provider/model purposes and requires no credentials or paid API use.

## Boundaries preserved

Phase 10 did not change or authorise:

- scheduled or rolling source snapshot automation;
- source snapshot generation, merge or historical snapshot mutation;
- deterministic candidate-selector behaviour;
- report generation, scheduling, publication or auto-merge;
- report/site rendering or public market-card behaviour;
- provider/model evaluation or invocation;
- credentials, secrets or paid API keys;
- Phase 9 outcome or recovery authority;
- news/event ingestion, causality, sentiment taxonomy, support/resistance, signals, targets, watchlists or trading guidance;
- committed generated `_site/` output.

The deterministic selector from Phase 6 remains the sole active selector. Phase 9 remains closed with `no-stable-material-uplift` and its temporary paid workflow remains archived.

## Delivery graph disposition

`planning/delivery/delivery.yaml` and generated `planning/delivery/graph.md` are not changed for Phase 10.

Disposition: **N/A under the existing compact causal graph rules**.

Phase 10 adds an offline deterministic evidence capability but does not integrate that capability into the active ingestion/report/site/publication pipeline. Adding a disconnected Phase 10 implementation island, or backfilling unrelated later phases solely to connect it, would turn the compact graph into an implementation inventory. This delivery record and `planning/delivery-log.md` remain the appropriate management-level navigation until a separately governed future phase makes comparison evidence a causal dependency in the active delivery path.

## Carry-forward

The Phase 10 comparison capability is a deterministic evidence boundary only. Any future phase that consumes comparison evidence for reports, site features, charts, controlled taxonomies, model evaluation or narrative requires separate shaping, governance and owner authority. No such follow-on is selected or authorised by this close-out.
