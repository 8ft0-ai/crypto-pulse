from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_crypto_snapshot import ValidationError, load_config, validate_snapshot

FIXTURES = ROOT / "tests" / "fixtures"
CONFIG = load_config(ROOT / "config" / "crypto_sources.yml")


class SnapshotQualityFixtureTests(unittest.TestCase):
    def assert_validates_as(self, filename: str, expected_status: str) -> None:
        quality = validate_snapshot(FIXTURES / filename, CONFIG)
        self.assertEqual(quality["status"], expected_status)

    def assert_rejected(self, filename: str) -> None:
        with self.assertRaises(ValidationError):
            validate_snapshot(FIXTURES / filename, CONFIG)

    def test_valid_ok_snapshot(self) -> None:
        self.assert_validates_as("valid_ok_snapshot.json", "valid-ok")

    def test_optional_source_warning_is_degraded_not_invalid(self) -> None:
        self.assert_validates_as("valid_degraded_optional_source_warning.json", "valid-degraded")

    def test_embedded_quality_status_mismatch_is_invalid(self) -> None:
        payload = json.loads((FIXTURES / "valid_ok_snapshot.json").read_text(encoding="utf-8"))
        payload["quality"]["status"] = "invalid"
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "quality_status_mismatch_source_snapshot.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValidationError, "quality.status"):
                validate_snapshot(path, CONFIG)

    def test_missing_required_source_is_invalid(self) -> None:
        self.assert_rejected("invalid_missing_required_source.json")

    def test_stale_required_source_is_invalid(self) -> None:
        self.assert_rejected("invalid_stale_required_source.json")

    def test_missing_required_asset_field_is_invalid(self) -> None:
        self.assert_rejected("invalid_missing_required_asset_field.json")

    def test_bad_numeric_values_are_invalid(self) -> None:
        self.assert_rejected("invalid_bad_numeric_values.json")

    def test_empty_stablecoin_data_is_invalid(self) -> None:
        self.assert_rejected("invalid_empty_stablecoin_data.json")

    def test_malformed_snapshot_is_invalid(self) -> None:
        self.assert_rejected("malformed_snapshot.json")


if __name__ == "__main__":
    unittest.main()
