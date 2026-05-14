"""Accessibility and reader-navigation post-processing for CryptoPulse pages."""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any


ACCESSIBILITY_STYLE_NAME = "cryptopulse-accessibility.css"
SKIP_LINK_HTML = '<a class="skip-link" href="#main-content">Skip to main content</a>'
MAIN_TAG_RE = re.compile(r'<main class="page"(?![^>]*id=)')
BODY_TAG_RE = re.compile(r'(<body[^>]*>)(\s*)', re.IGNORECASE)
DATA_QUALITY_PANEL_RE = re.compile(
    r'(<section class="report-data-quality-panel" aria-label="Report data quality">.*?<div class="data-quality-badges">.*?</div>)(\s*</section>)',
    re.DOTALL,
)


def relative_prefix(out_dir: Path, page_path: Path) -> str:
    rel = page_path.relative_to(out_dir)
    return "../" * (len(rel.parents) - 1)


def copy_accessibility_asset(base: Any) -> None:
    source = base.SITE_SRC / "assets" / ACCESSIBILITY_STYLE_NAME
    destination = base.OUT / "assets" / ACCESSIBILITY_STYLE_NAME
    if not source.exists():
        raise FileNotFoundError(f"Missing asset: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(source, destination)


def add_accessibility_stylesheet(base: Any, html: str, page_path: Path) -> str:
    if ACCESSIBILITY_STYLE_NAME in html:
        return html
    prefix = relative_prefix(base.OUT, page_path)
    return html.replace(
        "</head>",
        f'  <link rel="stylesheet" href="{prefix}assets/{ACCESSIBILITY_STYLE_NAME}">\n</head>',
        1,
    )


def add_skip_link(html: str) -> str:
    if 'class="skip-link"' in html:
        return html
    return BODY_TAG_RE.sub(lambda match: f"{match.group(1)}{match.group(2)}  {SKIP_LINK_HTML}\n", html, count=1)


def add_main_landmark_target(html: str) -> str:
    if 'id="main-content"' in html:
        return html
    return MAIN_TAG_RE.sub('<main class="page" id="main-content" tabindex="-1"', html, count=1)


def data_quality_legend() -> str:
    return """
        <div class="data-quality-legend" aria-label="Data-quality badge meanings">
          <span><strong>Full</strong> current and complete enough for this report</span>
          <span><strong>Partial</strong> usable but delayed, incomplete, or mixed</span>
          <span><strong>Unavailable</strong> not accessible during generation</span>
        </div>"""


def add_data_quality_legend(html: str) -> str:
    if "data-quality-legend" in html or "report-data-quality-panel" not in html:
        return html
    return DATA_QUALITY_PANEL_RE.sub(lambda match: f"{match.group(1)}\n{data_quality_legend()}{match.group(2)}", html, count=1)


def enhance_page(base: Any, page_path: Path) -> None:
    html = page_path.read_text(encoding="utf-8")
    html = add_accessibility_stylesheet(base, html, page_path)
    html = add_skip_link(html)
    html = add_main_landmark_target(html)
    html = add_data_quality_legend(html)
    page_path.write_text(html, encoding="utf-8")


def apply(base: Any) -> None:
    """Apply accessibility polish to generated HTML pages and copy CSS."""
    copy_accessibility_asset(base)
    for html_file in base.OUT.glob("**/*.html"):
        enhance_page(base, html_file)
