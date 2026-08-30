# Phase 17 — Trusted-main source-evidence accumulation and freshness

Status: complete.

Primary outcome: CryptoPulse can now deterministically accumulate immutable Phase-12-valid scheduled source evidence into bounded source-only candidates, promote one separately reviewed real candidate to protected `main`, prove the unchanged Phase 13 / 15 / 16 consumer and public chain against that promoted state, and refresh the disposable source-evidence candidate daily without granting automatic merge authority.

## Governance and delivery control

```text
Shaping issue: #516
Approved design: #516 comment 5418718664 — trusted-main-source-evidence-accumulation/v1.1
Fresh design approval: #516 comment 5425040365 — APPROVED
Owner roadmap/delivery decision: #516 comment 5425197783 — ACCEPT
Roadmap promotion: #521 / PR #522
Parent delivery-control issue: #523
Close-out plan: #523 comment 5471702402 — phase17-close-out-plan/v1
Close-out plan review: #523 comment 5471705380 — APPROVED
```

Protected `main` remained the sole public evidence authority throughout. Phase 17 changed the trusted source population and the candidate-refresh control plane; it did not create a second public authority.

## Slice A — deterministic accumulation and recovery

PR #526 delivered the pure `trusted-main-source-evidence-accumulation/v1.1` engine and closed offline proof corpus.

```text
Reviewed head: c6d563a9a2f9e367098aac88e4168a7ea0c5d4e4
Candidate tree: 32f22cd3ca2e7fd10bda9ce4e2a7c434f1f7a13b
Fresh approval: PR #526 comment 5434009034
Exact-head validation: 33033349524
Merge commit: 7b3be90cbc274dd83b5d797a1a8b0b3b13fab72b
Slice A close-out: #523 comment 5434544913
```

The engine binds exact base/tree identity, immutable run/attempt/artifact/snapshot provenance, current-main compatibility, canonical Phase-12 observation-hour identity, deterministic blocker/recovery identities and stable candidate materialisation. Duplicate evidence is never ranked into a winner; unavailable or invalid evidence never invents an hour; terminal recovery excludes exact unsafe evidence without promoting, backfilling or synthesising cursor movement.

## Slice B — source-only candidate builder

PR #527 delivered the bounded GitHub candidate-builder control plane around Slice A.

```text
Reviewed head: 4642bef5ebdec108c75e80e74e1146e5bfdf47f3
Fresh approval: PR #527 comment 5445043532
Exact-head validation: 33112753553
Merge commit: 244f6cfaf6e0a488a341340b0415f04a6a7f1888
Slice B close-out: #523 comment 5445216042
```

The initial Slice B boundary was manual `workflow_dispatch` only, with explicit recovery-comment IDs, additions-only `data/crypto/hourly/...` scope, complete retained-input population closure, exact Git-object replay/reclassification, force-with-lease candidate publication and no merge capability. No real accumulation candidate was created as part of implementation validation.

## Slice C — bounded real promotion

The first separately authorised real pilot dispatch, run `33119675314`, failed before canonical candidate evidence was produced. Its one-dispatch authority was consumed and was not reused. Remediation PR #528 was separately reviewed and merged before a new pilot plan and execution authority were established.

The successful real source-evidence candidate was PR #535:

```text
Reviewed base: 19a2126a0275a75067f84ae707e3a6f98e15537d
Reviewed candidate head: f7243428bce233e8bba7fdbc5e4e871ac26aae34
Candidate tree: fcff48a58822fecb530c6925135aa8e4be0b95fb
Candidate id: e02decaed27a95c4d416ca9f53366ad717ea186f4a3b89b55c39db38d9cf4256
Source-population closure SHA-256: 27c02d1b46c486f25b694b358e6d58fdb04478a9cc85689cd19527db72f0f9d5
Merge/protected-main commit: 877670ac6739fcfda1614c407a90c7417b1c7320
Protected-main tree: fcff48a58822fecb530c6925135aa8e4be0b95fb
Post-merge verification: PASS
```

The reviewed candidate contained 17 eligible/promoted canonical hours, 5 `no-promotable-observation` hours and 3 `terminal-excluded` hours with zero remaining blocking findings. Durable recovery decisions excluded 348 exact `source-input-unverifiable` blockers and 3 exact `duplicate-observation-hour` blockers; no excluded bytes were promoted and no duplicate winner or missing hour was synthesised.

An early Slice C verification comment misstated the `AGENTS.md` blob. The subsequent correction established the repository-local authority blob as `c84f5e71bfab7f0825c5a1bcc921bebc8724c926`; no other Slice C conclusion changed.

## Slice D — unchanged consumer and public proof

Slice D proved that the promoted trusted-main population flowed through the existing consumer/public path without changing Phase 13, Phase 15 or Phase 16 semantics merely to make the output appear fuller.

```text
Durable final disposition: #523 comment 5471238860 — PASS
Stage A proof run: 33307381837 / #3
Stage B Pages run: 33333144803 / #74
Stage C1 automatic live run: 33333182395 / #9
Stage C2 manual live run: 33333262565 / #10
```

Stage B built and deployed the exact frozen source-promoted state. Both live-verification evidence sets were bound to that deployment and proved HTTP 200 for the canonical pages, no verifier failures, no broken navigation, zero serious accessibility violations, zero unnamed controls and no Axe violations. C1 was independently proven as the automatic `workflow_run` path rather than being inferred through the manual-live operator shortcut.

## Slice E — recurring candidate-refresh decision

After Slice C/D proof, the separate owner decision selected `DAILY_CANDIDATE_REFRESH`.

```text
Decision package: #523 comment 5471266851
Fresh package review: #523 comment 5471271838 — APPROVED
Owner selection: #523 comment 5471296088 — DAILY_CANDIDATE_REFRESH
Implementation PR: #539
Approved head: 144c46d7957ffb9f7e2ddc6826f0ca285a42e9d7
Exact-head validation: 33336540615 / #679
Fresh implementation approval: PR #539 comment 5471393023
Owner merge decision: PR #539 comment 5471595854
Merge commit: 948ba28b965d9c3c9e5760af89f7367503f2a84f
Merge tree: a7bacf69e2639e2a7563b56bccd2b4ac3886f2cb
Merge result: #523 comment 5471600336 — MERGED / PASS
Configured cron: 47 0 * * * UTC
```

Fresh review found an empty-manual-input fallback edge in the first implementation candidate. It was corrected before approval; the final head received a new complete validation run. The merged schedule derives a scheduled candidate base from exact event `github.sha`, rechecks live protected main before preparation/publication, supplies no scheduled recovery authority, and retains manual inputs for explicitly governed recovery use.

Daily automation may create or refresh only the disposable source-evidence candidate. Every candidate remains separately subject to exact-head validation, fresh substantive review, a separate owner merge decision and an expected-head merge guard.

## Produced and enduring artefacts

- `scripts/trusted_main_source_evidence_accumulation.py` — pure deterministic accumulation/recovery authority.
- `scripts/trusted_main_source_evidence_candidate.py` — candidate preparation/replay/control helper.
- `.github/workflows/build-trusted-main-source-evidence-candidate.yml` — manual plus daily candidate refresh, with no merge capability.
- Phase 17 unit/proof fixtures and contract tests.
- the 17 exact reviewed source snapshots promoted by PR #535 to protected `main`.
- durable Slice A–E governance, review, execution and proof records under #523.

## Boundaries preserved

Phase 17 does not:

- make a mutable candidate/rolling branch public evidence authority;
- automatically merge a source-evidence candidate;
- infer or reconstruct missing evidence, elect a duplicate winner, backfill history or advance a synthetic cursor;
- reinterpret Phase 12, Phase 13, Phase 15 or Phase 16 evidence/reader semantics;
- activate Phase 14 deterministic publication or #477;
- add provider/model/credential/report-generation authority;
- add forecasts, recommendations, signals, technical levels or personalised guidance;
- claim public data is live/current/up to date merely because the repository population is fuller;
- commit generated `_site/` output.

Protected `main` remains the sole public evidence authority, and exact Phase-12-valid snapshot bytes remain the only canonical observation-hour authority.

## Delivery graph disposition

Phase 17 is represented in the compact delivery graph because it materially changes the causal source-evidence spine and creates an enduring candidate-refresh/no-auto-merge boundary. The graph records only the parent phase, representative real promotion, representative public proof, accumulation artefact and preserved automation boundary; the many recovery comments, individual source files, remediation attempts and additional Slice D runs remain in the canonical GitHub audit trail rather than becoming graph inventory.

## Carry-forward

No successor phase is selected by this close-out. Phase 14/#477 operationalisation, broader temporal/market-card scope, model/provider work, advice-like features and other backlog items remain parked.

The enduring operational rule is: scheduled automation may prepare a source-only candidate, but only protected-main evidence merged under exact candidate-specific human governance becomes public evidence authority.
