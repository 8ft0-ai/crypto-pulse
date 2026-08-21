# Phase 15 — Public deterministic temporal evidence

Status: complete. Delivered and publicly proved under #482; no successor phase is selected by this close-out.

This roadmap spec promoted the accepted `phase15-public-temporal-evidence/v1` design from #479 as the bounded CryptoPulse successor direction after Phase 14. The completed phase connects already-proved Phase 13 observation-hour temporal evidence to the existing public demo site without changing frozen Phase 11/12/13 contracts, enabling Phase 14 publication activation, or introducing model/provider behaviour.

## Governance

```text
Shaping issue: #479
Accepted design: current #479 issue body
Contract: phase15-public-temporal-evidence/v1
Prior changes-required disposition: #479 comment 5363665099
Remediation handoff: #479 comment 5363711810
Fresh substantive design approval: #479 comment 5363860245
Owner successor/promotion authority: #479 comment 5363896477
Roadmap-promotion issue: #480
Trusted promotion baseline: 591356bcb6ad6c247f530f3efd6f3c88379fc665
Parent delivery control: #482
Slice 1 proof: PR #483 / merge 3f39a2857cd1ba6df91f64077b1dff67788fa2b5
Trusted-main evidence prerequisite: #484 / PR #488 / merge 0a119deb5f44babe4239e693ac82d648801a3772
Slice 3 site integration: #489 / PR #490 / merge 99c4ced3001bb227d599173bb5a17011d23eea53
Automatic Pages proof: run 32528437373
Durable publication verification: #482 comment 5375652127
Slice 4 close-out: #491
```

## Problem statement

CryptoPulse already had deterministic temporal evidence foundations, but they remained offline and were not visible on the public demo site.

Phase 13 provides repository-bound `crypto-observation-hour-series/v1` records over exact canonical observation-hour slots with explicit gaps, continuity, provenance and replay validation. Phase 11 provides deterministic accessible rendering conventions, but its renderer validates the separately frozen `crypto-temporal-series/v1` schema and cannot be reused as though Phase 13 records were Phase 11 records.

At shaping time trusted `main` also contained no Phase-13-participating snapshot evidence because retained historical snapshots predated the additive Phase 12 `run.observation_hour_utc` identity. The delivered integration therefore defined both deterministic window selection and the empty-participation state without falling back to mutable branches, legacy evidence, wall clock or historical backfill, and satisfied the real trusted-main evidence prerequisite separately before public integration.

## Goal

Deliver and prove the smallest public integration that:

- derives one bounded historical series from one immutable checked-out repository commit;
- publishes only `metric` / `BTC.price_usd` over exactly 24 canonical observation-hour slots in v1;
- inherits exact frozen Phase 13 participation and malformed/unorderable-population semantics;
- fails closed when no participating observation exists;
- preserves duplicate-hour ambiguity, missing hours, validation failures, gaps and continuity breaks exactly as Phase 13 evidence;
- validates the canonical Phase 13 record directly before rendering;
- emits deterministic semantic HTML, inline SVG and a complete equivalent evidence table;
- integrates through the existing canonical `site_generator` pipeline;
- keeps demo/non-advice framing visible before market evidence;
- changes no Phase 14 activation or #477 state.

This goal is complete.

## Frozen Phase 15 contract

```text
phase15-public-temporal-evidence/v1
```

The v1 public surface remains intentionally narrow:

```text
series_kind: metric
series_key: BTC.price_usd
window_slots: 24 canonical UTC hours
public_page: temporal.html
homepage_discovery: one low-prominence link, only when the page succeeds
```

No additional metric, source-status series, market-card product surface, narrative, interpretation, forecast or advice is part of v1.

## Input authority and participation

The public temporal surface is derived only from the exact checked-out trusted repository commit used by the site build.

Phase 15 enumerates the snapshot population using the exact frozen Phase 13 participation semantics through the shared implementation primitive. It does not define a second or weaker notion of participation.

Legacy snapshots without `run.observation_hour_utc` remain non-participating. Any participating candidate that makes the population malformed or unorderable under Phase 13 fails closed before a public window is selected.

No raw-snapshot rendering bypass is permitted. The selected window is materialised as one canonical `crypto-observation-hour-series/v1` record and validated with `validate_observation_hour_series` from the same immutable repository context before rendering.

## Deterministic 24-slot window

For one immutable checked-out repository commit:

```text
1. enumerate using exact Phase 13 participation semantics
2. fail closed if the participating population is malformed/unorderable
3. collect canonical participating run.observation_hour_utc identities
4. if none exist, emit no asserted series and no temporal.html
5. otherwise:
     window.end_utc   = maximum canonical participating observation_hour_utc
     window.start_utc = window.end_utc - 23 hours
```

The selector does not use wall clock, workflow time, filesystem metadata, report titles, network state or mutable branch state.

Duplicate candidates for the selected end hour never elect a winner and never move the anchor backwards. The canonical duplicated hour remains the deterministic window end, while frozen Phase 13 semantics expose that selected slot as explicit ambiguity/gap evidence.

Missing, duplicate, invalid or otherwise unavailable evidence inside the 24 slots remains explicit. No slot is filled, interpolated, skipped, replaced by an older slot, carried forward or backfilled.

## Separately governed trusted-main evidence prerequisite

The original trusted baseline contained zero Phase-13-participating observations, so site integration could not truthfully produce the proposed public page.

The prerequisite was satisfied separately by #484 / PR #488 before site integration. Reviewed repository-owned evidence placed one Phase-12-valid participating snapshot on trusted `main`:

```text
path: data/crypto/hourly/2026/08/21/1549_AEST_source_snapshot.json
blob: 3908fb4e0f78b4688086158fc05d23dc33946191
SHA-256: c160c0bdc7610073f687ecbcba728fef70d8d6b48d0fde81193b8895897f3bd5
run.observation_hour_utc: 2026-08-21T05:00:00Z
source run/job: 32451979070 / 96682021706
merge: 0a119deb5f44babe4239e693ac82d648801a3772
```

The prerequisite did not require 24 successful observations because absent hours remain explicit gaps. It did not render directly from `automation/source-snapshot-rolling` or another mutable branch, mutate/backfill retained historical snapshots, reinterpret legacy snapshots, or use Phase 14/#477 as an implicit promotion path.

If a later checked-out commit has zero participating observations, temporal-page generation again fails closed rather than publishing stale, fabricated, branch-only or legacy evidence.

## Renderer boundary

Phase 15 provides one narrow public renderer boundary over validated Phase 13 evidence.

It reuses no incompatible Phase 11 schema semantics and does not:

- convert a Phase 13 record into a fake `crypto-temporal-series/v1` record;
- bypass `validate_observation_hour_series`;
- call an internal Phase 11 rendering path without its required Phase 11 validator;
- reinterpret any frozen Phase 11, Phase 12 or Phase 13 semantic contract.

The renderer public entry point itself accepts repository root plus record and directly calls `validate_observation_hour_series(repository_root, record)` before Phase 15 shape enforcement or output. The output is deterministic semantic HTML with inline SVG and a complete evidence table. Meaning does not depend on colour alone. Gaps, degraded evidence and continuity breaks remain visibly attributable.

## Public-site integration

Integration is through the canonical `site_generator` pipeline rather than a parallel Pages build path.

The v1 surface is:

```text
one generated temporal.html page
one low-prominence homepage discovery link
```

The homepage link is emitted only when `temporal.html` is successfully generated from the same checked-out repository commit. Fail-closed paths remove stale page/link output.

Generated `_site/` remains disposable and uncommitted.

No Pages workflow permission, trigger, environment or deployment redesign was introduced. The merge of PR #490 automatically exercised the existing Pages workflow and was verified through run `32528437373` for exact merged commit `99c4ced3001bb227d599173bb5a17011d23eea53`.

## Public framing

Before the chart or market evidence is read, the temporal page makes clear that it is deterministic historical evidence in an AI/demo project and is not a forecast, investment research, recommendation, trading signal, market call or financial advice.

No generated narrative or interpretation is added. Gaps and degraded evidence remain visible rather than being hidden for presentation quality.

## Non-goals

These remain unchanged after completion:

- no work under #477;
- no Phase 14 `pilot` or `recurring` activation;
- no deterministic-publication candidate generation or merge automation;
- no App, environment, branch-protection or ruleset change;
- no model/provider invocation or credentials;
- no prediction, sentiment, causal explanation, technical levels, targets or watchlists;
- no external data source;
- no series beyond `BTC.price_usd` in v1;
- no modification or reinterpretation of frozen Phase 10/11/12/13 contracts;
- no historical snapshot mutation or backfill;
- no mutable rolling branch as public rendering authority;
- no committed `_site/` output;
- no direct archived-report editing;
- no Pages workflow/permission change.

## Acceptance gates

- [x] Exact `phase15-public-temporal-evidence/v1` contract is frozen before implementation.
- [x] Latest-window selection inherits exact Phase 13 participation semantics from one immutable repository commit.
- [x] Malformed/unorderable participating population fails closed before window selection.
- [x] Zero participating observations reject temporal-series and page generation with no fallback.
- [x] The non-empty window is exactly 24 canonical slots ending at the maximum participating canonical observation hour.
- [x] Duplicate candidates never elect a winner or move the window anchor backwards.
- [x] Empty, malformed, non-empty deterministic selection, duplicate latest hour, internal missing-hour and repeatability paths have closed deterministic proof.
- [x] Before site integration, trusted `main` contains at least one separately governed Phase-12-valid participating snapshot.
- [x] Only repository-validated Phase 13 records can reach the renderer.
- [x] Rendering preserves exact values/statuses, gaps, continuity and attributable provenance without derived trend analytics.
- [x] Output is deterministic for the same repository tree/commit.
- [x] Semantic HTML/inline SVG and the complete evidence table provide accessible equivalent evidence without JavaScript or network assets.
- [x] Demo/non-advice framing appears before market evidence.
- [x] Site integration is one dedicated temporal page plus the minimum discovery link, emitted only when the page succeeds from the same commit.
- [x] No frozen Phase 10/11/12/13 contract, Phase 14 activation, #477 scope or report archive is changed.
- [x] Generated `_site/` remains uncommitted.
- [x] Exact-head repository validation succeeds for every implementation candidate.
- [x] Genuinely fresh independent substantive review approves each merge candidate where required.
- [x] Live Pages verification confirms deployed identity/content only after separately authorised site integration merge, using GitHub deployment success plus exact deployed-artifact inspection recorded in #482 comment `5375652127`.

## Delivered implementation slices

1. **Roadmap promotion and delivery control** — promoted the Phase 15 spec and established parent #482; no runtime change.
2. **Contract + deterministic renderer** — PR #483 implemented exact Phase 13 participation reuse, the 24-slot selector, direct validation, renderer and closed proof corpus.
3. **Trusted-main evidence prerequisite** — #484 / PR #488 separately promoted one reviewed Phase-12-valid participant after the validation-trigger prerequisite was corrected by #486 / PR #487.
4. **Site integration** — #489 / PR #490 added `temporal.html`, minimum homepage discoverability, focused accessibility/style coverage and complete site-build validation through the canonical pipeline.
5. **Public proof + close-out** — automatic Pages run `32528437373` proved publication of the exact PR #490 merge state; #491 records the bounded planning close-out.

The separately governed trusted-main evidence prerequisite was not collapsed into renderer/site implementation.

## Risks and delivered mitigations

### Risk: Phase 15 duplicates or drifts from Phase 13 participation semantics

Mitigation: the implementation reuses the exact Phase 13 population primitive with equivalence proof; malformed/unorderable population fails closed.

### Risk: an empty trusted-main population creates a fabricated or stale public chart

Mitigation: zero participation produces no asserted series/page, and site integration proceeded only after real reviewed Phase-12-valid evidence was merged to trusted `main`.

### Risk: duplicate latest-hour evidence is silently resolved

Mitigation: the maximum canonical participating hour remains the anchor; Phase 13 ambiguity is exposed as a gap with no fallback to an older hour.

### Risk: the Phase 11 renderer is reused across an incompatible schema boundary

Mitigation: the narrow Phase 15 renderer directly validates `crypto-observation-hour-series/v1` and does not cross the Phase 11 validator/schema boundary.

### Risk: the public surface drifts toward a market product or advice

Mitigation: one BTC price series, one bounded page, minimal discovery, no narrative/forecast/advice, and visible demo/non-advice framing.

### Risk: Phase 15 implicitly operationalises Phase 14 or #477

Mitigation: both remain explicit non-goals and parked backlog work; neither was used for evidence promotion, site integration or publication proof.

## Close-out evidence

```text
Slice 1 PR/head/tree: #483 / 31a6eda8a975bc8251ee4e57ad9cd30234bdec17 / 05d2ebd2b183a84d05dbc92646808444081691dd
Slice 1 validation: run 32451833403 / job 96681619786
Slice 1 fresh approval: comment 5365789771

Evidence PR/head/tree: #488 / 491a901f5fc3006815b1ef7a7cee1d11df8260d9 / 493d6aa030b137d0449e99c01f7703382ffe6a44
Evidence validation: run 32484067027 / job 96776544736
Evidence fresh approval: comment 5370258468

Site PR/head/tree: #490 / 1eeb96cfe4db61edba414f53fe29f60e678513a0 / 1360abd2f0bda5b165ec888c71c76a85416e4fa7
Site merge: 99c4ced3001bb227d599173bb5a17011d23eea53
Site validation: run 32525071794 / job 96905337127
Site fresh approval: comment 5375474533
Site merge decision: comment 5375578071

Pages run: 32528437373 — success
Published build identity: 99c4ced3001bb227d599173bb5a17011d23eea53
Publication verification: #482 comment 5375652127
```

The publication proof is intentionally precise: GitHub reported successful Pages deployment for the exact merged commit and the exact deployed artifact was inspected for the expected page, identity, discovery link, disclaimer ordering and 24 evidence rows. The close-out environment could not perform a separate CDN HTTP fetch, so no independent network-fetch claim is made.

## Definition of done

- [x] the parent issue and required linked slice issues exist, including #491 for close-out;
- [x] implementation and proof candidates satisfy their exact acceptance gates and are merged under separate authority;
- [x] the trusted-main evidence prerequisite is independently satisfied before site integration;
- [x] the public temporal page is deployed and its exact deployed identity/content is verified through GitHub deployment state plus exact deployed-artifact inspection;
- [x] `planning/delivery/phase-15-public-deterministic-temporal-evidence.md` records what actually shipped and what remains excluded;
- [x] `planning/delivery-log.md` records the Phase 15 close-out;
- [x] `planning/delivery/delivery.yaml` is updated with the compact Phase 15 causal/proof boundary;
- [x] `planning/delivery/graph.md` is regenerated from the updated delivery YAML;
- [x] roadmap files record Phase 15 as completed without selecting a successor;
- [x] generated `_site/` output is not committed.

## Follow-on delivery record

Completed delivery is recorded in:

```text
planning/delivery/phase-15-public-deterministic-temporal-evidence.md
```

No successor direction is selected automatically. Phase 14/#477 operationalisation, broader temporal series/market-card scope, model work and every other backlog item remain separately governed candidates requiring new shaping and owner authority.
