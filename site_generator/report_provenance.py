"""Report-page provenance hierarchy and product-boundary consolidation."""

from __future__ import annotations

import re
import shutil
from html import escape
from pathlib import Path
from typing import Any

STYLE_NAME = "cryptopulse-report-provenance.css"

WARNING_RE = re.compile(r'\s*<section class="report-warning compact-warning">.*?</section>\s*', re.DOTALL)
QUALITY_RE = re.compile(r'\s*<section class="report-data-quality-panel".*?</section>\s*', re.DOTALL)
BRIEF_CARD_RE = re.compile(r'\s*<article class="brief-glance-card">.*?</article>\s*', re.DOTALL)
STRONG_RE = re.compile(r'<strong>(.*?)</strong>', re.DOTALL)
TAG_RE = re.compile(r'<[^>]+>')
PLACEHOLDER_TOKENS = (
    "not specified",
    "not explicitly extracted",
    "open latest report",
    "missing fields are not inferred",
)
BOILERPLATE_TOKENS = (
    "not financial advice",
    "should not be used for trading",
    "should not be used for investing",
    "product and workflow illustration only",
    "ai-generated demo content",
)


def plain_text(html: str) -> str:
    return re.sub(r"\s+", " ", TAG_RE.sub(" ", html)).strip().lower()


def is_non_summary_text(value: str) -> bool:
    text = plain_text(value)
    return not text or any(token in text for token in PLACEHOLDER_TOKENS + BOILERPLATE_TOKENS)


def boundary_panel() -> str:
    return """
      <section class="report-provenance-lead" aria-label="Report provenance and generation boundaries">
        <div>
          <div class="eyebrow">Provenance first</div>
          <h2>What generated this page</h2>
          <p>This page is rendered from the archived Markdown report and its declared source metadata. The detailed source and audit trail remains available below.</p>
        </div>
        <ul class="generation-boundaries">
          <li><strong>No LLM calls during site build</strong><span>The static renderer does not generate or enrich market narrative.</span></li>
          <li><strong>No hidden enrichment</strong><span>Displayed summaries and source status come from committed report content and metadata.</span></li>
          <li><strong>No committed <code>_site/</code></strong><span>Published HTML is disposable build output; Markdown remains the source of truth.</span></li>
        </ul>
        <p class="product-boundary"><strong>Demo boundary:</strong> This is an automated publishing demonstration, not financial advice, investment research, a recommendation or a trading signal.</p>
      </section>
    """


def suppress_brief_boilerplate(html: str) -> str:
    removed = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal removed
        strong = STRONG_RE.search(match.group(0))
        if strong and is_non_summary_text(strong.group(1)):
            removed += 1
            return ""
        return match.group(0)

    html = BRIEF_CARD_RE.sub(replace, html)
    if removed and "report-format-note" not in html:
        marker = '        <div class="brief-glance-grid">'
        note = '<p class="report-format-note">Only meaningful fields available in this report format are shown.</p>\n        '
        html = html.replace(marker, note + marker, 1)
    return html


def transform_report_html(html: str) -> str:
    """Lead with provenance, consolidate warnings, and suppress summary boilerplate."""
    html = WARNING_RE.sub("\n", html, count=1)
    quality_match = QUALITY_RE.search(html)
    quality = quality_match.group(0).strip() if quality_match else ""
    if quality_match:
        html = QUALITY_RE.sub("\n", html, count=1)

    lead = boundary_panel()
    if quality:
        lead += "\n" + quality

    marker = '      <section class="brief-glance-panel"'
    if marker in html and "report-provenance-lead" not in html:
        html = html.replace(marker, lead + "\n" + marker, 1)
    elif "report-provenance-lead" not in html:
        html = html.replace('      <section class="headline">', lead + '\n      <section class="headline">', 1)

    return suppress_brief_boilerplate(html)


def copy_asset(base: Any) -> None:
    source = base.SITE_SRC / "assets" / STYLE_NAME
    destination = base.OUT / "assets" / STYLE_NAME
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(source, destination)


def add_stylesheet(html: str, prefix: str) -> str:
    if STYLE_NAME in html:
        return html
    return html.replace("</head>", f'  <link rel="stylesheet" href="{escape(prefix)}assets/{STYLE_NAME}">\n</head>', 1)


def apply(base: Any) -> None:
    copy_asset(base)
    reports = base.collect_reports()
    targets: list[Path] = [report.output_path for report in reports]
    if reports:
        targets.append(base.OUT / "latest.html")

    for path in targets:
        if not path.exists():
            continue
        prefix = "../" * (len(path.relative_to(base.OUT).parents) - 1)
        html = path.read_text(encoding="utf-8")
        html = transform_report_html(html)
        html = add_stylesheet(html, prefix)
        path.write_text(html, encoding="utf-8")
