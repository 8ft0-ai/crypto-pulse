"""Schema-aware rendering for the homepage latest-report summary.

The report archive contains multiple report formats. This adapter keeps the
homepage useful without promoting product-boundary boilerplate or rendering
retired fields as repeated placeholders.
"""

from __future__ import annotations

import re
from html import escape
from typing import Any


BOILERPLATE_PATTERNS = (
    r"\bnot financial advice\b",
    r"\bfor demonstration purposes only\b",
    r"\bdemo(?:nstration)? content\b",
    r"\bdeterministic demonstration content\b",
    r"\bdoes not constitute (?:financial|investment) advice\b",
    r"\bno investment advice\b",
    r"\bnot live verified market data\b",
    r"\bshould not be used for (?:trading|investing|risk decisions)\b",
    r"\bcall to buy, sell, or hold\b",
)

PLACEHOLDER_PATTERNS = (
    r"^not specified\.?$",
    r"^not explicitly extracted\b",
    r"^market regime was not explicitly extracted\b",
    r"^open (?:the )?latest report for\b",
    r"^detailed data-quality status was not specified\b",
)

SUMMARY_SECTIONS = (
    "Executive summary",
    "Market summary",
    "Market overview",
    "Summary",
    "Key findings",
)


def is_boilerplate(value: str) -> bool:
    """Return whether text is product-boundary/disclaimer boilerplate."""
    normalised = re.sub(r"\s+", " ", value).strip().lower()
    return bool(normalised) and any(re.search(pattern, normalised) for pattern in BOILERPLATE_PATTERNS)


def is_meaningful(value: str) -> bool:
    """Return whether a value is suitable for a primary homepage summary."""
    normalised = re.sub(r"\s+", " ", value).strip()
    if not normalised or is_boilerplate(normalised):
        return False
    lowered = normalised.lower()
    return not any(re.search(pattern, lowered) for pattern in PLACEHOLDER_PATTERNS)


def first_meaningful(values: list[str]) -> str:
    for value in values:
        if is_meaningful(value):
            return value.strip()
    return ""


def safe_headline(body: str, extracted: str) -> str:
    """Return a non-boilerplate headline for shared homepage/archive surfaces."""
    if is_meaningful(extracted):
        return extracted.strip()

    candidates: list[str] = []
    for raw_line in body.splitlines():
        line = raw_line.strip().strip("* ")
        if not line or line.startswith(("#", "|", "---")):
            continue
        if re.match(r"^(source|generated|timestamp|report id)\s*:", line, re.IGNORECASE):
            continue
        candidates.append(line)

    return first_meaningful(candidates) or "Deterministic source-snapshot evidence report."


def _section_summary(body: str, search: Any) -> str:
    candidates = [
        search.first_text_line(search.markdown_section(body, title))
        for title in SUMMARY_SECTIONS
    ]
    return first_meaningful(candidates)


def _card(label: str, value: str, *, wide: bool = False) -> str:
    css_class = "market-read-card market-read-card-wide" if wide else "market-read-card"
    return (
        f'<article class="{css_class}">'
        f"<span>{escape(label)}</span>"
        f"<strong>{escape(value)}</strong>"
        "</article>"
    )


def latest_market_read_panel(report: Any, search: Any, base: Any) -> str:
    """Render the latest summary across legacy and deterministic report schemas."""
    raw = report.source_path.read_text(encoding="utf-8")
    metadata, body = base.split_front_matter(raw)
    body = base.strip_chatgpt_citations(body)

    rolling = search.markdown_section(body, "Rolling trend analysis")
    emerging = search.first_text_line(search.markdown_section(rolling, "Emerging trend")) if rolling else ""
    analyst_read = search.first_text_line(search.markdown_section(rolling, "Analyst read")) if rolling else ""

    primary_summary = first_meaningful([
        emerging,
        _section_summary(body, search),
        str(getattr(report, "headline", "") or ""),
    ])
    analyst_read = first_meaningful([analyst_read])

    optional_fields = [
        ("Trend confidence", search.extract_trend_confidence(body), False),
        ("Leading assets", search.extract_leaders(body), False),
        ("Main risk", search.extract_main_risk(body), False),
    ]
    visible_optional = [field for field in optional_fields if is_meaningful(field[1])]
    omitted_count = len(optional_fields) - len(visible_optional)

    data_quality = search.extract_data_quality(body, metadata)
    if not is_meaningful(data_quality):
        live_status = str(metadata.get("live_data_status") or "").strip()
        data_quality = f"Live data status: {live_status}" if live_status and is_meaningful(live_status) else "See the source report for provenance and data-quality detail."

    cards: list[str] = []
    if primary_summary:
        cards.append(_card("Fact from latest report", primary_summary, wide=True))
    cards.extend(_card(label, value, wide=wide) for label, value, wide in visible_optional)
    if analyst_read:
        cards.append(_card("Analyst interpretation", analyst_read, wide=True))
    cards.append(_card("Data quality and provenance", data_quality, wide=True))

    format_note = ""
    if omitted_count:
        format_note = (
            '<p class="muted report-format-note">'
            "This report format does not publish every legacy interpretation field; unavailable fields are omitted."
            "</p>"
        )

    return f"""
        <section class="latest-market-read" aria-label="Latest market read">
          <div class="latest-market-read-header">
            <div>
              <div class="eyebrow">Latest report evidence</div>
              <h2>Schema-aware report summary</h2>
              <p class="muted">Extracted from the latest archived AI-generated demo report, timestamped {escape(report.timestamp)}. Review the source report for its generation boundary and full audit trail.</p>
            </div>
            <a class="button" href="{escape(report.url)}">Open source report</a>
          </div>
          <div class="market-read-grid">{''.join(cards)}</div>
          {format_note}
        </section>
    """