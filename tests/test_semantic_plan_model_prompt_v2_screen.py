from __future__ import annotations

import json
import unittest
from pathlib import Path

from llm_analysis.openrouter_client import HttpResponse
from llm_analysis.semantic_plan_model_final_calibration import EXECUTION_MESSAGE
from llm_analysis.semantic_plan_model_prompt_v2_screen import (
    PROMPT_V2_PATH,
    PROMPT_V2_VERSION,
    PromptV2RequestTransform,
    load_prompt_v2_screen_plan,
)


class _CaptureTransport:
    def __init__(self) -> None:
        self.body: bytes | None = None

    def post(self, url, *, headers, body, timeout_seconds):
        self.body = body
        return HttpResponse(status=200, body=b"{}", headers={})


class SemanticPlanModelPromptV2ScreenTests(unittest.TestCase):
    def test_prompt_v1_is_preserved_and_v2_exposes_source_grouping_rule(self) -> None:
        v1 = Path("prompts/crypto-market-claim-plan-v1.md")
        v2 = Path(PROMPT_V2_PATH)

        self.assertTrue(v1.is_file())
        self.assertTrue(v2.is_file())
        self.assertNotEqual(v1.read_bytes(), v2.read_bytes())
        rule = "A `source_status` claim must describe exactly one source subject."
        self.assertNotIn(rule, v1.read_text(encoding="utf-8"))
        self.assertIn(rule, v2.read_text(encoding="utf-8"))
        self.assertIn(
            "Every cited evidence record in that claim must belong to that same source subject.",
            v2.read_text(encoding="utf-8"),
        )

    def test_corrective_plan_is_three_call_and_ten_cent_bounded(self) -> None:
        plan = load_prompt_v2_screen_plan(
            Path("."), "config/semantic-plan-model-corrective-screen.yml"
        )

        self.assertEqual(plan.plan_id, "semantic-plan-model-corrective-screen/v1")
        self.assertEqual(plan.maximum_total_cost_usd, 0.10)
        self.assertEqual(
            tuple(item.model for item in plan.candidates),
            (
                "openai/gpt-5.6-luna",
                "deepseek/deepseek-v4-flash",
                "qwen/qwen3.6-flash",
            ),
        )
        self.assertGreaterEqual(
            plan.overrides["deepseek-v4-flash"]["route_probe_max_output_tokens"],
            256,
        )
        self.assertEqual(plan.overrides["qwen3-6-flash"]["max_output_tokens"], 8000)
        self.assertLessEqual(
            sum(item.maximum_model_cost_usd for item in plan.candidates),
            plan.maximum_total_cost_usd,
        )
        self.assertEqual(
            tuple(item["model"] for item in plan.excluded_models),
            ("xiaomi/mimo-v2.5-pro", "bytedance-seed/seed-2.0-mini"),
        )

    def test_final_sol_nex_plan_uses_prompt_v2(self) -> None:
        plan = load_prompt_v2_screen_plan(
            Path("."), "config/semantic-plan-model-final-calibration-v2.yml"
        )

        self.assertEqual(plan.plan_id, "semantic-plan-model-final-calibration/v2")
        self.assertEqual(plan.maximum_total_cost_usd, 0.25)
        self.assertEqual(
            tuple(item.model for item in plan.candidates),
            ("openai/gpt-5.6-sol", "nex-agi/nex-n2-mini"),
        )
        self.assertFalse(plan.overrides["gpt-5-6-sol"]["ensure_user_message"])
        self.assertTrue(plan.overrides["nex-n2-mini"]["ensure_user_message"])
        self.assertIsNone(plan.overrides["gpt-5-6-sol"]["reasoning"])
        self.assertIsNone(plan.overrides["nex-n2-mini"]["reasoning"])
        self.assertEqual(PROMPT_V2_VERSION, "crypto-market-claim-plan/v2")

    def test_deepseek_route_transform_replaces_sixteen_token_probe(self) -> None:
        inner = _CaptureTransport()
        transform = PromptV2RequestTransform(
            inner,
            send_temperature=True,
            ensure_user_message=True,
            reasoning={"enabled": True, "effort": "high", "exclude": True},
            max_output_tokens=256,
        )

        transform.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={},
            body=json.dumps(
                {
                    "model": "deepseek/deepseek-v4-flash",
                    "messages": [{"role": "system", "content": "probe"}],
                    "temperature": 0.2,
                    "max_tokens": 16,
                }
            ).encode(),
            timeout_seconds=60,
        )

        self.assertIsNotNone(inner.body)
        payload = json.loads(inner.body.decode())
        self.assertEqual(payload["max_tokens"], 256)
        self.assertEqual(payload["reasoning"], {"effort": "high", "exclude": True})
        self.assertEqual(
            [item for item in payload["messages"] if item["role"] == "user"],
            [{"role": "user", "content": EXECUTION_MESSAGE}],
        )

    def test_luna_transform_omits_temperature_and_disables_reasoning(self) -> None:
        inner = _CaptureTransport()
        transform = PromptV2RequestTransform(
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
                    "max_tokens": 4000,
                }
            ).encode(),
            timeout_seconds=60,
        )

        self.assertIsNotNone(inner.body)
        payload = json.loads(inner.body.decode())
        self.assertNotIn("temperature", payload)
        self.assertEqual(payload["reasoning"], {"effort": "none", "exclude": True})
        self.assertFalse(any(item["role"] == "user" for item in payload["messages"]))

    def test_qwen_transform_adds_one_user_message_and_disables_reasoning(self) -> None:
        inner = _CaptureTransport()
        transform = PromptV2RequestTransform(
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
                    "max_tokens": 8000,
                }
            ).encode(),
            timeout_seconds=60,
        )

        self.assertIsNotNone(inner.body)
        payload = json.loads(inner.body.decode())
        self.assertEqual(payload["reasoning"], {"enabled": False, "exclude": True})
        self.assertEqual(
            [item for item in payload["messages"] if item["role"] == "user"],
            [{"role": "user", "content": EXECUTION_MESSAGE}],
        )

    def test_null_reasoning_preserves_existing_provider_request(self) -> None:
        inner = _CaptureTransport()
        transform = PromptV2RequestTransform(
            inner,
            send_temperature=False,
            ensure_user_message=False,
            reasoning=None,
        )
        transform.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={},
            body=json.dumps(
                {
                    "model": "openai/gpt-5.6-sol",
                    "messages": [{"role": "system", "content": "governed"}],
                    "temperature": 0.2,
                }
            ).encode(),
            timeout_seconds=60,
        )

        self.assertIsNotNone(inner.body)
        payload = json.loads(inner.body.decode())
        self.assertNotIn("reasoning", payload)
        self.assertNotIn("temperature", payload)


if __name__ == "__main__":
    unittest.main()
