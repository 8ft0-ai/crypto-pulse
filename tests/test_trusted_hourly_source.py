"""Fail-closed source-only promotion tests; no GitHub mutations or real providers."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from deterministic_site_publication import CONTRACT
from trusted_hourly_source import SourcePromotionError, verify_bundle

HOUR = "2026-11-25T22:00:00Z"
ACTUAL = "2026-11-25T22:07:11Z"
BASE = "a" * 40
SOURCE_COMMIT = "b" * 40
PATH = "data/crypto/hourly/2026/11/26/0907_AEDT_source_snapshot.json"
RUN_ID = 12345
WORKFLOW_ID = 309042287


class TrustedHourlySourceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.snapshot_path = Path(self.tmp.name) / "snapshot.json"
        self.config_path = Path(self.tmp.name) / "config.yml"
        self.config_path.write_text("source: fixture\n")
        self.snapshot = {
            "run": {"observation_hour_utc": HOUR, "generated_at_utc": ACTUAL},
            "warnings": [], "errors": [],
        }
        self.raw = (json.dumps(self.snapshot, sort_keys=True) + "\n").encode()
        self.snapshot_path.write_bytes(self.raw)
        self.intent = {
            "publication_contract": CONTRACT,
            "source_workflow_path": ".github/workflows/ingest-crypto-sources.yml",
            "source_workflow_id": WORKFLOW_ID,
            "source_workflow_run_id": RUN_ID,
            "source_workflow_run_attempt": 1,
            "source_workflow_head_sha": BASE,
            "main_base_sha": BASE,
            "snapshot_commit_sha": SOURCE_COMMIT,
            "snapshot_path": PATH,
            "snapshot_sha256": hashlib.sha256(self.raw).hexdigest(),
            "observation_hour_utc": HOUR,
            "generated_at_utc": ACTUAL,
            "automatic_eligible": True,
            "refusal_reasons": [],
        }
        self.receipt = {
            "contract_version": "crypto-hour-ingestion/v1",
            "status": "accepted-on-artifact-upload",
            "run_id": RUN_ID,
            "run_attempt": 1,
            "source_event": "workflow_dispatch",
            "dispatch_correlation_id": "cp-2026112522",
            "quality_status": "valid-ok",
            "intended_hour_utc": HOUR,
            "accepted_hour_artifact": "crypto-hour-accepted-20261125T22",
            "snapshot_sha256": hashlib.sha256(self.raw).hexdigest(),
            "snapshot_commit_sha": SOURCE_COMMIT,
            "source_intent_artifact": f"deterministic-publication-intent-{RUN_ID}-1",
            "generated_at_utc": ACTUAL,
        }
        self.run = {
            "id": RUN_ID, "run_attempt": 1, "workflow_id": WORKFLOW_ID,
            "path": ".github/workflows/ingest-crypto-sources.yml",
            "head_branch": "main", "head_sha": BASE, "event": "workflow_dispatch",
        }

    def check(self, intent=None, receipt=None, run=None, raw=None):
        with patch("trusted_hourly_source.load_config", return_value={}):
            with patch("trusted_hourly_source.classify_snapshot_quality", return_value={
                "status": "valid-ok", "blocking_issues": [], "non_blocking_warnings": []
            }):
                with patch("trusted_hourly_source.validate_observation_hour", return_value={
                    "quality_status": "valid-ok",
                    "observation_hour_utc": HOUR,
                    "generated_at_utc": ACTUAL,
                }):
                    return verify_bundle(
                        intent if intent is not None else self.intent,
                        receipt if receipt is not None else self.receipt,
                        run if run is not None else self.run,
                        raw if raw is not None else self.raw,
                        self.snapshot_path, self.config_path,
                    )

    def test_wiring_is_opt_in_and_source_only_without_hourly_page_promotion(self):
        import yaml
        ingestion = yaml.safe_load((ROOT / ".github/workflows/ingest-crypto-sources.yml").read_text())
        jobs = ingestion["jobs"]
        assert "source-only-promotion" in jobs
        source = jobs["source-only-promotion"]
        self.assertEqual(source["needs"], "ingest")
        self.assertIn("vars.CRYPTO_SOURCE_PROMOTION_MODE == 'enabled'", source["if"])
        self.assertEqual(source["environment"], "deterministic-publication-control")
        self.assertEqual(source["permissions"]["contents"], "read")
        self.assertIn("accepted_hour_artifact", jobs["ingest"]["outputs"])
        self.assertIn("publication_intent_artifact", jobs["ingest"]["outputs"])
        self.assertIn("vars.CRYPTO_SOURCE_PROMOTION_MODE != 'enabled'", str(jobs["ingest"]["steps"]))
        workflow = yaml.safe_load((ROOT / ".github/workflows/deterministic-site-publication-gate.yml").read_text())
        self.assertEqual(workflow[True]["workflow_run"]["branches-ignore"], ["automation/source-only-*"])
        self.assertEqual(workflow["jobs"]["daily-merge"]["needs"], "daily-preflight")
        self.assertEqual(workflow["jobs"]["merge"]["needs"], "preflight")
        script = (ROOT / "scripts/promote_trusted_hourly_source.sh").read_text()
        self.assertIn("Build site and check generated output", script)
        self.assertIn("SOURCE_ONLY_PROTECTED_MAIN_ACCEPTANCE_PASS", script)
        self.assertIn("count_observation_hour(Path.cwd(), os.environ["SOURCE_HOUR"])", script)
        self.assertIn('[[ "$(git diff --name-only "$current_main" "$candidate_head")" == "$SOURCE_PATH" ]]', script)
        self.assertIn('-f "sha=$candidate_head" -f merge_method=merge', script)
        self.assertNotIn("reports/crypto/hourly/", script)

    def test_valid_accepted_hour(self):
        result = self.check()
        self.assertEqual(result["source_path"], PATH)
        self.assertEqual(result["snapshot_sha256"], hashlib.sha256(self.raw).hexdigest())

    def test_scheduled_ingestion_receipt(self):
        receipt = dict(self.receipt, source_event="schedule", dispatch_correlation_id=None)
        run = dict(self.run, event="schedule")
        self.assertEqual(self.check(receipt=receipt, run=run)["source_hour"], HOUR)

    def test_refuse_wrong_source_run_provenance(self):
        for change in (
            {"head_branch": "evil"}, {"head_sha": "c" * 40},
            {"path": ".github/workflows/rogue.yml"},
            {"id": RUN_ID + 1}, {"run_attempt": 2},
            {"event": "pull_request"}, {"workflow_id": WORKFLOW_ID + 1},
        ):
            with self.subTest(change=change), self.assertRaises(SourcePromotionError):
                self.check(run=dict(self.run, **change))

    def test_refuse_receipt_replay_tamper_and_mismatch(self):
        for change in (
            {"status": "not-accepted"}, {"source_event": "pull_request"},
            {"run_id": RUN_ID + 1}, {"run_attempt": 2},
            {"quality_status": "valid-degraded"},
            {"accepted_hour_artifact": "crypto-hour-accepted-20261125T21"},
            {"intended_hour_utc": "2026-11-25T21:00:00Z"},
            {"snapshot_sha256": "0" * 64},
            {"snapshot_commit_sha": "c" * 40},
            {"source_intent_artifact": "evil"},
            {"dispatch_correlation_id": "cp-2026112521"},
            {"generated_at_utc": "2026-11-25T22:08:11Z"},
        ):
            with self.subTest(change=change), self.assertRaises(SourcePromotionError):
                self.check(receipt=dict(self.receipt, **change))

    def test_refuse_immutable_intent_mutation(self):
        for change in (
            {"automatic_eligible": False}, {"refusal_reasons": ["provider warning"]},
            {"main_base_sha": "c" * 40}, {"source_workflow_run_id": RUN_ID+1},
            {"snapshot_sha256": "0" * 64},
            {"snapshot_path": "data/crypto/hourly/../../bad.json"},
            {"snapshot_commit_sha": "c" * 40},
            {"generated_at_utc": "2026-11-25T22:10:00Z"},
        ):
            with self.subTest(change=change), self.assertRaises(SourcePromotionError):
                self.check(intent=dict(self.intent, **change))

    def test_refuse_changed_source_bytes_even_with_original_receipt(self):
        with self.assertRaises(SourcePromotionError):
            self.check(raw=b"{}\n")

    def test_refuse_snapshot_file_mismatch(self):
        self.snapshot_path.write_bytes(b"tamper")
        with self.assertRaises(SourcePromotionError):
            self.check()

    def test_refuse_source_path_traversal_and_scope_expansion(self):
        for path in (
            "../outside.json", "/etc/passwd", "data/crypto/hourly/../bad_source_snapshot.json",
            "data/crypto/hourly/2026//11/26/0907_AEDT_source_snapshot.json",
            "reports/crypto/hourly/report.md",
        ):
            with self.subTest(path=path), self.assertRaises(SourcePromotionError):
                self.check(intent=dict(self.intent, snapshot_path=path))


if __name__ == "__main__":
    unittest.main()
