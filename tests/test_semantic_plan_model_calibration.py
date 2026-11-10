from __future__ import annotations

import json
import unittest
from pathlib import Path

from llm_analysis.openrouter_client import HttpResponse
from llm_analysis.semantic_plan_model_calibration import (
    RequestTransform,
    _diagnostic,
    _summary_markdown,
    load_calibration_config,
)


class _CaptureTransport:
    def __init__(self) -> None:
        self.body: bytes | None = None

    def post(self, url, *, headers, body, timeout_seconds):
        self.body = body
        return HttpResponse(status=200, body=b"{}", headers={})


class SemanticPlanModelCalibrationTests(unittest.TestCase):
    def test_checked_config_is_three_call_and_half_dollar_bounded(self) -> None:
        base, overrides, smoke_case, total_cap = load_calibration_config(
            Path("."), "config/semantic-plan-model-calibration.yml"
        )

        self.assertEqual(len(base.candidates), 3)
        self.assertEqual(smoke_case, "historical-normal-crosschecked")
        self.assertEqual(total_cap, 0.50)
        self.assertEqual(overrides["gpt-5-6-sol"]["maximum_generation_cost_usd"], 0.15)
        self.assertEqual(overrides["minimax-m3"]["max_output_tokens"], 8000)
        self.assertLessEqual(
            sum(row["maximum_model_cost_usd"] for row in overrides.values()),
            total_cap,
        )

    def test_request_transform_removes_temperature_only_when_declared(self) -> None:
        inner = _CaptureTransport()
        transport = RequestTransform(inner, send_temperature=False)

        transport.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={},
            body=json.dumps({"model": "openai/gpt-5.6-sol", "temperature": 0.2, "max_tokens": 4000}).encode(),
            timeout_seconds=60,
        )

        self.assertIsNotNone(inner.body)
        payload = json.loads(inner.body.decode())
        self.assertNotIn("temperature", payload)
        self.assertEqual(payload["max_tokens"], 4000)

    def test_diagnostic_retains_redacted_provider_detail_and_usage(self) -> None:
        secret = "secret-token"
        response = HttpResponse(
            status=400,
            headers={},
            body=json.dumps(
                {
                    "id": "gen-1",
                    "model": "nex-agi/nex-n2-mini",
                    "error": {
                        "code": 400,
                        "message": f"Provider rejected {secret}",
                        "metadata": {
                            "provider_name": "Nex AGI",
                            "provider_code": 422,
                            "error_type": "invalid_request",
                            "raw": f"schema unsupported for {secret}",
                        },
                    },
                    "usage": {
                        "prompt_tokens": 100,
                        "completion_tokens": 5,
                        "total_tokens": 105,
                        "cost": 0.001,
                    },
                }
            ).encode(),
        )

        value = _diagnostic(response, secret)

        self.assertEqual(value["http_status"], 400)
        self.assertEqual(value["provider_name"], "Nex AGI")
        self.assertEqual(value["estimated_cost_usd"], 0.001)
        self.assertNotIn(secret, json.dumps(value))
        self.assertIn("[REDACTED]", value["provider_raw"])

    def test_missing_plan_is_reported_unscored(self) -> None:
        text = _summary_markdown(
            {
                "trusted_main_sha": "abc",
                "completed_substantive_generations": 1,
                "observed_total_cost_usd": 0.01,
                "models": [
                    {
                        "model": "nex-agi/nex-n2-mini",
                        "route_status": "passed",
                        "full_contract_status": "failed",
                        "scored": False,
                    }
                ],
            }
        )

        self.assertIn("scored `no`", text)
        self.assertNotIn("quality", text.lower())
        self.assertNotIn("stability", text.lower())


if __name__ == "__main__":
    unittest.main()
