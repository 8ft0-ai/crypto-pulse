from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_crypto_observation_hour import (
    canonical_observation_hour,
    validate_observation_hour,
)
from validate_crypto_snapshot import ValidationError, load_config, validate_snapshot

LEGACY_SNAPSHOT = ROOT / "data" / "crypto" / "hourly" / "2026" / "07" / "08" / "1742_AEST_source_snapshot.json"
CONFIG_PATH = ROOT / "config" / "crypto_sources.yml"
VALIDATOR_PATH = ROOT / "scripts" / "validate_crypto_snapshot.py"
EXPECTED_VALIDATOR_BLOB = "b8c7fcc850bf0f5076f7d084bb6be9c24a9b7d3a"
EXPECTED_CONFIG_BLOB = "73c5a3f3db81954951801c7d348d09a4c6296d73"


def git_blob_sha(path: Path) -> str:
    payload = path.read_bytes()
    header = f"blob {len(payload)}\0".encode("ascii")
    return hashlib.sha1(header + payload).hexdigest()


class ObservationHourValidatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.config = load_config(CONFIG_PATH)
        cls.legacy = json.loads(LEGACY_SNAPSHOT.read_text(encoding="utf-8"))

    def write_snapshot(self, snapshot: dict) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        temp = tempfile.TemporaryDirectory()
        path = Path(temp.name) / "test_source_snapshot.json"
        path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return temp, path

    def slot_ready_snapshot(self) -> dict:
        snapshot = copy.deepcopy(self.legacy)
        generated = snapshot["run"]["generated_at_utc"]
        snapshot["run"]["observation_hour_utc"] = canonical_observation_hour(generated)
        return snapshot

    def test_canonical_observation_hour_boundaries_and_offsets(self) -> None:
        cases = {
            "2026-07-10T08:00:00Z": "2026-07-10T08:00:00Z",
            "2026-07-10T08:17:45Z": "2026-07-10T08:00:00Z",
            "2026-07-10T08:59:59Z": "2026-07-10T08:00:00Z",
            "2026-07-10T09:00:00Z": "2026-07-10T09:00:00Z",
            "2026-07-10T19:17:45+10:00": "2026-07-10T09:00:00Z",
        }
        for generated, expected in cases.items():
            with self.subTest(generated=generated):
                self.assertEqual(canonical_observation_hour(generated), expected)

    def test_slot_ready_snapshot_passes_frozen_and_phase12_validation(self) -> None:
        snapshot = self.slot_ready_snapshot()
        temp, path = self.write_snapshot(snapshot)
        self.addCleanup(temp.cleanup)

        frozen_quality = validate_snapshot(path, self.config)
        result = validate_observation_hour(path, self.config)

        self.assertIn(frozen_quality["status"], {"valid-ok", "valid-degraded"})
        self.assertEqual(result["contract_version"], "phase12-observation-hour/v1")
        self.assertEqual(result["generated_at_utc"], snapshot["run"]["generated_at_utc"])
        self.assertEqual(result["observation_hour_utc"], snapshot["run"]["observation_hour_utc"])

    def test_legacy_snapshot_remains_frozen_valid_but_is_not_slot_ready(self) -> None:
        quality = validate_snapshot(LEGACY_SNAPSHOT, self.config)
        self.assertIn(quality["status"], {"valid-ok", "valid-degraded"})
        with self.assertRaisesRegex(ValidationError, "observation_hour_utc is required"):
            validate_observation_hour(LEGACY_SNAPSHOT, self.config)

    def test_missing_malformed_noncanonical_and_mismatched_values_fail_closed(self) -> None:
        base = self.slot_ready_snapshot()
        cases = [
            (None, "observation_hour_utc is required"),
            ("not-a-time", "canonical YYYY-MM-DDTHH:00:00Z"),
            ("2026-07-08T07:00:00+00:00", "canonical YYYY-MM-DDTHH:00:00Z"),
            ("2026-07-08T07:30:00Z", "canonical YYYY-MM-DDTHH:00:00Z"),
            ("2026-07-08T08:00:00Z", "must equal containing UTC hour"),
        ]
        for value, message in cases:
            with self.subTest(value=value):
                snapshot = copy.deepcopy(base)
                if value is None:
                    snapshot["run"].pop("observation_hour_utc", None)
                else:
                    snapshot["run"]["observation_hour_utc"] = value
                temp, path = self.write_snapshot(snapshot)
                try:
                    with self.assertRaisesRegex(ValidationError, message):
                        validate_observation_hour(path, self.config)
                finally:
                    temp.cleanup()

    def test_frozen_validator_and_config_blob_identities_are_unchanged(self) -> None:
        self.assertEqual(git_blob_sha(VALIDATOR_PATH), EXPECTED_VALIDATOR_BLOB)
        self.assertEqual(git_blob_sha(CONFIG_PATH), EXPECTED_CONFIG_BLOB)


if __name__ == "__main__":
    unittest.main()
