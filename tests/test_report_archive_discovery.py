from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_pages_site
from generate_crypto_report import generate_report

CONFIG = ROOT / "config" / "crypto_sources.yml"
REAL_PR89_SNAPSHOT = ROOT / "data" / "crypto" / "hourly" / "2026" / "07" / "08" / "1742_AEST_source_snapshot.json"


class DeterministicReportArchiveDiscoveryTests(unittest.TestCase):
    def test_generated_report_is_discovered_by_archive_flow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            output_path = generate_report(REAL_PR89_SNAPSHOT, tmp_root / "reports" / "crypto", CONFIG)

            original_root = build_pages_site.ROOT
            original_reports_dir = build_pages_site.REPORTS_DIR
            original_out = build_pages_site.OUT
            try:
                build_pages_site.ROOT = tmp_root
                build_pages_site.REPORTS_DIR = tmp_root / "reports" / "crypto" / "hourly"
                build_pages_site.OUT = tmp_root / "_site"
                reports = build_pages_site.collect_reports()
            finally:
                build_pages_site.ROOT = original_root
                build_pages_site.REPORTS_DIR = original_reports_dir
                build_pages_site.OUT = original_out

            self.assertEqual(output_path.relative_to(tmp_root).as_posix(), "reports/crypto/hourly/2026/07/08/1742_AEST.md")
            self.assertEqual(len(reports), 1)
            report = reports[0]
            self.assertEqual(report.source_rel, "reports/crypto/hourly/2026/07/08/1742_AEST.md")
            self.assertEqual(report.url, "archive/2026/07/08/1742_AEST.html")
            self.assertEqual(report.output_path.relative_to(tmp_root).as_posix(), "_site/archive/2026/07/08/1742_AEST.html")
            self.assertIn("Crypto market evidence snapshot", report.title)
            self.assertFalse((tmp_root / "_site").exists())


if __name__ == "__main__":
    unittest.main()
