from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest import mock
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_crypto_observation_hour_comparison_record import (  # noqa: E402
    COMPARISON_SCHEMA_VERSION,
    build_observation_hour_comparison,
    canonical_json_bytes as comparison_json_bytes,
)
from crypto_observation_hour_series import (  # noqa: E402
    COMPARISON_GAP_MAP,
    MAX_SLOTS,
    METRIC_GAP_MAP,
    METRIC_IDENTITIES,
    SERIES_SCHEMA_VERSION,
    SOURCE_IDENTITIES,
    ObservationHourSeriesError,
    _continuity,
    build_observation_hour_series,
    canonical_json_bytes as series_json_bytes,
    series_id_for_record,
    validate_observation_hour_series,
)
from resolve_crypto_observation_hour_adjacency import (  # noqa: E402
    ADJACENCY_POLICY_VERSION,
    OBSERVATION_HOUR_CONTRACT_VERSION,
    PINNED_REFS,
    SEMANTIC_CONTRACT_VERSION,
)

CORPUS_PATH = (
    ROOT / "tests" / "fixtures" / "phase13_observation_hour_temporal_proof_v1.json"
)


def _git(
    repository: Path,
    *args: str,
    input_bytes: bytes | None = None,
    extra_env: dict[str, str] | None = None,
) -> bytes:
    env = os.environ.copy()
    env.update(
        {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_OPTIONAL_LOCKS": "0",
            "LC_ALL": "C",
        }
    )
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


def _git_blob_sha(raw: bytes) -> str:
    header = f"blob {len(raw)}\0".encode("ascii")
    return hashlib.sha1(header + raw).hexdigest()


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _utc(value: datetime) -> str:
    return (
        value.astimezone(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _slot(value: datetime) -> str:
    return _utc(
        value.astimezone(timezone.utc).replace(
            minute=0, second=0, microsecond=0
        )
    )


class Phase13ObservationHourTemporalProofTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.corpus = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))

    def _fixture_bytes(self, alias: str) -> bytes:
        spec = self.corpus["materialisation"]["source_fixtures"][alias]
        raw = (ROOT / spec["path"]).read_bytes()
        self.assertEqual(_git_blob_sha(raw), spec["git_blob_sha"])
        return raw

    def _snapshot(self, spec: dict[str, Any]) -> tuple[str, bytes]:
        payload = copy.deepcopy(
            json.loads(self._fixture_bytes(spec.get("fixture", "ok")))
        )
        generated = _dt(spec["generated_at_utc"])
        zone = ZoneInfo(self.corpus["materialisation"]["timezone"])
        local = generated.astimezone(zone)
        run = payload["run"]
        run.update(
            {
                "generated_at_utc": _utc(generated),
                "generated_at_local": local.isoformat(),
                "timezone": zone.key,
                "timezone_abbreviation": local.tzname(),
                "observation_hour_utc": spec.get("slot_override") or _slot(generated),
                "producer": spec.get(
                    "producer", self.corpus["materialisation"]["producer"]
                ),
                "cadence": self.corpus["materialisation"]["cadence"],
            }
        )
        if spec.get("legacy"):
            run.pop("observation_hour_utc", None)
        if "schema_version" in spec:
            payload["schema_version"] = spec["schema_version"]
        for source in payload.get("sources", {}).values():
            if isinstance(source, dict) and "fetched_at_utc" in source:
                source["fetched_at_utc"] = _utc(generated)
        for asset in payload.get("market", {}).get("assets", []):
            if isinstance(asset, dict) and "last_updated" in asset:
                asset["last_updated"] = _utc(generated)

        if "path_override" in spec:
            relative = Path(spec["path_override"])
        else:
            safe = "".join(
                ch for ch in (local.tzname() or "LOCAL") if ch.isalnum()
            ) or "LOCAL"
            relative = Path(
                f"{local.year:04d}/{local.month:02d}/{local.day:02d}/"
                f"{local.hour:02d}{local.minute:02d}_{safe}_source_snapshot.json"
            )
        raw = (
            json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
        return f"data/crypto/hourly/{relative.as_posix()}", raw

    def _seed_repository(
        self, case_id: str
    ) -> tuple[tempfile.TemporaryDirectory[str], Path, str, str]:
        case = self.corpus["repository_cases"][case_id]
        temporary = tempfile.TemporaryDirectory(prefix=f"phase13-proof-{case_id}-")
        repository = Path(temporary.name)
        _git(repository, "init", "-q")

        files: dict[str, bytes] = {}
        for ref in PINNED_REFS.values():
            files[ref["path"]] = (ROOT / ref["path"]).read_bytes()
        tamper_ref = case.get("tamper_ref")
        if tamper_ref is not None:
            path = PINNED_REFS[tamper_ref]["path"]
            files[path] += b"\n# synthetic contract drift\n"

        for snapshot in case.get("snapshots", []):
            path, raw = self._snapshot(snapshot)
            if path in files:
                raise AssertionError(f"duplicate materialised path: {path}")
            files[path] = raw

        for path in sorted(files):
            target = repository / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(files[path])

        _git(repository, "add", "-A")
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
                input_bytes=(seed["message"] + "\n").encode("utf-8"),
                extra_env=env,
            )
        )
        return temporary, repository, commit, tree

    def _comparison(self, repository: Path, commit: str, case_id: str) -> dict[str, Any]:
        case = self.corpus["repository_cases"][case_id]
        return build_observation_hour_comparison(
            repository, commit, case["target_slot_utc"]
        )

    def _series(self, repository: Path, commit: str, case_id: str) -> dict[str, Any]:
        spec = self.corpus["repository_cases"][case_id]["series"]
        return build_observation_hour_series(
            repository,
            commit,
            spec["kind"],
            spec["key"],
            spec["start_utc"],
            spec["end_utc"],
        )

    def _execute_comparison(self, case_id: str) -> tuple[bytes, str]:
        temporary, repository, commit, _ = self._seed_repository(case_id)
        try:
            record = self._comparison(repository, commit, case_id)
            return comparison_json_bytes(record), record["comparison_id"]
        finally:
            temporary.cleanup()

    def _execute_series(self, case_id: str) -> tuple[bytes, str]:
        temporary, repository, commit, _ = self._seed_repository(case_id)
        try:
            record = self._series(repository, commit, case_id)
            validate_observation_hour_series(repository, record)
            return series_json_bytes(record), record["series_id"]
        finally:
            temporary.cleanup()

    def test_corpus_contract_is_closed_and_bound(self) -> None:
        self.assertEqual(
            set(self.corpus),
            {
                "schema_version",
                "frozen_contract",
                "materialisation",
                "seed_commit",
                "repository_case_order",
                "repository_cases",
                "adapter_cases",
                "goldens",
            },
        )
        self.assertEqual(
            self.corpus["schema_version"],
            "phase13-observation-hour-temporal-proof-corpus/v1",
        )
        contract = self.corpus["frozen_contract"]
        self.assertEqual(contract["adjacency_policy_version"], ADJACENCY_POLICY_VERSION)
        self.assertEqual(
            contract["observation_hour_contract_version"],
            OBSERVATION_HOUR_CONTRACT_VERSION,
        )
        self.assertEqual(
            contract["semantic_contract_version"], SEMANTIC_CONTRACT_VERSION
        )
        self.assertEqual(
            contract["comparison_schema_version"], COMPARISON_SCHEMA_VERSION
        )
        self.assertEqual(contract["series_schema_version"], SERIES_SCHEMA_VERSION)
        self.assertEqual(contract["max_series_slots"], MAX_SLOTS)
        self.assertEqual(contract["metric_keys"], list(METRIC_IDENTITIES))
        self.assertEqual(contract["source_keys"], list(SOURCE_IDENTITIES))
        self.assertEqual(
            self.corpus["repository_case_order"],
            list(self.corpus["repository_cases"]),
        )
        for alias in self.corpus["materialisation"]["source_fixtures"]:
            self._fixture_bytes(alias)

    def test_repository_matrix_covers_every_closed_comparison_status(self) -> None:
        seen_failures: set[str] = set()
        for case_id in self.corpus["repository_case_order"]:
            case = self.corpus["repository_cases"][case_id]
            with self.subTest(case=case_id):
                temporary, repository, commit, _ = self._seed_repository(case_id)
                try:
                    comparison = self._comparison(repository, commit, case_id)
                    expected = case["expected_comparison_status"]
                    self.assertEqual(comparison["comparison_status"], expected)
                    if expected != "comparison-available":
                        seen_failures.add(expected)
                    if "expected_actual_elapsed_seconds" in case:
                        self.assertEqual(
                            comparison["actual_elapsed_seconds"],
                            case["expected_actual_elapsed_seconds"],
                        )
                    if "expected_current_candidates" in case:
                        self.assertEqual(
                            len(comparison["current_candidates"]),
                            case["expected_current_candidates"],
                        )
                    if "expected_degraded_side" in case:
                        side = case["expected_degraded_side"]
                        self.assertEqual(
                            comparison[side]["quality_status"], "valid-degraded"
                        )
                        self.assertTrue(
                            comparison[side]["non_blocking_warnings"]
                        )

                    series = self._series(repository, commit, case_id)
                    validate_observation_hour_series(repository, series)
                    if expected == "comparison-available":
                        self.assertIsNotNone(series["entries"][-1]["value"])
                    else:
                        entry = series["entries"][-1]
                        self.assertIsNone(entry["value"])
                        self.assertEqual(
                            entry["gap"]["reason"], COMPARISON_GAP_MAP[expected]
                        )
                finally:
                    temporary.cleanup()

        self.assertEqual(seen_failures, set(COMPARISON_GAP_MAP))

    def test_metric_unavailable_and_invalid_states_are_closed_gaps(self) -> None:
        identity = METRIC_IDENTITIES["BTC.price_usd"]
        context = {"commit_sha": "b" * 40}
        replay_context = mock.Mock()
        replay_context.matches.return_value = True
        for state, expected in self.corpus["adapter_cases"]["metric_gap_map"].items():
            comparison = {
                "comparison_status": "comparison-available",
                "comparison_id": "a" * 64,
                "repository_context": context,
                "current": {"path": "current"},
                "predecessor": {"path": "predecessor"},
                "metric_comparisons": [
                    {
                        "family": identity[0],
                        "symbol": identity[1],
                        "field": identity[2],
                        "predecessor": {"present": True, "value": 1},
                        "current": {"present": True, "value": 999},
                        "comparison_state": state,
                        "relation": None,
                    }
                ],
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
                        replay_context=replay_context,
                    )
                entry = record["entries"][0]
                self.assertIsNone(entry["value"])
                self.assertEqual(entry["gap"]["reason"], expected)
                self.assertEqual(
                    entry["gap"]["metric_evidence"]["current"]["value"], 999
                )
        self.assertEqual(
            self.corpus["adapter_cases"]["metric_gap_map"], METRIC_GAP_MAP
        )

    def test_side_specific_degraded_and_categorical_evidence_is_preserved(self) -> None:
        for case_id, side in (
            ("current-degraded", "current"),
            ("predecessor-degraded", "predecessor"),
        ):
            temporary, repository, commit, _ = self._seed_repository(case_id)
            try:
                record = self._series(repository, commit, case_id)
                evidence = record["entries"][0]["value"]["comparison"][side]
                self.assertEqual(evidence["quality_status"], "valid-degraded")
                self.assertTrue(evidence["non_blocking_warnings"])
                validate_observation_hour_series(repository, record)
            finally:
                temporary.cleanup()

        temporary, repository, commit, _ = self._seed_repository("source-status")
        try:
            record = self._series(repository, commit, "source-status")
            entry = record["entries"][0]
            self.assertEqual(
                entry["value"]["datum"],
                self.corpus["repository_cases"]["source-status"]["expected_datum"],
            )
            self.assertIsInstance(entry["value"]["datum"], str)
            self.assertEqual(
                entry["value"]["datum"],
                entry["value"]["evidence"]["current_status"],
            )
            validate_observation_hour_series(repository, record)
        finally:
            temporary.cleanup()

    def test_continuity_discontinuity_and_unavailable_are_identity_bound(self) -> None:
        identity = copy.deepcopy(
            self.corpus["adapter_cases"]["continuity_identity"]
        )
        continuous = _continuity(
            1,
            {"current": copy.deepcopy(identity)},
            {"predecessor": copy.deepcopy(identity)},
        )
        self.assertEqual(continuous["status"], "continuous")

        changed = copy.deepcopy(identity)
        changed["quality_status"] = "valid-degraded"
        changed["non_blocking_warnings"] = ["synthetic warning"]
        discontinuous = _continuity(
            1,
            {"current": copy.deepcopy(identity)},
            {"predecessor": changed},
        )
        self.assertEqual(discontinuous["status"], "discontinuous")
        self.assertEqual(discontinuous["previous_current"], identity)
        self.assertEqual(discontinuous["current_predecessor"], changed)

        unavailable = _continuity(
            1,
            {"current": copy.deepcopy(identity)},
            {"predecessor": None},
        )
        self.assertEqual(unavailable["status"], "unavailable")

    def test_real_series_continuity_and_replay_tamper_rejection(self) -> None:
        temporary, repository, commit, _ = self._seed_repository("continuous-series")
        try:
            record = self._series(repository, commit, "continuous-series")
            self.assertEqual(
                [item["continuity"]["status"] for item in record["entries"]],
                self.corpus["repository_cases"]["continuous-series"][
                    "expected_continuity"
                ],
            )
            validate_observation_hour_series(repository, record)

            tampered = copy.deepcopy(record)
            tampered["entries"][1]["continuity"]["status"] = "discontinuous"
            tampered["series_id"] = series_id_for_record(tampered)
            with self.assertRaises(ObservationHourSeriesError):
                validate_observation_hour_series(repository, tampered)

            unknown_top_level = copy.deepcopy(record)
            unknown_top_level["unexpected"] = True
            unknown_top_level["series_id"] = series_id_for_record(
                unknown_top_level
            )
            with self.assertRaises(ObservationHourSeriesError):
                validate_observation_hour_series(repository, unknown_top_level)

            unknown_key = copy.deepcopy(record)
            unknown_key["series_key"] = "BTC.change_24h_pct"
            unknown_key["series_id"] = series_id_for_record(unknown_key)
            with self.assertRaises(ObservationHourSeriesError):
                validate_observation_hour_series(repository, unknown_key)
        finally:
            temporary.cleanup()

    def test_frozen_exact_bytes_and_ids_repeat_across_independent_materialisations(self) -> None:
        first_comparison = self._execute_comparison("below-3600")
        second_comparison = self._execute_comparison("below-3600")
        self.assertEqual(first_comparison, second_comparison)
        comparison_golden = self.corpus["goldens"]["below-3600-comparison"]
        comparison_actual = {
            "canonical_bytes": len(first_comparison[0]),
            "canonical_sha256": hashlib.sha256(first_comparison[0]).hexdigest(),
            "comparison_id": first_comparison[1],
        }
        print(
            "PHASE13_DERIVE below-3600-comparison "
            + json.dumps(comparison_actual, sort_keys=True)
        )
        self.assertEqual(comparison_actual, comparison_golden)

        first_series = self._execute_series("continuous-series")
        second_series = self._execute_series("continuous-series")
        self.assertEqual(first_series, second_series)
        series_golden = self.corpus["goldens"]["continuous-series"]
        series_actual = {
            "canonical_bytes": len(first_series[0]),
            "canonical_sha256": hashlib.sha256(first_series[0]).hexdigest(),
            "series_id": first_series[1],
        }
        print(
            "PHASE13_DERIVE continuous-series "
            + json.dumps(series_actual, sort_keys=True)
        )
        self.assertEqual(series_actual, series_golden)


if __name__ == "__main__":
    unittest.main()
