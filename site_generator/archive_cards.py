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



# A typed article is the only source for *new* editorial copy. Untyped
# publications retain their original titles without inferred summaries.
EDITORIAL_STATES = {
    "finding": "Source-bounded finding",
    "factual_update": "Factual update — no qualifying finding",
    "inconclusive": "Inconclusive evidence",
}


def validated_projection(report: Any, base: Any) -> dict[str, Any] | None:
    metadata = getattr(report, "metadata", None)
    if not isinstance(metadata, dict) or "editorial_article" not in metadata:
        return None
    validator = getattr(base, "validated_editorial_article", None)
    if not callable(validator):
        raise ValueError("typed archive entry requires the canonical article validator")
    article = validator(report)
    if article is None:
        raise ValueError("typed archive entry failed canonical article validation")
    return article


def editorial_entry(report: Any, base: Any) -> dict[str, str]:
    article = validated_projection(report, base)
    if article is not None:
        state = article["article_state"]
        caveats = article["caveats"]
        return {
            "title": article["headline"],
            "summary": article["summary"],
            "status": EDITORIAL_STATES[state],
            "qualification": caveats[0] if caveats else (
                "Material source-quality limitation — inspect this report."
                if report.metadata.get("quality_status") == "valid-degraded" else ""
            ),
        }
    generation = archive_reader.report_generation(report)["key"]
    status = (
        "Original deterministic publication — no retrospective editorial assessment"
        if generation == "deterministic"
        else "Original AI-generated historical publication — not independently re-assessed"
    )
    return {
        "title": str(getattr(report, "title", "") or "Archived report"),
        "summary": "",  # Legacy Markdown is not a source for newly composed research copy.
        "status": status,
        "qualification": (
            "Degraded / partial source evidence; inspect the original report."
            if getattr(report, "metadata", {}).get("quality_status") == "valid-degraded"
            else ""
        ),
    }


def entry_copy(entry: dict[str, str]) -> str:
    summary = (
        f'<p class="archive-entry-summary">{escape(entry["summary"])}</p>'
        if entry["summary"] else ""
    )
    qualification = (
        f'<p class="archive-entry-qualification">{escape(entry["qualification"])}</p>'
        if entry["qualification"] else ""
    )
    return (
        f'<p class="archive-entry-status">{escape(entry["status"])}</p>'
        + summary + qualification
    )


def original_observation_excerpt(report: Any) -> str:
    """Return original, verbatim deterministic prose; never promote it to a finding."""
    metadata = getattr(report, "metadata", {})
    if (metadata.get("schema_version") != "deterministic-crypto-report/v1"
            or metadata.get("quality_status") != "valid-ok"
            or not metadata.get("source_snapshot")):
        return ""
    raw = report.source_path.read_text(encoding="utf-8")
    section = re.search(
        r"(?ms)^## Evidence-backed findings\s*\n(.*?)(?=^## |\Z)", raw
    )
    if not section:
        return ""
    # Only quote the original market-interval observation, not the preceding
    # venue/source-quality check. If the historical report offers no bounded
    # interval observation, present a neutral archive overview instead.
    interval = re.search(
        r"(?m)^\d+\.\s+(\*\*Archived interval comparison:\*\*[^\n]+)$",
        section.group(1),
    )
    if not interval or "This is a two-point observation, not evidence of a sustained trend." not in interval.group(1):
        return ""
    excerpt = re.sub(r"\*\*([^*]+)\*\*", lambda m: m.group(1), interval.group(1))
    # Flatten Markdown source-link markup for the plain-text teaser; the
    # exact original citations remain accessible through Supporting evidence.
    return re.sub(r"\[([^\]\n]+)\]\(https://github\.com/8ft0-ai/crypto-pulse/blob/[0-9a-f]{40}/data/crypto/hourly/[^)]+\.json\)", r"\1", excerpt).strip()


def homepage_lead(reports: list[Any], base: Any) -> str:
    """Lead only with a validated typed result; otherwise label an archival excerpt."""
    if not reports:
        return (
            '<section class="homepage-editorial-lead" aria-labelledby="homepage-lead-heading">'
            '<h2 id="homepage-lead-heading">No archived reports yet</h2>'
            '<p>No market observation is available for editorial presentation.</p></section>'
        )
    typed = [(report, validated_projection(report, base)) for report in reports]
    selected = next(
        ((report, article) for report, article in typed
         if article and article["article_state"] == "finding"), None
    )
    if selected is None:
        selected = next(
            ((report, article) for report, article in typed
             if article and article["article_state"] == "factual_update"), None
        )
    if selected is None:
        selected = next(
            ((report, article) for report, article in typed if article), None
        )
    report, article = selected if selected else (reports[0], None)
    entry = editorial_entry(report, base)
    classification = (
        EDITORIAL_STATES[article["article_state"]]
        if article else "Original archival observation — not newly assessed"
    )
    if article:
        synopsis = f'<p class="homepage-lead-synopsis">{escape(article["summary"])}</p>'
        uncertainty = next(
            (claim["uncertainty"] for claim in article["claims"]
             if claim["category"] == "market"), ""
        ) or (article["caveats"][0] if article["caveats"] else article.get("reason", ""))
    else:
        excerpt = original_observation_excerpt(report)
        synopsis = (
            '<p class="homepage-lead-synopsis"><strong>From the original report:</strong> '
            f'{escape(excerpt)}</p>'
            if excerpt else
            '<p class="homepage-lead-synopsis">Retained under its original publication '
            'title, without an unsupported retrospective research summary.</p>'
        )
        uncertainty = (
            "This is an original point-in-time archival observation, not a new "
            "validated editorial finding. Review the archived source and limitations."
        )
    if entry["qualification"]:
        uncertainty += " " + entry["qualification"]
    if selected:
        # Finding-first is deliberate. The selected finding can be older than
        # a factual update, so never imply it is the newest typed publication.
        if article["article_state"] == "finding":
            context = ("Most recent validated typed finding, prioritised over factual "
                       "updates and inconclusive reports. Newer retained reports may exist.")
        elif article["article_state"] == "factual_update":
            context = ("No validated typed finding is available. This is the most recent "
                       "validated typed factual update; newer retained reports may exist.")
        else:
            context = ("No validated typed finding or factual update is available. "
                       "This is the most recent inconclusive typed report; newer retained "
                       "reports may exist.")
    else:
        context = "No retained report has a qualifying typed editorial finding or update."
    return f"""
<section class="homepage-editorial-lead" aria-labelledby="homepage-lead-heading">
  <p class="editorial-kicker">{escape(classification)} · AI-generated demo/archive</p>
  <h2 id="homepage-lead-heading"><a href="{escape(report.url, quote=True)}">{escape(entry["title"])}</a></h2>
  <p class="homepage-lead-time"><strong>Report dated:</strong> {escape(report.timestamp)}.
    <strong>Freshness:</strong> static archive, not live or continuously updated.</p>
  {synopsis}
  <p class="homepage-lead-uncertainty"><strong>Uncertainty and limits:</strong> {escape(uncertainty)}</p>
  <p class="homepage-lead-context">{escape(context)}</p>
  <nav class="homepage-lead-actions" aria-label="Lead article and supporting resources">
    <a href="{escape(report.url, quote=True)}">Read archived article</a>
    <a href="{escape(report.url, quote=True)}#supporting-evidence">Supporting evidence</a>
    <a href="{escape(report.url, quote=True)}#technical-record">Original technical record</a>
    <a href="methodology.html">Methodology and limitations</a>
  </nav>
</section>
"""



def recent_report_cards(reports: list[Any], base: Any) -> str:
    if not reports:
        return "<p>No reports found.</p>"
    cards = []
    for report in reports[:12]:
        entry = editorial_entry(report, base)
        cards.append(
            f"""
          <article class="report-card archive-preview-card" {card_data_attributes(report)}>
            <div class="eyebrow">{escape(time_label(report))}</div>
            <h3><a href="{escape(report.url)}">{escape(entry["title"])}</a></h3>
            {entry_copy(entry)}
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
                    entry = editorial_entry(report, base)
                    parts.append(
                        f"""
                      <article class="archive-card"
                        data-year="{escape(report.year)}"
                        data-month="{escape(report.month)}"
                        data-day="{escape(report.day)}"
                        {card_data_attributes(report)}>
                        <div class="eyebrow">{escape(time_label(report))}</div>
                        <h5><a href="../{escape(report.url)}">{escape(entry["title"])}</a></h5>
                        {entry_copy(entry)}
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
