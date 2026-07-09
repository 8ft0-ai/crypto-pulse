# Delivery log

This log records completed CryptoPulse delivery phases in one place. It is a curated management record, not a replacement for the canonical GitHub issue, pull-request, commit, and workflow history.

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

Status: not started.

Proposed direction: make generated report PRs self-proving before they are opened.

Motivation from Phase 2:

```text
Generated PRs created by GitHub Actions with GITHUB_TOKEN may leave downstream PR validation in an approval-required state.
```

Target outcome:

```text
The report generation workflow performs the critical proof steps before opening the generated PR:
- validate source snapshot
- generate deterministic Markdown report
- validate generated report
- run relevant tests
- build static site
- prove rendered report path exists
- inspect changed files
- build complete PR evidence
- open PR
```

Downstream PR validation should remain valuable, but it should be defence in depth rather than the only proof source.
