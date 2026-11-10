"""Source-bound editorial Slice 1: producer, archive renderer, and Phase 16 boundary."""
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
from site_generator import report_provenance

REAL_REPORT = ROOT / "reports/crypto/hourly/2026/11/09/2107_AEDT.md"
REAL_SOURCE = ROOT / "data/crypto/hourly/2026/11/09/2107_AEDT_source_snapshot.json"
FIXTURE_SOURCE = ROOT / "data/crypto/hourly/2026/11/08/0807_AEDT_source_snapshot.json"


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True).stdout.strip()


class EditorialSliceOneTests(unittest.TestCase):
    def fixture(self, snapshot: dict):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        path = root / "data/crypto/hourly/2026/11/08/0807_AEDT_source_snapshot.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(snapshot, sort_keys=True), encoding="utf-8")
        git(root, "init", "-q")
        git(root, "config", "user.name", "Offline Fixture")
        git(root, "config", "user.email", "fixture@example.invalid")
        git(root, "add", ".")
        git(root, "commit", "-qm", "Pin isolated synthetic evidence")
        return root, path

    def test_real_november_report_is_immutable_and_accepted_claims_are_bounded(self):
        raw = REAL_REPORT.read_bytes()
        original = subprocess.run(
            ["git", "show", "HEAD:reports/crypto/hourly/2026/11/09/2107_AEDT.md"],
            cwd=ROOT, check=True, capture_output=True,
        ).stdout
        self.assertEqual(raw, original)
        self.assertEqual(hashlib.sha256(raw).hexdigest(), hashlib.sha256(original).hexdigest())

        snap = json.loads(REAL_SOURCE.read_text())
        result = producer.assess(snap, REAL_SOURCE, snap["quality"])["projection"]
        self.assertEqual(result["article_state"], "finding")
        self.assertIn("archived_interval", [c["kind"] for c in result["claims"]])
        self.assertIn("cross_source", [c["kind"] for c in result["claims"]])
        self.assertNotIn("eth_btc_24h", [c["kind"] for c in result["claims"]])
        self.assertEqual(result["source"]["sha256"], hashlib.sha256(REAL_SOURCE.read_bytes()).hexdigest())
        self.assertEqual(len(result["source"]["commit"]), 40)

    def test_offline_committed_stale_optional_crosscheck_preserves_independent_finding(self):
        snapshot = json.loads(FIXTURE_SOURCE.read_text())
        selected = snapshot["exchange_crosscheck"]["selected"]
        self.assertTrue(selected)
        for row in snapshot["exchange_crosscheck"]["sources"][selected]:
            row["source_time"] = "2026-10-01T00:00:00Z"
        root, path = self.fixture(snapshot)
        with patch.object(producer, "ROOT", root):
            result = producer.assess(snapshot, path, snapshot["quality"])["projection"]
        self.assertEqual(result["article_state"], "finding")
        self.assertEqual(snapshot["quality"]["status"], "valid-ok")
        self.assertEqual(result["source"]["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertTrue(result["source"]["url"].startswith("fixture://"))
        self.assertEqual(result["source"]["commit"], git(root, "rev-parse", "HEAD"))
        self.assertEqual(next(c["status"] for c in result["candidates"] if c["kind"] == "cross_source"), "rejected")
        self.assertTrue(any(c["kind"] == "seven_day_relative" for c in result["claims"]))
        self.assertFalse(any(c["kind"] == "cross_source" for c in result["claims"]))
        market = next(c for c in result["claims"] if c["category"] == "market")
        self.assertIn("Cross-source price check", " ".join(market["caveats"]))

    def test_offline_committed_no_material_market_finding_is_factual_update(self):
        snapshot = json.loads(FIXTURE_SOURCE.read_text())
        assets = {a["symbol"]: a for a in snapshot["market"]["assets"]}
        assets["SOL"]["change_7d_pct"] = assets["BTC"]["change_7d_pct"]
        root, path = self.fixture(snapshot)
        with patch.object(producer, "ROOT", root):
            result = producer.assess(snapshot, path, snapshot["quality"])["projection"]
        self.assertEqual(result["article_state"], "factual_update")
        self.assertEqual(result["source"]["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertFalse(any(c["category"] == "market" for c in result["claims"]))
        self.assertIn("no qualifying market finding", result["headline"])
        self.assertNotIn("market discovery", result["headline"])

    def test_forged_essential_source_is_inconclusive_not_published_as_finding(self):
        snapshot = json.loads(FIXTURE_SOURCE.read_text())
        root, path = self.fixture(snapshot)
        edited = deepcopy(snapshot)
        edited["market"]["assets"][0]["price_usd"] = 123.456
        with patch.object(producer, "ROOT", root):
            result = producer.assess(edited, path, edited["quality"])["projection"]
            missing = producer.assess(snapshot, root / "absent.json", snapshot["quality"])["projection"]
        for value in (result, missing):
            self.assertEqual(value["article_state"], "inconclusive")
            self.assertEqual(value["claims"], [])
            self.assertIsNone(value["source"])

    def test_report_has_one_projection_and_consistent_markdown(self):
        snapshot = json.loads(REAL_SOURCE.read_text())
        raw = render_report(snapshot, REAL_SOURCE, snapshot["quality"])
        metadata, markdown_body = pages.split_front_matter(raw)
        article = metadata["editorial_article"]
        self.assertEqual(metadata["schema_version"], "deterministic-crypto-report/v1")
        self.assertIs(metadata["llm_generated"], False)
        self.assertEqual(metadata["source_snapshot"], article["source"]["path"])
        self.assertEqual(metadata["generated_at_utc"], article["as_of_utc"])
        self.assertEqual(metadata["quality_status"], article["quality_status"])
        self.assertIn("**Archived interval comparison:**", markdown_body)
        self.assertIn(article["source"]["sha256"], markdown_body)
        self.assertTrue(50 <= len(article["summary"].split()) <= 100)

    def test_canonical_archive_orders_article_before_audit_and_latest_is_not_rewritten(self):
        snapshot = json.loads(REAL_SOURCE.read_text())
        metadata, _ = pages.split_front_matter(render_report(snapshot, REAL_SOURCE, snapshot["quality"]))
        archived = next(r for r in pages.collect_reports() if r.source_path == REAL_REPORT)
        typed = replace(archived, metadata=metadata)
        article_html = pages.html_page(typed, "../../../../", archive_article=True)
        transformed = report_provenance.transform_report_html(article_html)
        self.assertIn("archived JSON", transformed)
        self.assertIn("archived_interval", str(metadata["editorial_article"]))
        self.assertLess(transformed.index("editorial-demo-warning"), transformed.index("editorial-article"))
        self.assertLess(transformed.index('id="editorial-headline"'), transformed.index('class="editorial-audit"'))
        self.assertLess(transformed.index("editorial-article"), transformed.index("report-provenance-lead"))
        self.assertIn(metadata["editorial_article"]["source"]["url"], transformed)
        self.assertIn("Full original", transformed) if "Full original" in transformed else self.assertIn("Original archived report", transformed)
        latest = pages.html_page(typed, "")
        self.assertNotIn('class="editorial-article"', latest)
        self.assertIn('class="report-warning compact-warning"', latest)
        historic = pages.html_page(archived, "../../../../", archive_article=True)
        self.assertIn("Original archived publication", historic)
        self.assertNotIn('id="editorial-headline"', historic)
        self.assertIn('class="editorial-audit" open', historic)
        self.assertIn("2107_AEDT", historic)

    def test_typed_projection_rejects_mismatch_and_escapes_user_fields(self):
        snapshot = json.loads(REAL_SOURCE.read_text())
        metadata, _ = pages.split_front_matter(render_report(snapshot, REAL_SOURCE, snapshot["quality"]))
        archived = next(r for r in pages.collect_reports() if r.source_path == REAL_REPORT)
        altered = deepcopy(metadata)
        altered["editorial_article"]["source"]["sha256"] = "0" * 64
        with self.assertRaises(pages.EditorialArticleError):
            pages.html_page(replace(archived, metadata=altered), "../../../../", archive_article=True)
        altered = deepcopy(metadata)
        altered["source_snapshot"] = "data/crypto/hourly/2026/11/08/0807_AEDT_source_snapshot.json"
        with self.assertRaises(pages.EditorialArticleError):
            pages.html_page(replace(archived, metadata=altered), "../../../../", archive_article=True)
        altered = deepcopy(metadata)
        altered["editorial_article"]["article_state"] = "factual_update"
        with self.assertRaises(pages.EditorialArticleError):
            pages.html_page(replace(archived, metadata=altered), "../../../../", archive_article=True)
        altered = deepcopy(metadata)
        altered["editorial_article"]["headline"] = '<script>alert("bad")</script>'
        html = pages.html_page(replace(archived, metadata=altered), "../../../../", archive_article=True)
        self.assertNotIn("<script>alert", html)
        self.assertIn("&lt;script&gt;", html)


if __name__ == "__main__":
    unittest.main()
