from __future__ import annotations

import copy
import hashlib
import html
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
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from crypto_observation_hour_series import (  # noqa: E402
    ObservationHourSeriesError,
    series_id_for_record,
)
from phase15_public_temporal_evidence import (  # noqa: E402
    PUBLIC_SERIES_KEY,
    PUBLIC_SERIES_KIND,
    PUBLIC_SLOT_COUNT,
    PUBLIC_TEMPORAL_EVIDENCE_CONTRACT_VERSION,
    Phase15PublicTemporalEvidenceError,
    build_public_temporal_evidence,
    canonical_public_evidence_bytes,
)
from render_crypto_observation_hour_series import render_observation_hour_series  # noqa: E402
from resolve_crypto_observation_hour_adjacency import PINNED_REFS  # noqa: E402

CORPUS_PATH = ROOT / "tests" / "fixtures" / "phase15_public_temporal_evidence_v1.json"


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
    env.update(extra_env or {})
    completed = subprocess.run(
        ["git", "-C", str(repository), *args],
        check=False,
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    if completed.returncode:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise AssertionError(detail or f"git {' '.join(args)} failed")
    return completed.stdout


def _text(raw: bytes) -> str:
    return raw.decode("utf-8", errors="strict").strip()


def _dt(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _slot(value: datetime) -> str:
    return _utc(value.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0))


def _escaped_json(value: Any) -> str:
    return html.escape(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ),
        quote=True,
    )


class Phase15PublicTemporalEvidenceProofTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.corpus = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))

    def _snapshot(self, spec: dict[str, Any]) -> tuple[str, bytes]:
        fixture_path = ROOT / self.corpus["source_fixtures"][spec.get("fixture", "ok")]
        payload = copy.deepcopy(json.loads(fixture_path.read_text(encoding="utf-8")))
        generated = _dt(spec["generated_at_utc"])
        zone = ZoneInfo("Australia/Sydney")
        local = generated.astimezone(zone)
        run = payload["run"]
        run.update(
            {
                "generated_at_utc": _utc(generated),
                "generated_at_local": local.isoformat(),
                "timezone": zone.key,
                "timezone_abbreviation": local.tzname(),
                "observation_hour_utc": spec.get("slot_override") or _slot(generated),
                "producer": "scripts/ingest_crypto_sources.py",
                "cadence": "hourly",
            }
        )
        if spec.get("legacy"):
            run.pop("observation_hour_utc", None)
        for source in payload.get("sources", {}).values():
            if isinstance(source, dict) and "fetched_at_utc" in source:
                source["fetched_at_utc"] = _utc(generated)
        for asset in payload.get("market", {}).get("assets", []):
            if isinstance(asset, dict) and "last_updated" in asset:
                asset["last_updated"] = _utc(generated)

        safe = "".join(ch for ch in (local.tzname() or "LOCAL") if ch.isalnum()) or "LOCAL"
        relative = (
            f"data/crypto/hourly/{local.year:04d}/{local.month:02d}/{local.day:02d}/"
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
        return relative, raw

    def _seed(
        self, case_id: str
    ) -> tuple[tempfile.TemporaryDirectory[str], Path, str]:
        temporary = tempfile.TemporaryDirectory(prefix=f"phase15-proof-{case_id}-")
        repository = Path(temporary.name)
        _git(repository, "init", "-q")
        case = self.corpus["cases"][case_id]

        files: dict[str, bytes] = {}
        for ref in PINNED_REFS.values():
            files[ref["path"]] = (ROOT / ref["path"]).read_bytes()
        for spec in case.get("snapshots", []):
            path, raw = self._snapshot(spec)
            if path in files:
                raise AssertionError(f"duplicate materialised path: {path}")
            files[path] = raw
        if case.get("malformed_asserted_candidate"):
            files[
                "data/crypto/hourly/2026/07/08/2359_AEST_source_snapshot.json"
            ] = b'{"run":{"observation_hour_utc":"2026-07-08T13:00:00Z"\n'

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
        return temporary, repository, commit

    def test_corpus_contract_is_closed(self) -> None:
        self.assertEqual(
            self.corpus["schema_version"],
            "phase15-public-temporal-evidence-proof-corpus/v1",
        )
        self.assertEqual(
            self.corpus["contract"],
            {
                "contract_version": PUBLIC_TEMPORAL_EVIDENCE_CONTRACT_VERSION,
                "series_kind": PUBLIC_SERIES_KIND,
                "series_key": PUBLIC_SERIES_KEY,
                "slot_count": PUBLIC_SLOT_COUNT,
            },
        )
        self.assertEqual(self.corpus["case_order"], list(self.corpus["cases"]))

    def test_closed_repository_matrix(self) -> None:
        for case_id in self.corpus["case_order"]:
            case = self.corpus["cases"][case_id]
            expected = case["expected"]
            with self.subTest(case=case_id):
                temporary, repository, commit = self._seed(case_id)
                try:
                    if "error" in expected:
                        with self.assertRaisesRegex(
                            Phase15PublicTemporalEvidenceError, expected["error"]
                        ):
                            build_public_temporal_evidence(repository, commit)
                        continue
                    record = build_public_temporal_evidence(repository, commit)
                    if not expected["asserted_series"]:
                        self.assertIsNone(record)
                        continue
                    assert record is not None
                    self.assertEqual(record["series_kind"], "metric")
                    self.assertEqual(record["series_key"], "BTC.price_usd")
                    self.assertEqual(len(record["entries"]), 24)
                    self.assertEqual(record["window"]["end_utc"], expected["anchor_utc"])

                    if "latest_gap" in expected:
                        latest = record["entries"][-1]
                        self.assertIsNone(latest["value"])
                        self.assertEqual(latest["gap"]["reason"], expected["latest_gap"])
                        latest_comparison = latest["gap"]["comparison"]
                        self.assertEqual(len(latest_comparison["current_candidates"]), 2)
                    if "contains_gap" in expected:
                        self.assertIn(
                            expected["contains_gap"],
                            [
                                entry["gap"]["reason"]
                                for entry in record["entries"]
                                if entry["gap"] is not None
                            ],
                        )
                        gap_entry = next(
                            entry
                            for entry in record["entries"]
                            if entry["slot_utc"] == expected["gap_slot_utc"]
                        )
                        self.assertEqual(gap_entry["gap"]["reason"], expected["contains_gap"])
                    if "latest_current_quality" in expected:
                        self.assertEqual(
                            record["entries"][-1]["value"]["comparison"]["current"][
                                "quality_status"
                            ],
                            expected["latest_current_quality"],
                        )

                    rendered = render_observation_hour_series(repository, record)
                    self.assertEqual(rendered.count("<tr data-slot-utc="), 24)
                    self.assertIn(record["series_id"], rendered)
                    self.assertIn("Continuity evidence", rendered)
                    self.assertIn("Current candidates", rendered)
                    self.assertIn("Predecessor candidates", rendered)
                    for entry in record["entries"]:
                        comparison = (
                            entry["value"]["comparison"]
                            if entry["value"] is not None
                            else entry["gap"]["comparison"]
                        )
                        self.assertIn(_escaped_json(entry["continuity"]), rendered)
                        self.assertIn(
                            _escaped_json(comparison["current_candidates"]), rendered
                        )
                        self.assertIn(
                            _escaped_json(comparison["predecessor_candidates"]), rendered
                        )
                    if "latest_gap" in expected:
                        for candidate in latest_comparison["current_candidates"]:
                            self.assertIn(candidate["path"], rendered)
                            self.assertIn(candidate["sha256"], rendered)
                    self.assertNotIn("<script", rendered.lower())
                    self.assertNotIn("http://", rendered.lower())
                    self.assertNotIn("https://", rendered.lower())
                finally:
                    temporary.cleanup()

    def test_independent_repositories_produce_byte_identical_records_html_and_sha256(self) -> None:
        left_tmp, left_repo, left_commit = self._seed("deterministic-max-hour")
        right_tmp, right_repo, right_commit = self._seed("deterministic-max-hour")
        try:
            self.assertEqual(left_commit, right_commit)
            left = build_public_temporal_evidence(left_repo, left_commit)
            right = build_public_temporal_evidence(right_repo, right_commit)
            assert left is not None and right is not None
            left_json = canonical_public_evidence_bytes(left)
            right_json = canonical_public_evidence_bytes(right)
            left_html = render_observation_hour_series(left_repo, left).encode("utf-8")
            right_html = render_observation_hour_series(right_repo, right).encode("utf-8")
            self.assertEqual(left_json, right_json)
            self.assertEqual(left_html, right_html)
            self.assertEqual(hashlib.sha256(left_json).hexdigest(), hashlib.sha256(right_json).hexdigest())
            self.assertEqual(hashlib.sha256(left_html).hexdigest(), hashlib.sha256(right_html).hexdigest())
            self.assertEqual(len(hashlib.sha256(left_html).hexdigest()), 64)
        finally:
            left_tmp.cleanup()
            right_tmp.cleanup()

    def test_direct_renderer_rejects_tampered_record_even_with_recomputed_series_id(self) -> None:
        temporary, repository, commit = self._seed("deterministic-max-hour")
        try:
            record = build_public_temporal_evidence(repository, commit)
            assert record is not None
            tampered = copy.deepcopy(record)
            self.assertIsNotNone(tampered["entries"][-1]["value"])
            tampered["entries"][-1]["value"]["datum"] = 999999999
            tampered["series_id"] = series_id_for_record(tampered)
            with self.assertRaisesRegex(
                ObservationHourSeriesError,
                "immutable Phase 13 replay",
            ):
                render_observation_hour_series(repository, tampered)
        finally:
            temporary.cleanup()


if __name__ == "__main__":
    unittest.main()
