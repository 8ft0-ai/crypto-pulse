# Build the static site

> **Mode:** How-to  
> **Audience:** CryptoPulse contributors and operators  
> **Outcome:** Generate and verify the local `_site/` output from the current checked-in report archive.

## Install the local dependencies

From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install pyyaml markdown
```

The canonical build requires the repository source, PyYAML and Python-Markdown. It does not require market-data credentials or an LLM provider secret.

## Run the canonical build

```bash
python -m site_generator
```

The package entry point calls `site_generator.pipeline.build()`. The pipeline removes any existing `_site/` directory and rebuilds it from the current Markdown archive and site assets.

## Verify the required output

```bash
test -f _site/index.html
test -f _site/latest.html
test -f _site/archive/index.html
test -f _site/search.html
test -f _site/manifest.json
test -f _site/search-index.json
test -f _site/feed.xml
```

To verify one known source-to-output mapping:

```bash
test -f _site/archive/2026/05/09/1848_AEST_crypto_market_intelligence.html
```

## Inspect the result locally

```bash
python -m http.server 8000 --directory _site
```

Open `http://localhost:8000/`, then inspect `latest.html`, `archive/` and `search.html`.

## Run the repository validation

Before opening a pull request that can affect the site, run:

```bash
python -m unittest discover -s tests
python -m site_generator
```

Confirm that `_site/` is not tracked or staged:

```bash
git ls-files _site
git diff --cached --name-only -- _site
```

Both commands must produce no output.

## Remove generated output

The generated site is disposable:

```bash
rm -rf _site
```

Do not commit `_site/`. GitHub Actions rebuilds the output for validation and deployment.

For a guided first build, see [Build and inspect CryptoPulse locally](../tutorials/build-and-inspect-cryptopulse-locally.md). For output paths and formats, see [Generated site artefacts](../reference/generated-site-artefacts.md).
