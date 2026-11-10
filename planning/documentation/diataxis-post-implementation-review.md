# Diátaxis post-implementation documentation review

## Record status

This is a historical planning and review record. It does not override current documentation, code, workflows, schemas, prompts or configuration.

| Field | Value |
| --- | --- |
| Repository | `8ft0-ai/crypto-pulse` |
| Reviewed commit | `908a750f29f89ffbab55a3ecf5aa492652cebd51` |
| Original migration | [Diátaxis migration](diataxis-migration.md) |
| Remediation parent | [Issue #243](https://github.com/8ft0-ai/crypto-pulse/issues/243) |
| Review date | 12 July 2026 |
| Pre-remediation recommendation | **Create a documentation remediation stage** |

## Executive assessment

The Diátaxis migration succeeded. CryptoPulse now has a coherent documentation entry point, generally correct separation between tutorials, how-to guides, reference and explanation, and strong documentation of governed-analysis authority boundaries.

The information architecture should be preserved. No critical or high-severity correctness defect was found, and representative operational and governance tasks remained achievable. The review did identify several medium correctness and governance defects, plus one medium architecture-navigation gap. These findings justify a bounded remediation stage rather than another migration.

## Overall rating

**7.8 out of 10 — accepted with bounded remediation required.**

| Dimension | Rating | Assessment |
| --- | ---: | --- |
| Diátaxis separation | 9/10 | Pages generally have one dominant reader purpose and link appropriately across modes. |
| Safety and governance | 9/10 | Evidence, analysis, validation, secret and publication authority boundaries are unusually clear. |
| Reader navigation | 7/10 | Task-oriented entry points work, but the complete architecture requires excessive page assembly. |
| Technical accuracy | 7/10 | Mostly accurate, with several concrete stale or contradictory statements. |
| Completeness | 7/10 | Strong for operators and reviewers; one system-level explanatory path is missing. |
| Maintainability | 7/10 | Link validation is valuable but does not enforce catalogue completeness or required canonical-page structure. |

## Primary audiences and reader journeys

The repository supports these primary audiences:

- new contributors learning the checked-in report-to-site path;
- project operators building, publishing and verifying the site;
- contributors and coding agents delivering bounded repository issues;
- report and contract reviewers looking up exact source, report and governed-analysis rules;
- architects and governance reviewers understanding trust, validation and publication boundaries;
- repository administrators configuring protection and reviewing workflow evidence.

The most important journeys are:

1. build and inspect CryptoPulse locally;
2. validate source evidence and generate deterministic report content;
3. publish and verify the static site;
4. deliver a bounded repository slice through issue, branch, PR and merge;
5. run or review optional governed analysis;
6. look up exact source, report, workflow and provider contracts;
7. understand the complete evidence-to-publication architecture.

## Mode-by-mode assessment

### Tutorials

The existing local-build tutorial is a genuine tutorial. It begins from a clean checkout, uses checked-in data, follows one prescribed path, produces observable output and includes cleanup. It does not require live market access, provider credentials or repository write authority.

The page does, however, give a PowerShell activation command and later rely on POSIX-only `test` and `rm` commands without declaring that the complete path assumes a POSIX shell. This is a usability defect rather than a classification failure.

A second snapshot-to-report tutorial could improve learning coverage, but the review did not establish that the current tutorial fails its claimed scope. It is therefore an optional improvement and excluded from the remediation stage.

### How-to guides

The build, publish, live-verification, source-validation and governed-analysis guides begin with recognisable goals and provide supported procedures. They generally link to reference rather than reproducing complete contracts.

The main drift is in repository-delivery guidance: the PR workflow now runs explicit documentation validation, while some procedural pages describe or list only tests and site generation. This should be corrected so the documented baseline matches the workflow.

### Reference

The reference set is strong and usually identifies canonical implementation, schema, workflow or configuration sources. Governed-analysis pages distinguish descriptive documentation from machine-readable contracts.

The review found two material accuracy issues:

- repository-layout documentation does not distinguish legacy or demonstration report filenames from deterministic and governed output paths;
- generated-site artefacts omit an accessibility stylesheet required by CI.

These are correctness defects because the pages claim to summarise complete path or output contracts.

### Explanation

The explanation pages clearly state design questions and explain why deterministic generation, evidence separation, fail-closed validation and secret isolation exist. They avoid becoming command catalogues and preserve exact contracts in linked reference pages.

The set lacks one end-to-end explanation joining source evidence, snapshot validation, deterministic reporting, optional governed analysis, review authority, site generation, deployment and live verification. Existing pages are individually sufficient but require the reader to infer the whole architecture. This is a medium navigation and coverage gap, not a reason to restructure the explanation directory.

## Information architecture assessment

`README.md` is an effective concise front door, and `docs/index.md` provides task-oriented reader routes before listing pages by mode. Planning, evaluation and compatibility records remain outside current guidance.

The four Diátaxis directories remain appropriate and should not be reorganised. The index is still usable, although its complete mode catalogues are approaching the point where further growth may justify topic landing pages. No such restructuring is supported by current task evidence, so it is deferred.

The index retains one migration-status sentence referring to closed issue #232 as if it still tracks execution. This is stale implementation-record language and should be removed from current guidance while preserving the historical migration plan.

## Canonical ownership assessment

Canonical authority is generally clear:

| Concern | Canonical owner |
| --- | --- |
| Source and report validation | Repository code and reviewed configuration |
| Source and report shapes | Validators, schemas and generator implementation |
| Governed-analysis contracts | Versioned schemas, prompt and validation code |
| Provider limits and policy | `config/llm-generation.yml` and provider client validation |
| Workflow triggers, permissions and jobs | `.github/workflows/` |
| Current reader procedures | Canonical pages under `docs/` |
| Historical intent and evidence | `planning/` and `evaluation/` |
| Generated site output | Disposable `_site/`, never an independent authority |

The principal ownership risks are duplicated volatile facts and structural documentation conventions that are written in contributor guidance but not enforced. Remediation must continue linking to canonical sources rather than creating a second contract in prose.

## Clean-context reader-task baseline

The walkthroughs began from README or `docs/index.md` and did not rely on hidden repository history.

| Task | Expected entry | Actual pages visited | Transitions | Result | Authority found | Friction or failure |
| --- | --- | --- | ---: | --- | --- | --- |
| Build and inspect CryptoPulse locally | README | README → local tutorial | 1 | Completed on POSIX path | Site generator and checked-in reports | PowerShell activation suggests Windows support, but later commands are POSIX-only. |
| Publish and verify the public site | Docs index | Index → publish guide → verify guide | 2 | Completed | Pages and verification workflows | No material defect. |
| Deliver one repository issue | Docs index | Index → slice delivery → agent write strategy | 2 | Completed | Issue/branch/PR workflow and agent instructions | Validation baseline omits explicit documentation validation. |
| Determine whether `_site/` is ignored, tracked or disposable | README | README → local tutorial | 1 | Incorrect assumption likely | CI and tutorial clarify untracked disposable output | README incorrectly says Git ignores `_site/`. |
| Look up deterministic report paths | Docs index | Index → repository layout → deterministic report schema | 2 | Conflicting answer | Generator and report validator | Report classes are not distinguished in repository layout. |
| Decide whether governed analysis may be merged | Docs index | Index → dry run/review PR guides → governed workflow/reference → authority explanations | 3 | Completed | Validation code, workflow and normal review | Protected boundaries are recognised correctly. |
| Explain the complete source-to-publication architecture | Docs index | Index plus several explanation and reference pages | 5 or more | Partially completed | Individual owners are identifiable | No single conceptual map joins every stage and authority transition. |

## Findings and remediation ownership

| ID | Severity | Category | Finding | Owner | Disposition |
| --- | --- | --- | --- | --- | --- |
| F1 | Medium | Correctness | README says `_site/` is ignored by Git although it may appear as untracked generated output. | #245 | Correct. |
| F2 | Low | Correctness | Repository-layout reference retains “transition-era” wording after migration completion. | #245 | Correct. |
| F3 | Medium | Correctness | Repository layout conflates legacy/demo, deterministic and governed report filename patterns. | #245 | Correct and classify existing path families. |
| F4 | Medium | Correctness | Generated-site reference omits `cryptopulse-accessibility.css`, which CI requires. | #245 | Correct. |
| F5 | Medium | Correctness | Delivery and branch-protection descriptions omit the documentation-validation step enforced by CI. | #245 | Align documentation with workflow. |
| F6 | Low | Correctness | Current index retains closed migration execution-status wording. | #245 | Remove status wording; retain historical plan link. |
| F7 | Medium | Usability | Tutorial only partially supports Windows while implying broader command portability. | #245 | Declare the complete tutorial’s POSIX-shell assumption. |
| F8 | Low | Usability | Live-site failure procedure contains inconsistent sentence casing. | #245 | Correct. |
| F9 | Medium | Governance | Canonical pages can be added without appearing in the mode catalogue. | #246 | Add objective completeness validation. |
| F10 | Medium | Governance | Required H1 and page metadata are documented but not enforced. | #246 | Add canonical-page structural validation. |
| F11 | Medium | Governance | Declared mode and directory placement can drift. | #246 | Add mode-placement validation. |
| F12 | Low | Governance | Canonical filename convention is not enforced. | #246 | Add filename validation. |
| F13 | Low | Governance | Local Markdown image targets are not validated. | #246 | Extend local target validation. |
| F14 | Medium | Navigation and coverage | No single explanation joins the complete source-to-publication architecture. | #247 | Add one bounded explanation and navigation entry. |
| F15 | Optional | Learning coverage | A snapshot-to-deterministic-report tutorial could provide a second learning journey. | Deferred | Do not implement without stronger reader evidence. |
| F16 | Optional | Information architecture | Mode lists may eventually need topic landing pages as the catalogue grows. | Deferred | Reassess only after measurable navigation friction. |

No critical or high-severity finding was identified.

## Delivery posture

**Posture C — Documentation remediation stage.**

The correctness corrections are independently bounded, but the complete response also requires repository-wide validator changes and one new reader journey. The stage is intentionally small and preserves the existing architecture.

## Approved backlog and dependency order

1. [Issue #244](https://github.com/8ft0-ai/crypto-pulse/issues/244) — commit this review record.
2. [Issue #245](https://github.com/8ft0-ai/crypto-pulse/issues/245) — correct factual drift and reader guidance.
3. [Issue #246](https://github.com/8ft0-ai/crypto-pulse/issues/246) — strengthen objective documentation validation.
4. [Issue #247](https://github.com/8ft0-ai/crypto-pulse/issues/247) — add the end-to-end architecture explanation.

Each issue is independently reviewable and leaves the repository in a useful state if later work is stopped.

## Deliberate non-goals

- repeat the original migration;
- move pages for visual symmetry;
- remove compatibility paths;
- convert planning or evaluation evidence into current guidance;
- add a documentation framework, prose linter or external-link gate;
- change product, source collection, report generation, analysis, provider, deployment or publication behaviour;
- add a second tutorial during this stage;
- create category landing pages before task evidence justifies them.

## Validation strategy

Each remediation PR must run:

```bash
python -m unittest discover -s tests
python scripts/validate_documentation.py
python -m site_generator
```

The validator-hardening PR also runs focused documentation-validator tests. Every PR must prove that `_site/` is not committed and repeat its issue-specific clean-context walkthrough.

GitHub Actions is the executable validation source for this stage because the review environment can access repository content through the connector but cannot clone GitHub directly.

## Compatibility strategy

- Keep all canonical documentation URLs stable.
- Preserve current compatibility pointers.
- Preserve planning and evaluation history in place.
- Add new navigation without changing existing destinations.
- Do not remove an old path without a separate external-link lifecycle review.

## Risks and assumptions

- Contents-API fallback may create multiple small branch commits; PRs should be squash-merged after green checks.
- Structural validator additions must apply only to canonical mode directories and avoid imposing current-page metadata on historical records or compatibility pointers.
- Documentation describes repository behaviour at the reviewed commit; volatile values remain subordinate to linked enforceable sources.
- The new system overview must stay explanatory and must not become a duplicated reference contract.

## Stage completion criteria

The stage is complete when:

- every correctness finding F1–F8 is corrected;
- every governance finding F9–F13 has focused tests and the real repository passes;
- the architecture walkthrough succeeds from README or `docs/index.md` without hidden context;
- no canonical path or compatibility route is broken;
- unit tests, documentation validation and site generation pass;
- no `_site/` output is committed;
- optional findings F15 and F16 remain explicitly deferred rather than silently expanded into scope;
- the final independent recommendation is **Approve**.

## Pre-remediation recommendation

**Create a documentation remediation stage.**

The existing documentation is reliable enough to use for most tasks, but should not be considered fully closed until the bounded correctness, governance and architecture-navigation findings above are resolved.
