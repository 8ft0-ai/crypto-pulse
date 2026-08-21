# Phase 15 — Public deterministic temporal evidence

Status: complete.

Primary outcome: CryptoPulse now publishes one deterministic, repository-bound historical `BTC.price_usd` temporal-evidence surface over exactly 24 canonical observation-hour slots through the existing static-site pipeline, with explicit gaps/provenance and visible AI-demo/non-advice framing, while leaving Phase 14 publication activation and all broader temporal-product scope separately parked.

## Governance

```text
Shaping issue: #479
Accepted design: current #479 issue body
Contract: phase15-public-temporal-evidence/v1
Fresh substantive design approval: #479 comment 5363860245
Owner successor / roadmap-promotion authority: #479 comment 5363896477
Roadmap promotion: #480 / PR #481
Parent delivery-control issue: #482
Slice 1 contract/selector/renderer proof: PR #483
Trusted-main evidence prerequisite: #484 / PR #488
Validation-trigger remediation: #486 / PR #487
Slice 3 public-site integration: #489 / PR #490
Slice 4 close-out: #491
Slice 3 Pages publication verification: #482 comment 5375652127
```

Phase 15 closes only the accepted narrow public temporal-evidence contract. It does not select or authorise a successor phase.

## Delivered contract and deterministic proof

PR #483 delivered the Phase 15 selector/materialiser and public renderer boundary after fresh substantive review.

```text
reviewed head: 31a6eda8a975bc8251ee4e57ad9cd30234bdec17
tree: 05d2ebd2b183a84d05dbc92646808444081691dd
merge: 3f39a2857cd1ba6df91f64077b1dff67788fa2b5
exact-head validation: 32451833403
validation job: 96681619786
fresh approval: PR #483 comment 5365789771
```

The delivered proof freezes the public surface to:

```text
series_kind: metric
series_key: BTC.price_usd
window_slots: 24 canonical UTC hours
contract: phase15-public-temporal-evidence/v1
```

The selector reuses the exact Phase 13 participating-population semantics from one immutable repository commit. Zero participation produces no asserted series. Malformed or unorderable participating evidence fails closed before window selection. For a non-empty population the maximum canonical participating observation hour is the deterministic end of the 24-slot window; duplicate candidates at that hour remain explicit Phase 13 ambiguity rather than electing a winner or moving the anchor backwards.

The public renderer directly invokes repository-bound `validate_observation_hour_series(repository_root, record)` before Phase 15 shape enforcement or output. Its semantic HTML, inline SVG and complete evidence table preserve exact Phase 13 values, gaps, continuity, current/predecessor identities, quality/warnings and provenance without interpolation, aggregation, smoothing, inferred trend or generated narrative. The closed proof covers zero and malformed populations, deterministic anchoring, duplicate latest-hour ambiguity, internal gaps, degraded evidence, direct-renderer tamper/replay rejection and independent-materialisation repeatability.

## Trusted-main evidence prerequisite

The accepted design prohibited public integration from inventing an anchor from legacy snapshots or a mutable rolling branch. The separately governed prerequisite was therefore satisfied by one reviewed repository-owned Phase-12-valid snapshot.

PR #488 merged exactly:

```text
data/crypto/hourly/2026/08/21/1549_AEST_source_snapshot.json
```

Evidence identities:

```text
source workflow run/job: 32451979070 / 96682021706
source commit: 8d2d3417371dd7ff2a9a1b10e3ec83b4e615a265
snapshot blob: 3908fb4e0f78b4688086158fc05d23dc33946191
snapshot SHA-256: c160c0bdc7610073f687ecbcba728fef70d8d6b48d0fde81193b8895897f3bd5
run.observation_hour_utc: 2026-08-21T05:00:00Z
reviewed head: 491a901f5fc3006815b1ef7a7cee1d11df8260d9
tree: 493d6aa030b137d0449e99c01f7703382ffe6a44
merge: 0a119deb5f44babe4239e693ac82d648801a3772
exact-head validation: 32484067027
validation job: 96776544736
fresh approval: PR #488 comment 5370258468
```

The evidence was additive only. No retained historical snapshot was modified, reinterpreted, backfilled, renamed or deleted. The mutable rolling source branch remained provenance/navigation only and never became public evidence authority.

## Public-site integration

PR #490 integrated the proven contract only through the existing canonical `site_generator` pipeline.

```text
reviewed head: 1eeb96cfe4db61edba414f53fe29f60e678513a0
tree: 1360abd2f0bda5b165ec888c71c76a85416e4fa7
merge: 99c4ced3001bb227d599173bb5a17011d23eea53
exact-head validation: 32525071794
validation job: 96905337127
fresh approval: PR #490 comment 5375474533
owner merge decision: PR #490 comment 5375578071
```

The integration resolves the checked-out commit once and uses that exact identity for Phase 15 materialisation, direct Phase 13 replay validation and rendering. `_site/temporal.html` and exactly one low-prominence homepage discovery link are emitted only together on success. Zero participation, malformed/unorderable evidence, commit mismatch/resolution failure, validation failure or renderer failure removes stale temporal output and publishes neither page nor link.

The public page puts historical AI-demo/non-advice framing before the evidence and explicitly states that the output is not a forecast, investment research, recommendation, trading signal, market call or financial advice. No JavaScript or network asset is required for the temporal evidence surface.

Generated `_site/` remains disposable and uncommitted.

## Pages publication proof

The merge of PR #490 automatically triggered the existing Pages workflow; no manual dispatch or Pages redesign was used.

```text
workflow: Publish CryptoPulse Pages
run: 32528437373
run number: 69
trigger: push to main
published commit: 99c4ced3001bb227d599173bb5a17011d23eea53
published tree: 1360abd2f0bda5b165ec888c71c76a85416e4fa7
build: success
deploy: success
Pages URL: https://8ft0-ai.github.io/crypto-pulse/
durable verification: #482 comment 5375652127
```

The exact deployed Pages artifact contains `temporal.html`, the expected repository commit identity, exactly one homepage discovery link, the required disclaimer before evidence and the complete 24-slot evidence table. GitHub Pages reported the deployment for the exact merged commit successful.

The execution environment used for close-out could not independently perform a second CDN HTTP fetch, so the durable verification correctly relies on GitHub's successful deployment state plus inspection of the exact deployed artifact rather than claiming an unperformed independent network fetch.

## Acceptance-gate disposition

All accepted `phase15-public-temporal-evidence/v1` gates are satisfied:

- exact Phase 13 participation semantics are reused from one immutable repository commit;
- malformed/unorderable and zero-participation states fail closed;
- the non-empty window is exactly 24 canonical slots anchored at the maximum participating canonical hour;
- duplicate latest-hour ambiguity, internal gaps, degraded evidence, provenance and continuity remain explicit;
- direct repository-bound Phase 13 validation is mandatory before public rendering;
- deterministic semantic HTML, inline SVG and the complete evidence table are proven without JavaScript/network assets;
- one reviewed Phase-12-valid participant was promoted to trusted `main` without historical mutation;
- public integration is exactly one temporal page plus one success-coupled low-prominence homepage link;
- exact-head repository validation and genuinely fresh substantive review succeeded for each merge candidate;
- automatic Pages deployment succeeded for the exact merged Slice 3 identity and the deployed artifact was verified;
- generated `_site/` remains uncommitted.

## Delivery graph disposition

Phase 15 is represented in the compact delivery graph because it closes the Phase 13 public-integration boundary and adds a durable public evidence surface to the active site pipeline.

The graph records only the Phase 15 parent/control, the representative public integration PR, the Pages proof run, the rendered public artifact and the enduring narrow public-evidence boundary. It deliberately does not model every child PR, remediation or source snapshot.

## Boundaries preserved

Phase 15 does **not**:

- change or reinterpret frozen Phase 10/11/12/13 semantic contracts;
- mutate or backfill historical snapshots;
- make a mutable rolling branch public evidence authority;
- activate Phase 14 `pilot` or `recurring` publication or perform work under #477;
- change Pages permissions, environments or deployment architecture;
- add model/provider invocation, credentials or external data sources;
- publish another metric/source-status series or broader market-card product surface;
- add generated narrative, forecast, causal analysis, recommendation, trading signal or advice-like behaviour;
- commit generated `_site/` output.

Phase 14/#477 operationalisation remains parked. Broader deterministic charts/market cards, additional series and every other backlog item remain separately governed future possibilities, not implicit follow-on work.

## Carry-forward

Phase 15 is complete.

CryptoPulse now has a small public proof that repository-owned Phase 13 temporal evidence can cross the site boundary deterministically and transparently. The enduring constraint is intentionally narrow: `metric / BTC.price_usd / 24 UTC-hour slots`, exact checked-out-commit authority, explicit gaps/provenance and demo/non-advice framing.

No active successor phase is selected by this close-out. Any future direction must return through normal shaping, fresh review and separate owner authority rather than inheriting Phase 15 implementation or merge authority.
