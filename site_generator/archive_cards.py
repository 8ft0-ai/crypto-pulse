"""Stable reader-first archive card rendering for retained reports."""

from __future__ import annotations

import re
from collections import defaultdict
from html import escape
from pathlib import Path
from typing import Any

from site_generator import archive_reader

STYLE_NAME = "cryptopulse-archive-cards.css"


def clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip(" .")


def time_label(report: Any) -> str:
    parts = [clean(report.year), clean(report.month), clean(report.day)]
    date = "-".join(part for part in parts if part)
    clock = " ".join(
        part for part in (clean(report.time_label), clean(report.tz)) if part
    )
    if not clock:
        match = re.match(
            r"(?P<hhmm>\d{4})_(?P<tz>[A-Z]{2,5})",
            Path(report.source_path).stem,
        )
        if match:
            hhmm = match.group("hhmm")
            clock = f"{hhmm[:2]}:{hhmm[2:]} {match.group('tz')}"
    return " · ".join(part for part in (date, clock) if part) or clean(report.timestamp)


def display_headline(report: Any) -> str:
    headline = clean(getattr(report, "headline", ""))
    lowered = headline.lower()
    if (
        not headline
        or "not financial advice" in lowered
        or "deterministic demonstration content" in lowered
    ):
        return ""
    return headline


def taxonomy_html(report: Any) -> str:
    taxonomy = archive_reader.report_taxonomy(report)
    generation = taxonomy["generation"]
    evidence = taxonomy["evidence_state"]
    chips = [
        f'<span class="archive-taxonomy-generation">{escape(generation["label"])}</span>'
    ]
    if evidence:
        chips.append(
            f'<span class="archive-taxonomy-evidence">{escape(evidence["label"])}</span>'
        )
    return (
        '<div class="archive-taxonomy" aria-label="Report evidence classification">'
        + "".join(chips)
        + "</div>"
    )


def card_data_attributes(report: Any) -> str:
    attributes = archive_reader.archive_card_attributes(report)
    return (
        f'data-archive-month="{escape(attributes["month"], quote=True)}" '
        f'data-archive-generation="{escape(attributes["generation"], quote=True)}" '
        f'data-archive-evidence-state="{escape(attributes["evidence_state"], quote=True)}"'
    )


def recent_report_cards(reports: list[Any], base: Any) -> str:
    if not reports:
        return "<p>No reports found.</p>"
    cards = []
    for report in reports[:12]:
        headline = display_headline(report)
        headline_html = f"<p>{escape(headline)}</p>" if headline else ""
        cards.append(
            f"""
          <article class="report-card archive-preview-card" {card_data_attributes(report)}>
            <div class="eyebrow">{escape(time_label(report))}</div>
            <h3><a href="{escape(report.url)}">{escape(report.title)}</a></h3>
            {headline_html}
            {taxonomy_html(report)}
            <a class="text-link" href="{escape(report.url)}">Open report →</a>
          </article>"""
        )
    return "\n".join(cards)


def grouped_archive(reports: list[Any], base: Any) -> str:
    if not reports:
        return "<p>No reports found.</p>"

    # Dict insertion order deliberately follows the already-canonical report list.
    # Do not create a second chronology by re-sorting year/month/day keys here.
    grouped: dict[str, dict[str, dict[str, list[Any]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(list))
    )
    for report in reports:
        grouped[report.year or "Unknown year"][report.month or "Unknown month"][
            report.day or "Unknown day"
        ].append(report)

    parts: list[str] = []
    for year, months in grouped.items():
        parts.append(
            f'<section class="archive-year" data-year="{escape(year)}">'
            f"<h2>{escape(year)}</h2>"
        )
        for month, days in months.items():
            month_label = base.month_name(month)
            anchor = f"{year}-{month}"
            count = sum(len(items) for items in days.values())
            parts.append(
                f'<section class="archive-month" id="{escape(anchor)}" '
                f'data-year="{escape(year)}" data-month="{escape(month)}">'
                f"<h3>{escape(month_label)} <span>{count} reports</span></h3>"
            )
            for day, day_reports in days.items():
                day_label = f"{int(day)} {month_label}" if day.isdigit() else day
                parts.append(
                    f'<section class="archive-day" data-day="{escape(day)}">'
                    f"<h4>{escape(day_label)}</h4>"
                    '<div class="archive-card-grid">'
                )
                for report in day_reports:
                    headline = display_headline(report)
                    headline_html = f"<p>{escape(headline)}</p>" if headline else ""
                    parts.append(
                        f"""
                      <article class="archive-card"
                        data-year="{escape(report.year)}"
                        data-month="{escape(report.month)}"
                        data-day="{escape(report.day)}"
                        {card_data_attributes(report)}>
                        <div class="eyebrow">{escape(time_label(report))}</div>
                        <h5><a href="../{escape(report.url)}">{escape(report.title)}</a></h5>
                        {headline_html}
                        {taxonomy_html(report)}
                        <a class="text-link" href="../{escape(report.url)}">Open report →</a>
                      </article>"""
                    )
                parts.append("</div></section>")
            parts.append(
                '<p class="return-top"><a href="#top">Return to top ↑</a></p></section>'
            )
        parts.append("</section>")
    return "\n".join(parts)


def configure(base: Any) -> None:
    """Install reader-safe card renderers before the base site is generated."""
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
