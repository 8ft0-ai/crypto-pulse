from __future__ import annotations

import copy
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

import yaml

from llm_analysis.generation_config import (
    ConfigurationError,
    load_generation_config,
    model_matches,
)
from llm_analysis.openrouter_client import (
    CostLimitError,
    GenerationTimeoutError,
    HttpResponse,
    IneligibleRoutingError,
    InputLimitError,
    InvalidResponseError,
    MissingSecretError,
    OpenRouterClient,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "llm-generation.yml"

PROMPT = """Trusted instructions.\n<BEGIN_UNTRUSTED_EVIDENCE_BUNDLE>\n{{EVIDENCE_BUNDLE_JSON}}\n<END_UNTRUSTED_EVIDENCE_BUNDLE>\nReturn JSON only.\n"""
SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["schema_version"],
    "properties": {"schema_version": {"const": "crypto-market-analysis/v1"}},
}
BUNDLE = {
    "schema_version": "crypto-market-evidence-bundle/v1",
    "bundle_id": "sha256:" + "a" * 64,
    "source_snapshot": {
        "path": "data/crypto/hourly/2026/07/08/1742_AEST_source_snapshot.json",
        "sha256": "b" * 64,
    },
    "product_boundaries": ["Not financial advice."],
    "evidence": [
        {
            "evidence_id": "market.asset.bitcoin.price_usd",
            "evidence_type": "number",
            "value": 62739,
        }
    ],
}
ANALYSIS = {"schema_version": "crypto-market-analysis/v1"}


def response_payload(**overrides: Any) -> dict[str, Any]:
    value: dict[str, Any] = {
        "id": "gen-test-123",
        "model": "nvidia/nemotron-3-super-120b-a12b",
        "choices": [
            {
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": json.dumps(ANALYSIS)},
            }
        ],
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 20,
            "total_tokens": 120,
            "cost": 0,
        },
        "openrouter_metadata": {
            "requested": "nvidia/nemotron-3-super-120b-a12b:free",
            "strategy": "direct",
            "attempt": 1,
            "endpoints": {
                "total": 1,
                "available": [
                    {
                        "provider": "NVIDIA",
                        "model": "nvidia/nemotron-3-super-120b-a12b",
                        "selected": True,
                    }
                ],
            },
            "attempts": [
                {
                    "provider": "NVIDIA",
                    "model": "nvidia/nemotron-3-super-120b-a12b",
                    "status": 200,
                }
            ],
        },
    }
    value.update(overrides)
    return value


class FakeTransport:
    def __init__(self, outcomes: list[Any]):
        self.outcomes = list(outcomes)
        self.calls: list[dict[str, Any]] = []

    def post(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        body: bytes,
        timeout_seconds: float,
    ) -> HttpResponse:
        self.calls.append(
            {
                "url": url,
                "headers": dict(headers),
                "body": body,
                "timeout_seconds": timeout_seconds,
            }
        )
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def ok_response(payload: Mapping[str, Any] | None = None) -> HttpResponse:
    return HttpResponse(
        200,
        json.dumps(payload or response_payload()).encode("utf-8"),
        {"content-type": "application/json"},
    )


class GovernedOpenRouterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = load_generation_config(CONFIG_PATH)

    def client(self, transport: FakeTransport, *, times: list[float] | None = None):
        values = list(times or [10.0, 10.125])
        return OpenRouterClient(
            self.config,
            transport=transport,
            sleeper=lambda _: None,
            monotonic=lambda: values.pop(0),
            now=lambda: datetime(2026, 7, 11, 4, 30, tzinfo=timezone.utc),
        )

    def generate(self, client: OpenRouterClient, **kwargs: Any):
        return client.generate(
            evidence_bundle=BUNDLE,
            prompt_template=PROMPT,
            analysis_schema=SCHEMA,
            api_key="secret-test-key",
            **kwargs,
        )

    def test_configuration_pins_one_explicit_free_model_and_governance_policy(self) -> None:
        self.assertEqual(
            self.config.model, "nvidia/nemotron-3-super-120b-a12b:free"
        )
        self.assertFalse(self.config.cross_model_fallback)
        self.assertTrue(self.config.structured_output)
        self.assertTrue(self.config.router_metadata)
        self.assertTrue(self.config.provider_policy.require_parameters)
        self.assertEqual(self.config.provider_policy.data_collection, "deny")
        self.assertTrue(self.config.provider_policy.zdr)
        self.assertTrue(self.config.provider_policy.allow_fallbacks)
        self.assertEqual(
            self.config.provider_policy.as_request()["max_price"],
            {"prompt": 0.0, "completion": 0.0, "request": 0.0},
        )

    def test_configuration_rejects_router_alias_and_cross_model_fallback(self) -> None:
        raw = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        for model, cross_model in (("openrouter/auto", False), ("openrouter/free", False), (raw["generation"]["model"], True)):
            candidate = copy.deepcopy(raw)
            candidate["generation"]["model"] = model
            candidate["generation"]["cross_model_fallback"] = cross_model
            with tempfile.NamedTemporaryFile("w", suffix=".yml", delete=False) as handle:
                yaml.safe_dump(candidate, handle)
                path = handle.name
            with self.subTest(model=model, cross_model=cross_model):
                with self.assertRaises(ConfigurationError):
                    load_generation_config(path)

    def test_configuration_rejects_weakened_privacy_or_unbounded_retry(self) -> None:
        raw = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        mutations = [
            ("provider_policy", "data_collection", "allow"),
            ("provider_policy", "zdr", False),
            ("provider_policy", "require_parameters", False),
            ("api", "retry_limit", 99),
            ("api", "router_metadata", False),
        ]
        for section, key, value in mutations:
            candidate = copy.deepcopy(raw)
            candidate[section][key] = value
            with tempfile.NamedTemporaryFile("w", suffix=".yml", delete=False) as handle:
                yaml.safe_dump(candidate, handle)
                path = handle.name
            with self.subTest(section=section, key=key):
                with self.assertRaises(ConfigurationError):
                    load_generation_config(path)

    def test_missing_secret_fails_before_network_attempt(self) -> None:
        transport = FakeTransport([ok_response()])
        client = self.client(transport)
        with self.assertRaises(MissingSecretError):
            client.generate(
                evidence_bundle=BUNDLE,
                prompt_template=PROMPT,
                analysis_schema=SCHEMA,
                environment={},
            )
        self.assertEqual(transport.calls, [])

    def test_request_is_strict_single_model_secret_safe_and_policy_bounded(self) -> None:
        transport = FakeTransport([ok_response()])
        result = self.generate(self.client(transport))
        self.assertEqual(result.analysis, ANALYSIS)
        call = transport.calls[0]
        body = json.loads(call["body"])
        self.assertEqual(body["model"], self.config.model)
        self.assertNotIn("models", body)
        self.assertNotIn("route", body)
        self.assertEqual(body["response_format"]["type"], "json_schema")
        self.assertTrue(body["response_format"]["json_schema"]["strict"])
        self.assertEqual(body["provider"]["data_collection"], "deny")
        self.assertTrue(body["provider"]["zdr"])
        self.assertTrue(body["provider"]["require_parameters"])
        self.assertEqual(body["provider"]["max_price"]["prompt"], 0.0)
        self.assertEqual(call["headers"]["X-OpenRouter-Metadata"], "enabled")
        self.assertEqual(call["headers"]["Authorization"], "Bearer secret-test-key")
        self.assertNotIn(b"secret-test-key", call["body"])
        self.assertNotIn("Authorization", result.request_summary)
        self.assertNotIn("secret-test-key", json.dumps(result.request_summary))
        prompt = body["messages"][0]["content"]
        self.assertIn("<BEGIN_UNTRUSTED_EVIDENCE_BUNDLE>", prompt)
        self.assertIn("market.asset.bitcoin.price_usd", prompt)

    def test_success_captures_model_provider_usage_cost_latency_and_provenance(self) -> None:
        transport = FakeTransport([ok_response()])
        result = self.generate(self.client(transport, times=[1.0, 1.234]))
        metadata = result.metadata
        self.assertEqual(metadata.requested_model, self.config.model)
        self.assertEqual(metadata.actual_model, "nvidia/nemotron-3-super-120b-a12b")
        self.assertEqual(metadata.actual_provider, "NVIDIA")
        self.assertEqual(metadata.generation_id, "gen-test-123")
        self.assertEqual(metadata.input_tokens, 100)
        self.assertEqual(metadata.output_tokens, 20)
        self.assertEqual(metadata.total_tokens, 120)
        self.assertEqual(metadata.estimated_cost_usd, 0)
        self.assertEqual(metadata.latency_ms, 234)
        self.assertFalse(metadata.provider_fallback_used)
        self.assertFalse(metadata.cross_model_fallback_used)
        provenance = result.provenance
        self.assertEqual(provenance["provider"], "openrouter")
        self.assertEqual(provenance["requested_model"], self.config.model)
        self.assertEqual(provenance["actual_provider"], "NVIDIA")
        self.assertEqual(provenance["source_snapshot"]["sha256"], "b" * 64)
        self.assertRegex(provenance["prompt_sha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(provenance["completion_sha256"], r"^[0-9a-f]{64}$")
        self.assertFalse(provenance["routing"]["cross_model_fallback_used"])

    def test_same_model_provider_fallback_is_recorded(self) -> None:
        payload = response_payload()
        payload["openrouter_metadata"] = {
            "requested": self.config.model,
            "strategy": "direct",
            "attempt": 2,
            "endpoints": {
                "available": [
                    {
                        "provider": "NVIDIA",
                        "model": "nvidia/nemotron-3-super-120b-a12b",
                        "selected": True,
                    }
                ]
            },
            "attempts": [
                {"provider": "Provider A", "model": payload["model"], "status": 502},
                {"provider": "NVIDIA", "model": payload["model"], "status": 200},
            ],
        }
        result = self.generate(self.client(FakeTransport([ok_response(payload)])))
        self.assertTrue(result.metadata.provider_fallback_used)
        self.assertFalse(result.metadata.cross_model_fallback_used)
        self.assertTrue(result.provenance["routing"]["provider_fallback_used"])

    def test_different_actual_model_is_rejected(self) -> None:
        payload = response_payload(model="google/gemma-4-26b-a4b-it:free")
        with self.assertRaises(IneligibleRoutingError):
            self.generate(self.client(FakeTransport([ok_response(payload)])))
        self.assertTrue(
            model_matches(
                "nvidia/nemotron-3-super-120b-a12b:free",
                "nvidia/nemotron-3-super-120b-a12b",
            )
        )

    def test_timeout_retries_are_bounded(self) -> None:
        transport = FakeTransport(
            [GenerationTimeoutError("timeout"), GenerationTimeoutError("timeout")]
        )
        with self.assertRaises(GenerationTimeoutError):
            self.generate(self.client(transport, times=[1.0, 1.1]))
        self.assertEqual(len(transport.calls), self.config.retry_limit + 1)

    def test_retryable_provider_failure_can_recover_once(self) -> None:
        retryable = HttpResponse(
            502,
            json.dumps({"error": {"message": "provider unavailable"}}).encode(),
            {},
        )
        transport = FakeTransport([retryable, ok_response()])
        result = self.generate(self.client(transport))
        self.assertEqual(result.analysis, ANALYSIS)
        self.assertEqual(len(transport.calls), 2)

    def test_no_eligible_provider_is_typed_and_redacted(self) -> None:
        response = HttpResponse(
            404,
            json.dumps(
                {"error": {"message": "No allowed providers are available for secret-test-key"}}
            ).encode(),
            {},
        )
        with self.assertRaises(IneligibleRoutingError) as captured:
            self.generate(self.client(FakeTransport([response])))
        self.assertNotIn("secret-test-key", str(captured.exception))
        self.assertIn("[REDACTED]", str(captured.exception))

    def test_malformed_response_and_completion_json_fail_closed(self) -> None:
        malformed = response_payload(choices=[])
        invalid_completion = response_payload()
        invalid_completion["choices"][0]["message"]["content"] = "not json"
        for payload in (malformed, invalid_completion):
            with self.subTest(payload=payload):
                with self.assertRaises(InvalidResponseError):
                    self.generate(self.client(FakeTransport([ok_response(payload)])))

    def test_input_size_limit_blocks_network(self) -> None:
        raw = yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))
        raw["generation"]["max_request_bytes"] = 1024
        with tempfile.NamedTemporaryFile("w", suffix=".yml", delete=False) as handle:
            yaml.safe_dump(raw, handle)
            path = handle.name
        config = load_generation_config(path)
        transport = FakeTransport([ok_response()])
        client = OpenRouterClient(config, transport=transport, sleeper=lambda _: None)
        huge = copy.deepcopy(BUNDLE)
        huge["evidence"][0]["value"] = "x" * 5000
        with self.assertRaises(InputLimitError):
            client.generate(
                evidence_bundle=huge,
                prompt_template=PROMPT,
                analysis_schema=SCHEMA,
                api_key="secret-test-key",
            )
        self.assertEqual(transport.calls, [])

    def test_reported_cost_over_limit_is_rejected(self) -> None:
        payload = response_payload()
        payload["usage"]["cost"] = self.config.max_cost_usd + 0.01
        with self.assertRaises(CostLimitError):
            self.generate(self.client(FakeTransport([ok_response(payload)])))


if __name__ == "__main__":
    unittest.main()
