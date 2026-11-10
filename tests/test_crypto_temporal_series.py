from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from crypto_temporal_series import (  # noqa: E402
    GAP_REASONS,
    MAX_SLOTS,
    METRIC_GAP_MAP,
    METRIC_IDENTITIES,
    PHASE10_GAP_MAP,
    SERIES_SCHEMA_VERSION,
    SOURCE_IDENTITIES,
    SOURCE_STATUSES,
    TemporalSeriesError,
    _entry_for_unique_candidate,
    build_temporal_series,
    canonical_json_bytes,
    series_id_for_record,
    validate_temporal_series,
)
from validate_crypto_snapshot_comparison import (  # noqa: E402
    CONFIG_BLOB_SHA,
    CONFIG_PATH,
    VALIDATOR_BLOB_SHA,
    VALIDATOR_PATH,
)

CORPUS_PATH = ROOT / "tests" / "fixtures" / "phase10_comparison_proof_v1.json"
BASE_CASE = "01-comparison-available-mixed-evidence"
INVALID_CASE = "04-current-invalid"


def _git(
    repository: Path,
    *args: str,
    input_bytes: bytes | None = None,
    extra_env: dict[str, str] | None = None,
) -> bytes:
    env = os.environ.copy()
    env.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_OPTIONAL_LOCKS": "0", "LC_ALL": "C"})
    if extra_env:
        env.update(extra_env)
    completed = subprocess.run(
        ["git", "-C", str(repository), *args],
        check=False,
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise AssertionError(detail or f"git {' '.join(args)} failed")
    return completed.stdout


def _text(raw: bytes) -> str:
    return raw.decode("utf-8", errors="strict").strip()


def _canonical_utc(text: str) -> str:
    value = text[:-1] + "+00:00" if text.endswith("Z") else text
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class TemporalSeriesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.corpus = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))

    def _case_files(self, case_id: str) -> dict[str, str]:
        case = self.corpus["cases"][case_id]
        files = dict(case["repository_files"])
        files.update(case.get("contract_override", {}))
        return files

    def _seed_repository(
        self,
        case_id: str = BASE_CASE,
        *,
        extra_files: dict[str, str] | None = None,
    ) -> tuple[tempfile.TemporaryDirectory[str], Path, str]:
        temporary = tempfile.TemporaryDirectory(prefix="phase11-series-")
        repository = Path(temporary.name)
        _git(repository, "init", "-q")

        files = {
            VALIDATOR_PATH: (ROOT / VALIDATOR_PATH).read_text(encoding="utf-8"),
            CONFIG_PATH: (ROOT / CONFIG_PATH).read_text(encoding="utf-8"),
        }
        files.update(self._case_files(case_id))
        if extra_files:
            files.update(extra_files)

        self.assertEqual(
            _text(_git(repository, "hash-object", "--stdin", input_bytes=files[VALIDATOR_PATH].encode())),
            VALIDATOR_BLOB_SHA,
        )
        self.assertEqual(
            _text(_git(repository, "hash-object", "--stdin", input_bytes=files[CONFIG_PATH].encode())),
            CONFIG_BLOB_SHA,
        )

        for path in sorted(files):
            blob = _text(_git(repository, "hash-object", "-w", "--stdin", input_bytes=files[path].encode()))
            _git(repository, "update-index", "--add", "--cacheinfo", f"100644,{blob},{path}")
        tree = _text(_git(repository, "write-tree"))
        seed = self.corpus["seed_commit"]
        env = {
            "GIT_AUTHOR_NAME": seed["author_name"],
            "GIT_AUTHOR_EMAIL": seed["author_email"],
            "GIT_AUTHOR_DATE": seed["author_date"],
            "GIT_COMMITTER_NAME": seed["committer_name"],
            "GIT_COMMITTER_EMAIL": seed["committer_email"],
            "GIT_COMMITTER_DATE": seed["committer_date"],
        }
        commit = _text(
            _git(
                repository,
                "-c",
                "commit.gpgsign=false",
                "commit-tree",
                tree,
                input_bytes=(seed["message"] + "\n").encode(),
                extra_env=env,
            )
        )
        return temporary, repository, commit

    def _slot_for_case(self, case_id: str = BASE_CASE) -> str:
        case = self.corpus["cases"][case_id]
        raw = case["repository_files"][case["current_repository_path"]]
        payload = json.loads(raw)
        return _canonical_utc(payload["run"]["generated_at_utc"])

    def _build_one(self, case_id: str = BASE_CASE, kind: str = "metric", key: str = "BTC.price_usd"):
        temporary, repository, commit = self._seed_repository(case_id)
        slot = self._slot_for_case(case_id)
        record = build_temporal_series(repository, commit, kind, key, slot, slot)
        return temporary, repository, commit, record

    def test_contract_vocabulary_is_exact_and_closed(self) -> None:
        self.assertEqual(SERIES_SCHEMA_VERSION, "crypto-temporal-series/v1")
        self.assertEqual(len(METRIC_IDENTITIES), 12)
        self.assertEqual(len(SOURCE_IDENTITIES), 8)
        self.assertEqual(SOURCE_STATUSES, {"ok", "warning", "error", "skipped", "missing"})
        self.assertEqual(
            PHASE10_GAP_MAP,
            {
                "validation-contract-mismatch": "phase10-validation-contract-mismatch",
                "current-invalid": "phase10-current-invalid",
                "current-identity-invalid": "phase10-current-identity-invalid",
                "candidate-set-unorderable": "phase10-candidate-set-unorderable",
                "predecessor-missing": "phase10-predecessor-missing",
                "predecessor-ambiguous": "phase10-predecessor-ambiguous",
                "predecessor-invalid": "phase10-predecessor-invalid",
                "predecessor-identity-invalid": "phase10-predecessor-identity-invalid",
                "predecessor-out-of-window": "phase10-predecessor-out-of-window",
                "pair-schema-incompatible": "phase10-pair-schema-incompatible",
                "pair-semantics-incompatible": "phase10-pair-semantics-incompatible",
                "comparison-ready": "phase10-comparison-ready",
            },
        )
        self.assertEqual(
            METRIC_GAP_MAP,
            {
                "unavailable-current": "metric-unavailable-current",
                "unavailable-predecessor": "metric-unavailable-predecessor",
                "invalid-current": "metric-invalid-current",
                "invalid-predecessor": "metric-invalid-predecessor",
            },
        )
        self.assertEqual(len(GAP_REASONS), 18)

    def test_window_boundaries_and_invalid_windows_fail_closed(self) -> None:
        temporary, repository, commit = self._seed_repository()
        try:
            start = self._slot_for_case()
            start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
            end = (start_dt + timedelta(hours=MAX_SLOTS - 1)).isoformat().replace("+00:00", "Z")
            record = build_temporal_series(repository, commit, "metric", "BTC.price_usd", start, end)
            self.assertEqual(len(record["entries"]), MAX_SLOTS)
            self.assertEqual(record["entries"][0]["slot_utc"], start)
            self.assertEqual(record["entries"][-1]["slot_utc"], end)
        finally:
            temporary.cleanup()

        bad = [
            ("2026-07-08T05:30:00Z", "2026-07-08T06:00:00Z"),
            ("2026-07-08T06:00:00Z", "2026-07-08T05:00:00Z"),
            ("2026-07-08T00:00:00Z", "2026-07-15T00:00:00Z"),
        ]
        for start, end in bad:
            with self.subTest(start=start, end=end):
                with self.assertRaises(TemporalSeriesError):
                    build_temporal_series(Path("."), "0" * 40, "metric", "BTC.price_usd", start, end)

    def test_all_supported_metric_and_source_series_build_and_unknowns_reject(self) -> None:
        temporary, repository, commit = self._seed_repository()
        slot = self._slot_for_case()
        try:
            for key in METRIC_IDENTITIES:
                with self.subTest(metric=key):
                    record = build_temporal_series(repository, commit, "metric", key, slot, slot)
                    self.assertEqual(record["series_key"], key)
                    validate_temporal_series(repository, record)
            for key in SOURCE_IDENTITIES:
                with self.subTest(source=key):
                    record = build_temporal_series(repository, commit, "source-status", key, slot, slot)
                    self.assertEqual(record["series_key"], key)
                    entry = record["entries"][0]
                    if entry["value"] is not None:
                        self.assertIn(entry["value"]["datum"], SOURCE_STATUSES)
                        self.assertEqual(entry["value"]["datum"], entry["value"]["evidence"]["current_status"])
                    validate_temporal_series(repository, record)
        finally:
            temporary.cleanup()
        with self.assertRaises(TemporalSeriesError):
            build_temporal_series(Path("."), "0" * 40, "metric", "BTC.change_24h_pct", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z")
        with self.assertRaises(TemporalSeriesError):
            build_temporal_series(Path("."), "0" * 40, "source-status", "unknown", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z")

    def test_missing_and_ambiguous_current_are_explicit_and_deterministic(self) -> None:
        temporary, repository, commit = self._seed_repository()
        try:
            current = datetime.fromisoformat(self._slot_for_case().replace("Z", "+00:00"))
            missing = (current + timedelta(hours=1)).isoformat().replace("+00:00", "Z")
            record = build_temporal_series(repository, commit, "metric", "BTC.price_usd", missing, missing)
            self.assertEqual(record["entries"][0]["gap"], {"reason": "current-missing", "current_candidates": []})
        finally:
            temporary.cleanup()

        case = self.corpus["cases"][BASE_CASE]
        duplicate_raw = case["repository_files"][case["current_repository_path"]]
        duplicate_path = "data/crypto/hourly/9999/01/01/0000_DUP_source_snapshot.json"
        temporary, repository, commit = self._seed_repository(extra_files={duplicate_path: duplicate_raw})
        try:
            slot = self._slot_for_case()
            first = build_temporal_series(repository, commit, "metric", "BTC.price_usd", slot, slot)
            second = build_temporal_series(repository, commit, "metric", "BTC.price_usd", slot, slot)
            candidates = first["entries"][0]["gap"]["current_candidates"]
            self.assertEqual(first["entries"][0]["gap"]["reason"], "current-ambiguous")
            self.assertEqual(len(candidates), 2)
            self.assertEqual(candidates, sorted(candidates, key=lambda item: (item["path"], item["sha256"])))
            self.assertEqual(canonical_json_bytes(first), canonical_json_bytes(second))
        finally:
            temporary.cleanup()

    def test_unorderable_candidate_fails_before_slot_classification(self) -> None:
        bad_path = "data/crypto/hourly/9999/01/01/0000_BAD_source_snapshot.json"
        temporary, repository, commit = self._seed_repository(extra_files={bad_path: "not-json"})
        try:
            with self.assertRaises(TemporalSeriesError):
                build_temporal_series(
                    repository,
                    commit,
                    "metric",
                    "BTC.price_usd",
                    "2099-01-01T00:00:00Z",
                    "2099-01-01T00:00:00Z",
                )
        finally:
            temporary.cleanup()

    def test_raw_snapshot_value_never_bypasses_phase10_failure(self) -> None:
        temporary, repository, commit = self._seed_repository(INVALID_CASE)
        try:
            slot = self._slot_for_case(INVALID_CASE)
            record = build_temporal_series(repository, commit, "metric", "BTC.price_usd", slot, slot)
            entry = record["entries"][0]
            self.assertIsNone(entry["value"])
            self.assertEqual(entry["gap"]["reason"], "phase10-current-invalid")
        finally:
            temporary.cleanup()

    def test_metric_gap_mapping_and_comparison_precedence(self) -> None:
        base_record = {
            "comparison_status": "comparison-available",
            "comparison_id": "a" * 64,
            "current": {"quality_status": "valid-ok", "non_blocking_warnings": []},
            "predecessor": {"quality_status": "valid-ok", "non_blocking_warnings": []},
            "metric_comparisons": [],
            "source_availability_changes": [],
        }
        identity = METRIC_IDENTITIES["BTC.price_usd"]
        for state, reason in METRIC_GAP_MAP.items():
            with self.subTest(state=state):
                record = copy.deepcopy(base_record)
                record["metric_comparisons"] = [
                    {
                        "family": identity[0],
                        "symbol": identity[1],
                        "field": identity[2],
                        "current": {"present": True, "value": 1},
                        "predecessor": {"present": True, "value": 1},
                        "comparison_state": state,
                        "relation": None,
                    }
                ]
                with mock.patch("crypto_temporal_series.build_comparison_record", return_value=record):
                    entry = _entry_for_unique_candidate(
                        Path("."), "0" * 40, "metric", "BTC.price_usd", datetime(2026, 1, 1, tzinfo=timezone.utc), {"path": "x"}
                    )
                self.assertEqual(entry["gap"]["reason"], reason)

        failed = copy.deepcopy(base_record)
        failed["comparison_status"] = "current-invalid"
        failed["metric_comparisons"] = [
            {
                "family": identity[0], "symbol": identity[1], "field": identity[2],
                "current": {"present": True, "value": 999},
                "predecessor": {"present": True, "value": 1},
                "comparison_state": "comparable", "relation": "current-greater",
            }
        ]
        with mock.patch("crypto_temporal_series.build_comparison_record", return_value=failed):
            entry = _entry_for_unique_candidate(
                Path("."), "0" * 40, "metric", "BTC.price_usd", datetime(2026, 1, 1, tzinfo=timezone.utc), {"path": "x"}
            )
        self.assertEqual(entry["gap"]["reason"], "phase10-current-invalid")

    def test_current_and_predecessor_degraded_evidence_remain_side_specific(self) -> None:
        temporary, repository, commit, record = self._build_one()
        try:
            value = record["entries"][0]["value"]
            self.assertEqual(value["current"]["quality_status"], "valid-degraded")
            self.assertTrue(value["current"]["non_blocking_warnings"])
            self.assertEqual(value["predecessor"]["quality_status"], "valid-ok")
            self.assertEqual(value["predecessor"]["non_blocking_warnings"], [])
        finally:
            temporary.cleanup()

        case = self.corpus["cases"][BASE_CASE]
        predecessor_path = sorted(case["repository_files"])[0]
        valid_raw = json.loads(case["repository_files"][predecessor_path])
        valid_raw["run"]["generated_at_utc"] = "2026-07-08T06:00:00Z"
        valid_raw["run"]["generated_at_local"] = "2026-07-08T16:00:00+10:00"
        for asset in valid_raw["market"]["assets"]:
            asset["last_updated"] = "2026-07-08T06:00:00Z"
        for source in valid_raw["sources"].values():
            if isinstance(source, dict) and "fetched_at_utc" in source:
                source["fetched_at_utc"] = "2026-07-08T06:00:00Z"
        third_path = "data/crypto/hourly/2026/07/08/1600_AEST_source_snapshot.json"
        third_raw = json.dumps(valid_raw, sort_keys=True, separators=(",", ":"))
        temporary, repository, commit = self._seed_repository(extra_files={third_path: third_raw})
        try:
            record = build_temporal_series(repository, commit, "metric", "BTC.price_usd", "2026-07-08T06:00:00Z", "2026-07-08T06:00:00Z")
            value = record["entries"][0]["value"]
            self.assertEqual(value["current"]["quality_status"], "valid-ok")
            self.assertEqual(value["predecessor"]["quality_status"], "valid-degraded")
            self.assertTrue(value["predecessor"]["non_blocking_warnings"])
        finally:
            temporary.cleanup()

    def test_repository_identity_series_id_repeatability_and_replay_validation(self) -> None:
        temporary, repository, commit = self._seed_repository()
        slot = self._slot_for_case()
        try:
            first = build_temporal_series(repository, commit, "metric", "BTC.price_usd", slot, slot)
            second = build_temporal_series(repository, commit, "metric", "BTC.price_usd", slot, slot)
            self.assertEqual(canonical_json_bytes(first), canonical_json_bytes(second))
            self.assertEqual(first["series_id"], series_id_for_record(first))
            self.assertEqual(first["repository_context"]["commit_sha"], commit)
            self.assertEqual(first["repository_context"]["validator"]["git_blob_sha"], VALIDATOR_BLOB_SHA)
            self.assertEqual(first["repository_context"]["config"]["git_blob_sha"], CONFIG_BLOB_SHA)
            validate_temporal_series(repository, first)

            tampered = copy.deepcopy(first)
            tampered["entries"][0]["value"]["datum"] = 123456789
            tampered["series_id"] = series_id_for_record(tampered)
            with self.assertRaises(TemporalSeriesError):
                validate_temporal_series(repository, tampered)

            warnings_tampered = copy.deepcopy(first)
            warnings_tampered["entries"][0]["value"]["current"]["non_blocking_warnings"] = []
            warnings_tampered["series_id"] = series_id_for_record(warnings_tampered)
            with self.assertRaises(TemporalSeriesError):
                validate_temporal_series(repository, warnings_tampered)

            extra = copy.deepcopy(first)
            extra["derived"] = 1
            extra["series_id"] = series_id_for_record(extra)
            with self.assertRaises(TemporalSeriesError):
                validate_temporal_series(repository, extra)
        finally:
            temporary.cleanup()


if __name__ == "__main__":
    unittest.main()
