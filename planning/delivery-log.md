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
