#!/usr/bin/env python3
"""Build the CryptoPulse GitHub Pages site from archived Markdown reports.

Raw Markdown reports are the source of truth. The generated _site/ directory is
an artefact for GitHub Pages deployment.
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import format_datetime
from html import escape
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import markdown
import yaml

ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = ROOT / "reports" / "crypto" / "hourly"
SITE_SRC = ROOT / "site"
OUT = ROOT / "_site"
SITE_URL = "https://8ft0-ai.github.io/crypto-pulse/"
SITE_NAME = "CryptoPulse Demo"
SITE_DESCRIPTION = "AI-generated demo crypto market report examples. Not financial advice, investment research, or trading signals."
CONTENT_TYPE = "ai_generated_demo"
GITHUB_URL = "https://github.com/8ft0-ai/crypto-pulse"
DEMO_NOTICE_TITLE = "Demo site — AI-generated content"
DEMO_NOTICE_BODY = "CryptoPulse is a prototype demonstration. Reports on this site are AI-created examples used to show what automated market-report publishing could look like. They may be inaccurate, incomplete, outdated, or misleading. Do not use them for trading or investment decisions."
REPORT_NOTICE = "This report is AI-generated demo content. It has not been independently verified and should not be used for trading, investing, or risk decisions."
FOOTER_DISCLAIMER = "CryptoPulse is an experimental demonstration site. All reports are AI-generated examples for product and workflow illustration only. They may contain errors, omissions, hallucinations, stale data, or unsupported claims. Nothing on this site is financial advice, investment research, a recommendation, or a trading signal."
MANIFEST_DISCLAIMER = "Reports are AI-created examples for demonstration purposes only and must not be used for trading or investment decisions."

REPORT_FILE_RE = re.compile(r"(?P<hhmm>\d{4})_(?P<tz>AEDT|AEST|UTC|[A-Z]{2,5})_crypto_market_intelligence\.md$")
CHATGPT_CITATION_RE = re.compile(r"[^]*")
HEADING_RE = re.compile(r"^(#{2,4})\s+(.+?)\s*$", re.MULTILINE)
LEADING_H1_RE = re.compile(r"^\s*#\s+(.+?)\s*(?:\n+|$)", re.DOTALL)
SOURCE_HEADING_RE = re.compile(r"^#{2,4}\s+(?:\d+\.\s*)?Sources\s*$", re.IGNORECASE | re.MULTILINE)
NEXT_HEADING_RE = re.compile(r"^#{2,4}\s+", re.MULTILINE)


@dataclass
class Report:
    source_path: Path
    output_path: Path
    url: str
    title: str
    timestamp: str
    sort_key: str
    headline: str
    body_html: str
    metadata: dict[str, Any]
    source_rel: str
    toc_html: str
    source_items: list[str]
    year: str
    month: str
    day: str
    time_label: str
    tz: str


def split_front_matter(text: str) -> tuple[dict[str, Any], str]:
    if text.startswith("---\n"):
        parts = text.split("---\n", 2)
        if len(parts) == 3:
            metadata = yaml.safe_load(parts[1]) or {}
            return metadata if isinstance(metadata, dict) else {}, parts[2].strip()
    return {}, text.strip()


def strip_chatgpt_citations(text: str) -> str:
    text = CHATGPT_CITATION_RE.sub("", text)
    text = re.sub(r"\s+([.,;:])", r"\1", text)
    return text.strip()


def citation_marker(_match: re.Match[str]) -> str:
    return '<sup class="source-ref" title="Source reference from the original AI-generated report">source</sup>'


def clean_markdown_for_site(body: str) -> str:
    body = CHATGPT_CITATION_RE.sub(citation_marker, body)
    body = re.sub(r"\s+([.,;:])", r"\1", body)
    body = re.sub(r"\n{4,}", "\n\n\n", body)
    return body.strip()


def inline_markdown(text: str) -> str:
    html = markdown.markdown(text, extensions=["extra", "sane_lists"], output_format="html5").strip()
    if html.startswith("<p>") and html.endswith("</p>"):
        return html[3:-4]
    return html


def extract_source_items(body: str) -> list[str]:
    match = SOURCE_HEADING_RE.search(body)
    if not match:
        return []
    block = body[match.end():]
    next_match = NEXT_HEADING_RE.search(block)
    if next_match:
        block = block[:next_match.start()]

    items: list[str] = []
    seen: set[str] = set()
    for raw_line in block.splitlines():
        line = raw_line.strip()
        if not line or line == "---":
            continue
        lowered = line.lower()
        if "this is a market update" in lowered or "not financial advice" in lowered:
            continue
        if lowered.startswith("final disclaimer"):
            continue
        line = re.sub(r"^[-*+]\s+", "", line)
        line = re.sub(r"^\d+[.)]\s+", "", line)
        line = strip_chatgpt_citations(line).strip(" .")
        if not line:
            continue
        key = re.sub(r"\s+", " ", line).lower()
        if key in seen:
            continue
        seen.add(key)
        items.append(line)
        if len(items) >= 20:
            break
    return items


def source_panel(source_items: list[str]) -> str:
    if source_items:
        source_body = '<ul class="source-list">' + ''.join(f"<li>{inline_markdown(item)}</li>" for item in source_items) + '</ul>'
    else:
        source_body = '<p>No explicit source list was found in the archived Markdown report. Treat the report as unaudited AI-generated demo content.</p>'
    return f"""
      <section class="metadata-panel source-panel" aria-label="Report source attribution">
        <div>
          <span>Source attribution</span>
          <p class="source-note">Sources are extracted from the archived report where available. Inline source markers indicate that the original AI report contained runtime citations; only explicit Markdown links are clickable on the published site.</p>
          {source_body}
        </div>
      </section>
    """


def clean_output_dir() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True, exist_ok=True)


def extract_leading_h1(body: str) -> str | None:
    match = LEADING_H1_RE.match(body)
    return strip_chatgpt_citations(match.group(1).strip()) if match else None


def remove_leading_h1(body: str) -> str:
    return LEADING_H1_RE.sub("", body, count=1).strip()


def slugify_heading(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9\s-]", "", strip_chatgpt_citations(text)).strip().lower()
    slug = re.sub(r"[\s-]+", "-", slug)
    return slug or "section"


def add_heading_ids_and_toc(body: str) -> tuple[str, str]:
    seen: dict[str, int] = {}
    toc_items: list[str] = []

    def replace(match: re.Match[str]) -> str:
        hashes, heading = match.group(1), match.group(2).strip()
        base_slug = slugify_heading(heading)
        count = seen.get(base_slug, 0)
        seen[base_slug] = count + 1
        slug = base_slug if count == 0 else f"{base_slug}-{count + 1}"
        level = len(hashes)
        toc_items.append(f'<li class="toc-level-{level}"><a href="#{escape(slug)}">{escape(strip_chatgpt_citations(heading))}</a></li>')
        return f'{hashes} <span id="{slug}"></span>{heading}'

    rendered_body = HEADING_RE.sub(replace, body)
    if not toc_items:
        return rendered_body, ""
    toc_html = '<nav class="toc-card" aria-label="Report table of contents"><div class="eyebrow">In this report</div><ul>' + ''.join(toc_items) + '</ul></nav>'
    return rendered_body, toc_html


def path_parts(path: Path) -> tuple[str, str, str, str, str]:
    try:
        rel = path.relative_to(REPORTS_DIR)
        year, month, day = rel.parts[0], rel.parts[1], rel.parts[2]
        match = REPORT_FILE_RE.match(path.name)
        if match:
            hhmm = match.group("hhmm")
            return year, month, day, f"{hhmm[:2]}:{hhmm[2:]}", match.group("tz")
        return year, month, day, "", ""
    except Exception:
        return "", "", "", "", ""


def derive_timestamp_from_path(path: Path) -> str:
    year, month, day, time_label, tz = path_parts(path)
    return f"{year}-{month}-{day} {time_label} {tz}".strip() if year and month and day else path.stem.replace("_", " ")


def make_sort_key(path: Path, timestamp: str) -> str:
    year, month, day, time_label, _tz = path_parts(path)
    return f"{year}{month}{day}{time_label.replace(':', '')}" if year and month and day else timestamp


def title_from(metadata: dict[str, Any], timestamp: str, body: str) -> str:
    if metadata.get("title"):
        return str(metadata["title"])
    leading_h1 = extract_leading_h1(body)
    if leading_h1:
        return leading_h1
    return f"CryptoPulse Demo Briefing — {timestamp}" if timestamp else "CryptoPulse Demo Briefing"


def extract_headline(body: str) -> str:
    lines = [line.strip() for line in body.splitlines()]
    for i, line in enumerate(lines):
        if line.strip("# :").lower() in {"headline", "1. headline"}:
            for candidate in lines[i + 1:]:
                if candidate and not candidate.startswith("#") and not candidate.startswith("---"):
                    return strip_chatgpt_citations(candidate.strip("* "))
    for line in lines:
        if line and not line.startswith("#") and not line.startswith("---") and not line.startswith("|"):
            return strip_chatgpt_citations(line.strip("* "))
    return "Latest AI-generated demo crypto market report example."


def output_path_for(path: Path) -> Path:
    return OUT / "archive" / path.relative_to(REPORTS_DIR).with_suffix(".html")


def relative_url(path: Path) -> str:
    return path.relative_to(OUT).as_posix()


def asset_prefix_for(output_path: Path) -> str:
    rel = output_path.relative_to(OUT)
    return "../" * (len(rel.parents) - 1)


def render_markdown(body: str) -> str:
    return markdown.markdown(body, extensions=["extra", "tables", "fenced_code", "sane_lists", "toc"], output_format="html5")


def demo_banner() -> str:
    return f"""
      <section class="demo-banner" aria-label="Demo site notice">
        <div class="demo-banner-title">{escape(DEMO_NOTICE_TITLE)}</div>
        <p>{escape(DEMO_NOTICE_BODY)}</p>
      </section>
    """


def badges() -> str:
    return """
        <div class="badges" aria-label="Content status">
          <span>Demo</span>
          <span>AI-generated</span>
          <span>Not for trading</span>
        </div>
    """


def nav(asset_prefix: str = "") -> str:
    return f"""
      <nav class="site-nav" aria-label="Primary navigation">
        <a href="{asset_prefix}index.html">Home</a>
        <a href="{asset_prefix}latest.html">Latest</a>
        <a href="{asset_prefix}archive/index.html">Archive</a>
        <a href="{asset_prefix}feed.xml">RSS</a>
        <a href="{asset_prefix}manifest.json">Manifest</a>
        <a href="{asset_prefix}search-index.json">Search index</a>
        <a href="{escape(GITHUB_URL)}">GitHub</a>
      </nav>
    """


def footer() -> str:
    return f"""
      <footer class="footer">
        <strong>Demo disclaimer:</strong> {escape(FOOTER_DISCLAIMER)}
      </footer>
    """


def archive_range(reports: list[Report]) -> str:
    if not reports:
        return "No reports yet"
    newest, oldest = reports[0].timestamp, reports[-1].timestamp
    return newest if newest == oldest else f"{oldest} → {newest}"


def reporting_cadence(reports: list[Report]) -> str:
    return "Hourly archive cadence" if len(reports) > 1 else ("Single report" if reports else "No reports yet")


def dashboard_cards(reports: list[Report]) -> str:
    latest = reports[0] if reports else None
    cards = [
        ("Latest report", latest.timestamp if latest else "No reports yet"),
        ("Archived reports", str(len(reports))),
        ("Archive range", archive_range(reports)),
        ("Feed", "RSS + manifest + search index"),
    ]
    if latest:
        cards.insert(2, ("Latest headline", latest.headline))
    return "\n".join(f"""
          <article class="stat-card">
            <div class="eyebrow">{escape(label)}</div>
            <p>{escape(value)}</p>
          </article>""" for label, value in cards)


def recent_report_cards(reports: list[Report]) -> str:
    if not reports:
        return "<p>No reports found.</p>"
    return "\n".join(f"""
          <article class="report-card">
            <div class="eyebrow">{escape(report.timestamp)}</div>
            <h3><a href="{escape(report.url)}">{escape(report.title)}</a></h3>
            <p>{escape(report.headline)}</p>
            <a class="text-link" href="{escape(report.url)}">Open report →</a>
          </article>""" for report in reports[:12])


def metadata_panel(report: Report) -> str:
    return f"""
      <section class="metadata-panel" aria-label="Report metadata">
        <div><span>Generated</span><strong>{escape(report.timestamp)}</strong></div>
        <div><span>Content type</span><strong>AI-generated demo</strong></div>
        <div><span>Source</span><strong>Markdown archive</strong></div>
        <div><span>Archive path</span><strong>{escape(report.source_rel)}</strong></div>
      </section>
    """


def report_pager(previous_report: Report | None, next_report: Report | None, asset_prefix: str) -> str:
    prev_html = f'<a href="{asset_prefix}{escape(previous_report.url)}">← Previous report</a>' if previous_report else '<span>← Previous report</span>'
    next_html = f'<a href="{asset_prefix}{escape(next_report.url)}">Next report →</a>' if next_report else '<span>Next report →</span>'
    return f"""
      <nav class="report-pager" aria-label="Report navigation">
        {prev_html}
        <a href="{asset_prefix}archive/index.html">Back to archive</a>
        {next_html}
      </nav>
    """


def html_page(report: Report, asset_prefix: str, previous_report: Report | None = None, next_report: Report | None = None) -> str:
    pager = report_pager(previous_report, next_report, asset_prefix)
    return f"""<!doctype html>
<html lang="en-AU">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(report.title)} | {escape(SITE_NAME)}</title>
  <link rel="stylesheet" href="{asset_prefix}assets/cryptopulse.css">
</head>
<body>
  <main class="page">
    <article class="brief">
      {demo_banner()}
      {nav(asset_prefix)}
      <header class="hero report-hero">
        <div class="brandline"><span class="mark">CP</span> {escape(SITE_NAME)}</div>
        <h1>{escape(report.title)}</h1>
        <p>{escape(report.timestamp)}</p>
        {badges()}
      </header>
      <section class="report-warning compact-warning">
        <div class="eyebrow">Report warning</div>
        <p>{escape(REPORT_NOTICE)}</p>
      </section>
      {metadata_panel(report)}
      {source_panel(report.source_items)}
      <section class="headline">
        <div class="eyebrow">Headline</div>
        <p>{escape(report.headline)}</p>
      </section>
      {pager}
      <section class="content report-content">
        {report.toc_html}
        <div class="report-body">
          {report.body_html}
        </div>
      </section>
      {pager}
      {footer()}
    </article>
  </main>
</body>
</html>
"""


def index_page(reports: list[Report]) -> str:
    latest = reports[0] if reports else None
    latest_block = f"""
        <section class="latest-feature">
          <div>
            <div class="eyebrow">Latest demo report</div>
            <h2><a href="{escape(latest.url)}">{escape(latest.title)}</a></h2>
            <p class="muted">{escape(latest.timestamp)}</p>
            <p>{escape(latest.headline)}</p>
            <p class="demo-note">AI-generated demo content. Not financial advice, investment research, a recommendation, or a trading signal.</p>
          </div>
          <p><a class="button" href="{escape(latest.url)}">Open latest demo report</a></p>
        </section>""" if latest else "<p>No reports have been archived yet.</p>"
    return f"""<!doctype html>
<html lang="en-AU">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(SITE_NAME)}</title>
  <link rel="stylesheet" href="assets/cryptopulse.css">
</head>
<body>
  <main class="page">
    <article class="brief">
      {demo_banner()}
      {nav()}
      <header class="hero landing-hero">
        <div class="brandline"><span class="mark">CP</span> {escape(SITE_NAME)}</div>
        <h1>AI-generated crypto market report publishing prototype</h1>
        <p>An experimental GitHub Pages site showing how AI-generated crypto market reports might be archived, rendered, and published automatically.</p>
        {badges()}
      </header>
      <section class="content landing-content">
        <section class="stats-grid" aria-label="Archive summary">{dashboard_cards(reports)}</section>
        <div class="explainer-grid">
          <section class="explainer-card"><h2>What this is</h2><p>CryptoPulse is a demonstration site showing how AI-generated market reports could be produced, archived, and published using GitHub Pages.</p></section>
          <section class="explainer-card warning"><h2>What this is not</h2><p>This is not an investment research service, trading system, signal provider, market data product, or financial advice. The reports are generated examples and should not be relied on for accuracy, timeliness, or completeness.</p></section>
        </div>
        <section class="workflow-section">
          <div class="eyebrow">How this demo works</div>
          <h2>Prompt → AI Report → Markdown Archive → Static Site → RSS / Manifest</h2>
          <div class="workflow-grid">
            <article><strong>1. Generate</strong><p>A scheduled prompt creates a crypto market report example.</p></article>
            <article><strong>2. Archive</strong><p>The report is stored as Markdown, preserving the generated body.</p></article>
            <article><strong>3. Build</strong><p>GitHub Actions renders the archive into a static Pages site.</p></article>
            <article><strong>4. Publish</strong><p>The latest report, archive, RSS feed, and manifest are published automatically.</p></article>
          </div>
        </section>
        {latest_block}
        <section>
          <div class="section-heading"><div><div class="eyebrow">Archive preview</div><h2>Recent demo reports</h2></div><a class="text-link" href="archive/index.html">View full archive →</a></div>
          <div class="report-card-grid">{recent_report_cards(reports)}</div>
        </section>
      </section>
      {footer()}
    </article>
  </main>
</body>
</html>
"""


def archive_stats_cards(reports: list[Report]) -> str:
    cards = [("Total reports", str(len(reports))), ("Newest report", reports[0].timestamp if reports else "No reports yet"), ("Oldest report", reports[-1].timestamp if reports else "No reports yet"), ("Date range", archive_range(reports)), ("Cadence", reporting_cadence(reports)), ("Search index", "search-index.json")]
    return "\n".join(f"""
          <article class="archive-stat-card"><div class="eyebrow">{escape(label)}</div><p>{escape(value)}</p></article>""" for label, value in cards)


def month_name(month: str) -> str:
    try:
        return datetime.strptime(month, "%m").strftime("%B")
    except ValueError:
        return month


def archive_jump_links(reports: list[Report]) -> str:
    months: list[tuple[str, str, str]] = []
    seen: set[str] = set()
    for report in reports:
        if not report.year or not report.month:
            continue
        key = f"{report.year}-{report.month}"
        if key not in seen:
            seen.add(key)
            months.append((key, report.year, month_name(report.month)))
    if not months:
        return ""
    links = "\n".join(f'<a href="#{escape(key)}">{escape(label)} {escape(year)}</a>' for key, year, label in months)
    return f'<nav class="archive-jumps" aria-label="Archive month navigation"><div class="eyebrow">Jump to month</div><div>{links}</div></nav>'


def grouped_archive(reports: list[Report]) -> str:
    if not reports:
        return "<p>No reports found.</p>"
    grouped: dict[str, dict[str, dict[str, list[Report]]]] = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for report in reports:
        grouped[report.year or "Unknown year"][report.month or "Unknown month"][report.day or "Unknown day"].append(report)
    parts: list[str] = []
    for year in sorted(grouped.keys(), reverse=True):
        parts.append(f'<section class="archive-year" data-year="{escape(year)}"><h2>{escape(year)}</h2>')
        for month in sorted(grouped[year].keys(), reverse=True):
            month_label = month_name(month)
            month_anchor = f"{year}-{month}"
            month_reports = sum(len(day_reports) for day_reports in grouped[year][month].values())
            parts.append(f'<section class="archive-month" id="{escape(month_anchor)}" data-year="{escape(year)}" data-month="{escape(month)}"><h3>{escape(month_label)} <span>{month_reports} reports</span></h3>')
            for day in sorted(grouped[year][month].keys(), reverse=True):
                day_reports = grouped[year][month][day]
                day_label = f"{int(day)} {month_label}" if day.isdigit() else day
                parts.append(f'<section class="archive-day" data-day="{escape(day)}"><h4>{escape(day_label)}</h4><div class="archive-card-grid">')
                for report in day_reports:
                    keywords = " ".join([report.title, report.headline, report.timestamp, " ".join(report.source_items)]).lower()
                    parts.append(f"""
                      <article class="archive-card" data-year="{escape(report.year)}" data-month="{escape(report.month)}" data-day="{escape(report.day)}" data-keywords="{escape(keywords)}">
                        <div class="eyebrow">{escape(report.time_label)} {escape(report.tz)}</div>
                        <h5><a href="../{escape(report.url)}">{escape(report.title)}</a></h5>
                        <p>{escape(report.headline)}</p>
                        <a class="text-link" href="../{escape(report.url)}">Open report →</a>
                      </article>""")
                parts.append("</div></section>")
            parts.append('<p class="return-top"><a href="#top">Return to top ↑</a></p></section>')
        parts.append("</section>")
    return "\n".join(parts)


def archive_index_page(reports: list[Report]) -> str:
    return f"""<!doctype html>
<html lang="en-AU">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Archive | {escape(SITE_NAME)}</title><link rel="stylesheet" href="../assets/cryptopulse.css"></head>
<body><main class="page" id="top"><article class="brief">{demo_banner()}{nav("../")}
<header class="hero"><div class="brandline"><span class="mark">CP</span> {escape(SITE_NAME)}</div><h1>Archive</h1><p>Grouped archive of AI-generated CryptoPulse demo reports.</p>{badges()}</header>
<section class="content archive-content"><div class="section-heading"><div><div class="eyebrow">Archive browser</div><h2>Browse generated demo reports</h2></div><a class="text-link" href="../search-index.json">Open search index JSON →</a></div><section class="archive-stats-grid" aria-label="Archive statistics">{archive_stats_cards(reports)}</section>{archive_jump_links(reports)}<section class="archive-groups">{grouped_archive(reports)}</section></section>{footer()}</article></main></body></html>
"""


def rss_feed(reports: list[Report]) -> str:
    now = format_datetime(datetime.now(timezone.utc), usegmt=True)
    items = []
    for report in reports[:30]:
        absolute_url = urljoin(SITE_URL, report.url)
        items.append(f"""
    <item><title>{escape(report.title)}</title><link>{escape(absolute_url)}</link><guid>{escape(absolute_url)}</guid><description>{escape(SITE_DESCRIPTION + ' ' + report.headline)}</description></item>""")
    return f"""<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0"><channel><title>{escape(SITE_NAME)}</title><link>{escape(SITE_URL)}</link><description>{escape(SITE_DESCRIPTION)}</description><lastBuildDate>{now}</lastBuildDate>{''.join(items)}</channel></rss>
"""


def report_to_manifest(report: Report) -> dict[str, Any]:
    return {"title": report.title, "timestamp": report.timestamp, "headline": report.headline, "url": report.url, "source": report.source_rel, "sources": report.source_items, "content_type": CONTENT_TYPE, "disclaimer": MANIFEST_DISCLAIMER, "metadata": report.metadata}


def search_index(reports: list[Report]) -> list[dict[str, Any]]:
    return [{"title": report.title, "timestamp": report.timestamp, "headline": report.headline, "url": report.url, "path": report.source_rel, "year": report.year, "month": report.month, "day": report.day, "sources": report.source_items, "content_type": CONTENT_TYPE, "disclaimer": MANIFEST_DISCLAIMER} for report in reports]


def copy_assets() -> None:
    assets_out = OUT / "assets"
    assets_out.mkdir(parents=True, exist_ok=True)
    css_src = SITE_SRC / "assets" / "cryptopulse.css"
    if not css_src.exists():
        raise FileNotFoundError(f"Missing stylesheet: {css_src}")
    shutil.copy(css_src, assets_out / "cryptopulse.css")


def collect_reports() -> list[Report]:
    reports: list[Report] = []
    if not REPORTS_DIR.exists():
        return reports
    for source_path in sorted(REPORTS_DIR.glob("**/*.md")):
        raw = source_path.read_text(encoding="utf-8")
        metadata, body = split_front_matter(raw)
        source_items = extract_source_items(body)
        render_body = clean_markdown_for_site(body)
        body_for_text = strip_chatgpt_citations(body)
        timestamp = str(metadata.get("timestamp") or derive_timestamp_from_path(source_path))
        title = title_from(metadata, timestamp, render_body)
        headline = str(metadata.get("headline") or extract_headline(body_for_text))
        body_without_h1 = remove_leading_h1(render_body)
        body_with_ids, toc_html = add_heading_ids_and_toc(body_without_h1)
        body_html = render_markdown(body_with_ids)
        output_path = output_path_for(source_path)
        source_rel = source_path.relative_to(ROOT).as_posix()
        year, month, day, time_label, tz = path_parts(source_path)
        reports.append(Report(source_path, output_path, relative_url(output_path), title, timestamp, make_sort_key(source_path, timestamp), headline, body_html, metadata, source_rel, toc_html, source_items, year, month, day, time_label, tz))
    root_path = str(ROOT)
    if root_path not in sys.path:
        sys.path.insert(0, root_path)
    from site_generator import report_chronology

    return report_chronology.canonicalise_reports(reports)


def write_report_pages(reports: list[Report]) -> None:
    for index, report in enumerate(reports):
        previous_report = reports[index + 1] if index + 1 < len(reports) else None
        next_report = reports[index - 1] if index > 0 else None
        report.output_path.parent.mkdir(parents=True, exist_ok=True)
        report.output_path.write_text(html_page(report, asset_prefix_for(report.output_path), previous_report, next_report), encoding="utf-8")


def write_site_indexes(reports: list[Report]) -> None:
    (OUT / "index.html").write_text(index_page(reports), encoding="utf-8")
    archive_dir = OUT / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    (archive_dir / "index.html").write_text(archive_index_page(reports), encoding="utf-8")
    if reports:
        latest = reports[0]
        (OUT / "latest.html").write_text(html_page(latest, "", reports[1] if len(reports) > 1 else None, None), encoding="utf-8")
    manifest = {"site": SITE_NAME, "description": SITE_DESCRIPTION, "content_type": CONTENT_TYPE, "disclaimer": MANIFEST_DISCLAIMER, "generated_at": datetime.now(timezone.utc).isoformat(), "latest": report_to_manifest(reports[0]) if reports else None, "reports": [report_to_manifest(report) for report in reports[:100]]}
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (OUT / "feed.xml").write_text(rss_feed(reports), encoding="utf-8")
    (OUT / "search-index.json").write_text(json.dumps(search_index(reports), indent=2), encoding="utf-8")


def build() -> None:
    clean_output_dir()
    copy_assets()
    reports = collect_reports()
    write_report_pages(reports)
    write_site_indexes(reports)
    print(f"Built CryptoPulse Pages site with {len(reports)} report(s).")


if __name__ == "__main__":
    build()