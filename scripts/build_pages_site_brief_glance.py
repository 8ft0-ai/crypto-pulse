#!/usr/bin/env python3
"""Build CryptoPulse Pages with brief-at-a-glance report panels."""

from __future__ import annotations

import re
import shutil
from html import escape
from pathlib import Path
from typing import Any

import build_pages_site_mobile_ux as site


BRIEF_GLANCE_STYLE_NAME = "cryptopulse-brief-glance.css"
REPORT_CONTENT_RE = re.compile(r'<section class="content report-content">')
REPORT_WARNING_RE = re.compile(
    r'(      <section class="report-warning compact-warning">.*?</section>\n)',
    re.DOTALL,
)
SENTENCE_END_RE = re.compile(r"(?<=[.!?])\s+")
FALLBACK = "Not specified in archived report."


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


def add_brief_stylesheet_links() -> None:
    for html_file in base().OUT.glob("**/*.html"):
        html = html_file.read_text(encoding="utf-8")
        if BRIEF_GLANCE_STYLE_NAME in html:
            continue
        prefix = relative_prefix(html_file)
        html = html.replace(
            "</head>",
            f'  <link rel="stylesheet" href="{prefix}assets/{BRIEF_GLANCE_STYLE_NAME}">\n</head>',
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


def build() -> None:
    site.build()
    copy_asset(BRIEF_GLANCE_STYLE_NAME)
    add_brief_stylesheet_links()
    add_brief_panels()
    print("Added Brief at a glance panels to report pages and latest.html.")


if __name__ == "__main__":
    build()
