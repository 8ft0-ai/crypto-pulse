# Phase 2 — Deterministic report review loop

Status: complete.

This is a post-delivery record. It preserves the original issue, pull-request, workflow-run, commit, and evidence-comment history while making the completed phase easier to understand.

## Primary outcome

A merged `valid-ok` source snapshot can produce a reviewed deterministic Markdown report PR, pass generated-report validation, and render through the static site generator without committing generated `_site/` output.

## Parent issue

```text
#90 — Phase 2: Prove deterministic report generation and review loop
```

## Linked issues / work breakdown

```text
#91 — Prove deterministic report PR flow from merged snapshot
#92 — Harden deterministic report validation
#93 — Add real snapshot fixture tests for report generation
#94 — Improve deterministic report readability
#95 — Add report archive/index integration without committing _site
#96 — Add report PR evidence block
#97 — Prove full snapshot-to-report-to-site-preview loop
```

## Key PRs

```text
#99  — Harden deterministic report validation
#100 — Add real snapshot fixture tests for report generation
#101 — Improve deterministic report readability
#102 — Add report archive/index integration without committing _site
#103 — Add report PR evidence block
#104 — Add deterministic crypto report 1742_AEST
```

## Final proof evidence

```text
Source snapshot PR: #89
Source snapshot merge commit: 178703aef4be8fc0ecf35677e1ffeffe7d4d4a52
Source snapshot path: data/crypto/hourly/2026/07/08/1742_AEST_source_snapshot.json
Source snapshot quality: valid-ok

Report workflow run: https://github.com/8ft0-ai/crypto-pulse/actions/runs/28940526728
Generated report PR: #104
Generated report PR merge commit: f6083aff44377b6819ce66d56da848e289124eb8
Generated report path: reports/crypto/hourly/2026/07/08/1742_AEST.md
Report validation: passed
Advice-language check: passed

PR validation run/job: https://github.com/8ft0-ai/crypto-pulse/actions/runs/28940544039/job/85861945926?pr=104
Site generation command: python -m site_generator
Rendered archive path: _site/archive/2026/07/08/1742_AEST.html
_site committed: no
```

## Produced artefacts

```text
reports/crypto/hourly/2026/07/08/1742_AEST.md
_site/archive/2026/07/08/1742_AEST.html       # rendered proof path only; not committed
```

## Validation evidence

- A real merged `valid-ok` source snapshot drove deterministic report generation.
- Generated reports can be validated for front matter, source linkage, required sections, product-boundary language, evidence/source status, and prohibited advice-like language.
- Real-world fixture coverage exists for the merged PR #89 snapshot.
- The deterministic report format became more readable while remaining source-grounded, testable, and non-LLM.
- Generated reports are discoverable by the archive/site generation flow.
- Generated report PRs contain review evidence: source snapshot, report path, snapshot quality, source statuses, validation, advice-language check, changed files, `_site` status, and scope limitations.
- The static site generator can render the generated report without committing `_site/`.

## Boundaries preserved

- Raw Markdown reports remain the source of truth.
- `_site/` remains generated/disposable and uncommitted.
- No LLM-generated report narrative was introduced in this phase.
- No investment advice, trading recommendations, trading signals, target prices, or position guidance were introduced.
- No auto-publishing or auto-merge was introduced.
- No secrets or paid API keys were introduced.

## Carry-forward lesson

Phase 2 exposed an important workflow-management lesson. The report generation workflow was intentionally manual because it used `workflow_dispatch`. Separately, the PR validation workflow for the generated report PR required manual approval because the generated PR was created by GitHub Actions using `GITHUB_TOKEN`.

That manual approval did not invalidate the proof, because the generated PR was not merged until the validation job passed. However, it created friction for a more autonomous scheduled loop.

Phase 3 resolved this by making generated report PRs self-proving before they are opened. Downstream PR validation remains defence in depth rather than the first and only source of merge confidence.
