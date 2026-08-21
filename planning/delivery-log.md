# Delivery log

This log records completed CryptoPulse delivery phases in one place. It is a curated management record, not a replacement for the canonical GitHub issue, pull-request, commit, and workflow history.

## Pre-phase baseline — before formal Phase 1

Status: complete.

Primary outcome: useful early repository history is preserved without rewriting it as a formal delivery phase.

```text
Baseline record: planning/delivery/pre-phase-baseline.md
Representative foundational issues: #1, #6, #7, #8, #44, #45, #63, #64, #65
Representative foundational PRs: #2, #3, #4, #5, #9, #12, #13, #46, #51, #69, #71
Representative process-learning issues/PRs: #11/#14, #21/#22, #27/#28, #36/#37/#38
Graph edge: pre-phase-baseline -> phase-1, enabled formal phase delivery
_site committed: no
```

Delivery notes:

- Phase 1 remains the first formal phase-managed delivery phase.
- The pre-phase baseline captures early demo positioning, site UX, repository guidance, PR discipline, ingestion MVP work, scheduled ingestion automation, and snapshot quality hardening.
- The delivery graph intentionally models this as one compact baseline node rather than a node for every early PR.

## Phase 1 — Source evidence spine

Status: complete.

Primary outcome: scheduled ingestion can produce a scoped `valid-ok` source snapshot PR.

```text
Known parent issue: #75
Key proof PR: #89
Workflow run: https://github.com/8ft0-ai/crypto-pulse/actions/runs/28926128310
Snapshot path: data/crypto/hourly/2026/07/08/1742_AEST_source_snapshot.json
Snapshot quality: valid-ok
Selected exchange cross-check: coinbase_exchange
Merge commit: 178703aef4be8fc0ecf35677e1ffeffe7d4d4a52
```

Delivery notes:

- Source snapshots are archived under `data/crypto/hourly/...`.
- Snapshot validation records required source status, optional exchange cross-check status, disabled sources, warnings, and blocking issues.
- The source snapshot PR did not generate a Markdown report and did not commit `_site/`.

## Phase 2 — Deterministic report review loop

Status: complete.

Primary outcome: a merged `valid-ok` source snapshot can produce a reviewed deterministic Markdown report PR and can be rendered by the static site generator without committing generated `_site/` output.

```text
Parent issue: #90
Child issues: #91, #92, #93, #94, #95, #96, #97
Key implementation PRs: #99, #100, #101, #102, #103
Generated report PR: #104
Report workflow run: https://github.com/8ft0-ai/crypto-pulse/actions/runs/28940526728
PR validation run/job: https://github.com/8ft0-ai/crypto-pulse/actions/runs/28940544039/job/85861945926?pr=104
Generated report path: reports/crypto/hourly/2026/07/08/1742_AEST.md
Expected rendered path: _site/archive/2026/07/08/1742_AEST.html
Report merge commit: f6083aff44377b6819ce66d56da848e289124eb8
_site committed: no
```

Delivery notes:

- `scripts/validate_crypto_report.py` now gates deterministic report structure, source linkage, product-boundary language, evidence/source status, and prohibited advice-like phrasing.
- Real fixture coverage uses the merged PR #89 source snapshot.
- Generated report PRs carry review evidence and explicit scope limitations.
- `python -m site_generator` remains the canonical static site build command.
- `_site/` remains disposable generated output and must not be committed.

## Phase 3 — Self-proving generated report PRs

Status: complete.

Primary outcome: generated report PRs now carry their own pre-PR proof from the report-generation workflow, with downstream PR validation retained as defence in depth.

```text
Parent issue: #115
Close-out issue: #123
Implementation issues: #116, #117, #118, #119, #120, #121
Proof issue: #122
Key implementation PRs: #124, #125, #126, #129, #130, #131
Generated report proof PR: #132
Generated report workflow run: https://github.com/8ft0-ai/crypto-pulse/actions/runs/28999816016
Generated report path: reports/crypto/hourly/2026/07/08/2031_AEST.md
Rendered archive path: _site/archive/2026/07/08/2031_AEST.html
Downstream PR validation run: https://github.com/8ft0-ai/crypto-pulse/actions/runs/29000320882
Generated report merge commit: 5a77e5aa315f72c76363a7286396c67c8ec43405
_site committed: no
```

Delivery notes:

- Generated report PR bodies now use `scripts/build_report_pr_evidence.py` to render deterministic self-proof evidence.
- The generated report workflow validates the source snapshot, generates the Markdown report, validates the generated report, runs unit tests, builds the static site, verifies the rendered archive path, inspects changed files, validates changed-file scope, builds PR evidence, and only then opens the generated report PR.
- PR #132 proved the flow end to end using a `valid-ok` snapshot and changed exactly one raw Markdown report file.
- Downstream PR validation still ran and passed as defence in depth.
- Phase 3 did not introduce a GitHub App token, personal access token, auto-merge, auto-publish, committed `_site/` output, LLM-generated report narrative, investment advice, secrets, or paid API keys.

## Post-Phase 3 operating-model tidy-ups

Status: complete.

Primary outcome: the demo keeps running with less review inventory, and the planning layer now has explicit close-out and graph-modelling rules.

```text
Rolling source snapshot PR issue: #149
Rolling source snapshot PR: #152
Planning close-out guidance issue: #150
Planning close-out guidance PR: #154
Delivery graph modelling rules issue: #151
Delivery graph modelling rules PR: #155
Rolling source snapshot branch: automation/source-snapshot-rolling
Rolling source snapshot PR title: Update rolling crypto source snapshot
_site committed: no
```

Delivery notes:

- #149 changed scheduled ingestion from creating a new generated snapshot PR every run to updating one rolling source snapshot PR.
- #150 codified that phase close-out PRs must update the relevant planning delivery record, delivery log, delivery YAML, and generated graph where applicable.
- #151 documented that the delivery graph is a compact causal map, not a complete issue or PR inventory.

## Phase 4 — Live-site provenance UX

Status: implementation complete; public live-site fetch requires external confirmation.

Primary outcome: CryptoPulse now leads with provenance, generation boundaries and schema-aware rendering rather than placeholder-heavy market commentary.

```text
Parent issue: #160
Close-out issue: #165
Implementation issues: #161, #163, #162, #164
Implementation PRs: #166, #167, #168, #169
Validation runs: 29081901945, 29082778088, 29083425572, 29084860287
Delivery record: planning/delivery/phase-04-live-site-provenance-ux.md
Configured live URL: https://8ft0-ai.github.io/crypto-pulse/
Delivery graph update: N/A under compact causal graph rules
_site committed: no
```

Delivery notes:

- Homepage extraction excludes product-boundary boilerplate and suppresses unavailable retired fields.
- Report pages surface source quality, provenance and generation boundaries before extracted summaries and full report content.
- Homepage hierarchy now explains the demo and its auditable publishing model before report and archive scanning.
- Archive cards show hourly timestamps and stable BTC, ETH and data-quality slots where available, with non-colour direction and status cues.
- Focused tests and all four implementation PR validation runs passed.
- A direct public HTTP smoke test was attempted during close-out, but the execution environment could not resolve the GitHub Pages host. This limitation is recorded rather than treated as a pass.
- Issue #165 and parent #160 should close only after an external browser confirms the homepage, latest report, archive and search pages on the deployed site.

## Phase 6 — Deterministic claim candidates and bounded model selection

Status: complete.

Primary outcome: repository code now owns claim-candidate semantics, deterministic ranking, plan reconstruction, validation and rendering; the deterministic selector remains the sole active selection path.

```text
Parent issue: #283
Governance transition: #282 / PR #284
Implementation issues: #285, #287, #289, #291, #293, #295
Implementation PRs: #286, #288, #290, #292, #294, #296
Corrective transport: #300 / PR #301
Protected comparison runs: 30771922641, 30777564268
Final decision: #310 / PR #311
Decision merge: 06320a5598f630a04c3d88353fe7d18361d2fa89
Delivery record: planning/delivery/phase-06-deterministic-claim-selection.md
Delivery graph update: N/A under compact causal graph rules
_site committed: no
```

Delivery notes:

- The versioned candidate contract gives repository code complete ownership of evidence references, intent, operands, comparison relation, subject, section, confidence and stable identity.
- The compiler produced 100% recall over 38 reviewed useful expectations across five frozen cases while excluding 20 prohibited combinations.
- The permanent deterministic baseline selected 35 candidates, including 26 reviewed-useful candidates, for 74.29% precision, 68.42% recall and 71.23% F1; all five plans validated and rendered without a provider call.
- The optional model boundary accepted candidate IDs only, enforced exact validation and at most one semantic repair, and proved byte-identical deterministic fallback across 15 offline fallback scenarios.
- Protected run `30771922641` failed closed when the first full-catalogue corpus call cost USD 0.23914375 against the fixed USD 0.12 cap.
- Corrective PR #301 retained the full candidate set and introduced compact transport, revised output limits and decisive fallback stopping without enabling a model.
- Final run `30777564268` retained three incomplete GPT diagnostic repeats, then failed closed when the next exact-route call cost USD 0.15841625 against the fixed USD 0.15 cap. Total reported final-run spend was USD 0.37542275. No Nex corpus call occurred.
- The comparison is formally `inconclusive-infrastructure`; no formal GPT Gate A or Nex deployment conclusion is claimed.
- The reviewed roadmap decision removes bounded model selection from the active roadmap and retains deterministic selection as the only supported active selector.
- No further paid Phase 6 run, provider substitution, third model, prompt retuning or cost-ceiling increase is authorised.
- The obsolete paid comparison workflow is archived during close-out while configuration, prompts, schemas, runners, scoring code, documentation, Git history and protected artifact references remain auditable.
- Automatic report generation and publication remain disabled and separately governed.

## Phase 9 — GPT-OSS quality and stability comparison

Status: complete.

Primary outcome: the governed GPT-OSS 120B / DeepInfra comparison terminates as `no-stable-material-uplift`; deterministic selection remains the sole active selector and the temporary paid Phase 9 workflow is archived.

```text
Parent issue: #352
Implementation PR: #355
Canonical decision: #389
Paid-workflow archival: #390 / PR #391
Roadmap decision: #392 / PR #394
Close-out issue: #395
Dispatcher run: 31867552577
Protected run: 31867564494
Trusted execution SHA: 43c69ed122c4e39cf2dda92bfcefa7e4314b3922
Protected run attempt: 1
Outcome: no-stable-material-uplift
Attempted paid calls: 1
Accepted calls: 0
Unattempted calls: 14
Observed cost: USD 0.000953014
Prepared artefact: 9242467310
Protected comparison artefact: 9242498501
Delivery record: planning/delivery/phase-09-gpt-oss-quality-comparison.md
Delivery graph update: N/A under compact causal graph rules
_site committed: no
```

Delivery notes:

- The first Stage A call reached exact model `openai/gpt-oss-120b` on pinned DeepInfra successfully with one router attempt, no fallback, no retry, no semantic repair and no route probe.
- Canonical reconstruction/validation then failed the frozen candidate-section contract because five selected IDs mapped to `key_observations`, where the maximum is four.
- #352 predeclared this model-content/candidate-contract failure class as terminal `no-stable-material-uplift`, not `inconclusive-infrastructure`.
- The remaining fourteen calls were unattempted; aggregate quality, case-level, stability, stable-majority and incremental-value promotion metrics remain `partial-non-adjudicable` / `not_adjudicable` and were not threshold-tested or imputed.
- Prepared artefact `9242467310` retains digest `sha256:69eef6f0989a61865e59210e97ec7187865243834cc1cee014013eff441a42f8`.
- Protected comparison artefact `9242498501` retains digest `sha256:4664e6dbff016aad2e60473728545ee08f9da5094f5ca79b8cea766e4fa8b073`.
- Earlier infrastructure failures were handled through separately governed one-time recovery lifecycles and bounded remediations without changing the frozen quality, stability, incremental-value, call or cost gates.
- The canonical decision authorises no Phase 9 rerun or recovery-v5 and does not promote GPT-OSS 120B or DeepInfra into operational selection.
- PR #391 archives `.github/workflows/governed-gpt-oss-quality-comparison.yml` from executable `main` while retaining configuration, implementation, tests, historical commits and protected evidence for audit.
- PR #394 durably records the accepted decision in `planning/roadmap/phase-09-gpt-oss-quality-decision.md`.
- Historical consumed IssueOps authority records and immutable execution tags remain audit evidence and are not rewritten by close-out.
- Automatic report generation, scheduling and publication remain disabled.
- `planning/delivery/delivery.yaml` and generated `planning/delivery/graph.md` are not changed because Phase 9 adds no new production pipeline stage or committed runtime artefact; representing its execution/recovery history in the compact graph would be an implementation inventory rather than a causal delivery node.

## Phase 10 — Deterministic previous-hour comparison engine

Status: complete.

Primary outcome: repository code now produces deterministic, fail-closed previous-hour comparison evidence from one current snapshot and its uniquely resolved immediate predecessor under the frozen exact-hour contract.

```text
Parent issue: #400
Close-out issue: #412
Planning issues: #401, #404, #406, #409
Implementation/proof PRs: #403, #405, #407, #410
Corrective reconciliation: #402
Close-out semantic correction: #411 / PR #413
Proof merge: 873df207b81afb8c9a0fa2a2410b4683136b1e02
Proof exact-head validation: 31911287479
Final corrective merge: 47c92d2cb8849bf673763bf31f4caf2406ef49eb
Final corrective exact-head validation: 31913953865
Proof corpus: phase10-comparison-proof-corpus/v1 — 14 ordered cases
Delivery record: planning/delivery/phase-10-previous-hour-comparison.md
Delivery graph update: N/A under compact causal graph rules
_site committed: no
```

Delivery notes:

- `phase10-predecessor-exact-hour/v1` selects the greatest strictly prior `run.generated_at_utc` candidate from one immutable repository tree, never skips the immediate predecessor, and accepts exactly `3,600` elapsed seconds with no tolerance or fallback.
- Snapshot identity is bound to repository path, exact bytes, schema and authoritative UTC time; validator/config blob identities are pinned, with `valid-ok` and `valid-degraded` evidence preserved.
- `crypto-snapshot-comparison/v1` emits deterministic fixed-order metric/source evidence and a canonical full-record `comparison_id`; missing or invalid metrics are never coerced to zero and source availability remains distinct from market movement.
- PR #410 proves the complete path offline with exact inputs/golden outputs, repeatable commit/tree construction and stable comparison identities across the required success and fail-closed classes.
- Close-out review found one enforcement gap for additional asset/stablecoin identities; #411/PR #413 corrected it so supported identities are exactly BTC/ETH/SOL and USDT/USDC and unknown additional identities fail `pair-semantics-incompatible`, without widening the frozen contract.
- No provider/model call, credential, workflow, snapshot, selector, report/site, publication or generated `_site/` change was required.
- `planning/delivery/delivery.yaml` and `planning/delivery/graph.md` remain unchanged because Phase 10 is an offline evidence capability not yet integrated as a causal dependency in the active delivery pipeline.

## Phase 11 — Deterministic temporal visualisation

Status: complete.

Primary outcome: repository code now materialises deterministic repository-bound temporal series from replayed Phase 10 comparison evidence, validates them fail closed, renders deterministic accessible HTML/SVG/table output, and proves repeatability entirely offline.

```text
Parent issue: #418
Shaping/design issue: #416
Implementation/proof issues: #419, #421, #423
Close-out issue: #426
Implementation/proof PRs: #420, #422, #425
Slice 1 merge: fbdf09cef53a5d3bd826118472fac25063d688d6
Slice 2 merge: fc16e65dea5c8294748040fbda2650c2b7a91cbb
Slice 3 merge: 972ec1240d6f227798dca894a711028824c77645
Renderer exact-head validation: 31920585985
Proof exact-head validation: 31922157164
Proof corpus: phase11-temporal-series-proof-corpus/v1
Series contract: crypto-temporal-series/v1
Delivery record: planning/delivery/phase-11-deterministic-temporal-visualisation.md
Delivery graph update: N/A under compact causal graph rules
_site committed: no
```

Delivery notes:

- `crypto-temporal-series/v1` preserves exact inclusive UTC-hour slots, a maximum 168-slot window, immutable repository candidate enumeration and the existing Phase 10 comparison replay as the only successful value-producing evidence path; raw snapshot metrics never bypass Phase 10.
- Missing, ambiguity, Phase 10 and metric failure classes remain explicit and fail closed; current/predecessor snapshot identity, side-specific `valid-degraded` quality and warnings remain independently attributable.
- The deterministic renderer consumes only repository-validated canonical series, emits semantic HTML with inline SVG and a complete table, breaks numeric lines across gaps or identity discontinuities, and keeps source status categorical rather than mapping it onto a numeric market axis.
- The closed proof corpus independently materialises synthetic immutable Git repositories, proves complete table/continuity/tamper semantics and requires two independently materialised executions to be byte-identical and match frozen canonical-series/renderer SHA-256 identities and byte lengths.
- No provider/model call, credential, source snapshot/acquisition, selector, report/site, workflow/publication or generated `_site/` change was required.
- `planning/delivery/delivery.yaml` and `planning/delivery/graph.md` remain unchanged because Phase 11 is an offline deterministic evidence/rendering capability and has not become a causal dependency of the active ingestion/report/site/publication pipeline.
- Public/site integration of the proven temporal renderer and broader visual market-card product work remain parked for separate future governance. No successor phase is selected by Phase 11 close-out.

## Phase 12 — Canonical observation-hour evidence

Status: complete.

Primary outcome: future source snapshots now preserve actual generation/fetch timing while adding a separately validated canonical UTC containing-hour identity before rolling PR publication.

```text
Discovery/shaping issues: #430, #431
Roadmap promotion: #432 / PR #435
Parent issue: #436
Implementation issues: #437, #439
Close-out issue: #441
Implementation PRs: #438, #440
Slice 1 merge: 188d2c824e7bca30fdfd2ee6e1ab36006d314a6c
Slice 1 exact-head validation: 31924056018
Slice 2 merge: cb251970eb671d39cfcb8650b03b8fa55f6dfa23
Slice 2 exact-head validation: 31924356028
Contract: phase12-observation-hour/v1
Delivery record: planning/delivery/phase-12-canonical-observation-hour-evidence.md
Delivery graph update: yes — active source-evidence causal boundary
_site committed: no
```

Delivery notes:

- New snapshots remain schema `0.2` and keep actual `run.generated_at_utc`, local generation metadata, source `fetched_at_utc`, path naming and source/quality semantics while adding canonical `run.observation_hour_utc`.
- `scripts/validate_crypto_observation_hour.py` first requires the frozen snapshot validator and then fails closed unless the observation-hour field is canonical and exactly equals the UTC hour containing actual `run.generated_at_utc`.
- Legacy snapshots remain valid under the frozen validator but are not Phase-12 slot-ready; historical snapshot paths and bytes were not edited or backfilled.
- Regression proof pins the frozen snapshot-validator/config identities unchanged and covers exact boundary/mid/end-hour derivation, offset normalisation, preserved actual/fetched timestamps and malformed/non-canonical/mismatched rejection.
- Rolling ingestion now validates observation-hour evidence before PR evidence or any branch/commit/push/PR mutation and shows reviewers both actual generation time and the containing evidence hour.
- The schedule, manual dispatch, stable rolling branch/PR, snapshot-only commit scope, no-auto-merge, no-report and no-LLM boundaries remain unchanged.
- Phase 12 does not reinterpret Phase 10's exact `3,600`-second actual-time predecessor rule or Phase 11 temporal semantics and defines no duplicate-hour winner, fallback, interpolation, backfill or live temporal consumer.
- The compact delivery graph is updated because Phase 12 changes the active source-evidence spine and establishes an enduring evidence boundary that a later separately governed consumer may depend on.
- Observation-hour comparison/temporal consumption and public/site integration remain parked. No successor phase is selected by this close-out.

## Phase 13 — Deterministic observation-hour comparison and temporal evidence

Status: complete.

Primary outcome: repository code now consumes Phase-12 observation-hour identity through separately versioned exact adjacent-slot comparison and canonical temporal-series contracts, with repository-bound validation and a closed offline proof corpus.

```text
Shaping/design issue: #443
Roadmap promotion: #444 / PR #445
Parent issue: #446
Implementation/proof issues: #447, #449, #451
Close-out issue: #453
Implementation/proof PRs: #448, #450, #452
Slice 1 merge: 4e67918ba9e9be05689d3976e08d9230844263df
Slice 1 exact-head validation: 31928211032
Slice 2 merge: 07385273c48ad4d4ead26b75797d704119bbcaf5
Slice 2 exact-head validation: 31935983698
Slice 3 merge: 43cbf6a62afbc83d97f6f677795b0fe61c50738a
Slice 3 exact-head validation: 31937233333
Contracts: phase13-observation-hour-adjacency/v1, crypto-observation-hour-comparison/v1, crypto-observation-hour-series/v1
Proof corpus: tests/fixtures/phase13_observation_hour_temporal_proof_v1.json
Delivery record: planning/delivery/phase-13-observation-hour-temporal-evidence.md
Delivery graph update: yes — enduring observation-hour temporal evidence dependency
_site committed: no
```

Delivery notes:

- Exact current hour `H` and predecessor `H-1h` are selected by observation-hour slot identity from immutable repository evidence; legacy snapshots do not participate, malformed participating evidence fails globally, ambiguity precedes side validity and no older fallback exists.
- Successful comparison preserves actual elapsed time as non-gating evidence, including below/equal/above-3,600-second cases, while fixed 26-metric/8-source evidence and side-specific quality/warnings remain deterministic and repository-bound.
- `crypto-observation-hour-series/v1` replays only Phase 13 comparison evidence across exact bounded UTC-hour windows, exposes only the frozen 12-metric/8-source vocabulary, preserves categorical source status and breaks continuity unless retained identities match field-for-field.
- Missing, ambiguity, identity, validation, semantic and metric failures remain explicit gaps; there is no raw-snapshot success bypass, interpolation, aggregation, smoothing, normalisation, carry-forward, backfill or inferred-value path.
- The Slice 3 corpus independently materialises immutable synthetic Git repositories, covers the accepted closed/degraded/continuity/tamper matrix, and requires independent materialisations to reproduce byte-identical canonical comparison/series output and stable IDs.
- Representative proof freezes comparison at 9,459 canonical bytes / SHA-256 `046f1f65e5a90d5138068791e5a0b1d6da2b1ec58e45e5aef7f222dac471f3e7` and series at 21,626 bytes / SHA-256 `70495c03030003d6082774a22fc11ccc895aaf403c97f6e0033af2d0683839be`.
- Frozen Phase 10/11/12 semantics, historical snapshots, acquisition/workflows/publication, selector/report/site/renderer, provider/model/credential behaviour and generated `_site/` remain unchanged.
- The compact delivery graph records Phase 13 as an enduring evidence dependency while explicitly preserving the boundary that rendering/public-site integration requires separate future governance.
- No successor phase is selected by this close-out.

## Phase 14 — Deterministic site publication

Status: complete at the safe inert control-plane boundary; operational activation deferred.

Primary outcome: the reviewed `deterministic-site-publication/v3` control plane, dedicated repository-scoped publication App/protection boundary and candidate identity proof machinery are delivered, while automatic publication remains disabled and the unresolved live stale-base race, live pilot and recurring activation are explicitly deferred.

```text
Shaping issue: #455
Roadmap promotion: #456 / PR #457
Parent issue: #458
Inert implementation: #459 / PR #460
Inert implementation merge: 02f9ef75633a8bff4f84448d24e0f6167c610b73
Inert implementation exact-head validation: 31978089661
Provisioning/App protection: #461
App integration carrier: #462 / PR #463
App integration proof run: 31991433001
Candidate attestation/head-change proof: #465
Candidate proof carrier: PR #466
Proofability remediation: PR #467
Final candidate proof adjudication: #465 comment 5327452648
Stale-base live proof: #472 — closed not planned / deferred
Deferred live-proof successor: #477
Cadence restoration: #473 / PR #476
Close-out baseline: bf729ff61731ce515e48c9cd45ab7c1aa3266a5e
Owner inert-boundary close-out decision: #458 comment 5361248316
Delivery record: planning/delivery/phase-14-deterministic-site-publication.md
Delivery graph update: N/A under compact causal graph rules — no newly operational live publication stage
_site committed: no
```

Delivery notes:

- PR #460 delivered immutable source-intent/candidate/attestation identity, credential-free exact-head validation, a metadata-only gate that executes no candidate code, closed `valid-ok`/scope/idempotency policy and fail-closed activation semantics.
- #461 separately established the repository-scoped publication App, protected environment, strict required check bound to GitHub Actions app id `15368`, and PR-only publication-App ruleset bypass.
- App integration run `31991433001` proved the bounded App token/PR path while activation remained disabled and cleaned up its disposable PR/branch unmerged.
- #465 proved immutable attestation reconstruction and ordinary-writer changed-head rejection before the privileged merge boundary; final adjudication `5327452648` records proof success and cleanup complete.
- The real stale-base race was not successfully observed. V1–V13 repeatedly failed closed under scheduler timing, with final V13 stopping because the first qualifying source had already completed before pilot-id binding. That criterion is not claimed as proven.
- #472 was closed `not planned` / deferred and #477 now holds any future deterministic proof-carrier/operationalisation work. V1–V13 must not be revived and another timing-only V14+ runner is out of scope.
- PR #476 restored normal hourly ingestion cadence `17 * * * *`; publication activation remains absent/`disabled`.
- No Phase 14 live publication pilot, Phase 14 Pages/live identity proof or recurring activation occurred.
- `planning/delivery/delivery.yaml` and generated `planning/delivery/graph.md` remain unchanged because Phase 14 closes inert and does not add a newly operational publication stage to the causal graph.
- No model/provider, Phase 13 temporal public rendering, forecasting, sentiment, advice or broader product scope was introduced.
- No active successor phase is selected by this close-out.

## Phase 15 — Public deterministic temporal evidence

Status: complete.

Primary outcome: the validated Phase 13 observation-hour temporal evidence family is now exposed through one deterministic public `BTC.price_usd` 24-slot page plus one success-coupled low-prominence homepage discovery link, using the exact checked-out repository commit as evidence authority and preserving explicit gaps, provenance and demo/non-advice framing.

```text
Shaping issue: #479
Roadmap promotion: #480 / PR #481
Parent issue: #482
Slice 1 proof: PR #483
Slice 1 merge: 3f39a2857cd1ba6df91f64077b1dff67788fa2b5
Slice 1 exact-head validation: 32451833403
Slice 1 fresh approval: PR #483 comment 5365789771
Trusted-main evidence prerequisite: #484 / PR #488
Evidence merge: 0a119deb5f44babe4239e693ac82d648801a3772
Evidence exact-head validation: 32484067027
Evidence fresh approval: PR #488 comment 5370258468
Site integration: #489 / PR #490
Site integration merge: 99c4ced3001bb227d599173bb5a17011d23eea53
Site exact-head validation: 32525071794
Site fresh approval: PR #490 comment 5375474533
Pages publication run: 32528437373 — success
Pages/publication verification: #482 comment 5375652127
Close-out issue: #491
Contract: phase15-public-temporal-evidence/v1
Delivery record: planning/delivery/phase-15-public-deterministic-temporal-evidence.md
Delivery graph update: yes — closes the Phase 13 public-integration boundary with a narrow public evidence artifact
_site committed: no
```

Delivery notes:

- The selector reuses exact frozen Phase 13 participation semantics, fails malformed/unorderable and zero-participation populations closed, and anchors exactly 24 canonical UTC-hour slots at the maximum participating observation hour without duplicate-hour winner selection or older-slot fallback.
- The public renderer directly validates the repository-bound Phase 13 record before output and preserves exact values, gaps, continuity, candidate identities, quality/warnings and provenance in deterministic semantic HTML, inline SVG and a complete evidence table.
- The trusted-main prerequisite was satisfied by one additive reviewed Phase-12-valid snapshot at `data/crypto/hourly/2026/08/21/1549_AEST_source_snapshot.json`; no retained historical evidence was mutated or backfilled and the rolling branch never became public evidence authority.
- PR #490 integrates only through the canonical site generator. `temporal.html` and exactly one homepage discovery link are emitted only together on success; stale output is removed on fail-closed paths.
- Automatic Pages run `32528437373` built and deployed exact merge commit `99c4ced3001bb227d599173bb5a17011d23eea53` successfully. The exact deployed artifact contains the temporal page, expected commit identity, one homepage link, disclaimer-before-evidence ordering and all 24 evidence rows.
- The close-out does not claim an independent CDN HTTP fetch that the execution environment could not perform; it records GitHub's successful deployment state plus exact deployed-artifact inspection.
- Phase 14 publication activation/#477, broader temporal series/market cards, model/provider paths, narrative/forecast/advice and generated `_site/` remain outside Phase 15.
- No active successor phase is selected by this close-out.
