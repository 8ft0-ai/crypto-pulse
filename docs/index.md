# CryptoPulse documentation

CryptoPulse is an AI-generated crypto market report demo and archive. Reports may be inaccurate, incomplete, stale, misleading or hallucinated. They are not financial advice, investment research, recommendations or trading signals.

Use this index to find documentation by what you are trying to achieve. Planning, delivery and evaluation records remain outside `docs/` so current guidance is not mixed with historical evidence.

## Choose your path

| Reader | Start here |
| --- | --- |
| New contributor | [Build and inspect CryptoPulse locally](tutorials/build-and-inspect-cryptopulse-locally.md) |
| Project operator | [Build the static site](how-to/build-the-static-site.md), [publish it](how-to/publish-the-static-site.md) or [verify the live site](how-to/verify-the-live-site.md) |
| Contract reviewer | [Source snapshot quality](reference/source-snapshot-quality.md), [deterministic report schema](reference/deterministic-report-schema.md) or [governed analysis contract](reference/governed-analysis-contract.md) |
| Architect | [Deterministic site generation](explanation/deterministic-site-generation.md), [evidence and analysis boundary](explanation/evidence-and-analysis-boundary.md) or [trusted main and secret isolation](explanation/trusted-main-and-secret-isolation.md) |
| Contributor or coding agent | [Deliver a repository slice](how-to/deliver-a-repository-slice.md) and [choose an agent write strategy](how-to/choose-agent-write-strategy.md) |

## Start by task

### Learn CryptoPulse locally

Follow [Build and inspect CryptoPulse locally](tutorials/build-and-inspect-cryptopulse-locally.md) to generate the site from checked-in report data, serve it locally and trace a Markdown source report to its rendered HTML page.

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
- [Look up the governed analysis contract](reference/governed-analysis-contract.md) for evidence, claim, provenance and policy rules.
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
- [Governed LLM workflows](reference/governed-llm-workflows.md)
- [Offline validation pipeline](reference/offline-validation-pipeline.md)
- [Governed OpenRouter client](reference/governed-openrouter-client.md)

### Explanation

- [Deterministic site generation](explanation/deterministic-site-generation.md)
- [Evidence and analysis boundary](explanation/evidence-and-analysis-boundary.md)
- [Fail-closed analysis validation](explanation/fail-closed-analysis-validation.md)
- [Trusted main and secret isolation](explanation/trusted-main-and-secret-isolation.md)

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

The authoritative migration plan is [`planning/documentation/diataxis-migration.md`](../planning/documentation/diataxis-migration.md). Parent issue #232 tracks execution status.
