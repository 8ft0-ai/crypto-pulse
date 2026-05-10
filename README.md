# CryptoPulse

CryptoPulse is a generated crypto market intelligence archive.

The repository stores raw generated market intelligence reports as Markdown and publishes them as a static GitHub Pages site.

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
scripts/build_pages_site.py
```

The build writes a disposable static site to:

```text
_site/
```

The deployed site contains:

```text
index.html              # Home page and latest report card
latest.html             # Copy of the latest report
archive/index.html      # Full report archive
archive/**/*.html       # Rendered reports
manifest.json           # Machine-readable latest/report index
feed.xml                # RSS feed
assets/cryptopulse.css  # Site styling
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
.github/workflows/pages.yml
```

It can also be run manually from the GitHub Actions tab.

## Required GitHub Pages setting

In the GitHub repository, enable Pages with:

```text
Settings → Pages → Build and deployment → Source → GitHub Actions
```

Once enabled, the expected site URL is:

```text
https://8ft0-ai.github.io/crypto-pulse/
```

Note: this repository is currently private. Check the repository plan/settings if the Pages deployment is not publicly accessible.

## Local build

To test locally:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install pyyaml markdown
python scripts/build_pages_site.py
python -m http.server 8000 --directory _site
```

Then open:

```text
http://localhost:8000
```

## Design principle

Raw Markdown reports are the source of truth. The GitHub Pages site is generated output and should be treated as disposable.
