"""G3 editorial projection: verified typed copy, faithful legacy and site order."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from copy import deepcopy
from dataclasses import replace
from html import unescape
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_pages_site as pages
from generate_crypto_report import render_report
from site_generator import archive_cards, archive_reader, reader_evidence

REAL_REPORT = ROOT / "reports/crypto/hourly/2026/11/09/2107_AEDT.md"
REAL_SOURCE = ROOT / "data/crypto/hourly/2026/11/09/2107_AEDT_source_snapshot.json"


class SitewideEditorialG3Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.archived = next(r for r in pages.collect_reports() if r.source_path == REAL_REPORT)
        cls.legacy = replace(
            cls.archived,
            metadata={key: value for key, value in cls.archived.metadata.items()
                      if key != "editorial_article"},
        )
        cls.newer_untyped = replace(
            cls.legacy,
            title="Controlled newer untyped report",
            timestamp="2026-11-21 16:07 AEDT",
            sort_key="2026-11-21T05:07:00Z",
            url="archive/2026/11/21/1607_AEDT.html",
        )
        source = json.loads(REAL_SOURCE.read_text(encoding="utf-8"))
        metadata, _ = pages.split_front_matter(render_report(source, REAL_SOURCE, source["quality"]))
        cls.typed = replace(cls.legacy, metadata=metadata)
        cls.article = pages.validated_editorial_article(cls.typed)

    def test_qualifying_typed_finding_leads_over_newer_untyped_archive(self):
        self.assertGreater(self.newer_untyped.sort_key, self.typed.sort_key)
        homepage = archive_cards.homepage_lead([self.newer_untyped, self.typed], pages)
        self.assertIn(archive_cards.EDITORIAL_STATES["finding"], homepage)
        self.assertIn(self.article["headline"], unescape(homepage))
        self.assertIn(self.article["summary"], unescape(homepage))
        uncertainty = next(c["uncertainty"] for c in self.article["claims"] if c["category"] == "market")
        self.assertIn(uncertainty, unescape(homepage))
        self.assertIn(f'href="{self.typed.url}"', homepage)
        self.assertIn(f'href="{self.typed.url}#supporting-evidence"', homepage)
        self.assertIn(f'href="{self.typed.url}#technical-record"', homepage)
        self.assertIn(self.typed.timestamp, homepage)
        self.assertIn("static archive, not live or continuously updated", homepage)
        self.assertNotIn(self.newer_untyped.title, homepage)

    def test_legacy_only_archive_has_explicitly_qualified_lead(self):
        self.assertNotIn("editorial_article", self.legacy.metadata)
        homepage = pages.homepage_editorial_lead([self.legacy])
        self.assertIn("Original archival observation", homepage)
        self.assertIn(self.legacy.title, homepage)
        self.assertIn(self.legacy.url, homepage)
        self.assertIn("not a new validated editorial finding", homepage)
        self.assertIn("No retained report has a qualifying typed", homepage)
        self.assertLess(homepage.index("homepage-lead-heading"), homepage.index("homepage-lead-actions"))
        # Existing report wording is quoted without a new deterministic assessment.
        excerpt = archive_cards.original_observation_excerpt(self.legacy)
        self.assertTrue(excerpt)
        self.assertIn(excerpt, unescape(homepage))

    def test_legacy_lead_uses_original_market_interval_not_diagnostic(self):
        # Real archival item 1 is an assurance check; item 2 is a bounded
        # historical market observation carrying its own limitation.
        excerpt = archive_cards.original_observation_excerpt(self.archived)
        self.assertTrue(excerpt.startswith("Archived interval comparison:"))
        self.assertIn("spot-price change over 1.00 h", excerpt)
        self.assertIn("This is a two-point observation, not evidence of a sustained trend.", excerpt)
        self.assertIn("Test with subsequent aligned hours.", excerpt)
        self.assertNotIn("Cross-source price check", excerpt)
        html = archive_cards.homepage_lead([self.archived], pages)
        self.assertIn(excerpt, unescape(html))
        self.assertNotIn("Cross-source price check:", html)
        self.assertIn("Original archival observation", html)

    def test_legacy_without_bounded_market_observation_uses_neutral_overview(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "report.md"
            path.write_text(
                "## Evidence-backed findings\n\n"
                "1. **Cross-source price check:** accepted within tolerance.\n"
                "### Evidence boundaries\n\nPoint-in-time only.\n",
                encoding="utf-8",
            )
            legacy = replace(self.archived, source_path=path)
            self.assertEqual(archive_cards.original_observation_excerpt(legacy), "")
            html = archive_cards.homepage_lead([legacy], pages)
            self.assertIn("without an unsupported retrospective research summary", html)
            self.assertNotIn("Cross-source price check:", html)

    def test_older_typed_finding_does_not_claim_to_be_newest_typed_report(self):
        # Synthetic precedence case: separate canonical-validator tests cover
        # actual source admission, while this case checks truthful copy.
        newer = self.newer_untyped
        self.assertNotEqual(newer.url, self.typed.url)
        factual = deepcopy(self.article)
        factual["article_state"] = "factual_update"
        factual["headline"] = "Factual update without a qualifying market finding"
        factual["claims"] = []
        newer = replace(newer, metadata={**newer.metadata, "editorial_article": factual})
        stub = SimpleNamespace(validated_editorial_article=lambda r: r.metadata["editorial_article"])
        html = archive_cards.homepage_lead([newer, self.typed], stub)
        self.assertIn(f'href="{self.typed.url}"', html)
        self.assertIn("Most recent validated typed finding, prioritised over factual updates", html)
        self.assertIn("Newer retained reports may exist.", html)
        self.assertNotIn("most recent qualifying typed publication", html)
        just_factual = archive_cards.homepage_lead([newer], stub)
        self.assertIn(f'href="{newer.url}"', just_factual)
        self.assertIn("most recent validated typed factual update", just_factual)
        self.assertIn("No validated typed finding is available.", just_factual)

    def test_typed_archive_entry_uses_same_validated_article_contract(self):
        cards = archive_cards.recent_report_cards([self.typed], pages)
        self.assertIn(self.article["headline"], unescape(cards))
        self.assertIn(self.article["summary"], unescape(cards))
        self.assertIn("Source-bounded finding", cards)
        self.assertIn("Validated source evidence", cards)
        self.assertIn(f'href="{self.typed.url}"', cards)
        self.assertNotIn("<script>", cards)

    def test_legacy_archive_keeps_original_title_and_no_retrospective_summary(self):
        item = self.legacy
        cards = archive_cards.recent_report_cards([item], pages)
        self.assertIn(item.title, unescape(cards))
        self.assertIn("Original deterministic publication", cards)
        self.assertNotIn("archive-entry-summary", cards)
        self.assertIn("Validated source evidence", cards)
        self.assertNotIn("Source-bounded finding", cards)
        self.assertNotIn("Fresh analysis", cards)

    def test_freshly_generated_typed_report_coexists_with_legacy_in_archive(self):
        # Exercise the actual report parser and Pages builder with a generated
        # typed report alongside an unchanged earlier archival report. The
        # disposable archive is isolated from the checked-in production files.
        source = json.loads(REAL_SOURCE.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            archive = Path(tmp) / "reports/crypto/hourly"
            legacy_path = archive / "2026/11/09/2007_AEDT.md"
            typed_path = archive / "2026/11/09/2107_AEDT.md"
            legacy_path.parent.mkdir(parents=True)
            legacy_path.write_bytes(REAL_REPORT.with_name("2007_AEDT.md").read_bytes())
            typed_path.write_text(
                render_report(source, REAL_SOURCE, source["quality"]), encoding="utf-8"
            )
            with patch.object(pages, "REPORTS_DIR", archive), patch.object(
                pages, "DAILY_REPORTS_DIR_NAME", (Path(tmp).name, "reports", "crypto", "daily")
            ), patch.object(pages, "OUT", Path(tmp) / "_site"):
                reports = pages.collect_reports()
                self.assertEqual(len(reports), 2)
                typed, legacy = reports
                self.assertIn("editorial_article", typed.metadata)
                self.assertNotIn("editorial_article", legacy.metadata)
                self.assertEqual(pages.validated_editorial_article(typed)["headline"],
                                 self.article["headline"])
                pages.build()
                home = (pages.OUT / "index.html").read_text(encoding="utf-8")
                self.assertIn(self.article["headline"], unescape(home))
                cards = archive_cards.recent_report_cards(reports, pages)
                self.assertIn("Source-bounded finding", cards)
                self.assertIn("Original deterministic publication", cards)
                self.assertIn(legacy.title, unescape(cards))
                self.assertIn("editorial_article", pages.report_to_manifest(typed)["metadata"])
                self.assertNotIn("editorial_article", pages.report_to_manifest(legacy)["metadata"])
                self.assertTrue((pages.OUT / "manifest.json").is_file())
                self.assertTrue((pages.OUT / "archive/index.html").is_file())

    def test_material_quality_limitation_and_no_finding_states_are_visible(self):
        altered = deepcopy(self.article)
        altered["article_state"] = "factual_update"
        altered["claims"] = []
        altered["headline"] = "No qualifying market finding"
        altered["summary"] = "No new market conclusion is supported. " * 10
        altered["caveats"] = ["Optional venue observation stale; comparison excluded."]
        stub = SimpleNamespace(validated_editorial_article=lambda report: report.metadata["editorial_article"])
        report = replace(self.typed, metadata={**self.typed.metadata, "editorial_article": altered})
        text = archive_cards.recent_report_cards([report], stub)
        self.assertIn("Factual update", text)
        self.assertIn("Optional venue observation stale; comparison excluded.", text)
        self.assertNotIn("Source-bounded finding", text)
        altered = deepcopy(altered)
        altered["article_state"] = "inconclusive"
        report = replace(report, metadata={**report.metadata, "editorial_article": altered})
        self.assertIn("Inconclusive evidence", archive_cards.recent_report_cards([report], stub))

    def test_forged_typed_source_fails_closed_across_home_and_archive(self):
        metadata = deepcopy(self.typed.metadata)
        metadata["editorial_article"]["source"]["sha256"] = "0" * 64
        invalid = replace(self.typed, metadata=metadata)
        with self.assertRaises(pages.EditorialArticleError):
            archive_cards.homepage_lead([invalid], pages)
        with self.assertRaises(pages.EditorialArticleError):
            archive_cards.grouped_archive([invalid], pages)

    def test_home_reader_authority_is_secondary_to_explicit_editorial_lead(self):
        from test_phase16_reader_evidence_site_integration import HOME, CONTEXT
        lead = (
            '<section class="homepage-editorial-lead" aria-labelledby="homepage-lead-heading">'
            '<h2 id="homepage-lead-heading">Verified original report</h2></section>'
        )
        html = HOME.replace('<section class="latest-market-read">', lead + '<section class="latest-market-read">', 1)
        transformed = reader_evidence.transform_home(html, CONTEXT)
        self.assertLess(transformed.index('id="homepage-lead-heading"'), transformed.index('data-reader-surface="home"'))
        self.assertLess(transformed.index('data-reader-surface="home"'), transformed.index('class="stats-grid"'))
        self.assertEqual(transformed.count('data-reader-surface="home"'), 1)
        self.assertLess(transformed.index("prototype demonstration"), transformed.index('id="homepage-lead-heading"'))

    def test_upfront_demo_notice_is_compact_not_duplicated(self):
        text = reader_evidence._reader_demo_framing(pages.demo_banner())
        self.assertEqual(text.count("CryptoPulse is a prototype demonstration"), 1)
        self.assertIn("Do not use this site for trading", text)

    def test_navigation_and_metadata_preserve_history_and_no_advice(self):
        nav = archive_reader._reader_nav(pages, "../../../../", "", True)
        for href in ("index.html", "latest.html", "archive/index.html", "search.html",
                     "index.html#about", "methodology.html", "temporal.html"):
            self.assertIn(href, nav)
        self.assertEqual(nav.count('aria-label="Primary navigation"'), 1)
        self.assertIn('aria-current="page"', archive_reader._reader_nav(pages, "", "archive", True))
        feed = pages.rss_feed([self.legacy])
        manifest = pages.report_to_manifest(self.legacy)
        self.assertIn("Not financial advice", feed)
        self.assertIn("not be used for trading", manifest["disclaimer"])
        self.assertEqual(manifest["source"], self.legacy.source_rel)
        self.assertEqual(manifest["url"], self.legacy.url)
        self.assertNotIn("editorial_article", manifest["metadata"])

    def test_styles_scope_mobile_focus_and_wide_tables_without_new_framework(self):
        css = (ROOT / "site/assets/cryptopulse.css").read_text(encoding="utf-8")
        for token in (".homepage-editorial-lead", "max-width: 780px",
                      ".archive-entry-summary", ".site-nav a:focus-visible",
                      ".editorial-audit .report-body", "overflow-x: auto",
                      "@media (max-width: 720px)"):
            self.assertIn(token, css)


if __name__ == "__main__":
    unittest.main()
