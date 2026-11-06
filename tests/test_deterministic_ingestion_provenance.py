"""Regression contract: only receipt-backed, exact-hour dispatch may publish."""
from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts" / "deterministic_ingestion_provenance.py"
SPEC = importlib.util.spec_from_file_location("deterministic_ingestion_provenance", MODULE)
assert SPEC and SPEC.loader
provenance = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = provenance
SPEC.loader.exec_module(provenance)


class DeterministicIngestionProvenanceTests(unittest.TestCase):
    def setUp(self):
        fixture = json.loads((ROOT / "tests/fixtures/deterministic_site_publication_v3.json").read_text())
        self.attestation = fixture["attestation"]
        self.run = {
            "id": self.attestation["source_workflow_run_id"],
            "run_attempt": 1,
            "workflow_id": self.attestation["source_workflow_id"],
            "path": provenance.SOURCE_WORKFLOW_PATH,
            "head_sha": self.attestation["source_workflow_head_sha"],
            "head_branch": "main",
            "status": "completed",
            "conclusion": "success",
            "event": "workflow_dispatch",
            "actor": {"login": "8ft0-ai"},
            "repository": {"full_name": "8ft0-ai/crypto-pulse"},
            "created_at": "2026-08-17T00:07:03Z",
        }
        self.receipt = {
            "contract_version": "crypto-hour-ingestion/v1",
            "status": "accepted-on-artifact-upload",
            "source_event": "workflow_dispatch",
            "dispatch_correlation_id": "cp-2026081700",
            "intended_hour_utc": "2026-08-17T00:00:00Z",
            "run_id": self.run["id"],
            "run_attempt": 1,
            "quality_status": "valid-ok",
            "accepted_hour_artifact": "crypto-hour-accepted-20260817T00",
            "snapshot_sha256": self.attestation["snapshot_sha256"],
            "snapshot_commit_sha": self.attestation["snapshot_commit_sha"],
            "source_intent_artifact": "deterministic-publication-intent-54321-1",
            "rolling_pr_outcome": "failure",
            "receipt_prepared_at_utc": "2026-08-17T00:07:20Z",
        }

    def verify(self, run=None, evidence=None, receipt="default", repository="8ft0-ai/crypto-pulse"):
        return provenance.verify_source(
            self.run if run is None else run,
            self.attestation if evidence is None else evidence,
            receipt=self.receipt if receipt == "default" else receipt,
            repository=repository,
        )

    def test_positive_dispatch_is_bound_to_run_and_snapshot(self):
        self.assertEqual("workflow_dispatch", self.verify())
        intent = dict(self.attestation, source_workflow_path=provenance.SOURCE_WORKFLOW_PATH)
        self.assertEqual("workflow_dispatch", self.verify(evidence=intent))
        self.assertEqual(
            "crypto-hour-accepted-20260817T00",
            provenance.receipt_name(provenance.canonical_hour("2026-08-17T00:00:00Z")),
        )

    def test_existing_successful_schedule_remains_valid_without_receipt(self):
        run = dict(self.run, event="schedule")
        self.assertEqual("schedule", self.verify(run=run, receipt=None))

    def test_dispatch_without_receipt_fails_closed(self):
        with self.assertRaisesRegex(provenance.ProvenanceError, "missing accepted-hour"):
            self.verify(receipt=None)

    def test_each_bound_receipt_field_is_immutable(self):
        invalid = {
            "contract_version": "other",
            "status": "proposed",
            "source_event": "schedule",
            "dispatch_correlation_id": "cp-2026081701",
            "intended_hour_utc": "2026-08-17T01:00:00Z",
            "run_id": 54322,
            "run_attempt": 2,
            "quality_status": "valid-degraded",
            "accepted_hour_artifact": "crypto-hour-accepted-20260817T01",
            "snapshot_sha256": "f" * 64,
            "snapshot_commit_sha": "e" * 40,
            "source_intent_artifact": "deterministic-publication-intent-54322-1",
            "rolling_pr_outcome": "unknown",
        }
        for field, value in invalid.items():
            with self.subTest(field=field):
                receipt = dict(self.receipt, **{field: value})
                with self.assertRaises(provenance.ProvenanceError):
                    self.verify(receipt=receipt)

    def test_invalid_run_identity_origin_and_event_are_rejected(self):
        invalid = {
            "id": 123,
            "run_attempt": 2,
            "workflow_id": 1,
            "path": ".github/workflows/other.yml",
            "head_sha": "e" * 40,
            "head_branch": "feature",
            "status": "queued",
            "conclusion": "failure",
            "event": "push",
            "actor": {"login": "unrelated-collaborator"},
            "repository": {"full_name": "other/repo"},
            "created_at": "2026-08-17T00:05:00Z",
        }
        for field, value in invalid.items():
            with self.subTest(field=field):
                with self.assertRaises(provenance.ProvenanceError):
                    self.verify(run=dict(self.run, **{field: value}))

    def test_out_of_window_replays_and_noncanonical_hours_are_rejected(self):
        for t in ("2026-08-17T00:06:59Z", "2026-08-17T00:30:00Z"):
            with self.subTest(time=t):
                receipt = dict(self.receipt, receipt_prepared_at_utc=t)
                with self.assertRaises(provenance.ProvenanceError):
                    self.verify(receipt=receipt)
        for hour in ("2026-08-17T00:01:00Z", "2026-08-17T00:00:00+00:00", "2026-13-17T00:00:00Z"):
            with self.subTest(hour=hour):
                evidence = dict(self.attestation, observation_hour_utc=hour)
                with self.assertRaises(provenance.ProvenanceError):
                    self.verify(evidence=evidence)

    def test_rejects_tampered_attestation_base_and_workflow(self):
        with self.assertRaisesRegex(provenance.ProvenanceError, "main base"):
            self.verify(evidence=dict(self.attestation, main_base_sha="e" * 40))
        with self.assertRaisesRegex(provenance.ProvenanceError, "source workflow"):
            self.verify(evidence=dict(self.attestation, source_workflow_path="other.yml"))
        with self.assertRaisesRegex(provenance.ProvenanceError, "repository"):
            self.verify(repository="other/repo")

    def test_cli_proves_immutable_fixture_with_no_external_calls(self):
        with tempfile.TemporaryDirectory() as directory:
            temp = Path(directory)
            for key, data in (("run", self.run), ("evidence", self.attestation), ("receipt", self.receipt)):
                (temp / (key + ".json")).write_text(json.dumps(data))
            result = subprocess.run(
                [sys.executable, str(MODULE), "verify",
                 "--source-run", str(temp / "run.json"),
                 "--evidence", str(temp / "evidence.json"),
                 "--receipt", str(temp / "receipt.json"),
                 "--repository", "8ft0-ai/crypto-pulse"],
                capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("SOURCE_PROVENANCE_PASS workflow_dispatch", result.stdout)

    def test_workflows_enforce_receipt_before_generation_and_merge(self):
        gen = (ROOT / ".github/workflows/generate-deterministic-site-publication.yml").read_text()
        gate = (ROOT / ".github/workflows/deterministic-site-publication-gate.yml").read_text()
        self.assertIn("github.event.workflow_run.event == 'workflow_dispatch'", gen)
        self.assertLess(gen.index("Independently verify source run"), gen.index("Generate deterministic Markdown report"))
        self.assertLess(gate.index("Independently verify immutable source-run provenance"),
                        gate.index("Build credential-free gate facts"))
        self.assertIn('gh run download "$SOURCE_RUN_ID"', gen)
        self.assertIn('gh run download "$source_run_id"', gate)
        self.assertIn('--source-receipt-json "$WORK/source-receipt.json"', gate)
        self.assertIn("--source-run-json", gate)
        self.assertIn("--source-repository", gate)
        self.assertLess(gate.index("Build credential-free gate facts"), gate.index("Mint short-lived repository-scoped publication App token"))


if __name__ == "__main__":
    unittest.main()
