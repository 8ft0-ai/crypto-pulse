# CryptoPulse

CryptoPulse is an AI-generated crypto market report demo and archive.

The repository stores raw generated market report examples as Markdown and publishes them as a static GitHub Pages site. The reports are demonstration content only. They are AI-created, may contain errors or stale information, and must not be treated as financial advice, investment research, recommendations, or trading signals.

## Documentation

Start with the [CryptoPulse documentation index](docs/index.md) to find learning material, operating guides, contracts and architectural explanations. The documentation is being migrated incrementally so the current README remains usable until the new destination is complete.

## Report archive

Hourly crypto reports are archived under:

```text
reports/crypto/hourly/YYYY/MM/DD/HHMM_TZ_crypto_market_intelligence.md
```

Example:

```text
reports/crypto/hourly/2026/05/09/1848_AEST_crypto_market_intelligence.md
```

The archive process should preserve the generated report body exactly and add YAML front matter only when required.

## GitHub Pages site

The canonical build command is:

```bash
python -m site_generator
```

The build writes a disposable static site to:

```text
_site/
```

The deployed site contains:

```text
index.html                               # Home page and latest demo report card
latest.html                              # Copy of the latest demo report
archive/index.html                       # Full report archive
archive/**/*.html                        # Rendered demo reports
search.html                              # Browser-side archive search and filters
manifest.json                            # Machine-readable latest/report index
search-index.json                        # Browser-side search/filter index
feed.xml                                 # RSS feed
assets/cryptopulse.css                   # Base site styling
assets/cryptopulse-data-quality.css      # Data-quality panel styling
assets/cryptopulse-product-demo.css      # Product-demo framing
assets/cryptopulse-report-ux.css         # Mobile report-reading UX styling
assets/cryptopulse-report-ux.js          # Progressive report-reading UX helpers
assets/cryptopulse-brief-glance.css      # Brief-at-a-glance panel styling
assets/cryptopulse-structured-sources.css # Structured source-card styling
assets/cryptopulse-search-filters.css    # Archive search/filter styling
```

## Generator architecture

The canonical generator package is:

```text
site_generator/
  __init__.py
  __main__.py
  pipeline.py
```

`site_generator.pipeline` orchestrates the build stages directly:

1. base site generation;
2. search page, latest-market-read, metadata chips, and data-quality panels;
3. product framing, simplified navigation, developer-output links, and mobile UX;
4. brief-at-a-glance panels and structured source cards;
5. structured search-index metadata and client-side archive filters.

The older scripts under `scripts/` remain as implementation modules and compatibility shims during the refactor, but GitHub Actions and local documentation should use the package command above rather than invoking stacked wrappers directly.

Rollback path: if the package orchestration needs to be backed out quickly, the Pages workflow can temporarily be switched back to the previous implementation command:

```bash
python scripts/build_pages_site_search_filters.py
```

## Publishing workflow

GitHub Pages is deployed by:

```text
.github/workflows/pages.yml
```

The workflow runs when changes are pushed to:

```text
reports/crypto/hourly/**/*.md
site/**
site_generator/**
scripts/build_pages_site.py
scripts/build_pages_site_with_search.py
scripts/build_pages_site_mobile_ux.py
scripts/build_pages_site_brief_glance.py
scripts/build_pages_site_search_filters.py
.github/workflows/pages.yml
```

It can also be run manually from the GitHub Actions tab.

## Post-deployment live-site evidence

After a successful Pages deployment, this workflow checks the public site with Chromium:

```text
.github/workflows/verify-live-pages.yml
```

It captures rendered HTML, visible text, full-page screenshots, structured results and Axe accessibility evidence for the homepage, latest report, archive and search. Every run uploads a 30-day artifact named:

```text
cryptopulse-live-site-evidence
```

The workflow can also be started manually. See `docs/live-site-evidence.md` for the checks, artifact contents and review steps.

## Pull request validation

Pull requests that change reports, site assets, build scripts, workflows, documentation, planning assets, tests, config, or the README are validated by:

```text
.github/workflows/pr-validation.yml
```

The validation workflow builds the site with `python -m site_generator`, checks that expected generated artefacts exist, runs unit tests, and rejects committed `_site/` output.

For the recommended `main` branch protection settings, see:

```text
docs/main-branch-protection.md
```

## Required GitHub Pages setting

In the GitHub repository, enable Pages with:

```text
Settings → Pages → Build and deployment → Source → GitHub Actions
```

Once enabled, the expected site URL is:

```text
https://8ft0-ai.github.io/crypto-pulse/
```

## Local build

To test locally:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install pyyaml markdown
python -m site_generator
python -m http.server 8000 --directory _site
```

Then open:

```text
http://localhost:8000
```

## Design principle

Raw Markdown reports are the source of truth. The GitHub Pages site is generated output and should be treated as disposable.

The user should understand that CryptoPulse is AI-generated demo content before they read any market claim.
