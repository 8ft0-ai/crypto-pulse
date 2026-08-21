# Phase 15 — Public deterministic temporal evidence

Status: promoted for delivery planning; implementation not yet authorised by this roadmap record.

This roadmap spec promotes the accepted `phase15-public-temporal-evidence/v1` design from #479 as the next bounded CryptoPulse successor direction after Phase 14. It connects already-proved Phase 13 observation-hour temporal evidence to the existing public demo site without changing frozen Phase 11/12/13 contracts, enabling Phase 14 publication activation, or introducing model/provider behaviour.

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
```

## Problem statement

CryptoPulse already has deterministic temporal evidence foundations, but they remain offline and are not visible on the public demo site.

Phase 13 provides repository-bound `crypto-observation-hour-series/v1` records over exact canonical observation-hour slots with explicit gaps, continuity, provenance and replay validation. Phase 11 provides deterministic accessible rendering conventions, but its renderer validates the separately frozen `crypto-temporal-series/v1` schema and cannot be reused as though Phase 13 records were Phase 11 records.

The trusted baseline also contains no Phase-13-participating snapshot evidence because retained historical snapshots predate the additive Phase 12 `run.observation_hour_utc` identity. A safe public integration must therefore define both deterministic window selection and the empty-participation state without falling back to mutable branches, legacy evidence, wall clock or historical backfill.

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

## Frozen Phase 15 contract

```text
phase15-public-temporal-evidence/v1
```

The v1 public surface is intentionally narrow:

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

Phase 15 must enumerate the snapshot population using the exact frozen Phase 13 participation semantics. It may reuse or extract a shared implementation primitive only when behaviour remains exactly equivalent to the Phase 13 contract. It must not define a second or weaker notion of participation.

Legacy snapshots without `run.observation_hour_utc` remain non-participating. Any participating candidate that makes the population malformed or unorderable under Phase 13 fails closed before a public window is selected.

No raw-snapshot rendering bypass is permitted. The selected window must be materialised as one canonical `crypto-observation-hour-series/v1` record and validated with `validate_observation_hour_series` from the same immutable repository context before rendering.

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

The selector must not use wall clock, workflow time, filesystem metadata, report titles, network state or mutable branch state.

Duplicate candidates for the selected end hour never elect a winner and never move the anchor backwards. The canonical duplicated hour remains the deterministic window end, while frozen Phase 13 semantics expose that selected slot as explicit ambiguity/gap evidence.

Missing, duplicate, invalid or otherwise unavailable evidence inside the 24 slots remains explicit. No slot may be filled, interpolated, skipped, replaced by an older slot, carried forward or backfilled.

## Separately governed trusted-main evidence prerequisite

The baseline trusted `main` contains zero Phase-13-participating observations, so site integration cannot yet truthfully produce the proposed public page.

Before the site-integration/public-proof slice may begin, separately governed source-evidence promotion must place at least one reviewed Phase-12-valid participating snapshot on trusted `main`.

That prerequisite:

- is repository-owned evidence merged into trusted `main` under its own authority;
- does not require 24 successful observations because absent hours remain explicit gaps;
- must not render directly from `automation/source-snapshot-rolling` or another mutable branch;
- must not mutate or backfill retained historical snapshots;
- must not reinterpret legacy snapshots as Phase-12-ready evidence;
- must not use Phase 14 `pilot`/`recurring`, deterministic-publication candidate automation or #477 as an implicit promotion path;
- requires its own governing authority for any repository mutation.

Contract, selector and renderer proof may proceed offline against deterministic fixtures before real trusted-main evidence exists. Public site integration remains gated until the prerequisite is independently satisfied.

If a later checked-out commit has zero participating observations, temporal-page generation must again fail closed rather than publish stale, fabricated, branch-only or legacy evidence.

## Renderer boundary

Phase 15 introduces one narrow public renderer boundary over validated Phase 13 evidence.

It may reuse Phase 11 visual/accessibility conventions or pure presentation helpers that carry no Phase 11 schema semantics. It must not:

- convert a Phase 13 record into a fake `crypto-temporal-series/v1` record;
- bypass `validate_observation_hour_series`;
- call an internal Phase 11 rendering path without its required Phase 11 validator;
- reinterpret any frozen Phase 11, Phase 12 or Phase 13 semantic contract.

The output must be deterministic semantic HTML with inline SVG and a complete evidence table. Meaning must not depend on colour alone. Gaps, degraded evidence and continuity breaks remain visibly attributable.

## Public-site integration

Integrate through the canonical `site_generator` pipeline rather than creating a parallel Pages build path.

The v1 surface is:

```text
one generated temporal.html page
one low-prominence homepage discovery link
```

The homepage link may be emitted only when `temporal.html` was successfully generated from the same checked-out repository commit.

Generated `_site/` remains disposable and uncommitted.

No Pages workflow permission, trigger, environment or deployment redesign is selected by this phase. Any implementation merge that affects the public site requires its separately governed review/merge and live verification gates.

## Public framing

Before the chart or market evidence is read, the temporal page must make clear that it is deterministic historical evidence in an AI/demo project and is not a forecast, investment research, recommendation, trading signal or market call.

No generated narrative or interpretation is added. Gaps and degraded evidence remain visible rather than being hidden for presentation quality.

## Non-goals

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
- no Pages workflow/permission change unless a later separately reviewed design proves it unavoidable.

## Acceptance gates

- [ ] Exact `phase15-public-temporal-evidence/v1` contract is frozen before implementation.
- [ ] Latest-window selection inherits exact Phase 13 participation semantics from one immutable repository commit.
- [ ] Malformed/unorderable participating population fails closed before window selection.
- [ ] Zero participating observations reject temporal-series and page generation with no fallback.
- [ ] The non-empty window is exactly 24 canonical slots ending at the maximum participating canonical observation hour.
- [ ] Duplicate candidates never elect a winner or move the window anchor backwards.
- [ ] Empty, malformed, non-empty deterministic selection, duplicate latest hour, internal missing-hour and repeatability paths have closed deterministic proof.
- [ ] Before site integration, trusted `main` contains at least one separately governed Phase-12-valid participating snapshot.
- [ ] Only repository-validated Phase 13 records can reach the renderer.
- [ ] Rendering preserves exact values/statuses, gaps, continuity and attributable provenance without derived trend analytics.
- [ ] Output is deterministic for the same repository tree/commit.
- [ ] Semantic HTML/inline SVG and the complete evidence table provide accessible equivalent evidence without JavaScript or network assets.
- [ ] Demo/non-advice framing appears before market evidence.
- [ ] Site integration is one dedicated temporal page plus the minimum discovery link, emitted only when the page succeeds from the same commit.
- [ ] No frozen Phase 10/11/12/13 contract, Phase 14 activation, #477 scope or report archive is changed.
- [ ] Generated `_site/` remains uncommitted.
- [ ] Exact-head repository validation succeeds for every implementation candidate.
- [ ] Genuinely fresh independent substantive review approves each merge candidate where required.
- [ ] Live Pages verification confirms deployed identity/content only after separately authorised site integration merge.

## Proposed implementation slices

1. **Roadmap promotion and delivery control** — promote this forward-looking spec and establish the parent Phase 15 delivery-control issue; no runtime change.
2. **Contract + deterministic renderer** — implement the exact-Phase-13-participation selector, closed proof corpus, direct Phase 13 validation and deterministic renderer; no public-site integration yet.
3. **Trusted-main evidence prerequisite** — if trusted `main` still has zero participants, establish a separately governed source-evidence promotion and independently verify at least one Phase-12-valid participant on `main`.
4. **Site integration** — add `temporal.html`, minimum homepage discoverability, focused accessibility/style coverage and complete site-build validation.
5. **Public proof + close-out** — separately authorised merge, Pages/live identity verification, delivery record and phase close-out.

Keep slices smaller when that improves reviewability. Do not collapse the separately governed trusted-main evidence prerequisite into renderer/site implementation merely to make the page buildable.

## Risks and mitigations

### Risk: Phase 15 duplicates or drifts from Phase 13 participation semantics

Mitigation: reuse or extract the exact Phase 13 primitive with equivalence proof; malformed/unorderable population fails closed.

### Risk: an empty trusted-main population creates a fabricated or stale public chart

Mitigation: zero participation produces no asserted series/page, and site integration is separately gated on real reviewed Phase-12-valid evidence on trusted `main`.

### Risk: duplicate latest-hour evidence is silently resolved

Mitigation: the maximum canonical participating hour remains the anchor; Phase 13 ambiguity is exposed as a gap with no fallback to an older hour.

### Risk: the Phase 11 renderer is reused across an incompatible schema boundary

Mitigation: use a narrow Phase 15 renderer that directly validates `crypto-observation-hour-series/v1`; reuse only schema-neutral presentation helpers/conventions.

### Risk: the public surface drifts toward a market product or advice

Mitigation: one BTC price series, one bounded page, minimal discovery, no narrative/forecast/advice, and visible demo/non-advice framing.

### Risk: Phase 15 implicitly operationalises Phase 14 or #477

Mitigation: both remain explicit non-goals and are prohibited as evidence-promotion shortcuts.

## Definition of done

Phase 15 is complete only when:

- [ ] the parent issue and required linked slice issues exist;
- [ ] implementation and proof candidates satisfy their exact acceptance gates and are merged under separate authority;
- [ ] the trusted-main evidence prerequisite is independently satisfied before site integration;
- [ ] the public temporal page is deployed and its exact live identity/content is verified;
- [ ] `planning/delivery/phase-15-public-deterministic-temporal-evidence.md` records what actually shipped and what remains excluded;
- [ ] `planning/delivery-log.md` is updated if required by the close-out decision;
- [ ] `planning/delivery/delivery.yaml` is updated or explicitly marked not applicable;
- [ ] `planning/delivery/graph.md` is regenerated when delivery YAML changes;
- [ ] roadmap files are updated only for material intent/scope/next-direction changes;
- [ ] generated `_site/` output is not committed.

## Follow-on delivery record

At close-out, create or update:

```text
planning/delivery/phase-15-public-deterministic-temporal-evidence.md
```
