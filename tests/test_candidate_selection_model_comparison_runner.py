from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from llm_analysis.candidate_selection_model_comparison_runner import (
    metered_fail_closed_route_probe,
)
from llm_analysis.generation_config import GenerationConfig, ProviderPolicy


def runtime() -> GenerationConfig:
    return GenerationConfig(
        provider="openrouter",
        endpoint="https://openrouter.ai/api/v1/chat/completions",
        model="openai/gpt-5.6-sol",
        prompt_path="prompts/crypto-market-candidate-selection-v1.txt",
        analysis_schema_path="schemas/crypto-market-candidate-selection-v1.json",
        prompt_version="crypto-market-candidate-selection/v1",
        analysis_schema_version="crypto-market-candidate-selection/v1",
        evidence_schema_version="crypto-market-evidence-bundle/v1",
        temperature=0.0,
        max_output_tokens=512,
        timeout_seconds=30.0,
        retry_limit=0,
        retry_backoff_seconds=0.0,
        max_request_bytes=5_000_000,
        max_cost_usd=0.12,
        structured_output=True,
        cross_model_fallback=False,
        router_metadata=True,
        app_referer="https://github.com/8ft0-ai/crypto-pulse",
        app_title="CryptoPulse",
        provider_policy=ProviderPolicy(
            require_parameters=True,
            data_collection="deny",
            zdr=False,
            allow_fallbacks=False,
            order=(),
            only=("OpenAI",),
            ignore=(),
            sort=None,
            max_prompt_price_per_million=6.0,
            max_completion_price_per_million=36.0,
            max_request_price=0.12,
        ),
    )


class CandidateSelectionComparisonRunnerTests(unittest.TestCase):
    def test_successful_probe_preserves_reported_cost_and_writes_evidence(self) -> None:
        reported = {
            "requested_model": "openai/gpt-5.6-sol",
            "actual_model": "openai/gpt-5.6-sol",
            "actual_provider": "OpenAI",
            "generation_id": "generation-1",
            "estimated_cost_usd": 0.001,
        }
        with tempfile.TemporaryDirectory() as temporary:
            with patch.dict(
                os.environ,
                {"CRYPTOPULSE_SELECTOR_EVIDENCE_DIR": temporary},
            ), patch(
                "llm_analysis.candidate_selection_model_comparison_runner.projected_paid_route_probe",
                return_value=reported,
            ):
                result = metered_fail_closed_route_probe(runtime(), "secret")
            evidence = (
                Path(temporary)
                / "route-probes/openai__gpt-5.6-sol.json"
            )
            self.assertTrue(evidence.is_file())
            retained = json.loads(evidence.read_text(encoding="utf-8"))
        self.assertEqual(result["estimated_cost_usd"], 0.001)
        self.assertEqual(result["actual_provider"], "OpenAI")
        self.assertEqual(result["metering_status"], "reported")
        self.assertEqual(retained, result)

    def test_failed_probe_reserves_full_cap_and_writes_sanitised_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with patch.dict(
                os.environ,
                {"CRYPTOPULSE_SELECTOR_EVIDENCE_DIR": temporary},
            ), patch(
                "llm_analysis.candidate_selection_model_comparison_runner.projected_paid_route_probe",
                side_effect=RuntimeError("route failed with secret"),
            ):
                result = metered_fail_closed_route_probe(runtime(), "secret")
            evidence = (
                Path(temporary)
                / "route-probes/openai__gpt-5.6-sol.json"
            )
            retained = json.loads(evidence.read_text(encoding="utf-8"))
        self.assertEqual(result["estimated_cost_usd"], 0.12)
        self.assertEqual(result["metering_status"], "reserved-maximum")
        self.assertEqual(result["probe_status"], "failed")
        self.assertIsNone(result["actual_provider"])
        self.assertNotIn("secret", result["message"])
        self.assertIn("[REDACTED]", result["message"])
        self.assertEqual(retained, result)


if __name__ == "__main__":
    unittest.main()
