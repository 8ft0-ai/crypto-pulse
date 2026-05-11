#!/usr/bin/env python3
"""Build CryptoPulse Pages with product-demo and mobile reading enhancements."""

from __future__ import annotations

import re
import shutil
from html import escape
from pathlib import Path

import build_pages_site_with_search as enhanced


MOBILE_UX_STYLE_NAME = "cryptopulse-report-ux.css"
MOBILE_UX_SCRIPT_NAME = "cryptopulse-report-ux.js"
PRODUCT_DEMO_STYLE_NAME = "cryptopulse-product-demo.css"
SITE_NAV_RE = re.compile(
    r"\s*<nav class=\"site-nav\" aria-label=\"Primary navigation\">.*?</nav>",
    re.DOTALL,
)


def relative_prefix(page_path: Path) -> str:
    rel = page_path.relative_to(enhanced.base.OUT)
    return "../" * (len(rel.parents) - 1)


def copy_asset(filename: str) -> None:
    source = enhanced.base.SITE_SRC / "assets" / filename
    destination = enhanced.base.OUT / "assets" / filename
    if not source.exists():
        raise FileNotFoundError(f"Missing asset: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(source, destination)


def active_page_for(html_file: Path) -> str:
    rel = html_file.relative_to(enhanced.base.OUT).as_posix()
    if rel == "index.html":
        return "home"
    if rel == "latest.html":
        return "latest"
    if rel == "search.html":
        return "search"
    if rel == "archive/index.html" or rel.startswith("archive/"):
        return "archive"
    return ""


def nav_link(href: str, label: str, key: str, active: str) -> str:
    current = ' aria-current="page"' if key == active else ""
    return f'<a href="{href}"{current}>{label}</a>'


def product_nav(prefix: str, active: str) -> str:
    return f"""
      <nav class="site-nav" aria-label="Primary navigation">
        {nav_link(f'{prefix}index.html', 'Home', 'home', active)}
        {nav_link(f'{prefix}latest.html', 'Latest Report', 'latest', active)}
        {nav_link(f'{prefix}archive/index.html', 'Archive', 'archive', active)}
        {nav_link(f'{prefix}search.html', 'Search', 'search', active)}
        <a href="{escape(enhanced.base.GITHUB_URL)}">GitHub</a>
      </nav>
    """


def developer_outputs(prefix: str) -> str:
    workflow_url = f"{enhanced.base.GITHUB_URL}/actions/workflows/pages.yml"
    return f"""
        <div class="developer-output-links" aria-label="Developer outputs">
          <span>Developer outputs</span>
          <a href="{prefix}feed.xml">RSS</a>
          <a href="{prefix}manifest.json">Manifest</a>
          <a href="{prefix}search-index.json">Search index</a>
          <a href="{escape(workflow_url)}">Pages workflow</a>
        </div>
    """


def reframe_homepage() -> None:
    reports = enhanced.base.collect_reports()
    latest_url = reports[0].url if reports else "latest.html"
    index_path = enhanced.base.OUT / "index.html"
    if not index_path.exists():
        return

    html = index_path.read_text(encoding="utf-8")
    html = html.replace('<header class="hero landing-hero">', '<header class="hero landing-hero product-hero">', 1)
    html = html.replace(
        "<h1>AI-generated crypto market report publishing prototype</h1>",
        "<h1>AI-generated crypto market intelligence, archived hourly.</h1>",
        1,
    )
    html = html.replace(
        "<p>An experimental GitHub Pages site showing how AI-generated crypto market reports might be archived, rendered, and published automatically.</p>",
        "<p>A static, searchable demo showing how scheduled AI reports can be generated, quality-labelled, source-attributed and published automatically.</p>",
        1,
    )

    hero_actions = f"""
        <div class="hero-actions" aria-label="Primary actions">
          <a class="button hero-primary-action" href="{escape(latest_url)}">Open latest report</a>
          <a class="button secondary-button" href="search.html">Search archive</a>
          <a class="button ghost-button" href="{escape(enhanced.base.GITHUB_URL)}/actions/workflows/pages.yml">View GitHub workflow</a>
        </div>"""
    html = re.sub(
        r'(<div class="badges" aria-label="Content status">.*?</div>)\s*</header>',
        lambda match: f"{match.group(1)}\n{hero_actions}\n      </header>",
        html,
        count=1,
        flags=re.DOTALL,
    )

    html = html.replace(
        "<section class=\"explainer-card\"><h2>What this is</h2><p>CryptoPulse is a demonstration site showing how AI-generated market reports could be produced, archived, and published using GitHub Pages.</p></section>",
        "<section class=\"explainer-card\"><h2>What this demonstrates</h2><p>CryptoPulse shows how scheduled AI market analysis can become a searchable, auditable, static intelligence archive with report metadata, source attribution and data-quality labelling.</p></section>",
        1,
    )
    html = html.replace(
        "<section class=\"explainer-card warning\"><h2>What this is not</h2><p>This is not an investment research service, trading system, signal provider, market data product, or financial advice. The reports are generated examples and should not be relied on for accuracy, timeliness, or completeness.</p></section>",
        "<section class=\"explainer-card warning\"><h2>Demo boundary</h2><p>This is not an investment research service, trading system, signal provider, market data product, or financial advice. The reports are generated examples and should not be relied on for accuracy, timeliness, or completeness.</p></section>",
        1,
    )
    html = html.replace(
        "<h2>Prompt → AI Report → Markdown Archive → Static Site → RSS / Manifest</h2>",
        "<h2>Scheduled prompt → AI brief → Markdown archive → Static intelligence site</h2>",
        1,
    )

    index_path.write_text(html, encoding="utf-8")


def simplify_primary_navigation() -> None:
    for html_file in enhanced.base.OUT.glob("**/*.html"):
        html = html_file.read_text(encoding="utf-8")
        prefix = relative_prefix(html_file)
        active = active_page_for(html_file)
        html = SITE_NAV_RE.sub(product_nav(prefix, active), html, count=1)
        html_file.write_text(html, encoding="utf-8")


def add_developer_outputs_to_footers() -> None:
    for html_file in enhanced.base.OUT.glob("**/*.html"):
        html = html_file.read_text(encoding="utf-8")
        if "developer-output-links" in html:
            continue
        prefix = relative_prefix(html_file)
        html = html.replace("</footer>", f"{developer_outputs(prefix)}\n      </footer>", 1)
        html_file.write_text(html, encoding="utf-8")


def add_mobile_assets_to_pages() -> None:
    for html_file in enhanced.base.OUT.glob("**/*.html"):
        html = html_file.read_text(encoding="utf-8")
        prefix = relative_prefix(html_file)

        for stylesheet_name in (PRODUCT_DEMO_STYLE_NAME, MOBILE_UX_STYLE_NAME):
            stylesheet = f'<link rel="stylesheet" href="{prefix}assets/{stylesheet_name}">'
            if stylesheet_name not in html:
                html = html.replace("</head>", f"  {stylesheet}\n</head>", 1)

        script = f'<script src="{prefix}assets/{MOBILE_UX_SCRIPT_NAME}" defer></script>'
        if MOBILE_UX_SCRIPT_NAME not in html:
            html = html.replace("</body>", f"  {script}\n</body>", 1)

        html_file.write_text(html, encoding="utf-8")


def build() -> None:
    enhanced.build()
    copy_asset(PRODUCT_DEMO_STYLE_NAME)
    copy_asset(MOBILE_UX_STYLE_NAME)
    copy_asset(MOBILE_UX_SCRIPT_NAME)
    reframe_homepage()
    simplify_primary_navigation()
    add_developer_outputs_to_footers()
    add_mobile_assets_to_pages()
    print("Added CryptoPulse product-demo framing, simplified navigation, developer outputs, and mobile report-reading UX enhancements.")


if __name__ == "__main__":
    build()
