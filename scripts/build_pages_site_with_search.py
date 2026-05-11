#!/usr/bin/env python3
"""Build CryptoPulse Pages and add search and dashboard enhancements.

This wrapper keeps the existing site generator as the source of the base static
site, then adds reader-facing enhancements over the generated output.
"""

from __future__ import annotations

import re
import shutil
from html import escape
from pathlib import Path

import build_pages_site as base


SEARCH_SCRIPT_NAME = "cryptopulse-search.js"
HEADING_RE = re.compile(r"^(#{2,4})\s+(?:\d+\.\s*)?(?P<title>.+?)\s*$", re.IGNORECASE | re.MULTILINE)
ASSET_SYMBOLS = (
    "BTC", "ETH", "SOL", "XRP", "BNB", "ADA", "DOGE", "LINK", "SUI", "ONDO",
    "ZEC", "XMR", "TON", "TAO", "ATOM", "HYPE", "TRX", "DOT", "UNI", "HBAR",
)


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


def normalise_heading(title: str) -> str:
    title = base.strip_chatgpt_citations(title)
    title = re.sub(r"^\d+\.\s*", "", title)
    return re.sub(r"\s+", " ", title.strip().lower())


def markdown_section(markdown_text: str, title: str) -> str:
    """Return a Markdown section by heading title, stopping at same-or-higher heading."""
    wanted = normalise_heading(title)
    matches = list(HEADING_RE.finditer(markdown_text))
    for index, match in enumerate(matches):
        if normalise_heading(match.group("title")) != wanted:
            continue
        level = len(match.group(1))
        end = len(markdown_text)
        for next_match in matches[index + 1:]:
            if len(next_match.group(1)) <= level:
                end = next_match.start()
                break
        return markdown_text[match.end():end].strip()
    return ""


def clean_line(line: str) -> str:
    line = base.strip_chatgpt_citations(line)
    line = re.sub(r"^[-*+]\s+", "", line.strip())
    line = re.sub(r"^\d+[.)]\s+", "", line)
    line = re.sub(r"[*_`]+", "", line)
    return line.strip(" .")


def first_text_line(block: str) -> str:
    for raw_line in block.splitlines():
        line = clean_line(raw_line)
        if not line or line.startswith("#") or line.startswith("|") or line == "---":
            continue
        return line
    return ""


def extract_data_quality(body: str, metadata: dict[str, object]) -> str:
    match = re.search(r"Data quality:\s*(?P<items>(?:\n\s*-\s+.+)+)", body, re.IGNORECASE)
    if match:
        items: list[str] = []
        for raw_line in match.group("items").splitlines():
            item = clean_line(raw_line)
            if item:
                items.append(item)
        if items:
            return "; ".join(items[:5])

    live_status = metadata.get("live_data_status")
    if live_status:
        return f"Live data status: {live_status}"
    return "Detailed data-quality status was not specified in the archived report."


def extract_trend_confidence(body: str) -> str:
    match = re.search(r"Trend confidence:\s*(?P<value>[^\n]+)", body, re.IGNORECASE)
    if not match:
        return "Not specified"
    value = clean_line(match.group("value"))
    sentence = value.split(".", 1)[0].strip()
    return sentence or value


def extract_leaders(body: str) -> str:
    gainers = markdown_section(body, "Top gainers among major liquid assets")
    leaders: list[str] = []
    for line in gainers.splitlines():
        cells = [clean_line(cell) for cell in line.strip().strip("|").split("|")]
        if len(cells) < 2:
            candidate = clean_line(line).split(" ", 1)[0]
        else:
            candidate = cells[0]
        symbol_match = re.search(r"\b[A-Z][A-Z0-9_]{1,12}\b", candidate)
        if symbol_match:
            symbol = symbol_match.group(0)
            if symbol not in {"ASSET", "RANK"} and symbol not in leaders:
                leaders.append(symbol)
        if len(leaders) >= 5:
            break

    if leaders:
        return ", ".join(leaders)

    upper_body = base.strip_chatgpt_citations(body).upper()
    fallback = [symbol for symbol in ASSET_SYMBOLS if symbol in upper_body]
    return ", ".join(fallback[:5]) if fallback else "Open latest report for asset detail"


def extract_main_risk(body: str) -> str:
    cleaned = re.sub(r"\s+", " ", base.strip_chatgpt_citations(body))
    risk_match = re.search(
        r"(?:main|principal|key)\s+(?:near-term\s+)?risk(?: over the next few hours)?(?: remains| is)?\s*[:\-]?\s*(?P<risk>[^.]+)",
        cleaned,
        re.IGNORECASE,
    )
    if risk_match:
        return clean_line(risk_match.group("risk"))

    invalidate = markdown_section(body, "What would invalidate the trend")
    return first_text_line(invalidate) or "Open latest report for risk detail"


def latest_market_read_panel(report: base.Report) -> str:
    raw = report.source_path.read_text(encoding="utf-8")
    metadata, body = base.split_front_matter(raw)
    body = base.strip_chatgpt_citations(body)

    rolling = markdown_section(body, "Rolling trend analysis")
    emerging = first_text_line(markdown_section(rolling, "Emerging trend")) if rolling else ""
    analyst_read = first_text_line(markdown_section(rolling, "Analyst read")) if rolling else ""

    if not emerging:
        emerging = "Market regime was not explicitly extracted; open the latest report for the full archived read."
    if not analyst_read:
        analyst_read = report.headline

    trend_confidence = extract_trend_confidence(body)
    leaders = extract_leaders(body)
    main_risk = extract_main_risk(body)
    data_quality = extract_data_quality(body, metadata)

    return f"""
        <section class="latest-market-read" aria-label="Latest market read">
          <div class="latest-market-read-header">
            <div>
              <div class="eyebrow">Latest market read</div>
              <h2>Archived report regime summary</h2>
              <p class="muted">Extracted from the latest archived AI-generated demo report, timestamped {escape(report.timestamp)}. This is not live verified market data.</p>
            </div>
            <a class="button" href="{escape(report.url)}">Open source report</a>
          </div>
          <div class="market-read-grid">
            <article class="market-read-card market-read-card-wide">
              <span>Fact from latest report</span>
              <strong>{escape(emerging)}</strong>
            </article>
            <article class="market-read-card">
              <span>Trend confidence</span>
              <strong>{escape(trend_confidence)}</strong>
            </article>
            <article class="market-read-card">
              <span>Leading assets</span>
              <strong>{escape(leaders)}</strong>
            </article>
            <article class="market-read-card market-read-card-wide">
              <span>Analyst interpretation</span>
              <strong>{escape(analyst_read)}</strong>
            </article>
            <article class="market-read-card">
              <span>Main risk</span>
              <strong>{escape(main_risk)}</strong>
            </article>
            <article class="market-read-card">
              <span>Data limitation</span>
              <strong>{escape(data_quality)}</strong>
            </article>
          </div>
        </section>
    """


def add_latest_market_read_to_homepage() -> None:
    reports = base.collect_reports()
    if not reports:
        return
    index_path = base.OUT / "index.html"
    html = index_path.read_text(encoding="utf-8")
    if "latest-market-read" in html:
        return
    panel = latest_market_read_panel(reports[0])
    html = html.replace(
        '        <div class="explainer-grid">',
        f'{panel}\n        <div class="explainer-grid">',
        1,
    )
    index_path.write_text(html, encoding="utf-8")


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
    add_latest_market_read_to_homepage()
    add_search_link_to_existing_pages()
    print("Added CryptoPulse archive search page and latest market read panel.")


if __name__ == "__main__":
    build()
