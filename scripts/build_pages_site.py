#!/usr/bin/env python3
"""Build the CryptoPulse GitHub Pages site from archived Markdown reports.

The archive process writes reports to:

    reports/crypto/hourly/YYYY/MM/DD/HHMM_TZ_crypto_market_intelligence.md

This script renders those Markdown files into a static site under _site/ for
GitHub Pages deployment. It intentionally keeps the raw reports as the source
of truth and treats the generated site as a disposable build artefact.
"""

from __future__ import annotations

import json
import re
import shutil
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

REPORT_FILE_RE = re.compile(
    r"(?P<hhmm>\d{4})_(?P<tz>AEDT|AEST|UTC|[A-Z]{2,5})_crypto_market_intelligence\.md$"
)

# ChatGPT/web citations are useful inside a chat response, but they are not
# meaningful in a static GitHub Pages render. Preserve them in the archived raw
# Markdown, but remove them from the generated public HTML.
CHATGPT_CITATION_RE = re.compile(r"[^]*")
LEADING_H1_RE = re.compile(r"^\s*#\s+(.+?)\s*(?:\n+|$)", re.DOTALL)

TZ_OFFSETS = {
    "AEST": "+10:00",
    "AEDT": "+11:00",
    "UTC": "+00:00",
}


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


def clean_output_dir() -> None:
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True, exist_ok=True)


def split_front_matter(text: str) -> tuple[dict[str, Any], str]:
    if text.startswith("---\n"):
        parts = text.split("---\n", 2)
        if len(parts) == 3:
            _, raw_yaml, body = parts
            metadata = yaml.safe_load(raw_yaml) or {}
            if not isinstance(metadata, dict):
                metadata = {}
            return metadata, body.strip()
    return {}, text.strip()


def clean_markdown_for_site(body: str) -> str:
    """Clean render-only artefacts without mutating the archived report."""
    body = CHATGPT_CITATION_RE.sub("", body)
    # Remove spaces before punctuation left behind by stripped citations.
    body = re.sub(r"\s+([.,;:])", r"\1", body)
    # Collapse excessive blank lines introduced by stripping render-only tokens.
    body = re.sub(r"\n{4,}", "\n\n\n", body)
    return body.strip()


def extract_leading_h1(body: str) -> str | None:
    match = LEADING_H1_RE.match(body)
    if not match:
        return None
    return match.group(1).strip()


def remove_leading_h1(body: str) -> str:
    """Avoid duplicating the report title below the branded page hero."""
    return LEADING_H1_RE.sub("", body, count=1).strip()


def derive_timestamp_from_path(path: Path) -> str:
    """Return a readable timestamp from the archive path when metadata is absent."""
    try:
        rel = path.relative_to(REPORTS_DIR)
        year, month, day = rel.parts[0], rel.parts[1], rel.parts[2]
        match = REPORT_FILE_RE.match(path.name)
        if match:
            hhmm = match.group("hhmm")
            tz = match.group("tz")
            return f"{year}-{month}-{day} {hhmm[:2]}:{hhmm[2:]} {tz}"
        return f"{year}-{month}-{day}"
    except Exception:
        return path.stem.replace("_", " ")


def make_sort_key(path: Path, timestamp: str) -> str:
    """Use archive path first because it is deterministic and sortable."""
    try:
        rel = path.relative_to(REPORTS_DIR)
        year, month, day = rel.parts[0], rel.parts[1], rel.parts[2]
        match = REPORT_FILE_RE.match(path.name)
        if match:
            hhmm = match.group("hhmm")
            return f"{year}{month}{day}{hhmm}"
    except Exception:
        pass
    return timestamp


def title_from(metadata: dict[str, Any], timestamp: str, body: str) -> str:
    if metadata.get("title"):
        return str(metadata["title"])
    leading_h1 = extract_leading_h1(body)
    if leading_h1:
        return leading_h1
    if timestamp:
        return f"CryptoPulse Intelligence Briefing — {timestamp}"
    return "CryptoPulse Intelligence Briefing"


def extract_headline(body: str) -> str:
    """Extract a short headline from common report structures."""
    lines = [line.strip() for line in body.splitlines()]
    for i, line in enumerate(lines):
        normalised = line.strip("# :").lower()
        if normalised in {"headline", "1. headline"}:
            for candidate in lines[i + 1 :]:
                if candidate and not candidate.startswith("#") and not candidate.startswith("---"):
                    return candidate.strip("* ")
    for line in lines:
        if line and not line.startswith("#") and not line.startswith("---") and not line.startswith("|"):
            return line.strip("* ")
    return "Latest generated crypto market intelligence briefing."


def output_path_for(path: Path) -> Path:
    rel = path.relative_to(REPORTS_DIR).with_suffix(".html")
    return OUT / "archive" / rel


def relative_url(path: Path) -> str:
    return path.relative_to(OUT).as_posix()


def asset_prefix_for(output_path: Path) -> str:
    rel = output_path.relative_to(OUT)
    depth = len(rel.parents) - 1
    return "../" * depth


def render_markdown(body: str) -> str:
    return markdown.markdown(
        body,
        extensions=["extra", "tables", "fenced_code", "sane_lists", "toc"],
        output_format="html5",
    )


def html_page(title: str, timestamp: str, headline: str, body_html: str, asset_prefix: str) -> str:
    return f"""<!doctype html>
<html lang=\"en-AU\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>{escape(title)}</title>
  <link rel=\"stylesheet\" href=\"{asset_prefix}assets/cryptopulse.css\">
</head>
<body>
  <main class=\"page\">
    <article class=\"brief\">
      <header class=\"hero\">
        <div class=\"brandline\"><span class=\"mark\">CP</span> CryptoPulse Intelligence</div>
        <h1>{escape(title)}</h1>
        <p>{escape(timestamp)}</p>
      </header>
      <section class=\"headline\">
        <div class=\"eyebrow\">Headline</div>
        <p>{escape(headline)}</p>
      </section>
      <section class=\"content\">
        {body_html}
      </section>
      <footer class=\"footer\">
        <strong>Disclaimer:</strong> This is a market update, not financial advice. Crypto markets are volatile and data may change quickly.
      </footer>
    </article>
  </main>
</body>
</html>
"""


def index_page(reports: list[Report]) -> str:
    latest = reports[0] if reports else None
    recent = reports[:40]
    latest_block = (
        f"""
        <div class=\"latest-card\">
          <div class=\"eyebrow\">Latest brief</div>
          <h2><a href=\"{escape(latest.url)}\">{escape(latest.title)}</a></h2>
          <p class=\"muted\">{escape(latest.timestamp)}</p>
          <p>{escape(latest.headline)}</p>
          <p><a class=\"button\" href=\"{escape(latest.url)}\">Open latest briefing</a></p>
        </div>
        """
        if latest
        else "<p>No reports have been archived yet.</p>"
    )
    recent_items = "\n".join(
        f"<li><a href=\"{escape(report.url)}\">{escape(report.title)}</a><span class=\"muted\"> — {escape(report.timestamp)}</span></li>"
        for report in recent
    )
    return f"""<!doctype html>
<html lang=\"en-AU\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>CryptoPulse Intelligence</title>
  <link rel=\"stylesheet\" href=\"assets/cryptopulse.css\">
</head>
<body>
  <main class=\"page\">
    <article class=\"brief\">
      <header class=\"hero\">
        <div class=\"brandline\"><span class=\"mark\">CP</span> CryptoPulse Intelligence</div>
        <h1>CryptoPulse Intelligence</h1>
        <p>Static archive of generated crypto market intelligence briefs.</p>
      </header>
      <section class=\"content\">
        {latest_block}
        <h2>Recent reports</h2>
        <ul class=\"report-list\">
          {recent_items or '<li>No reports found.</li>'}
        </ul>
      </section>
    </article>
  </main>
</body>
</html>
"""


def archive_index_page(reports: list[Report]) -> str:
    items = "\n".join(
        f"<li><a href=\"../{escape(report.url)}\">{escape(report.title)}</a><span class=\"muted\"> — {escape(report.timestamp)}</span></li>"
        for report in reports
    )
    return f"""<!doctype html>
<html lang=\"en-AU\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <title>CryptoPulse Archive</title>
  <link rel=\"stylesheet\" href=\"../assets/cryptopulse.css\">
</head>
<body>
  <main class=\"page\">
    <article class=\"brief\">
      <header class=\"hero\">
        <div class=\"brandline\"><span class=\"mark\">CP</span> CryptoPulse Intelligence</div>
        <h1>Archive</h1>
        <p>All generated CryptoPulse reports.</p>
      </header>
      <section class=\"content\">
        <p><a href=\"../index.html\">← Home</a></p>
        <ul class=\"report-list\">
          {items or '<li>No reports found.</li>'}
        </ul>
      </section>
    </article>
  </main>
</body>
</html>
"""


def rss_feed(reports: list[Report]) -> str:
    now = format_datetime(datetime.now(timezone.utc), usegmt=True)
    items: list[str] = []
    for report in reports[:30]:
        absolute_url = urljoin(SITE_URL, report.url)
        items.append(
            f"""
    <item>
      <title>{escape(report.title)}</title>
      <link>{escape(absolute_url)}</link>
      <guid>{escape(absolute_url)}</guid>
      <description>{escape(report.headline)}</description>
    </item>"""
        )
    return f"""<?xml version=\"1.0\" encoding=\"UTF-8\" ?>
<rss version=\"2.0\">
  <channel>
    <title>CryptoPulse Intelligence</title>
    <link>{escape(SITE_URL)}</link>
    <description>Generated crypto market intelligence briefs.</description>
    <lastBuildDate>{now}</lastBuildDate>
    {''.join(items)}
  </channel>
</rss>
"""


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
        render_body = clean_markdown_for_site(body)
        timestamp = str(metadata.get("timestamp") or derive_timestamp_from_path(source_path))
        title = title_from(metadata, timestamp, render_body)
        headline = str(metadata.get("headline") or extract_headline(render_body))
        body_html = render_markdown(remove_leading_h1(render_body))
        output_path = output_path_for(source_path)
        reports.append(
            Report(
                source_path=source_path,
                output_path=output_path,
                url=relative_url(output_path),
                title=title,
                timestamp=timestamp,
                sort_key=make_sort_key(source_path, timestamp),
                headline=headline,
                body_html=body_html,
                metadata=metadata,
            )
        )

    reports.sort(key=lambda report: report.sort_key, reverse=True)
    return reports


def write_report_pages(reports: list[Report]) -> None:
    for report in reports:
        report.output_path.parent.mkdir(parents=True, exist_ok=True)
        report.output_path.write_text(
            html_page(
                title=report.title,
                timestamp=report.timestamp,
                headline=report.headline,
                body_html=report.body_html,
                asset_prefix=asset_prefix_for(report.output_path),
            ),
            encoding="utf-8",
        )


def write_site_indexes(reports: list[Report]) -> None:
    (OUT / "index.html").write_text(index_page(reports), encoding="utf-8")

    archive_dir = OUT / "archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    (archive_dir / "index.html").write_text(archive_index_page(reports), encoding="utf-8")

    if reports:
        latest = reports[0]
        (OUT / "latest.html").write_text(
            html_page(
                title=latest.title,
                timestamp=latest.timestamp,
                headline=latest.headline,
                body_html=latest.body_html,
                asset_prefix="",
            ),
            encoding="utf-8",
        )

    manifest = {
        "site": "CryptoPulse Intelligence",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "latest": report_to_manifest(reports[0]) if reports else None,
        "reports": [report_to_manifest(report) for report in reports[:100]],
    }
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (OUT / "feed.xml").write_text(rss_feed(reports), encoding="utf-8")


def report_to_manifest(report: Report) -> dict[str, Any]:
    return {
        "title": report.title,
        "timestamp": report.timestamp,
        "headline": report.headline,
        "url": report.url,
        "source": report.source_path.relative_to(ROOT).as_posix(),
        "metadata": report.metadata,
    }


def build() -> None:
    clean_output_dir()
    copy_assets()
    reports = collect_reports()
    write_report_pages(reports)
    write_site_indexes(reports)
    print(f"Built CryptoPulse Pages site with {len(reports)} report(s).")


if __name__ == "__main__":
    build()
