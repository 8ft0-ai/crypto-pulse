# Repository layout

> **Mode:** Reference  
> **Audience:** CryptoPulse contributors, operators and reviewers  
> **Outcome:** Look up the responsibility and source-of-truth status of the main repository paths.

## Top-level paths

| Path | Responsibility | Source-of-truth status |
| --- | --- | --- |
| `README.md` | Concise repository entry point and quick start. | Human front door; detailed guidance belongs under `docs/`. |
| `AGENTS.md` | Repository-wide operating rules for coding agents and maintainers. | Canonical machine-oriented instruction file. |
| `.agents/` | Specialised agent skills and runbooks. | Machine-oriented guidance retained beside agent tooling. |
| `.github/` | GitHub Actions workflows and contribution templates. | Canonical automation configuration. |
| `analysis/` | Accepted generated analysis and provenance records. | Source-controlled accepted analysis artefacts only. |
| `config/` | Executable source, generation and validation configuration. | Canonical configuration. |
| `data/` | Checked-in source snapshots and related evidence inputs. | Immutable source evidence used by validation and generation. |
| `docs/` | Current human documentation organised by Diátaxis. | Canonical tutorials, how-to guides, reference and explanation. |
| `evaluation/` | Model and workflow evaluation evidence and decisions. | Historical and governance evidence, not current operating documentation. |
| `llm_analysis/` | Governed evidence projection, provider, validation, rendering and publication modules. | Canonical governed-analysis implementation. |
| `planning/` | Roadmap intent, delivery records, decisions and close-out evidence. | Planning and historical delivery evidence. |
| `prompts/` | Versioned provider prompt artefacts. | Canonical prompts. |
| `reports/` | Archived Markdown report source content. | Source of truth for the generated report site. |
| `schemas/` | Machine-readable JSON contracts. | Canonical schemas. |
| `scripts/` | Collection, validation, compatibility and site-build implementation modules. | Executable repository tooling. |
| `site/` | Checked-in static-site source assets. | Source assets copied or transformed into generated output. |
| `site_generator/` | Canonical Python package entry point and build orchestration. | Canonical local and CI site build interface. |
| `tests/` | Unit tests, fixtures and test-specific notes. | Validation evidence and fixture contracts. |
| `_site/` | Generated static site. | Disposable output; never source-controlled. |

## Documentation layout

```text
docs/
├── index.md
├── tutorials/
├── how-to/
├── reference/
└── explanation/
```

Only current documentation for learning, operating, looking up or understanding CryptoPulse belongs here. Planning, evaluation and test evidence remains in its domain-specific path.

## Market evidence and report paths

Checked-in source snapshots use:

```text
data/crypto/hourly/YYYY/MM/DD/<time>_<timezone>_source_snapshot.json
```

The report archive contains three path families with different owners.

Legacy or demonstration reports may retain descriptive historical filenames such as:

```text
reports/crypto/hourly/YYYY/MM/DD/<time>_<timezone>_crypto_market_intelligence.md
```

Deterministic snapshot reports produced by [`scripts/generate_crypto_report.py`](../../scripts/generate_crypto_report.py) use:

```text
reports/crypto/hourly/YYYY/MM/DD/<time>_<timezone>.md
```

Accepted governed-analysis source files use:

```text
analysis/crypto/hourly/YYYY/MM/DD/governed/<time>_<timezone>_analysis.json
analysis/crypto/hourly/YYYY/MM/DD/governed/<time>_<timezone>_provenance.json
reports/crypto/hourly/YYYY/MM/DD/governed/<time>_<timezone>_crypto_market_intelligence.md
```

The complete deterministic report contract is [Deterministic report schema](deterministic-report-schema.md). The governed output contract is [Governed analysis contract](governed-analysis-contract.md).

## Site-generation paths

The canonical command is:

```bash
python -m site_generator
```

The package entry point invokes [`site_generator/pipeline.py`](../../site_generator/pipeline.py), which orchestrates the build stages implemented by the existing site modules under `scripts/`.

Report Markdown beneath `reports/crypto/hourly/` maps to the same relative path beneath `_site/archive/`, with `.md` replaced by `.html`.

Example:

```text
reports/crypto/hourly/2026/05/09/1848_AEST_crypto_market_intelligence.md
    ↓
_site/archive/2026/05/09/1848_AEST_crypto_market_intelligence.html
```

For the complete generated output catalogue, see [Generated site artefacts](generated-site-artefacts.md).

## Validation entry points

| Goal | Command or path |
| --- | --- |
| Run all unit tests | `python -m unittest discover -s tests` |
| Validate documentation | `python scripts/validate_documentation.py` |
| Build the static site | `python -m site_generator` |
| Validate source snapshots | `python scripts/validate_crypto_snapshot.py <path>` |
| Validate pull requests | [`.github/workflows/pr-validation.yml`](../../.github/workflows/pr-validation.yml) |
| Deploy GitHub Pages | [`.github/workflows/pages.yml`](../../.github/workflows/pages.yml) |
| Verify the public site | [`.github/workflows/verify-live-pages.yml`](../../.github/workflows/verify-live-pages.yml) |

## Boundary rules

- Do not treat `_site/` as source content.
- Do not copy schemas, prompts or executable configuration into `docs/`; link to their canonical files.
- Do not move planning, evaluation or fixture evidence into the current documentation tree.
- Do not use generated analysis as market evidence for a later analysis run.
- Do not modify source snapshots or archived reports during a documentation-only change.
