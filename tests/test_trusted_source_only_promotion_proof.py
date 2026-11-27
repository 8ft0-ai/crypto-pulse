"""Stage 4C GitHub lineage regression tests — bounded synthetic evidence only."""
from __future__ import annotations

import copy
import hashlib
import io
import json
import sys
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import trusted_main_source_only_promotion_proof as proof
import trusted_main_source_evidence_candidate as candidate

REPO = "/repos/8ft0-ai/crypto-pulse"


class Stage4CLineageTests(unittest.TestCase):
    def setUp(self):
        self.run_id = 45726388495
        self.intent = b'{"test":"immutable intent"}'
        self.snapshot = b'{"fixture":"realistic original bytes"}\n'
        self.receipt = b'{"test":"accepted receipt"}'
        self.digest = hashlib.sha256(self.snapshot).hexdigest()
        self.hour = "2026-11-26T00:00:00Z"
        self.path = "data/crypto/hourly/2026/11/26/1107_AEDT_source_snapshot.json"
        self.source_sha = "a" * 40
        self.base = "b" * 40
        self.head = "c" * 40
        self.merge = "d" * 40
        self.main = "e" * 40
        self.original = "f" * 40
        self.branch = f"automation/source-only-{self.run_id}-1"
        self.artifact_id = 1234
        self.pr = 798
        self.ci_id = 5678
        self.check_suite = 9101
        promotion = {
            "status": "merged", "source_run_id": str(self.run_id),
            "source_path": self.path, "snapshot_sha256": self.digest,
            "pull_request_number": str(self.pr),
            "independent_ci_run_id": str(self.ci_id),
            "expected_main_base_sha": self.base,
            "candidate_head_sha": self.head, "merge_commit_sha": self.merge,
        }
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w") as bundle:
            bundle.writestr("source-promotion-proof.json", json.dumps(promotion))
        self.zip = output.getvalue()
        self.json = {
            f"{REPO}/actions/runs/{self.run_id}/artifacts?per_page=100":
                {"artifacts": [{
                    "id": self.artifact_id, "name": f"cryptopulse-source-only-promotion-{self.run_id}-1",
                    "expired": False, "workflow_run": {"id": self.run_id, "head_sha": self.source_sha},
                }]},
            f"{REPO}/actions/runs/{self.run_id}": {
                "id": self.run_id, "run_attempt": 1,
                "workflow_id": 309042287, "status": "completed", "conclusion": "success",
                "repository": {"full_name": "8ft0-ai/crypto-pulse"},
                "head_sha": self.source_sha, "event": "workflow_dispatch",
            },
            f"{REPO}/compare/{self.source_sha}...{self.base}":
                self.ancestry(self.source_sha, "ahead"),
            f"{REPO}/pulls/{self.pr}": {
                "number": self.pr, "state": "closed", "merged": True,
                "merged_at": "2026-11-26T00:12:55Z", "merge_commit_sha": self.merge,
                "user": {"login": "cryptopulse-deterministic-pub[bot]"},
                "merged_by": {"login": "cryptopulse-deterministic-pub[bot]"},
                "head": {"sha": self.head, "ref": self.branch, "repo": {"id": 1}},
                "base": {"sha": self.base, "ref": "main",
                         "repo": {"id": 1, "full_name": "8ft0-ai/crypto-pulse"}},
                "body": (
                    f"Immutable ingestion run: {self.run_id}, attempt 1.\n"
                    f"Exact source path: `{self.path}`.\n"
                    f"Snapshot SHA-256: `{self.digest}`.\n"
                    f"Expected protected-main base: `{self.base}`."
                ),
            },
            f"{REPO}/pulls/{self.pr}/files?per_page=100":
                [{"filename": self.path, "status": "added", "deletions": 0}],
            f"{REPO}/actions/runs/{self.ci_id}": {
                "id": self.ci_id, "name": "Validate CryptoPulse PR",
                "path": ".github/workflows/pr-validation.yml",
                "event": "pull_request", "head_sha": self.head,
                "head_branch": self.branch, "status": "completed",
                "conclusion": "success", "check_suite_id": self.check_suite,
                "repository": {"full_name": "8ft0-ai/crypto-pulse"},
            },
            f"{REPO}/actions/runs/{self.ci_id}/jobs?per_page=100": {"jobs": [{
                "name": "Build site and check generated output",
                "run_id": self.ci_id,
                "status": "completed", "conclusion": "success",
                "head_sha": self.head,
            }]},
            f"{REPO}/commits/{self.merge}": {
                "sha": self.merge, "parents": [{"sha": self.base}, {"sha": self.head}],
            },
            f"{REPO}/compare/{self.merge}...{self.main}":
                self.ancestry(self.merge, "ahead"),
        }
        self.raw = {
            f"{REPO}/actions/artifacts/{self.artifact_id}/zip": self.zip,
            f"{REPO}/contents/{self.path}?ref={self.merge}": self.snapshot,
        }

    @staticmethod
    def ancestry(base, status):
        return {"status": status, "base_commit": {"sha": base},
                "merge_base_commit": {"sha": base}}

    def run_proof(self, json_data=None, raw_data=None, receipt=True):
        data = self.json if json_data is None else json_data
        raw = self.raw if raw_data is None else raw_data
        def gh_json(endpoint):
            return copy.deepcopy(data[endpoint])
        def gh_bytes(endpoint, accept=None):
            return raw[endpoint]
        with patch.object(proof, "verify_bundle", return_value={
            "source_path": self.path, "snapshot_sha256": self.digest,
            "source_hour": self.hour, "intent_snapshot_commit_sha": self.original,
        }):
            return proof.verify_source_only_promotion(
                self.run_id, 1, self.intent, self.snapshot,
                self.receipt if receipt else None,
                Path("/tmp/source.json"), ROOT, self.main,
                "cryptopulse-deterministic-pub", gh_json, gh_bytes,
            )

    def test_complete_lineage_verifies_without_original_git_commit(self):
        result = self.run_proof()
        self.assertTrue(result["verified"])
        self.assertEqual(result["original_snapshot_commit_sha"], self.original)
        self.assertEqual(result["promotion_pr_number"], self.pr)

    def test_no_promotion_artifact_uses_legacy_fallback(self):
        data = copy.deepcopy(self.json)
        data[f"{REPO}/actions/runs/{self.run_id}/artifacts?per_page=100"]["artifacts"] = []
        self.assertIsNone(self.run_proof(json_data=data))

    def test_missing_or_conflicting_proof_fails_closed(self):
        variants = [
            ("missing PR", f"{REPO}/pulls/{self.pr}", "merged", False),
            ("failed CI", f"{REPO}/actions/runs/{self.ci_id}", "conclusion", "failure"),
            ("wrong CI job", f"{REPO}/actions/runs/{self.ci_id}/jobs?per_page=100", "jobs", []),
            ("untrusted PR author", f"{REPO}/pulls/{self.pr}", "user", {"login": "other[bot]"}),
            ("untrusted PR merger", f"{REPO}/pulls/{self.pr}", "merged_by", {"login": "other"}),
            ("wrong PR path", f"{REPO}/pulls/{self.pr}/files?per_page=100",
             None, [{"filename": "data/crypto/hourly/wrong.json", "status": "added", "deletions": 0}]),
            ("missing merge proof", f"{REPO}/commits/{self.merge}", "parents", []),
            ("wrong main ancestry", f"{REPO}/compare/{self.merge}...{self.main}", "status", "diverged"),
            ("wrong source ancestry", f"{REPO}/compare/{self.source_sha}...{self.base}", "status", "diverged"),
            ("wrong PR head", f"{REPO}/pulls/{self.pr}", "head",
             {"sha": "0" * 40, "ref": self.branch, "repo": {"id": 1}}),
            ("wrong PR base", f"{REPO}/pulls/{self.pr}", "base",
             {"sha": "0" * 40, "ref": "main", "repo": {"id": 1, "full_name": "8ft0-ai/crypto-pulse"}}),
        ]
        for label, endpoint, field, value in variants:
            with self.subTest(label=label):
                data = copy.deepcopy(self.json)
                if field is None:
                    data[endpoint] = value
                else:
                    data[endpoint][field] = value
                with self.assertRaises(proof.PromotionProofError):
                    self.run_proof(json_data=data)

    def test_mismatched_promoted_bytes_fail_closed(self):
        raw = dict(self.raw)
        raw[f"{REPO}/contents/{self.path}?ref={self.merge}"] = b"tampered"
        with self.assertRaisesRegex(proof.PromotionProofError, "JSON"):
            self.run_proof(raw_data=raw)

    def test_missing_receipt_and_duplicate_artifact_fail_closed(self):
        with self.assertRaisesRegex(proof.PromotionProofError, "accepted-hour"):
            self.run_proof(receipt=False)
        data = copy.deepcopy(self.json)
        endpoint = f"{REPO}/actions/runs/{self.run_id}/artifacts?per_page=100"
        data[endpoint]["artifacts"].append(dict(data[endpoint]["artifacts"][0]))
        with self.assertRaisesRegex(proof.PromotionProofError, "ambiguous"):
            self.run_proof(json_data=data)

    def test_conflicting_promotion_payload_fails_closed(self):
        raw = dict(self.raw)
        bogus = {"status": "merged", "source_run_id": "wrong"}
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w") as bundle:
            bundle.writestr("source-promotion-proof.json", json.dumps(bogus))
        raw[f"{REPO}/actions/artifacts/{self.artifact_id}/zip"] = output.getvalue()
        with self.assertRaisesRegex(proof.PromotionProofError, "promotion claim"):
            self.run_proof(raw_data=raw)

    def test_candidate_replay_accepts_exact_bound_stage4c_and_rejects_tampering(self):
        """Prepared replay must work without original ingestion Git object."""
        generated = "2026-11-26T00:07:10Z"
        intent_obj = {
            "snapshot_commit_sha": self.original, "snapshot_path": self.path,
            "snapshot_sha256": self.digest, "observation_hour_utc": self.hour,
            "generated_at_utc": generated, "source_workflow_id": 309042287,
            "source_workflow_run_id": self.run_id, "source_workflow_run_attempt": 1,
            "source_workflow_head_sha": self.source_sha,
            "source_workflow_path": candidate.EXPECTED_WORKFLOW_PATH,
            "automatic_eligible": True, "refusal_reasons": [],
        }
        intent = json.dumps(intent_obj, sort_keys=True).encode()
        carrier_name = "crypto-hour-accepted-20261126T00"
        receipt_obj = {
            "contract_version": "crypto-hour-ingestion/v1",
            "status": "accepted-on-artifact-upload",
            "run_id": self.run_id, "run_attempt": 1,
            "source_event": "workflow_dispatch", "quality_status": "valid-ok",
            "source_intent_artifact": f"deterministic-publication-intent-{self.run_id}-1",
            "accepted_hour_artifact": carrier_name,
            "snapshot_sha256": self.digest, "snapshot_commit_sha": self.original,
            "intended_hour_utc": self.hour, "generated_at_utc": generated,
            "dispatch_correlation_id": "cp-2026112600",
        }
        receipt = json.dumps(receipt_obj, sort_keys=True).encode()
        source = {
            "repository": candidate.EXPECTED_REPOSITORY,
            "workflow_path": candidate.EXPECTED_WORKFLOW_PATH,
            "workflow_id": 309042287, "event": "workflow_dispatch",
            "conclusion": "success", "run_id": self.run_id,
            "run_attempt": 1, "workflow_head_sha": self.source_sha,
            "artifact_name": receipt_obj["source_intent_artifact"],
            "publication_intent_bytes": intent, "snapshot_bytes": self.snapshot,
            "accepted_hour_receipt_bytes": receipt,
            "accepted_hour_artifact": {
                "name": carrier_name, "id": 234, "expired": False,
                "workflow_run": {"id": self.run_id, "head_sha": self.source_sha},
            },
        }
        lineage = {
            "contract": proof.CONTRACT, "run_id": self.run_id,
            "run_attempt": 1, "source_workflow_id": 309042287,
            "source_workflow_head_sha": self.source_sha,
            "source_event": "workflow_dispatch",
            "publication_intent_sha256": hashlib.sha256(intent).hexdigest(),
            "accepted_hour_receipt_sha256": hashlib.sha256(receipt).hexdigest(),
            "snapshot_sha256": self.digest, "source_path": self.path,
            "source_hour": self.hour, "original_snapshot_commit_sha": self.original,
            "promotion_artifact_id": 1234, "promotion_artifact_sha256": "8" * 64,
            "promotion_pr_number": self.pr, "candidate_head_sha": self.head,
            "expected_main_base_sha": self.base,
            "merge_commit_sha": self.merge,
            "independent_ci_run_id": self.ci_id,
            "protected_main_sha": self.main, "verified": True,
        }
        reference = candidate.publication_intent_git_reference(intent)
        wrapped = {
            "run_id": self.run_id, "run_attempt": 1,
            **reference, "snapshot_sha256": self.digest,
            **{key: False for key in (
                "fetch_succeeded", "commit_present", "path_present", "bytes_match")},
            "source_only_promotion": lineage,
        }
        effective = candidate._apply_git_object_proof([source], [wrapped], self.main)
        self.assertEqual(effective[0]["snapshot_bytes"], self.snapshot)
        self.assertEqual(effective[0]["publication_intent_bytes"], intent)
        modified = copy.deepcopy(wrapped)
        modified["source_only_promotion"]["source_path"] = "data/crypto/hourly/wrong.json"
        with self.assertRaises(candidate.CandidateError):
            candidate._apply_git_object_proof([source], [modified], self.main)
        with self.assertRaises(candidate.CandidateError):
            candidate._apply_git_object_proof([source], [wrapped], "0" * 40)
        modified = copy.deepcopy(wrapped)
        modified["source_only_promotion"]["verified"] = False
        with self.assertRaises(candidate.CandidateError):
            candidate._apply_git_object_proof([source], [modified], self.main)

    def test_workflow_rechecks_live_lineage_and_receipts_for_both_events(self):
        import yaml
        workflow = yaml.safe_load((ROOT / ".github/workflows/build-trusted-main-source-evidence-candidate.yml").read_text())
        prep = "\n".join(x.get("run", "") for x in workflow["jobs"]["prepare"]["steps"])
        publish = "\n".join(x.get("run", "") for x in workflow["jobs"]["publish"]["steps"])
        self.assertIn("verify_source_only_promotion(", prep)
        self.assertIn("verify_source_only_promotion(", publish)
        self.assertIn("promotion != prepared", publish)
        self.assertIn('accepted = attempt.get("accepted_hour_artifact")', prep)
        self.assertNotIn('if attempt["event"] == "workflow_dispatch":\n                          accepted =', prep)
        self.assertIn('fetch --no-tags origin "$commit_sha"', publish)
        self.assertNotIn("gh pr merge", prep + publish)


if __name__ == "__main__":
    unittest.main()
