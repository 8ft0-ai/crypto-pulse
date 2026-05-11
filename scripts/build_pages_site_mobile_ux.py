#!/usr/bin/env python3
"""Build CryptoPulse Pages with mobile report-reading enhancements."""

from __future__ import annotations

import shutil
from pathlib import Path

import build_pages_site_with_search as enhanced


MOBILE_UX_STYLE_NAME = "cryptopulse-report-ux.css"
MOBILE_UX_SCRIPT_NAME = "cryptopulse-report-ux.js"


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


def add_mobile_assets_to_pages() -> None:
    for html_file in enhanced.base.OUT.glob("**/*.html"):
        html = html_file.read_text(encoding="utf-8")
        prefix = relative_prefix(html_file)

        stylesheet = f'<link rel="stylesheet" href="{prefix}assets/{MOBILE_UX_STYLE_NAME}">'
        if MOBILE_UX_STYLE_NAME not in html:
            html = html.replace("</head>", f"  {stylesheet}\n</head>", 1)

        script = f'<script src="{prefix}assets/{MOBILE_UX_SCRIPT_NAME}" defer></script>'
        if MOBILE_UX_SCRIPT_NAME not in html:
            html = html.replace("</body>", f"  {script}\n</body>", 1)

        html_file.write_text(html, encoding="utf-8")


def build() -> None:
    enhanced.build()
    copy_asset(MOBILE_UX_STYLE_NAME)
    copy_asset(MOBILE_UX_SCRIPT_NAME)
    add_mobile_assets_to_pages()
    print("Added CryptoPulse mobile report-reading UX enhancements.")


if __name__ == "__main__":
    build()
