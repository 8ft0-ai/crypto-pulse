#!/usr/bin/env python3
"""Build CryptoPulse Pages with brief-at-a-glance and structured source panels."""

from __future__ import annotations

import json
import re
import shutil
from html import escape
from pathlib import Path
from typing import Any

import build_pages_site_mobile_ux as site


BRIEF_GLANCE_STYLE_NAME = "cryptopulse-brief-glance.css"
STRUCTURED_SOURCE_STYLE_NAME = "cryptopulse-structured-sources.css"
REPORT_CONTENT_RE = re.compile(r'<section class="content report-content">')
REPORT_WARNING_RE = re.compile(
    r'(      <section class="report-warning compact-warning">.*?</section>\n)',
    re.DOTALL,
)
SOURCE_PANEL_RE = re.compile(
    r'\s*<section class="metadata-panel source-panel" aria-label="Report source attribution">.*?</section>\s*',
    re.DOTALL,
)
SENTENCE_END_RE = re.compile(r"(?<=[.!?])\s+")
FALLBACK = "Not specified in archived report."

SOURCE_CATEGORY_LABELS = {
    "market_data": "Market data",
    "market": "Market data",
    "prices": "Market data",
    "derivatives_data": "Derivatives / liquidations",
    "derivatives": "Derivatives / liquidations",
    "liquidations": "Derivatives / liquidations",
    "etf_flows": "ETF / institutional flows",
    "institutional_flows": "ETF / institutional flows",
    "etf": "ETF / institutional flows",
    "news": "News and macro",
    "macro": "News and macro",
    "regulation": "Regulation / official releases",
    "official_release": "Regulation / official releases",
    "official_releases": "Regulation / official releases",
    "protocol_update": "Protocol / exchange announcements",
    "protocol_updates": "Protocol / exchange announcements",
    "exchange_announcement": "Protocol / exchange announcements",
    "exchange_announcements": "Protocol / exchange announcements",
    "other": "Other",
}
SOURCE_CATEGORY_ORDER = [
    "Market data",
    "Derivatives / liquidations",
    "ETF / institutional flows",
    "News and macro",
    "Regulation / official releases",
    "Protocol / exchange announcements",
    "Other",
]


def base() -> Any:
    return site.enhanced.base


def enhanced() -> Any:
    return site.enhanced


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


def add_stylesheet_links() -> None:
    for html_file in base().OUT.glob("**/*.html"):
        html = html_file.read_text(encoding="utf-8")
        prefix = relative_prefix(html_file)
        for stylesheet_name in (BRIEF_GLANCE_STYLE_NAME, STRUCTURED_SOURCE_STYLE_NAME):
            if stylesheet_name in html:
                continue
            html = html.replace(
                "</head>",
                f'  <link rel="stylesheet" href="{prefix}assets/{stylesheet_name}">\n</head>',
                1,
            )
        html_file.write_text(html, encoding="utf-8")


def as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return enhanced().clean_line(value)
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        parts = [as_text(item) for item in value]
        return ", ".join(part for part in parts if part)
    if isinstance(value, dict):
        for key in ("summary", "value", "read", "label", "status", "text"):
            if key in value:
                text = as_text(value[key])
                if text:
                    return text
        parts = [as_text(item) for item in value.values()]
        return ", ".join(part for part in parts if part)
    return enhanced().clean_line(str(value))


def metadata_field(metadata: dict[str, Any], *keys: str) -> str:
    normalised = {key.lower().replace("-", "_"): value for key, value in metadata.items()}
    for key in keys:
        value = normalised.get(key.lower().replace("-", "_"))
        text = as_text(value)
        if text:
            return text
    return ""


def first_sentence(text: str, limit: int = 220) -> str:
    text = re.sub(r"\s+", " ", enhanced().clean_line(text)).strip()
    if not text:
        return ""
    sentence = SENTENCE_END_RE.split(text, maxsplit=1)[0].strip()
    if len(sentence) > limit:
        return sentence[: limit - 1].rstrip() + "…"
    return sentence


def extract_market_regime(metadata: dict[str, Any], body: str) -> str:
    from_metadata = metadata_field(
        metadata,
        "market_regime",
        "emerging_trend",
        "regime",
        "trend",
        "market_mode",
    )
    if from_metadata:
        return first_sentence(from_metadata)

    rolling = enhanced().markdown_section(body, "Rolling trend analysis")
    emerging = enhanced().markdown_section(rolling, "Emerging trend") if rolling else ""
    if emerging:
        return first_sentence(enhanced().first_text_line(emerging))

    analyst = enhanced().markdown_section(rolling, "Analyst read") if rolling else ""
    if analyst:
        return first_sentence(enhanced().first_text_line(analyst))

    return FALLBACK


def asset_row_read(body: str, symbol: str) -> str:
    for line in body.splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = enhanced().table_cells(line)
        if enhanced().looks_like_separator(cells) or len(cells) < 2:
            continue
        if not any(enhanced().asset_matches(cell, symbol) for cell in cells[:3]):
            continue

        note = cells[-1] if cells[-1].lower() not in {"note", "read", "observation"} else ""
        one_hour = ""
        day = ""
        changes = enhanced().extract_asset_changes(body, symbol)
        if changes.get("1h"):
            one_hour = f"1h {changes['1h']}"
        if changes.get("24h"):
            day = f"24h {changes['24h']}"
        parts = [part for part in (one_hour, day, note) if part]
        if parts:
            return f"{symbol}: " + "; ".join(parts[:3])
    return ""


def extract_btc_eth_read(metadata: dict[str, Any], body: str) -> str:
    from_metadata = metadata_field(metadata, "btc_eth_read", "btc_eth", "major_asset_read")
    if from_metadata:
        return first_sentence(from_metadata, limit=260)

    reads = [asset_row_read(body, symbol) for symbol in ("BTC", "ETH")]
    reads = [read for read in reads if read]
    if reads:
        return " | ".join(reads)

    analyst = enhanced().markdown_section(enhanced().markdown_section(body, "Rolling trend analysis"), "Analyst read")
    if analyst and re.search(r"\bBTC\b|\bBitcoin\b|\bETH\b|\bEthereum\b", analyst, re.IGNORECASE):
        return first_sentence(enhanced().first_text_line(analyst), limit=260)

    return FALLBACK


def extract_leading_assets(metadata: dict[str, Any], body: str) -> str:
    from_metadata = metadata_field(metadata, "leading_assets", "strongest_movers", "movers", "asset_leadership")
    if from_metadata:
        return from_metadata

    leaders = enhanced().extract_leaders(body)
    return leaders if leaders and "open latest report" not in leaders.lower() else FALLBACK


def extract_main_risk(metadata: dict[str, Any], body: str) -> str:
    from_metadata = metadata_field(metadata, "main_risk", "risk", "key_risk", "near_term_risk")
    if from_metadata:
        return first_sentence(from_metadata, limit=240)

    risk_block_match = re.search(
        r"Main risks? over the next few hours:\s*(?P<items>(?:\n\s*[-*+]\s+.+)+)",
        body,
        re.IGNORECASE,
    )
    if risk_block_match:
        for line in risk_block_match.group("items").splitlines():
            risk = enhanced().clean_line(line)
            if risk:
                return first_sentence(risk, limit=240)

    risk = enhanced().extract_main_risk(body)
    if risk and "open latest report" not in risk.lower():
        return first_sentence(risk, limit=240)

    return FALLBACK


def extract_trend_confidence(metadata: dict[str, Any], body: str) -> str:
    from_metadata = metadata_field(metadata, "trend_confidence", "confidence")
    if from_metadata:
        return first_sentence(from_metadata, limit=160)

    confidence = enhanced().extract_trend_confidence(body)
    return confidence if confidence and confidence != "Not specified" else FALLBACK


def extract_data_quality(metadata: dict[str, Any], body: str) -> str:
    status = metadata_field(metadata, "live_data_status", "data_quality", "data_status")
    extracted = enhanced().extract_data_quality(body, metadata)
    if status and extracted and status.lower() not in extracted.lower():
        return f"{status}; {first_sentence(extracted, limit=220)}"
    if status:
        return status
    return first_sentence(extracted, limit=240) if extracted else FALLBACK


def brief_values(report: Any) -> dict[str, str]:
    raw = report.source_path.read_text(encoding="utf-8")
    metadata, body = base().split_front_matter(raw)
    body = base().strip_chatgpt_citations(body)

    return {
        "Market regime": extract_market_regime(metadata, body),
        "BTC / ETH": extract_btc_eth_read(metadata, body),
        "Leading assets": extract_leading_assets(metadata, body),
        "Main risk": extract_main_risk(metadata, body),
        "Trend confidence": extract_trend_confidence(metadata, body),
        "Data quality": extract_data_quality(metadata, body),
    }


def brief_panel(report: Any) -> str:
    rows = []
    for label, value in brief_values(report).items():
        safe_value = value or FALLBACK
        rows.append(
            f"""
              <article class="brief-glance-card">
                <span>{escape(label)}</span>
                <strong>{escape(safe_value)}</strong>
              </article>"""
        )

    return f"""
      <section class="brief-glance-panel" aria-label="Brief at a glance">
        <div class="brief-glance-header">
          <div>
            <div class="eyebrow">Extracted summary</div>
            <h2>Brief at a glance</h2>
            <p>Extracted from the archived AI-generated report. Missing fields are not inferred.</p>
          </div>
          <a class="text-link" href="#full-report-body">Jump to full report body →</a>
        </div>
        <div class="brief-glance-grid">
          {''.join(rows)}
        </div>
      </section>
    """


def add_panel_to_page(html_path: Path, report: Any) -> None:
    if not html_path.exists():
        return
    html = html_path.read_text(encoding="utf-8")
    if "brief-glance-panel" in html:
        return

    html = REPORT_CONTENT_RE.sub('<section class="content report-content" id="full-report-body">', html, count=1)
    panel = brief_panel(report)

    if REPORT_WARNING_RE.search(html):
        html = REPORT_WARNING_RE.sub(lambda match: f"{match.group(1)}{panel}\n", html, count=1)
    else:
        html = html.replace('      <section class="headline">', f"{panel}\n      <section class=\"headline\">", 1)

    html_path.write_text(html, encoding="utf-8")


def add_brief_panels() -> None:
    reports = base().collect_reports()
    for report in reports:
        add_panel_to_page(report.output_path, report)

    if reports:
        add_panel_to_page(base().OUT / "latest.html", reports[0])


def source_category(raw_type: str) -> str:
    key = re.sub(r"[^a-z0-9]+", "_", raw_type.lower()).strip("_")
    return SOURCE_CATEGORY_LABELS.get(key, "Other")


def structured_sources(metadata: dict[str, Any]) -> list[dict[str, Any]]:
    raw_sources = metadata.get("sources")
    if not isinstance(raw_sources, list):
        return []

    sources: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for item in raw_sources:
        if isinstance(item, str):
            name = enhanced().clean_line(item)
            raw_type = "other"
            url = ""
            used_for: list[str] = []
        elif isinstance(item, dict):
            name = as_text(item.get("name") or item.get("title") or item.get("source"))
            raw_type = as_text(item.get("type") or item.get("category") or "other") or "other"
            url = as_text(item.get("url") or item.get("href"))
            used_for_value = item.get("used_for") or item.get("uses") or item.get("purpose") or []
            if isinstance(used_for_value, list):
                used_for = [as_text(value) for value in used_for_value if as_text(value)]
            else:
                used_for_text = as_text(used_for_value)
                used_for = [used_for_text] if used_for_text else []
        else:
            continue

        if not name:
            continue

        key = (name.lower(), url.lower())
        if key in seen:
            continue
        seen.add(key)
        sources.append(
            {
                "name": name,
                "type": raw_type,
                "category": source_category(raw_type),
                "url": url,
                "used_for": used_for,
            }
        )
    return sources


def structured_sources_for_report(report: Any) -> list[dict[str, Any]]:
    raw = report.source_path.read_text(encoding="utf-8")
    metadata, _body = base().split_front_matter(raw)
    return structured_sources(metadata)


def source_card(source: dict[str, Any]) -> str:
    url = as_text(source.get("url"))
    used_for = source.get("used_for") if isinstance(source.get("used_for"), list) else []
    used_for_html = ""
    if used_for:
        used_for_html = (
            '<div class="structured-source-uses"><span>Used for</span><ul>'
            + "".join(f"<li>{escape(as_text(item))}</li>" for item in used_for if as_text(item))
            + "</ul></div>"
        )

    url_html = (
        f'<a class="structured-source-url" href="{escape(url)}">Open source</a>'
        if url
        else '<span class="structured-source-url missing">Source named; URL unavailable</span>'
    )

    return f"""
            <article class="structured-source-card">
              <div class="structured-source-card-header">
                <span>{escape(as_text(source.get('category')) or 'Other')}</span>
                <strong>{escape(as_text(source.get('name')))}</strong>
              </div>
              {url_html}
              {used_for_html}
            </article>"""


def structured_source_panel(sources: list[dict[str, Any]]) -> str:
    grouped: dict[str, list[dict[str, Any]]] = {label: [] for label in SOURCE_CATEGORY_ORDER}
    for source in sources:
        grouped.setdefault(as_text(source.get("category")) or "Other", []).append(source)

    groups_html: list[str] = []
    for category in SOURCE_CATEGORY_ORDER:
        category_sources = grouped.get(category) or []
        if not category_sources:
            continue
        cards = "".join(source_card(source) for source in category_sources)
        groups_html.append(
            f"""
          <section class="structured-source-group">
            <h3>{escape(category)}</h3>
            <div class="structured-source-grid">{cards}</div>
          </section>"""
        )

    return f"""
      <section class="structured-source-panel" aria-label="Structured report sources">
        <div class="structured-source-intro">
          <div class="eyebrow">Source attribution</div>
          <h2>Structured sources</h2>
          <p>Rendered from YAML source metadata in the archived AI-generated report. Source URLs are shown only when explicitly provided.</p>
        </div>
        {''.join(groups_html)}
      </section>
    """


def replace_source_panel(html_path: Path, report: Any) -> None:
    if not html_path.exists():
        return
    sources = structured_sources_for_report(report)
    if not sources:
        return

    html = html_path.read_text(encoding="utf-8")
    if "structured-source-panel" in html:
        return

    panel = structured_source_panel(sources)
    html = SOURCE_PANEL_RE.sub(f"\n{panel}\n", html, count=1)
    html_path.write_text(html, encoding="utf-8")


def add_structured_source_panels() -> None:
    reports = base().collect_reports()
    for report in reports:
        replace_source_panel(report.output_path, report)

    if reports:
        replace_source_panel(base().OUT / "latest.html", reports[0])


def update_search_index_with_structured_sources() -> None:
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
        report = reports_by_path.get(as_text(item.get("path")))
        if not report:
            continue
        sources = structured_sources_for_report(report)
        if not sources:
            continue
        item["structured_source_names"] = [source["name"] for source in sources]
        item["structured_sources"] = sources

    index_path.write_text(json.dumps(index, indent=2), encoding="utf-8")


def build() -> None:
    site.build()
    copy_asset(BRIEF_GLANCE_STYLE_NAME)
    copy_asset(STRUCTURED_SOURCE_STYLE_NAME)
    add_stylesheet_links()
    add_brief_panels()
    add_structured_source_panels()
    update_search_index_with_structured_sources()
    print("Added Brief at a glance panels and structured source cards to generated report pages.")


if __name__ == "__main__":
    build()
