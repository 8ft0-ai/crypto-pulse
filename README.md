# CryptoPulse

CryptoPulse is an AI-generated crypto market report demo and archive.

The repository stores raw generated market report examples as Markdown and publishes them as a static GitHub Pages site. The reports are demonstration content only. They are AI-created, may contain errors or stale information, and must not be treated as financial advice, investment research, recommendations, or trading signals.

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

The site is generated from the Markdown archive by:

```text
scripts/build_pages_site_mobile_ux.py
```

The build writes a disposable static site to:

```text
_site/
```

The deployed site contains:

```text
index.html                         # Home page and latest demo report card
latest.html                        # Copy of the latest demo report
archive/index.html                 # Full report archive
archive/**/*.html                  # Rendered demo reports
search.html                        # Browser-side archive search
manifest.json                      # Machine-readable latest/report index
search-index.json                  # Browser-side search index
feed.xml                           # RSS feed
assets/cryptopulse.css             # Base site styling
assets/cryptopulse-report-ux.css   # Mobile report-reading UX styling
assets/cryptopulse-report-ux.js    # Progressive report-reading UX helpers
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
scripts/build_pages_site.py
scripts/build_pages_site_with_search.py
scripts/build_pages_site_mobile_ux.py
.github/workflows/pages.yml
```

It can also be run manually from the GitHub Actions tab.

## Pull request validation

Pull requests that change reports, site assets, build scripts, workflows, documentation, or the README are validated by:

```text
.github/workflows/pr-validation.yml
```

The validation workflow builds the site, checks that expected generated artefacts exist, and rejects committed `_site/` output.

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
python scripts/build_pages_site_mobile_ux.py
python -m http.server 8000 --directory _site
```

Then open:

```text
http://localhost:8000
```

## Design principle

Raw Markdown reports are the source of truth. The GitHub Pages site is generated output and should be treated as disposable.

The user should understand that CryptoPulse is AI-generated demo content before they read any market claim.
