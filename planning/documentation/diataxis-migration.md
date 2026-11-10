# Diátaxis documentation migration

## Purpose

Align CryptoPulse's current user-facing documentation with the Diátaxis framework so that readers can learn the system, complete operational tasks, look up precise contracts and understand architectural decisions without navigating mixed implementation records.

This is a cross-cutting documentation initiative. It is not a numbered product phase. This planning record is authoritative for scope, information architecture, migration decisions and definition of done. Parent issue #232 is authoritative for execution status. Pull requests and close-out comments are authoritative for delivery evidence.

## Scope

The initiative covers current documentation intended for:

- new contributors learning CryptoPulse;
- operators building, validating or publishing repository artefacts;
- reviewers looking up contracts, workflows and evidence formats;
- maintainers contributing documentation or repository changes;
- architects understanding provenance, deterministic generation, validation and trust boundaries.

The work will:

1. establish `docs/index.md` and a populated Diátaxis structure;
2. migrate the governed-analysis material as a complete pilot journey;
3. add a safe local learning and operation journey;
4. assess and migrate the remaining current user-facing documents;
5. refocus `README.md` only after the documentation destination is useful;
6. add objective documentation validation.

## Non-goals

This initiative will not change:

- market-data collection or source selection;
- source-snapshot, report or analysis behaviour;
- model configuration or provider routing;
- schemas, prompts or report content;
- security policy or workflow permissions, except for documentation validation if objectively required;
- publication behaviour or generated-site behaviour;
- historical planning, delivery, evaluation or test evidence;
- the rule that `_site/` is disposable generated output and must not be committed.

The work will not gather every Markdown file under `docs/`, create empty category directories, or automate subjective Diátaxis classification decisions.

## Repository boundary

Only Diátaxis documentation belongs under `docs/`.

The following repository domains retain their current responsibilities:

| Path | Responsibility | Migration rule |
| --- | --- | --- |
| `planning/` | planning, roadmap, delivery and decision records | Keep outside `docs/`; preserve as management and historical evidence. |
| `evaluation/` | evaluation evidence and reviewed decisions | Keep outside `docs/`; move historical evaluation records here when appropriate. |
| `tests/` | tests, fixtures and test-specific notes | Keep beside the tests and fixtures they explain. |
| `schemas/` | machine-readable contracts | Keep canonical schemas here; reference documentation links to them. |
| `prompts/` | versioned prompt artefacts | Keep canonical prompts here; reference documentation links to them. |
| `config/` | executable configuration | Keep configuration here; reference documentation describes supported values and constraints. |
| `reports/` | source report content | Keep reports as source content; tutorials may use checked-in examples. |
| `analysis/` | accepted generated analysis artefacts | Keep accepted analysis artefacts here if and when the directory is used. |
| `.agents/` and `AGENTS.md` | machine-oriented agent instructions and runbooks | Retain in place; link to human documentation where useful. |
| `.github/` | workflow and contribution templates | Retain in place; update links or commands when canonical documentation changes. |

## Diátaxis definitions

### Tutorial

A tutorial is a guided learning experience for a reader starting from a known state. It leads through a safe sequence, produces an observable result, avoids unnecessary options and links to deeper reference or explanation.

### How-to guide

A how-to guide is a goal-oriented procedure for a reader who already understands the basic context. It solves one concrete problem, focuses on the required steps and links to reference for exhaustive detail.

### Reference

Reference documentation is a precise, neutral description of the system. It covers contracts, schemas, configuration, commands, paths, workflows, artefact formats, supported values and constraints. It must be structured for scanning and free of delivery narrative.

### Explanation

Explanation documentation helps readers understand why the system works as it does. It covers architecture, rationale, trade-offs, provenance, deterministic rendering, fail-closed validation, trust boundaries, security and governance decisions. It must not become a procedural runbook or exhaustive field catalogue.

## Current-state documentation inventory

The inventory records the intended final disposition of current documentation candidates. Paths under `planning/`, `evaluation/`, `tests/`, `schemas/`, `prompts/`, `config/`, `reports/` and `analysis/` are explicitly excluded from indiscriminate migration; they remain in their domain and may be linked from Diátaxis pages.

| Current path | Primary audience | Primary user need | Primary Diátaxis mode | Secondary mixed content | Current or historical status | Recommended action | Target path | Migration issue |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `README.md` | Repository visitors and contributors | Understand the project, its safety boundary and the shortest local start | Repository front door, not a Diátaxis page | How-to, reference and explanation | Current, but overloaded | Keep broadly usable until the new destination is complete, then refocus | `README.md` | #237 |
| `AGENTS.md` | Coding agents and maintainers | Follow repository operating and safety rules | Machine-oriented reference | How-to guidance | Current | Retain at repository root; update links only where canonical docs move | `AGENTS.md` | #236, #237 |
| `.github/pull_request_template.md` | Contributors | Supply review and validation evidence | Contribution template, not a Diátaxis page | How-to guidance | Current | Retain under `.github/`; align commands and documentation links during close-out | `.github/pull_request_template.md` | #237 |
| `.agents/skills/*.md` | Coding agents | Execute specialised repository workflows safely | Machine-oriented runbook | Reference and how-to | Current | Retain beside agent artefacts; update moved links where required | `.agents/skills/*.md` | #236 |
| `docs/agent-write-strategies.md` | Agents and maintainers | Choose a safe repository write path | How-to | Rationale and process reference | Current | Rewrite as one goal-oriented guide and remove migration/process history | `docs/how-to/choose-agent-write-strategy.md` | #236 |
| `docs/crypto-snapshot-quality-contract.md` | Operators, reviewers and developers | Look up snapshot quality states and blocking rules | Reference | Historical issue metadata and rationale | Current contract with historical framing | Rewrite as neutral reference; link configuration and validator | `docs/reference/source-snapshot-quality.md` | #236 |
| `docs/crypto-source-crosscheck-discovery.md` | Maintainers and architects | Understand the evidence behind source-selection decisions | Explanation / evaluation evidence | Historical run details and implementation recommendation | Historical discovery record | Preserve outside current docs rather than relabelling it | `evaluation/source-crosscheck-discovery.md` | #236 |
| `docs/deterministic-crypto-report-schema.md` | Developers and reviewers | Look up deterministic report fields and constraints | Reference | Implementation history and examples | Current contract | Rewrite as neutral, scan-friendly reference linked to source code and tests | `docs/reference/deterministic-report-schema.md` | #236 |
| `docs/governed-llm-analysis-contract.md` | Operators, reviewers and architects | Understand the governed analysis contract and boundaries | Reference | Architectural rationale and delivery status | Current contract with mixed modes | Split contract reference from evidence-boundary explanation | `docs/reference/governed-analysis-contract.md`; `docs/explanation/evidence-and-analysis-boundary.md` | #234 |
| `docs/governed-llm-dry-run.md` | Operators and reviewers | Run and inspect a governed dry run | How-to | Workflow reference and historical issue status | Current procedure with mixed modes | Rewrite into a focused procedure plus workflow reference | `docs/how-to/run-governed-llm-dry-run.md`; `docs/reference/governed-llm-dry-run-workflow.md` | #234 |
| `docs/governed-llm-model-evaluation.md` | Evaluators and maintainers | Understand and complete the bounded model-evaluation harness | Evaluation evidence / historical runbook | Trust-boundary explanation and current candidates | Historical phase-five record | Preserve with the phase-five evaluation evidence; link from explanations if useful | `evaluation/phase-05/model-evaluation-harness.md` | #236 |
| `docs/governed-llm-rolling-review.md` | Operators and reviewers | Create and review a governed rolling-analysis PR | How-to | Workflow contract and historical status | Current procedure with mixed modes | Rewrite into a procedure and concise workflow reference | `docs/how-to/create-governed-rolling-review-pr.md`; `docs/reference/governed-llm-review-workflow.md` | #234 |
| `docs/governed-openrouter-client.md` | Developers, reviewers and architects | Look up provider-client behaviour and understand routing controls | Reference | Trust, retention and secret-boundary explanation | Current contract with mixed modes | Split neutral client reference from trust-boundary explanation where required | `docs/reference/governed-openrouter-client.md`; `docs/explanation/trusted-main-and-secret-isolation.md` | #234 |
| `docs/live-site-evidence.md` | Operators and reviewers | Run and inspect post-deployment live-site verification | How-to | Artefact format reference | Current | Split operating procedure from evidence-artefact description if the content justifies it | `docs/how-to/verify-the-live-site.md`; `docs/reference/live-site-evidence-artefact.md` | #236 |
| `docs/main-branch-protection.md` | Repository administrators | Configure the recommended main-branch controls | How-to | Required-check reference | Current | Rewrite as one configuration procedure linked to workflow reference | `docs/how-to/configure-main-branch-protection.md` | #236 |
| `docs/offline-governed-analysis-pipeline.md` | Architects, reviewers and developers | Understand the offline validation and publication boundary | Explanation | Pipeline-stage reference | Current | Split conceptual boundary from precise pipeline-stage reference only where useful | `docs/explanation/fail-closed-analysis-validation.md`; `docs/reference/offline-validation-pipeline.md` | #234 |
| `docs/optional-llm-narrative-boundary.md` | Architects and governance reviewers | Understand why LLM narrative remains optional and bounded | Explanation | Historical phase rationale | Current architectural boundary with history | Rewrite into current conceptual explanation and preserve phase evidence in planning/evaluation | `docs/explanation/optional-llm-narrative-boundary.md` | #234 |
| `docs/report-self-proof-evidence-contract.md` | Workflow developers and reviewers | Look up evidence required before a generated report PR opens | Reference | Delivery history | Current contract | Rewrite as neutral reference linked to workflow and builder | `docs/reference/generated-report-pr-evidence.md` | #236 |
| `docs/slice-delivery-process.md` | Contributors and maintainers | Deliver a bounded repository change through issue, PR and evidence | How-to | Process rationale and historical wording | Current | Rewrite as a contributor procedure; avoid duplicating `AGENTS.md` | `docs/how-to/deliver-a-repository-slice.md` | #236 |

### Explicitly excluded Markdown

The following Markdown remains outside the Diátaxis migration unless a link must be updated:

- `planning/**/*.md` — planning intent, delivery records, graph guidance and historical close-out;
- `evaluation/**/*.md` — evaluation corpus guidance, decisions and evidence;
- `tests/**/*.md` — fixture-specific notes;
- `reports/**/*.md` — report source content;
- `prompts/**/*.md` — versioned prompt artefacts;
- machine-oriented README files that belong beside their artefacts.

## Target information architecture

The target documentation tree is:

```text
docs/
├── index.md
├── tutorials/
│   └── build-and-inspect-cryptopulse-locally.md
├── how-to/
│   ├── contribute-documentation.md
│   └── ... goal-oriented procedures
├── reference/
│   └── ... contracts, workflows, commands, paths and artefact formats
└── explanation/
    └── ... architecture, rationale, trust and validation boundaries
```

Directories are created only when useful content lands in the same pull request. No category receives placeholder or “coming soon” pages.

`docs/index.md` is the primary human documentation entry point. It organises links first by reader intent and then by Diátaxis mode. Repository-domain records remain linked from their own indexes rather than copied into `docs/`.

## Documentation metadata and authoring conventions

Every Diátaxis page must contain:

1. one H1 title;
2. a visible metadata block near the top using this form:

   ```markdown
   > **Mode:** Tutorial | How-to | Reference | Explanation  
   > **Audience:** ...  
   > **Outcome:** ...
   ```

3. one dominant reader need;
4. repository-relative links to canonical source artefacts;
5. no issue-status banner, implementation-record status or PR-close language in current operational documentation.

Additional conventions:

- Use lower-case, hyphenated filenames.
- Use Australian English and the repository term `artefact`.
- Keep commands in fenced code blocks and verify them against current repository behaviour.
- Link directly to schemas, configuration, workflows, prompts, tests and implementation entry points rather than copying them.
- Prefer rewriting mixed material over duplicating paragraphs across modes.
- Keep tutorials linear and safe, how-to guides task-focused, reference neutral and explanation conceptual.
- Use relative links that resolve from the source page.
- Do not link to future pages until they exist in the same merged branch.
- Preserve historical evidence in Git history, planning records, evaluation records, issues and pull requests.

## Migration principles

1. **One primary purpose per page.** A page may link across modes but must not attempt to teach, instruct, catalogue and justify at the same depth.
2. **Rewrite rather than copy.** Mixed source documents are decomposed for their intended readers; paragraphs are not duplicated mechanically.
3. **Current docs are not delivery records.** Issue numbers, implementation status and close conditions are removed from canonical operating pages.
4. **Stable source links remain direct.** Reference pages link to the actual schema, config, workflow, prompt, code and tests.
5. **Evidence remains evidence.** Discovery results, evaluation decisions and phase close-out records remain under planning or evaluation.
6. **README sequencing is protected.** The full README simplification happens only after issues #234–#236 create a useful destination.
7. **No empty structure.** A directory appears only with useful content.
8. **No product-scope expansion.** Documentation changes do not alter behaviour merely to make a page easier to write.

## Issue breakdown

### #233 — Audit current documentation and establish the Diátaxis structure

Create this planning record, the documentation index, initial authoring guidance and the minimum README link. Do not migrate the pilot or refocus the README.

### #234 — Create the governed-analysis Diátaxis documentation journey

Use the governed analysis documents as the first complete how-to, reference and explanation journey. Remove mixed-mode duplication and historical status wording.

### #235 — Add the local CryptoPulse learning and operation documentation

Create a safe checked-in-data tutorial, focused local operation guides, repository and generated-artefact reference, and deterministic-generation explanation.

### #236 — Migrate remaining user-facing documentation into Diátaxis

Resolve the remainder of this inventory, preserving historical and machine-oriented records in their proper domains and updating incoming links.

### #237 — Refocus the repository README and validate the documentation system

Make the README a concise front door, add objective link/path validation, record the deferred backlog and close the initiative with evidence.

## Dependency order

```text
#233 audit and structure
  ├── #234 governed-analysis pilot
  └── #235 local learning and operation
        #234 + #235
             └── #236 remaining migration
                    └── #237 README, validation and close-out
```

Only one implementation pull request is active at a time. A subsequent issue begins from confirmed current `main` after the previous pull request has merged.

## README sequencing

The required sequence is:

1. create the documentation structure and `docs/index.md`;
2. populate a complete governed-analysis pilot journey;
3. add the local learning and operation journey;
4. migrate remaining current user-facing documentation;
5. refocus `README.md` only after the destination is useful.

Issue #233 may add a small link to `docs/index.md`. It must otherwise preserve the current README content and local instructions.

## Link-preservation strategy

For each moved or removed document:

1. search the repository for the old path;
2. update valid internal links in the same pull request;
3. identify whether the old path is likely to have stable external references;
4. prefer removing the duplicate after updating links;
5. retain a short compatibility page only where external stability is materially justified;
6. make any compatibility page point clearly to one canonical location and contain no duplicated body content;
7. record old-to-new paths in the pull-request evidence.

Git history, merged pull requests, planning records and evaluation records remain the evidence trail. Moving historical material does not authorise rewriting its substantive findings.

## Validation strategy

Existing repository validation remains authoritative:

```bash
python -m unittest discover -s tests
python -m site_generator
```

Each pull request must also confirm:

- every internal Markdown link introduced or changed resolves;
- every referenced repository path exists on the branch;
- old paths have no unintended incoming links;
- expected generated site artefacts exist after the build;
- `_site/` is generated locally or in CI but is not staged or committed;
- the changed-file scope matches the linked issue;
- no product, data, provider, schema, prompt, report or publication behaviour changed.

Issue #237 will add an objective repository check for internal Markdown links, removed document paths, malformed relative links, index destinations, duplicate top-level navigation entries and accidental committed `_site/` content. It will not score or classify subjective writing quality.

## Definition of done

The initiative is complete only when:

- `docs/index.md` exists and is useful;
- tutorials, how-to, reference and explanation contain real content;
- planning, evaluation and test artefacts remain outside the Diátaxis structure;
- the governed-analysis pilot is complete;
- the local learning and operation journey is complete;
- every inventory candidate has a completed final action;
- `README.md` is a concise repository front door;
- old internal documentation links are updated or deliberately preserved;
- objective documentation validation passes;
- repository tests pass;
- static-site generation succeeds;
- no `_site/` content is committed;
- issues #233–#237 are closed;
- all initiative pull requests are merged;
- parent issue #232 contains complete close-out evidence and is closed from verified `main`.

## Deferred backlog

The backlog is initially empty. During delivery, lower-priority work may be recorded here only when it is not required for the definition of done. Likely candidates include:

- external documentation-site rendering beyond the current repository Markdown experience;
- automatic prose-style linting;
- broader public URL compatibility pages where no internal reference exists;
- diagrams that improve an explanation but are not needed to make the current text accurate;
- native GitHub sub-issue reconciliation or project-board presentation.

Deferred items must state why they are not blocking and identify a future owner or issue where practical.

## Close-out evidence template

Use the following structure in the final parent-issue comment:

```text
Planning record:
Execution issues:
Merged PRs:
Final main commit:
Documentation entry point:
Tutorials delivered:
How-to guides delivered:
Reference documents delivered:
Explanation documents delivered:
Old paths removed or retained:
README refocused:
Link validation:
Repository tests:
Static-site build:
Generated _site committed:
Deferred backlog:
Known limitations:
```
