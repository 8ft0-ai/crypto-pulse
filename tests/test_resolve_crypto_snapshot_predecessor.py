from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from resolve_crypto_snapshot_predecessor import (  # noqa: E402
    PREDECESSOR_POLICY_VERSION,
    resolve_predecessor,
)
from validate_crypto_snapshot import load_config  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures"
CONFIG = load_config(ROOT / "config" / "crypto_sources.yml")
SYDNEY = ZoneInfo("Australia/Sydney")


def _utc_text(value: datetime) -> str:
    return (
        value.astimezone(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _fixture(name: str = "valid_ok_snapshot.json") -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _payload_at(
    when: datetime,
    *,
    fixture_name: str = "valid_ok_snapshot.json",
    schema_version: str = "0.2",
) -> dict:
    payload = copy.deepcopy(_fixture(fixture_name))
    when = when.astimezone(timezone.utc).replace(microsecond=0)
    utc_text = _utc_text(when)
    local = when.astimezone(SYDNEY)

    payload["schema_version"] = schema_version
    payload["run"]["generated_at_utc"] = utc_text
    payload["run"]["generated_at_local"] = local.isoformat()
    payload["run"]["timezone"] = "Australia/Sydney"

    for source in payload["sources"].values():
        if isinstance(source, dict) and "fetched_at_utc" in source:
            source["fetched_at_utc"] = utc_text

    for asset in payload["market"]["assets"]:
        asset["last_updated"] = utc_text

    return payload


def _expected_path(snapshot_root: Path, when: datetime) -> Path:
    local = when.astimezone(SYDNEY)
    tz_name = local.tzname() or "LOCAL"
    safe_tz = "".join(ch for ch in tz_name if ch.isalnum()) or "LOCAL"
    return (
        snapshot_root
        / f"{local.year:04d}"
        / f"{local.month:02d}"
        / f"{local.day:02d}"
        / f"{local.hour:02d}{local.minute:02d}_{safe_tz}_source_snapshot.json"
    )


def _write_snapshot(
    snapshot_root: Path,
    when: datetime,
    *,
    payload: dict | None = None,
    fixture_name: str = "valid_ok_snapshot.json",
    schema_version: str = "0.2",
    path_override: Path | None = None,
) -> Path:
    if payload is None:
        payload = _payload_at(
            when,
            fixture_name=fixture_name,
            schema_version=schema_version,
        )
    path = path_override or _expected_path(snapshot_root, when)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    return path


class PredecessorResolverTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.snapshot_root = Path(self.tempdir.name) / "data" / "crypto" / "hourly"
        self.current_time = datetime(2026, 7, 8, 5, 0, tzinfo=timezone.utc)

    def resolve(self, current: Path) -> dict:
        return resolve_predecessor(current, self.snapshot_root, CONFIG)

    def pair(
        self,
        *,
        current_fixture: str = "valid_ok_snapshot.json",
        predecessor_fixture: str = "valid_ok_snapshot.json",
        gap_seconds: int = 3600,
        current_schema: str = "0.2",
        predecessor_schema: str = "0.2",
    ) -> tuple[Path, Path]:
        predecessor_time = self.current_time - timedelta(seconds=gap_seconds)
        predecessor = _write_snapshot(
            self.snapshot_root,
            predecessor_time,
            fixture_name=predecessor_fixture,
            schema_version=predecessor_schema,
        )
        current = _write_snapshot(
            self.snapshot_root,
            self.current_time,
            fixture_name=current_fixture,
            schema_version=current_schema,
        )
        return current, predecessor

    def test_exact_hour_valid_ok_pair_resolves(self) -> None:
        current, predecessor = self.pair()
        result = self.resolve(current)

        self.assertEqual(result["predecessor_policy_version"], PREDECESSOR_POLICY_VERSION)
        self.assertEqual(result["resolution_status"], "predecessor-resolved")
        self.assertEqual(result["elapsed_seconds"], 3600)
        self.assertEqual(result["current"]["quality_status"], "valid-ok")
        self.assertEqual(result["predecessor"]["quality_status"], "valid-ok")
        self.assertEqual(
            result["predecessor"]["sha256"],
            hashlib.sha256(predecessor.read_bytes()).hexdigest(),
        )

    def test_valid_degraded_current_is_eligible_and_preserved(self) -> None:
        current, _ = self.pair(
            current_fixture="valid_degraded_optional_source_warning.json"
        )
        result = self.resolve(current)

        self.assertEqual(result["resolution_status"], "predecessor-resolved")
        self.assertEqual(result["current"]["quality_status"], "valid-degraded")
        self.assertTrue(result["current"]["non_blocking_warnings"])

    def test_valid_degraded_predecessor_is_eligible_and_preserved(self) -> None:
        current, _ = self.pair(
            predecessor_fixture="valid_degraded_optional_source_warning.json"
        )
        result = self.resolve(current)

        self.assertEqual(result["resolution_status"], "predecessor-resolved")
        self.assertEqual(result["predecessor"]["quality_status"], "valid-degraded")
        self.assertTrue(result["predecessor"]["non_blocking_warnings"])

    def test_current_validator_failure_fails_closed(self) -> None:
        predecessor_time = self.current_time - timedelta(hours=1)
        _write_snapshot(self.snapshot_root, predecessor_time)
        payload = _payload_at(self.current_time)
        payload["sources"]["coingecko"]["status"] = "error"
        current = _write_snapshot(self.snapshot_root, self.current_time, payload=payload)

        result = self.resolve(current)

        self.assertEqual(result["resolution_status"], "current-invalid")
        self.assertIsNone(result["current"]["quality_status"])

    def test_current_identity_mismatch_fails_closed(self) -> None:
        predecessor_time = self.current_time - timedelta(hours=1)
        _write_snapshot(self.snapshot_root, predecessor_time)
        wrong_path = _expected_path(
            self.snapshot_root, self.current_time + timedelta(minutes=1)
        )
        current = _write_snapshot(
            self.snapshot_root,
            self.current_time,
            path_override=wrong_path,
        )

        result = self.resolve(current)

        self.assertEqual(result["resolution_status"], "current-identity-invalid")

    def test_unparseable_candidate_makes_set_unorderable(self) -> None:
        current = _write_snapshot(self.snapshot_root, self.current_time)
        malformed = (
            self.snapshot_root
            / "2026"
            / "07"
            / "08"
            / "9999_AEST_source_snapshot.json"
        )
        malformed.parent.mkdir(parents=True, exist_ok=True)
        malformed.write_text("{not-json", encoding="utf-8")

        result = self.resolve(current)

        self.assertEqual(result["resolution_status"], "candidate-set-unorderable")

    def test_no_prior_snapshot_is_missing(self) -> None:
        current = _write_snapshot(self.snapshot_root, self.current_time)

        result = self.resolve(current)

        self.assertEqual(result["resolution_status"], "predecessor-missing")

    def test_tied_immediate_prior_is_ambiguous(self) -> None:
        predecessor_time = self.current_time - timedelta(hours=1)
        _write_snapshot(self.snapshot_root, predecessor_time)
        duplicate_path = (
            self.snapshot_root
            / "2026"
            / "07"
            / "08"
            / "0001_AEST_source_snapshot.json"
        )
        _write_snapshot(
            self.snapshot_root,
            predecessor_time,
            path_override=duplicate_path,
        )
        current = _write_snapshot(self.snapshot_root, self.current_time)

        result = self.resolve(current)

        self.assertEqual(result["resolution_status"], "predecessor-ambiguous")

    def test_invalid_immediate_predecessor_fails_closed(self) -> None:
        predecessor_time = self.current_time - timedelta(hours=1)
        payload = _payload_at(predecessor_time)
        payload["sources"]["coingecko"]["status"] = "error"
        _write_snapshot(self.snapshot_root, predecessor_time, payload=payload)
        current = _write_snapshot(self.snapshot_root, self.current_time)

        result = self.resolve(current)

        self.assertEqual(result["resolution_status"], "predecessor-invalid")

    def test_predecessor_identity_mismatch_fails_closed(self) -> None:
        predecessor_time = self.current_time - timedelta(hours=1)
        wrong_path = _expected_path(
            self.snapshot_root, predecessor_time - timedelta(minutes=1)
        )
        _write_snapshot(
            self.snapshot_root,
            predecessor_time,
            path_override=wrong_path,
        )
        current = _write_snapshot(self.snapshot_root, self.current_time)

        result = self.resolve(current)

        self.assertEqual(result["resolution_status"], "predecessor-identity-invalid")

    def test_gap_less_than_one_hour_is_out_of_window(self) -> None:
        current, _ = self.pair(gap_seconds=3599)

        result = self.resolve(current)

        self.assertEqual(result["resolution_status"], "predecessor-out-of-window")
        self.assertEqual(result["elapsed_seconds"], 3599)

    def test_gap_greater_than_one_hour_is_out_of_window(self) -> None:
        current, _ = self.pair(gap_seconds=3601)

        result = self.resolve(current)

        self.assertEqual(result["resolution_status"], "predecessor-out-of-window")
        self.assertEqual(result["elapsed_seconds"], 3601)

    def test_schema_mismatch_at_exact_hour_is_incompatible(self) -> None:
        current, _ = self.pair(predecessor_schema="0.1")

        result = self.resolve(current)

        self.assertEqual(result["resolution_status"], "pair-schema-incompatible")

    def test_invalid_immediate_prior_is_not_skipped_for_older_candidate(self) -> None:
        immediate_time = self.current_time - timedelta(minutes=30)
        payload = _payload_at(immediate_time)
        payload["sources"]["coingecko"]["status"] = "error"
        _write_snapshot(self.snapshot_root, immediate_time, payload=payload)
        _write_snapshot(self.snapshot_root, self.current_time - timedelta(hours=1))
        current = _write_snapshot(self.snapshot_root, self.current_time)

        result = self.resolve(current)

        self.assertEqual(result["resolution_status"], "predecessor-invalid")
        self.assertEqual(
            result["predecessor"]["generated_at_utc"], _utc_text(immediate_time)
        )

    def test_out_of_window_immediate_prior_is_not_skipped(self) -> None:
        immediate_time = self.current_time - timedelta(minutes=30)
        _write_snapshot(self.snapshot_root, immediate_time)
        _write_snapshot(self.snapshot_root, self.current_time - timedelta(hours=1))
        current = _write_snapshot(self.snapshot_root, self.current_time)

        result = self.resolve(current)

        self.assertEqual(result["resolution_status"], "predecessor-out-of-window")
        self.assertEqual(result["elapsed_seconds"], 1800)
        self.assertEqual(
            result["predecessor"]["generated_at_utc"], _utc_text(immediate_time)
        )

    def test_schema_incompatible_immediate_prior_is_not_skipped(self) -> None:
        immediate_time = self.current_time - timedelta(hours=1)
        _write_snapshot(
            self.snapshot_root,
            immediate_time,
            schema_version="0.1",
        )
        _write_snapshot(
            self.snapshot_root,
            self.current_time - timedelta(hours=2),
            schema_version="0.2",
        )
        current = _write_snapshot(self.snapshot_root, self.current_time)

        result = self.resolve(current)

        self.assertEqual(result["resolution_status"], "pair-schema-incompatible")
        self.assertEqual(
            result["predecessor"]["generated_at_utc"], _utc_text(immediate_time)
        )

    def test_enumeration_creation_order_does_not_change_result(self) -> None:
        logical_times = [
            self.current_time - timedelta(hours=2),
            self.current_time - timedelta(hours=1),
        ]

        first_root = self.snapshot_root
        for value in logical_times:
            _write_snapshot(first_root, value)
        current_first = _write_snapshot(first_root, self.current_time)
        first = resolve_predecessor(current_first, first_root, CONFIG)

        with tempfile.TemporaryDirectory() as second_tmp:
            second_root = Path(second_tmp) / "data" / "crypto" / "hourly"
            for value in reversed(logical_times):
                _write_snapshot(second_root, value)
            current_second = _write_snapshot(second_root, self.current_time)
            second = resolve_predecessor(current_second, second_root, CONFIG)

        self.assertEqual(first, second)

    def test_authoritative_utc_selects_immediate_then_identity_failure_stops(self) -> None:
        selected_time = self.current_time - timedelta(hours=1)
        wrong_path = _expected_path(
            self.snapshot_root, selected_time - timedelta(minutes=10)
        )
        _write_snapshot(
            self.snapshot_root,
            selected_time,
            path_override=wrong_path,
        )
        _write_snapshot(
            self.snapshot_root,
            self.current_time - timedelta(hours=1, minutes=15),
        )
        current = _write_snapshot(self.snapshot_root, self.current_time)

        result = self.resolve(current)

        self.assertEqual(result["resolution_status"], "predecessor-identity-invalid")
        self.assertEqual(
            result["predecessor"]["generated_at_utc"], _utc_text(selected_time)
        )


if __name__ == "__main__":
    unittest.main()
