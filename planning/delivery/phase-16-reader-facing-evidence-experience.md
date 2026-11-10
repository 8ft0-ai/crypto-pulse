# Phase 16 — Reader-facing evidence experience

Status: complete.

Primary outcome: CryptoPulse now presents repository-owned evidence through one coherent reader-facing Home / Most recent / Temporal evidence / Archive experience while keeping canonical report chronology, deterministic current-observation authority, archived report authority and the frozen Phase 15 temporal record explicitly separate.

## Governance

```text
Contract: reader-facing-evidence-experience/v1
Primary delivery control: #501
Combined Slice 1: #502 / PR #505
Combined Slice 2: #503 / PR #506
Combined Slice 3: #504 / PR #507
Final public proof: #504 comments 5385594175 and 5385606902
Close-out implementation authority: #501 comment 5385624782
```

The phase closes only the approved reader-facing evidence contract. It does not select or authorise a successor phase.

## Delivered slices

### Combined Slice 1 — canonical reader authority + Home / Most recent

PR #505 delivered one canonical report chronology and one shared reader-evidence context for Home and `latest.html`.

```text
reviewed head: c9bb192a300d893fcee84b5bccf855298f75cfef
tree: 43798a45bac5e31db7b89b8c0bea36ff9a7a0c7e
merge: 9d37798b391b3cf37e76d0d234ad5cb0738df449
exact-head validation: 32622782169
validation job: 97153421414
fresh approval: PR #505 comment 5384679137
```

The delivered chronology fixes the normative `2031_AEST.md` / `1742_AEST.md` ordering defect and keeps unsupported duplicate instants fail closed. The separately approved retained-legacy alias amendment permits one logical chronology event only when every alias independently validates to the same instant and the aliases are equivalent outside the bounded timestamp/data-cutoff representation, without mutating historical reports.

Home and `latest.html` now consume one exact-checkout reader context. Deterministic BTC/ETH/SOL values, evidence status and provenance remain bound to the selected Phase 13 observation; report title, body, citations and generation semantics remain bound to the canonical latest report; association exists only on exact governed `source_snapshot` equality.

### Combined Slice 2 — temporal reader-state projection + presentation

PR #506 preserves the frozen `phase15-public-temporal-evidence/v1` authority and adds only its reader projection.

```text
reviewed head: ddf519f218a74242a9fc2731bee6c74f45e5c082
tree: 614f5482d1c4121c0242e15e1907676ca0b8485d
merge: 546927212c831bd0bfa124db86d0d68f05a7d61f
exact-head validation: 32630137655
validation job: 97171546189
fresh approval: PR #506 comment 5385263900
```

The reader projection exposes exact value, gap, degradation and continuity counts from the replay-valid 24-slot record. Empty windows produce no chart or synthetic extrema; isolated values are not joined; line segments exist only across exact continuous adjacent asserted values; gaps are never bridged; and the complete 24-slot evidence remains inspectable.

### Combined Slice 3 — Archive reader model + navigation integration

PR #507 delivers canonical Archive chronology, truthful retained discontinuity, separate generation/evidence taxonomy, deterministic repository-backed filters, developer-output demotion and coherent navigation.

```text
reviewed head: 4a75e88ba42fa706589e5c3a70acb4f2a5eaea7b
tree: 123a04572a5099512cdb52deafb94048db62c90f
merge: ee46ae895036b60bccfab99e4f462bf5f53c15cd
exact-head validation: 32632856711
validation job: 97178143732
fresh approval: PR #507 review 5002168400
```

Archive consumes the Slice 1 chronology rather than creating a second recency rule. It no longer implies continuous hourly retention, does not heuristically normalise legacy report prose into deterministic BTC/ETH market fields, remains readable without JavaScript, and uses JavaScript only as local progressive filtering over generated attributes.

## Exact public proof

The final Slice 3 merge automatically triggered the existing Pages workflow.

```text
workflow: Publish CryptoPulse Pages
run: 32633849094
published commit: ee46ae895036b60bccfab99e4f462bf5f53c15cd
build job: 97180544420 — success
deploy job: 97180592436 — success
Pages artifact: 9491771705 / github-pages
artifact digest: sha256:1f105dd2979dd6e793e939ad9f18dfcd840a9866d8eda956227625b5c906e9c0
Pages URL: https://8ft0-ai.github.io/crypto-pulse/
```

Deployment logs recorded `pages_build_version` exactly `ee46ae895036b60bccfab99e4f462bf5f53c15cd` and a successful deployment for that identity.

The exact deployed artifact and a separate live-URL observation matched byte-for-byte for every required public surface:

```text
index.html:
403df9e9d5ae32fbad6254c71349793809c83ed8dbc27a62f381b47c30956f99

latest.html:
44fe762868b795617c6a1e8dab6479d38478d5658b64676e5f0362ae1fc5d0c1

archive/index.html:
47bb426c475d8cf02dce77580d42461bd3fd7e8bf4ba709439c6c994be22d362

temporal.html:
308ed68b1cd0b1d0f8d3064ee32aa431fd119a4ade9543dc12380542382cb8c7
```

The deployed result proves the `2031_AEST` chronology behaviour, Home/latest authority separation, sparse temporal semantics, Archive discontinuity/taxonomy and the required pre-claim demo/non-advice boundary.

## Boundaries preserved

Phase 16 does **not**:

- activate #497 T2 source-evidence accumulation or promotion;
- activate Phase 14 `pilot` / `recurring` publication or #477 operationalisation;
- introduce a mutable rolling branch as public authority;
- reinterpret frozen Phase 10/11/12/13/15 contracts;
- add providers, models, credentials or model invocation;
- add temporal series, derived analytics, forecasts, recommendations, signals or personalised guidance;
- mutate or backfill historical source/report evidence;
- redesign Pages permissions or publication authority;
- commit generated `_site/` output.

The existing public site remains an AI-generated demo. Market claims remain behind the visible possible-inaccuracy / non-advice / non-research / non-recommendation / non-signal boundary.

## Delivery graph disposition

Phase 16 is represented compactly in the delivery graph because it closes the reader-facing public integration over the Phase 13/15 evidence foundations. The graph records the parent control, representative final integration PR, exact Pages proof, public reader artifact and enduring authority boundary rather than every slice detail.

## Carry-forward

Phase 16 is complete.

No Phase 17 or other successor is selected by this close-out. #497 T2, Phase 14/#477 operationalisation, broader temporal analytics, model/provider work and trading-oriented features remain parked and require normal shaping, fresh review and separate owner authority before any future promotion.
