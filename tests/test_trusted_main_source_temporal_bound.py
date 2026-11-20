from __future__ import annotations

import json
import sys
import unittest
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import trusted_main_source_evidence_accumulation as legacy  # noqa: E402
import trusted_main_source_temporal_bound as temporal  # noqa: E402


def source() -> dict:
    head = "a" * 40
    return {
        "event": "schedule",
        "conclusion": "success",
        "workflow_path": temporal.SOURCE_WORKFLOW,
        "workflow_id": 309042287,
        "workflow_head_sha": head,
        "run_id": 12345,
        "run_attempt": 1,
        "temporal_job_proof": {
            "total_count": 1,
            "jobs": [{
                "id": 888,
                "run_id": 12345,
                "run_attempt": 1,
                "head_sha": head,
                "name": temporal.INGEST_JOB_NAME,
                "status": "completed",
                "conclusion": "success",
                "started_at": "2026-10-15T09:57:09Z",
                "completed_at": "2026-10-15T09:57:22Z",
                "steps": [
                    {
                        "name": "Fetch source data",
                        "status": "completed",
                        "conclusion": "success",
                        "started_at": "2026-10-15T09:57:14Z",
                        "completed_at": "2026-10-15T09:57:15Z",
                    },
                    {
                        "name": "Validate observation hour",
                        "status": "completed",
                        "conclusion": "success",
                        "started_at": "2026-10-15T09:57:15Z",
                        "completed_at": "2026-10-15T09:57:15Z",
                    },
                ],
            }],
        },
    }


def supported_git_blob(repository_root, command, object_expression):
    if command != "rev-parse":
        raise AssertionError("unexpected Git operation")
    return temporal.SUPPORTED_BLOBS[object_expression.split(":", 1)[1]]


class TemporalBoundTests(unittest.TestCase):
    def prove(self, candidate: dict) -> dict:
        with mock.patch.object(legacy, "_git_text", side_effect=supported_git_blob):
            return temporal.prove_bound(Path("."), candidate)

    def test_exact_completed_job_and_approved_source_blobs(self):
        proof = self.prove(source())
        self.assertEqual(proof["job_id"], 888)
        self.assertEqual(
            proof["latest_admissible_observation_hour_utc"],
            "2026-10-16T09:00:00Z",
        )
        self.assertEqual(proof["max_post_completion_skew_hours"], 24)
        self.assertNotIn("canonical_observation_hour_utc", proof)
        self.assertEqual(
            set(proof["source_provenance_blobs"]), set(temporal.SUPPORTED_BLOBS)
        )

    def test_ambiguous_missing_mismatched_or_incomplete_jobs_fail_closed(self):
        cases = [
            lambda x: x.pop("temporal_job_proof"),
            lambda x: x["temporal_job_proof"].update(total_count=2),
            lambda x: x["temporal_job_proof"].update(jobs=[]),
            lambda x: x["temporal_job_proof"]["jobs"][0].update(run_id=54321),
            lambda x: x["temporal_job_proof"]["jobs"][0].update(run_attempt=2),
            lambda x: x["temporal_job_proof"]["jobs"][0].update(head_sha="b" * 40),
            lambda x: x["temporal_job_proof"]["jobs"][0].update(name="Other job"),
            lambda x: x["temporal_job_proof"]["jobs"][0].update(conclusion="failure"),
            lambda x: x["temporal_job_proof"]["jobs"][0].update(completed_at=None),
            lambda x: x["temporal_job_proof"]["jobs"][0].update(completed_at="2026-10-15T09:57:00Z"),
            lambda x: x["temporal_job_proof"]["jobs"][0]["steps"].pop(),
            lambda x: x["temporal_job_proof"]["jobs"][0]["steps"][0].update(conclusion="failure"),
            lambda x: x["temporal_job_proof"]["jobs"][0]["steps"].append(
                deepcopy(x["temporal_job_proof"]["jobs"][0]["steps"][0])
            ),
            lambda x: x.update(workflow_head_sha="b" * 40),
            lambda x: x.update(event="workflow_dispatch"),
        ]
        for mutate in cases:
            candidate = source()
            mutate(candidate)
            with self.subTest(mutation=str(mutate)), self.assertRaises(ValueError):
                self.prove(candidate)

    def test_later_approved_scheduled_workflow_blob(self):
        def later_blob(root, command, expression):
            path = expression.split(":", 1)[1]
            if path == temporal.SOURCE_WORKFLOW:
                return "b23c2854e01073ed9022305e4b881ac4e1dc2613"
            return temporal.SUPPORTED_BLOBS[path]

        with mock.patch.object(legacy, "_git_text", side_effect=later_blob):
            bound = temporal.prove_bound(Path("."), source())
        self.assertEqual(
            bound["source_provenance_blobs"][temporal.SOURCE_WORKFLOW],
            "b23c2854e01073ed9022305e4b881ac4e1dc2613",
        )

    def test_unsupported_producer_blob_is_ineligible_for_historical_rule(self):
        with mock.patch.object(legacy, "_git_text", return_value="f" * 40):
            with self.assertRaisesRegex(ValueError, "unsupported historical temporal provenance"):
                temporal.prove_bound(Path("."), source())

    def test_exact_snapshot_timestamp_admissibility_boundary(self):
        candidate = source()
        proof = self.prove(candidate)
        completed = datetime.fromisoformat(
            proof["job_completed_at_utc"].replace("Z", "+00:00")
        )
        for offset, accepted in (
            (timedelta(hours=23), True),
            (timedelta(hours=24), True),
            (timedelta(hours=24, seconds=1), False),
        ):
            timestamp = (completed + offset).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
            candidate["snapshot_bytes"] = json.dumps({
                "run": {"generated_at_utc": timestamp}
            }).encode("utf-8")
            if accepted:
                temporal.verify_exact_snapshot_timestamp(candidate, proof)
            else:
                with self.assertRaisesRegex(ValueError, "admissibility ceiling"):
                    temporal.verify_exact_snapshot_timestamp(candidate, proof)

    def test_job_timestamp_drift_changes_candidate_bound_and_digest(self):
        a = source()
        b = source()
        b["temporal_job_proof"]["jobs"][0]["completed_at"] = "2026-10-15T09:57:23Z"
        x = self.prove(a)
        y = self.prove(b)
        self.assertNotEqual(x["job_proof_sha256"], y["job_proof_sha256"])
        self.assertNotEqual(x["job_completed_at_utc"], y["job_completed_at_utc"])


if __name__ == "__main__":
    unittest.main()
