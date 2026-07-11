from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from llm_analysis.dry_run import (
    ACTIONS_SUMMARY_FILE,
    EVIDENCE_BUNDLE_FILE,
    GENERATION_METADATA_FILE,
    MARKDOWN_PREVIEW_FILE,
    NORMALISED_ANALYSIS_FILE,
    RAW_COMPLETION_FILE,
    RUN_STATUS_FILE,
    VALIDATION_REPORT_FILE,
    execute_dry_run,
)
from llm_analysis.evidence_bundle import EvidenceBundleBuild, EvidenceBundleError, build_evidence_bundle
from llm_analysis.openrouter_client import MissingSecretError


class FakeReport:
    def __init__(self, valid: bool):
        self.is_valid = valid

    def as_dict(self):
        return {
            "valid": self.is_valid,
            "diagnostics": []
            if self.is_valid
            else [
                {
                    "stage": "policy",
                    "code": "advice_language",
                    "path": "$.headline",
                    "message": "rejected",
                }
            ],
        }


class GovernedDryRunTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "prompt.md").write_text(
            "prompt {{EVIDENCE_BUNDLE_JSON}}", encoding="utf-8"
        )
        self.output = self.root / "out"
        self.bundle = {
            "bundle_id": "sha256:" + "1" * 64,
            "schema_version": "crypto-market-evidence-bundle/v1",
            "source_snapshot": {
                "path": "data/crypto/hourly/2026/07/08/example_source_snapshot.json",
                "sha256": "2" * 64,
                "schema_version": "0.2",
                "quality_status": "valid-ok",
                "generated_at_utc": "2026-07-08T07:42:09Z",
            },
            "product_boundaries": ["Not financial advice."],
            "evidence": [],
        }
        self.build = EvidenceBundleBuild(
            self.bundle,
            self.bundle["source_snapshot"]["path"],
            self.bundle["source_snapshot"]["sha256"],
            "valid-ok",
        )
        self.config = SimpleNamespace(
            prompt_path="prompt.md",
            analysis_schema_path="analysis-schema.json",
            prompt_version="crypto-market-analysis/v1",
            analysis_schema_version="crypto-market-analysis/v1",
            evidence_schema_version="crypto-market-evidence-bundle/v1",
            model="provider/model:free",
        )
        self.metadata = SimpleNamespace(
            requested_model="provider/model:free",
            actual_model="provider/model",
            actual_provider="Provider",
            generation_id="gen-1",
            input_tokens=10,
            output_tokens=20,
            total_tokens=30,
            estimated_cost_usd=0.0,
            latency_ms=5,
            provider_fallback_used=False,
            cross_model_fallback_used=False,
            provider_preferences=(),
            router_attempt=1,
            finish_reason="stop",
        )
        self.generation = SimpleNamespace(
            analysis={"schema_version": "crypto-market-analysis/v1"},
            raw_completion='{"schema_version":"crypto-market-analysis/v1"}',
            metadata=self.metadata,
            provenance={
                "schema_version": "crypto-market-generation-provenance/v1"
            },
            request_summary={"model": "provider/model:free"},
        )

    def tearDown(self):
        self.temp.cleanup()

    def _run(self, *, valid=True, client_error=None):
        outer = self

        class Client:
            def generate(self, **kwargs):
                if client_error:
                    raise client_error
                return outer.generation

        pipeline = SimpleNamespace(
            report=FakeReport(valid),
            normalised_analysis=b'{"accepted":true}\n' if valid else None,
            markdown=b"# Accepted\n" if valid else None,
        )
        with (
            patch("llm_analysis.dry_run.load_json", return_value={}),
            patch("llm_analysis.dry_run.validate_schema", return_value=[]),
            patch(
                "llm_analysis.dry_run.load_generation_config",
                return_value=self.config,
            ),
            patch("llm_analysis.dry_run.process_analysis", return_value=pipeline),
        ):
            return execute_dry_run(
                repository_root=self.root,
                snapshot_path=self.build.snapshot_path,
                output_dir=self.output,
                api_key="secret-value",
                trusted_main_sha="abc123",
                client_factory=lambda config: Client(),
                bundle_builder=lambda *args, **kwargs: self.build,
            )

    def test_success_writes_all_review_artefacts(self):
        outcome = self._run(valid=True)
        self.assertEqual(outcome.exit_code, 0)
        for name in (
            EVIDENCE_BUNDLE_FILE,
            RAW_COMPLETION_FILE,
            NORMALISED_ANALYSIS_FILE,
            MARKDOWN_PREVIEW_FILE,
            VALIDATION_REPORT_FILE,
            GENERATION_METADATA_FILE,
            RUN_STATUS_FILE,
            ACTIONS_SUMMARY_FILE,
        ):
            self.assertTrue((self.output / name).is_file(), name)
        status = json.loads((self.output / RUN_STATUS_FILE).read_text())
        self.assertTrue(status["publishable_output"])
        summary = (self.output / ACTIONS_SUMMARY_FILE).read_text()
        self.assertIn("abc123", summary)
        self.assertIn("No branch, commit, issue, pull request", summary)
        retained = "".join(
            path.read_text(errors="ignore") for path in self.output.iterdir()
        )
        self.assertNotIn("secret-value", retained)

    def test_rejected_analysis_retains_diagnostics_but_no_publishable_output(self):
        outcome = self._run(valid=False)
        self.assertEqual(outcome.exit_code, 2)
        self.assertFalse((self.output / NORMALISED_ANALYSIS_FILE).exists())
        self.assertFalse((self.output / MARKDOWN_PREVIEW_FILE).exists())
        self.assertTrue((self.output / RAW_COMPLETION_FILE).is_file())
        status = json.loads((self.output / RUN_STATUS_FILE).read_text())
        self.assertFalse(status["publishable_output"])

    def test_missing_secret_failure_is_diagnostic_and_fail_closed(self):
        outcome = self._run(
            client_error=MissingSecretError("OPENROUTER_API_KEY is required")
        )
        self.assertEqual(outcome.exit_code, 2)
        report = json.loads((self.output / VALIDATION_REPORT_FILE).read_text())
        self.assertEqual(report["diagnostics"][0]["code"], "missing_secret")
        self.assertFalse((self.output / RAW_COMPLETION_FILE).exists())
        self.assertFalse((self.output / MARKDOWN_PREVIEW_FILE).exists())

    def test_prepared_bundle_must_match_rebuilt_trusted_bundle(self):
        prepared = self.root / "prepared.json"
        prepared.write_text('{"different":true}', encoding="utf-8")
        with (
            patch("llm_analysis.dry_run.load_json", return_value={}),
            patch(
                "llm_analysis.dry_run.load_generation_config",
                return_value=self.config,
            ),
        ):
            outcome = execute_dry_run(
                repository_root=self.root,
                snapshot_path=self.build.snapshot_path,
                output_dir=self.output,
                prepared_bundle_path=prepared,
                api_key="secret",
                bundle_builder=lambda *args, **kwargs: self.build,
            )
        self.assertEqual(outcome.exit_code, 2)
        self.assertFalse((self.output / RAW_COMPLETION_FILE).exists())


class EvidenceBundleBuilderTests(unittest.TestCase):
    def test_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(EvidenceBundleError):
                build_evidence_bundle(
                    "../snapshot.json",
                    repository_root=temp,
                    validator=lambda path, config: {"status": "valid-ok"},
                    config_loader=lambda path: {},
                )

    def test_projection_is_deterministic_and_binds_raw_snapshot(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            relative = (
                "data/crypto/hourly/2026/07/08/example_source_snapshot.json"
            )
            path = root / relative
            path.parent.mkdir(parents=True)
            snapshot = {
                "schema_version": "0.2",
                "run": {"generated_at_utc": "2026-07-08T07:42:09Z"},
                "quality": {"status": "valid-ok"},
                "sources": {
                    "coingecko": {
                        "status": "ok",
                        "fetched_at_utc": "2026-07-08T07:42:09Z",
                    }
                },
                "market": {
                    "assets": [
                        {
                            "id": "bitcoin",
                            "symbol": "BTC",
                            "name": "Bitcoin",
                            "price_usd": 62739,
                            "change_24h_pct": -0.5,
                            "last_updated": "2026-07-08T07:41:15Z",
                        }
                    ]
                },
                "exchange_crosscheck": {"selected": None, "sources": {}},
                "defi": {"total_tvl_usd": 100, "stablecoins": []},
            }
            path.write_text(json.dumps(snapshot, sort_keys=True), encoding="utf-8")
            kwargs = dict(
                repository_root=root,
                validator=lambda selected, config: {"status": "valid-ok"},
                config_loader=lambda config_path: {},
            )
            first = build_evidence_bundle(relative, **kwargs)
            second = build_evidence_bundle(relative, **kwargs)
            self.assertEqual(first.bundle, second.bundle)
            self.assertRegex(first.bundle["bundle_id"], r"^sha256:[0-9a-f]{64}$")
            self.assertEqual(first.snapshot_path, relative)
            self.assertTrue(
                any(
                    item["evidence_id"] == "market.asset.bitcoin.price_usd"
                    for item in first.bundle["evidence"]
                )
            )


if __name__ == "__main__":
    unittest.main()
