# Phase 3 — Self-proving generated report PRs

Status: delivered; retrospective roadmap spec.

This is a reconstructed forward-looking roadmap spec. It describes the Phase 3 planning intent that later became the completed self-proofing delivery record.

## Problem statement

Phase 2 proved deterministic report generation and static-site rendering, but it exposed an operational friction point.

Generated report PRs were created by GitHub Actions using `GITHUB_TOKEN`. Downstream pull-request validation could therefore require manual approval before it ran. That meant the generated PR existed before the main validation proof was visible.

The problem was not missing validation. The problem was that the first visible proof depended on a second workflow that could be approval-gated.

## Goal

Make generated report PRs self-proving before they are opened.

The report-generation workflow should run the critical proof steps itself, then open a PR whose body contains enough evidence for review even if downstream PR validation is pending or approval-required.

## Non-goals

Phase 3 should not introduce:

- GitHub App installation tokens;
- personal access tokens;
- auto-merge;
- auto-publish;
- committed `_site/` output;
- LLM-generated report narrative;
- advice-like or recommendation-style report language;
- secrets or paid API keys;
- changes to the site publication model.

Credential expansion may be reconsidered later if the self-proof model is insufficient, but it is not the first Phase 3 move.

## Target workflow or target state

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

Downstream PR validation should remain as defence in depth. Self-proof makes the generated PR reviewable; it does not make downstream validation unnecessary.

## Acceptance gates

Phase 3 is complete when generated report PRs can prove before PR creation that:

- [x] the source snapshot was resolved and validated;
- [x] deterministic report generation completed;
- [x] generated report validation passed;
- [x] advice-like language checks passed;
- [x] relevant unit tests passed;
- [x] `python -m site_generator` completed successfully;
- [x] the expected rendered archive path exists under `_site/archive/...` after the build;
- [x] generated `_site/` output was not staged or committed;
- [x] changed files are limited to the generated Markdown report path or explicitly allowed report evidence files;
- [x] the PR body contains the complete evidence block;
- [x] downstream PR validation remains available as defence in depth;
- [x] no credential expansion or publication automation is introduced.

## Proposed implementation slices

```text
1. Define self-proof evidence contract.
2. Add report evidence manifest builder.
3. Move site-preview proof into the report-generation workflow.
4. Add changed-file scope validation for generated report PRs.
5. Add workflow-order regression tests.
6. Update generated report PR body with self-proof evidence.
7. Prove end-to-end self-proving generated PR flow.
8. Record close-out evidence.
```

## Risks and mitigations

### Risk: The generating workflow becomes too large

Mitigation: keep proof steps small, deterministic, and script-backed. Prefer reusable scripts over long shell blocks embedded in YAML.

### Risk: Site build proof slows report PR creation

Mitigation: accept the cost. A generated report PR should not be opened if the report cannot render through the canonical site generator.

### Risk: The evidence block becomes stale or hand-maintained

Mitigation: generate PR body evidence from workflow outputs or a small evidence manifest rather than duplicating text in multiple places.

### Risk: Downstream PR validation is ignored

Mitigation: keep downstream PR validation as defence in depth and record it as a separate merge gate.

### Risk: Credential expansion becomes the default answer

Mitigation: explicitly keep GitHub App tokens and PATs out of Phase 3.

## Definition of done

The phase is complete when a real generated report PR demonstrates:

```text
Source snapshot validation: passed
Report validation: passed
Advice-language check: passed
Unit tests: passed
Static site build: passed
Rendered-path proof: passed
Changed-file scope proof: passed
Generated PR body self-proof: present
Downstream PR validation: passed
_site committed: no
```

## Follow-on delivery record

Completed evidence is recorded in:

```text
planning/delivery/phase-03-self-proving-generated-report-prs.md
```

## Carry-forward direction

Future phases should treat pre-PR proof and downstream validation as layered controls. If a later operating model needs fewer manual gates, credential expansion should be considered explicitly rather than introduced as a side effect.
