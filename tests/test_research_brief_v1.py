from __future__ import annotations
import json
import sys
import unittest
from unittest.mock import patch
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from research_brief_v1 import research_brief, number, evidence
from generate_crypto_report import render_report

PATH = ROOT / "data/crypto/hourly/2026/11/08/0807_AEDT_source_snapshot.json"


class ResearchBriefTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = json.loads(PATH.read_text())
        self.quality = self.snapshot["quality"]

    def test_actual_archived_snapshot_findings_and_evidence(self):
        text = research_brief(self.snapshot, PATH, self.quality)
        self.assertIn("Seven-day relative movement", text)
        self.assertIn("-4.63 percentage points", text)
        self.assertIn("-5.94 percentage points", text)
        self.assertIn("Cross-source price check", text)
        self.assertIn("SHA-256", text)
        self.assertIn("Archived interval comparison", text)

    def test_report_leads_with_findings_before_technical_tables(self):
        body = render_report(self.snapshot, PATH, self.quality)
        self.assertLess(body.index("## Evidence-backed findings"), body.index("## Snapshot at a glance"))
        self.assertLess(body.index("## Evidence-backed findings"), body.index("## Market summary"))
        self.assertIn("blob/", body)

    def test_changed_in_memory_exchange_cannot_borrow_archived_source_identity(self):
        snapshot = deepcopy(self.snapshot)
        for row in snapshot["exchange_crosscheck"]["sources"]["coinbase_exchange"]:
            row["source_time"] = "2026-10-01T00:00:00Z"
        text = research_brief(snapshot, PATH, self.quality)
        self.assertIn("immutable public link unavailable", text)
        self.assertNotIn("**Cross-source price check:**", text)
        self.assertIn("No qualifying finding", text)

    def test_stale_market_refused(self):
        snapshot = deepcopy(self.snapshot)
        for row in snapshot["market"]["assets"]:
            row["last_updated"] = "2026-10-01T00:00:00Z"
        text = research_brief(snapshot, PATH, self.quality)
        self.assertNotIn("Seven-day relative movement", text)

    def test_untracked_snapshot_has_no_unpinned_claims(self):
        text = research_brief(self.snapshot, Path("/tmp/absent597.json"), self.quality)
        self.assertIn("immutable public link unavailable", text)
        self.assertIn("No qualifying finding", text)

    def test_nonfinite_rejected(self):
        self.assertIsNone(number("nan"))
        self.assertIsNone(number("inf"))

    def test_modified_local_bytes_not_accepted_as_committed_evidence(self):
        with patch.object(Path, "read_bytes", return_value=b"uncommitted changes"):
            self.assertIsNone(evidence(PATH))

    def test_current_stale_asset_excluded_from_historical_comparison(self):
        snapshot = deepcopy(self.snapshot)
        for asset in snapshot["market"]["assets"]:
            asset["last_updated"] = "2026-10-01T00:00:00Z"
        text = research_brief(snapshot, PATH, self.quality)
        self.assertNotIn("Archived interval comparison", text)

    def test_changed_in_memory_over_threshold_cannot_borrow_source_identity(self):
        snapshot = deepcopy(self.snapshot)
        rows = snapshot["exchange_crosscheck"]["sources"]["coinbase_exchange"]
        rows[0]["price"] = float(rows[0]["price"]) * 1.5
        text = research_brief(snapshot, PATH, self.quality)
        self.assertIn("immutable public link unavailable", text)
        self.assertNotIn("**Cross-source price check:**", text)
