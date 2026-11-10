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
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_crypto_observation_hour_comparison_record import (
    build_observation_hour_comparison,
    comparison_id_for_record,
)
from resolve_crypto_observation_hour_adjacency import PINNED_REFS
from validate_crypto_observation_hour_comparison import (
    ObservationHourComparisonValidationError,
    validate_observation_hour_comparison,
)

FIXTURES = ROOT / "tests" / "fixtures"
BASE = datetime(2026, 7, 8, 4, 34, 0, tzinfo=timezone.utc)
PRODUCER = "scripts/ingest_crypto_sources.py"


def _git(root: Path, *args: str) -> bytes:
    return subprocess.run(["git", "-C", str(root), *args], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout


def _utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _slot(value: datetime) -> str:
    return _utc(value.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0))


def _write(root: Path, when: datetime) -> None:
    payload = copy.deepcopy(json.loads((FIXTURES / "valid_ok_snapshot.json").read_text(encoding="utf-8")))
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
    safe = "".join(ch for ch in (local.tzname() or "LOCAL") if ch.isalnum()) or "LOCAL"
    path = root / f"{local.year:04d}/{local.month:02d}/{local.day:02d}/{local.hour:02d}{local.minute:02d}_{safe}_source_snapshot.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")


def _repo(tmp: str) -> tuple[Path, Path, str]:
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
    _write(root, BASE - timedelta(minutes=54))
    _write(root, BASE)
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "fixture")
    commit = _git(repo, "rev-parse", "HEAD").decode().strip()
    return repo, root, commit


class ObservationHourComparisonValidatorTests(unittest.TestCase):
    def test_repository_replay_accepts_exact_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, _, commit = _repo(tmp)
            record = build_observation_hour_comparison(repo, commit, _slot(BASE))
            validated = validate_observation_hour_comparison(repo, record)
            self.assertEqual(validated, record)

    def test_recomputed_id_does_not_hide_tampered_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, _, commit = _repo(tmp)
            record = build_observation_hour_comparison(repo, commit, _slot(BASE))
            tampered = copy.deepcopy(record)
            tampered["actual_elapsed_seconds"] = 3600
            tampered["comparison_id"] = comparison_id_for_record(tampered)
            with self.assertRaises(ObservationHourComparisonValidationError):
                validate_observation_hour_comparison(repo, tampered)

    def test_unknown_top_level_vocabulary_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, _, commit = _repo(tmp)
            record = build_observation_hour_comparison(repo, commit, _slot(BASE))
            record["unexpected"] = True
            record["comparison_id"] = comparison_id_for_record(record)
            with self.assertRaises(ObservationHourComparisonValidationError):
                validate_observation_hour_comparison(repo, record)


if __name__ == "__main__":
    unittest.main()
