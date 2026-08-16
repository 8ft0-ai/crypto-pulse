# Phase 11 — Deterministic temporal visualisation

Status: complete.

Primary outcome: CryptoPulse now has a deterministic offline temporal evidence layer over the frozen Phase 10 comparison boundary, with repository-bound validation, accessible semantic HTML/inline-SVG rendering, and a closed repeatability proof corpus. No provider, model, network, credential, report/site or publication path is required.

## Governance

```text
Shaping/design issue: #416
Frozen design: #416 comment 5304820349
Parent delivery-control issue: #418
Approved implementation plan: #418 comment 5305066681
Slice 1 issue / PR: #419 / #420
Slice 2 issue / PR: #421 / #422
Slice 3 issue / PR: #423 / #425
Close-out issue: #426
```

Phase 11 adopted `phase11-temporal-visualisation/v1` without relaxing Phase 10. The successful value path remains replay of the existing Phase 10 comparison builder under one immutable repository commit/tree and pinned validator/config identities.

## Delivered slices

```text
Slice 1 — canonical series builder + repository-bound validator
PR #420 merge: fbdf09cef53a5d3bd826118472fac25063d688d6

Slice 2 — deterministic accessible renderer
PR #422 merge: fc16e65dea5c8294748040fbda2650c2b7a91cbb
Exact-head validation: 31920585985

Slice 3 — closed offline proof corpus
PR #425 reviewed head: 7c707581c64cc804df53e749469132c9ab0b720c
PR #425 merge: 972ec1240d6f227798dca894a711028824c77645
Exact-head validation: 31922157164
Substantive approval: #423 comment 5305361850
Merge authority: #423 comment 5305363215
```

A temporary derivation head `81474219e1ba389d6f21441a2364d8facb683e6a` was used only to derive exact golden output identities for Slice 3. Its validation run `31921451119` failed exactly the predeclared golden-freeze assertion and exposed no production or frozen-contract defect. The final proof candidate replaced it with one atomic commit directly from trusted `main`.

## Shipped temporal-series contract

The canonical `crypto-temporal-series/v1` implementation preserves the frozen design:

- exact inclusive UTC-hour windows with at most 168 slots;
- immutable repository candidate enumeration and fail-closed handling of unorderable candidates;
- `current-missing` and complete deterministic `current-ambiguous` evidence;
- replay of the existing Phase 10 comparison path for every unique current slot;
- closed metric, source-status and gap vocabularies;
- numeric values only from replayed `comparison-available` + `comparable` current-side Phase 10 evidence;
- categorical source status kept separate from market movement;
- complete current/predecessor snapshot identity, quality and warning evidence;
- canonical UTF-8 JSON and deterministic full-record `series_id` hashing;
- no interpolation, resampling, aggregation, smoothing, moving averages, normalisation, rebasing, percentage conversion, carry-forward, backfill or inferred values.

Repository-bound validation re-enumerates immutable candidates and replays Phase 10 rather than trusting asserted values, status, provenance, ambiguity, comparison identity or `series_id`.

## Deterministic accessible renderer

The renderer accepts only a repository-validated canonical series and emits deterministic self-contained semantic HTML containing one figure, inline SVG, deterministic title/description/figcaption and a complete hourly evidence table.

Numeric continuity exists only when the later retained predecessor input is field-for-field identical to the earlier retained current input. Gaps and identity discontinuities break lines. Source-status evidence is categorical and uses text plus distinct marker shapes rather than a numeric market axis. Meaning does not depend on colour alone. The renderer uses no JavaScript, canvas, network resource or external asset and does not reopen snapshots or derive new market evidence.

## Closed offline proof

Slice 3 independently materialises synthetic immutable Git repositories and reruns the production builder, validator and renderer. It covers:

- continuous exact-hour numeric evidence;
- separately current- and predecessor-side `valid-degraded` evidence and warnings;
- `current-missing` and complete deterministic `current-ambiguous` identities;
- reachable Phase 10 failure mappings and all supported metric unavailable/invalid mappings;
- comparison-failure precedence and raw-value non-bypass;
- explicit gap breaks and exact predecessor/current identity continuity;
- categorical source-status history;
- complete accessible table equivalence;
- tamper, replay and unknown-vocabulary rejection;
- two independently materialised executions with byte-identical canonical series and renderer output.

Frozen proof output identities are:

```text
numeric canonical series: 6599 bytes
sha256: 8c7402db6690d888d9c5811e5d581fafd18b782d6ff8acf269d3b3511403b0d5

numeric renderer: 10645 bytes
sha256: a86ff5f22517ca5bc9a873a73cc5ee2d2b50c3e39ceca3ca5bc37cfdd69297db

source canonical series: 5393 bytes
sha256: 6a81ff5e9ff9b2e14e919b55cbc13f4b55728217e2418d6b77796e6bc36233a9

source renderer: 8182 bytes
sha256: 889f75b77990387321ab8d8b11314f4d56e3cb11894e60128d2f048413046661
```

Exact-head full repository validation `31922157164` succeeded for the final proof candidate.

## Boundaries preserved

Phase 11 did not change or authorise:

- Phase 10 predecessor, comparison, schema, semantic, quality or identity behaviour;
- the Phase 6 deterministic selector;
- source snapshots, acquisition or rolling/scheduled snapshot automation;
- providers, models, credentials or paid API use;
- reports, site rendering or `scripts/build_pages_site.py`;
- workflows, publication or auto-merge;
- committed generated `_site/` output;
- sentiment, forecasting, causality, support/resistance, technical levels, targets, watchlists or trading guidance.

The Phase 6 deterministic selector remains the sole active selector. Phase 9 remains closed with `no-stable-material-uplift`.

## Delivery graph disposition

`planning/delivery/delivery.yaml` and generated `planning/delivery/graph.md` are unchanged for Phase 11.

Disposition: **N/A under the existing compact causal graph rules**.

Phase 11 is an offline deterministic evidence/rendering capability and has not become a causal dependency of the active ingestion, report-generation, site-rendering or publication pipeline. Adding a disconnected Phase 11 implementation island would turn the compact graph into an implementation inventory rather than a causal delivery map.

## Carry-forward

Public/site integration of the proven temporal renderer remains parked in `planning/roadmap/backlog.md`. Broader visual market-card product work also remains parked. Any future integration requires a separately shaped and authorised phase.

No successor phase is selected or authorised by this close-out.
