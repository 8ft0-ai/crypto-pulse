#!/usr/bin/env python3
"""Build CryptoPulse Pages and add the client-side archive search page.

This wrapper keeps the existing site generator as the source of the base static
site, then adds a reader-facing search experience over search-index.json.
"""

from __future__ import annotations

import shutil
from html import escape
from pathlib import Path

import build_pages_site as base


SEARCH_SCRIPT_NAME = "cryptopulse-search.js"


def relative_prefix(page_path: Path) -> str:
    """Return a prefix from an output HTML file back to the site root."""
    rel = page_path.relative_to(base.OUT)
    return "../" * (len(rel.parents) - 1)


def nav_with_search(asset_prefix: str = "") -> str:
    return f"""
      <nav class="site-nav" aria-label="Primary navigation">
        <a href="{asset_prefix}index.html">Home</a>
        <a href="{asset_prefix}latest.html">Latest</a>
        <a href="{asset_prefix}archive/index.html">Archive</a>
        <a href="{asset_prefix}search.html">Search</a>
        <a href="{asset_prefix}feed.xml">RSS</a>
        <a href="{asset_prefix}manifest.json">Manifest</a>
        <a href="{asset_prefix}search-index.json">Search index</a>
        <a href="{escape(base.GITHUB_URL)}">GitHub</a>
      </nav>
    """


def search_page() -> str:
    return f"""<!doctype html>
<html lang="en-AU">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Search | {escape(base.SITE_NAME)}</title>
  <link rel="stylesheet" href="assets/cryptopulse.css">
</head>
<body>
  <main class="page">
    <article class="brief">
      {base.demo_banner()}
      {nav_with_search()}
      <header class="hero">
        <div class="brandline"><span class="mark">CP</span> {escape(base.SITE_NAME)}</div>
        <h1>Search the CryptoPulse archive</h1>
        <p>Search archived AI-generated demo reports by asset, headline, date, source, or report path.</p>
        {base.badges()}
      </header>
      <section class="content search-content">
        <section class="search-panel" aria-label="Archive search">
          <div>
            <div class="eyebrow">Archive search</div>
            <h2>Find a demo report</h2>
            <p class="muted">Search runs locally in your browser over <code>search-index.json</code>. Results are archived report metadata, not live market data.</p>
          </div>
          <form id="search-form" class="search-form" role="search">
            <label for="search-query">Search query</label>
            <div class="search-input-row">
              <input id="search-query" name="q" type="search" autocomplete="off" placeholder="Try BTC, ETH, SOL, 2026-05-11, ETF, liquidations">
              <button type="submit">Search</button>
            </div>
          </form>
          <div class="search-suggestions" aria-label="Suggested searches">
            <button type="button" data-search-suggestion="BTC">BTC</button>
            <button type="button" data-search-suggestion="ETH">ETH</button>
            <button type="button" data-search-suggestion="SOL">SOL</button>
            <button type="button" data-search-suggestion="ETF">ETF</button>
            <button type="button" data-search-suggestion="liquidations">Liquidations</button>
            <button type="button" data-search-suggestion="altcoin">Altcoin</button>
          </div>
        </section>
        <section class="search-results-section" aria-live="polite">
          <div id="search-status" class="search-status">Loading archive index…</div>
          <div id="search-results" class="search-results"></div>
        </section>
      </section>
      {base.footer()}
    </article>
  </main>
  <script src="assets/{SEARCH_SCRIPT_NAME}" defer></script>
</body>
</html>
"""


def copy_search_asset() -> None:
    source = base.SITE_SRC / "assets" / SEARCH_SCRIPT_NAME
    destination = base.OUT / "assets" / SEARCH_SCRIPT_NAME
    if not source.exists():
        raise FileNotFoundError(f"Missing search script: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(source, destination)


def add_search_link_to_existing_pages() -> None:
    for html_file in base.OUT.glob("**/*.html"):
        if html_file.name == "search.html":
            continue
        html = html_file.read_text(encoding="utf-8")
        if ">Search</a>" in html:
            continue
        prefix = relative_prefix(html_file)
        html = html.replace(
            f'<a href="{prefix}feed.xml">RSS</a>',
            f'<a href="{prefix}search.html">Search</a>\n        <a href="{prefix}feed.xml">RSS</a>',
        )
        html = html.replace("RSS feed, and manifest", "RSS feed, search page, and manifest")
        html_file.write_text(html, encoding="utf-8")


def build() -> None:
    base.build()
    copy_search_asset()
    (base.OUT / "search.html").write_text(search_page(), encoding="utf-8")
    add_search_link_to_existing_pages()
    print("Added CryptoPulse archive search page.")


if __name__ == "__main__":
    build()
