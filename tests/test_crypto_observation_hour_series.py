from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from crypto_observation_hour_series import (
    COMPARISON_GAP_MAP,
    MAX_SLOTS,
    METRIC_GAP_MAP,
    METRIC_IDENTITIES,
    SERIES_SCHEMA_VERSION,
    SOURCE_IDENTITIES,
    ObservationHourSeriesError,
    _continuity,
    build_observation_hour_series,
    canonical_json_bytes,
    series_id_for_record,
    validate_observation_hour_series,
)
from resolve_crypto_observation_hour_adjacency import PINNED_REFS

FIXTURE = ROOT / "tests" / "fixtures" / "valid_ok_snapshot.json"
BASE = datetime(2026, 7, 8, 4, 20, tzinfo=timezone.utc)
ZONE = ZoneInfo("Australia/Sydney")


def _git(repo: Path, *args: str) -> bytes:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.stdout


def _utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _slot(value: datetime) -> str:
    return _utc(value.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0))


def _snapshot_path(repo: Path, when: datetime) -> Path:
    local = when.astimezone(ZONE)
    safe = "".join(ch for ch in (local.tzname() or "LOCAL") if ch.isalnum()) or "LOCAL"
    return (
        repo
        / "data"
        / "crypto"
        / "hourly"
        / f"{local.year:04d}"
        / f"{local.month:02d}"
        / f"{local.day:02d}"
        / f"{local.hour:02d}{local.minute:02d}_{safe}_source_snapshot.json"
    )


def _write_snapshot(repo: Path, when: datetime, *, fixture: str = "valid_ok_snapshot.json") -> Path:
    payload = copy.deepcopy(
        json.loads((ROOT / "tests" / "fixtures" / fixture).read_text(encoding="utf-8"))
    )
    local = when.astimezone(ZONE)
    payload["schema_version"] = "0.2"
    payload["run"]["generated_at_utc"] = _utc(when)
    payload["run"]["generated_at_local"] = local.isoformat()
    payload["run"]["timezone"] = ZONE.key
    payload["run"]["timezone_abbreviation"] = local.tzname()
    payload["run"]["observation_hour_utc"] = _slot(when)
    payload["run"]["producer"] = "scripts/ingest_crypto_sources.py"
    payload["run"]["cadence"] = "hourly"
    for source in payload.get("sources", {}).values():
        if isinstance(source, dict) and "fetched_at_utc" in source:
            source["fetched_at_utc"] = _utc(when)
    for asset in payload.get("market", {}).get("assets", []):
        if isinstance(asset, dict) and "last_updated" in asset:
            asset["last_updated"] = _utc(when)
    path = _snapshot_path(repo, when)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    return path


def _repo(tmp: str, times: list[datetime] | None = None) -> tuple[Path, str]:
    repo = Path(tmp)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "phase13@example.invalid")
    _git(repo, "config", "user.name", "Phase 13 tests")
    for ref in PINNED_REFS.values():
        target = repo / ref["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / ref["path"], target)
    for when in times or [BASE - timedelta(minutes=50), BASE, BASE + timedelta(minutes=55)]:
        _write_snapshot(repo, when)
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "fixture")
    return repo, _git(repo, "rev-parse", "HEAD").decode().strip()


class ObservationHourSeriesTests(unittest.TestCase):
    def test_contract_vocabulary_is_closed(self) -> None:
        self.assertEqual(SERIES_SCHEMA_VERSION, "crypto-observation-hour-series/v1")
        self.assertEqual(len(METRIC_IDENTITIES), 12)
        self.assertEqual(len(SOURCE_IDENTITIES), 8)
        self.assertEqual(len(COMPARISON_GAP_MAP), 12)
        self.assertEqual(len(METRIC_GAP_MAP), 4)

    def test_all_series_keys_build_and_validate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, commit = _repo(tmp)
            slot = _slot(BASE)
            for series_key in METRIC_IDENTITIES:
                with self.subTest(series_kind="metric", series_key=series_key):
                    record = build_observation_hour_series(
                        repo, commit, "metric", series_key, slot, slot
                    )
                    validate_observation_hour_series(repo, record)
            for series_key in SOURCE_IDENTITIES:
                with self.subTest(series_kind="source-status", series_key=series_key):
                    record = build_observation_hour_series(
                        repo, commit, "source-status", series_key, slot, slot
                    )
                    validate_observation_hour_series(repo, record)

    def test_window_bounds_and_unknown_vocabulary_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, commit = _repo(tmp)
            start = _slot(BASE)
            end = _slot(BASE + timedelta(hours=MAX_SLOTS - 1))
            record = build_observation_hour_series(
                repo, commit, "metric", "BTC.price_usd", start, end
            )
            self.assertEqual(len(record["entries"]), MAX_SLOTS)
        for start, end in (
            ("2026-07-08T04:30:00Z", "2026-07-08T05:00:00Z"),
            ("2026-07-08T05:00:00Z", "2026-07-08T04:00:00Z"),
            ("2026-07-01T00:00:00Z", "2026-07-08T00:00:00Z"),
        ):
            with self.assertRaises(ObservationHourSeriesError):
                build_observation_hour_series(Path("."), "0" * 40, "metric", "BTC.price_usd", start, end)
        with self.assertRaises(ObservationHourSeriesError):
            build_observation_hour_series(Path("."), "0" * 40, "metric", "BTC.change_24h_pct", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z")

    def test_metric_series_replays_comparison_and_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, commit = _repo(tmp)
            start = _slot(BASE)
            end = _slot(BASE + timedelta(hours=1))
            first = build_observation_hour_series(repo, commit, "metric", "BTC.price_usd", start, end)
            second = build_observation_hour_series(repo, commit, "metric", "BTC.price_usd", start, end)
            self.assertEqual(canonical_json_bytes(first), canonical_json_bytes(second))
            self.assertEqual(first["series_id"], series_id_for_record(first))
            self.assertEqual(first["entries"][0]["value"]["comparison"]["comparison_status"], "comparison-available")
            self.assertEqual(first["entries"][1]["continuity"]["status"], "continuous")
            validate_observation_hour_series(repo, first)

    def test_source_status_remains_categorical(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, commit = _repo(tmp)
            slot = _slot(BASE)
            record = build_observation_hour_series(repo, commit, "source-status", "coingecko", slot, slot)
            entry = record["entries"][0]
            self.assertEqual(entry["value"]["datum"], entry["value"]["evidence"]["current_status"])
            self.assertIsInstance(entry["value"]["datum"], str)
            validate_observation_hour_series(repo, record)

    def test_all_comparison_failures_map_to_closed_gaps(self) -> None:
        context = {"commit_sha": "b" * 40}
        for status, reason in COMPARISON_GAP_MAP.items():
            comparison = {
                "comparison_status": status,
                "repository_context": context,
                "current": None,
                "predecessor": None,
            }
            with self.subTest(status=status):
                with mock.patch(
                    "crypto_observation_hour_series.build_observation_hour_comparison",
                    return_value=comparison,
                ):
                    record = build_observation_hour_series(
                        Path("."),
                        "b" * 40,
                        "metric",
                        "BTC.price_usd",
                        "2026-01-01T00:00:00Z",
                        "2026-01-01T00:00:00Z",
                    )
                self.assertIsNone(record["entries"][0]["value"])
                self.assertEqual(record["entries"][0]["gap"]["reason"], reason)

    def test_all_metric_failures_map_to_closed_gaps_without_raw_value_bypass(self) -> None:
        identity = METRIC_IDENTITIES["BTC.price_usd"]
        context = {"commit_sha": "b" * 40}
        for state, reason in METRIC_GAP_MAP.items():
            comparison = {
                "comparison_status": "comparison-available",
                "comparison_id": "a" * 64,
                "repository_context": context,
                "current": {"path": "current"},
                "predecessor": {"path": "pred"},
                "metric_comparisons": [{
                    "family": identity[0],
                    "symbol": identity[1],
                    "field": identity[2],
                    "predecessor": {"present": True, "value": 1},
                    "current": {"present": True, "value": 999},
                    "comparison_state": state,
                    "relation": None,
                }],
                "source_availability_changes": [],
            }
            with self.subTest(state=state):
                with mock.patch(
                    "crypto_observation_hour_series.build_observation_hour_comparison",
                    return_value=comparison,
                ):
                    record = build_observation_hour_series(
                        Path("."),
                        "b" * 40,
                        "metric",
                        "BTC.price_usd",
                        "2026-01-01T00:00:00Z",
                        "2026-01-01T00:00:00Z",
                    )
                self.assertIsNone(record["entries"][0]["value"])
                self.assertEqual(record["entries"][0]["gap"]["reason"], reason)
                self.assertEqual(
                    record["entries"][0]["gap"]["metric_evidence"]["current"]["value"],
                    999,
                )

    def test_missing_and_duplicate_slots_propagate_from_slice1(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, commit = _repo(tmp, [BASE - timedelta(minutes=50)])
            slot = _slot(BASE)
            record = build_observation_hour_series(repo, commit, "metric", "BTC.price_usd", slot, slot)
            self.assertEqual(record["entries"][0]["gap"]["reason"], "phase13-current-missing")
            self.assertEqual(record["entries"][0]["gap"]["comparison"]["current_candidates"], [])
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            repo, _ = _repo(tmp, [BASE - timedelta(minutes=50), BASE, BASE + timedelta(minutes=15)])
            commit = _git(repo, "rev-parse", "HEAD").decode().strip()
            slot = _slot(BASE)
            record = build_observation_hour_series(repo, commit, "metric", "BTC.price_usd", slot, slot)
            self.assertEqual(record["entries"][0]["gap"]["reason"], "phase13-current-ambiguous")
            self.assertEqual(len(record["entries"][0]["gap"]["comparison"]["current_candidates"]), 2)

    def test_degraded_side_evidence_is_retained_for_current_and_predecessor(self) -> None:
        for degraded_side in ("current", "predecessor"):
            with self.subTest(degraded_side=degraded_side):
                with tempfile.TemporaryDirectory() as tmp:
                    repo = Path(tmp)
                    _git(repo, "init", "-q")
                    _git(repo, "config", "user.email", "phase13@example.invalid")
                    _git(repo, "config", "user.name", "Phase 13 tests")
                    for ref in PINNED_REFS.values():
                        target = repo / ref["path"]
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(ROOT / ref["path"], target)
                    predecessor_fixture = (
                        "valid_degraded_optional_source_warning.json"
                        if degraded_side == "predecessor"
                        else "valid_ok_snapshot.json"
                    )
                    current_fixture = (
                        "valid_degraded_optional_source_warning.json"
                        if degraded_side == "current"
                        else "valid_ok_snapshot.json"
                    )
                    _write_snapshot(
                        repo,
                        BASE - timedelta(minutes=50),
                        fixture=predecessor_fixture,
                    )
                    _write_snapshot(repo, BASE, fixture=current_fixture)
                    _git(repo, "add", ".")
                    _git(repo, "commit", "-q", "-m", "fixture")
                    commit = _git(repo, "rev-parse", "HEAD").decode().strip()
                    record = build_observation_hour_series(
                        repo,
                        commit,
                        "metric",
                        "BTC.price_usd",
                        _slot(BASE),
                        _slot(BASE),
                    )
                    comparison = record["entries"][0]["value"]["comparison"]
                    self.assertEqual(
                        comparison[degraded_side]["quality_status"],
                        "valid-degraded",
                    )
                    self.assertTrue(
                        comparison[degraded_side]["non_blocking_warnings"]
                    )

    def test_continuity_requires_field_for_field_identity(self) -> None:
        identity = {
            "path": "data/crypto/hourly/current.json",
            "sha256": "a" * 64,
            "schema_version": "0.2",
            "generated_at_utc": "2026-01-01T00:20:00Z",
            "observation_hour_utc": "2026-01-01T00:00:00Z",
            "quality_status": "valid-ok",
            "non_blocking_warnings": [],
        }
        continuous = _continuity(
            1,
            {"current": copy.deepcopy(identity)},
            {"predecessor": copy.deepcopy(identity)},
        )
        self.assertEqual(continuous["status"], "continuous")
        changed = copy.deepcopy(identity)
        changed["quality_status"] = "valid-degraded"
        changed["non_blocking_warnings"] = ["source warning"]
        discontinuous = _continuity(
            1,
            {"current": copy.deepcopy(identity)},
            {"predecessor": changed},
        )
        self.assertEqual(discontinuous["status"], "discontinuous")
        self.assertEqual(discontinuous["previous_current"], identity)
        self.assertEqual(discontinuous["current_predecessor"], changed)

    def test_discontinuity_and_tamper_are_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, commit = _repo(tmp)
            start = _slot(BASE)
            end = _slot(BASE + timedelta(hours=1))
            record = build_observation_hour_series(repo, commit, "metric", "BTC.price_usd", start, end)
            tampered = copy.deepcopy(record)
            tampered["entries"][1]["continuity"]["status"] = "discontinuous"
            tampered["series_id"] = series_id_for_record(tampered)
            with self.assertRaises(ObservationHourSeriesError):
                validate_observation_hour_series(repo, tampered)
            unknown = copy.deepcopy(record)
            unknown["unexpected"] = True
            unknown["series_id"] = series_id_for_record(unknown)
            with self.assertRaises(ObservationHourSeriesError):
                validate_observation_hour_series(repo, unknown)


if __name__ == "__main__":
    unittest.main()
