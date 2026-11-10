from __future__ import annotations

import json
import unittest
from pathlib import Path

from llm_analysis.openrouter_client import HttpResponse
from llm_analysis.semantic_plan_model_catalogue_screen import (
    CatalogueRequestTransform,
    EXPECTED_MODELS,
    _catalogue_reasoning_failure,
    load_catalogue_screen_config,
)
from llm_analysis.semantic_plan_model_final_calibration import EXECUTION_MESSAGE


class _CaptureTransport:
    def __init__(self) -> None:
        self.body: bytes | None = None

    def post(self, url, *, headers, body, timeout_seconds):
        self.body = body
        return HttpResponse(status=200, body=b"{}", headers={})


class SemanticPlanModelCatalogueScreenTests(unittest.TestCase):
    def test_checked_config_is_five_call_and_fifteen_cent_bounded(self) -> None:
        plan = load_catalogue_screen_config(
            Path("."), "config/semantic-plan-model-catalogue-screen.yml"
        )

        self.assertEqual(
            tuple((item.key, item.model) for item in plan.candidates),
            EXPECTED_MODELS,
        )
        self.assertEqual(plan.smoke_case_key, "historical-normal-crosschecked")
        self.assertEqual(plan.maximum_total_cost_usd, 0.15)
        self.assertEqual(len(plan.candidates), 5)
        self.assertLessEqual(
            sum(item.maximum_model_cost_usd for item in plan.candidates),
            plan.maximum_total_cost_usd,
        )
        self.assertEqual(
            plan.overrides["deepseek-v4-flash"]["reasoning"]["effort"],
            "high",
        )
        self.assertEqual(
            plan.overrides["gpt-5-6-luna"]["reasoning"]["effort"],
            "none",
        )
        self.assertEqual(
            plan.overrides["seed-2-0-mini"]["reasoning"]["effort"],
            "minimal",
        )

    def test_luna_transform_omits_temperature_and_disables_reasoning(self) -> None:
        inner = _CaptureTransport()
        transform = CatalogueRequestTransform(
            inner,
            send_temperature=False,
            ensure_user_message=False,
            reasoning={"enabled": False, "effort": "none", "exclude": True},
        )

        transform.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={},
            body=json.dumps(
                {
                    "model": "openai/gpt-5.6-luna",
                    "messages": [{"role": "system", "content": "governed"}],
                    "temperature": 0.2,
                }
            ).encode(),
            timeout_seconds=60,
        )

        self.assertIsNotNone(inner.body)
        payload = json.loads(inner.body.decode())
        self.assertNotIn("temperature", payload)
        self.assertEqual(payload["reasoning"], {"effort": "none", "exclude": True})
        self.assertFalse(any(item["role"] == "user" for item in payload["messages"]))

    def test_non_openai_transform_adds_one_user_message_and_disables_reasoning(self) -> None:
        inner = _CaptureTransport()
        transform = CatalogueRequestTransform(
            inner,
            send_temperature=True,
            ensure_user_message=True,
            reasoning={"enabled": False, "effort": None, "exclude": True},
        )

        transform.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={},
            body=json.dumps(
                {
                    "model": "qwen/qwen3.6-flash",
                    "messages": [{"role": "system", "content": "governed"}],
                    "temperature": 0.2,
                }
            ).encode(),
            timeout_seconds=60,
        )

        self.assertIsNotNone(inner.body)
        payload = json.loads(inner.body.decode())
        self.assertEqual(payload["temperature"], 0.2)
        self.assertEqual(
            payload["reasoning"], {"enabled": False, "exclude": True}
        )
        self.assertEqual(
            [item for item in payload["messages"] if item["role"] == "user"],
            [{"role": "user", "content": EXECUTION_MESSAGE}],
        )

    def test_transform_does_not_duplicate_existing_user_message(self) -> None:
        inner = _CaptureTransport()
        transform = CatalogueRequestTransform(
            inner,
            send_temperature=True,
            ensure_user_message=True,
            reasoning={"enabled": True, "effort": "minimal", "exclude": True},
        )
        transform.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={},
            body=json.dumps(
                {
                    "messages": [
                        {"role": "system", "content": "governed"},
                        {"role": "user", "content": "existing"},
                    ],
                    "temperature": 0.2,
                }
            ).encode(),
            timeout_seconds=60,
        )

        self.assertIsNotNone(inner.body)
        payload = json.loads(inner.body.decode())
        self.assertEqual(
            [item for item in payload["messages"] if item["role"] == "user"],
            [{"role": "user", "content": "existing"}],
        )
        self.assertEqual(
            payload["reasoning"], {"effort": "minimal", "exclude": True}
        )

    def test_live_catalogue_reasoning_policy_is_checked(self) -> None:
        row = {
            "supported_parameters": ["reasoning", "response_format", "structured_outputs"],
            "reasoning": {
                "mandatory": False,
                "supported_efforts": ["high", "minimal", "none"],
            },
        }
        self.assertIsNone(
            _catalogue_reasoning_failure(
                row, {"enabled": True, "effort": "high", "exclude": True}
            )
        )
        self.assertIn(
            "reviewed reasoning effort low",
            _catalogue_reasoning_failure(
                row, {"enabled": True, "effort": "low", "exclude": True}
            )
            or "",
        )
        mandatory = {
            "supported_parameters": ["reasoning"],
            "reasoning": {"mandatory": True, "supported_efforts": ["high"]},
        }
        self.assertIn(
            "mandatory reasoning",
            _catalogue_reasoning_failure(
                mandatory,
                {"enabled": False, "effort": None, "exclude": True},
            )
            or "",
        )


if __name__ == "__main__":
    unittest.main()
