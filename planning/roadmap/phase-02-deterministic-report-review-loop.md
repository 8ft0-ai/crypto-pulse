# Phase 2 — Deterministic report review loop

Status: delivered; retrospective roadmap spec.

This is a reconstructed forward-looking roadmap spec. It describes the intended Phase 2 direction before the completed delivery evidence was recorded.

## Problem statement

Phase 1 produced a validated source snapshot, but CryptoPulse still needed to prove that a snapshot could become a reviewable report without losing traceability.

The next problem was to generate a deterministic raw Markdown report from a merged `valid-ok` snapshot, validate the report structure and product boundary, and prove the static site could render the report without committing generated `_site/` output.

## Goal

Prove that a merged `valid-ok` source snapshot can produce a reviewed deterministic Markdown report PR and render through the static site generator.

The generated report should be source-grounded, deterministic, non-LLM, and explicitly bounded as demo content rather than customer-facing financial guidance.

## Non-goals

Phase 2 should not introduce:

- LLM-generated report narrative;
- discretionary market commentary;
- advice-like or recommendation-style report language;
- auto-publish;
- auto-merge;
- committed `_site/` output;
- secrets or paid API keys;
- GitHub App tokens or personal access tokens.

## Target workflow or target state

```text
select merged valid-ok source snapshot
generate deterministic Markdown report
validate generated report front matter and body
validate source linkage and evidence status
check product-boundary language
open generated report PR
run PR validation
build static site
prove expected rendered archive path
merge only after review evidence is available
```

## Acceptance gates

Phase 2 is complete when:

- [x] a real merged `valid-ok` source snapshot drives deterministic report generation;
- [x] generated report front matter links back to the source snapshot;
- [x] generated report validation checks source status, product-boundary language, required sections, and prohibited advice-like phrasing;
- [x] real snapshot fixture tests cover the report generation path;
- [x] report readability improves without making the report non-deterministic;
- [x] generated report PRs include enough evidence for review;
- [x] `python -m site_generator` can render the report;
- [x] the expected `_site/archive/...` path is proved by CI or workflow evidence;
- [x] generated `_site/` output is not committed.

## Proposed implementation slices

```text
1. Prove deterministic report PR flow from a merged source snapshot.
2. Harden deterministic report validation.
3. Add real snapshot fixture tests.
4. Improve deterministic report readability.
5. Add archive/index integration without committing _site.
6. Add generated report PR evidence.
7. Prove the full snapshot-to-report-to-site-preview loop.
```

## Risks and mitigations

### Risk: A deterministic report accidentally reads like guidance

Mitigation: validate product-boundary language and prohibit recommendation-style phrasing.

### Risk: The rendered report exists only after committing `_site/`

Mitigation: treat `_site/` as disposable build output and prove rendering in CI or workflow output rather than source control.

### Risk: The generated PR is reviewable only after an approval-gated downstream workflow runs

Mitigation: accept that friction for Phase 2 but record it as a carry-forward problem if it limits scheduled automation.

## Definition of done

The phase is complete when a generated report PR is merged and the delivery record captures:

```text
Parent issue
Child issues
Implementation PRs
Generated report PR
Report workflow run
PR validation run
Source snapshot path
Generated report path
Rendered archive path
Report validation
Advice-language check
_site committed: no
```

## Follow-on delivery record

Completed evidence is recorded in:

```text
planning/delivery/phase-02-deterministic-report-review-loop.md
```

## Follow-on phase

Phase 3 should address the approval-gated generated PR validation friction by making generated report PRs self-proving before they are opened.
