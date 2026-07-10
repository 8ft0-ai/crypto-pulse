"""Stable archive card rendering for hourly report scanning."""

from __future__ import annotations

import re
from collections import defaultdict
from html import escape
from pathlib import Path
from typing import Any

STYLE_NAME = "cryptopulse-archive-cards.css"
MISSING = {"", "not specified", "not specified in archived report", "n/a", "unavailable", "—", "-"}


def clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip(" .")


def meaningful(value: object) -> bool:
    text = clean(value).lower()
    return bool(text) and text not in MISSING and "not specified" not in text


def table_cells(line: str) -> list[str]:
    return [clean(cell) for cell in line.strip().strip("|").split("|")]


def asset_changes(body: str, symbol: str) -> dict[str, str]:
    aliases = {symbol, "BITCOIN" if symbol == "BTC" else "ETHEREUM" if symbol == "ETH" else symbol}
    for line in body.splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = table_cells(line)
        if len(cells) < 4 or all(re.fullmatch(r":?-{3,}:?", cell.replace(" ", "")) for cell in cells):
            continue
        asset_index = next((i for i, cell in enumerate(cells[:3]) if aliases & set(re.sub(r"[^A-Z0-9]+", " ", cell.upper()).split())), None)
        if asset_index is None:
            continue
        one_hour_index, day_index = ((2, 3) if asset_index == 0 else (asset_index + 2, asset_index + 3))
        result: dict[str, str] = {}
        if one_hour_index < len(cells) and re.search(r"[-+]?\d", cells[one_hour_index]):
            result["1h"] = cells[one_hour_index]
        if day_index < len(cells) and re.search(r"[-+]?\d", cells[day_index]):
            result["24h"] = cells[day_index]
        if result:
            return result
    return {}


def data_quality(metadata: dict[str, Any], body: str) -> str:
    for key in ("live_data_status", "data_quality", "data_status"):
        value = clean(metadata.get(key))
        if meaningful(value):
            return value
    match = re.search(r"Data quality:\s*(?P<items>(?:\n\s*-\s+.+)+)", body, re.IGNORECASE)
    if match:
        values = [clean(line.lstrip("-* ")) for line in match.group("items").splitlines()]
        values = [value for value in values if meaningful(value)]
        if values:
            return values[0]
    return ""


def report_metrics(report: Any, base: Any) -> list[tuple[str, str, str]]:
    raw = report.source_path.read_text(encoding="utf-8")
    metadata, body = base.split_front_matter(raw)
    body = base.strip_chatgpt_citations(body)
    metrics: list[tuple[str, str, str]] = []
    for symbol in ("BTC", "ETH"):
        changes = asset_changes(body, symbol)
        value = changes.get("24h") or changes.get("1h")
        period = "24h" if changes.get("24h") else "1h"
        if value and meaningful(value):
            direction = "up" if value.lstrip().startswith("+") else "down" if value.lstrip().startswith("-") else "flat"
            metrics.append((f"{symbol} {period}", value, direction))
    quality = data_quality(metadata, body)
    if meaningful(quality):
        metrics.append(("Data", quality, "status"))
    return metrics


def metric_html(metrics: list[tuple[str, str, str]]) -> str:
    if not metrics:
        return ""
    chips = "".join(
        f'<span class="archive-metric archive-metric-{escape(kind)}"><span>{escape(label)}</span><strong>{escape(value)}</strong></span>'
        for label, value, kind in metrics
    )
    return f'<div class="archive-metrics" aria-label="Report metrics">{chips}</div>'


def time_label(report: Any) -> str:
    parts = [clean(report.year), clean(report.month), clean(report.day)]
    date = "-".join(part for part in parts if part)
    clock = " ".join(part for part in (clean(report.time_label), clean(report.tz)) if part)
    if not clock:
        match = re.match(r"(?P<hhmm>\d{4})_(?P<tz>[A-Z]{2,5})", Path(report.source_path).stem)
        if match:
            hhmm = match.group("hhmm")
            clock = f"{hhmm[:2]}:{hhmm[2:]} {match.group('tz')}"
    return " · ".join(part for part in (date, clock) if part) or clean(report.timestamp)


def display_headline(report: Any) -> str:
    headline = clean(getattr(report, "headline", ""))
    lowered = headline.lower()
    if not headline or "not financial advice" in lowered or "deterministic demonstration content" in lowered:
        return ""
    return headline


def recent_report_cards(reports: list[Any], base: Any) -> str:
    if not reports:
        return "<p>No reports found.</p>"
    cards = []
    for report in reports[:12]:
        headline = display_headline(report)
        headline_html = f'<p>{escape(headline)}</p>' if headline else ""
        cards.append(f'''\n          <article class="report-card archive-preview-card">\n            <div class="eyebrow">{escape(time_label(report))}</div>\n            <h3><a href="{escape(report.url)}">{escape(report.title)}</a></h3>\n            {headline_html}\n            {metric_html(report_metrics(report, base))}\n            <a class="text-link" href="{escape(report.url)}">Open report →</a>\n          </article>''')
    return "\n".join(cards)


def grouped_archive(reports: list[Any], base: Any) -> str:
    if not reports:
        return "<p>No reports found.</p>"
    grouped: dict[str, dict[str, dict[str, list[Any]]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for report in reports:
        grouped[report.year or "Unknown year"][report.month or "Unknown month"][report.day or "Unknown day"].append(report)
    parts: list[str] = []
    for year in sorted(grouped, reverse=True):
        parts.append(f'<section class="archive-year" data-year="{escape(year)}"><h2>{escape(year)}</h2>')
        for month in sorted(grouped[year], reverse=True):
            month_label = base.month_name(month)
            anchor = f"{year}-{month}"
            count = sum(len(items) for items in grouped[year][month].values())
            parts.append(f'<section class="archive-month" id="{escape(anchor)}" data-year="{escape(year)}" data-month="{escape(month)}"><h3>{escape(month_label)} <span>{count} reports</span></h3>')
            for day in sorted(grouped[year][month], reverse=True):
                day_reports = grouped[year][month][day]
                day_label = f"{int(day)} {month_label}" if day.isdigit() else day
                parts.append(f'<section class="archive-day" data-day="{escape(day)}"><h4>{escape(day_label)}</h4><div class="archive-card-grid">')
                for report in day_reports:
                    keywords = " ".join([report.title, report.headline, report.timestamp, " ".join(report.source_items)]).lower()
                    headline = display_headline(report)
                    headline_html = f'<p>{escape(headline)}</p>' if headline else ""
                    parts.append(f'''\n                      <article class="archive-card" data-year="{escape(report.year)}" data-month="{escape(report.month)}" data-day="{escape(report.day)}" data-keywords="{escape(keywords)}">\n                        <div class="eyebrow">{escape(time_label(report))}</div>\n                        <h5><a href="../{escape(report.url)}">{escape(report.title)}</a></h5>\n                        {headline_html}\n                        {metric_html(report_metrics(report, base))}\n                        <a class="text-link" href="../{escape(report.url)}">Open report →</a>\n                      </article>''')
                parts.append("</div></section>")
            parts.append('<p class="return-top"><a href="#top">Return to top ↑</a></p></section>')
        parts.append("</section>")
    return "\n".join(parts)


def configure(base: Any) -> None:
    """Install stable card renderers before the base site is generated."""
    base.recent_report_cards = lambda reports: recent_report_cards(reports, base)
    base.grouped_archive = lambda reports: grouped_archive(reports, base)


def copy_style(base: Any) -> None:
    source = base.SITE_SRC / "assets" / STYLE_NAME
    destination = base.OUT / "assets" / STYLE_NAME
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    for html_file in (base.OUT / "index.html", base.OUT / "archive" / "index.html"):
        if not html_file.exists():
            continue
        html = html_file.read_text(encoding="utf-8")
        prefix = "../" if html_file.parent.name == "archive" else ""
        link = f'<link rel="stylesheet" href="{prefix}assets/{STYLE_NAME}">'
        if STYLE_NAME not in html:
            html = html.replace("</head>", f"  {link}\n</head>", 1)
            html_file.write_text(html, encoding="utf-8")