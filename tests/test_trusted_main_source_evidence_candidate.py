from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import trusted_main_source_evidence_candidate as candidate  # noqa: E402

FIXTURE = ROOT / "tests/fixtures/phase17_trusted_main_source_evidence_candidate_v1.json"
WORKFLOW = ROOT / ".github/workflows/build-trusted-main-source-evidence-candidate.yml"


class TrustedMainSourceEvidenceCandidateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def base_capture(self) -> dict[str, object]:
        return copy.deepcopy(self.fixture["base_capture"])

    def test_workflow_is_manual_only_with_exact_two_job_permissions_and_concurrency(self) -> None:
        workflow = yaml.load(WORKFLOW.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
        self.assertEqual(set(workflow["on"]), {"workflow_dispatch"})
        self.assertEqual(set(workflow["jobs"]), {"prepare", "publish"})
        self.assertEqual(
            workflow["jobs"]["prepare"]["permissions"],
            {"actions": "read", "contents": "read", "issues": "read", "pull-requests": "read"},
        )
        self.assertEqual(
            workflow["jobs"]["publish"]["permissions"],
            {"actions": "read", "contents": "write", "issues": "read", "pull-requests": "write"},
        )
        self.assertEqual(workflow["concurrency"]["group"], "phase17-source-evidence-candidate")
        self.assertEqual(workflow["concurrency"]["cancel-in-progress"], "false")
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertNotIn("workflow_run:", text)
        self.assertNotIn("issue_comment:", text)
        self.assertNotIn("repository_dispatch:", text)
        self.assertNotIn("gh pr merge", text)
        self.assertNotIn("enable-auto-merge", text)
        self.assertIn("persist-credentials: false", text)

    def test_workflow_contains_exact_main_object_replay_and_freshness_guards(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertGreaterEqual(text.count('live_main="$(gh api'), 4)
        self.assertGreaterEqual(text.count("fetch --no-tags origin"), 1)
        self.assertIn('"fetch",', text)
        self.assertIn("git-object-proof.json", text)
        self.assertGreaterEqual(text.count("git cat-file -e"), 2)
        self.assertGreaterEqual(text.count('"cat-file", "-e"'), 2)
        self.assertGreaterEqual(text.count("cmp --silent"), 1)
        self.assertIn("bytes_match", text)
        self.assertIn("intent_reference_valid", text)
        self.assertGreaterEqual(text.count('"workflow_id": workflow_id'), 2)
        self.assertGreaterEqual(text.count("ARTIFACT_NAME_RE.fullmatch"), 2)
        self.assertIn("candidate-evidence.json", text)
        self.assertIn("--force-with-lease=", text)
        self.assertIn("verify-closure", text)
        self.assertGreaterEqual(text.count("verify-recoveries"), 3)
        self.assertIn("verify-pr", text)
        self.assertIn("retention-days: 14", text)

    def test_census_bounds_cover_full_rerun_horizon_without_creating_hour_authority(self) -> None:
        bounds = candidate.census_bounds(
            {"start_utc": "2026-08-27T01:00:00Z", "end_utc": "2026-08-28T01:00:00Z"}
        )
        self.assertEqual(bounds["start_utc"], "2026-07-27T01:00:00Z")
        self.assertEqual(bounds["end_utc"], "2026-08-28T02:00:00Z")

    def test_population_closure_is_canonical_and_binds_complete_attempt_artifact_state(self) -> None:
        closure = candidate.build_source_population_closure(self.base_capture())
        self.assertEqual(closure["contract"], candidate.CLOSURE_CONTRACT)
        self.assertEqual(closure["workflow_id"], 77)
        self.assertEqual(closure["discovered_run_ids"], [100])
        self.assertEqual(closure["retained_artifact_extension_run_ids"], [100])
        attempt = closure["runs"][0]["attempts"][0]
        self.assertEqual(attempt["run_attempt"], 1)
        self.assertEqual(attempt["artifact"]["availability"], "retained")
        self.assertEqual(attempt["artifact"]["artifact"]["id"], 9001)
        identity = dict(closure)
        digest = identity.pop("sha256")
        self.assertEqual(digest, hashlib.sha256(candidate.canonical_json_bytes(identity)).hexdigest())
        self.assertEqual(
            candidate.canonical_json_bytes(closure),
            candidate.canonical_json_bytes(candidate.build_source_population_closure(self.base_capture())),
        )

    def test_incomplete_attempt_enumeration_fails_closed(self) -> None:
        capture = self.base_capture()
        capture["runs"][0]["latest_run_attempt"] = 2
        with self.assertRaisesRegex(candidate.CandidateError, "attempt enumeration is incomplete"):
            candidate.build_source_population_closure(capture)

    def test_duplicate_exact_artifact_carrier_fails_closed(self) -> None:
        capture = self.base_capture()
        duplicate = copy.deepcopy(capture["runs"][0]["artifacts"][0])
        duplicate["id"] = 9002
        capture["runs"][0]["artifacts"].append(duplicate)
        with self.assertRaisesRegex(candidate.CandidateError, "ambiguous exact artifact carrier"):
            candidate.build_source_population_closure(capture)

    def test_same_prefix_carrier_from_different_workflow_fails_closed(self) -> None:
        capture = self.base_capture()
        capture["runs"][0]["attempts"][0]["workflow_id"] = 88
        with self.assertRaisesRegex(candidate.CandidateError, "workflow id does not match capture workflow"):
            candidate.build_source_population_closure(capture)

    def test_successful_unavailable_artifact_is_preserved_as_unavailable_source_input(self) -> None:
        capture = self.base_capture()
        capture["runs"][0]["artifacts"] = []
        with tempfile.TemporaryDirectory() as temporary:
            inputs = candidate.source_inputs_from_capture(capture, Path(temporary))
        self.assertEqual(len(inputs), 1)
        self.assertEqual(inputs[0]["conclusion"], "success")
        self.assertEqual(inputs[0]["artifact_name"], "deterministic-publication-intent-100-1")
        self.assertIsNone(inputs[0]["publication_intent_bytes"])
        self.assertIsNone(inputs[0]["snapshot_bytes"])

    def test_later_failed_attempt_does_not_erase_earlier_successful_attempt_input(self) -> None:
        capture = copy.deepcopy(self.fixture["higher_attempt_capture"])
        with tempfile.TemporaryDirectory() as temporary:
            inputs = candidate.source_inputs_from_capture(capture, Path(temporary))
        self.assertEqual([(row["run_attempt"], row["conclusion"]) for row in inputs], [(1, "success"), (2, "failure")])

    def test_second_pass_higher_attempt_and_new_run_both_change_closure(self) -> None:
        base = candidate.canonical_json_bytes(candidate.build_source_population_closure(self.base_capture()))
        higher = candidate.canonical_json_bytes(
            candidate.build_source_population_closure(copy.deepcopy(self.fixture["higher_attempt_capture"]))
        )
        new_run = candidate.canonical_json_bytes(
            candidate.build_source_population_closure(copy.deepcopy(self.fixture["new_run_capture"]))
        )
        self.assertNotEqual(base, higher)
        self.assertNotEqual(base, new_run)

    def test_verify_closure_rejects_population_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            prepared = Path(temporary) / "source-population-closure.json"
            candidate._write_json(prepared, candidate.build_source_population_closure(self.base_capture()))
            candidate.verify_closure(prepared, self.base_capture())
            with self.assertRaisesRegex(candidate.CandidateError, "closure drifted"):
                candidate.verify_closure(prepared, copy.deepcopy(self.fixture["higher_attempt_capture"]))

    def test_recovery_capture_preserves_exact_empty_set_and_exact_utf8_body_identity(self) -> None:
        self.assertEqual(candidate.decode_recovery_capture([]), [])
        prepared = candidate.decode_recovery_capture(copy.deepcopy(self.fixture["prepared_recovery"]))
        changed = candidate.decode_recovery_capture(copy.deepcopy(self.fixture["changed_recovery"]))
        self.assertEqual(prepared[0]["issue_number"], 523)
        self.assertEqual(prepared[0]["author_login"], "8ft0-ai")
        self.assertNotEqual(prepared[0]["body_bytes"], changed[0]["body_bytes"])

    def test_final_recovery_check_rejects_edit_during_pr_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            recovery = candidate.decode_recovery_capture(copy.deepcopy(self.fixture["prepared_recovery"]))
            candidate._serialise_recoveries(recovery, root)
            candidate._write_json(
                root / "raw-inputs/recovery-comments.json",
                [
                    {
                        "issue_number": 523,
                        "comment_id": recovery[0]["comment_id"],
                        "author_login": recovery[0]["author_login"],
                        "body_path": f"raw-inputs/recovery-comments/{recovery[0]['comment_id']}.txt",
                        "body_sha256": candidate.sha256_bytes(recovery[0]["body_bytes"]),
                    }
                ],
            )
            candidate.compare_recovery_capture(root, copy.deepcopy(self.fixture["prepared_recovery"]))
            with self.assertRaisesRegex(candidate.CandidateError, "recovery carrier identity/body drifted"):
                candidate.compare_recovery_capture(root, copy.deepcopy(self.fixture["changed_recovery"]))

    def test_bundle_is_self_contained_hash_protected_and_replayable(self) -> None:
        capture = self.base_capture()
        intent = b'{"fixture":"intent"}\n'
        snapshot = b'{"fixture":"snapshot"}\n'
        added_path = "data/crypto/hourly/2026/08/27/1200_AEST_source_snapshot.json"
        manifest = {
            "contract": "trusted-main-source-evidence-accumulation/v1.1",
            "repository": candidate.EXPECTED_REPOSITORY,
            "base_sha": "b" * 40,
            "base_tree_sha": "c" * 40,
            "anchor_observation_hour_utc": "2026-08-27T00:00:00Z",
            "window": {"start_utc": "2026-08-27T01:00:00Z", "end_utc": "2026-08-28T01:00:00Z", "hours": 25},
            "hours": [],
            "verified_source_inputs": [],
            "supersession_records": [],
            "operational_diagnostics": [],
            "input_level_blockers": [],
            "hour_level_blockers": [],
            "applied_recovery_decisions": [],
            "blocking_findings": [],
            "added_paths": [
                {
                    "path": added_path,
                    "sha256": hashlib.sha256(snapshot).hexdigest(),
                    "git_blob_sha": candidate.accumulation.git_blob_sha(snapshot),
                    "canonical_observation_hour_utc": "2026-08-27T01:00:00Z",
                    "source_run_id": 100,
                    "source_run_attempt": 1,
                }
            ],
            "candidate_id": "d" * 64,
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            artifact_root = root / "artifacts"
            source_dir = artifact_root / "100/1"
            (source_dir / "payload").mkdir(parents=True)
            (source_dir / "deterministic-publication-intent.json").write_bytes(intent)
            (source_dir / "payload/snapshot.json").write_bytes(snapshot)
            bundle = root / "bundle"
            with mock.patch.object(candidate.accumulation, "build_accumulation_manifest", return_value=manifest):
                evidence = candidate.prepare_bundle(
                    Path("."),
                    "b" * 40,
                    capture,
                    artifact_root,
                    [],
                    bundle,
                    55,
                    3,
                )
                self.assertEqual(evidence["status"], "candidate")
                candidate.verify_bundle(bundle)
                replayed = candidate.replay_bundle(Path("."), "b" * 40, bundle)
                self.assertEqual(replayed["candidate_id"], "d" * 64)
            self.assertEqual((bundle / added_path).read_bytes(), snapshot)
            (bundle / "candidate-evidence.json").write_text("tampered\n", encoding="utf-8")
            with self.assertRaisesRegex(candidate.CandidateError, "SHA-256 table mismatch"):
                candidate.verify_bundle(bundle)

    def test_candidate_scope_is_additions_only_exact_manifest_and_source_scoped(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Test"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.com"], check=True)
            (root / "README.md").write_text("base\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "README.md"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-qm", "base"], check=True)
            base = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
            path = "data/crypto/hourly/2026/08/27/1200_AEST_source_snapshot.json"
            raw = b"source\n"
            target = root / path
            target.parent.mkdir(parents=True)
            target.write_bytes(raw)
            subprocess.run(["git", "-C", str(root), "add", path], check=True)
            manifest = {
                "added_paths": [
                    {
                        "path": path,
                        "sha256": hashlib.sha256(raw).hexdigest(),
                        "git_blob_sha": candidate.accumulation.git_blob_sha(raw),
                    }
                ]
            }
            candidate.verify_worktree(root, base, manifest)
            (root / "unexpected.txt").write_text("x\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "unexpected.txt"], check=True)
            with self.assertRaisesRegex(candidate.CandidateError, "outside trusted source scope|not in manifest"):
                candidate.verify_worktree(root, base, manifest)

    def test_exact_git_object_proof_fails_closed_without_complete_identity_proof(self) -> None:
        intent = json.dumps(
            {
                "snapshot_commit_sha": "a" * 40,
                "snapshot_path": "data/crypto/hourly/x_source_snapshot.json",
            },
            sort_keys=True,
        ).encode("utf-8")
        snapshot = b"snapshot\n"
        source = {
            "repository": candidate.EXPECTED_REPOSITORY,
            "workflow_path": candidate.EXPECTED_WORKFLOW_PATH,
            "workflow_id": 111,
            "event": "schedule",
            "conclusion": "success",
            "run_id": 100,
            "run_attempt": 1,
            "workflow_head_sha": "a" * 40,
            "artifact_name": "deterministic-publication-intent-100-1",
            "publication_intent_bytes": intent,
            "snapshot_bytes": snapshot,
        }
        unavailable = candidate._apply_git_object_proof([source], [])
        self.assertIsNone(unavailable[0]["publication_intent_bytes"])
        self.assertIsNone(unavailable[0]["snapshot_bytes"])

        reference = candidate.publication_intent_git_reference(intent)
        complete = candidate._apply_git_object_proof(
            [source],
            [{
                "run_id": 100,
                "run_attempt": 1,
                **reference,
                "snapshot_sha256": hashlib.sha256(snapshot).hexdigest(),
                "fetch_succeeded": True,
                "commit_present": True,
                "path_present": True,
                "bytes_match": True,
            }],
        )
        self.assertEqual(complete[0]["publication_intent_bytes"], intent)
        self.assertEqual(complete[0]["snapshot_bytes"], snapshot)

    def test_malformed_retained_intent_produces_replayable_blocked_bundle(self) -> None:
        capture = self.base_capture()
        malformed_intent = b'{"snapshot_commit_sha":'
        snapshot = b'{"fixture":"snapshot"}\n'
        reference = candidate.publication_intent_git_reference(malformed_intent)
        self.assertFalse(reference["intent_parse_succeeded"])
        self.assertFalse(reference["intent_reference_valid"])
        proof = [{
            "run_id": 100,
            "run_attempt": 1,
            **reference,
            "snapshot_sha256": hashlib.sha256(snapshot).hexdigest(),
            "fetch_succeeded": False,
            "commit_present": False,
            "path_present": False,
            "bytes_match": False,
        }]
        blocker = {
            "blocker_class": "source-input-unverifiable",
            "blocker_fingerprint": "e" * 64,
        }
        manifest = {
            "contract": "trusted-main-source-evidence-accumulation/v1.1",
            "repository": candidate.EXPECTED_REPOSITORY,
            "base_sha": "b" * 40,
            "base_tree_sha": "c" * 40,
            "anchor_observation_hour_utc": "2026-08-27T00:00:00Z",
            "window": {"start_utc": "2026-08-27T01:00:00Z", "end_utc": "2026-08-28T01:00:00Z", "hours": 25},
            "hours": [],
            "verified_source_inputs": [],
            "supersession_records": [],
            "operational_diagnostics": [],
            "input_level_blockers": [blocker],
            "hour_level_blockers": [],
            "applied_recovery_decisions": [],
            "blocking_findings": [blocker],
            "added_paths": [],
            "candidate_id": "d" * 64,
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            artifact_root = root / "artifacts"
            source_dir = artifact_root / "100/1"
            (source_dir / "payload").mkdir(parents=True)
            (source_dir / "deterministic-publication-intent.json").write_bytes(malformed_intent)
            (source_dir / "payload/snapshot.json").write_bytes(snapshot)
            bundle = root / "bundle"
            with mock.patch.object(candidate.accumulation, "build_accumulation_manifest", return_value=manifest):
                evidence = candidate.prepare_bundle(
                    Path("."), "b" * 40, capture, artifact_root, [], bundle, 55, 3, proof
                )
                self.assertEqual(evidence["status"], "blocked")
                self.assertEqual(
                    (bundle / "raw-inputs/sources/100/1/deterministic-publication-intent.json").read_bytes(),
                    malformed_intent,
                )
                replayed = candidate.replay_bundle(Path("."), "b" * 40, bundle)
                self.assertEqual(replayed["candidate_id"], "d" * 64)

    def test_pr_body_contains_complete_source_only_evidence_contract(self) -> None:
        manifest = {
            "base_sha": "a" * 40,
            "base_tree_sha": "b" * 40,
            "candidate_id": "c" * 64,
            "anchor_observation_hour_utc": "2026-08-27T00:00:00Z",
            "window": {"start_utc": "2026-08-27T01:00:00Z", "end_utc": "2026-08-28T01:00:00Z"},
            "hours": [
                {"canonical_observation_hour_utc": "2026-08-27T01:00:00Z", "disposition": "eligible"}
            ],
            "added_paths": [
                {"path": "data/crypto/hourly/x_source_snapshot.json", "sha256": "d" * 64, "git_blob_sha": "e" * 40}
            ],
            "applied_recovery_decisions": [],
            "blocking_findings": [],
        }
        evidence = {
            "workflow_run_id": 123,
            "workflow_run_attempt": 2,
            "prepared_artifact_name": "trusted-main-source-evidence-candidate-123-2",
            "expected_main_sha": "a" * 40,
            "source_population_closure_sha256": "f" * 64,
        }
        body = candidate.render_pr_body(manifest, evidence, "9" * 40)
        for expected in (
            "Part of #523",
            "not public evidence authority",
            "Ordered hour dispositions",
            "Git blob",
            "Remaining blockers",
            "Deterministic replay",
            "No model or report generation",
            "No automatic merge",
            "protected `main` remains the sole public evidence authority",
        ):
            self.assertIn(expected, body)

    def test_final_pr_identity_requires_exact_base_head_and_run_body_pairing(self) -> None:
        body = " ".join(("c" * 64, "9" * 40, "123", "2", "a" * 40))
        snapshot = {
            "base": {"ref": "main", "sha": "a" * 40},
            "head": {"ref": candidate.EXPECTED_BRANCH, "sha": "9" * 40},
            "body": body,
        }
        candidate.verify_pr_snapshot(snapshot, "a" * 40, "9" * 40, "c" * 64, 123, 2)
        drifted = copy.deepcopy(snapshot)
        drifted["base"]["sha"] = "b" * 40
        with self.assertRaisesRegex(candidate.CandidateError, "base identity mismatch"):
            candidate.verify_pr_snapshot(drifted, "a" * 40, "9" * 40, "c" * 64, 123, 2)

    def test_fixture_declares_all_closed_race_regressions(self) -> None:
        self.assertIn("higher_attempt_capture", self.fixture)
        self.assertIn("new_run_capture", self.fixture)
        self.assertIn("changed_recovery", self.fixture)


if __name__ == "__main__":
    unittest.main()
