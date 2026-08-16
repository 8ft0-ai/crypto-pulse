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
from typing import Callable
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_crypto_observation_hour_comparison_record import (
    build_observation_hour_comparison,
    comparison_id_for_record,
)
from resolve_crypto_observation_hour_adjacency import PINNED_REFS

FIXTURES = ROOT / "tests" / "fixtures"
BASE = datetime(2026, 7, 8, 4, 34, 0, tzinfo=timezone.utc)
PRODUCER = "scripts/ingest_crypto_sources.py"


def _git(root: Path, *args: str) -> bytes:
    return subprocess.run(["git", "-C", str(root), *args], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout


def _utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _slot(value: datetime) -> str:
    return _utc(value.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0))


def _retime(payload: dict, when: datetime) -> None:
    zone = ZoneInfo(payload["run"].get("timezone", "Australia/Sydney"))
    local = when.astimezone(zone)
    payload["run"]["generated_at_utc"] = _utc(when)
    payload["run"]["generated_at_local"] = local.isoformat()
    payload["run"]["timezone"] = zone.key
    payload["run"]["timezone_abbreviation"] = local.tzname()
    payload["run"]["cadence"] = "hourly"
    payload["run"]["producer"] = PRODUCER
    payload["run"]["observation_hour_utc"] = _slot(when)
    for source in payload.get("sources", {}).values():
        if isinstance(source, dict) and "fetched_at_utc" in source:
            source["fetched_at_utc"] = _utc(when)
    for asset in payload.get("market", {}).get("assets", []):
        if isinstance(asset, dict) and "last_updated" in asset:
            asset["last_updated"] = _utc(when)


def _write(
    root: Path,
    when: datetime,
    fixture: str = "valid_ok_snapshot.json",
    mutate: Callable[[dict], None] | None = None,
) -> None:
    payload = copy.deepcopy(json.loads((FIXTURES / fixture).read_text(encoding="utf-8")))
    _retime(payload, when)
    if mutate is not None:
        mutate(payload)
    local = when.astimezone(ZoneInfo(payload["run"]["timezone"]))
    safe = "".join(ch for ch in (local.tzname() or "LOCAL") if ch.isalnum()) or "LOCAL"
    path = root / f"{local.year:04d}/{local.month:02d}/{local.day:02d}/{local.hour:02d}{local.minute:02d}_{safe}_source_snapshot.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")


def _repo(tmp: str) -> tuple[Path, Path]:
    repo = Path(tmp)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "tests@example.invalid")
    _git(repo, "config", "user.name", "CryptoPulse Tests")
    for ref in PINNED_REFS.values():
        target = repo / ref["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / ref["path"], target)
    root = repo / "data/crypto/hourly"
    root.mkdir(parents=True, exist_ok=True)
    return repo, root


def _commit(repo: Path) -> str:
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "fixture")
    return _git(repo, "rev-parse", "HEAD").decode().strip()


def _build_pair(
    tmp: str,
    predecessor: datetime,
    *,
    current_fixture: str = "valid_ok_snapshot.json",
    predecessor_fixture: str = "valid_ok_snapshot.json",
    current_mutate: Callable[[dict], None] | None = None,
    predecessor_mutate: Callable[[dict], None] | None = None,
) -> dict:
    repo, root = _repo(tmp)
    _write(root, predecessor, predecessor_fixture, predecessor_mutate)
    _write(root, BASE, current_fixture, current_mutate)
    return build_observation_hour_comparison(repo, _commit(repo), _slot(BASE))


class ObservationHourComparisonRecordTests(unittest.TestCase):
    def test_below_3600_actual_elapsed_is_comparison_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            record = _build_pair(tmp, BASE - timedelta(minutes=54))
            self.assertEqual(record["comparison_status"], "comparison-available")
            self.assertEqual(record["actual_elapsed_seconds"], 3240)
            self.assertEqual(len(record["metric_comparisons"]), 26)
            self.assertEqual(len(record["source_availability_changes"]), 8)
            self.assertEqual(record["comparison_id"], comparison_id_for_record(record))

    def test_equal_3600_actual_elapsed_is_comparison_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            record = _build_pair(tmp, BASE - timedelta(hours=1))
            self.assertEqual(record["comparison_status"], "comparison-available")
            self.assertEqual(record["actual_elapsed_seconds"], 3600)

    def test_above_3600_actual_elapsed_is_comparison_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            record = _build_pair(tmp, BASE - timedelta(hours=1, minutes=14))
            self.assertEqual(record["comparison_status"], "comparison-available")
            self.assertEqual(record["actual_elapsed_seconds"], 4440)

    def test_side_specific_degraded_evidence_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            record = _build_pair(
                tmp,
                BASE - timedelta(minutes=54),
                predecessor_fixture="valid_degraded_optional_source_warning.json",
            )
            self.assertEqual(record["comparison_status"], "comparison-available")
            self.assertEqual(record["current"]["quality_status"], "valid-ok")
            self.assertEqual(record["predecessor"]["quality_status"], "valid-degraded")
            self.assertTrue(record["predecessor"]["non_blocking_warnings"])

    def test_missing_predecessor_is_explicit_and_has_no_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, root = _repo(tmp)
            _write(root, BASE - timedelta(hours=2))
            _write(root, BASE)
            record = build_observation_hour_comparison(repo, _commit(repo), _slot(BASE))
            self.assertEqual(record["comparison_status"], "predecessor-missing")
            self.assertIsNone(record["predecessor"])
            self.assertEqual(record["metric_comparisons"], [])

    def test_pair_schema_incompatible_is_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            record = _build_pair(
                tmp,
                BASE - timedelta(minutes=54),
                predecessor_mutate=lambda payload: payload.__setitem__("schema_version", "0.3"),
            )
            self.assertEqual(record["comparison_status"], "pair-schema-incompatible")
            self.assertEqual(record["metric_comparisons"], [])

    def test_pair_semantics_incompatible_is_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            record = _build_pair(
                tmp,
                BASE - timedelta(minutes=54),
                predecessor_mutate=lambda payload: payload["run"].__setitem__("producer", "other.py"),
            )
            self.assertEqual(record["comparison_status"], "pair-semantics-incompatible")
            self.assertEqual(record["metric_comparisons"], [])


if __name__ == "__main__":
    unittest.main()
