#!/usr/bin/env python3
"""Build CryptoPulse Pages with structured search-index metadata and filters."""

from __future__ import annotations

import json
import re
import shutil
from html import escape
from pathlib import Path
from typing import Any

import build_pages_site_brief_glance as site


SEARCH_FILTER_STYLE_NAME = "cryptopulse-search-filters.css"
SEARCH_FILTERS_MARKER = "search-filter-panel"
ASSET_SYMBOLS = (
    "BTC", "ETH", "SOL", "XRP", "BNB", "ADA", "DOGE", "LINK", "SUI", "ONDO",
    "ZEC", "XMR", "TON", "TAO", "ATOM", "HYPE", "TRX", "DOT", "UNI", "HBAR",
)


def base() -> Any:
    return site.base()


def enhanced() -> Any:
    return site.enhanced()


def relative_prefix(page_path: Path) -> str:
    rel = page_path.relative_to(base().OUT)
    return "../" * (len(rel.parents) - 1)


def copy_asset(filename: str) -> None:
    source = base().SITE_SRC / "assets" / filename
    destination = base().OUT / "assets" / filename
    if not source.exists():
        raise FileNotFoundError(f"Missing asset: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(source, destination)


def add_filter_stylesheet_links() -> None:
    for html_file in base().OUT.glob("**/*.html"):
        html = html_file.read_text(encoding="utf-8")
        if SEARCH_FILTER_STYLE_NAME in html:
            continue
        prefix = relative_prefix(html_file)
        html = html.replace(
            "</head>",
            f'  <link rel="stylesheet" href="{prefix}assets/{SEARCH_FILTER_STYLE_NAME}">\n</head>',
            1,
        )
        html_file.write_text(html, encoding="utf-8")


def normalise_status(value: str) -> str:
    text = re.sub(r"[^a-z]+", " ", value.lower()).strip()
    if not text or "not specified" in text:
        return "not_specified"
    if any(token in text for token in ("unavailable", "missing", "failed", "not accessible")):
        return "unavailable"
    if any(token in text for token in ("partial", "delayed", "incomplete", "limited", "mixed")):
        return "partial"
    if any(token in text for token in ("full", "available", "current", "complete")):
        return "full"
    return "not_specified"


def trend_bucket(value: str) -> str:
    match = re.search(r"\b(high|medium|low)\b", value, re.IGNORECASE)
    return match.group(1).lower() if match else "not_specified"


def report_date(report: Any) -> str:
    timestamp = str(report.timestamp or "")
    match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", timestamp)
    if match:
        return match.group(1)
    if report.year and report.month and report.day:
        return f"{report.year}-{report.month}-{report.day}"
    return ""


def extract_assets(metadata: dict[str, Any], body: str) -> list[str]:
    assets: list[str] = []
    raw_assets = metadata.get("primary_assets") or metadata.get("assets") or []
    if isinstance(raw_assets, str):
        raw_assets = re.split(r"[,\s]+", raw_assets)
    if isinstance(raw_assets, list):
        for raw in raw_assets:
            symbol = site.as_text(raw).upper()
            if symbol in ASSET_SYMBOLS and symbol not in assets:
                assets.append(symbol)

    body_upper = body.upper()
    for symbol in ASSET_SYMBOLS:
        if symbol in assets:
            continue
        if re.search(rf"\b{re.escape(symbol)}\b", body_upper):
            assets.append(symbol)

    return assets


def filter_metadata_for_report(report: Any) -> dict[str, Any]:
    raw = report.source_path.read_text(encoding="utf-8")
    metadata, body = base().split_front_matter(raw)
    clean_body = base().strip_chatgpt_citations(body)

    trend_value = site.extract_trend_confidence(metadata, clean_body)
    data_quality = site.extract_data_quality(metadata, clean_body)
    data_quality_status = normalise_status(str(metadata.get("live_data_status") or data_quality))
    regime = site.extract_market_regime(metadata, clean_body)

    return {
        "report_date": report_date(report),
        "assets": extract_assets(metadata, clean_body),
        "trend_confidence": trend_value if trend_value != site.FALLBACK else "not_specified",
        "trend_confidence_bucket": trend_bucket(trend_value),
        "data_quality": data_quality if data_quality != site.FALLBACK else "not_specified",
        "data_quality_status": data_quality_status,
        "market_regime": regime if regime != site.FALLBACK else "not_specified",
    }


def update_search_index_with_filter_metadata() -> None:
    index_path = base().OUT / "search-index.json"
    if not index_path.exists():
        return

    reports_by_path = {report.source_rel: report for report in base().collect_reports()}
    index = json.loads(index_path.read_text(encoding="utf-8"))
    if not isinstance(index, list):
        return

    for item in index:
        if not isinstance(item, dict):
            continue
        report = reports_by_path.get(site.as_text(item.get("path")))
        if not report:
            item.setdefault("assets", [])
            item.setdefault("trend_confidence", "not_specified")
            item.setdefault("trend_confidence_bucket", "not_specified")
            item.setdefault("data_quality", "not_specified")
            item.setdefault("data_quality_status", "not_specified")
            item.setdefault("report_date", "")
            continue
        item.update(filter_metadata_for_report(report))

    index_path.write_text(json.dumps(index, indent=2), encoding="utf-8")


def filter_controls() -> str:
    asset_options = "".join(f'<option value="{asset}">{asset}</option>' for asset in ASSET_SYMBOLS[:12])
    return f"""
          <section class="search-filter-panel" aria-label="Archive filters">
            <div class="search-filter-header">
              <div>
                <div class="eyebrow">Structured filters</div>
                <h2>Filter the archive</h2>
                <p class="muted">Filters use metadata extracted from archived AI-generated reports. Missing values are shown as not specified rather than inferred.</p>
              </div>
              <button type="button" id="search-clear-filters" class="search-filter-clear">Clear filters</button>
            </div>
            <div class="search-filter-grid">
              <label for="search-asset">Asset
                <select id="search-asset" name="asset">
                  <option value="">Any asset</option>
                  {asset_options}
                </select>
              </label>
              <label for="search-data-quality">Data quality
                <select id="search-data-quality" name="data_quality">
                  <option value="">Any data quality</option>
                  <option value="full">Full</option>
                  <option value="partial">Partial</option>
                  <option value="unavailable">Unavailable</option>
                  <option value="not_specified">Not specified</option>
                </select>
              </label>
              <label for="search-trend-confidence">Trend confidence
                <select id="search-trend-confidence" name="trend_confidence">
                  <option value="">Any confidence</option>
                  <option value="high">High</option>
                  <option value="medium">Medium</option>
                  <option value="low">Low</option>
                  <option value="not_specified">Not specified</option>
                </select>
              </label>
              <label for="search-date-from">From date
                <input id="search-date-from" name="date_from" type="date">
              </label>
              <label for="search-date-to">To date
                <input id="search-date-to" name="date_to" type="date">
              </label>
            </div>
          </section>
    """


def add_filter_controls_to_search_page() -> None:
    search_path = base().OUT / "search.html"
    if not search_path.exists():
        return

    html = search_path.read_text(encoding="utf-8")
    if SEARCH_FILTERS_MARKER in html:
        return

    html = html.replace(
        '          <div class="search-suggestions" aria-label="Suggested searches">',
        f'{filter_controls()}\n          <div class="search-suggestions" aria-label="Suggested searches">',
        1,
    )
    search_path.write_text(html, encoding="utf-8")


def build() -> None:
    site.build()
    copy_asset(SEARCH_FILTER_STYLE_NAME)
    add_filter_stylesheet_links()
    update_search_index_with_filter_metadata()
    add_filter_controls_to_search_page()
    print("Added structured archive metadata and client-side search filters.")


if __name__ == "__main__":
    build()
