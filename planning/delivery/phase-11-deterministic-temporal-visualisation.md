# Phase 11 — Deterministic temporal visualisation

Status: complete.

Primary outcome: CryptoPulse now has a deterministic offline temporal evidence and accessible rendering capability built only from replayed Phase 10 comparison evidence, with explicit gaps, immutable provenance, exact continuity binding and no provider/model/network dependency.

## Governance

```text
Shaping/design issue: #416
Frozen design: #416 comment 5304820349
Parent delivery-control issue: #418
Approved four-slice plan: #418 comment 5305066681
Close-out issue: #428
Slice 4 authority: #418 comment 5305368385
History-only state reconciliation: #418 comment 5305399301
Phase 11 design: phase11-temporal-visualisation/v1
Series contract: crypto-temporal-series/v1
Phase 10 comparison contract: crypto-snapshot-comparison/v1
Phase 10 predecessor policy: phase10-predecessor-exact-hour/v1
Phase 10 semantic contract: phase10-snapshot-semantics-0.2/v1
```

The Phase 11 design was independently accepted before implementation planning. Delivery remained additive: Phase 10 contracts and production files were not changed to make Phase 11 pass, and every implementation/proof slice was separately bounded, validated and reviewed before merge.

## Delivered slices

```text
Slice 1 issue: #419
Slice 1 PR: #420
Slice 1 reviewed head: b4bc86df42b7ce4fc70f42018d440c2f294341b5
Slice 1 exact-head validation: 31919416387
Slice 1 merge: fbdf09cef53a5d3bd826118472fac25063d688d6

Slice 2 issue: #421
Slice 2 PR: #422
Slice 2 reviewed head: 6affe16a20dea0ca8662712bf9299891af64b5f5
Slice 2 exact-head validation: 31920585985
Slice 2 merge: fc16e65dea5c8294748040fbda2650c2b7a91cbb

Slice 3 issue: #423
Slice 3 proof PR: #425
Slice 3 reviewed head: 7c707581c64cc804df53e749469132c9ab0b720c
Slice 3 exact-head validation: 31922157164
Slice 3 merge: 972ec1240d6f227798dca894a711028824c77645

Close-out issue: #428
```

A temporary non-reviewable derivation head was used only to obtain exact expected proof bytes. Run `31921451119` executed 656 unit tests and failed exactly one deliberately predeclared golden-freeze assertion; no substantive production or frozen-contract defect was exposed. The final proof candidate replaced that derivation state with one atomic two-file commit from the trusted base.

During close-out preparation, an accidental connector write was immediately neutralised by a second commit. Current close-out base `17e2a9fba0b320cf11e029871018d3bef91624c4` is two history-only commits ahead of the Slice 3 merge with no changed files and the exact same tree `2ece1b6ddccc2bef68c83777475d1f24a2a5817d`. The reconciliation is recorded on #418 and does not change Phase 11 content or authority.

## Shipped canonical series contract

Phase 11 ships the frozen `crypto-temporal-series/v1` boundary:

- one immutable repository commit/tree plus pinned Phase 10 validator/config blob identities bind each series;
- inclusive UTC windows require exact hour alignment and contain at most 168 hourly slots;
- every requested hour appears exactly once in ascending order;
- zero current candidates produce `current-missing`;
- multiple current candidates produce `current-ambiguous` with every competing exact candidate identity retained deterministically;
- a unique current candidate is evaluated only through the existing Phase 10 `build_comparison_record(...)` path;
- raw snapshot metrics are never an alternate successful value path;
- non-available Phase 10 states and supported metric unavailable/invalid states map to the frozen explicit gap vocabulary with fixed precedence;
- numeric values require replayed `comparison-available` plus `comparable` Phase 10 metric evidence and retain the exact current-side datum;
- source-status values remain categorical `ok`, `warning`, `error`, `skipped` or `missing` evidence and are never converted into market movement;
- current and predecessor snapshot identity, `quality_status` and `non_blocking_warnings` remain separately attributable;
- canonical UTF-8 JSON and lowercase SHA-256 `series_id` bind the complete record excluding only `series_id` itself.

The repository-bound validator re-enumerates immutable slot candidates and replays Phase 10. It does not trust asserted `comparison_id`, value, status, identity, ambiguity evidence, warning evidence or `series_id` as attestation.

## Deterministic accessible renderer

The merged renderer accepts only a repository-bound validated canonical series record and emits deterministic, self-contained semantic HTML containing:

```text
figure
inline SVG
figcaption
complete adjacent hourly evidence table
```

No JavaScript, canvas, network resource or external asset is required.

Numeric lines connect only when the later point's retained predecessor record is field-for-field identical to the earlier point's retained current record. Explicit gaps and identity discontinuities break line segments. Source-status history uses categorical labels and distinct marker shapes without a numeric market axis. Gap, degraded and categorical meaning is not dependent on colour alone.

The complete table exposes every slot's timestamp, exact value/status or gap, current/predecessor quality and warnings when present, concise provenance and ambiguity candidate identities.

## Closed offline proof

PR #425 adds the synthetic `phase11-temporal-series-proof-corpus/v1` corpus and independently materialises immutable Git repositories before rerunning the merged builder, repository-bound validator and renderer.

The proof covers:

- continuous exact-hour numeric history;
- independently attributable current-side and predecessor-side `valid-degraded` evidence and warnings;
- `current-missing` and deterministic complete `current-ambiguous` evidence;
- every reachable non-available Phase 10 status and frozen `phase10-*` mapping;
- all supported metric unavailable/invalid mappings;
- comparison-level failure precedence over metric/source fallback classification;
- raw snapshot value non-bypass;
- explicit gap line breaks and exact predecessor/current identity continuity;
- categorical source-status history without numeric conversion;
- complete accessible table equivalence;
- tamper rejection for values, provenance, warnings, ambiguity evidence, comparison IDs, derived fields and `series_id`;
- unknown vocabulary and replay-disagreement rejection;
- two independently materialised executions producing byte-identical canonical series and renderer output.

The accepted frozen exact-byte identities are:

```text
numeric canonical series: 6599 bytes / 8c7402db6690d888d9c5811e5d581fafd18b782d6ff8acf269d3b3511403b0d5
numeric renderer:         10645 bytes / a86ff5f22517ca5bc9a873a73cc5ee2d2b50c3e39ceca3ca5bc37cfdd69297db
source canonical series:  5393 bytes / 6a81ff5e9ff9b2e14e919b55cbc13f4b55728217e2418d6b77796e6bc36233a9
source renderer:           8182 bytes / 889f75b77990387321ab8d8b11314f4d56e3cb11894e60128d2f048413046661
```

Exact-head repository validation `31922157164` succeeded for the final proof candidate.

## Boundaries preserved

Phase 11 did not change or authorise:

- Phase 10 predecessor, comparison, snapshot-schema, semantic, quality or identity behaviour;
- Phase 6 deterministic selector behaviour;
- source snapshots, historical source evidence, acquisition or rolling/scheduled snapshot automation;
- providers/models, credentials, secrets or paid API use;
- report generation, reports/site rendering or `scripts/build_pages_site.py`;
- workflows, publication or auto-merge;
- generated `_site/` output;
- interpolation, resampling, aggregation, smoothing, moving averages, normalisation, rebasing, percentage conversion, forecasting, carry-forward/back-fill or inferred values;
- sentiment, causality, support/resistance, technical levels, targets, watchlists or trading guidance.

Phase 11 proof is synthetic, network-free, credential-free and provider/model-free. Historical snapshots were not edited to manufacture continuity or failure cases.

## Delivery graph disposition

`planning/delivery/delivery.yaml` and generated `planning/delivery/graph.md` are unchanged for Phase 11.

Disposition: **N/A under the existing compact causal graph rules**.

Phase 11 is an offline evidence/rendering capability and has not become a causal dependency of ingestion, report generation, site rendering or publication. Adding a disconnected Phase 11 node would model implementation inventory rather than the active causal delivery path.

## Carry-forward

The offline deterministic temporal capability is proven and complete. Public/site chart integration remains parked and requires a later separately governed phase if pursued. No successor phase is selected or authorised by this close-out.
