"""Reorder homepage sections and clarify primary actions."""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any

STYLE_NAME = "cryptopulse-homepage-hierarchy.css"


def copy_style(base: Any) -> None:
    source = base.SITE_SRC / "assets" / STYLE_NAME
    destination = base.OUT / "assets" / STYLE_NAME
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(source, destination)


def reorder_sections(html: str) -> str:
    explainer = re.search(r'\s*(<div class="explainer-grid">.*?</div>)', html, re.DOTALL)
    workflow = re.search(r'\s*(<section class="workflow-section">.*?</section>)', html, re.DOTALL)
    latest = re.search(r'\s*(<section class="latest-market-read".*?</section>)', html, re.DOTALL)
    if not (explainer and workflow and latest):
        return html

    blocks = [explainer.group(1), workflow.group(1), latest.group(1)]
    for block in blocks:
        html = html.replace(block, "", 1)

    insert = (
        '<section class="homepage-proof" aria-label="What this demo proves">'
        '<div class="eyebrow">What this demonstrates</div>'
        '<h2>Auditable automated publishing, not market advice</h2>'
        '<p>CryptoPulse demonstrates a traceable path from scheduled generation to Markdown archive, source and data-quality evidence, static rendering and published developer outputs.</p>'
        '</section>\n'
        + explainer.group(1)
        + "\n"
        + workflow.group(1)
        + "\n"
        + latest.group(1)
    )
    return html.replace('<section class="stats-grid" aria-label="Archive summary">', insert + '\n<section class="stats-grid" aria-label="Archive summary">', 1)


def prioritise_ctas(html: str) -> str:
    html = html.replace('>Open latest report</a>', '>Read latest report</a>', 1)
    html = html.replace('>Open source report</a>', '>Read full latest report</a>', 1)
    html = re.sub(
        r'<p><a class="button" href="([^"]+)">Open latest demo report</a></p>',
        r'<p><a class="text-link" href="\1">View report details →</a></p>',
        html,
        count=1,
    )
    return html


def add_style(html: str) -> str:
    if STYLE_NAME in html:
        return html
    return html.replace("</head>", f'  <link rel="stylesheet" href="assets/{STYLE_NAME}">\n</head>', 1)


def apply(base: Any) -> None:
    index_path: Path = base.OUT / "index.html"
    if not index_path.exists():
        return
    copy_style(base)
    html = index_path.read_text(encoding="utf-8")
    html = reorder_sections(html)
    html = prioritise_ctas(html)
    html = add_style(html)
    index_path.write_text(html, encoding="utf-8")
