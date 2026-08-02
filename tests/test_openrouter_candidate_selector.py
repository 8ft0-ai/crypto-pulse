from __future__ import annotations

import json
import unittest

from llm_analysis.candidate_selector import SelectorClientError
from llm_analysis.generation_config import GenerationConfig, ProviderPolicy
from llm_analysis.openrouter_candidate_selector import OpenRouterCandidateSelectorClient
from llm_analysis.openrouter_client import HttpResponse

CANDIDATE_ID = "claim-candidate:sha256:" + "a" * 64


class FakeTransport:
    def __init__(self, *, provider_fallback: bool = False) -> None:
        self.provider_fallback = provider_fallback
        self.requests: list[dict] = []

    def post(self, url, *, headers, body, timeout_seconds):
        self.requests.append(json.loads(body.decode("utf-8")))
        attempts = [
            {"status": 200, "provider": "OpenAI"},
            *(
                [{"status": 200, "provider": "OpenAI"}]
                if self.provider_fallback
                else []
            ),
        ]
        payload = {
            "id": "generation-1",
            "model": "openai/gpt-5.6-sol",
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {
                        "content": json.dumps(
                            {"selected_candidate_ids": [CANDIDATE_ID]},
                            separators=(",", ":"),
                        )
                    },
                }
            ],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 20,
                "total_tokens": 120,
                "cost": 0.001,
                "completion_tokens_details": {"reasoning_tokens": 5},
            },
            "openrouter_metadata": {
                "attempt": len(attempts),
                "attempts": attempts,
                "endpoints": {
                    "available": [{"selected": True, "provider": "OpenAI"}]
                },
            },
        }
        return HttpResponse(200, json.dumps(payload).encode("utf-8"), {})


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


class OpenRouterCandidateSelectorTests(unittest.TestCase):
    def request(self):
        return {
            "request_id": "sha256:" + "1" * 64,
            "max_selection_count": 7,
            "section_limits": {"market_summary": 1},
            "intent_limits": {"absolute_observation": 1},
            "candidates": [
                {
                    "candidate_id": CANDIDATE_ID,
                    "features": {"redundancy_group": "group-a"},
                }
            ],
        }

    def schema(self):
        return {
            "type": "object",
            "additionalProperties": False,
            "required": ["selected_candidate_ids"],
            "properties": {
                "selected_candidate_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                }
            },
        }

    def test_adapter_returns_only_the_decoded_selection_and_records_provenance(self):
        transport = FakeTransport()
        before: list[float] = []
        after: list[float] = []
        client = OpenRouterCandidateSelectorClient(
            runtime(),
            prompt_template=(
                "Request {{CANDIDATE_SELECTOR_REQUEST_JSON}} "
                "Repair {{CANDIDATE_SELECTOR_REPAIR_JSON}}"
            ),
            api_key="secret",
            logical_id="test/run",
            transport=transport,
            send_temperature=False,
            before_provider_call=before.append,
            after_provider_call=after.append,
        )
        result = client.select(
            request=self.request(),
            response_schema=self.schema(),
            repair=None,
        )
        self.assertEqual(result.payload, {"selected_candidate_ids": [CANDIDATE_ID]})
        self.assertEqual(before, [0.12])
        self.assertEqual(after, [0.001])
        self.assertEqual(len(client.call_records), 1)
        record = client.call_records[0]
        self.assertEqual(record.actual_model, "openai/gpt-5.6-sol")
        self.assertEqual(record.actual_provider, "OpenAI")
        self.assertEqual(record.reasoning_tokens, 5)
        self.assertFalse(record.provider_fallback_used)
        request_body = transport.requests[0]
        self.assertNotIn("temperature", request_body)
        self.assertEqual(request_body["provider"]["only"], ["OpenAI"])
        self.assertEqual(
            set(result.metadata),
            {
                "client",
                "model",
                "provider",
                "generation_id",
                "latency_ms",
                "input_tokens",
                "output_tokens",
                "estimated_cost_usd",
            },
        )

    def test_provider_fallback_is_rejected_before_slice5_validation(self):
        client = OpenRouterCandidateSelectorClient(
            runtime(),
            prompt_template=(
                "Request {{CANDIDATE_SELECTOR_REQUEST_JSON}} "
                "Repair {{CANDIDATE_SELECTOR_REPAIR_JSON}}"
            ),
            api_key="secret",
            logical_id="test/run",
            transport=FakeTransport(provider_fallback=True),
            send_temperature=False,
        )
        with self.assertRaises(SelectorClientError) as context:
            client.select(
                request=self.request(),
                response_schema=self.schema(),
                repair=None,
            )
        self.assertEqual(context.exception.code, "ineligible_routing")
        self.assertEqual(client.call_records, [])


if __name__ == "__main__":
    unittest.main()
