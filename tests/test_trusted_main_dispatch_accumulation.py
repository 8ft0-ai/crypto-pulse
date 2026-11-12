"""Receipt-backed dispatch may enter v1.2 source accumulation; no implicit trust."""
from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import trusted_main_source_evidence_accumulation_v12 as accumulation
import trusted_main_source_evidence_candidate_v12 as candidate

SHA = "a" * 40
HOUR = "2026-11-11T01:00:00Z"
SNAPSHOT = b'{"source":"synthetic test evidence"}\n'


def accepted_source():
    run = {
        "id": 1234, "run_attempt": 1, "workflow_id": 77,
        "path": ".github/workflows/ingest-crypto-sources.yml",
        "head_sha": SHA, "head_branch": "main",
        "status": "completed", "conclusion": "success",
        "event": "workflow_dispatch",
        "actor": {"login": "8ft0-ai"},
        "repository": {"full_name": "8ft0-ai/crypto-pulse"},
        "created_at": "2026-11-11T01:07:03Z",
    }
    intent = {
        "publication_contract": "deterministic-site-publication/v3",
        "source_workflow_path": run["path"],
        "observation_hour_utc": HOUR,
        "source_workflow_run_id": run["id"],
        "source_workflow_run_attempt": 1,
        "source_workflow_id": run["workflow_id"],
        "snapshot_sha256": hashlib.sha256(SNAPSHOT).hexdigest(),
        "main_base_sha": SHA,
        "source_workflow_head_sha": SHA,
        "snapshot_commit_sha": "b" * 40,
    }
    receipt = {
        "contract_version": "crypto-hour-ingestion/v1",
        "status": "accepted-on-artifact-upload",
        "source_event": "workflow_dispatch",
        "dispatch_correlation_id": "cp-2026111101",
        "intended_hour_utc": HOUR,
        "run_id": 1234, "run_attempt": 1, "quality_status": "valid-ok",
        "accepted_hour_artifact": "crypto-hour-accepted-20261111T01",
        "snapshot_sha256": intent["snapshot_sha256"],
        "snapshot_commit_sha": intent["snapshot_commit_sha"],
        "source_intent_artifact": "deterministic-publication-intent-1234-1",
        "rolling_pr_outcome": "success",
        "receipt_prepared_at_utc": "2026-11-11T01:07:20Z",
    }
    return {
        "repository": "8ft0-ai/crypto-pulse",
        "workflow_path": run["path"], "workflow_id": run["workflow_id"],
        "event": "workflow_dispatch", "conclusion": "success",
        "run_id": 1234, "run_attempt": 1, "workflow_head_sha": SHA,
        "artifact_name": "deterministic-publication-intent-1234-1",
        "publication_intent_bytes": json.dumps(intent).encode(),
        "snapshot_bytes": SNAPSHOT,
        "accepted_hour_receipt_bytes": json.dumps(receipt).encode(),
        "dispatch_source_run": run,
        "accepted_hour_artifact": {
            "id": 999, "name": receipt["accepted_hour_artifact"],
            "expired": False,
            "workflow_run": {"id": run["id"], "head_sha": run["head_sha"]},
        },
    }


class ReceiptGateTests(unittest.TestCase):
    def verify(self, source):
        with mock.patch.object(
            accumulation._v11, "_verify_source",
            return_value={"input_identity": {}, "canonical_observation_hour_utc": HOUR},
        ) as verifier:
            result = accumulation._verify_candidate_source(Path("."), SHA, {}, source)
            self.assertEqual(verifier.call_args.args[3]["event"], "schedule")
            self.assertEqual(source["event"], "workflow_dispatch")
            self.assertEqual(result["input_identity"]["event"], "workflow_dispatch")
            self.assertEqual(
                result["accepted_hour_receipt_sha256"],
                hashlib.sha256(source["accepted_hour_receipt_bytes"]).hexdigest(),
            )

    def test_positive_dispatch_preserves_original_provenance(self):
        self.verify(accepted_source())

    def test_missing_receipt_is_not_scheduled_evidence(self):
        source = accepted_source()
        source["accepted_hour_receipt_bytes"] = None
        with self.assertRaises(ValueError):
            accumulation._verify_candidate_source(Path("."), SHA, {}, source)

    def test_mutated_receipt_and_run_metadata_fail_closed(self):
        for field, value in (
            ("status", "proposed"),
            ("snapshot_sha256", "f" * 64),
            ("source_intent_artifact", "deterministic-publication-intent-1-1"),
            ("receipt_prepared_at_utc", "2026-11-11T01:31:00Z"),
        ):
            with self.subTest(field=field):
                source = accepted_source()
                receipt = json.loads(source["accepted_hour_receipt_bytes"])
                receipt[field] = value
                source["accepted_hour_receipt_bytes"] = json.dumps(receipt).encode()
                with self.assertRaises(ValueError):
                    accumulation._verify_candidate_source(Path("."), SHA, {}, source)
        for field, value in (
            ("actor", {"login": "untrusted"}),
            ("head_branch", "feature"),
            ("run_attempt", 2),
            ("created_at", "2026-11-11T01:06:00Z"),
        ):
            with self.subTest(field=field):
                source = accepted_source()
                source["dispatch_source_run"] = {**source["dispatch_source_run"], field: value}
                with self.assertRaises(ValueError):
                    accumulation._verify_candidate_source(Path("."), SHA, {}, source)

    def test_non_object_intent_and_receipt_fail_closed(self):
        for field in ("publication_intent_bytes", "accepted_hour_receipt_bytes"):
            with self.subTest(field=field):
                source = accepted_source()
                source[field] = b"[]"
                with self.assertRaisesRegex(ValueError, "JSON objects"):
                    accumulation._verify_candidate_source(Path("."), SHA, {}, source)

    def test_artifact_mismatch_or_expiry_fails_closed(self):
        for field, value in (("expired", True), ("name", "another-hour"), ("id", 0)):
            with self.subTest(field=field):
                source = accepted_source()
                source["accepted_hour_artifact"][field] = value
                with self.assertRaises(ValueError):
                    accumulation._verify_candidate_source(Path("."), SHA, {}, source)


class CandidateCarrierTests(unittest.TestCase):
    def capture(self):
        f = ROOT / "tests/fixtures/phase17_trusted_main_source_evidence_candidate_v1.json"
        capture = copy.deepcopy(json.loads(f.read_text())["base_capture"])
        raw = capture["runs"][0]
        attempt = raw["attempts"][0]
        attempt.update({
            "event": "workflow_dispatch",
            "path": ".github/workflows/ingest-crypto-sources.yml",
            "actor": {"login": "8ft0-ai"},
            "repository": {"full_name": "8ft0-ai/crypto-pulse"},
        })
        raw["artifacts"].append({
            "id": 9002, "name": "crypto-hour-accepted-20260827T01",
            "expired": False, "workflow_run": {"id": 100, "head_sha": attempt["head_sha"]},
        })
        return capture

    def test_closure_admits_exact_dispatch_and_binds_receipt_carrier(self):
        closure = candidate.build_source_population_closure(self.capture())
        attempt = closure["runs"][0]["attempts"][0]
        self.assertEqual(attempt["event"], "workflow_dispatch")
        self.assertEqual(attempt["accepted_hour_artifact"]["id"], 9002)
        self.assertEqual(
            attempt["accepted_hour_artifact"]["workflow_run"],
            {"id": 100, "head_sha": attempt["head_sha"]},
        )
        self.assertEqual(attempt["dispatch_source_run"]["actor"]["login"], "8ft0-ai")

    def test_duplicate_or_foreign_receipt_artifact_rejected(self):
        capture = self.capture()
        capture["runs"][0]["artifacts"].append(dict(capture["runs"][0]["artifacts"][-1], id=9003))
        with self.assertRaisesRegex(candidate.CandidateError, "ambiguous"):
            candidate.build_source_population_closure(capture)
        capture = self.capture()
        capture["runs"][0]["artifacts"][-1]["workflow_run"]["id"] = 999
        with self.assertRaisesRegex(candidate.CandidateError, "another run"):
            candidate.build_source_population_closure(capture)

    def test_missing_carrier_expiry_rejected(self):
        capture = self.capture()
        del capture["runs"][0]["artifacts"][-1]["expired"]
        with self.assertRaisesRegex(candidate.CandidateError, "explicitly be unexpired"):
            candidate.build_source_population_closure(capture)

    def test_contradictory_carrier_head_sha_rejected(self):
        capture = self.capture()
        capture["runs"][0]["artifacts"][-1]["workflow_run"]["head_sha"] = "f" * 40
        with self.assertRaisesRegex(candidate.CandidateError, "head SHA differs"):
            candidate.build_source_population_closure(capture)

    def test_bundled_receipt_bytes_and_digest_replay(self):
        source = accepted_source()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            row = candidate._serialisable_source_input(source, root)
            candidate._write_json(root / "raw-inputs/source-inputs.json", [row])
            replayed = candidate.source_inputs_from_bundle(root)[0]
            self.assertEqual(replayed["accepted_hour_receipt_bytes"], source["accepted_hour_receipt_bytes"])
            self.assertEqual(replayed["dispatch_source_run"], source["dispatch_source_run"])
            self.assertEqual(
                replayed["accepted_hour_artifact"]["workflow_run"],
                source["accepted_hour_artifact"]["workflow_run"],
            )
            tampered = root / row["accepted_hour_receipt_path"]
            tampered.write_bytes(b"{}")
            with self.assertRaisesRegex(candidate.CandidateError, "hash mismatch"):
                candidate.source_inputs_from_bundle(root)

    def test_workflow_captures_both_events_and_downloads_receipt(self):
        workflow = (ROOT / ".github/workflows/build-trusted-main-source-evidence-candidate.yml").read_text()
        self.assertEqual(workflow.count('for source_event in ("schedule", "workflow_dispatch")'), 2)
        self.assertIn('accepted-hour/receipt.json', workflow)
        self.assertIn('zipped.namelist() != ["receipt.json"]', workflow)
        self.assertNotIn("gh pr merge", workflow)


if __name__ == "__main__":
    unittest.main()
