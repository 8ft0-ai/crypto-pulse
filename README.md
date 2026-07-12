# CryptoPulse

CryptoPulse is an AI-generated crypto market report demo and archive. It stores report source content as Markdown and publishes a disposable static site through GitHub Pages.

The reports are demonstration content only. They may be inaccurate, incomplete, stale, misleading or hallucinated. They are not financial advice, investment research, recommendations or trading signals.

## Documentation

Start with the [CryptoPulse documentation index](docs/index.md).

Common entry points:

- [Build and inspect CryptoPulse locally](docs/tutorials/build-and-inspect-cryptopulse-locally.md)
- [Build the static site](docs/how-to/build-the-static-site.md)
- [Validate a source snapshot](docs/how-to/validate-a-source-snapshot.md)
- [Publish the static site](docs/how-to/publish-the-static-site.md)
- [Verify the live site](docs/how-to/verify-the-live-site.md)
- [Governed analysis contract](docs/reference/governed-analysis-contract.md)
- [Repository layout](docs/reference/repository-layout.md)

## Quick start

From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install pyyaml markdown
python -m site_generator
python -m http.server 8000 --directory _site
```

Open:

```text
http://localhost:8000
```

The build uses checked-in report data. It does not require a market-data credential or LLM provider secret.

## Repository sources

| Path | Purpose |
| --- | --- |
| [`data/crypto/hourly/`](data/crypto/hourly/) | Checked-in source snapshots. |
| [`reports/crypto/hourly/`](reports/crypto/hourly/) | Markdown report source content. |
| [`docs/`](docs/) | Tutorials, how-to guides, reference and explanation. |
| [`site_generator/`](site_generator/) | Canonical static-site build package. |
| [`site/`](site/) | Checked-in site assets. |
| [`planning/`](planning/) | Planning, delivery and decision records. |
| [`evaluation/`](evaluation/) | Evaluation evidence and reviewed decisions. |

The generated `_site/` directory is disposable output. It may appear as untracked content locally, is rebuilt by CI and deployment workflows, and must not be staged or committed.

## Validation

Run the repository baseline before opening a pull request:

```bash
python -m unittest discover -s tests
python scripts/validate_documentation.py
python -m site_generator
```

Pull requests are also validated by [`.github/workflows/pr-validation.yml`](.github/workflows/pr-validation.yml), which runs the test suite, validates documentation navigation, rejects committed `_site/` output, builds the site and checks expected artefacts.

## Publication

[`.github/workflows/pages.yml`](.github/workflows/pages.yml) builds and deploys the current `main` site through GitHub Pages. The expected public site is:

```text
https://8ft0-ai.github.io/crypto-pulse/
```

Post-deployment browser evidence is produced by [`.github/workflows/verify-live-pages.yml`](.github/workflows/verify-live-pages.yml). See [Publish the static site](docs/how-to/publish-the-static-site.md) and [Verify the live site](docs/how-to/verify-the-live-site.md) for the operating procedures.

## Design boundary

Checked-in snapshots, accepted analysis records, Markdown reports, schemas, prompts, configuration and source assets are the reviewable repository sources. Generated HTML and raw provider completions are derived or retained evidence, not independent publication authority.

The project must present its AI-generated demo and non-advice boundary before a reader relies on any market claim.
