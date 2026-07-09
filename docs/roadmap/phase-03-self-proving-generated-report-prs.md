# Phase 3 — Self-proving generated report PRs

Status: shaping.

This specification defines Phase 3 before opening the full implementation issue tree. It should be treated as the design anchor for the next set of linked issues and PRs.

## Problem statement

Phase 2 proved that a merged `valid-ok` source snapshot can generate a deterministic Markdown report PR and that the report can be rendered by the static site generator without committing `_site/`.

However, Phase 2 also exposed an operational friction point. The generated report PR was created by GitHub Actions using `GITHUB_TOKEN`, and the downstream pull-request validation workflow required manual approval before it ran. That meant the generated PR existed before the main validation proof was visible.

The problem is not that validation was missing. Phase 2 waited for validation and did not merge until the proof was available. The problem is that the proof depended on a second workflow that can be approval-gated.

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
- investment advice, trading recommendations, trading signals, target prices, or position guidance;
- secrets or paid API keys;
- changes to the site publication model.

GitHub App tokens may be reconsidered later if self-proofing is not sufficient, but they are not the first Phase 3 move.

## Current workflow

The current generated report flow is conceptually:

```text
manual workflow_dispatch
  -> validate source snapshot
  -> generate deterministic Markdown report
  -> validate generated Markdown report
  -> build PR evidence
  -> create automation branch
  -> commit generated report
  -> open generated report PR

pull_request workflow
  -> run unit tests
  -> reject committed _site output
  -> build static site
  -> verify expected build artefacts
```

The weakness is that the second workflow can be approval-gated for PRs created by automation using `GITHUB_TOKEN`.

## Target workflow

The generated report workflow should become:

```text
resolve source snapshot
validate source snapshot
generate deterministic Markdown report
validate generated Markdown report
run relevant tests
build static site
prove rendered report path exists
inspect changed files
build complete PR evidence
create automation branch
commit generated report
open generated report PR
```

The downstream PR validation workflow should remain in place as defence in depth. It should not be the first and only proof that the generated report is reviewable.

## Self-proof evidence contract

Every generated report PR should include a structured evidence block with at least:

```text
Source snapshot:
Generated report:
Snapshot quality:
Required sources:
Optional exchange sources:
Selected exchange cross-check:
Report validation:
Advice-language check:
Unit tests:
Static site build:
Rendered archive path:
Changed files:
_site committed:
Workflow run:
Scope limitations:
```

The evidence block should distinguish between:

```text
passed       -> proof completed successfully
not run      -> proof was intentionally not executed, with reason
not required -> proof does not apply to this generated report
failed       -> workflow should not open the PR
```

For Phase 3, any failure in source snapshot validation, report generation, report validation, advice-language checks, unit tests, site build, rendered-path proof, or changed-file scope should fail the generating workflow before a PR is opened.

## Acceptance gates

A generated report PR is self-proving only if the generating workflow can prove:

- the source snapshot was resolved and validated;
- deterministic report generation completed;
- generated report validation passed;
- advice-like language checks passed;
- relevant unit tests passed;
- `python -m site_generator` completed successfully;
- the expected rendered archive path exists under `_site/archive/...` after the build;
- generated `_site/` output was not staged or committed;
- changed files are limited to the generated Markdown report path or explicitly allowed report evidence files;
- the PR body contains the complete evidence block;
- the PR body preserves the scope limitations: no LLM call, no financial advice, no publish/deploy, no auto-merge, and no secrets or paid API keys.

## Proposed implementation slices

Use linked issues rather than native GitHub sub-issues.

Proposed sequence:

```text
1. Phase 3: Make generated report PRs self-proving
   Parent delivery issue after this spec is merged.

2. Define self-proof evidence contract
   Document the exact PR evidence fields, allowed statuses, and failure semantics.

3. Add report evidence manifest builder
   Introduce a deterministic script that assembles Markdown PR evidence and, optionally, JSON evidence for logs/tests.

4. Move site-preview proof into the report-generation workflow
   Run `python -m site_generator` before opening the generated report PR and verify the expected rendered archive path.

5. Add changed-file scope validation for generated report PRs
   Ensure the generating workflow fails before PR creation if generated changes include `_site/` or unexpected paths.

6. Add workflow-order regression tests
   Assert the generation workflow performs validation, tests, site build, rendered-path proof, scope inspection, and evidence construction before PR creation.

7. Update generated report PR body
   Include the complete self-proof evidence block and clear scope limitations.

8. Prove end-to-end self-proving generated PR flow
   Run the generation workflow against a known valid snapshot and prove the generated PR is reviewable from its own evidence.

9. Phase 3 close-out evidence
   Close the parent issue only after the final proof PR and evidence comments are complete.
```

## Risks and mitigations

### Risk: The generating workflow becomes too large

Mitigation: keep proof steps small, deterministic, and script-backed. Prefer reusable scripts over long shell blocks embedded in YAML.

### Risk: Site build proof slows report PR creation

Mitigation: accept the cost. A generated report PR should not be opened if the report cannot render through the canonical site generator.

### Risk: The evidence block becomes stale or hand-maintained

Mitigation: generate the PR body evidence from workflow outputs or a small evidence manifest rather than duplicating text in multiple places.

### Risk: Downstream PR validation is ignored

Mitigation: keep downstream PR validation as defence in depth. The Phase 3 policy should say self-proof makes a generated PR reviewable, not that downstream validation is useless.

### Risk: Credential expansion becomes the default answer

Mitigation: explicitly keep GitHub App tokens and PATs out of Phase 3. Add credentials only in a later phase if the self-proof model is insufficient.

## Definition of done

Phase 3 is complete when:

- the Phase 3 parent issue and linked child issues exist;
- the generated report workflow runs the critical proof steps before opening a PR;
- generated report PRs contain the self-proof evidence contract;
- a real generated report PR demonstrates source snapshot validation, report validation, tests, site build, rendered-path proof, changed-file scope proof, and `_site` exclusion before PR creation;
- downstream PR validation remains available as defence in depth;
- no GitHub App token, PAT, auto-merge, auto-publish, LLM narrative, investment advice, secrets, paid API keys, or committed `_site/` output are introduced;
- close-out evidence is added to the parent issue and delivery log.

## Follow-on issue plan

After this spec merges, create the Phase 3 parent issue:

```text
Phase 3: Make generated report PRs self-proving
```

Then create linked child issues using the implementation slices above. Each child issue should include:

```text
Parent phase:
Phase spec:
Goal:
Acceptance criteria:
Evidence required:
Dependencies:
Out of scope:
```

Do not rely on native GitHub sub-issues. Use explicit parent references and linked issue checklists so the structure remains usable through the connector.
