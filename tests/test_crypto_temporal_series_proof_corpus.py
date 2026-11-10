from __future__ import annotations

import base64
import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from unittest import mock
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from crypto_temporal_series import (  # noqa: E402
    METRIC_GAP_MAP,
    METRIC_IDENTITIES,
    PHASE10_GAP_MAP,
    TemporalSeriesError,
    _entry_for_unique_candidate,
    build_temporal_series,
    canonical_json_bytes,
    series_id_for_record,
    validate_temporal_series,
)
from render_crypto_temporal_series import (  # noqa: E402
    _render_validated_series,
    render_temporal_series,
)
from validate_crypto_snapshot_comparison import (  # noqa: E402
    CONFIG_BLOB_SHA,
    CONFIG_PATH,
    VALIDATOR_BLOB_SHA,
    VALIDATOR_PATH,
)

CORPUS_PATH = ROOT / "tests" / "fixtures" / "phase11_temporal_series_proof_v1.json"
REPOSITORY_STATUS_CASES = (
    "predecessor-missing",
    "current-invalid",
    "current-identity-invalid",
    "predecessor-ambiguous",
    "predecessor-invalid",
    "predecessor-identity-invalid",
    "predecessor-out-of-window",
    "pair-schema-incompatible",
    "pair-semantics-incompatible",
)


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


def _utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _canonical_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _snapshot_path(generated_at_utc: str, timezone_name: str) -> str:
    local = _utc(generated_at_utc).astimezone(ZoneInfo(timezone_name))
    tz = "".join(ch for ch in (local.tzname() or "LOCAL") if ch.isalnum()) or "LOCAL"
    return (
        f"data/crypto/hourly/{local.year:04d}/{local.month:02d}/{local.day:02d}/"
        f"{local.hour:02d}{local.minute:02d}_{tz}_source_snapshot.json"
    )


def _set_source(snapshot: dict[str, Any], name: str, status: str, generated_at_utc: str) -> None:
    sources = snapshot["sources"]
    if status == "missing":
        sources.pop(name, None)
        return
    item: dict[str, Any] = {"status": status}
    if status == "skipped":
        item["reason"] = "synthetic skipped"
    else:
        item["fetched_at_utc"] = generated_at_utc
    sources[name] = item


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_table = False
        self.current_row: list[str] | None = None
        self.current_cell: list[str] | None = None
        self.rows: list[list[str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "table" and "temporal-evidence-table" in (attributes.get("class") or ""):
            self.in_table = True
        elif self.in_table and tag == "tr":
            self.current_row = []
        elif self.in_table and tag in {"th", "td"} and self.current_row is not None:
            self.current_cell = []

    def handle_data(self, data: str) -> None:
        if self.current_cell is not None:
            self.current_cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self.in_table and tag in {"th", "td"} and self.current_cell is not None:
            assert self.current_row is not None
            self.current_row.append("".join(self.current_cell))
            self.current_cell = None
        elif self.in_table and tag == "tr" and self.current_row is not None:
            self.rows.append(self.current_row)
            self.current_row = None
        elif tag == "table" and self.in_table:
            self.in_table = False


class Phase11TemporalSeriesProofTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.corpus = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))

    def _materialise_snapshot(self, spec: dict[str, Any]) -> tuple[str, bytes]:
        timezone_name = self.corpus["materialisation"]["timezone"]
        generated_at_utc = spec["generated_at_utc"]
        generated = _utc(generated_at_utc)
        local = generated.astimezone(ZoneInfo(timezone_name))
        snapshot = copy.deepcopy(self.corpus["snapshot_template"])
        snapshot["schema_version"] = spec.get("schema_version", snapshot["schema_version"])
        snapshot["run"].update(
            {
                "generated_at_utc": _canonical_utc(generated),
                "generated_at_local": local.isoformat(),
                "timezone": timezone_name,
                "cadence": "hourly",
                "producer": spec.get("producer", "scripts/ingest_crypto_sources.py"),
            }
        )
        for asset in snapshot["market"]["assets"]:
            asset["last_updated"] = _canonical_utc(generated)
            if asset["symbol"] == "BTC" and "btc_price_usd" in spec:
                asset["price_usd"] = spec["btc_price_usd"]
        for source_name, payload in list(snapshot["sources"].items()):
            if payload["status"] != "skipped":
                payload["fetched_at_utc"] = _canonical_utc(generated)
        for key, source_name in (
            ("coingecko_status", "coingecko"),
            ("coinbase_status", "coinbase_exchange"),
            ("binance_status", "binance"),
        ):
            if key in spec:
                _set_source(snapshot, source_name, spec[key], _canonical_utc(generated))
        raw = json.dumps(
            snapshot,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        path = spec.get("path") or _snapshot_path(generated_at_utc, timezone_name)
        return path, raw

    def _seed_repository(
        self, case_id: str
    ) -> tuple[tempfile.TemporaryDirectory[str], Path, str, str, dict[str, bytes]]:
        case = self.corpus["repository_cases"][case_id]
        temporary = tempfile.TemporaryDirectory(prefix=f"phase11-proof-{case_id}-")
        repository = Path(temporary.name)
        _git(repository, "init", "-q")

        validator_bytes = (ROOT / VALIDATOR_PATH).read_bytes()
        config_bytes = (ROOT / CONFIG_PATH).read_bytes()
        self.assertEqual(_text(_git(repository, "hash-object", "--stdin", input_bytes=validator_bytes)), VALIDATOR_BLOB_SHA)
        self.assertEqual(_text(_git(repository, "hash-object", "--stdin", input_bytes=config_bytes)), CONFIG_BLOB_SHA)
        if case.get("tamper_config"):
            config_bytes += b"\n# synthetic contract mismatch\n"

        files: dict[str, bytes] = {VALIDATOR_PATH: validator_bytes, CONFIG_PATH: config_bytes}
        for spec in case.get("snapshots", []):
            path, raw = self._materialise_snapshot(spec)
            if path in files:
                raise AssertionError(f"duplicate materialised repository path: {path}")
            files[path] = raw
        for path, raw in case.get("raw_files", {}).items():
            if path in files:
                raise AssertionError(f"duplicate raw repository path: {path}")
            files[path] = raw.encode("utf-8")

        for path in sorted(files):
            blob = _text(_git(repository, "hash-object", "-w", "--stdin", input_bytes=files[path]))
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
                input_bytes=(seed["message"] + "\n").encode("utf-8"),
                extra_env=env,
            )
        )
        return temporary, repository, commit, tree, files

    def _build_case(self, repository: Path, commit: str, case_id: str) -> dict[str, Any]:
        series = self.corpus["repository_cases"][case_id]["series"]
        return build_temporal_series(
            repository,
            commit,
            series["kind"],
            series["key"],
            series["start_utc"],
            series["end_utc"],
        )

    def _execute_case(self, case_id: str) -> tuple[str, str, bytes, bytes]:
        temporary, repository, commit, tree, _ = self._seed_repository(case_id)
        try:
            record = self._build_case(repository, commit, case_id)
            validate_temporal_series(repository, record)
            rendered = render_temporal_series(repository, record).encode("utf-8")
            return commit, tree, canonical_json_bytes(record), rendered
        finally:
            temporary.cleanup()

    @staticmethod
    def _emit_chunks(label: str, raw: bytes) -> None:
        encoded = base64.b64encode(raw).decode("ascii")
        chunks = [encoded[index : index + 1200] for index in range(0, len(encoded), 1200)]
        print(f"DERIVE {label} COUNT {len(chunks)}")
        for index, chunk in enumerate(chunks):
            print(f"DERIVE {label} {index:03d} {chunk}")

    @staticmethod
    def _side_text(value: Any, field: str) -> str:
        if not isinstance(value, dict):
            return "—"
        result = value.get(field)
        return "—" if result is None else str(result)

    @staticmethod
    def _warning_text(value: Any) -> str:
        if not isinstance(value, dict) or value.get("non_blocking_warnings") is None:
            return "—"
        warnings = value["non_blocking_warnings"]
        return "none" if not warnings else "; ".join(str(item) for item in warnings)

    @staticmethod
    def _provenance_text(value: Any) -> str:
        if not isinstance(value, dict):
            return "—"
        return "; ".join(
            (
                f"path={value.get('path')}",
                f"sha256={value.get('sha256')}",
                f"schema={value.get('schema_version')}",
                f"generated_at_utc={value.get('generated_at_utc')}",
            )
        )

    @staticmethod
    def _evidence_text(entry: dict[str, Any]) -> str:
        value = entry.get("value")
        if value is not None:
            evidence = value.get("evidence")
            return "—" if evidence is None else json.dumps(evidence, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        gap = entry["gap"]
        if gap["reason"] == "current-ambiguous":
            return " | ".join(
                f"path={item.get('path')}; sha256={item.get('sha256')}; schema={item.get('schema_version')}; generated_at_utc={item.get('generated_at_utc')}"
                for item in gap["current_candidates"]
            )
        detail = {key: value for key, value in gap.items() if key not in {"current", "predecessor"}}
        return json.dumps(detail, sort_keys=True, separators=(",", ":"), ensure_ascii=False) if detail else "—"

    def _assert_table_equivalence(self, record: dict[str, Any], rendered: str) -> None:
        parser = _TableParser()
        parser.feed(rendered)
        rows = [row for row in parser.rows if row and row[0].endswith("Z")]
        self.assertEqual(len(rows), len(record["entries"]))
        for entry, row in zip(record["entries"], rows):
            value, gap = entry.get("value"), entry.get("gap")
            payload = value if value is not None else gap
            current = payload.get("current") if isinstance(payload, dict) else None
            predecessor = payload.get("predecessor") if isinstance(payload, dict) else None
            if value is not None:
                datum = value["datum"]
                exact = datum if isinstance(datum, str) else json.dumps(datum, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
                state = "value"
            else:
                exact = "—"
                state = gap["reason"]
            expected = [
                entry["slot_utc"],
                state,
                exact,
                self._side_text(current, "quality_status"),
                self._warning_text(current),
                self._side_text(predecessor, "quality_status"),
                self._warning_text(predecessor),
                payload.get("comparison_id") or "—",
                self._provenance_text(current),
                self._provenance_text(predecessor),
                self._evidence_text(entry),
            ]
            self.assertEqual(row, expected)

    def test_corpus_contract_is_closed_and_frozen(self) -> None:
        self.assertEqual(
            set(self.corpus),
            {
                "schema_version",
                "frozen_contract",
                "materialisation",
                "seed_commit",
                "snapshot_template",
                "repository_case_order",
                "repository_cases",
                "adapter_cases",
                "goldens",
            },
        )
        self.assertEqual(self.corpus["schema_version"], "phase11-temporal-series-proof-corpus/v1")
        contract = self.corpus["frozen_contract"]
        self.assertEqual(contract["series_schema_version"], "crypto-temporal-series/v1")
        self.assertEqual(contract["comparison_schema_version"], "crypto-snapshot-comparison/v1")
        self.assertEqual(contract["predecessor_policy_version"], "phase10-predecessor-exact-hour/v1")
        self.assertEqual(contract["semantic_contract_version"], "phase10-snapshot-semantics-0.2/v1")
        self.assertEqual(contract["validator"], {"path": VALIDATOR_PATH, "git_blob_sha": VALIDATOR_BLOB_SHA})
        self.assertEqual(contract["config"], {"path": CONFIG_PATH, "git_blob_sha": CONFIG_BLOB_SHA})
        self.assertEqual(self.corpus["repository_case_order"], list(self.corpus["repository_cases"]))
        self.assertEqual(self.corpus["materialisation"], {"snapshot_encoding": "canonical-json-utf8", "timezone": "Australia/Sydney"})
        raw = CORPUS_PATH.read_text(encoding="utf-8")
        self.assertNotIn("phase10_comparison_proof_v1", raw)
        self.assertNotIn("data/crypto/hourly/2026/07/08/1400_AEST_source_snapshot.json", raw)

    def test_frozen_canonical_series_and_renderer_goldens_repeat_independently(self) -> None:
        for case_id in ("numeric-history", "source-history"):
            first = self._execute_case(case_id)
            second = self._execute_case(case_id)
            self.assertEqual(first, second)
            golden = self.corpus["goldens"][case_id]
            self.assertEqual(len(first[2]), golden["canonical_series_bytes"])
            self.assertEqual(hashlib.sha256(first[2]).hexdigest(), golden["canonical_series_sha256"])
            self.assertEqual(len(first[3]), golden["renderer_bytes"])
            self.assertEqual(hashlib.sha256(first[3]).hexdigest(), golden["renderer_sha256"])

    def test_numeric_history_proves_continuity_degradation_gaps_and_table_equivalence(self) -> None:
        temporary, repository, commit, _, _ = self._seed_repository("numeric-history")
        try:
            record = self._build_case(repository, commit, "numeric-history")
            validate_temporal_series(repository, record)
            expected_states = self.corpus["repository_cases"]["numeric-history"]["expected_states"]
            actual_states = ["value" if entry["value"] is not None else entry["gap"]["reason"] for entry in record["entries"]]
            self.assertEqual(actual_states, expected_states)
            current_degraded = record["entries"][1]["value"]
            predecessor_degraded = record["entries"][2]["value"]
            self.assertEqual(current_degraded["current"]["quality_status"], "valid-degraded")
            self.assertTrue(current_degraded["current"]["non_blocking_warnings"])
            self.assertEqual(current_degraded["predecessor"]["quality_status"], "valid-ok")
            self.assertEqual(predecessor_degraded["current"]["quality_status"], "valid-ok")
            self.assertEqual(predecessor_degraded["predecessor"]["quality_status"], "valid-degraded")
            self.assertTrue(predecessor_degraded["predecessor"]["non_blocking_warnings"])
            self.assertEqual(record["entries"][1]["value"]["predecessor"], record["entries"][0]["value"]["current"])
            self.assertEqual(record["entries"][2]["value"]["predecessor"], record["entries"][1]["value"]["current"])
            rendered = render_temporal_series(repository, record)
            self.assertIn('data-segment-count="2"', rendered)
            self.assertEqual(rendered.count('class="metric-line"'), 2)
            self.assertIn('class="gap-marker" data-slot-index="3"', rendered)
            self.assertIn('class="gap-marker" data-slot-index="4"', rendered)
            self.assertNotIn("interpolated", rendered.lower())
            self._assert_table_equivalence(record, rendered)
        finally:
            temporary.cleanup()

    def test_source_history_is_exact_categorical_evidence_with_complete_table(self) -> None:
        temporary, repository, commit, _, _ = self._seed_repository("source-history")
        try:
            record = self._build_case(repository, commit, "source-history")
            validate_temporal_series(repository, record)
            statuses = [entry["value"]["datum"] for entry in record["entries"]]
            self.assertEqual(statuses, self.corpus["repository_cases"]["source-history"]["expected_states"])
            rendered = render_temporal_series(repository, record)
            self.assertIn('data-visual-mode="categorical"', rendered)
            self.assertNotIn('data-visual-mode="numeric"', rendered)
            self.assertIn("no numeric market axis", rendered)
            for status in statuses:
                self.assertIn(f'data-status="{status}"', rendered)
            self._assert_table_equivalence(record, rendered)
        finally:
            temporary.cleanup()

    def test_missing_and_ambiguous_current_evidence_is_complete_and_deterministic(self) -> None:
        temporary, repository, commit, _, files = self._seed_repository("current-ambiguous")
        try:
            record = self._build_case(repository, commit, "current-ambiguous")
            validate_temporal_series(repository, record)
            entry = record["entries"][0]
            self.assertEqual(entry["gap"]["reason"], "current-ambiguous")
            candidates = entry["gap"]["current_candidates"]
            self.assertEqual(len(candidates), 2)
            self.assertEqual(candidates, sorted(candidates, key=lambda item: (item["path"], item["sha256"])))
            for candidate in candidates:
                self.assertIn(candidate["path"], files)
                self.assertEqual(candidate["sha256"], hashlib.sha256(files[candidate["path"]]).hexdigest())
                self.assertEqual(candidate["generated_at_utc"], "2026-07-10T01:00:00Z")
            rendered = render_temporal_series(repository, record)
            self._assert_table_equivalence(record, rendered)
            for candidate in candidates:
                self.assertIn(candidate["path"], rendered)
                self.assertIn(candidate["sha256"], rendered)
        finally:
            temporary.cleanup()

        temporary, repository, commit, _, _ = self._seed_repository("numeric-history")
        try:
            record = self._build_case(repository, commit, "numeric-history")
            missing = record["entries"][3]
            self.assertEqual(missing["gap"], {"reason": "current-missing", "current_candidates": []})
            validate_temporal_series(repository, record)
        finally:
            temporary.cleanup()

    def test_every_reachable_phase10_failure_maps_exactly_and_raw_values_never_bypass(self) -> None:
        seen: set[str] = set()
        for case_id in REPOSITORY_STATUS_CASES:
            with self.subTest(case=case_id):
                temporary, repository, commit, _, _ = self._seed_repository(case_id)
                try:
                    record = self._build_case(repository, commit, case_id)
                    validate_temporal_series(repository, record)
                    entry = record["entries"][0]
                    self.assertIsNone(entry["value"])
                    expected = self.corpus["repository_cases"][case_id]["expected_gap_reason"]
                    self.assertEqual(entry["gap"]["reason"], expected)
                    self.assertTrue(expected.startswith("phase10-"))
                    seen.add(expected)
                    if case_id == "current-invalid":
                        self.assertEqual(entry["gap"]["reason"], "phase10-current-invalid")
                        self.assertNotIn(999, [item.get("datum") for item in record["entries"] if item.get("value")])
                finally:
                    temporary.cleanup()
        self.assertEqual(
            seen,
            {
                "phase10-predecessor-missing",
                "phase10-current-invalid",
                "phase10-current-identity-invalid",
                "phase10-predecessor-ambiguous",
                "phase10-predecessor-invalid",
                "phase10-predecessor-identity-invalid",
                "phase10-predecessor-out-of-window",
                "phase10-pair-schema-incompatible",
                "phase10-pair-semantics-incompatible",
            },
        )

    def test_phase11_fails_before_slot_classification_for_unindexable_or_unbound_repository(self) -> None:
        for case_id in ("validation-contract-mismatch", "candidate-set-unorderable"):
            with self.subTest(case=case_id):
                temporary, repository, commit, _, _ = self._seed_repository(case_id)
                try:
                    with self.assertRaisesRegex(
                        TemporalSeriesError,
                        self.corpus["repository_cases"][case_id]["expected_error_contains"],
                    ):
                        self._build_case(repository, commit, case_id)
                finally:
                    temporary.cleanup()

    def test_metric_gap_adapter_and_comparison_precedence_are_closed(self) -> None:
        identity = METRIC_IDENTITIES["BTC.price_usd"]
        base = {
            "comparison_status": "comparison-available",
            "comparison_id": "a" * 64,
            "current": {"quality_status": "valid-ok", "non_blocking_warnings": []},
            "predecessor": {"quality_status": "valid-ok", "non_blocking_warnings": []},
            "metric_comparisons": [],
            "source_availability_changes": [],
        }
        for state, expected in self.corpus["adapter_cases"]["metric_gap_map"].items():
            record = copy.deepcopy(base)
            record["metric_comparisons"] = [
                {
                    "family": identity[0],
                    "symbol": identity[1],
                    "field": identity[2],
                    "predecessor": {"present": state != "unavailable-predecessor", "value": 1},
                    "current": {"present": state != "unavailable-current", "value": 2},
                    "comparison_state": state,
                    "relation": None,
                }
            ]
            with mock.patch("crypto_temporal_series.build_comparison_record", return_value=record):
                entry = _entry_for_unique_candidate(
                    Path("."), "0" * 40, "metric", "BTC.price_usd", _utc("2026-01-01T00:00:00Z"), {"path": "synthetic"}
                )
            self.assertEqual(entry["gap"]["reason"], expected)
            self.assertEqual(entry["gap"]["metric_evidence"]["comparison_state"], state)

        failed = copy.deepcopy(base)
        failed["comparison_status"] = self.corpus["adapter_cases"]["precedence_failure_status"]
        failed["metric_comparisons"] = [
            {
                "family": identity[0], "symbol": identity[1], "field": identity[2],
                "predecessor": {"present": True, "value": 1},
                "current": {"present": True, "value": 999999},
                "comparison_state": "comparable", "relation": "current-greater",
            }
        ]
        failed["source_availability_changes"] = [
            {"source": "binance", "current_status": "ok"}
        ]
        for kind, key in (("metric", "BTC.price_usd"), ("source-status", "binance")):
            with mock.patch("crypto_temporal_series.build_comparison_record", return_value=failed):
                entry = _entry_for_unique_candidate(
                    Path("."), "0" * 40, kind, key, _utc("2026-01-01T00:00:00Z"), {"path": "synthetic"}
                )
            self.assertEqual(entry["gap"]["reason"], "phase10-current-invalid")
            self.assertIsNone(entry["value"])

        ready = copy.deepcopy(base)
        ready["comparison_status"] = "comparison-ready"
        with mock.patch("crypto_temporal_series.build_comparison_record", return_value=ready):
            entry = _entry_for_unique_candidate(
                Path("."), "0" * 40, "metric", "BTC.price_usd", _utc("2026-01-01T00:00:00Z"), {"path": "synthetic"}
            )
        self.assertEqual(entry["gap"]["reason"], self.corpus["adapter_cases"]["comparison_gap_map"]["comparison-ready"])

    def test_exact_identity_continuity_not_timestamp_or_comparison_id_controls_lines(self) -> None:
        temporary, repository, commit, _, _ = self._seed_repository("numeric-history")
        try:
            record = self._build_case(repository, commit, "numeric-history")
            probe = copy.deepcopy(record)
            probe["window"] = {"start_utc": probe["entries"][0]["slot_utc"], "end_utc": probe["entries"][1]["slot_utc"]}
            probe["entries"] = probe["entries"][:2]
            probe["series_id"] = series_id_for_record(probe)
            connected = _render_validated_series(probe)
            self.assertIn('data-segment-count="1"', connected)
            self.assertEqual(connected.count('class="metric-line"'), 1)

            broken = copy.deepcopy(probe)
            broken["entries"][1]["value"]["predecessor"]["path"] = "data/crypto/hourly/2099/01/01/0000_FAKE_source_snapshot.json"
            broken["entries"][1]["value"]["comparison_id"] = broken["entries"][0]["value"]["comparison_id"]
            broken["series_id"] = series_id_for_record(broken)
            disconnected = _render_validated_series(broken)
            self.assertIn('data-segment-count="2"', disconnected)
            self.assertEqual(disconnected.count('class="metric-line"'), 0)
        finally:
            temporary.cleanup()

    def test_tamper_unknown_vocabulary_and_replay_disagreement_fail_closed_before_render(self) -> None:
        temporary, repository, commit, _, _ = self._seed_repository("numeric-history")
        try:
            original = self._build_case(repository, commit, "numeric-history")
            validate_temporal_series(repository, original)
            tampered: list[dict[str, Any]] = []

            datum = copy.deepcopy(original)
            datum["entries"][0]["value"]["datum"] = 123456789
            datum["series_id"] = series_id_for_record(datum)
            tampered.append(datum)

            current = copy.deepcopy(original)
            current["entries"][0]["value"]["current"]["sha256"] = "0" * 64
            current["series_id"] = series_id_for_record(current)
            tampered.append(current)

            predecessor = copy.deepcopy(original)
            predecessor["entries"][2]["value"]["predecessor"]["non_blocking_warnings"] = []
            predecessor["series_id"] = series_id_for_record(predecessor)
            tampered.append(predecessor)

            comparison = copy.deepcopy(original)
            comparison["entries"][0]["value"]["comparison_id"] = "0" * 64
            comparison["series_id"] = series_id_for_record(comparison)
            tampered.append(comparison)

            unknown_gap = copy.deepcopy(original)
            unknown_gap["entries"][3]["gap"]["reason"] = "future-gap"
            unknown_gap["series_id"] = series_id_for_record(unknown_gap)
            tampered.append(unknown_gap)

            wrong_id = copy.deepcopy(original)
            wrong_id["series_id"] = "0" * 64
            tampered.append(wrong_id)

            derived = copy.deepcopy(original)
            derived["derived"] = {"moving_average": 1}
            derived["series_id"] = series_id_for_record(derived)
            tampered.append(derived)

            for candidate in tampered:
                with self.assertRaises(TemporalSeriesError):
                    validate_temporal_series(repository, candidate)
                with self.assertRaises(TemporalSeriesError):
                    render_temporal_series(repository, candidate)
        finally:
            temporary.cleanup()

        temporary, repository, commit, _, _ = self._seed_repository("current-ambiguous")
        try:
            ambiguous = self._build_case(repository, commit, "current-ambiguous")
            candidates = ambiguous["entries"][0]["gap"]["current_candidates"]
            self.assertEqual(len(candidates), 2)
            for transform in ("remove", "reorder"):
                candidate = copy.deepcopy(ambiguous)
                if transform == "remove":
                    candidate["entries"][0]["gap"]["current_candidates"] = candidates[:1]
                else:
                    candidate["entries"][0]["gap"]["current_candidates"] = list(reversed(candidates))
                candidate["series_id"] = series_id_for_record(candidate)
                with self.assertRaises(TemporalSeriesError):
                    validate_temporal_series(repository, candidate)
                with self.assertRaises(TemporalSeriesError):
                    render_temporal_series(repository, candidate)
        finally:
            temporary.cleanup()

        future = {
            "comparison_status": "future-phase10-status",
            "comparison_id": "f" * 64,
            "current": None,
            "predecessor": None,
            "metric_comparisons": [],
            "source_availability_changes": [],
        }
        with mock.patch("crypto_temporal_series.build_comparison_record", return_value=future):
            with self.assertRaises(TemporalSeriesError):
                _entry_for_unique_candidate(
                    Path("."), "0" * 40, "metric", "BTC.price_usd", _utc("2026-01-01T00:00:00Z"), {"path": "synthetic"}
                )

    def test_contract_maps_remain_exact_and_unknowns_are_not_coerced(self) -> None:
        self.assertEqual(self.corpus["adapter_cases"]["metric_gap_map"], METRIC_GAP_MAP)
        for status, reason in self.corpus["adapter_cases"]["comparison_gap_map"].items():
            self.assertEqual(PHASE10_GAP_MAP[status], reason)
        self.assertEqual(PHASE10_GAP_MAP["current-invalid"], "phase10-current-invalid")


if __name__ == "__main__":
    unittest.main()
