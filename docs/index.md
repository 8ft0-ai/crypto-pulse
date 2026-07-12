# CryptoPulse documentation

CryptoPulse is an AI-generated crypto market report demo and archive. Reports may be inaccurate, incomplete, stale, misleading or hallucinated. They are not financial advice, investment research, recommendations or trading signals.

Use this index to find documentation by what you are trying to achieve. Planning, delivery and evaluation records remain outside `docs/` so current guidance is not mixed with historical evidence.

## Choose your path

| Reader | Start here |
| --- | --- |
| New contributor | [Build and inspect CryptoPulse locally](tutorials/build-and-inspect-cryptopulse-locally.md) |
| Project operator | [Build the static site](how-to/build-the-static-site.md) or [Validate a source snapshot](how-to/validate-a-source-snapshot.md) |
| Contract reviewer | [Governed analysis contract](reference/governed-analysis-contract.md) or [Generated site artefacts](reference/generated-site-artefacts.md) |
| Architect | [Evidence and analysis boundary](explanation/evidence-and-analysis-boundary.md) or [Deterministic site generation](explanation/deterministic-site-generation.md) |

## Start by task

### Learn CryptoPulse locally

Follow [Build and inspect CryptoPulse locally](tutorials/build-and-inspect-cryptopulse-locally.md) to generate the site from checked-in report data, serve it locally and trace a Markdown source report to its rendered HTML page.

### Build and validate local artefacts

- [Build the static site](how-to/build-the-static-site.md).
- [Validate a source snapshot](how-to/validate-a-source-snapshot.md).
- [Look up the repository layout](reference/repository-layout.md).
- [Look up generated site artefacts](reference/generated-site-artefacts.md).
- [Understand deterministic site generation](explanation/deterministic-site-generation.md).

Publication, post-deployment verification and detailed workflow operation remain in the README or their current flat documents until issue #236 migrates them.

### Run and review governed analysis

- [Run a governed LLM dry run](how-to/run-governed-llm-dry-run.md) to produce and inspect an artefact-only accepted or rejected result.
- [Create a governed rolling-review pull request](how-to/create-governed-rolling-review-pr.md) when an approved configuration may promote accepted structured analysis into controlled source files.
- [Look up the governed analysis contract](reference/governed-analysis-contract.md) for evidence, claim, provenance and policy rules.
- [Look up the governed workflows](reference/governed-llm-workflows.md) for triggers, inputs, permissions, artefacts and repository effects.
- [Understand the evidence and analysis boundary](explanation/evidence-and-analysis-boundary.md) before treating generated analysis as reviewable repository content.

### Look up current contracts

The governed-analysis reference set is organised under `docs/reference/`. These remaining flat documents stay canonical until issue #236 lands:

- [Crypto snapshot quality contract](crypto-snapshot-quality-contract.md)
- [Deterministic crypto report schema](deterministic-crypto-report-schema.md)
- [Report self-proof evidence contract](report-self-proof-evidence-contract.md)

### Contribute documentation

Follow [Contribute documentation](how-to/contribute-documentation.md) for page purpose, metadata, links and review requirements.

## Documentation modes

CryptoPulse uses four documentation modes. Each page has one primary purpose even when it links to another mode.

### Tutorials

Tutorials guide a new reader through a safe sequence that produces an observable result. They minimise choices and link to deeper material after the reader succeeds.

- [Build and inspect CryptoPulse locally](tutorials/build-and-inspect-cryptopulse-locally.md)

### How-to guides

How-to guides solve one concrete problem for a reader who already understands the context. They contain the steps required to achieve the goal and link to reference for exhaustive detail.

- [Build the static site](how-to/build-the-static-site.md)
- [Validate a source snapshot](how-to/validate-a-source-snapshot.md)
- [Contribute documentation](how-to/contribute-documentation.md)
- [Run a governed LLM dry run](how-to/run-governed-llm-dry-run.md)
- [Create a governed rolling-review pull request](how-to/create-governed-rolling-review-pr.md)

### Reference

Reference pages describe contracts, commands, paths, configuration, workflows and artefact formats precisely and neutrally.

- [Repository layout](reference/repository-layout.md)
- [Generated site artefacts](reference/generated-site-artefacts.md)
- [Governed analysis contract](reference/governed-analysis-contract.md)
- [Governed LLM workflows](reference/governed-llm-workflows.md)
- [Offline validation pipeline](reference/offline-validation-pipeline.md)
- [Governed OpenRouter client](reference/governed-openrouter-client.md)

### Explanation

Explanation pages describe architecture, rationale, trade-offs, provenance, deterministic generation, fail-closed validation, trust boundaries and governance decisions.

- [Deterministic site generation](explanation/deterministic-site-generation.md)
- [Evidence and analysis boundary](explanation/evidence-and-analysis-boundary.md)
- [Fail-closed analysis validation](explanation/fail-closed-analysis-validation.md)
- [Trusted main and secret isolation](explanation/trusted-main-and-secret-isolation.md)

## Records outside the documentation system

These paths are intentionally separate from Diátaxis documentation:

- [`planning/`](../planning/README.md) — roadmap intent, delivery records and close-out evidence;
- [`evaluation/`](../evaluation/phase-05/README.md) — model evaluation evidence and decisions;
- [`tests/`](../tests/) — tests, fixtures and fixture-specific notes;
- [`schemas/`](../schemas/) — machine-readable contracts;
- [`prompts/`](../prompts/) — versioned prompt artefacts;
- [`config/`](../config/) — executable configuration;
- [`reports/`](../reports/) — source report content.

Reference and explanation pages link to these canonical artefacts rather than copying them into `docs/`.

## Migration status

The authoritative migration plan is [`planning/documentation/diataxis-migration.md`](../planning/documentation/diataxis-migration.md). Parent issue #232 tracks execution status. The governed-analysis pilot and local learning journey are complete in the new structure; other flat documents remain available until issue #236 migrates or preserves them deliberately.
