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
from crypto_ingestion_slot import canonical_hour, receipt_name
import trusted_hourly_source as hourly
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
                }], "total_count": 1},
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
                "pull_requests": [{
                    "number": self.pr,
                    "head": {"sha": self.head, "ref": self.branch, "repo": {"id": 1}},
                    "base": {"ref": "main", "repo": {"id": 1}},
                }],
            },
            f"{REPO}/commits/{self.head}/pulls?per_page=100": [{
                "number": self.pr,
                "head": {"sha": self.head, "ref": self.branch, "repo": {"id": 1}},
                "base": {"ref": "main", "repo": {"id": 1}},
            }],
            f"{REPO}/actions/runs/{self.ci_id}/jobs?per_page=100": {"jobs": [{
                "name": "Build site and check generated output",
                "run_id": self.ci_id,
                "status": "completed", "conclusion": "success",
                "head_sha": self.head,
            }], "total_count": 1},
            f"{REPO}/commits/{self.merge}": {
                "sha": self.merge, "parents": [{"sha": self.base}, {"sha": self.head}],
            },
            f"{REPO}/compare/{self.merge}...{self.main}":
                self.ancestry(self.merge, "ahead"),
        }
        self.raw = {
            f"{REPO}/actions/artifacts/{self.artifact_id}/zip": self.zip,
            f"{REPO}/contents/{self.path}?ref={self.merge}": self.snapshot,
            f"{REPO}/contents/{self.path}?ref={self.main}": self.snapshot,
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
        endpoint = f"{REPO}/actions/runs/{self.run_id}/artifacts?per_page=100"
        data[endpoint]["artifacts"] = []
        data[endpoint]["total_count"] = 0
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
        data[endpoint]["total_count"] = 2
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

    def test_artifact_listing_requires_complete_pagination(self):
        endpoint = f"{REPO}/actions/runs/{self.run_id}/artifacts?per_page=100"
        page2 = endpoint + "&page=2"
        data = copy.deepcopy(self.json)
        data[endpoint]["total_count"] = 101
        filler = [{"id": i + 2000, "name": f"unrelated-{i}"} for i in range(99)]
        data[endpoint]["artifacts"].extend(filler)
        data[page2] = {"total_count": 101, "artifacts": [
            {**data[endpoint]["artifacts"][0], "id": 7890},
        ]}
        with self.assertRaisesRegex(proof.PromotionProofError, "ambiguous"):
            self.run_proof(json_data=data)  # duplicate outside page one is detected
        data[page2]["artifacts"] = []
        with self.assertRaisesRegex(proof.PromotionProofError, "incomplete"):
            self.run_proof(json_data=data)
        data = copy.deepcopy(self.json)
        data[endpoint]["total_count"] = 2
        with self.assertRaisesRegex(proof.PromotionProofError, "incomplete"):
            self.run_proof(json_data=data)

    def test_ci_jobs_require_complete_pagination(self):
        endpoint = f"{REPO}/actions/runs/{self.ci_id}/jobs?per_page=100"
        page2 = endpoint + "&page=2"
        data = copy.deepcopy(self.json)
        required = data[endpoint]["jobs"].pop()
        data[endpoint]["jobs"] = [
            {"name": f"unrelated-{i}", "status": "completed", "conclusion": "success"}
            for i in range(100)
        ]
        data[endpoint]["total_count"] = 101
        data[page2] = {"total_count": 101, "jobs": [required]}
        self.assertTrue(self.run_proof(json_data=data)["verified"])
        data[page2]["jobs"] = []
        with self.assertRaisesRegex(proof.PromotionProofError, "incomplete"):
            self.run_proof(json_data=data)
        data = copy.deepcopy(self.json)
        data[endpoint]["total_count"] = 2
        with self.assertRaisesRegex(proof.PromotionProofError, "incomplete"):
            self.run_proof(json_data=data)

    def test_ci_must_link_unique_exact_promotion_pr(self):
        endpoint = f"{REPO}/actions/runs/{self.ci_id}"
        for description, change in (
            ("other PR", lambda a: a.update(number=999)),
            ("other repository", lambda a: a["base"]["repo"].update(id=999)),
            ("other branch", lambda a: a["base"].update(ref="other")),
        ):
            with self.subTest(description=description):
                data = copy.deepcopy(self.json)
                change(data[endpoint]["pull_requests"][0])
                with self.assertRaisesRegex(proof.PromotionProofError, "different PR"):
                    self.run_proof(json_data=data)
        data = copy.deepcopy(self.json)
        data[endpoint]["pull_requests"].append(
            copy.deepcopy(data[endpoint]["pull_requests"][0]))
        with self.assertRaisesRegex(proof.PromotionProofError, "unique"):
            self.run_proof(json_data=data)

    def test_merged_pr_empty_ci_links_require_unique_commit_association(self):
        endpoint = f"{REPO}/actions/runs/{self.ci_id}"
        association = f"{REPO}/commits/{self.head}/pulls?per_page=100"
        data = copy.deepcopy(self.json)
        data[endpoint]["pull_requests"] = []  # GitHub clears after some merges
        self.assertTrue(self.run_proof(json_data=data)["verified"])
        data[association].append(copy.deepcopy(data[association][0]))
        with self.assertRaisesRegex(proof.PromotionProofError, "unique"):
            self.run_proof(json_data=data)
        data[association] = []
        with self.assertRaisesRegex(proof.PromotionProofError, "unique"):
            self.run_proof(json_data=data)
        data[endpoint].pop("pull_requests")
        with self.assertRaisesRegex(proof.PromotionProofError, "missing"):
            self.run_proof(json_data=data)

    def test_modified_bytes_at_pinned_main_fail_closed(self):
        raw = dict(self.raw)
        raw[f"{REPO}/contents/{self.path}?ref={self.main}"] = b"changed after promotion"
        with self.assertRaisesRegex(proof.PromotionProofError, "pinned protected-main"):
            self.run_proof(raw_data=raw)

    def test_scheduled_accepted_hour_receipt_verifies_with_real_receipt_checks(self):
        data = copy.deepcopy(self.json)
        run = data[f"{REPO}/actions/runs/{self.run_id}"]
        run.update(event="schedule", head_branch="main", path=hourly.INGEST_WORKFLOW)
        generated = "2026-11-26T00:07:10Z"
        intent = {
            "automatic_eligible": True, "refusal_reasons": [],
            "snapshot_path": self.path, "snapshot_commit_sha": self.original,
            "observation_hour_utc": self.hour, "generated_at_utc": generated,
        }
        receipt = {
            "contract_version": "crypto-hour-ingestion/v1",
            "status": "accepted-on-artifact-upload", "run_id": self.run_id,
            "run_attempt": 1, "source_event": "schedule",
            "quality_status": "valid-ok",
            "source_intent_artifact": f"deterministic-publication-intent-{self.run_id}-1",
            "accepted_hour_artifact": receipt_name(canonical_hour(self.hour)),
            "snapshot_sha256": self.digest, "snapshot_commit_sha": self.original,
            "intended_hour_utc": self.hour, "generated_at_utc": generated,
        }
        def gh_json(endpoint):
            return copy.deepcopy(data[endpoint])
        def gh_bytes(endpoint, accept=None):
            return self.raw[endpoint]
        def real_receipt(intent_value, receipt_value, run_value, snapshot_value, file_value, config_value):
            return hourly.verify_bundle(
                intent_value, receipt_value, run_value, snapshot_value,
                file_value, config_value)
        with (patch.object(proof, "verify_bundle", side_effect=real_receipt),
             patch.object(hourly, "verify_publication_intent"),
             patch.object(hourly, "load_config", return_value={}),
             patch.object(hourly, "classify_snapshot_quality", return_value={}),
             patch.object(hourly, "quality_reasons", return_value=[]),
             patch.object(hourly, "validate_observation_hour", return_value={
                 "observation_hour_utc": self.hour,
                 "generated_at_utc": generated, "quality_status": "valid-ok",
             }),
             patch.object(Path, "read_bytes", return_value=self.snapshot)):
            result = proof.verify_source_only_promotion(
                self.run_id, 1, json.dumps(intent).encode(), self.snapshot,
                json.dumps(receipt).encode(), Path("/tmp/source.json"), ROOT,
                self.main, "cryptopulse-deterministic-pub", gh_json, gh_bytes)
            self.assertTrue(result["verified"])
            self.assertEqual(result["source_event"], "schedule")
            receipt["dispatch_correlation_id"] = "cp-2026112600"
            with self.assertRaisesRegex(proof.PromotionProofError, "receipt"):
                proof.verify_source_only_promotion(
                    self.run_id, 1, json.dumps(intent).encode(), self.snapshot,
                    json.dumps(receipt).encode(), Path("/tmp/source.json"), ROOT,
                    self.main, "cryptopulse-deterministic-pub", gh_json, gh_bytes)

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
