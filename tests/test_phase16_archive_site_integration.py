from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from site_generator import archive_reader


ARCHIVE = """<!doctype html><html><head><title>Archive</title></head><body>
<nav class="site-nav" aria-label="Primary navigation"><a href="../latest.html">Latest Report</a></nav>
<header class="hero"><h1>Archive</h1><p>Grouped archive of AI-generated CryptoPulse demo reports.</p></header>
<section class="content archive-content"><div class="section-heading"><div><div class="eyebrow">Archive browser</div><h2>Browse generated demo reports</h2></div><a class="text-link" href="../search-index.json">Open search index JSON →</a></div>
<section class="archive-stats-grid" aria-label="Archive statistics"><article><p>Hourly archive cadence</p></article></section>
<section class="archive-groups"><article class="archive-card" data-archive-month="2026-07" data-archive-generation="deterministic" data-archive-evidence-state="validated-source-evidence">Report</article></section></section>
<footer class="footer"><div class="developer-output-links" aria-label="Developer outputs"><span>Developer outputs</span><a href="../search-index.json">Search index</a></div></footer>
</body></html>"""

PAGE = """<!doctype html><html><head><title>Page</title></head><body>
<nav class="site-nav" aria-label="Primary navigation"><a href="latest.html">Latest Report</a></nav>
<footer class="footer"></footer></body></html>"""

REPORT_PAGE = """<!doctype html><html><head><title>Report</title></head><body>
<nav class="site-nav" aria-label="Primary navigation"><a href="../../../../latest.html">Latest Report</a></nav>
<footer class="footer"></footer></body></html>"""


def retained_report():
    return SimpleNamespace(
        report_time_utc="2026-07-08T10:31:48Z",
        timestamp="2026-07-08 20:31 AEST",
        year="2026",
        month="07",
        day="08",
        chronology_kind="deterministic",
        metadata={
            "schema_version": "deterministic-crypto-report/v1",
            "quality_status": "valid-ok",
        },
    )


def base_for(root: Path, reports):
    return SimpleNamespace(
        ROOT=root,
        OUT=root / "_site",
        SITE_SRC=root / "site",
        GITHUB_URL="https://github.com/8ft0-ai/crypto-pulse",
        collect_reports=lambda: list(reports),
        month_name=lambda month: "July" if month == "07" else month,
    )


def prepare(root: Path, *, temporal: bool):
    out = root / "_site"
    archive = out / "archive"
    report_dir = archive / "2026" / "07" / "08"
    assets = root / "site" / "assets"
    report_dir.mkdir(parents=True)
    assets.mkdir(parents=True)

    (archive / "index.html").write_text(ARCHIVE, encoding="utf-8")
    (out / "index.html").write_text(PAGE, encoding="utf-8")
    (out / "latest.html").write_text(PAGE, encoding="utf-8")
    (out / "search.html").write_text(PAGE, encoding="utf-8")
    (report_dir / "2031_AEST.html").write_text(REPORT_PAGE, encoding="utf-8")
    if temporal:
        (out / "temporal.html").write_text(PAGE, encoding="utf-8")

    (assets / archive_reader.STYLE_NAME).write_text(
        ".archive-reader-controls{}\n",
        encoding="utf-8",
    )
    (assets / archive_reader.SCRIPT_NAME).write_text(
        "document.querySelector('[data-archive-filter-controls]');\n",
        encoding="utf-8",
    )


class ArchiveReaderSiteIntegrationTests(unittest.TestCase):
    def test_apply_copies_assets_transforms_archive_and_harmonises_navigation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare(root, temporal=True)
            base = base_for(root, [retained_report()])

            archive_reader.apply(base)

            archive_html = (root / "_site" / "archive" / "index.html").read_text(
                encoding="utf-8"
            )
            report_html = (
                root / "_site" / "archive" / "2026" / "07" / "08" / "2031_AEST.html"
            ).read_text(encoding="utf-8")

            self.assertIn("Most recent available", archive_html)
            self.assertIn('href="../temporal.html"', archive_html)
            self.assertIn('aria-current="page">Archive</a>', archive_html)
            self.assertIn("Search index JSON", archive_html)
            self.assertNotIn("Open search index JSON", archive_html)
            self.assertIn("data-archive-filter-controls hidden", archive_html)
            self.assertIn("cryptopulse-archive-reader.css", archive_html)
            self.assertIn("cryptopulse-archive-reader.js", archive_html)
            self.assertTrue((root / "_site" / "assets" / archive_reader.STYLE_NAME).exists())
            self.assertTrue((root / "_site" / "assets" / archive_reader.SCRIPT_NAME).exists())

            self.assertIn("Most recent available", report_html)
            self.assertIn('href="../../../../temporal.html"', report_html)
            self.assertIn('href="../../../../archive/index.html"', report_html)

    def test_navigation_omits_temporal_link_when_same_commit_temporal_page_is_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare(root, temporal=False)
            base = base_for(root, [retained_report()])

            archive_reader.apply(base)

            for path in (root / "_site").glob("**/*.html"):
                html = path.read_text(encoding="utf-8")
                self.assertNotIn("Temporal evidence", html)

    def test_no_javascript_baseline_keeps_all_archive_cards_in_markup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepare(root, temporal=True)
            base = base_for(root, [retained_report()])

            archive_reader.apply(base)

            html = (root / "_site" / "archive" / "index.html").read_text(
                encoding="utf-8"
            )
            self.assertIn(">Report</article>", html)
            self.assertIn("Archive filters are optional", html)
            self.assertIn('hidden aria-label="Archive reader filters"', html)


if __name__ == "__main__":
    unittest.main()
