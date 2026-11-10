# Phase 18 — Deterministic multi-asset temporal evidence

Status: selected; implementation not authorised.

This roadmap spec records the approved `phase18-public-multi-asset-price-evidence/v1` successor design promoted from #541. It is forward-looking planning only. Delivery evidence belongs in a later `planning/delivery/` close-out record after separately governed implementation and proof.

## Problem statement

Phase 15 proved that one repository-bound `BTC.price_usd` temporal series can cross the public-site boundary deterministically. Phase 16 made that existing surface reader-first without changing evidence authority. Phase 17 then increased trusted-main source-evidence availability and proved the unchanged Phase 13 / 15 / 16 consumer and public chain.

The remaining bounded product gap is that the public temporal surface remains intentionally single-series even though the frozen Phase 13 series contract already supports direct ETH and SOL price evidence under the same repository-bound authority model.

The next safe move is therefore not new acquisition, publication automation or derived analytics. It is a narrow public-evidence expansion that exposes exactly the already-supported BTC, ETH and SOL price series while preserving the existing 24-slot public-window, replay-validation, missingness, continuity and reader-safety semantics.

## Goal

Deliver the minimum safe multi-asset public temporal evidence capability defined by:

```text
phase18-public-multi-asset-price-evidence/v1
```

The fixed public series set and order is exactly:

```text
BTC.price_usd
ETH.price_usd
SOL.price_usd
```

Phase 18 must:

- use one common Phase-15-compatible 24 canonical UTC-hour window;
- bind all evidence to one immutable checked-out protected-main commit;
- replay-validate every Phase 13 series and the enclosing bundle;
- preserve byte-compatible Phase 15 BTC evidence for the same commit/window;
- expose exact gaps, degraded evidence and continuity without interpolation or inference;
- generalise/reuse the existing Phase 15/16 reader-rendering behaviour instead of creating a second semantics path;
- require truthful real protected-main evidence for all three assets before public integration.

## Non-goals

Phase 18 does not authorise or introduce:

- any Phase 13 metric or source-status series beyond the fixed BTC/ETH/SOL `price_usd` set;
- market-cap, rolling-volume, DeFi TVL, stablecoin-circulation or source-status cards/series;
- percentage-return calculation, rebasing, normalisation, correlation, ranking or relative-performance interpretation;
- multi-asset chart overlay or dual-axis presentation;
- interpolation, smoothing, aggregation, carry-forward, historical backfill or inferred trend;
- sentiment/risk taxonomy, causality, forecasts, recommendations, technical levels, targets, watchlists or signals;
- model/provider invocation, model selection, credentials or news/event ingestion;
- source-evidence acquisition, recovery or merge automation changes;
- automatic source-candidate merge;
- Phase 14 publication operationalisation or #477 activation;
- mutable rolling/candidate branches as public evidence authority;
- wall-clock `live`, `current` or `up-to-date` claims;
- committed generated `_site/` output;
- reinterpretation of Phase 12, 13, 15, 16 or 17 authority semantics.

## Authority and temporal-window contract

Protected `main` remains the sole public evidence authority.

Phase 18 inherits the Phase 15 public-window semantics exactly:

- enumerate Phase-13-participating evidence from one immutable checked-out commit;
- zero participation yields no asserted public multi-asset bundle/page;
- malformed or unorderable participating evidence fails closed;
- the deterministic anchor is the maximum canonical participating observation hour;
- the common window contains exactly 24 canonical UTC-hour slots ending at that anchor;
- duplicate, ambiguous, missing or invalid evidence remains explicit Phase 13 evidence;
- no fallback selects an older anchor or mutable branch.

The new Phase 18 selector/bundle boundary must reuse that existing public anchoring rule rather than create a second recency policy.

## Canonical bundle contract

The Phase 18 bundle contains at least:

```text
contract: phase18-public-multi-asset-price-evidence/v1
repository_context
window: {start_utc, end_utc}
series:
  - BTC.price_usd
  - ETH.price_usd
  - SOL.price_usd
bundle_id
```

Each member is an exact canonical `crypto-observation-hour-series/v1` record and must be independently replay-validated through the existing Phase 13 repository-bound validator.

All members must have exactly the same repository context and 24-slot window. Series ordering is fixed and canonical. Bundle canonical bytes use sorted keys, compact separators, UTF-8, no NaN and no wall-clock/process/filesystem identity. `bundle_id` is a lowercase SHA-256 over the canonical bundle identity material before inserting `bundle_id`.

Bundle validation must reconstruct/replay member evidence and bundle identity rather than trust asserted values or hashes.

No new market number is calculated by the bundle.

## Phase 15 compatibility boundary

For the same exact repository commit and common window, the Phase 18 BTC member must reproduce the existing Phase 15 BTC canonical record exactly.

A mismatch is a hard compatibility failure. Phase 18 may add ETH and SOL members but may not reinterpret, relax or silently replace the frozen Phase 15 BTC evidence contract.

## Reader-facing contract

Keep the existing `temporal.html` route for compatibility and evolve the reader-facing presentation to **Asset price evidence** rather than creating a second competing temporal product.

The primary hierarchy is:

1. historical/not-live demo and non-advice framing before market evidence;
2. exact common 24-slot UTC window;
3. fixed BTC / ETH / SOL evidence cards;
4. one independent chart region per asset only where chart-eligible evidence exists;
5. one compact reader table retaining exact values/gaps across the common window;
6. progressive disclosure for exact contract, provenance and audit evidence.

### Asset evidence cards

Each card may show only deterministic projections of its validated series:

- asset symbol;
- exact window-end slot value when asserted;
- otherwise `Unavailable at window end`;
- asserted-value coverage count;
- degraded-value warning count when non-zero;
- reader state derived from exact retained gaps/continuity.

There is no older-value fallback and no best/worst, trend, change, high/low, ranking or other inferred interpretation.

### Chart semantics

Each asset is evaluated independently under frozen Phase 13 continuity evidence:

- zero asserted values: no chart;
- asserted values with no exact continuous adjacent pair: no line chart;
- at least one exact continuous adjacent pair: render only exact points and continuity-approved segments;
- gaps and discontinuities remain visually broken;
- numeric extrema, if shown, are derived only from actually asserted values for that asset and only when a chart exists.

No chart may bridge a gap or use cross-asset overlays, rebasing, returns or normalisation to imply relative performance.

## Renderer reuse boundary

The existing Phase 15/16 reader path already implements the accepted projection, degraded-evidence detection, continuity segmentation, numeric validation, accessible SVG semantics and complete evidence-table behaviour.

Phase 18 Slice B must generalise/reuse those proven primitives rather than introduce a parallel projection/gap/continuity policy.

The renderer work must:

- preserve existing BTC behaviour wherever the compatibility proof requires byte-for-byte stability;
- parameterise/extract only the smallest generic primitives needed by the fixed BTC/ETH/SOL price set;
- retain exact continuity segmentation, gap retention and degraded-backed evidence semantics;
- keep asset-specific labels deterministic from the fixed series identity;
- prove existing BTC reader behaviour/regression explicitly when refactoring the single-series renderer.

The Phase 18 bundle is the new contract boundary; Phase 13 and Phase 15 evidence contracts remain frozen.

## Mandatory real-evidence usefulness gate

Before public-site integration may be approved, retain one exact protected-main proof showing that for one immutable commit:

- the Phase 18 bundle validates and replay-reconstructs deterministically;
- the BTC member exactly matches the Phase 15 BTC record for the same commit/window;
- BTC has at least one exact chart-eligible continuous adjacent pair;
- ETH has at least one exact chart-eligible continuous adjacent pair;
- SOL has at least one exact chart-eligible continuous adjacent pair.

This is a product-usefulness integration gate, not a new evidence-authority rule. If any asset fails it, do not weaken continuity/gap semantics or publish a fuller-looking page. Record the insufficiency and return to shaping/evidence availability.

## Delivery sequence

### Slice A — deterministic bundle contract and closed offline proof

Deliver the pure Phase 18 bundle builder/validator and a closed deterministic proof corpus. No site, CSS, workflow or publication change.

Prove at minimum:

- exact fixed series set/order;
- Phase 15 BTC compatibility;
- shared repository/window identity across all members;
- valid/gap/degraded behaviour independently for BTC, ETH and SOL;
- tamper, unknown-series, window and repository-context mismatch rejection;
- deterministic canonical bundle bytes and `bundle_id` across independent materialisations;
- zero derived market calculation.

### Slice B — reader projection and accessible multi-asset renderer

Generalise/reuse the existing Phase 15/16 reader primitives over an already validated Phase 18 bundle. No site integration yet.

Prove at minimum:

- exact window-end/no-fallback card semantics;
- independent chart/no-chart states;
- no line across gaps/discontinuities;
- accessible non-visual equivalent for every rendered chart;
- complete retained evidence under progressive disclosure;
- no JavaScript/network dependency required for evidence meaning;
- deterministic output bytes;
- BTC regression compatibility for reused/refactored renderer behaviour.

### Real-evidence usefulness proof

Before Slice C, prove the mandatory BTC/ETH/SOL continuous-pair gate against one exact protected-main commit without changing source-evidence semantics to manufacture success.

### Slice C — existing-site integration and public proof

Integrate the accepted multi-asset reader surface into the existing static-site generator and existing `temporal.html` route.

Require:

- exact-head repository validation;
- genuinely fresh substantive review;
- separate owner merge authority;
- automatic deployment through the existing Pages workflow;
- exact deployed-artifact and live-verification proof;
- no Pages permission/architecture redesign;
- generated `_site/` remains disposable and uncommitted.

## Acceptance gates

Phase 18 is complete only when separately governed implementation/proof candidates establish all of the following:

- [ ] Phase 18 remains a consumer of frozen Phase 13 evidence, not a replacement for it.
- [ ] Fixed public set is exactly BTC/ETH/SOL `price_usd` in canonical order.
- [ ] One common Phase-15-compatible 24-slot window is used.
- [ ] BTC member is canonical/byte-compatible with Phase 15 for the same commit/window.
- [ ] Every series and the enclosing bundle require repository-bound deterministic replay validation.
- [ ] Bundle bytes and `bundle_id` reproduce across independent materialisations.
- [ ] Real protected-main usefulness proof satisfies the continuous-pair gate for all three assets before site integration.
- [ ] Cards use exact window-end values only and never fallback to an older value.
- [ ] Charts never bridge retained gaps/discontinuities or imply cross-asset relative performance.
- [ ] Existing Phase 15/16 reader primitives are reused/generalised rather than semantically forked.
- [ ] Reader tables/progressive disclosure retain exact values, gaps, quality and provenance.
- [ ] Public demo / possible-inaccuracy / non-advice / non-research / non-recommendation / non-signal posture is preserved.
- [ ] Exact-head validation and fresh substantive review pass for every merge candidate.
- [ ] Existing Pages deployment/live-verification proves the exact merged public state.
- [ ] No Phase 14/#477 activation, model/provider/news/derived-analytics/trading authority or source-evidence merge automation is introduced.
- [ ] Generated `_site/` output is not committed.

## Risks and mitigations

### Risk: multi-asset presentation becomes derived market analysis

Mitigation: expose only three direct price series, separate charts, exact window-end values and coverage states; prohibit returns, rebasing, ranking, overlays and comparative interpretation.

### Risk: Phase 18 silently changes the trusted BTC product

Mitigation: require exact Phase 15 BTC compatibility for the same commit/window and explicit regression proof through any renderer generalisation.

### Risk: three assets create three subtly different evidence policies

Mitigation: one fixed common window, one Phase 13 series contract, one bundle validator and reused/common reader primitives.

### Risk: product pressure weakens missingness to make charts look complete

Mitigation: the real-evidence usefulness gate never changes validity/continuity rules; insufficient evidence blocks public integration rather than relaxing gaps.

### Risk: visual expansion implies publication or freshness expansion

Mitigation: existing protected-main/Pages authority remains unchanged; Phase 14/#477 stays parked and public wording remains historical/not-live.

## Definition of done

The phase is complete when:

- [ ] a Phase 18 parent delivery-control issue and bounded child work are durable;
- [ ] Slice A deterministic bundle/validator/proof is merged after exact-head validation and fresh review;
- [ ] Slice B reused/generalised renderer/projection proof is merged after exact-head validation and fresh review;
- [ ] the real protected-main usefulness gate passes for BTC, ETH and SOL without semantic relaxation;
- [ ] Slice C existing-site integration is merged under separate owner authority;
- [ ] exact Pages deployment and live/deployed-artifact proof succeed for the merged public state;
- [ ] close-out records exact implementation, proof identities and preserved boundaries in `planning/delivery/` and the concise ledger/graph where applicable;
- [ ] roadmap/backlog state is reconciled without promoting broader analytics or other parked capabilities;
- [ ] `_site/` remains uncommitted.

## Governing evidence

- shaping issue: #541;
- candidate contract: `phase18-public-multi-asset-price-evidence/v1`;
- renderer-reuse clarification: #541 comment `5472275034`;
- fresh substantive design review: #541 comment `5472280449` — `APPROVED`;
- owner successor/roadmap-promotion decision: #541 comment `5474584463` — `ACCEPT`;
- roadmap-promotion control: #542.

Implementation authority remains separate. Roadmap selection does not by itself authorise Slice A code mutation, workflow dispatch, merge, deployment/publication or any Phase 14/#477 action.
