# Build and inspect CryptoPulse locally

> **Mode:** Tutorial  
> **Audience:** New CryptoPulse contributors  
> **Outcome:** Build the static site from checked-in report data, inspect the homepage and archive, and trace one Markdown source report to its generated HTML page.

This tutorial uses only files already committed to the repository. It does not collect live market data, call an LLM provider, require a secret or publish anything.

The complete command sequence assumes Bash or a compatible POSIX shell on macOS, Linux or Windows Subsystem for Linux. Native PowerShell users must translate the shell-specific `source`, `test` and `rm` commands before following the sequence.

## 1. Prepare the local environment

Start from a clean checkout of the repository with Python 3.11 or later available:

```bash
git clone https://github.com/8ft0-ai/crypto-pulse.git
cd crypto-pulse
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install pyyaml markdown
```

Confirm that the checked-in example report used later in this tutorial exists:

```bash
test -f reports/crypto/hourly/2026/05/09/1848_AEST_crypto_market_intelligence.md
```

A successful command produces no output.

## 2. Generate the site

Run the canonical build command from the repository root:

```bash
python -m site_generator
```

The command rebuilds the disposable `_site/` directory from the checked-in report archive and repository-owned site assets.

Confirm that the main entry points were generated:

```bash
test -f _site/index.html
test -f _site/latest.html
test -f _site/archive/index.html
test -f _site/manifest.json
test -f _site/search-index.json
```

Each command should complete without output.

## 3. Serve the generated site

Start a local HTTP server:

```bash
python -m http.server 8000 --directory _site
```

Leave this terminal running. In a browser, open:

```text
http://localhost:8000/
```

The homepage should show the CryptoPulse demo boundary, a latest-report card and links to the archive and generated developer artefacts.

Open the latest page:

```text
http://localhost:8000/latest.html
```

Then open the archive:

```text
http://localhost:8000/archive/
```

The archive should list the checked-in reports and allow you to open an individual rendered report.

## 4. Trace one source report to its generated page

The generator preserves the report's path beneath `reports/crypto/hourly/` and changes only the source root and file extension.

For this checked-in source:

```text
reports/crypto/hourly/2026/05/09/1848_AEST_crypto_market_intelligence.md
```

the generated page is:

```text
_site/archive/2026/05/09/1848_AEST_crypto_market_intelligence.html
```

Confirm that the generated page exists:

```bash
test -f _site/archive/2026/05/09/1848_AEST_crypto_market_intelligence.html
```

Open it in the browser:

```text
http://localhost:8000/archive/2026/05/09/1848_AEST_crypto_market_intelligence.html
```

The page should display the source report as HTML while adding repository-owned navigation, safety notices, metadata and source presentation.

## 5. Observe that `_site/` is generated output

In a second terminal at the repository root, ask Git which `_site/` files are tracked:

```bash
git ls-files _site
```

The command should produce no output. The generated site exists locally, but it is not part of the source archive.

Now inspect its working-tree status:

```bash
git status --short _site
```

The directory may appear as untracked generated output. Do not add or commit it. Pull-request validation rejects committed `_site/` content.

## 6. Clean up

Stop the HTTP server with `Ctrl+C`, then remove the generated site:

```bash
rm -rf _site
```

The checked-in Markdown report remains unchanged. Running `python -m site_generator` again recreates the same path structure from the repository sources.

## What you have learned

You have now completed the local documentation journey:

```text
checked-in Markdown report
        ↓
python -m site_generator
        ↓
disposable _site/ output
        ↓
local homepage, latest page, archive and rendered report
```

For the compact operating procedure, see [Build the static site](../how-to/build-the-static-site.md). For the complete output catalogue, see [Generated site artefacts](../reference/generated-site-artefacts.md). For the design rationale, see [Deterministic site generation](../explanation/deterministic-site-generation.md).
