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

from resolve_crypto_observation_hour_adjacency import PINNED_REFS, resolve_observation_hour_adjacency

FIXTURES = ROOT / "tests" / "fixtures"
BASE = datetime(2026, 7, 8, 4, 34, 0, tzinfo=timezone.utc)


def _git(root: Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(root), *args], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    ).stdout


def _utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _slot(value: datetime) -> str:
    return _utc(value.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0))


def _retime(payload: dict, when: datetime, *, slot_override: str | None = None) -> None:
    zone = ZoneInfo(payload["run"].get("timezone", "Australia/Sydney"))
    local = when.astimezone(zone)
    payload["run"]["generated_at_utc"] = _utc(when)
    payload["run"]["generated_at_local"] = local.isoformat()
    payload["run"]["timezone"] = zone.key
    payload["run"]["timezone_abbreviation"] = local.tzname()
    payload["run"]["observation_hour_utc"] = slot_override or _slot(when)
    for source in payload.get("sources", {}).values():
        if isinstance(source, dict) and "fetched_at_utc" in source:
            source["fetched_at_utc"] = _utc(when)
    for asset in payload.get("market", {}).get("assets", []):
        if isinstance(asset, dict) and "last_updated" in asset:
            asset["last_updated"] = _utc(when)


def _relative(when: datetime) -> Path:
    local = when.astimezone(ZoneInfo("Australia/Sydney"))
    safe = "".join(ch for ch in (local.tzname() or "LOCAL") if ch.isalnum()) or "LOCAL"
    return Path(f"{local.year:04d}/{local.month:02d}/{local.day:02d}/{local.hour:02d}{local.minute:02d}_{safe}_source_snapshot.json")


def _write(
    root: Path,
    when: datetime,
    *,
    legacy: bool = False,
    slot_override: str | None = None,
    path_override: Path | None = None,
    fixture: str = "valid_ok_snapshot.json",
) -> Path:
    payload = copy.deepcopy(json.loads((FIXTURES / fixture).read_text(encoding="utf-8")))
    _retime(payload, when, slot_override=slot_override)
    if legacy:
        payload["run"].pop("observation_hour_utc", None)
    path = root / (path_override or _relative(when))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
    return path


def _repo(tmp: str) -> tuple[Path, Path]:
    repo = Path(tmp)
    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "tests@example.invalid")
    _git(repo, "config", "user.name", "CryptoPulse Tests")
    for ref in PINNED_REFS.values():
        target = repo / ref["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / ref["path"], target)
    snapshots = repo / "data/crypto/hourly"
    snapshots.mkdir(parents=True, exist_ok=True)
    return repo, snapshots


def _commit(repo: Path) -> str:
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "fixture")
    return _git(repo, "rev-parse", "HEAD").decode().strip()


class ObservationHourAdjacencyTests(unittest.TestCase):
    def test_adjacent_slots_accept_non_3600_actual_elapsed_time(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, root = _repo(tmp)
            predecessor = BASE - timedelta(minutes=54)
            _write(root, predecessor)
            _write(root, BASE)
            result = resolve_observation_hour_adjacency(repo, _commit(repo), _slot(BASE))
            self.assertEqual(result["resolution_status"], "adjacency-resolved")
            self.assertEqual(result["actual_elapsed_seconds"], 3240)
            self.assertEqual(result["current"]["quality_status"], "valid-ok")
            self.assertEqual(result["predecessor"]["observation_hour_utc"], _slot(predecessor))

    def test_legacy_snapshot_without_slot_is_non_participating(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, root = _repo(tmp)
            _write(root, BASE - timedelta(minutes=54))
            _write(root, BASE)
            _write(root, BASE + timedelta(minutes=5), legacy=True)
            result = resolve_observation_hour_adjacency(repo, _commit(repo), _slot(BASE))
            self.assertEqual(result["resolution_status"], "adjacency-resolved")
            self.assertEqual(len(result["current_candidates"]), 1)

    def test_current_missing_is_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, root = _repo(tmp)
            _write(root, BASE - timedelta(minutes=54))
            result = resolve_observation_hour_adjacency(repo, _commit(repo), _slot(BASE))
            self.assertEqual(result["resolution_status"], "current-missing")
            self.assertEqual(result["current_candidates"], [])

    def test_current_duplicate_is_ambiguous_before_validity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, root = _repo(tmp)
            _write(root, BASE - timedelta(minutes=54))
            _write(root, BASE)
            _write(root, BASE + timedelta(minutes=10), slot_override=_slot(BASE))
            result = resolve_observation_hour_adjacency(repo, _commit(repo), _slot(BASE))
            self.assertEqual(result["resolution_status"], "current-ambiguous")
            self.assertEqual(len(result["current_candidates"]), 2)

    def test_current_phase12_mismatch_is_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, root = _repo(tmp)
            actual = BASE - timedelta(hours=2)
            _write(root, actual, slot_override=_slot(BASE))
            result = resolve_observation_hour_adjacency(repo, _commit(repo), _slot(BASE))
            self.assertEqual(result["resolution_status"], "current-invalid")

    def test_current_wrong_repository_path_is_identity_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, root = _repo(tmp)
            _write(root, BASE, path_override=Path("2026/07/08/9999_AEST_source_snapshot.json"))
            result = resolve_observation_hour_adjacency(repo, _commit(repo), _slot(BASE))
            self.assertEqual(result["resolution_status"], "current-identity-invalid")

    def test_predecessor_missing_does_not_fall_back_two_hours(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, root = _repo(tmp)
            _write(root, BASE - timedelta(hours=2))
            _write(root, BASE)
            result = resolve_observation_hour_adjacency(repo, _commit(repo), _slot(BASE))
            self.assertEqual(result["resolution_status"], "predecessor-missing")
            self.assertIsNone(result["predecessor"])

    def test_predecessor_duplicate_is_ambiguous(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, root = _repo(tmp)
            _write(root, BASE)
            _write(root, BASE - timedelta(minutes=54))
            _write(root, BASE - timedelta(minutes=44))
            result = resolve_observation_hour_adjacency(repo, _commit(repo), _slot(BASE))
            self.assertEqual(result["resolution_status"], "predecessor-ambiguous")
            self.assertEqual(len(result["predecessor_candidates"]), 2)

    def test_predecessor_duplicate_ambiguity_wins_over_invalid_duplicate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, root = _repo(tmp)
            _write(root, BASE)
            _write(root, BASE - timedelta(minutes=54))
            _write(root, BASE - timedelta(hours=2, minutes=-10), slot_override=_slot(BASE - timedelta(hours=1)))
            result = resolve_observation_hour_adjacency(repo, _commit(repo), _slot(BASE))
            self.assertEqual(result["resolution_status"], "predecessor-ambiguous")
            self.assertEqual(len(result["predecessor_candidates"]), 2)

    def test_predecessor_wrong_repository_path_is_identity_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, root = _repo(tmp)
            _write(root, BASE)
            _write(
                root,
                BASE - timedelta(minutes=54),
                path_override=Path("2026/07/08/9998_AEST_source_snapshot.json"),
            )
            result = resolve_observation_hour_adjacency(repo, _commit(repo), _slot(BASE))
            self.assertEqual(result["resolution_status"], "predecessor-identity-invalid")

    def test_predecessor_phase12_mismatch_is_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, root = _repo(tmp)
            _write(root, BASE)
            actual = BASE - timedelta(hours=2)
            _write(root, actual, slot_override=_slot(BASE - timedelta(hours=1)))
            result = resolve_observation_hour_adjacency(repo, _commit(repo), _slot(BASE))
            self.assertEqual(result["resolution_status"], "predecessor-invalid")

    def test_malformed_asserted_slot_fails_whole_candidate_set(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, root = _repo(tmp)
            _write(root, BASE - timedelta(minutes=54))
            _write(root, BASE)
            _write(root, BASE + timedelta(hours=2), slot_override="not-an-hour")
            result = resolve_observation_hour_adjacency(repo, _commit(repo), _slot(BASE))
            self.assertEqual(result["resolution_status"], "candidate-set-unorderable")

    def test_dependency_drift_fails_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo, root = _repo(tmp)
            _write(root, BASE)
            config = repo / PINNED_REFS["config"]["path"]
            config.write_text(config.read_text(encoding="utf-8") + "\n# drift\n", encoding="utf-8")
            result = resolve_observation_hour_adjacency(repo, _commit(repo), _slot(BASE))
            self.assertEqual(result["resolution_status"], "validation-contract-mismatch")
            self.assertNotEqual(
                result["repository_context"]["config"]["git_blob_sha"],
                PINNED_REFS["config"]["git_blob_sha"],
            )


if __name__ == "__main__":
    unittest.main()
