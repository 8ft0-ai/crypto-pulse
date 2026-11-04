from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from crypto_ingestion_slot import (
    build_receipt, canonical_hour, check_request, inspect_snapshot,
    receipt_name, verify_vacant,
)
from validate_crypto_snapshot import ValidationError

HOUR = "2026-11-04T01:00:00Z"
CORRELATION = "cp-2026110401"
NOW = datetime(2026, 11, 4, 1, 12, tzinfo=timezone.utc)


class CryptoIngestionSlotTests(unittest.TestCase):
    def test_dispatch_accepts_only_exact_scheduled_hour_and_deadline(self) -> None:
        self.assertEqual(check_request("workflow_dispatch", HOUR, CORRELATION, NOW), canonical_hour(HOUR))
        for now in (
            NOW - timedelta(minutes=6),  # :06, before the :07 cron
            datetime(2026, 11, 4, 1, 30, tzinfo=timezone.utc),
            datetime(2026, 11, 4, 2, 10, tzinfo=timezone.utc),
        ):
            with self.subTest(now=now), self.assertRaisesRegex(ValidationError, "outside"):
                check_request("workflow_dispatch", HOUR, CORRELATION, now)

    def test_rejects_noncanonical_and_cross_hour_input(self) -> None:
        for intended in (
            "2026-11-04T01:00:00+00:00",
            "2026-11-04T01:07:00Z",
            "2026-11-04T01:00:00z",
            "2026-11-32T01:00:00Z",
            "",
        ):
            with self.subTest(intended=intended), self.assertRaises((ValidationError, ValueError)):
                check_request("workflow_dispatch", intended, CORRELATION, NOW)
        with self.assertRaisesRegex(ValidationError, "correlation"):
            check_request("workflow_dispatch", HOUR, "cp-2026110402", NOW)
        with self.assertRaisesRegex(ValidationError, "correlation"):
            check_request("workflow_dispatch", HOUR, "", NOW)

    def test_no_schedule_hour_override_or_unknown_event(self) -> None:
        self.assertIsNone(check_request("schedule", "", "", NOW))
        with self.assertRaisesRegex(ValidationError, "cannot override"):
            check_request("schedule", HOUR, CORRELATION, NOW)
        with self.assertRaisesRegex(ValidationError, "unsupported"):
            check_request("pull_request", "", "", NOW)

    def test_only_actual_valid_ok_snapshot_in_requested_hour(self) -> None:
        def evidence(hour=HOUR, quality="valid-ok"):
            return {
                "observation_hour_utc": hour,
                "generated_at_utc": "2026-11-04T01:10:00Z",
                "quality_status": quality,
            }

        with patch("crypto_ingestion_slot.load_config", return_value={}):
            with patch("crypto_ingestion_slot.validate_observation_hour", return_value=evidence()):
                hour, _ = inspect_snapshot(Path("ignored"), Path("ignored"), "workflow_dispatch", HOUR, CORRELATION, NOW)
                self.assertEqual(hour.strftime("%Y-%m-%dT%H:00:00Z"), HOUR)
            with patch("crypto_ingestion_slot.validate_observation_hour", return_value=evidence("2026-11-04T00:00:00Z")):
                with self.assertRaisesRegex(ValidationError, "differs"):
                    inspect_snapshot(Path("ignored"), Path("ignored"), "workflow_dispatch", HOUR, CORRELATION, NOW)
            with patch("crypto_ingestion_slot.validate_observation_hour", return_value=evidence(quality="valid-degraded")):
                with self.assertRaisesRegex(ValidationError, "valid-ok"):
                    inspect_snapshot(Path("ignored"), Path("ignored"), "schedule", "", "", NOW)
            with patch("crypto_ingestion_slot.validate_observation_hour", return_value={
                **evidence(), "generated_at_utc": "2026-11-04T01:20:00Z",
            }):
                with self.assertRaisesRegex(ValidationError, "future"):
                    inspect_snapshot(Path("ignored"), Path("ignored"), "workflow_dispatch", HOUR, CORRELATION, NOW)

    def test_artifact_vacancy_fails_closed_on_duplicate_or_incomplete_list(self) -> None:
        name = receipt_name(canonical_hour(HOUR))
        self.assertEqual(name, "crypto-hour-accepted-20261104T01")
        verify_vacant({"total_count": 0, "artifacts": []}, name)
        for listing in (
            {"total_count": 1, "artifacts": [{"name": name, "expired": True}]},
            {"total_count": 1, "artifacts": []},
            {"artifacts": []},
            {"total_count": 101, "artifacts": []},
            {"total_count": 0, "artifacts": [{}]},
            {"total_count": 1, "artifacts": [{"name": "wrong-hour"}]},
        ):
            with self.subTest(listing=listing), self.assertRaises(ValidationError):
                verify_vacant(listing, name)
        with self.assertRaisesRegex(ValidationError, "invalid acceptance"):
            verify_vacant({"total_count": 0, "artifacts": []}, "../bad")

    def test_receipt_retains_provenance_and_noncritical_pr_status(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            snapshot = Path(directory) / "source_snapshot.json"
            snapshot.write_bytes(b'{"source": "example"}\n')
            sample = {
                "observation_hour_utc": HOUR,
                "generated_at_utc": "2026-11-04T01:10:00Z",
                "quality_status": "valid-ok",
            }
            with patch("crypto_ingestion_slot.load_config", return_value={}):
                with patch("crypto_ingestion_slot.validate_observation_hour", return_value=sample):
                    kwargs = dict(
                        snapshot=snapshot, config=Path("ignored"),
                        event="workflow_dispatch", intended=HOUR, correlation=CORRELATION,
                        now=NOW, run_id="12345", run_attempt="1",
                        snapshot_commit="a" * 40,
                        source_intent="deterministic-publication-intent-12345-1",
                        rolling_pr_outcome="failure",
                    )
                    receipt = build_receipt(**kwargs)
                    self.assertEqual(receipt["snapshot_sha256"], hashlib.sha256(snapshot.read_bytes()).hexdigest())
                    self.assertEqual(receipt["source_intent_artifact"], kwargs["source_intent"])
                    self.assertEqual(receipt["rolling_pr_outcome"], "failure")
                    self.assertEqual(receipt["dispatch_correlation_id"], CORRELATION)
                    self.assertNotIn("token", str(receipt).lower())
                    with self.assertRaisesRegex(ValidationError, "intent artifact"):
                        build_receipt(**{**kwargs, "source_intent": "incorrect"})
                    with self.assertRaisesRegex(ValidationError, "rolling PR"):
                        build_receipt(**{**kwargs, "rolling_pr_outcome": "unknown"})


if __name__ == "__main__":
    unittest.main()
