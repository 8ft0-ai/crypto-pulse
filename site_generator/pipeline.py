"""Canonical CryptoPulse site build pipeline.

This module gives the project one coherent build entry point while preserving
existing generated output behaviour. The older scripts remain available as
compatibility shims, but GitHub Actions and documentation invoke this package
instead of chaining wrapper scripts directly.
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

from site_generator import (
    accessibility,
    archive_cards,
    homepage_hierarchy,
    homepage_summary,
    report_provenance,
    temporal_evidence,
)


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT / "scripts"


def ensure_script_import_path() -> None:
    """Allow the legacy script modules to be imported as implementation stages."""
    scripts_path = str(SCRIPTS_DIR)
    if scripts_path not in sys.path:
        sys.path.insert(0, scripts_path)


def stage(name: str) -> ModuleType:
    ensure_script_import_path()
    return importlib.import_module(name)


def build_base_site(base: Any) -> None:
    """Generate the core home, latest, archive, report, RSS, and index files."""
    base.build()


def add_search_and_quality(base: Any, search: Any) -> None:
    """Add search page, latest read, and report data-quality panels."""
    search.copy_enhancement_assets()
    (base.OUT / "search.html").write_text(search.search_page(), encoding="utf-8")
    search.latest_market_read_panel = lambda report: homepage_summary.latest_market_read_panel(report, search, base)
    search.add_latest_market_read_to_homepage()
    # Archive cards now own their stable metric vocabulary. The older metadata-chip
    # post-processor is intentionally not run because it duplicated the same slots.
    search.add_data_quality_panels_to_report_pages()
    search.add_search_link_to_existing_pages()
    search.add_enhancement_stylesheet_links()


def add_mobile_and_product_ux(mobile: Any) -> None:
    """Add product framing, simplified nav, developer links, and mobile UX."""
    mobile.copy_asset(mobile.PRODUCT_DEMO_STYLE_NAME)
    mobile.copy_asset(mobile.MOBILE_UX_STYLE_NAME)
    mobile.copy_asset(mobile.MOBILE_UX_SCRIPT_NAME)
    mobile.reframe_homepage()
    mobile.simplify_primary_navigation()
    mobile.add_developer_outputs_to_footers()
    mobile.add_mobile_assets_to_pages()


def add_brief_and_sources(brief: Any) -> None:
    """Add brief-at-a-glance panels and structured source cards."""
    brief.copy_asset(brief.BRIEF_GLANCE_STYLE_NAME)
    brief.copy_asset(brief.STRUCTURED_SOURCE_STYLE_NAME)
    brief.add_stylesheet_links()
    brief.add_brief_panels()
    brief.add_structured_source_panels()
    brief.update_search_index_with_structured_sources()


def add_archive_filters(filters: Any) -> None:
    """Add structured search-index fields and client-side filter controls."""
    filters.copy_asset(filters.SEARCH_FILTER_STYLE_NAME)
    filters.add_filter_stylesheet_links()
    filters.update_search_index_with_filter_metadata()
    filters.add_filter_controls_to_search_page()


def add_accessibility_polish(base: Any) -> None:
    """Add skip links, visible focus states, reduced-motion support, and legends."""
    accessibility.apply(base)


def configure_safe_headlines(base: Any) -> None:
    """Prevent disclaimer boilerplate becoming shared card/stat headline text."""
    original_extract = base.extract_headline
    base.extract_headline = lambda body: homepage_summary.safe_headline(body, original_extract(body))


def build() -> None:
    """Build the complete CryptoPulse static site from the Markdown archive."""
    base = stage("build_pages_site")
    search = stage("build_pages_site_with_search")
    mobile = stage("build_pages_site_mobile_ux")
    brief = stage("build_pages_site_brief_glance")
    filters = stage("build_pages_site_search_filters")

    configure_safe_headlines(base)
    archive_cards.configure(base)
    build_base_site(base)
    archive_cards.copy_style(base)
    add_search_and_quality(base, search)
    add_mobile_and_product_ux(mobile)
    add_brief_and_sources(brief)
    report_provenance.apply(base)
    homepage_hierarchy.apply(base)
    add_archive_filters(filters)
    temporal_evidence.apply(base)
    add_accessibility_polish(base)

    print("Built CryptoPulse site with safe summary headlines, stable hourly archive cards, provenance-first report pages, hierarchy-led homepage, search, data-quality, mobile UX, brief, source-card, archive-filter, deterministic temporal evidence, and accessibility enhancements.")


if __name__ == "__main__":
    build()
