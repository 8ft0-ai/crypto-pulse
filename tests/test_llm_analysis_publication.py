from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from llm_analysis.contracts import canonical_json_bytes, content_sha256
from llm_analysis.publication import (
    PublicationError,
    prepare_publication,
    publication_paths,
    validate_changed_files,
)


class Report:
    is_valid = True

    @staticmethod
    def as_dict():
        return {"valid": True, "diagnostics": []}


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.artifacts = self.root / "artifacts"
        self.artifacts.mkdir()
        self.snapshot_rel = "data/crypto/hourly/2026/07/08/1742_AEST_source_snapshot.json"
        snapshot = b'{"snapshot":true}\n'
        path = self.root / self.snapshot_rel
        path.parent.mkdir(parents=True)
        path.write_bytes(snapshot)
        snapshot_sha = hashlib.sha256(snapshot).hexdigest()
        self.bundle = {
            "bundle_id": "sha256:" + "1" * 64,
            "schema_version": "crypto-market-evidence-bundle/v1",
            "source_snapshot": {
                "path": self.snapshot_rel,
                "sha256": snapshot_sha,
                "schema_version": "0.2",
                "quality_status": "valid-ok",
                "generated_at_utc": "2026-07-08T07:42:09Z",
            },
            "product_boundaries": ["Not financial advice."],
            "evidence": [],
        }
        self.analysis = {
            "schema_version": "crypto-market-analysis/v1",
            "headline": {
                "text": "Market evidence remains mixed",
                "claim_type": "data_quality_limitation",
                "confidence": "high",
                "evidence_ids": [],
            },
        }
        self.analysis_bytes = canonical_json_bytes(self.analysis) + b"\n"
        self.preview = b"# Market evidence remains mixed\n"
        raw = b'{"schema_version":"crypto-market-analysis/v1"}'
        provenance = {
            "schema_version": "crypto-market-generation-provenance/v1",
            "provider": "openrouter",
            "requested_model": "provider/model:free",
            "actual_model": "provider/model",
            "actual_provider": "Provider",
            "prompt_version": "crypto-market-analysis/v1",
            "analysis_schema_version": "crypto-market-analysis/v1",
            "evidence_schema_version": "crypto-market-evidence-bundle/v1",
            "source_snapshot": {"path": self.snapshot_rel, "sha256": snapshot_sha},
            "evidence_bundle": {
                "bundle_id": self.bundle["bundle_id"],
                "sha256": content_sha256(self.bundle),
            },
            "generated_at": "2026-07-11T00:00:00Z",
            "generation_parameters": {"temperature": 0.2, "max_output_tokens": 4000},
            "usage": {"input_tokens": 10, "output_tokens": 20, "total_tokens": 30},
            "generation_id": "gen-1",
            "prompt_sha256": "2" * 64,
            "completion_sha256": hashlib.sha256(raw).hexdigest(),
            "routing": {
                "provider_fallback_used": False,
                "cross_model_fallback_used": False,
                "provider_preferences": [],
            },
            "estimated_cost_usd": 0.0,
        }
        files = {
            "run-status.json": {
                "status": "accepted",
                "failure_code": None,
                "publishable_output": True,
            },
            "evidence-bundle.json": self.bundle,
            "accepted-analysis.json": self.analysis,
            "generation-metadata.json": {
                "metadata": {},
                "provenance": provenance,
                "request_summary": {"model": "provider/model:free"},
            },
            "validation-report.json": {"valid": True, "diagnostics": []},
        }
        for name, value in files.items():
            (self.artifacts / name).write_bytes(canonical_json_bytes(value) + b"\n")
        (self.artifacts / "provider-completion.raw.json").write_bytes(raw + b"\n")
        (self.artifacts / "rendered-preview.md").write_bytes(self.preview)
        self.config = SimpleNamespace(analysis_schema_path="schema.json")
        self.pipeline = SimpleNamespace(
            report=Report(), normalised_analysis=self.analysis_bytes, markdown=self.preview
        )

    def tearDown(self):
        self.temp.cleanup()

    def _prepare(self):
        with (
            patch("llm_analysis.publication.load_generation_config", return_value=self.config),
            patch("llm_analysis.publication.load_json", return_value={}),
            patch("llm_analysis.publication.process_analysis", return_value=self.pipeline),
        ):
            return prepare_publication(
                repository_root=self.root,
                snapshot_path=self.snapshot_rel,
                artifact_dir=self.artifacts,
                trusted_main_sha="abc123",
                workflow_run_url="https://github.com/example/actions/runs/1",
            )

    def test_paths_are_rolling_report_source_paths(self):
        paths = publication_paths(self.snapshot_rel)
        self.assertEqual(
            paths.analysis,
            "analysis/crypto/hourly/2026/07/08/governed/1742_AEST_analysis.json",
        )
        self.assertTrue(
            paths.report.endswith("/governed/1742_AEST_crypto_market_intelligence.md")
        )

    def test_accepted_artifacts_create_analysis_provenance_and_deterministic_report(self):
        result = self._prepare()
        for path in result.changed_files:
            self.assertTrue((self.root / path).is_file())
        report = (self.root / result.paths.report).read_text()
        self.assertIn('schema_version: "governed-crypto-report/v1"', report)
        self.assertIn("# Market evidence remains mixed", report)
        provenance = json.loads((self.root / result.paths.provenance).read_text())
        self.assertEqual(provenance["source_snapshot"]["path"], self.snapshot_rel)
        self.assertEqual(provenance["analysis"]["sha256"], result.analysis_sha256)
        self.assertFalse(result.manifest["raw_provider_output_committed"])
        self.assertNotIn("provider-completion.raw.json", result.changed_files)
        self.assertIn("Actual provider", result.pr_body)
        self.assertIn("Static-site build: `passed`", result.pr_body)

    def test_rejected_status_cannot_publish(self):
        (self.artifacts / "run-status.json").write_text(
            '{"status":"rejected","publishable_output":false}'
        )
        with self.assertRaises(PublicationError):
            self._prepare()

    def test_completion_hash_must_match_raw_artifact(self):
        (self.artifacts / "provider-completion.raw.json").write_text("tampered\n")
        with self.assertRaises(PublicationError):
            self._prepare()

    def test_changed_file_scope_is_exact_and_rejects_site_output(self):
        expected = ("analysis/a.json", "analysis/a.provenance.json", "reports/a.md")
        validate_changed_files(list(expected), expected)
        with self.assertRaises(PublicationError):
            validate_changed_files([*expected, "_site/index.html"], expected)

    def test_snapshot_path_rejects_traversal(self):
        with self.assertRaises(PublicationError):
            publication_paths("../snapshot.json")


if __name__ == "__main__":
    unittest.main()
