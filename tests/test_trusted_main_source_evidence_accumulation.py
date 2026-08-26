from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import trusted_main_source_evidence_accumulation as accumulation  # noqa: E402


class TrustedMainSourceEvidenceAccumulationTests(unittest.TestCase):
    def _source(self, run_id: int = 10, attempt: int = 1, **overrides: object) -> dict[str, object]:
        source: dict[str, object] = {
            "repository": accumulation.EXPECTED_REPOSITORY,
            "workflow_path": accumulation.EXPECTED_WORKFLOW_PATH,
            "workflow_id": 111,
            "event": "schedule",
            "conclusion": "success",
            "run_id": run_id,
            "run_attempt": attempt,
            "workflow_head_sha": "a" * 40,
            "artifact_name": f"deterministic-publication-intent-{run_id}-{attempt}",
            "publication_intent_bytes": b"{}",
            "snapshot_bytes": b"{}",
        }
        source.update(overrides)
        return source

    def _verified(self, source: dict[str, object], hour: str, path: str | None = None, raw: bytes = b"snapshot\n") -> dict[str, object]:
        run_id = int(source["run_id"])
        attempt = int(source["run_attempt"])
        path = path or f"data/crypto/hourly/2026/08/27/{run_id:04d}_AEST_source_snapshot.json"
        return {
            "input_identity": accumulation._identity(source),
            "workflow_id": int(source["workflow_id"]),
            "run_id": run_id,
            "run_attempt": attempt,
            "workflow_head_sha": source["workflow_head_sha"],
            "artifact_name": source["artifact_name"],
            "publication_intent_sha256": hashlib.sha256(source["publication_intent_bytes"]).hexdigest(),
            "snapshot_sha256": hashlib.sha256(raw).hexdigest(),
            "snapshot_git_blob_sha": accumulation.git_blob_sha(raw),
            "snapshot_commit_sha": "b" * 40,
            "snapshot_path": path,
            "canonical_observation_hour_utc": hour,
            "quality_status": "valid-ok",
            "snapshot_bytes": raw,
        }

    def _build(self, sources: list[dict[str, object]], verified: list[dict[str, object]], **kwargs: object) -> dict[str, object]:
        by_key = {(item["run_id"], item["run_attempt"]): item for item in verified}

        def verifier(repository_root: Path, base_sha: str, config: dict[str, object], source: dict[str, object]) -> dict[str, object]:
            return dict(by_key[(source["run_id"], source["run_attempt"])])

        with (
            mock.patch.object(accumulation, "_require_exact_commit", return_value=("1" * 40, "2" * 40)),
            mock.patch.object(accumulation, "_load_base_config", return_value={}),
            mock.patch.object(accumulation, "_resolve_anchor", return_value="2026-08-27T00:00:00Z"),
            mock.patch.object(accumulation, "_verify_source", side_effect=verifier),
            mock.patch.object(accumulation, "_git_bytes_at", return_value=None),
        ):
            return accumulation.build_accumulation_manifest(
                Path("."),
                "1" * 40,
                sources,
                kwargs.get("recovery_comment_inputs", []),
                kwargs.get("allowed_recovery_issue_numbers", []),
            )

    def test_canonical_json_and_candidate_identity_are_stable(self) -> None:
        payload = {"b": 1, "a": [3, 2, 1]}
        self.assertEqual(accumulation.canonical_json_bytes(payload), b'{"a":[3,2,1],"b":1}')
        self.assertEqual(accumulation.sha256_bytes(b"x"), hashlib.sha256(b"x").hexdigest())

    def test_exact_base_sha_rejects_symbolic_refs(self) -> None:
        with self.assertRaisesRegex(accumulation.AccumulationError, "40-character lowercase"):
            accumulation._require_exact_commit(Path("."), "main")

    def test_window_contains_exactly_next_25_hours(self) -> None:
        manifest = self._build([], [])
        self.assertEqual(len(manifest["hours"]), 25)
        self.assertEqual(manifest["hours"][0]["canonical_observation_hour_utc"], "2026-08-27T01:00:00Z")
        self.assertEqual(manifest["hours"][-1]["canonical_observation_hour_utc"], "2026-08-28T01:00:00Z")

    def test_non_schedule_and_non_success_inputs_are_diagnostic_only(self) -> None:
        sources = [
            self._source(event="workflow_dispatch"),
            self._source(run_id=11, conclusion="failure"),
        ]
        manifest = self._build(sources, [])
        self.assertFalse(manifest["blocking_findings"])
        self.assertEqual(
            [row["kind"] for row in manifest["operational_diagnostics"]],
            ["non-schedule-input", "non-success-input"],
        )

    def test_highest_successful_attempt_supersedes_lower_attempt(self) -> None:
        low = self._source(run_id=12, attempt=1)
        high = self._source(run_id=12, attempt=2)
        candidate = self._verified(high, "2026-08-27T01:00:00Z")
        manifest = self._build([low, high], [candidate])
        self.assertEqual(len(manifest["supersession_records"]), 1)
        self.assertEqual(manifest["supersession_records"][0]["superseded_run_attempt"], 1)
        self.assertEqual(manifest["hours"][0]["disposition"], "eligible")

    def test_distinct_runs_same_hour_are_duplicate_blocker(self) -> None:
        first = self._source(run_id=20)
        second = self._source(run_id=21)
        verified = [
            self._verified(first, "2026-08-27T01:00:00Z", raw=b"one\n"),
            self._verified(second, "2026-08-27T01:00:00Z", raw=b"two\n"),
        ]
        manifest = self._build([first, second], verified)
        self.assertEqual(manifest["hours"][0]["disposition"], "duplicate")
        self.assertEqual(manifest["blocking_findings"][0]["blocker_class"], "duplicate-observation-hour")
        self.assertEqual(manifest["added_paths"], [])

    def test_anchor_selects_highest_phase13_validated_current_candidate(self) -> None:
        population = [
            "2026-08-27T00:00:00Z",
            "2026-08-27T01:00:00Z",
            "2026-08-27T02:00:00Z",
        ]

        def resolve(repository_root: Path, base_sha: str, slot: str) -> dict[str, object]:
            if slot == "2026-08-27T02:00:00Z":
                return {"current": {"observation_hour_utc": slot}}
            return {
                "current": {
                    "observation_hour_utc": slot,
                    "quality_status": "valid-ok",
                }
            }

        with (
            mock.patch.object(accumulation, "load_observation_hour_population", return_value=population),
            mock.patch.object(accumulation, "resolve_observation_hour_adjacency", side_effect=resolve) as resolver,
        ):
            anchor = accumulation._resolve_anchor(Path("."), "1" * 40)
        self.assertEqual(anchor, "2026-08-27T01:00:00Z")
        self.assertEqual(resolver.call_args_list[0].args[-1], "2026-08-27T02:00:00Z")

    def test_unverifiable_successful_input_is_hard_blocker(self) -> None:
        source = self._source(run_id=30)
        with (
            mock.patch.object(accumulation, "_require_exact_commit", return_value=("1" * 40, "2" * 40)),
            mock.patch.object(accumulation, "_load_base_config", return_value={}),
            mock.patch.object(accumulation, "_resolve_anchor", return_value="2026-08-27T00:00:00Z"),
            mock.patch.object(accumulation, "_verify_source", side_effect=ValueError("unsafe")),
        ):
            manifest = accumulation.build_accumulation_manifest(Path("."), "1" * 40, [source])
        self.assertEqual(manifest["blocking_findings"][0]["blocker_class"], "source-input-unverifiable")
        self.assertEqual(manifest["hours"][0]["disposition"], "no-promotable-observation")

    def test_already_trusted_identical_bytes_are_not_added(self) -> None:
        source = self._source(run_id=40)
        candidate = self._verified(source, "2026-08-27T01:00:00Z", raw=b"same\n")
        with mock.patch.object(accumulation, "_git_bytes_at", return_value=b"same\n"):
            manifest = self._build([source], [candidate])
        self.assertEqual(manifest["hours"][0]["disposition"], "eligible")
        # _build owns the final _git_bytes_at patch; exercise classification explicitly below.
        with (
            mock.patch.object(accumulation, "_require_exact_commit", return_value=("1" * 40, "2" * 40)),
            mock.patch.object(accumulation, "_load_base_config", return_value={}),
            mock.patch.object(accumulation, "_resolve_anchor", return_value="2026-08-27T00:00:00Z"),
            mock.patch.object(accumulation, "_verify_source", return_value=candidate),
            mock.patch.object(accumulation, "_git_bytes_at", return_value=b"same\n"),
        ):
            manifest = accumulation.build_accumulation_manifest(Path("."), "1" * 40, [source])
        self.assertEqual(manifest["hours"][0]["disposition"], "already-trusted")
        self.assertEqual(manifest["added_paths"], [])

    def test_trusted_path_conflict_is_hard_blocker(self) -> None:
        source = self._source(run_id=41)
        candidate = self._verified(source, "2026-08-27T01:00:00Z", raw=b"incoming\n")
        with (
            mock.patch.object(accumulation, "_require_exact_commit", return_value=("1" * 40, "2" * 40)),
            mock.patch.object(accumulation, "_load_base_config", return_value={}),
            mock.patch.object(accumulation, "_resolve_anchor", return_value="2026-08-27T00:00:00Z"),
            mock.patch.object(accumulation, "_verify_source", return_value=candidate),
            mock.patch.object(accumulation, "_git_bytes_at", return_value=b"trusted\n"),
        ):
            manifest = accumulation.build_accumulation_manifest(Path("."), "1" * 40, [source])
        self.assertEqual(manifest["hours"][0]["disposition"], "path-conflict")
        self.assertEqual(manifest["blocking_findings"][0]["blocker_class"], "trusted-path-conflict")

    def test_recovery_body_must_contain_exactly_one_machine_record(self) -> None:
        record = {"contract": accumulation.RECOVERY_CONTRACT}
        self.assertEqual(accumulation._parse_recovery_body(json.dumps(record)), record)
        fenced = "owner decision\n```json\n" + json.dumps(record) + "\n```"
        self.assertEqual(accumulation._parse_recovery_body(fenced), record)
        duplicate = fenced + "\n```json\n" + json.dumps(record) + "\n```"
        with self.assertRaisesRegex(ValueError, "exactly one"):
            accumulation._parse_recovery_body(duplicate)

    def test_recovery_requires_exact_owner_repository_disposition_and_body_bytes(self) -> None:
        blocker = accumulation._blocker("x", [{"run_id": 1}], None)
        record = {
            "contract": accumulation.RECOVERY_CONTRACT,
            "repository": accumulation.EXPECTED_REPOSITORY,
            "disposition": accumulation.RECOVERY_DISPOSITION,
            "blocker_class": "x",
            "blocker_fingerprint": blocker["blocker_fingerprint"],
            "canonical_observation_hour_utc": None,
            "input_identities": blocker["input_identities"],
            "reason": "owner exclusion",
        }
        body_bytes = json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")
        recovered, applied, recovery_blockers = accumulation._apply_recoveries(
            [blocker],
            [
                {
                    "issue_number": 523,
                    "comment_id": 100,
                    "author_login": accumulation.OWNER_LOGIN,
                    "body_bytes": body_bytes,
                }
            ],
            {523},
        )
        self.assertEqual(recovered, {blocker["blocker_fingerprint"]})
        self.assertFalse(recovery_blockers)
        self.assertEqual(
            applied[0]["carrier"]["body_sha256"],
            hashlib.sha256(body_bytes).hexdigest(),
        )
        self.assertEqual(applied[0]["carrier"]["comment_id"], 100)

    def test_recovery_repository_or_disposition_edit_restores_hard_block(self) -> None:
        blocker = accumulation._blocker("x", [{"run_id": 1}], None)
        base_record = {
            "contract": accumulation.RECOVERY_CONTRACT,
            "repository": accumulation.EXPECTED_REPOSITORY,
            "disposition": accumulation.RECOVERY_DISPOSITION,
            "blocker_class": "x",
            "blocker_fingerprint": blocker["blocker_fingerprint"],
            "canonical_observation_hour_utc": None,
            "input_identities": blocker["input_identities"],
            "reason": "owner exclusion",
        }
        for field, value in (("repository", "other/repo"), ("disposition", "promote")):
            edited = dict(base_record)
            edited[field] = value
            body_bytes = json.dumps(edited, sort_keys=True, separators=(",", ":")).encode("utf-8")
            recovered, applied, recovery_blockers = accumulation._apply_recoveries(
                [blocker],
                [{"issue_number": 523, "comment_id": 101, "author_login": accumulation.OWNER_LOGIN, "body_bytes": body_bytes}],
                {523},
            )
            self.assertFalse(recovered)
            self.assertFalse(applied)
            self.assertEqual(recovery_blockers[0]["blocker_class"], "recovery-decision-invalid")

    def test_recovery_carrier_rejects_non_utf8_or_wrong_owner(self) -> None:
        blocker = accumulation._blocker("x", [], None)
        bad_inputs = [
            {"issue_number": 523, "comment_id": 1, "author_login": accumulation.OWNER_LOGIN, "body_bytes": b"\xff"},
            {"issue_number": 523, "comment_id": 2, "author_login": "not-owner", "body_bytes": b"{}"},
        ]
        recovered, applied, recovery_blockers = accumulation._apply_recoveries(blocker and [blocker], bad_inputs, {523})
        self.assertFalse(recovered)
        self.assertFalse(applied)
        self.assertEqual(len(recovery_blockers), 2)

    def test_blocker_fingerprint_is_stable_under_input_order(self) -> None:
        first = accumulation._blocker("duplicate", [{"run_id": 2}, {"run_id": 1}], "2026-08-27T01:00:00Z")
        second = accumulation._blocker("duplicate", [{"run_id": 1}, {"run_id": 2}], "2026-08-27T01:00:00Z")
        self.assertEqual(first["blocker_fingerprint"], second["blocker_fingerprint"])
        self.assertEqual(first["input_identities"], second["input_identities"])

    def test_anchor_unavailable_is_fail_closed(self) -> None:
        with (
            mock.patch.object(accumulation, "_require_exact_commit", return_value=("1" * 40, "2" * 40)),
            mock.patch.object(accumulation, "_load_base_config", return_value={}),
            mock.patch.object(accumulation, "_resolve_anchor", return_value=None),
        ):
            manifest = accumulation.build_accumulation_manifest(Path("."), "1" * 40, [])
        self.assertIsNone(manifest["anchor_observation_hour_utc"])
        self.assertEqual(manifest["blocking_findings"][0]["blocker_class"], "anchor-unavailable")
        self.assertEqual(manifest["added_paths"], [])

    def test_decode_source_input_uses_exact_base64_bytes(self) -> None:
        decoded = accumulation.decode_source_input(
            {"publication_intent_base64": "e30=", "snapshot_base64": "e30K"}
        )
        self.assertEqual(decoded["publication_intent_bytes"], b"{}")
        self.assertEqual(decoded["snapshot_bytes"], b"{}\n")
        recovery = accumulation.decode_recovery_input({"body_base64": "e30K"})
        self.assertEqual(recovery["body_bytes"], b"{}\n")

    def test_manifest_replay_is_byte_identical(self) -> None:
        source = self._source(run_id=50)
        candidate = self._verified(source, "2026-08-27T02:00:00Z")
        first = self._build([source], [candidate])
        second = self._build([source], [candidate])
        self.assertEqual(accumulation.canonical_json_bytes(first), accumulation.canonical_json_bytes(second))
        self.assertEqual(first["candidate_id"], second["candidate_id"])


if __name__ == "__main__":
    unittest.main()
