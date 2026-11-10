from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from site_generator import reader_evidence

CONTEXT = {
    "repository_context": {"commit_sha": "1" * 40, "tree_sha": "2" * 40},
    "canonical_report_chronology": ["2026-07-08T10:31:48Z"],
    "latest_report": {
        "title": "Crypto market evidence snapshot — 8 July 2026, 20:31 AEST",
        "headline": "Archived report headline",
        "timestamp": "2026-07-08 20:31 AEST",
        "url": "archive/2026/07/08/2031_AEST.html",
        "source_snapshot": "data/crypto/hourly/2026/07/08/2031_AEST_source_snapshot.json",
        "generation": "Deterministic archived report",
        "citation_count": 0,
    },
    "current_observation": {
        "identity": {
            "path": "data/crypto/hourly/2026/08/21/1549_AEST_source_snapshot.json",
            "sha256": "3" * 64,
            "generated_at_utc": "2026-08-21T05:49:38Z",
            "observation_hour_utc": "2026-08-21T05:00:00Z",
        },
        "assets": [
            {"symbol": "BTC", "price_usd": 75199, "change_1h_pct": 0.5, "change_24h_pct": 8.4},
            {"symbol": "ETH", "price_usd": 2352.5, "change_1h_pct": 0.3, "change_24h_pct": 4.6},
            {"symbol": "SOL", "price_usd": 90.17, "change_1h_pct": 0.2, "change_24h_pct": 5.8},
        ],
        "quality_status": "valid-ok",
        "required_sources": ["coingecko", "defillama"],
        "disabled_sources": ["binance"],
        "source_status": {"coingecko": "ok", "defillama": "ok", "binance": "skipped"},
        "generated_at_local": "2026-08-21T15:49:38+10:00",
        "timezone_abbreviation": "AEST",
        "resolution_status": "predecessor-missing",
    },
    "report_observation_relation": "different-evidence-objects",
}

HOME = """<!doctype html><html><head><title>Home</title></head><body>
<section class="demo-banner"><div class="demo-banner-title">Demo site — AI-generated content</div><p>Reports on this site are AI-created examples used to show what automated market-report publishing could look like. They may be inaccurate, incomplete, outdated, or misleading. Do not use them for trading or investment decisions.</p></section>
<nav class="site-nav"><a href="latest.html">Latest Report</a></nav>
<header class="hero landing-hero product-hero"><h1>Demo</h1><div class="badges"><span>Demo</span><span>AI-generated</span><span>Not for trading</span></div><div class="hero-actions"><a href="archive/report.html">Open latest report</a></div></header>
<section class="latest-market-read"><p>Heuristic report summary</p></section>
<section class="latest-feature"><p>Old latest report feature</p></section>
<section class="stats-grid"><article><div class="eyebrow">Latest report</div></article><article><div class="eyebrow">Latest headline</div></article></section>
<footer class="footer">Footer</footer></body></html>"""

LATEST = """<!doctype html><html><head><title>Old archived report | CryptoPulse Demo</title></head><body>
<section class="demo-banner"><div class="demo-banner-title">Demo site — AI-generated content</div><p>Reports on this site are AI-created examples used to show what automated market-report publishing could look like. They may be inaccurate, incomplete, outdated, or misleading. Do not use them for trading or investment decisions.</p></section>
<nav class="site-nav"><a href="latest.html">Latest Report</a></nav>
<header class="hero report-hero"><div class="brandline">CP</div><h1>Old report title</h1><p>2026-07-08 20:31 AEST</p><div class="badges"><span>Demo</span><span>AI-generated</span><span>Not for trading</span></div></header>
<section class="report-provenance-lead"><h2>What generated this page</h2></section>
<section class="content report-content">Archived body</section>
<footer class="footer">Footer</footer></body></html>"""


class Phase16ReaderEvidenceSiteIntegrationTests(unittest.TestCase):
    def test_home_replaces_conflicting_summary_and_leads_market_claims_with_safety(self) -> None:
        transformed = reader_evidence.transform_home(HOME, CONTEXT)
        self.assertNotIn("Heuristic report summary", transformed)
        self.assertNotIn("Old latest report feature", transformed)
        self.assertIn(">Most recent</a>", transformed)
        self.assertIn('href="latest.html">Most recent</a>', transformed)
        self.assertIn("Most recent archived report", transformed)
        self.assertIn("Archived report headline", transformed)
        self.assertIn("US$75,199.00", transformed)
        self.assertLess(transformed.index("CryptoPulse is a prototype demonstration"), transformed.index("US$75,199.00"))
        self.assertIn("different evidence objects", transformed)
        self.assertIn("cryptopulse-reader-evidence.css", transformed)
        self.assertNotIn("Reports on this site are AI-created examples", transformed)
        self.assertIn("Repository evidence</span>", transformed)
        self.assertNotIn("live market data", transformed.lower().replace("not live market data", ""))

    def test_latest_keeps_archived_report_below_separate_reader_authority(self) -> None:
        transformed = reader_evidence.transform_latest(LATEST, CONTEXT)
        self.assertIn("<title>Most recent available market evidence | CryptoPulse Demo</title>", transformed)
        self.assertIn("<h1>Most recent available market evidence</h1>", transformed)
        self.assertIn("US$75,199.00", transformed)
        self.assertIn("Most recent archived report", transformed)
        self.assertIn("Archived body", transformed)
        self.assertLess(transformed.index("reader-evidence"), transformed.index("report-provenance-lead"))
        self.assertLess(transformed.index("CryptoPulse is a prototype demonstration"), transformed.index("US$75,199.00"))
        self.assertIn("No embedded report citation list", transformed)
        self.assertIn("data/crypto/hourly/2026/07/08/2031_AEST_source_snapshot.json", transformed)

    def test_unexpected_surface_structure_fails_instead_of_half_updating(self) -> None:
        with self.assertRaises(reader_evidence.ReaderEvidenceIntegrationError):
            reader_evidence.transform_home("<html><head></head><body></body></html>", CONTEXT)
        with self.assertRaises(reader_evidence.ReaderEvidenceIntegrationError):
            reader_evidence.transform_latest("<html><head></head><body></body></html>", CONTEXT)

    def test_apply_uses_one_shared_context_for_home_and_latest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "_site"
            assets = root / "site" / "assets"
            out.mkdir()
            assets.mkdir(parents=True)
            (out / "index.html").write_text(HOME, encoding="utf-8")
            (out / "latest.html").write_text(LATEST, encoding="utf-8")
            (assets / reader_evidence.STYLE_NAME).write_text(".reader-evidence{}\n", encoding="utf-8")
            base = SimpleNamespace(ROOT=root, OUT=out, SITE_SRC=root / "site")
            with mock.patch.object(reader_evidence, "build_reader_evidence_context", return_value=CONTEXT) as build_context:
                reader_evidence.apply(base)
            build_context.assert_called_once_with(base)
            self.assertIn("US$75,199.00", (out / "index.html").read_text(encoding="utf-8"))
            self.assertIn("US$75,199.00", (out / "latest.html").read_text(encoding="utf-8"))
            self.assertTrue((out / "assets" / reader_evidence.STYLE_NAME).exists())


if __name__ == "__main__":
    unittest.main()
