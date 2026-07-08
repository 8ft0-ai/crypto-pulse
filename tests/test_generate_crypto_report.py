from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from generate_crypto_report import generate_report
from validate_crypto_snapshot import ValidationError

FIXTURES = ROOT / "tests" / "fixtures"
CONFIG = ROOT / "config" / "crypto_sources.yml"


class DeterministicCryptoReportGeneratorTests(unittest.TestCase):
    def test_generates_report_from_valid_ok_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_root = Path(tmp)
            snapshot_path = tmp_root / "data" / "crypto" / "hourly" / "2026" / "07" / "08" / "1434_AEST_source_snapshot.json"
            snapshot_path.parent.mkdir(parents=True)
            shutil.copyfile(FIXTURES / "valid_ok_snapshot.json", snapshot_path)

            output_path = generate_report(snapshot_path, tmp_root / "reports" / "crypto", CONFIG)
            self.assertEqual(output_path.relative_to(tmp_root).as_posix(), "reports/crypto/2026/07/08/1434_AEST.md")
            body = output_path.read_text(encoding="utf-8")

        self.assertIn("schema_version: \"deterministic-crypto-report/v1\"", body)
        self.assertIn("quality_status: \"valid-ok\"", body)
        self.assertIn("source_snapshot:", body)
        self.assertIn("## Product boundary and non-investment-advice notice", body)
        self.assertIn("## Snapshot quality", body)
        self.assertIn("## Market summary", body)
        self.assertIn("## DeFi and stablecoin summary", body)
        self.assertIn("## Exchange cross-check summary", body)
        self.assertIn("## Evidence and source status", body)
        self.assertIn("## Scope limitations", body)
        self.assertIn("not financial advice", body)
        self.assertIn("llm_generated: false", body)

    def test_invalid_snapshot_fails_without_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValidationError):
                generate_report(FIXTURES / "invalid_missing_required_source.json", Path(tmp), CONFIG)
            self.assertEqual(list(Path(tmp).rglob("*.md")), [])

    def test_degraded_snapshot_includes_warnings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_path = generate_report(FIXTURES / "valid_degraded_optional_source_warning.json", Path(tmp), CONFIG)
            body = output_path.read_text(encoding="utf-8")

        self.assertIn("quality_status: \"valid-degraded\"", body)
        self.assertIn("This report is visibly degraded", body)
        self.assertIn("no optional exchange cross-check source succeeded", body)


if __name__ == "__main__":
    unittest.main()
