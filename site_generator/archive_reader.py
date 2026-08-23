"""Reader-first Archive model and navigation integration for Phase 16."""

from __future__ import annotations

import re
import shutil
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from typing import Any

STYLE_NAME = "cryptopulse-archive-reader.css"
SCRIPT_NAME = "cryptopulse-archive-reader.js"
DETERMINISTIC_SCHEMA = "deterministic-crypto-report/v1"

ARCHIVE_STATS_RE = re.compile(
    r'<section class="archive-stats-grid" aria-label="Archive statistics">.*?</section>',
    re.DOTALL,
)
DEVELOPER_OUTPUTS_RE = re.compile(
    r'\s*<div class="developer-output-links" aria-label="Developer outputs">.*?</div>\s*',
    re.DOTALL,
)
SITE_NAV_RE = re.compile(
    r'\s*<nav class="site-nav" aria-label="Primary navigation">.*?</nav>',
    re.DOTALL,
)
ARCHIVE_GROUPS_MARKER = '<section class="archive-groups">'
ARCHIVE_HEADING = (
    '<div class="section-heading"><div><div class="eyebrow">Archive browser</div>'
    '<h2>Browse generated demo reports</h2></div>'
    '<a class="text-link" href="../search-index.json">Open search index JSON →</a></div>'
)


class ArchiveReaderIntegrationError(ValueError):
    """Raised when the Phase 16 Archive reader projection cannot be applied safely."""


def _metadata(report: Any) -> dict[str, Any]:
    value = getattr(report, "metadata", None)
    return value if isinstance(value, dict) else {}


def report_generation(report: Any) -> dict[str, str]:
    """Return the repository-backed generation classification for one report."""
    metadata = _metadata(report)
    chronology_kind = getattr(report, "chronology_kind", "")
    deterministic = (
        chronology_kind == "deterministic"
        or metadata.get("schema_version") == DETERMINISTIC_SCHEMA
    )
    if deterministic:
        return {"key": "deterministic", "label": "Deterministic evidence"}
    return {"key": "ai-historical", "label": "AI-generated historical report"}


def report_evidence_state(report: Any) -> dict[str, str] | None:
    """Return only evidence-state labels supported by governed report metadata."""
    generation = report_generation(report)
    if generation["key"] == "ai-historical":
        return {"key": "legacy-evidence-format", "label": "Legacy evidence format"}

    quality = _metadata(report).get("quality_status")
    if quality == "valid-ok":
        return {"key": "validated-source-evidence", "label": "Validated source evidence"}
    if quality == "valid-degraded":
        return {"key": "degraded-partial-evidence", "label": "Degraded / partial evidence"}
    return None


def report_taxonomy(report: Any) -> dict[str, Any]:
    """Keep generation mechanism and evidence quality as separate facts."""
    return {
        "generation": report_generation(report),
        "evidence_state": report_evidence_state(report),
    }


def archive_month_key(report: Any) -> str:
    year = str(getattr(report, "year", "") or "")
    month = str(getattr(report, "month", "") or "")
    if not re.fullmatch(r"\d{4}", year) or not re.fullmatch(r"\d{2}", month):
        return ""
    try:
        parsed = int(month)
    except ValueError:
        return ""
    if not 1 <= parsed <= 12:
        return ""
    return f"{year}-{month}"


def archive_card_attributes(report: Any) -> dict[str, str]:
    taxonomy = report_taxonomy(report)
    evidence = taxonomy["evidence_state"]
    return {
        "month": archive_month_key(report),
        "generation": taxonomy["generation"]["key"],
        "evidence_state": evidence["key"] if evidence else "",
    }


def _canonical_time(report: Any) -> datetime:
    value = getattr(report, "report_time_utc", None)
    if not isinstance(value, str) or not value:
        raise ArchiveReaderIntegrationError(
            "canonical report chronology is unavailable for Archive projection"
        )
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ArchiveReaderIntegrationError("canonical report time is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ArchiveReaderIntegrationError("canonical report time must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _duration_text(seconds: int) -> str:
    remaining = max(0, int(seconds))
    days, remaining = divmod(remaining, 86400)
    hours, remaining = divmod(remaining, 3600)
    minutes, seconds = divmod(remaining, 60)
    parts: list[str] = []
    if days:
        parts.append(f"{days}d")
    if hours or days:
        parts.append(f"{hours}h")
    if minutes or hours or days:
        parts.append(f"{minutes}m")
    if seconds or not parts:
        parts.append(f"{seconds}s")
    return " ".join(parts)


def _month_label(base: Any, report: Any, key: str) -> str:
    month = str(getattr(report, "month", "") or "")
    year = str(getattr(report, "year", "") or "")
    month_name = getattr(base, "month_name", None)
    if callable(month_name):
        label = str(month_name(month))
        if label:
            return f"{label} {year}".strip()
    return key


def build_archive_context(base: Any) -> dict[str, Any]:
    """Project reader facts from the existing canonical report list without re-sorting it."""
    reports = list(base.collect_reports())
    times = [_canonical_time(report) for report in reports]

    for earlier, later in zip(times, times[1:]):
        if earlier <= later:
            raise ArchiveReaderIntegrationError(
                "Archive input is not the strict reverse canonical report chronology"
            )

    months: list[dict[str, str]] = []
    seen_months: set[str] = set()
    generations: list[dict[str, str]] = []
    seen_generations: set[str] = set()
    evidence_states: list[dict[str, str]] = []
    seen_evidence: set[str] = set()

    for report in reports:
        month_key = archive_month_key(report)
        if month_key and month_key not in seen_months:
            seen_months.add(month_key)
            months.append({"key": month_key, "label": _month_label(base, report, month_key)})

        taxonomy = report_taxonomy(report)
        generation = taxonomy["generation"]
        if generation["key"] not in seen_generations:
            seen_generations.add(generation["key"])
            generations.append(generation)

        evidence = taxonomy["evidence_state"]
        if evidence and evidence["key"] not in seen_evidence:
            seen_evidence.add(evidence["key"])
            evidence_states.append(evidence)

    intervals = [
        int((newer - older).total_seconds())
        for newer, older in zip(times, times[1:])
    ]
    over_one_hour = [seconds for seconds in intervals if seconds > 3600]
    represented_dates = len({value.date() for value in times})
    calendar_days = (
        (times[0].date() - times[-1].date()).days + 1
        if times
        else 0
    )

    return {
        "reports": reports,
        "total_count": len(reports),
        "newest": str(getattr(reports[0], "timestamp", "")) if reports else "No reports yet",
        "oldest": str(getattr(reports[-1], "timestamp", "")) if reports else "No reports yet",
        "represented_utc_dates": represented_dates,
        "calendar_days": calendar_days,
        "intervals_over_one_hour": len(over_one_hour),
        "largest_interval_seconds": max(intervals, default=0),
        "months": months,
        "generations": generations,
        "evidence_states": evidence_states,
    }


def _summary(context: dict[str, Any]) -> str:
    discontinuity = (
        f"{context['intervals_over_one_hour']} retained interval(s) exceed 1 hour"
        if context["intervals_over_one_hour"]
        else "No retained interval exceeds 1 hour"
    )
    if context["largest_interval_seconds"]:
        discontinuity += (
            f"; largest retained interval "
            f"{_duration_text(context['largest_interval_seconds'])}"
        )

    cards = (
        ("Total retained reports", str(context["total_count"])),
        ("Newest retained evidence", context["newest"]),
        ("Oldest retained evidence", context["oldest"]),
        (
            "Retained UTC dates",
            f"{context['represented_utc_dates']} represented across "
            f"{context['calendar_days']} calendar day(s)",
        ),
        ("Observed discontinuity", discontinuity),
    )
    rendered = "".join(
        '<article class="archive-stat-card">'
        f'<div class="eyebrow">{escape(label)}</div>'
        f"<p>{escape(value)}</p></article>"
        for label, value in cards
    )
    return (
        '<section class="archive-stats-grid archive-reader-stats" '
        'aria-label="Archive retained coverage">'
        f"{rendered}</section>"
    )


def _safety_panel() -> str:
    return """
<section class="archive-reader-safety" aria-label="Archive demo and use limitations">
  <div class="eyebrow">Demo archive — not for trading</div>
  <p><strong>CryptoPulse is a prototype demonstration.</strong> Retained reports include deterministic repository-backed evidence and preserved AI-generated historical reports that may be inaccurate, incomplete, stale, misleading or hallucinated.</p>
  <p>Nothing in this archive is financial advice, investment research, a recommendation or a trading signal. Do not use these reports for trading, investing or risk decisions.</p>
</section>
"""


def _taxonomy_note() -> str:
    return """
<section class="archive-reader-taxonomy" aria-label="Archive evidence taxonomy">
  <div class="eyebrow">How to read the archive</div>
  <p><strong>Generation type</strong> describes how a retained report was produced. <strong>Evidence state</strong> is a separate repository-backed fact and is shown only when the retained report format supports it. Historical reports are not retroactively validated or normalised into deterministic market fields.</p>
  <p class="muted">Coverage describes only the reports retained in this repository. Missing intervals are not backfilled, interpolated or treated as continuous hourly coverage.</p>
</section>
"""


def _option(value: str, label: str) -> str:
    return f'<option value="{escape(value, quote=True)}">{escape(label)}</option>'


def render_filter_controls(context: dict[str, Any]) -> str:
    month_options = "".join(
        _option(item["key"], item["label"]) for item in context["months"]
    )
    generation_options = "".join(
        _option(item["key"], item["label"]) for item in context["generations"]
    )
    evidence_options = "".join(
        _option(item["key"], item["label"]) for item in context["evidence_states"]
    )
    return f"""
<section class="archive-reader-controls" data-archive-filter-controls hidden aria-label="Archive reader filters">
  <div>
    <div class="eyebrow">Reader filters</div>
    <h2>Filter retained reports</h2>
    <p>Filters use generated repository-backed attributes only. They do not inspect report prose or make network requests.</p>
  </div>
  <div class="archive-reader-filter-grid">
    <label>Month
      <select data-archive-filter="month">
        <option value="">All months</option>{month_options}
      </select>
    </label>
    <label>Generation type
      <select data-archive-filter="generation">
        <option value="">All generation types</option>{generation_options}
      </select>
    </label>
    <label>Evidence state
      <select data-archive-filter="evidence">
        <option value="">All evidence states</option>{evidence_options}
      </select>
    </label>
  </div>
  <div class="archive-reader-filter-status">
    <p aria-live="polite" data-archive-result-count>{context['total_count']} retained reports shown</p>
    <button type="button" class="secondary-button" data-archive-filter-reset>Show all</button>
  </div>
</section>
<noscript><p class="archive-reader-noscript">Archive filters are optional. JavaScript is off, so all retained reports remain visible in canonical reverse chronology.</p></noscript>
"""


def _developer_details(base: Any) -> str:
    workflow_url = f"{base.GITHUB_URL}/actions/workflows/pages.yml"
    return f"""
<details class="archive-reader-developer">
  <summary>Developer outputs</summary>
  <p>Machine-readable and repository workflow outputs are secondary to the reader archive.</p>
  <ul>
    <li><a href="../search-index.json">Search index JSON</a></li>
    <li><a href="../feed.xml">RSS</a></li>
    <li><a href="../manifest.json">Manifest</a></li>
    <li><a href="{escape(workflow_url, quote=True)}">Pages workflow</a></li>
  </ul>
</details>
"""


def _inject_assets(source: str) -> str:
    stylesheet = f'<link rel="stylesheet" href="../assets/{STYLE_NAME}">'
    script = f'<script src="../assets/{SCRIPT_NAME}" defer></script>'
    if STYLE_NAME not in source:
        if source.count("</head>") != 1:
            raise ArchiveReaderIntegrationError("Archive page must contain one head close tag")
        source = source.replace("</head>", f"  {stylesheet}\n</head>", 1)
    if SCRIPT_NAME not in source:
        if source.count("</body>") != 1:
            raise ArchiveReaderIntegrationError("Archive page must contain one body close tag")
        source = source.replace("</body>", f"  {script}\n</body>", 1)
    return source


def transform_archive(source: str, context: dict[str, Any], base: Any) -> str:
    """Replace legacy archive claims with the reader-first model or fail closed."""
    hero_old = (
        "<h1>Archive</h1><p>Grouped archive of AI-generated CryptoPulse demo reports.</p>"
    )
    hero_new = (
        "<h1>Archive</h1><p>Retained CryptoPulse evidence in canonical reverse chronology, "
        "with generation and source-evidence states kept distinct.</p>"
    )
    if source.count(hero_old) != 1:
        raise ArchiveReaderIntegrationError("expected one legacy Archive hero")
    source = source.replace(hero_old, hero_new, 1)

    if source.count(ARCHIVE_HEADING) != 1:
        raise ArchiveReaderIntegrationError("expected one legacy Archive heading")
    source = source.replace(
        ARCHIVE_HEADING,
        '<div class="section-heading"><div><div class="eyebrow">Archive browser</div>'
        '<h2>Browse retained evidence</h2></div></div>',
        1,
    )

    source, stats_count = ARCHIVE_STATS_RE.subn(_summary(context), source, count=2)
    if stats_count != 1:
        raise ArchiveReaderIntegrationError("expected one legacy Archive statistics block")

    if source.count(ARCHIVE_GROUPS_MARKER) != 1:
        raise ArchiveReaderIntegrationError("expected one Archive groups anchor")
    reader_blocks = (
        _safety_panel()
        + _taxonomy_note()
        + render_filter_controls(context)
    )
    source = source.replace(
        ARCHIVE_GROUPS_MARKER,
        reader_blocks + ARCHIVE_GROUPS_MARKER,
        1,
    )

    source, developer_count = DEVELOPER_OUTPUTS_RE.subn(
        "\n" + _developer_details(base) + "\n",
        source,
        count=2,
    )
    if developer_count != 1:
        raise ArchiveReaderIntegrationError("expected one developer-output footer block")

    return _inject_assets(source)


def _relative_prefix(base: Any, html_file: Path) -> str:
    rel = html_file.relative_to(Path(base.OUT))
    return "../" * (len(rel.parents) - 1)


def _active_page(base: Any, html_file: Path) -> str:
    rel = html_file.relative_to(Path(base.OUT)).as_posix()
    if rel == "index.html":
        return "home"
    if rel == "latest.html":
        return "latest"
    if rel == "temporal.html":
        return "temporal"
    if rel == "search.html":
        return "search"
    if rel == "archive/index.html":
        return "archive"
    return ""


def _nav_link(href: str, label: str, key: str, active: str) -> str:
    current = ' aria-current="page"' if key == active else ""
    return f'<a href="{escape(href, quote=True)}"{current}>{escape(label)}</a>'


def _reader_nav(base: Any, prefix: str, active: str, temporal_available: bool) -> str:
    links = [
        _nav_link(f"{prefix}index.html", "Home", "home", active),
        _nav_link(f"{prefix}latest.html", "Most recent available", "latest", active),
    ]
    if temporal_available:
        links.append(
            _nav_link(
                f"{prefix}temporal.html",
                "Temporal evidence",
                "temporal",
                active,
            )
        )
    links.extend(
        [
            _nav_link(f"{prefix}archive/index.html", "Archive", "archive", active),
            _nav_link(f"{prefix}search.html", "Search", "search", active),
            f'<a href="{escape(base.GITHUB_URL, quote=True)}">GitHub</a>',
        ]
    )
    return (
        '\n      <nav class="site-nav" aria-label="Primary navigation">\n        '
        + "\n        ".join(links)
        + "\n      </nav>"
    )


def harmonise_navigation(base: Any) -> None:
    """Give all generated reader pages one coherent Phase 16 navigation vocabulary."""
    out = Path(base.OUT)
    temporal_available = (out / "temporal.html").exists()
    for html_file in out.glob("**/*.html"):
        source = html_file.read_text(encoding="utf-8")
        matches = list(SITE_NAV_RE.finditer(source))
        if not matches:
            continue
        if len(matches) != 1:
            raise ArchiveReaderIntegrationError(
                f"unexpected navigation count in {html_file.relative_to(out)}"
            )
        prefix = _relative_prefix(base, html_file)
        active = _active_page(base, html_file)
        source = SITE_NAV_RE.sub(
            _reader_nav(base, prefix, active, temporal_available),
            source,
            count=1,
        )
        html_file.write_text(source, encoding="utf-8")


def copy_assets(base: Any) -> None:
    for filename in (STYLE_NAME, SCRIPT_NAME):
        source = Path(base.SITE_SRC) / "assets" / filename
        if not source.exists():
            raise ArchiveReaderIntegrationError(f"missing Archive reader asset: {source}")
        destination = Path(base.OUT) / "assets" / filename
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(source, destination)


def apply(base: Any) -> None:
    """Apply the reader-first Archive model after temporal publication is decided."""
    archive_path = Path(base.OUT) / "archive" / "index.html"
    if not archive_path.exists():
        raise ArchiveReaderIntegrationError("Archive page is unavailable")

    context = build_archive_context(base)
    copy_assets(base)
    source = archive_path.read_text(encoding="utf-8")
    archive_path.write_text(transform_archive(source, context, base), encoding="utf-8")
    harmonise_navigation(base)


__all__ = [
    "ArchiveReaderIntegrationError",
    "STYLE_NAME",
    "SCRIPT_NAME",
    "apply",
    "archive_card_attributes",
    "archive_month_key",
    "build_archive_context",
    "harmonise_navigation",
    "render_filter_controls",
    "report_evidence_state",
    "report_generation",
    "report_taxonomy",
    "transform_archive",
]
