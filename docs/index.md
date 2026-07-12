# CryptoPulse documentation

CryptoPulse is an AI-generated crypto market report demo and archive. Reports may be inaccurate, incomplete, stale, misleading or hallucinated. They are not financial advice, investment research, recommendations or trading signals.

Use this index to find documentation by what you are trying to achieve. Planning, delivery and evaluation records remain outside `docs/` so current guidance is not mixed with historical evidence.

## Start by task

### Learn CryptoPulse locally

The complete local tutorial will be added in issue #235. Until then, use the verified [local build instructions in the repository README](../README.md#local-build).

### Build and operate the static site

Current operating details remain in the README while the migration is in progress:

- [GitHub Pages site and generated artefacts](../README.md#github-pages-site)
- [Publishing workflow](../README.md#publishing-workflow)
- [Post-deployment live-site evidence](../README.md#post-deployment-live-site-evidence)
- [Pull-request validation](../README.md#pull-request-validation)

### Work with governed analysis

The governed-analysis documents remain available at their current paths until the pilot migration in issue #234:

- [Governed analysis contract](governed-llm-analysis-contract.md)
- [Governed dry run](governed-llm-dry-run.md)
- [Governed rolling review](governed-llm-rolling-review.md)
- [Offline governed analysis pipeline](offline-governed-analysis-pipeline.md)
- [Governed OpenRouter client](governed-openrouter-client.md)
- [Optional LLM narrative boundary](optional-llm-narrative-boundary.md)

### Look up current contracts

These documents remain canonical at their current paths until their assigned migration issues land:

- [Crypto snapshot quality contract](crypto-snapshot-quality-contract.md)
- [Deterministic crypto report schema](deterministic-crypto-report-schema.md)
- [Report self-proof evidence contract](report-self-proof-evidence-contract.md)

### Contribute documentation

Follow [How to contribute documentation](how-to/contribute-documentation.md) for page purpose, metadata, links and review requirements.

## Documentation modes

CryptoPulse uses four documentation modes. Each page has one primary purpose even when it links to another mode.

### Tutorials

Tutorials guide a new reader through a safe sequence that produces an observable result. They minimise choices and link to deeper material after the reader succeeds.

No tutorial directory is created until the first complete local learning journey lands in issue #235.

### How-to guides

How-to guides solve one concrete problem for a reader who already understands the context. They contain the steps required to achieve the goal and link to reference for exhaustive detail.

Current guides:

- [Contribute documentation](how-to/contribute-documentation.md)

### Reference

Reference pages describe contracts, commands, paths, configuration, workflows and artefact formats precisely and neutrally.

The first populated reference set will land with the governed-analysis pilot in issue #234.

### Explanation

Explanation pages describe architecture, rationale, trade-offs, provenance, deterministic generation, fail-closed validation, trust boundaries and governance decisions.

The first populated explanation set will land with the governed-analysis pilot in issue #234.

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

The authoritative migration plan is [`planning/documentation/diataxis-migration.md`](../planning/documentation/diataxis-migration.md). Parent issue #232 tracks execution status. Existing flat documents remain available during the staged migration so the README and current operational paths stay usable until their replacements are merged.
