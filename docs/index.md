# CryptoPulse documentation

CryptoPulse is an AI-generated crypto market report demo and archive. Reports may be inaccurate, incomplete, stale, misleading or hallucinated. They are not financial advice, investment research, recommendations or trading signals.

Use this index to find documentation by what you are trying to achieve. Planning, delivery and evaluation records remain outside `docs/` so current guidance is not mixed with historical evidence.

## Choose your path

| Reader | Start here |
| --- | --- |
| New contributor | [Build and inspect CryptoPulse locally](tutorials/build-and-inspect-cryptopulse-locally.md) |
| Project operator | [Build the static site](how-to/build-the-static-site.md), [publish it](how-to/publish-the-static-site.md) or [verify the live site](how-to/verify-the-live-site.md) |
| Contract reviewer | [Source snapshot quality](reference/source-snapshot-quality.md), [deterministic report schema](reference/deterministic-report-schema.md), [semantic claim-plan contract](reference/semantic-claim-plan-contract.md), [deterministic claim-candidate contract](reference/claim-candidate-contract.md), [deterministic candidate compilation](reference/claim-candidate-compilation.md), [reviewed claim-candidate gold corpus](reference/claim-candidate-gold-corpus.md), [deterministic candidate-ranking baseline](reference/deterministic-candidate-ranking-baseline.md), [bounded candidate-ID selection](reference/bounded-candidate-id-selection.md), [governed bounded-selector model comparison](reference/candidate-selection-model-comparison.md), [low-cost candidate-selector Stage 0](reference/low-cost-candidate-selector-stage-0.md) or [semantic claim-plan rendering](reference/semantic-claim-plan-rendering.md) |
| Architect | [How CryptoPulse works](explanation/how-cryptopulse-works.md), [evidence and analysis boundary](explanation/evidence-and-analysis-boundary.md) or [trusted main and secret isolation](explanation/trusted-main-and-secret-isolation.md) |
| Contributor or coding agent | [Deliver a repository slice](how-to/deliver-a-repository-slice.md) and [choose an agent write strategy](how-to/choose-agent-write-strategy.md) |

## Start by task

### Learn CryptoPulse locally

Follow [Build and inspect CryptoPulse locally](tutorials/build-and-inspect-cryptopulse-locally.md) to generate the site from checked-in report data, serve it locally and trace a Markdown source report to its rendered HTML page.

### Understand the complete system

Read [How CryptoPulse works](explanation/how-cryptopulse-works.md) to follow source evidence through validation, deterministic or governed reporting, repository review, site generation, deployment and live verification.

### Build, publish and verify the site

- [Build the static site](how-to/build-the-static-site.md).
- [Publish the static site](how-to/publish-the-static-site.md).
- [Verify the live site](how-to/verify-the-live-site.md).
- [Look up generated site artefacts](reference/generated-site-artefacts.md).
- [Look up the live-site evidence artefact](reference/live-site-evidence-artefact.md).
- [Understand deterministic site generation](explanation/deterministic-site-generation.md).

### Work with source snapshots and deterministic reports

- [Validate a source snapshot](how-to/validate-a-source-snapshot.md).
- [Look up source snapshot quality](reference/source-snapshot-quality.md).
- [Look up the deterministic report schema](reference/deterministic-report-schema.md).
- [Look up generated report PR evidence](reference/generated-report-pr-evidence.md).

### Run and review governed analysis

- [Run a governed LLM dry run](how-to/run-governed-llm-dry-run.md) to produce and inspect an artefact-only accepted or rejected result.
- [Create a governed rolling-review pull request](how-to/create-governed-rolling-review-pr.md) when an approved configuration may promote accepted structured analysis into controlled source files.
- [Look up the governed analysis contract](reference/governed-analysis-contract.md) for the historical evidence, claim, provenance and policy rules.
- [Look up the semantic claim-plan contract](reference/semantic-claim-plan-contract.md) for the bounded model-owned plan and deterministic-rendering responsibility split.
- [Look up the deterministic claim-candidate contract](reference/claim-candidate-contract.md) for the Phase 6 repository-owned candidate shape, stable identity, ordering and future ID-only selection boundary.
- [Look up deterministic candidate compilation](reference/claim-candidate-compilation.md) for the exact evidence eligibility, comparison, quality and fail-closed rules used to produce candidates.
- [Look up the reviewed claim-candidate gold corpus](reference/claim-candidate-gold-corpus.md) for candidate recall, prohibited-combination absence, output identities and the explicit cross-source normalisation result.
- [Look up the deterministic candidate-ranking baseline](reference/deterministic-candidate-ranking-baseline.md) for bounded no-LLM selection, canonical plan reconstruction, retained precision and recall, and the permanent fallback contract.
- [Look up bounded candidate-ID selection](reference/bounded-candidate-id-selection.md) for the one-field model response, exact validation, one semantic repair and deterministic fallback contract.
- [Look up the governed bounded-selector model comparison](reference/candidate-selection-model-comparison.md) for the completed Slice 6 contract, protected evidence and archival decision boundary.
- [Look up the low-cost candidate-selector Stage 0 screen](reference/low-cost-candidate-selector-stage-0.md) for the Phase 7 models, real request, route/schema controls, cost ceilings and compatibility classifications.
- [Look up observable OpenRouter transport calibration](reference/openrouter-transport-calibration.md) for the Phase 8 real-request discovery, evidence-first response capture and pinned-provider reproduction boundary.
- [Look up the GPT-OSS candidate-selection quality comparison](reference/gpt-oss-quality-comparison.md) for the Phase 9 frozen corpus, staged execution, scoring, stability and operational decision boundary.
- [Look up semantic claim-plan rendering](reference/semantic-claim-plan-rendering.md) for exact repository-owned values, formatting, templates and fail-closed rules.
- [Look up the semantic claim-plan benchmark](reference/semantic-plan-benchmark.md) for protected workflow boundaries, retained artefacts and qualification fields.
- [Review the historical five-model catalogue screen](governed-semantic-plan-model-catalogue-screen.md) for the retained compatibility evidence and exclusions.
- [Review the corrective prompt-v2 screen](governed-semantic-plan-model-corrective-screen.md) for the Luna, DeepSeek and Qwen retry contract and USD 0.10 boundary.
- [Read the semantic claim-plan simplification note](notes/simplifying-semantic-claim-plan-pipeline.md) for the proposed shift from model-authored plans to deterministic candidates and bounded selection.
- [Look up the governed workflows](reference/governed-llm-workflows.md) for triggers, inputs, permissions, artefacts and repository effects.
- [Understand the evidence and analysis boundary](explanation/evidence-and-analysis-boundary.md) before treating generated analysis as reviewable repository content.

### Contribute and administer the repository

- [Contribute documentation](how-to/contribute-documentation.md).
- [Deliver a repository slice](how-to/deliver-a-repository-slice.md).
- [Choose an agent write strategy](how-to/choose-agent-write-strategy.md).
- [Configure main branch protection](how-to/configure-main-branch-protection.md).
- [Look up the repository layout](reference/repository-layout.md).

## Documentation modes

CryptoPulse uses four documentation modes. Each page has one primary purpose even when it links to another mode.

### Tutorials

- [Build and inspect CryptoPulse locally](tutorials/build-and-inspect-cryptopulse-locally.md)

### How-to guides

- [Build the static site](how-to/build-the-static-site.md)
- [Publish the static site](how-to/publish-the-static-site.md)
- [Verify the live site](how-to/verify-the-live-site.md)
- [Validate a source snapshot](how-to/validate-a-source-snapshot.md)
- [Run a governed LLM dry run](how-to/run-governed-llm-dry-run.md)
- [Create a governed rolling-review pull request](how-to/create-governed-rolling-review-pr.md)
- [Contribute documentation](how-to/contribute-documentation.md)
- [Deliver a repository slice](how-to/deliver-a-repository-slice.md)
- [Choose an agent write strategy](how-to/choose-agent-write-strategy.md)
- [Configure main branch protection](how-to/configure-main-branch-protection.md)

### Reference

- [Repository layout](reference/repository-layout.md)
- [Generated site artefacts](reference/generated-site-artefacts.md)
- [Live-site evidence artefact](reference/live-site-evidence-artefact.md)
- [Source snapshot quality](reference/source-snapshot-quality.md)
- [Deterministic report schema](reference/deterministic-report-schema.md)
- [Generated report PR evidence](reference/generated-report-pr-evidence.md)
- [Governed analysis contract](reference/governed-analysis-contract.md)
- [Semantic claim-plan contract](reference/semantic-claim-plan-contract.md)
- [Deterministic claim-candidate contract](reference/claim-candidate-contract.md)
- [Deterministic claim-candidate compilation](reference/claim-candidate-compilation.md)
- [Reviewed claim-candidate gold corpus](reference/claim-candidate-gold-corpus.md)
- [Deterministic candidate-ranking baseline](reference/deterministic-candidate-ranking-baseline.md)
- [Bounded candidate-ID selection](reference/bounded-candidate-id-selection.md)
- [Governed bounded-selector model comparison](reference/candidate-selection-model-comparison.md)
- [Low-cost candidate-selector Stage 0](reference/low-cost-candidate-selector-stage-0.md)
- [Observable OpenRouter transport calibration](reference/openrouter-transport-calibration.md)
- [GPT-OSS candidate-selection quality comparison](reference/gpt-oss-quality-comparison.md)
- [Semantic claim-plan rendering](reference/semantic-claim-plan-rendering.md)
- [Semantic claim-plan benchmark](reference/semantic-plan-benchmark.md)
- [Governed LLM workflows](reference/governed-llm-workflows.md)
- [Offline validation pipeline](reference/offline-validation-pipeline.md)
- [Governed OpenRouter client](reference/governed-openrouter-client.md)

### Explanation

- [How CryptoPulse works](explanation/how-cryptopulse-works.md)
- [Deterministic site generation](explanation/deterministic-site-generation.md)
- [Evidence and analysis boundary](explanation/evidence-and-analysis-boundary.md)
- [Fail-closed analysis validation](explanation/fail-closed-analysis-validation.md)
- [Trusted main and secret isolation](explanation/trusted-main-and-secret-isolation.md)

### Working notes

Working notes preserve research and architectural reflection without making them normative documentation.

- [Notes index](notes/README.md)
- [Simplifying the semantic claim-plan pipeline](notes/simplifying-semantic-claim-plan-pipeline.md)
- [Semantic claim selection: implementation patterns and references](notes/semantic-claim-selection-implementation-patterns.md)

## Records outside the documentation system

These paths are intentionally separate from Diátaxis documentation:

- [`planning/`](../planning/README.md) — roadmap intent, delivery records and close-out evidence;
- [`evaluation/`](../evaluation/phase-05/README.md) — discovery evidence, model evaluation and reviewed decisions;
- [`tests/`](../tests/) — tests, fixtures and fixture-specific notes;
- [`schemas/`](../schemas/) — machine-readable contracts;
- [`prompts/`](../prompts/) — versioned prompt artefacts;
- [`config/`](../config/) — executable configuration;
- [`reports/`](../reports/) — source report content.

Reference and explanation pages link to these canonical artefacts rather than copying them into `docs/`.

## Compatibility paths

Former flat documentation paths remain as short pointers where historical issues and pull requests are likely to link to them. They are not canonical and contain no duplicated procedure or contract body.

The migration history is recorded in the [`Diátaxis migration plan`](../planning/documentation/diataxis-migration.md) and [`post-implementation review`](../planning/documentation/diataxis-post-implementation-review.md).