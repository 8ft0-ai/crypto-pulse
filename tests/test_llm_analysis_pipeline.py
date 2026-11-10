from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from llm_analysis.pipeline import process_analysis

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "llm_analysis"
SCHEMAS = ROOT / "schemas"


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


class GovernedAnalysisPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.evidence_schema = load_json(SCHEMAS / "crypto-market-evidence-bundle-v1.json")
        cls.analysis_schema = load_json(SCHEMAS / "crypto-market-analysis-v1.json")
        cls.bundle = load_json(FIXTURES / "evidence_bundle_valid.json")
        cls.analysis = load_json(FIXTURES / "analysis_valid.json")
        cls.prompt_injection = load_json(FIXTURES / "prompt_injection_cases.json")
        cls.expected_markdown = (FIXTURES / "analysis_valid_rendered.md").read_bytes()

    def run_pipeline(self, *, analysis=None, bundle=None):
        return process_analysis(
            copy.deepcopy(bundle if bundle is not None else self.bundle),
            copy.deepcopy(analysis if analysis is not None else self.analysis),
            evidence_schema=self.evidence_schema,
            analysis_schema=self.analysis_schema,
        )

    @staticmethod
    def codes(result, stage=None):
        return {
            diagnostic.code
            for diagnostic in result.report.diagnostics
            if stage is None or diagnostic.stage == stage
        }

    def test_valid_fixture_passes_all_stages_and_matches_golden_markdown(self) -> None:
        result = self.run_pipeline()
        self.assertTrue(result.report.is_valid, result.report.diagnostics)
        self.assertEqual(result.report.diagnostics, ())
        self.assertIsNotNone(result.normalised_analysis)
        self.assertEqual(result.markdown, self.expected_markdown)

    def test_identical_inputs_are_byte_stable(self) -> None:
        left = self.run_pipeline()
        right = self.run_pipeline()
        self.assertEqual(left.normalised_analysis, right.normalised_analysis)
        self.assertEqual(left.markdown, right.markdown)

    def test_malformed_json_shapes_fail_closed_without_crashing(self) -> None:
        analysis = copy.deepcopy(self.analysis)
        analysis["headline"]["evidence_ids"] = None
        analysis["market_summary"] = "not-an-array"
        bundle = copy.deepcopy(self.bundle)
        bundle["evidence"] = None
        result = self.run_pipeline(analysis=analysis, bundle=bundle)
        self.assertFalse(result.report.is_valid)
        self.assertIn("type", self.codes(result, "schema"))
        self.assertIsNone(result.normalised_analysis)
        self.assertIsNone(result.markdown)

    def test_schema_rejection_and_prohibited_field_are_separate_diagnostics(self) -> None:
        analysis = copy.deepcopy(self.analysis)
        analysis["headline"]["recommendation"] = "buy"
        result = self.run_pipeline(analysis=analysis)
        self.assertIn("additional_property", self.codes(result, "schema"))
        self.assertIn("prohibited_field", self.codes(result, "policy"))
        self.assertIsNone(result.normalised_analysis)
        self.assertIsNone(result.markdown)

    def test_evidence_schema_rejects_declared_number_with_string_value(self) -> None:
        bundle = copy.deepcopy(self.bundle)
        bundle["evidence"][0]["value"] = "62739"
        result = self.run_pipeline(bundle=bundle)
        self.assertIn("type", self.codes(result, "schema"))
        self.assertIsNone(result.markdown)

    def test_unknown_evidence_id_fails_referential_validation(self) -> None:
        analysis = copy.deepcopy(self.analysis)
        analysis["market_summary"][0]["evidence_ids"] = ["market.asset.bitcoin.unknown"]
        result = self.run_pipeline(analysis=analysis)
        self.assertIn("unknown_evidence_id", self.codes(result, "referential"))

    def test_duplicate_evidence_id_fails_referential_validation(self) -> None:
        bundle = copy.deepcopy(self.bundle)
        bundle["evidence"].append(copy.deepcopy(bundle["evidence"][0]))
        result = self.run_pipeline(bundle=bundle)
        self.assertIn("duplicate_evidence_id", self.codes(result, "referential"))

    def test_bundle_id_mismatch_fails_referential_validation(self) -> None:
        analysis = copy.deepcopy(self.analysis)
        analysis["evidence_bundle_id"] = "sha256:" + "0" * 64
        result = self.run_pipeline(analysis=analysis)
        self.assertIn("bundle_id_mismatch", self.codes(result, "referential"))

    def test_quoted_value_and_unit_mismatch_fail_value_validation(self) -> None:
        analysis = copy.deepcopy(self.analysis)
        quote = analysis["market_summary"][0]["quoted_values"][0]
        quote["value"] = 10
        quote["unit"] = "percent"
        analysis["market_summary"][0]["text"] = "Bitcoin was recorded at 10%."
        result = self.run_pipeline(analysis=analysis)
        self.assertIn("quoted_value_mismatch", self.codes(result, "value"))
        self.assertIn("unit_mismatch", self.codes(result, "value"))
        self.assertIn("untraceable_number", self.codes(result, "value"))

    def test_wrong_asset_name_fails_value_validation(self) -> None:
        analysis = copy.deepcopy(self.analysis)
        analysis["market_summary"][0]["text"] = "Ethereum was recorded at US$62,739."
        result = self.run_pipeline(analysis=analysis)
        self.assertIn("entity_mismatch", self.codes(result, "value"))

    def test_unknown_named_entity_fails_value_validation(self) -> None:
        analysis = copy.deepcopy(self.analysis)
        analysis["market_summary"][0]["text"] = "Cardano was recorded at US$62,739."
        result = self.run_pipeline(analysis=analysis)
        self.assertIn("untraceable_entity", self.codes(result, "value"))

    def test_wrong_source_name_fails_value_validation(self) -> None:
        analysis = copy.deepcopy(self.analysis)
        analysis["market_summary"][0]["text"] = "DefiLlama recorded Bitcoin at US$62,739."
        result = self.run_pipeline(analysis=analysis)
        self.assertIn("entity_mismatch", self.codes(result, "value"))

    def test_timestamp_mismatch_fails_value_validation(self) -> None:
        analysis = copy.deepcopy(self.analysis)
        analysis["market_summary"][0]["text"] = (
            "Bitcoin was recorded at US$62,739 at 2026-07-09T07:41:15.609Z."
        )
        result = self.run_pipeline(analysis=analysis)
        self.assertIn("timestamp_mismatch", self.codes(result, "value"))

    def test_matching_observation_timestamp_is_accepted(self) -> None:
        analysis = copy.deepcopy(self.analysis)
        analysis["market_summary"][0]["text"] = (
            "Bitcoin was recorded at US$62,739 at 2026-07-08T07:41:15.609Z."
        )
        result = self.run_pipeline(analysis=analysis)
        self.assertTrue(result.report.is_valid, result.report.diagnostics)

    def test_comparison_direction_mismatch_fails_value_validation(self) -> None:
        analysis = copy.deepcopy(self.analysis)
        analysis["headline"]["comparison"]["relation"] = "less_than"
        result = self.run_pipeline(analysis=analysis)
        self.assertIn("comparison_mismatch", self.codes(result, "value"))

    def test_comparison_references_must_be_declared_on_claim(self) -> None:
        analysis = copy.deepcopy(self.analysis)
        analysis["headline"]["evidence_ids"] = ["market.asset.bitcoin.change_24h_pct"]
        result = self.run_pipeline(analysis=analysis)
        self.assertIn("comparison_reference_mismatch", self.codes(result, "value"))

    def test_data_quality_claim_rejects_market_value_support(self) -> None:
        analysis = copy.deepcopy(self.analysis)
        analysis["risks_and_limitations"][0] = {
            "claim_type": "data_quality_limitation",
            "text": "Bitcoin quality was limited.",
            "evidence_ids": ["market.asset.bitcoin.price_usd"],
            "confidence": "low",
        }
        result = self.run_pipeline(analysis=analysis)
        self.assertIn("invalid_data_quality_support", self.codes(result, "semantic"))

    def test_unsupported_claim_type_is_both_schema_and_semantic_failure(self) -> None:
        analysis = copy.deepcopy(self.analysis)
        analysis["headline"]["claim_type"] = "causal_explanation"
        result = self.run_pipeline(analysis=analysis)
        self.assertIn("enum", self.codes(result, "schema"))
        self.assertIn("unsupported_claim_type", self.codes(result, "semantic"))

    def test_policy_categories_fail_closed(self) -> None:
        cases = {
            "causal_language": "Bitcoin fell because demand weakened.",
            "forecast_language": "Bitcoin will rise next week.",
            "advice_language": "Investors should buy Bitcoin.",
            "target_language": "Bitcoin has a price target of US$70,000.",
            "signal_language": "Bitcoin produced a buy signal.",
            "position_guidance": "Reduce the position in Bitcoin.",
            "prompt_override_language": self.prompt_injection["unsafe_analysis_text"],
            "disclaimer_weakening": "This is financial advice.",
        }
        for expected, text in cases.items():
            with self.subTest(expected=expected):
                analysis = copy.deepcopy(self.analysis)
                analysis["headline"] = {
                    "claim_type": "qualitative_interpretation",
                    "text": text,
                    "evidence_ids": [
                        "market.asset.bitcoin.change_24h_pct",
                        "market.asset.ethereum.change_24h_pct",
                    ],
                    "confidence": "low",
                }
                result = self.run_pipeline(analysis=analysis)
                self.assertIn(expected, self.codes(result, "policy"), result.report.diagnostics)
                self.assertIsNone(result.markdown)

    def test_source_failure_explanation_is_not_mistaken_for_market_causality(self) -> None:
        analysis = copy.deepcopy(self.analysis)
        analysis["risks_and_limitations"][0]["text"] = (
            "Binance was skipped because GitHub-hosted runners returned HTTP 451."
        )
        result = self.run_pipeline(analysis=analysis)
        self.assertNotIn("causal_language", self.codes(result, "policy"))
        self.assertTrue(result.report.is_valid, result.report.diagnostics)

    def test_prompt_injection_inside_source_data_cannot_change_contract(self) -> None:
        bundle = copy.deepcopy(self.bundle)
        bundle["evidence"][-1]["value"] = self.prompt_injection["untrusted_source_value"]
        analysis = copy.deepcopy(self.analysis)
        analysis["risks_and_limitations"][0]["text"] = (
            "Binance was skipped; the source reason contained untrusted instruction-like text."
        )
        result = self.run_pipeline(analysis=analysis, bundle=bundle)
        repeat = self.run_pipeline(analysis=analysis, bundle=bundle)
        self.assertTrue(result.report.is_valid, result.report.diagnostics)
        self.assertEqual(result.markdown, repeat.markdown)
        self.assertNotIn(b"Ignore the schema", result.markdown)
        self.assertTrue(result.markdown.startswith(b"<!-- Deterministically rendered"))

    def test_renderer_collapses_model_controlled_newlines(self) -> None:
        analysis = copy.deepcopy(self.analysis)
        analysis["market_summary"][0]["text"] = "Bitcoin was recorded\n# injected heading\nat US$62,739."
        result = self.run_pipeline(analysis=analysis)
        self.assertTrue(result.report.is_valid, result.report.diagnostics)
        self.assertNotIn(b"\n# injected heading", result.markdown)
        self.assertIn(b"Bitcoin was recorded \\# injected heading at US$62,739.", result.markdown)

    def test_invalid_cli_run_removes_stale_outputs(self) -> None:
        analysis = copy.deepcopy(self.analysis)
        analysis["headline"]["recommendation"] = "buy"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle_path = root / "bundle.json"
            analysis_path = root / "analysis.json"
            markdown_path = root / "report.md"
            normalised_path = root / "analysis.normalised.json"
            bundle_path.write_text(json.dumps(self.bundle), encoding="utf-8")
            analysis_path.write_text(json.dumps(analysis), encoding="utf-8")
            markdown_path.write_text("stale", encoding="utf-8")
            normalised_path.write_text("stale", encoding="utf-8")
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "llm_analysis",
                    str(bundle_path),
                    str(analysis_path),
                    "--schemas-dir",
                    str(SCHEMAS),
                    "--markdown-output",
                    str(markdown_path),
                    "--normalised-output",
                    str(normalised_path),
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 2, completed.stdout + completed.stderr)
            self.assertFalse(markdown_path.exists())
            self.assertFalse(normalised_path.exists())

    def test_pipeline_has_no_secret_or_network_dependency(self) -> None:
        previous = os.environ.pop("OPENROUTER_API_KEY", None)
        try:
            result = self.run_pipeline()
            self.assertTrue(result.report.is_valid, result.report.diagnostics)
        finally:
            if previous is not None:
                os.environ["OPENROUTER_API_KEY"] = previous


if __name__ == "__main__":
    unittest.main()
