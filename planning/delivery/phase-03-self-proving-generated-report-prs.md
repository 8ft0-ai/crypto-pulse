# Phase 3 — Self-proving generated report PRs

Status: complete.

This is a post-delivery record. It captures what actually shipped and how the completed phase was proved.

## Primary outcome

Generated report PRs now carry their own pre-PR proof from the report-generation workflow, with downstream PR validation retained as defence in depth.

## Parent issue

```text
#115 — Phase 3: Make generated report PRs self-proving
```

## Linked issues / work breakdown

```text
#116 — Define self-proof evidence contract
#117 — Add report evidence manifest builder
#118 — Move site-preview proof into report generation workflow
#119 — Add generated report changed-file scope validation
#120 — Add generated report workflow-order regression tests
#121 — Update generated report PR body with self-proof evidence
#122 — Prove end-to-end self-proving generated report flow
#123 — Phase 3 close-out evidence
```

## Key PRs

```text
#124 — Define self-proof evidence contract
#125 — Add generated report site preview proof
#126 — Add generated report changed-file scope validator
#129 — Add report PR evidence manifest builder
#130 — Add generated report workflow-order regression tests
#131 — Use evidence builder for generated report PR body
#132 — Add deterministic crypto report 2031_AEST
#134 — Record Phase 3 close-out evidence
```

## Problem addressed

Phase 2 proved deterministic Markdown report generation and rendering, but generated PR validation could be approval-gated. The first visible proof depended on a second workflow that could require manual approval.

## Delivered workflow shape

```text
resolve source snapshot
validate source snapshot
generate deterministic Markdown report
validate generated Markdown report
run relevant tests
build static site
prove rendered report path exists
inspect changed files
validate changed-file scope
build complete PR evidence
create automation branch
commit generated report
open generated report PR
```

The downstream PR validation workflow remains in place as defence in depth.

## Final proof evidence

```text
Parent issue: #115
Close-out issue: #123
Implementation issues: #116, #117, #118, #119, #120, #121
Proof issue: #122
Key implementation PRs: #124, #125, #126, #129, #130, #131
Generated report proof PR: #132
Close-out PR: #134
Generated report workflow run: 28999816016
Generated report path: reports/crypto/hourly/2026/07/08/2031_AEST.md
Rendered archive path: _site/archive/2026/07/08/2031_AEST.html
Downstream PR validation run: 29000320882
Generated report merge commit: 5a77e5aa315f72c76363a7286396c67c8ec43405
Delivery log merge commit: 06039f42d3b4eb20889c7fafe4d983a1f2dde3f1
_site committed: no
```

## Produced artefacts

```text
scripts/build_report_pr_evidence.py
scripts/validate_generated_report_pr_scope.py
reports/crypto/hourly/2026/07/08/2031_AEST.md
_site/archive/2026/07/08/2031_AEST.html       # rendered proof path only; not committed
```

## Validation evidence

- The generated report workflow runs validation, tests, static-site build, rendered-path proof, changed-file inspection, changed-file scope validation, and PR evidence construction before opening a PR.
- Generated report PRs contain the self-proof evidence contract.
- PR #132 proved a real generated report flow end to end.
- PR #132 changed exactly one raw Markdown report file.
- Downstream PR validation passed as defence in depth.
- `_site/` output was generated only as a preview/proof artefact and was not committed.

## Boundaries preserved

- No credential expansion was introduced.
- No auto-merge was introduced.
- No auto-publish was introduced.
- No committed `_site/` output was introduced.
- No LLM-generated report narrative was introduced.
- No secrets or paid API keys were introduced.
- No changes to the site publication model were introduced.

## Carry-forward lesson

Self-proofing makes generated report PRs reviewable even when downstream PR validation is pending or approval-gated. It does not make downstream validation unnecessary. Future phases should treat pre-PR proof and downstream validation as layered controls, not substitutes for each other.
