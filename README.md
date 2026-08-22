# CryptoPulse

CryptoPulse is an evidence-first, AI-generated crypto market demo and archive. It is designed to make public market evidence inspectable: where deterministic evidence exists, the repository—not an opaque model response—carries the factual authority.

Today the public experience combines an archive of AI-generated report examples with a bounded deterministic temporal-evidence view for one 24-slot `BTC.price_usd` series. Checked-in evidence and reviewed repository state are the traceable source boundary; generated HTML is disposable output, and gaps or degraded evidence are intended to remain visible rather than be silently filled.

CryptoPulse is a demo, not a live market terminal or investment service. Reports may be inaccurate, incomplete, stale, misleading or hallucinated. Nothing here is financial advice, investment research, a recommendation or a trading signal, and it should not be relied on for trading, investing or risk decisions.

The product principle is **evidence before intelligence**: use deterministic, reproducible evidence where possible, and keep AI-generated interpretation clearly subordinate to that evidence. Read [Product positioning](docs/explanation/product-positioning.md) for the current proposition, shipped capabilities and limits.

## Documentation

Start with the [CryptoPulse documentation index](docs/index.md).

Common entry points:

- [Product positioning](docs/explanation/product-positioning.md)
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
