from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_crypto_snapshot_comparison_record import build_comparison_record  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "valid_ok_snapshot.json"
SYDNEY = ZoneInfo("Australia/Sydney")
PRODUCER = "scripts/ingest_crypto_sources.py"


def _git(repository: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repository), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return completed.stdout.strip()


def _payload_at(when: datetime) -> dict:
    payload = copy.deepcopy(json.loads(FIXTURE.read_text(encoding="utf-8")))
    when = when.astimezone(timezone.utc).replace(microsecond=0)
    utc_text = when.isoformat().replace("+00:00", "Z")
    local = when.astimezone(SYDNEY)

    payload["schema_version"] = "0.2"
    payload["run"]["generated_at_utc"] = utc_text
    payload["run"]["generated_at_local"] = local.isoformat()
    payload["run"]["timezone"] = "Australia/Sydney"
    payload["run"]["timezone_abbreviation"] = local.tzname()
    payload["run"]["cadence"] = "hourly"
    payload["run"]["producer"] = PRODUCER

    for source in payload["sources"].values():
        if isinstance(source, dict) and "fetched_at_utc" in source:
            source["fetched_at_utc"] = utc_text
    for asset in payload["market"]["assets"]:
        asset["last_updated"] = utc_text
    return payload


def _snapshot_path(repository: Path, when: datetime) -> Path:
    local = when.astimezone(SYDNEY)
    abbreviation = local.tzname() or "LOCAL"
    safe_abbreviation = "".join(ch for ch in abbreviation if ch.isalnum()) or "LOCAL"
    return (
        repository
        / "data"
        / "crypto"
        / "hourly"
        / f"{local.year:04d}"
        / f"{local.month:02d}"
        / f"{local.day:02d}"
        / f"{local.hour:02d}{local.minute:02d}_{safe_abbreviation}_source_snapshot.json"
    )


def _write_snapshot(repository: Path, when: datetime, payload: dict) -> Path:
    path = _snapshot_path(repository, when)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    return path


def _build_pair(mutator=None, mutated_side: str = "current") -> dict:
    with tempfile.TemporaryDirectory() as temporary:
        repository = Path(temporary)
        _git(repository, "init", "-q")
        _git(repository, "config", "user.email", "phase10-tests@example.invalid")
        _git(repository, "config", "user.name", "Phase 10 tests")

        (repository / "scripts").mkdir(parents=True)
        (repository / "config").mkdir(parents=True)
        (repository / "scripts" / "validate_crypto_snapshot.py").write_bytes(
            (ROOT / "scripts" / "validate_crypto_snapshot.py").read_bytes()
        )
        (repository / "config" / "crypto_sources.yml").write_bytes(
            (ROOT / "config" / "crypto_sources.yml").read_bytes()
        )

        current_time = datetime(2026, 7, 8, 5, 0, tzinfo=timezone.utc)
        predecessor_time = current_time - timedelta(hours=1)
        current_payload = _payload_at(current_time)
        predecessor_payload = _payload_at(predecessor_time)

        if mutator is not None:
            target = current_payload if mutated_side == "current" else predecessor_payload
            mutator(target)

        _write_snapshot(repository, predecessor_time, predecessor_payload)
        current_path = _write_snapshot(repository, current_time, current_payload)
        _git(repository, "add", "-A")
        _git(repository, "commit", "-q", "-m", "phase10 semantic fixture")
        commit = _git(repository, "rev-parse", "HEAD")

        return build_comparison_record(
            repository,
            commit,
            current_path.relative_to(repository).as_posix(),
        )


class UnknownSemanticIdentityTests(unittest.TestCase):
    def test_supported_identity_sets_remain_comparison_available(self) -> None:
        record = _build_pair()
        self.assertEqual(record["comparison_status"], "comparison-available")

    def test_unknown_market_asset_fails_closed_on_either_side(self) -> None:
        def add_unknown_asset(payload: dict) -> None:
            extra = copy.deepcopy(payload["market"]["assets"][0])
            extra["id"] = "ripple"
            extra["symbol"] = "XRP"
            payload["market"]["assets"].append(extra)

        for side in ("current", "predecessor"):
            with self.subTest(side=side):
                record = _build_pair(add_unknown_asset, side)
                self.assertEqual(record["comparison_status"], "pair-semantics-incompatible")
                self.assertEqual(record["metric_comparisons"], [])
                self.assertEqual(record["source_availability_changes"], [])

    def test_unknown_stablecoin_fails_closed_on_either_side(self) -> None:
        def add_unknown_stablecoin(payload: dict) -> None:
            extra = copy.deepcopy(payload["defi"]["stablecoins"][0])
            extra["id"] = "dai"
            extra["symbol"] = "DAI"
            payload["defi"]["stablecoins"].append(extra)

        for side in ("current", "predecessor"):
            with self.subTest(side=side):
                record = _build_pair(add_unknown_stablecoin, side)
                self.assertEqual(record["comparison_status"], "pair-semantics-incompatible")
                self.assertEqual(record["metric_comparisons"], [])
                self.assertEqual(record["source_availability_changes"], [])


if __name__ == "__main__":
    unittest.main()
