from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from deterministic_site_publication import CONTRACT as PUBLICATION_CONTRACT  # noqa: E402
from resolve_crypto_observation_hour_adjacency import PINNED_REFS  # noqa: E402
from trusted_main_source_evidence_accumulation import (  # noqa: E402
    CONTRACT,
    EXPECTED_REPOSITORY,
    EXPECTED_WORKFLOW_PATH,
    OWNER_LOGIN,
    RECOVERY_CONTRACT,
    RECOVERY_DISPOSITION,
    build_accumulation_manifest,
    canonical_json_bytes,
    sha256_bytes,
)

CORPUS = ROOT / "tests" / "fixtures" / "phase17_trusted_main_source_evidence_accumulation_v1_1.json"
VALID_SNAPSHOT = ROOT / "tests" / "fixtures" / "valid_ok_snapshot.json"
INVALID_SNAPSHOT = ROOT / "tests" / "fixtures" / "invalid_missing_required_asset_field.json"
BASE_HOUR = datetime(2026, 8, 27, 0, 0, tzinfo=timezone.utc)
WORKFLOW_ID = 9001

EXPECTED_SCENARIOS = {
    "fully-contiguous-25-hour-valid-population",
    "missing-hour-later-valid",
    "failed-run-diagnostic-only",
    "delayed-success-actual-containing-hour",
    "rerun-highest-attempt-different-hour",
    "distinct-runs-same-hour-duplicate",
    "artifact-hash-mismatch",
    "successful-run-artifact-unavailable",
    "current-main-validation-failure",
    "already-trusted-identical",
    "trusted-path-conflict",
    "invalid-evidence-recovery-later-valid",
    "duplicate-recovery-whole-set",
    "unavailable-input-null-hour-recovery",
    "recovery-drift-restores-hard-block",
    "candidate-base-change-reclassifies",
    "recovery-no-eligible-additions",
    "byte-identical-replay",
}


def _git(repository: Path, *args: str, input_bytes: bytes | None = None) -> bytes:
    env = os.environ.copy()
    env.update(
        {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_OPTIONAL_LOCKS": "0",
            "LC_ALL": "C",
            "GIT_AUTHOR_NAME": "Phase 17 proof",
            "GIT_AUTHOR_EMAIL": "phase17@example.invalid",
            "GIT_AUTHOR_DATE": "2026-08-27T00:00:00Z",
            "GIT_COMMITTER_NAME": "Phase 17 proof",
            "GIT_COMMITTER_EMAIL": "phase17@example.invalid",
            "GIT_COMMITTER_DATE": "2026-08-27T00:00:00Z",
        }
    )
    completed = subprocess.run(
        ["git", "-C", str(repository), *args],
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        env=env,
    )
    if completed.returncode != 0:
        raise AssertionError(completed.stderr.decode("utf-8", errors="replace"))
    return completed.stdout


def _text(raw: bytes) -> str:
    return raw.decode("utf-8", errors="strict").strip()


def _utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _hour(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0).strftime("%Y-%m-%dT%H:00:00Z")


def _snapshot(
    generated: datetime,
    *,
    path_override: str | None = None,
    invalid_hour: bool = False,
    template: Path = VALID_SNAPSHOT,
) -> tuple[str, bytes]:
    payload = copy.deepcopy(json.loads(template.read_text(encoding="utf-8")))
    zone = ZoneInfo("Australia/Sydney")
    local = generated.astimezone(zone)
    run = payload["run"]
    run.update(
        {
            "generated_at_utc": _utc(generated),
            "generated_at_local": local.isoformat(),
            "timezone": zone.key,
            "timezone_abbreviation": local.tzname(),
            "observation_hour_utc": _hour(generated + (timedelta(hours=1) if invalid_hour else timedelta())),
            "producer": "github-actions",
            "cadence": "hourly",
        }
    )
    for source in payload.get("sources", {}).values():
        if isinstance(source, dict) and "fetched_at_utc" in source:
            source["fetched_at_utc"] = _utc(generated)
    for asset in payload.get("market", {}).get("assets", []):
        if isinstance(asset, dict) and "last_updated" in asset:
            asset["last_updated"] = _utc(generated)
    if path_override is None:
        safe = "".join(ch for ch in (local.tzname() or "LOCAL") if ch.isalnum()) or "LOCAL"
        path_override = (
            f"data/crypto/hourly/{local.year:04d}/{local.month:02d}/{local.day:02d}/"
            f"{local.hour:02d}{local.minute:02d}_{safe}_source_snapshot.json"
        )
    raw = (
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False) + "\n"
    ).encode("utf-8")
    return path_override, raw


class Phase17TrustedMainSourceEvidenceProofTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.corpus = json.loads(CORPUS.read_text(encoding="utf-8"))

    def _seed(
        self,
        *,
        anchor: bool = True,
        extra_base_files: dict[str, bytes] | None = None,
    ) -> tuple[tempfile.TemporaryDirectory[str], Path, str]:
        temporary = tempfile.TemporaryDirectory(prefix="phase17-proof-")
        repository = Path(temporary.name)
        _git(repository, "init", "-q")
        files: dict[str, bytes] = {
            ref["path"]: (ROOT / ref["path"]).read_bytes() for ref in PINNED_REFS.values()
        }
        if anchor:
            anchor_path, anchor_raw = _snapshot(BASE_HOUR + timedelta(minutes=17))
            files[anchor_path] = anchor_raw
        files.update(extra_base_files or {})
        for path, raw in sorted(files.items()):
            target = repository / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
        _git(repository, "add", "-A")
        tree = _text(_git(repository, "write-tree"))
        commit = _text(
            _git(
                repository,
                "-c",
                "commit.gpgsign=false",
                "commit-tree",
                tree,
                input_bytes=b"phase17 proof base\n",
            )
        )
        return temporary, repository, commit

    def _child_commit(self, repository: Path, base: str, files: dict[str, bytes], message: bytes) -> str:
        _git(repository, "read-tree", base)
        for path, raw in sorted(files.items()):
            target = repository / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
            _git(repository, "add", "--", path)
        tree = _text(_git(repository, "write-tree"))
        return _text(
            _git(
                repository,
                "-c",
                "commit.gpgsign=false",
                "commit-tree",
                tree,
                "-p",
                base,
                input_bytes=message,
            )
        )

    def _source(
        self,
        repository: Path,
        base: str,
        offset: int,
        run_id: int,
        attempt: int = 1,
        *,
        minute: int = 17,
        path_override: str | None = None,
        raw_override: bytes | None = None,
        artifact_name: str | None = None,
        intent_changes: dict[str, Any] | None = None,
        commit_snapshot: bool = True,
    ) -> dict[str, Any]:
        generated = BASE_HOUR + timedelta(hours=offset, minutes=minute)
        path, raw = _snapshot(generated, path_override=path_override)
        if raw_override is not None:
            raw = raw_override
        snapshot_commit = "f" * 40
        if commit_snapshot:
            snapshot_commit = self._child_commit(
                repository,
                base,
                {path: raw},
                f"source {run_id}/{attempt}\n".encode(),
            )
        snapshot_payload = json.loads(raw.decode("utf-8"))
        observation_hour = snapshot_payload["run"]["observation_hour_utc"]
        intent: dict[str, Any] = {
            "publication_contract": PUBLICATION_CONTRACT,
            "source_workflow_id": WORKFLOW_ID,
            "source_workflow_path": EXPECTED_WORKFLOW_PATH,
            "source_workflow_run_id": run_id,
            "source_workflow_run_attempt": attempt,
            "source_workflow_head_sha": base,
            "main_base_sha": base,
            "snapshot_commit_sha": snapshot_commit,
            "snapshot_path": path,
            "snapshot_sha256": hashlib.sha256(raw).hexdigest(),
            "generated_at_utc": snapshot_payload["run"]["generated_at_utc"],
            "observation_hour_utc": observation_hour,
            "observation_hour_compact": observation_hour.replace("-", "").replace(":", "")[:11] + "Z",
            "snapshot_quality": "valid-ok",
            "blocking_issues": [],
            "non_blocking_warnings": [],
            "warnings": [],
            "errors": [],
            "automatic_eligible": True,
            "refusal_reasons": [],
        }
        intent.update(intent_changes or {})
        return {
            "repository": EXPECTED_REPOSITORY,
            "workflow_path": EXPECTED_WORKFLOW_PATH,
            "workflow_id": WORKFLOW_ID,
            "event": "schedule",
            "conclusion": "success",
            "run_id": run_id,
            "run_attempt": attempt,
            "workflow_head_sha": base,
            "artifact_name": artifact_name or f"deterministic-publication-intent-{run_id}-{attempt}",
            "publication_intent_bytes": canonical_json_bytes(intent) + b"\n",
            "snapshot_bytes": raw,
        }

    def _recovery(
        self,
        blocker: dict[str, Any],
        *,
        record_changes: dict[str, Any] | None = None,
        comment_id: int = 5439990001,
    ) -> dict[str, Any]:
        record = {
            "contract": RECOVERY_CONTRACT,
            "repository": EXPECTED_REPOSITORY,
            "disposition": RECOVERY_DISPOSITION,
            "blocker_class": blocker["blocker_class"],
            "blocker_fingerprint": blocker["blocker_fingerprint"],
            "canonical_observation_hour_utc": blocker["canonical_observation_hour_utc"],
            "input_identities": blocker["input_identities"],
            "reason": "owner explicitly excludes this exact blocker evidence",
        }
        record.update(record_changes or {})
        return {
            "issue_number": int(self.corpus["recovery_issue"]),
            "comment_id": comment_id,
            "author_login": OWNER_LOGIN,
            "body_bytes": canonical_json_bytes(record),
        }

    def test_proof_corpus_declares_exact_18_approved_scenarios(self) -> None:
        self.assertEqual(set(self.corpus["scenarios"]), EXPECTED_SCENARIOS)
        self.assertEqual(len(self.corpus["scenarios"]), 18)
        self.assertEqual(self.corpus["window_hours"], 25)
        self.assertEqual(self.corpus["identity_policy"], "recompute-from-exact-materialised-inputs")

    def test_fully_contiguous_25_hour_valid_population(self) -> None:
        temporary, repo, base = self._seed()
        try:
            sources = [self._source(repo, base, offset, 1000 + offset) for offset in range(1, 26)]
            manifest = build_accumulation_manifest(repo, base, sources)
            self.assertEqual([row["disposition"] for row in manifest["hours"]], ["eligible"] * 25)
            self.assertEqual(len(manifest["added_paths"]), 25)
            self.assertEqual(manifest["blocking_findings"], [])
        finally:
            temporary.cleanup()

    def test_missing_hour_later_valid(self) -> None:
        temporary, repo, base = self._seed()
        try:
            first = self._source(repo, base, 1, 1101)
            later = self._source(repo, base, 3, 1103)
            manifest = build_accumulation_manifest(repo, base, [first, later])
            self.assertEqual(
                [row["disposition"] for row in manifest["hours"][:3]],
                ["eligible", "no-promotable-observation", "eligible"],
            )
            self.assertEqual(len(manifest["added_paths"]), 2)
        finally:
            temporary.cleanup()

    def test_failed_run_is_diagnostic_only(self) -> None:
        temporary, repo, base = self._seed()
        try:
            failed = {
                "repository": EXPECTED_REPOSITORY,
                "workflow_path": EXPECTED_WORKFLOW_PATH,
                "workflow_id": WORKFLOW_ID,
                "event": "schedule",
                "conclusion": "failure",
                "run_id": 1201,
                "run_attempt": 1,
                "workflow_head_sha": base,
                "artifact_name": "deterministic-publication-intent-1201-1",
            }
            manifest = build_accumulation_manifest(repo, base, [failed])
            self.assertEqual(manifest["operational_diagnostics"][0]["kind"], "non-success-input")
            self.assertTrue(all(row["disposition"] == "no-promotable-observation" for row in manifest["hours"]))
            self.assertEqual(manifest["blocking_findings"], [])
        finally:
            temporary.cleanup()

    def test_delayed_success_uses_actual_snapshot_containing_hour(self) -> None:
        temporary, repo, base = self._seed()
        try:
            source = self._source(repo, base, 2, 1301, minute=5)
            source["run_started_at_utc"] = "2026-08-27T01:59:50Z"
            manifest = build_accumulation_manifest(repo, base, [source])
            self.assertEqual(manifest["hours"][0]["disposition"], "no-promotable-observation")
            self.assertEqual(manifest["hours"][1]["disposition"], "eligible")
            self.assertEqual(
                manifest["verified_source_inputs"][0]["canonical_observation_hour_utc"],
                "2026-08-27T02:00:00Z",
            )
        finally:
            temporary.cleanup()

    def test_rerun_highest_successful_attempt_can_resolve_to_different_hour(self) -> None:
        temporary, repo, base = self._seed()
        try:
            low = self._source(repo, base, 1, 1401, 1)
            high = self._source(repo, base, 2, 1401, 2)
            manifest = build_accumulation_manifest(repo, base, [low, high])
            self.assertEqual(manifest["hours"][0]["disposition"], "no-promotable-observation")
            self.assertEqual(manifest["hours"][1]["disposition"], "eligible")
            self.assertEqual(manifest["supersession_records"][0]["superseded_run_attempt"], 1)
            self.assertEqual(manifest["verified_source_inputs"][0]["run_attempt"], 2)
        finally:
            temporary.cleanup()

    def test_distinct_runs_same_hour_are_duplicate_with_no_winner(self) -> None:
        temporary, repo, base = self._seed()
        try:
            first = self._source(repo, base, 1, 1501)
            second = self._source(repo, base, 1, 1502)
            manifest = build_accumulation_manifest(repo, base, [first, second])
            self.assertEqual(manifest["hours"][0]["disposition"], "duplicate")
            self.assertEqual(manifest["blocking_findings"][0]["blocker_class"], "duplicate-observation-hour")
            self.assertEqual(manifest["added_paths"], [])
        finally:
            temporary.cleanup()

    def test_artifact_hash_mismatch_is_input_level_blocker(self) -> None:
        temporary, repo, base = self._seed()
        try:
            source = self._source(repo, base, 1, 1601, intent_changes={"snapshot_sha256": "0" * 64})
            manifest = build_accumulation_manifest(repo, base, [source])
            self.assertEqual(manifest["blocking_findings"][0]["blocker_class"], "source-input-unverifiable")
            self.assertIsNone(manifest["blocking_findings"][0]["canonical_observation_hour_utc"])
            self.assertEqual(manifest["added_paths"], [])
        finally:
            temporary.cleanup()

    def test_successful_run_with_unavailable_artifact_is_null_hour_blocker(self) -> None:
        temporary, repo, base = self._seed()
        try:
            source = self._source(repo, base, 1, 1701)
            source["snapshot_bytes"] = None
            manifest = build_accumulation_manifest(repo, base, [source])
            blocker = manifest["blocking_findings"][0]
            self.assertEqual(blocker["blocker_class"], "source-input-unverifiable")
            self.assertIsNone(blocker["canonical_observation_hour_utc"])
            self.assertTrue(all(row["disposition"] == "no-promotable-observation" for row in manifest["hours"]))
        finally:
            temporary.cleanup()

    def test_current_main_validation_failure_is_input_level_blocker(self) -> None:
        temporary, repo, base = self._seed()
        try:
            path, invalid_raw = _snapshot(
                BASE_HOUR + timedelta(hours=1, minutes=17),
                template=INVALID_SNAPSHOT,
            )
            source = self._source(repo, base, 1, 1801, path_override=path, raw_override=invalid_raw)
            manifest = build_accumulation_manifest(repo, base, [source])
            self.assertEqual(manifest["blocking_findings"][0]["blocker_class"], "source-input-unverifiable")
            self.assertIsNone(manifest["blocking_findings"][0]["canonical_observation_hour_utc"])
        finally:
            temporary.cleanup()

    def test_already_trusted_identical(self) -> None:
        trusted_path = "data/crypto/hourly/2026/08/27/9999_AEST_source_snapshot.json"
        path, raw = _snapshot(BASE_HOUR + timedelta(hours=1, minutes=17), path_override=trusted_path)
        temporary, repo, base = self._seed(extra_base_files={path: raw})
        try:
            source = self._source(repo, base, 1, 1901, path_override=path, raw_override=raw)
            manifest = build_accumulation_manifest(repo, base, [source])
            self.assertEqual(manifest["hours"][0]["disposition"], "already-trusted")
            self.assertEqual(manifest["added_paths"], [])
        finally:
            temporary.cleanup()

    def test_trusted_path_conflict_binds_staged_and_trusted_identities(self) -> None:
        path, occupant = _snapshot(BASE_HOUR + timedelta(hours=1, minutes=17), invalid_hour=True)
        temporary, repo, base = self._seed(extra_base_files={path: occupant})
        try:
            source = self._source(repo, base, 1, 2001, path_override=path)
            manifest = build_accumulation_manifest(repo, base, [source])
            blocker = manifest["blocking_findings"][0]
            self.assertEqual(manifest["hours"][0]["disposition"], "path-conflict")
            self.assertEqual(blocker["blocker_class"], "trusted-path-conflict")
            self.assertEqual(blocker["staged_snapshot_identity"]["path"], path)
            self.assertEqual(blocker["trusted_main_identity"]["base_sha"], base)
        finally:
            temporary.cleanup()

    def test_invalid_evidence_recovery_allows_later_valid_only(self) -> None:
        temporary, repo, base = self._seed()
        try:
            bad = self._source(repo, base, 1, 2101, path_override="../unsafe_source_snapshot.json", commit_snapshot=False)
            later = self._source(repo, base, 2, 2102)
            initial = build_accumulation_manifest(repo, base, [bad, later])
            self.assertEqual(initial["hours"][1]["disposition"], "eligible")
            self.assertEqual(initial["added_paths"], [])
            recovery = self._recovery(initial["blocking_findings"][0])
            manifest = build_accumulation_manifest(repo, base, [bad, later], [recovery], [523])
            self.assertEqual(manifest["blocking_findings"], [])
            self.assertEqual(len(manifest["added_paths"]), 1)
            self.assertEqual(manifest["added_paths"][0]["canonical_observation_hour_utc"], "2026-08-27T02:00:00Z")
        finally:
            temporary.cleanup()

    def test_duplicate_recovery_excludes_entire_set_and_never_elects_winner(self) -> None:
        temporary, repo, base = self._seed()
        try:
            first = self._source(repo, base, 1, 2201)
            second = self._source(repo, base, 1, 2202)
            later = self._source(repo, base, 2, 2203)
            initial = build_accumulation_manifest(repo, base, [first, second, later])
            recovery = self._recovery(initial["blocking_findings"][0])
            manifest = build_accumulation_manifest(repo, base, [first, second, later], [recovery], [523])
            self.assertEqual(manifest["hours"][0]["disposition"], "terminal-excluded")
            self.assertEqual(len(manifest["hours"][0]["source_candidates"]), 2)
            self.assertEqual(manifest["blocking_findings"], [])
            self.assertEqual(len(manifest["added_paths"]), 1)
            self.assertEqual(manifest["added_paths"][0]["canonical_observation_hour_utc"], "2026-08-27T02:00:00Z")
        finally:
            temporary.cleanup()

    def test_unavailable_input_null_hour_recovery_does_not_synthesise_hour(self) -> None:
        temporary, repo, base = self._seed()
        try:
            unavailable = self._source(repo, base, 1, 2301)
            unavailable["publication_intent_bytes"] = None
            later = self._source(repo, base, 3, 2303)
            initial = build_accumulation_manifest(repo, base, [unavailable, later])
            blocker = initial["blocking_findings"][0]
            self.assertIsNone(blocker["canonical_observation_hour_utc"])
            recovery = self._recovery(blocker)
            manifest = build_accumulation_manifest(repo, base, [unavailable, later], [recovery], [523])
            self.assertEqual(manifest["hours"][0]["disposition"], "no-promotable-observation")
            self.assertEqual(manifest["hours"][1]["disposition"], "no-promotable-observation")
            self.assertEqual(manifest["hours"][2]["disposition"], "eligible")
            self.assertEqual(len(manifest["added_paths"]), 1)
        finally:
            temporary.cleanup()

    def test_recovery_body_or_blocker_drift_restores_hard_block(self) -> None:
        temporary, repo, base = self._seed()
        try:
            bad = self._source(repo, base, 1, 2401, path_override="../unsafe_source_snapshot.json", commit_snapshot=False)
            initial = build_accumulation_manifest(repo, base, [bad])
            blocker = initial["blocking_findings"][0]
            edited = self._recovery(blocker, record_changes={"repository": "other/repo"})
            stale = self._recovery(blocker, record_changes={"blocker_fingerprint": "0" * 64}, comment_id=5439990002)
            for recovery in (edited, stale):
                manifest = build_accumulation_manifest(repo, base, [bad], [recovery], [523])
                self.assertIn(
                    "recovery-decision-invalid",
                    [row["blocker_class"] for row in manifest["blocking_findings"]],
                )
                self.assertEqual(manifest["added_paths"], [])
        finally:
            temporary.cleanup()

    def test_candidate_base_change_changes_anchor_tree_identity_and_reclassification(self) -> None:
        temporary, repo, base = self._seed()
        try:
            source = self._source(repo, base, 1, 2501)
            first = build_accumulation_manifest(repo, base, [source])
            intent = json.loads(source["publication_intent_bytes"])
            second_base = self._child_commit(
                repo,
                base,
                {intent["snapshot_path"]: source["snapshot_bytes"]},
                b"advance trusted base\n",
            )
            second = build_accumulation_manifest(repo, second_base, [source])
            self.assertNotEqual(first["base_sha"], second["base_sha"])
            self.assertNotEqual(first["base_tree_sha"], second["base_tree_sha"])
            self.assertNotEqual(first["candidate_id"], second["candidate_id"])
            self.assertEqual(first["anchor_observation_hour_utc"], "2026-08-27T00:00:00Z")
            self.assertEqual(second["anchor_observation_hour_utc"], "2026-08-27T01:00:00Z")
            self.assertEqual(len(first["added_paths"]), 1)
            self.assertEqual(second["added_paths"], [])
            self.assertIn("verified-input-outside-window", [row["kind"] for row in second["operational_diagnostics"]])
        finally:
            temporary.cleanup()

    def test_recovery_with_no_later_eligible_additions_stays_empty(self) -> None:
        temporary, repo, base = self._seed()
        try:
            bad = self._source(repo, base, 1, 2601, path_override="../unsafe_source_snapshot.json", commit_snapshot=False)
            initial = build_accumulation_manifest(repo, base, [bad])
            recovery = self._recovery(initial["blocking_findings"][0])
            manifest = build_accumulation_manifest(repo, base, [bad], [recovery], [523])
            self.assertEqual(manifest["blocking_findings"], [])
            self.assertEqual(manifest["added_paths"], [])
            self.assertTrue(all(row["disposition"] == "no-promotable-observation" for row in manifest["hours"]))
        finally:
            temporary.cleanup()

    def test_byte_identical_replay(self) -> None:
        temporary, repo, base = self._seed()
        try:
            sources = [self._source(repo, base, 2, 2701), self._source(repo, base, 4, 2702)]
            first = build_accumulation_manifest(repo, base, sources)
            second = build_accumulation_manifest(repo, base, list(reversed(sources)))
            self.assertEqual(first["candidate_id"], second["candidate_id"])
            self.assertEqual(canonical_json_bytes(first), canonical_json_bytes(second))
            self.assertEqual(sha256_bytes(canonical_json_bytes(first)), sha256_bytes(canonical_json_bytes(second)))
            self.assertEqual(first["contract"], CONTRACT)
        finally:
            temporary.cleanup()


if __name__ == "__main__":
    unittest.main()
