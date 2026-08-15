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

from build_crypto_snapshot_comparison_record import (  # noqa: E402
    CONFIG_BLOB_SHA,
    VALIDATOR_BLOB_SHA,
    build_comparison_record,
)
from validate_crypto_snapshot_comparison import (  # noqa: E402
    ComparisonValidationError,
    comparison_id_for_record,
    validate_comparison_record,
)

FIXTURES = ROOT / "tests" / "fixtures"
SYDNEY = ZoneInfo("Australia/Sydney")
PRODUCER = "scripts/ingest_crypto_sources.py"


def _git(repo: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return completed.stdout.strip()


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
    producer: str | None = PRODUCER,
    cadence: str = "hourly",
) -> dict:
    payload = copy.deepcopy(_fixture(fixture_name))
    when = when.astimezone(timezone.utc).replace(microsecond=0)
    utc_text = _utc_text(when)
    local = when.astimezone(SYDNEY)
    payload["schema_version"] = schema_version
    payload["run"]["generated_at_utc"] = utc_text
    payload["run"]["generated_at_local"] = local.isoformat()
    payload["run"]["timezone"] = "Australia/Sydney"
    payload["run"]["cadence"] = cadence
    if producer is None:
        payload["run"].pop("producer", None)
    else:
        payload["run"]["producer"] = producer
    for source in payload["sources"].values():
        if isinstance(source, dict) and "fetched_at_utc" in source:
            source["fetched_at_utc"] = utc_text
    for asset in payload["market"]["assets"]:
        asset["last_updated"] = utc_text
    return payload


def _snapshot_path(repo: Path, when: datetime, *, minute_offset: int = 0) -> Path:
    local = (when + timedelta(minutes=minute_offset)).astimezone(SYDNEY)
    tz_name = local.tzname() or "LOCAL"
    safe_tz = "".join(ch for ch in tz_name if ch.isalnum()) or "LOCAL"
    return (
        repo
        / "data"
        / "crypto"
        / "hourly"
        / f"{local.year:04d}"
        / f"{local.month:02d}"
        / f"{local.day:02d}"
        / f"{local.hour:02d}{local.minute:02d}_{safe_tz}_source_snapshot.json"
    )


def _write_snapshot(
    repo: Path,
    when: datetime,
    *,
    payload: dict | None = None,
    fixture_name: str = "valid_ok_snapshot.json",
    schema_version: str = "0.2",
    producer: str | None = PRODUCER,
    cadence: str = "hourly",
    path_override: Path | None = None,
) -> Path:
    payload = payload or _payload_at(
        when,
        fixture_name=fixture_name,
        schema_version=schema_version,
        producer=producer,
        cadence=cadence,
    )
    path = path_override or _snapshot_path(repo, when)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    return path


class ComparisonRecordTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.repo = Path(self.tempdir.name)
        _git(self.repo, "init", "-q")
        _git(self.repo, "config", "user.email", "phase10-tests@example.invalid")
        _git(self.repo, "config", "user.name", "Phase 10 tests")
        (self.repo / "scripts").mkdir(parents=True)
        (self.repo / "config").mkdir(parents=True)
        (self.repo / "scripts" / "validate_crypto_snapshot.py").write_bytes(
            (ROOT / "scripts" / "validate_crypto_snapshot.py").read_bytes()
        )
        (self.repo / "config" / "crypto_sources.yml").write_bytes(
            (ROOT / "config" / "crypto_sources.yml").read_bytes()
        )
        self.current_time = datetime(2026, 7, 8, 5, 0, tzinfo=timezone.utc)

        self.assertEqual(
            _git(self.repo, "hash-object", "scripts/validate_crypto_snapshot.py"),
            VALIDATOR_BLOB_SHA,
        )
        self.assertEqual(
            _git(self.repo, "hash-object", "config/crypto_sources.yml"),
            CONFIG_BLOB_SHA,
        )

    def commit(self, message: str = "fixture") -> str:
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", message)
        return _git(self.repo, "rev-parse", "HEAD")

    def pair(
        self,
        *,
        current_fixture: str = "valid_ok_snapshot.json",
        predecessor_fixture: str = "valid_ok_snapshot.json",
        gap_seconds: int = 3600,
        current_schema: str = "0.2",
        predecessor_schema: str = "0.2",
        current_producer: str | None = PRODUCER,
        predecessor_producer: str | None = PRODUCER,
        current_cadence: str = "hourly",
        predecessor_cadence: str = "hourly",
    ) -> tuple[Path, Path]:
        predecessor_time = self.current_time - timedelta(seconds=gap_seconds)
        predecessor = _write_snapshot(
            self.repo,
            predecessor_time,
            fixture_name=predecessor_fixture,
            schema_version=predecessor_schema,
            producer=predecessor_producer,
            cadence=predecessor_cadence,
        )
        current = _write_snapshot(
            self.repo,
            self.current_time,
            fixture_name=current_fixture,
            schema_version=current_schema,
            producer=current_producer,
            cadence=current_cadence,
        )
        return current, predecessor

    def build(self, commit: str, current: Path) -> dict:
        return build_comparison_record(
            self.repo,
            commit,
            current.relative_to(self.repo).as_posix(),
        )

    def test_exact_hour_pair_is_comparison_ready_and_deterministic(self) -> None:
        current, _ = self.pair()
        commit = self.commit()
        first = self.build(commit, current)
        second = self.build(commit, current)

        self.assertEqual(first, second)
        self.assertEqual(first["comparison_status"], "comparison-ready")
        self.assertEqual(first["elapsed_seconds"], 3600)
        self.assertEqual(first["current"]["schema_version"], "0.2")
        self.assertEqual(first["predecessor"]["schema_version"], "0.2")
        self.assertEqual(first["metric_comparisons"], [])
        self.assertEqual(first["source_availability_changes"], [])
        validate_comparison_record(first)

    def test_valid_degraded_inputs_are_preserved(self) -> None:
        for side in ("current", "predecessor"):
            with self.subTest(side=side):
                with tempfile.TemporaryDirectory() as nested:
                    repo = Path(nested)
                    _git(repo, "init", "-q")
                    _git(repo, "config", "user.email", "phase10-tests@example.invalid")
                    _git(repo, "config", "user.name", "Phase 10 tests")
                    (repo / "scripts").mkdir(parents=True)
                    (repo / "config").mkdir(parents=True)
                    (repo / "scripts" / "validate_crypto_snapshot.py").write_bytes(
                        (ROOT / "scripts" / "validate_crypto_snapshot.py").read_bytes()
                    )
                    (repo / "config" / "crypto_sources.yml").write_bytes(
                        (ROOT / "config" / "crypto_sources.yml").read_bytes()
                    )
                    pred_fixture = (
                        "valid_degraded_optional_source_warning.json"
                        if side == "predecessor"
                        else "valid_ok_snapshot.json"
                    )
                    cur_fixture = (
                        "valid_degraded_optional_source_warning.json"
                        if side == "current"
                        else "valid_ok_snapshot.json"
                    )
                    predecessor = _write_snapshot(
                        repo, self.current_time - timedelta(hours=1), fixture_name=pred_fixture
                    )
                    current = _write_snapshot(repo, self.current_time, fixture_name=cur_fixture)
                    _git(repo, "add", "-A")
                    _git(repo, "commit", "-q", "-m", "fixture")
                    commit = _git(repo, "rev-parse", "HEAD")
                    record = build_comparison_record(
                        repo, commit, current.relative_to(repo).as_posix()
                    )
                    self.assertEqual(record["comparison_status"], "comparison-ready")
                    self.assertEqual(record[side]["quality_status"], "valid-degraded")
                    self.assertTrue(record[side]["non_blocking_warnings"])
                    self.assertTrue(predecessor.exists())

    def test_validator_or_config_blob_mismatch_fails_contract(self) -> None:
        for index, path in enumerate((
            "scripts/validate_crypto_snapshot.py",
            "config/crypto_sources.yml",
        )):
            with self.subTest(path=path):
                if index:
                    self.setUp()
                current, _ = self.pair()
                target = self.repo / path
                target.write_bytes(target.read_bytes() + b"\n# drift\n")
                commit = self.commit()
                record = self.build(commit, current)
                self.assertEqual(record["comparison_status"], "validation-contract-mismatch")
                validate_comparison_record(record)

    def test_absent_or_outside_current_path_fails_identity(self) -> None:
        current, _ = self.pair()
        commit = self.commit()
        missing = "data/crypto/hourly/2099/01/01/0000_AEDT_source_snapshot.json"
        record = build_comparison_record(self.repo, commit, missing)
        self.assertEqual(record["comparison_status"], "current-identity-invalid")

        outside = build_comparison_record(self.repo, commit, "tests/current_source_snapshot.json")
        self.assertEqual(outside["comparison_status"], "current-identity-invalid")
        self.assertTrue(current.exists())

    def test_slice1_current_invalid_and_candidate_unorderable_propagate(self) -> None:
        predecessor_time = self.current_time - timedelta(hours=1)
        _write_snapshot(self.repo, predecessor_time)
        payload = _payload_at(self.current_time)
        payload["sources"]["coingecko"]["status"] = "error"
        current = _write_snapshot(self.repo, self.current_time, payload=payload)
        commit = self.commit("current invalid")
        self.assertEqual(self.build(commit, current)["comparison_status"], "current-invalid")

        with tempfile.TemporaryDirectory() as nested:
            repo = Path(nested)
            _git(repo, "init", "-q")
            _git(repo, "config", "user.email", "phase10-tests@example.invalid")
            _git(repo, "config", "user.name", "Phase 10 tests")
            (repo / "scripts").mkdir(parents=True)
            (repo / "config").mkdir(parents=True)
            (repo / "scripts" / "validate_crypto_snapshot.py").write_bytes(
                (ROOT / "scripts" / "validate_crypto_snapshot.py").read_bytes()
            )
            (repo / "config" / "crypto_sources.yml").write_bytes(
                (ROOT / "config" / "crypto_sources.yml").read_bytes()
            )
            current = _write_snapshot(repo, self.current_time)
            malformed = _snapshot_path(repo, self.current_time - timedelta(hours=2))
            malformed.parent.mkdir(parents=True, exist_ok=True)
            malformed.write_text("{not-json", encoding="utf-8")
            _git(repo, "add", "-A")
            _git(repo, "commit", "-q", "-m", "unorderable")
            commit = _git(repo, "rev-parse", "HEAD")
            record = build_comparison_record(repo, commit, current.relative_to(repo).as_posix())
            self.assertEqual(record["comparison_status"], "candidate-set-unorderable")

    def test_slice1_predecessor_missing_propagates(self) -> None:
        current = _write_snapshot(self.repo, self.current_time)
        commit = self.commit("predecessor missing")
        self.assertEqual(self.build(commit, current)["comparison_status"], "predecessor-missing")

    def test_predecessor_ambiguous_invalid_identity_and_window_propagate(self) -> None:
        pred_time = self.current_time - timedelta(hours=1)
        payload = _payload_at(pred_time)
        _write_snapshot(self.repo, pred_time, payload=payload)
        duplicate = self.repo / "data/crypto/hourly/2026/07/08/duplicate_source_snapshot.json"
        _write_snapshot(self.repo, pred_time, payload=payload, path_override=duplicate)
        current = _write_snapshot(self.repo, self.current_time)
        commit = self.commit("ambiguous")
        self.assertEqual(self.build(commit, current)["comparison_status"], "predecessor-ambiguous")

        self.setUp()
        pred_payload = _payload_at(pred_time)
        pred_payload["sources"]["coingecko"]["status"] = "error"
        _write_snapshot(self.repo, pred_time, payload=pred_payload)
        current = _write_snapshot(self.repo, self.current_time)
        commit = self.commit("invalid predecessor")
        self.assertEqual(self.build(commit, current)["comparison_status"], "predecessor-invalid")

        self.setUp()
        wrong_path = _snapshot_path(self.repo, pred_time, minute_offset=-1)
        _write_snapshot(self.repo, pred_time, path_override=wrong_path)
        current = _write_snapshot(self.repo, self.current_time)
        commit = self.commit("identity mismatch")
        self.assertEqual(
            self.build(commit, current)["comparison_status"], "predecessor-identity-invalid"
        )

        self.setUp()
        current, _ = self.pair(gap_seconds=3599)
        commit = self.commit("out of window")
        record = self.build(commit, current)
        self.assertEqual(record["comparison_status"], "predecessor-out-of-window")
        self.assertEqual(record["elapsed_seconds"], 3599)

    def test_schema_mismatch_and_equal_non_02_are_distinct(self) -> None:
        current, _ = self.pair(predecessor_schema="0.1")
        commit = self.commit("schema mismatch")
        self.assertEqual(self.build(commit, current)["comparison_status"], "pair-schema-incompatible")

        self.setUp()
        current, _ = self.pair(current_schema="0.1", predecessor_schema="0.1")
        commit = self.commit("equal old schema")
        self.assertEqual(self.build(commit, current)["comparison_status"], "pair-semantics-incompatible")

    def test_producer_and_cadence_semantics_fail_closed(self) -> None:
        cases = [
            {"current_producer": None},
            {"predecessor_producer": None},
            {"current_producer": "other.py"},
            {"predecessor_cadence": "daily"},
        ]
        for index, kwargs in enumerate(cases):
            with self.subTest(case=index):
                if index:
                    self.setUp()
                current, _ = self.pair(**kwargs)
                commit = self.commit(f"semantics {index}")
                self.assertEqual(
                    self.build(commit, current)["comparison_status"],
                    "pair-semantics-incompatible",
                )

    def test_duplicate_symbols_and_unknown_source_fail_closed(self) -> None:
        mutations = []

        def duplicate_asset(payload: dict) -> None:
            payload["market"]["assets"].append(copy.deepcopy(payload["market"]["assets"][0]))

        def duplicate_stablecoin(payload: dict) -> None:
            payload["defi"]["stablecoins"].append(
                copy.deepcopy(payload["defi"]["stablecoins"][0])
            )

        def unknown_source(payload: dict) -> None:
            payload["sources"]["future_source"] = {"status": "skipped", "reason": "fixture"}

        mutations.extend([duplicate_asset, duplicate_stablecoin, unknown_source])
        for index, mutate in enumerate(mutations):
            with self.subTest(case=index):
                if index:
                    self.setUp()
                _write_snapshot(self.repo, self.current_time - timedelta(hours=1))
                payload = _payload_at(self.current_time)
                mutate(payload)
                current = _write_snapshot(self.repo, self.current_time, payload=payload)
                commit = self.commit(f"identity {index}")
                self.assertEqual(
                    self.build(commit, current)["comparison_status"],
                    "pair-semantics-incompatible",
                )

    def test_unsupported_extra_fields_do_not_become_comparison_output(self) -> None:
        _write_snapshot(self.repo, self.current_time - timedelta(hours=1))
        payload = _payload_at(self.current_time)
        payload["market"]["assets"][0]["future_metric"] = 123
        payload["defi"]["stablecoins"][0]["future_metric"] = 456
        current = _write_snapshot(self.repo, self.current_time, payload=payload)
        commit = self.commit()
        record = self.build(commit, current)
        self.assertEqual(record["comparison_status"], "comparison-ready")
        self.assertEqual(record["metric_comparisons"], [])
        self.assertEqual(record["source_availability_changes"], [])

    def test_untracked_files_and_filesystem_order_cannot_change_commit_result(self) -> None:
        current, _ = self.pair()
        commit = self.commit()
        first = self.build(commit, current)
        _write_snapshot(self.repo, self.current_time + timedelta(hours=1))
        second = self.build(commit, current)
        self.assertEqual(first, second)

    def test_changed_immutable_context_changes_comparison_id(self) -> None:
        current, _ = self.pair()
        first_commit = self.commit("first context")
        first = self.build(first_commit, current)
        (self.repo / "context-marker.txt").write_text("context two\n", encoding="utf-8")
        second_commit = self.commit("second context")
        second = self.build(second_commit, current)
        self.assertEqual(first["current"]["sha256"], second["current"]["sha256"])
        self.assertEqual(first["predecessor"]["sha256"], second["predecessor"]["sha256"])
        self.assertNotEqual(first["repository_context"]["commit_sha"], second["repository_context"]["commit_sha"])
        self.assertNotEqual(first["comparison_id"], second["comparison_id"])

    def test_tamper_and_recomputed_illegal_record_are_rejected(self) -> None:
        current, _ = self.pair()
        commit = self.commit()
        record = self.build(commit, current)

        tampered = copy.deepcopy(record)
        tampered["elapsed_seconds"] = 1
        with self.assertRaises(ComparisonValidationError):
            validate_comparison_record(tampered)

        illegal = copy.deepcopy(record)
        illegal["elapsed_seconds"] = 1
        illegal["comparison_id"] = comparison_id_for_record(illegal)
        with self.assertRaises(ComparisonValidationError):
            validate_comparison_record(illegal)

    def test_slice2_rejects_adapter_output_and_comparison_available(self) -> None:
        current, _ = self.pair()
        commit = self.commit()
        record = self.build(commit, current)

        for field in ("metric_comparisons", "source_availability_changes"):
            illegal = copy.deepcopy(record)
            illegal[field] = [{"not": "authorised"}]
            illegal["comparison_id"] = comparison_id_for_record(illegal)
            with self.assertRaises(ComparisonValidationError):
                validate_comparison_record(illegal)

        premature = copy.deepcopy(record)
        premature["comparison_status"] = "comparison-available"
        premature["comparison_id"] = comparison_id_for_record(premature)
        with self.assertRaises(ComparisonValidationError):
            validate_comparison_record(premature)


if __name__ == "__main__":
    unittest.main()
