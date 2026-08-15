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
