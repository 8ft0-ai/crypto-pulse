"""Slice 2 G2: exact evidence, locally visible uncertainty, method and audit navigation."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_pages_site as pages
import research_brief_v1 as producer
from generate_crypto_report import render_report
from site_generator import archive_reader, report_provenance

REAL_REPORT = ROOT / "reports/crypto/hourly/2026/11/09/2107_AEDT.md"
REAL_SOURCE = ROOT / "data/crypto/hourly/2026/11/09/2107_AEDT_source_snapshot.json"
FIXTURE_SOURCE = ROOT / "data/crypto/hourly/2026/11/08/0807_AEDT_source_snapshot.json"


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True).stdout.strip()


class EvidenceSliceTwoTests(unittest.TestCase):
    def setUp(self):
        self.archived = next(r for r in pages.collect_reports() if r.source_path == REAL_REPORT)

    def isolated_fixture(self, snapshot: dict) -> tuple[Path, Path]:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        source = root / "data/crypto/hourly/2026/11/08/0807_AEDT_source_snapshot.json"
        source.parent.mkdir(parents=True)
        source.write_text(json.dumps(snapshot, sort_keys=True), encoding="utf-8")
        git(root, "init", "-q")
        git(root, "config", "user.name", "Offline Fixture")
        git(root, "config", "user.email", "fixture@example.invalid")
        git(root, "add", ".")
        git(root, "commit", "-qm", "Pin test-only source bytes")
        return root, source

    def render_fixture(self, snapshot: dict) -> tuple[dict, str]:
        root, source = self.isolated_fixture(snapshot)
        with patch.object(producer, "ROOT", root):
            raw = render_report(snapshot, source, snapshot["quality"])
        metadata, _ = pages.split_front_matter(raw)

        def verify_fixture(reference: dict) -> None:
            self.assertEqual(reference["commit"], git(root, "rev-parse", "HEAD"))
            self.assertEqual(reference["url"], f'fixture://{reference["commit"]}/{reference["path"]}')
            exact = (root / reference["path"]).read_bytes()
            self.assertEqual(hashlib.sha256(exact).hexdigest(), reference["sha256"])
            self.assertEqual(
                subprocess.run(["git", "show", f'{reference["commit"]}:{reference["path"]}'],
                               cwd=root, check=True, capture_output=True).stdout,
                exact,
            )

        with patch.object(pages, "verify_editorial_source", side_effect=verify_fixture):
            html = pages.html_page(replace(self.archived, metadata=metadata),
                                   "../../../../", archive_article=True)
        return metadata, html

    def test_real_source_bound_claim_links_exact_json_and_markdown(self):
        source_bytes = REAL_SOURCE.read_bytes()
        original_bytes = REAL_REPORT.read_bytes()
        self.assertEqual(original_bytes, subprocess.run(
            ["git", "show", "HEAD:reports/crypto/hourly/2026/11/09/2107_AEDT.md"],
            cwd=ROOT, capture_output=True, check=True).stdout)
        snapshot = json.loads(source_bytes)
        metadata, _ = pages.split_front_matter(render_report(snapshot, REAL_SOURCE, snapshot["quality"]))
        article = metadata["editorial_article"]
        self.assertEqual(article["article_state"], "finding")
        typed = replace(self.archived, metadata=metadata)
        html = report_provenance.transform_report_html(pages.html_page(
            typed, "../../../../", archive_article=True))
        self.assertLess(html.index("editorial-demo-warning"), html.index('id="editorial-headline"'))
        self.assertLess(html.index('id="editorial-headline"'), html.index('id="supporting-evidence"'))
        self.assertLess(html.index('id="supporting-evidence"'), html.index('id="technical-record"'))
        self.assertIn("Original archived report, evidence and technical record", html)
        self.assertIn("methodology.html", html)
        self.assertIn("Source assurance (not a market finding)", html)
        self.assertIn("Figures and comparison window", html)
        for claim in article["claims"]:
            for source in claim["sources"]:
                self.assertIn(f'href="{source["url"]}"', html)
                self.assertIn(source["sha256"], html)
                self.assertIn(source["commit"], html)
                self.assertIn(source["path"], html)
        self.assertIn(
            f'blob/{git(ROOT, "rev-parse", "HEAD")}/{self.archived.source_rel}', html)
        self.assertIn("archived Markdown citations", html)
        self.assertEqual(hashlib.sha256(REAL_SOURCE.read_bytes()).hexdigest(),
                         hashlib.sha256(source_bytes).hexdigest())

    def test_rejected_optional_rows_remain_beside_independent_finding(self):
        snap = json.loads(FIXTURE_SOURCE.read_text())
        selected = snap["exchange_crosscheck"]["selected"]
        for item in snap["exchange_crosscheck"]["sources"][selected]:
            item["source_time"] = "2026-10-01T00:00:00Z"
        metadata, html = self.render_fixture(snap)
        article = metadata["editorial_article"]
        self.assertEqual(article["article_state"], "finding")
        self.assertEqual(snap["quality"]["status"], "valid-ok")
        self.assertEqual(next(c["status"] for c in article["candidates"]
                              if c["kind"] == "cross_source"), "rejected")
        self.assertIn("Cross-source price check rejected/inconclusive", html)
        finding = html.index('<article class="editorial-finding">')
        caveat = html.index("Cross-source price check rejected/inconclusive")
        next_test = html.index("<strong>Next test.</strong>")
        self.assertLess(finding, caveat)
        self.assertLess(caveat, next_test)
        self.assertNotIn("Source assurance (not a market finding)", html)
        self.assertIn("fixture://", html)
        self.assertNotIn(f'https://github.com/8ft0-ai/crypto-pulse/blob/{article["source"]["commit"]}/data/', html)
        self.assertIn("report and technical record", html)

        altered = deepcopy(metadata)
        altered["editorial_article"]["claims"][0]["caveats"].clear()
        root, _ = self.isolated_fixture(snap)
        # Independently check the claim-local integrity rule without weakening source checks.
        with patch.object(pages, "verify_editorial_source", lambda source: None):
            with self.assertRaisesRegex(pages.EditorialArticleError, "material caveat"):
                pages.html_page(replace(self.archived, metadata=altered), "../../../../", archive_article=True)

    def test_valid_no_finding_remains_factual_with_inspectable_evidence(self):
        snap = json.loads(FIXTURE_SOURCE.read_text())
        assets = {a["symbol"]: a for a in snap["market"]["assets"]}
        assets["SOL"]["change_7d_pct"] = assets["BTC"]["change_7d_pct"]
        metadata, html = self.render_fixture(snap)
        self.assertEqual(metadata["editorial_article"]["article_state"], "factual_update")
        self.assertNotIn('<article class="editorial-finding">', html)
        self.assertIn("no qualifying market finding", html)
        self.assertIn("Inspect exact primary source JSON", html)
        self.assertIn("fixture://", html)
        self.assertLess(html.index("editorial-summary"), html.index("supporting-evidence"))

    def test_unverifiable_essential_evidence_is_not_a_source_link(self):
        snap = json.loads(FIXTURE_SOURCE.read_text())
        original = deepcopy(snap)
        root, source = self.isolated_fixture(original)
        snap["market"]["assets"][0]["price_usd"] = 123.456
        with patch.object(producer, "ROOT", root):
            raw = render_report(snap, source, snap["quality"])
        metadata, _ = pages.split_front_matter(raw)
        self.assertEqual(metadata["editorial_article"]["article_state"], "inconclusive")
        html = pages.html_page(replace(self.archived, metadata=metadata),
                               "../../../../", archive_article=True)
        self.assertIn("Essential source authority was not established", html)
        self.assertIn("Evidence assessment inconclusive", html)
        self.assertNotIn("fixture://", html)
        self.assertNotIn("Pinned archived JSON", html)

    def test_legacy_archival_fidelity_without_retrospective_finding(self):
        html = pages.html_page(self.archived, "../../../../", archive_article=True)
        self.assertIn("Original archived publication", html)
        self.assertNotIn('id="editorial-headline"', html)
        self.assertIn("historical Markdown", html)
        self.assertIn(f'blob/{git(ROOT, "rev-parse", "HEAD")}/{self.archived.source_rel}', html)
        self.assertIn('class="editorial-audit"', html)
        self.assertIn('id="technical-record"', html)

    def test_original_source_backed_report_has_json_citations_before_closed_audit(self):
        # The real committed report predates the typed editorial_article projection.
        self.assertIs(self.archived.metadata["llm_generated"], False)
        self.assertNotIn("editorial_article", self.archived.metadata)
        original = REAL_REPORT.read_bytes()
        self.assertEqual(original, subprocess.run(
            ["git", "show", "HEAD:reports/crypto/hourly/2026/11/09/2107_AEDT.md"],
            cwd=ROOT, capture_output=True, check=True).stdout)

        links = pages.legacy_report_json_citations(self.archived)
        self.assertEqual(len(links), 2)
        self.assertEqual(links[0][0], "Original report primary snapshot citation")
        self.assertEqual(links[1][0], "Original report comparison/other snapshot citation")

        html = pages.html_page(self.archived, "../../../../", archive_article=True)
        supporting = html.split('<section id="supporting-evidence"', 1)[1].split(
            '<details class="editorial-audit"', 1)[0]
        self.assertIn('aria-label="Original report JSON citations"', supporting)
        self.assertIn("not newly verified typed claims", supporting)
        for label, url, digest in links:
            self.assertIn(f'href="{url}"', supporting)
            self.assertIn(label, supporting)
            self.assertIsNotNone(digest)
            self.assertIn(digest, supporting)
            self.assertTrue(url.startswith("https://github.com/8ft0-ai/crypto-pulse/blob/"))
            self.assertTrue(url.endswith(".json"))
        self.assertIn(self.archived.metadata["source_snapshot"], links[0][1])
        self.assertNotIn("Source-bounded finding", supporting)
        self.assertIn('class="editorial-audit"', html)
        self.assertIn("Archived interval comparison", html)

        # Reports without deterministic source-backed identity cannot inherit these links.
        unbound = replace(self.archived, metadata={**self.archived.metadata, "llm_generated": True})
        unbound_html = pages.html_page(unbound, "../../../../", archive_article=True)
        unbound_support = unbound_html.split('<section id="supporting-evidence"', 1)[1].split(
            '<details class="editorial-audit"', 1)[0]
        self.assertNotIn('aria-label="Original report JSON citations"', unbound_support)

    def test_methodology_is_shared_and_accessible_before_claims(self):
        page = pages.methodology_page()
        self.assertIn("<h1>Methodology and limitations</h1>", page)
        self.assertLess(page.index("Demo site — AI-generated content"), page.index("Source records and observation semantics"))
        for marker in ("Source records and observation semantics", "Deterministic and AI-generated",
                       "Validation, alignment and freshness", "Finding and uncertainty states",
                       "Inspecting provenance and reproducing the record",
                       "Demo and non-advice boundary", "factual update", "inconclusive",
                       "not investment research", "trading signal"):
            self.assertIn(marker.lower(), page.lower())
        self.assertIn('href="methodology.html"', pages.nav())
        self.assertIn('href="methodology.html"', page)
        # Archive reader is the FINAL navigation owner across Home, Latest, Archive and reports.
        nav = archive_reader._reader_nav(pages, "../../../../", "archive", temporal_available=True)
        self.assertIn('href="../../../../methodology.html"', nav)
        self.assertEqual(archive_reader._active_page(pages, pages.OUT / "methodology.html"), "methodology")
        current = archive_reader._reader_nav(pages, "", "methodology", temporal_available=True)
        self.assertIn('href="methodology.html" aria-current="page"', current)


if __name__ == "__main__":
    unittest.main()
