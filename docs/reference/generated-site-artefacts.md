# Generated site artefacts

> **Mode:** Reference  
> **Audience:** CryptoPulse contributors, operators and reviewers  
> **Outcome:** Look up the files produced by the canonical static-site build and the source material from which they are derived.

## Build command and output root

```bash
python -m site_generator
```

The build removes any existing `_site/` directory and writes a complete replacement beneath:

```text
_site/
```

`_site/` is deployment output. It is not committed.

## Top-level pages and indexes

| Generated path | Purpose | Primary source |
| --- | --- | --- |
| `_site/index.html` | Homepage, product boundary and latest-report card. | Report archive plus repository-owned templates. |
| `_site/latest.html` | Copy of the latest rendered report page. | Newest accepted Markdown report by generator sort order. |
| `_site/archive/index.html` | Full report archive. | All matching Markdown reports under `reports/crypto/hourly/`. |
| `_site/search.html` | Browser-side archive search and filters. | Repository-owned template and `search-index.json`. |
| `_site/manifest.json` | Machine-readable latest-report and archive index. | Parsed report metadata and generated URLs. |
| `_site/search-index.json` | Search and filter records for archived reports. | Parsed report metadata, headings and structured fields. |
| `_site/feed.xml` | RSS feed for report entries. | Parsed report metadata and generated URLs. |

## Rendered report pages

A source report matching:

```text
reports/crypto/hourly/<relative-path>.md
```

is rendered as:

```text
_site/archive/<relative-path>.html
```

Example:

```text
reports/crypto/hourly/2026/05/09/1848_AEST_crypto_market_intelligence.md
    ↓
_site/archive/2026/05/09/1848_AEST_crypto_market_intelligence.html
```

The source Markdown remains authoritative. The HTML page adds repository-owned navigation, demo and non-advice notices, metadata, source presentation, table of contents and archive navigation.

## Static assets

The generated site includes repository-owned CSS and JavaScript under `_site/assets/`.

| Generated asset | Responsibility |
| --- | --- |
| `assets/cryptopulse.css` | Base site and report presentation. |
| `assets/cryptopulse-data-quality.css` | Data-quality panel presentation. |
| `assets/cryptopulse-product-demo.css` | Product-demo framing and boundary notices. |
| `assets/cryptopulse-report-ux.css` | Report-reading and responsive UX. |
| `assets/cryptopulse-report-ux.js` | Progressive report-reading behaviour. |
| `assets/cryptopulse-brief-glance.css` | Brief-at-a-glance presentation. |
| `assets/cryptopulse-structured-sources.css` | Structured source-card presentation. |
| `assets/cryptopulse-search-filters.css` | Archive search and filter presentation. |
| `assets/cryptopulse-accessibility.css` | Skip-link and reader-navigation accessibility refinements. |

The checked-in source assets remain under `site/` and the site-build implementation under `scripts/` and `site_generator/`.

## Expected validation artefacts

Pull-request validation checks at least:

```text
_site/index.html
_site/latest.html
_site/archive/index.html
_site/search.html
_site/search-index.json
_site/assets/cryptopulse.css
_site/assets/cryptopulse-report-ux.js
_site/assets/cryptopulse-search-filters.css
_site/assets/cryptopulse-accessibility.css
```

A successful build should also contain the manifest, RSS feed and one HTML page for every matching source report.

## Disposal and reproducibility

Use these commands to confirm that generated output is not source-controlled:

```bash
git ls-files _site
git diff --cached --name-only -- _site
```

Both outputs must be empty before a pull request is merged.

Remove the generated site with:

```bash
rm -rf _site
```

Re-running the canonical build recreates the output from the current repository sources.

For the operating procedure, see [Build the static site](../how-to/build-the-static-site.md). For why generated output remains disposable, see [Deterministic site generation](../explanation/deterministic-site-generation.md).
