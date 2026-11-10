from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from unittest.mock import patch

from llm_analysis.contracts import canonical_json_bytes
from llm_analysis.generation_config import GenerationConfig
from llm_analysis.openrouter_client import GenerationMetadata, GenerationResult, HttpResponse
from llm_analysis.semantic_plan_benchmark import prepare_semantic_plan_benchmark
from llm_analysis.semantic_plan_protected_runner import (
    INFRASTRUCTURE_DECISION,
    decision_exit_code,
    execute_protected_semantic_plan_benchmark,
    main as protected_main,
)

ROOT = Path(__file__).resolve().parents[1]
PROFILE = "config/llm-public-data-semantic-plan.yml"


class _Clock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        self.value += 30.0
        return self.value


class _Client:
    def __init__(self, config: GenerationConfig, *, reject: bool = False) -> None:
        self.config = config
        self.reject = reject
        self.counter = 0

    def generate(
        self,
        *,
        evidence_bundle: Mapping[str, Any],
        prompt_template: str,
        analysis_schema: Mapping[str, Any],
        api_key: str,
    ) -> GenerationResult:
        self.counter += 1
        evidence_id = "missing.evidence" if self.reject else "quality.snapshot.status"
        plan = {
            "claim_plan_version": "crypto-market-claim-plan/v1",
            "prompt_version": "crypto-market-claim-plan/v1",
            "evidence_bundle_id": evidence_bundle["bundle_id"],
            "analysis_order": ["risks_and_limitations"],
            "sections": [
                {
                    "section_kind": "risks_and_limitations",
                    "claims": [
                        {
                            "claim_id": "claim-snapshot-status",
                            "intent": "snapshot_status",
                            "evidence_ids": [evidence_id],
                            "comparison_relation": "none",
                            "confidence": "high",
                        }
                    ],
                }
            ],
        }
        raw = canonical_json_bytes(plan).decode("utf-8")
        return GenerationResult(
            analysis=plan,
            raw_completion=raw,
            metadata=GenerationMetadata(
                requested_model=self.config.model,
                actual_model="openai/gpt-4o-mini",
                actual_provider="OpenAI",
                generation_id=f"generation-{self.counter}",
                input_tokens=100,
                output_tokens=50,
                total_tokens=150,
                estimated_cost_usd=0.001,
                latency_ms=250,
                provider_fallback_used=False,
                cross_model_fallback_used=False,
                provider_preferences=(),
                router_attempt=1,
                finish_reason="stop",
            ),
            provenance={},
            request_summary={
                "model": self.config.model,
                "provider_policy": self.config.provider_policy.as_request(),
                "structured_output": True,
            },
        )


class _RouteTransport:
    def __init__(
        self,
        *,
        status: int = 200,
        message: str = "invalid strict schema",
        provider_code: str | None = None,
        error_type: str | None = None,
    ) -> None:
        self.status = status
        self.message = message
        self.provider_code = provider_code
        self.error_type = error_type
        self.request_body: dict[str, Any] | None = None

    def post(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        body: bytes,
        timeout_seconds: float,
    ) -> HttpResponse:
        self.request_body = json.loads(body.decode("utf-8"))
        if self.status != 200:
            return HttpResponse(
                status=self.status,
                body=json.dumps(
                    {
                        "error": {
                            "message": self.message,
                            "metadata": {
                                "provider_code": self.provider_code,
                                "error_type": self.error_type,
                            },
                        }
                    }
                ).encode("utf-8"),
                headers={},
            )
        return HttpResponse(
            status=200,
            body=json.dumps(
                {
                    "id": "route-generation",
                    "model": "openai/gpt-4o-mini",
                    "choices": [{"message": {"content": json.dumps({"ok": True})}}],
                    "openrouter_metadata": {
                        "endpoints": {
                            "available": [{"selected": True, "provider": "OpenAI"}]
                        }
                    },
                    "usage": {"cost": 0.001},
                }
            ).encode("utf-8"),
            headers={},
        )


def _catalogue() -> Mapping[str, Any]:
    return {
        "data": [
            {
                "id": "openai/gpt-4o-mini",
                "supported_parameters": ["response_format", "structured_outputs"],
                "pricing": {"prompt": "0.00000015", "completion": "0.00000060"},
                "context_length": 128000,
                "top_provider": {"max_completion_tokens": 16384},
                "expiration_date": None,
            }
        ]
    }


def _key_status(_: str) -> Mapping[str, Any]:
    return {
        "limit_remaining": 10.0,
        "limit": 10.0,
        "limit_reset": None,
        "usage": 0.0,
        "usage_daily": 0.0,
        "usage_weekly": 0.0,
        "usage_monthly": 0.0,
        "is_free_tier": False,
    }


def _kwargs(
    prepared_dir: str,
    output_dir: str,
    *,
    transport: _RouteTransport,
    reject: bool = False,
) -> dict[str, Any]:
    return {
        "repository_root": ROOT,
        "profile_path": PROFILE,
        "viability_config_path": "config/llm-evaluation-viability.yml",
        "prepared_dir": prepared_dir,
        "output_dir": output_dir,
        "api_key": "test-secret",
        "trusted_main_sha": "a" * 40,
        "catalogue_loader": _catalogue,
        "key_status_loader": _key_status,
        "route_transport": transport,
        "client_builder": lambda config: _Client(config, reject=reject),
        "sleeper": lambda _: None,
        "monotonic": _Clock(),
        "now": lambda: datetime(2026, 7, 12, 0, 0, tzinfo=timezone.utc),
        "jitter": lambda _minimum, _maximum: 0.0,
    }


class ProtectedSemanticPlanRunnerTests(unittest.TestCase):
    def test_route_probe_uses_shared_strict_schema_projection(self) -> None:
        transport = _RouteTransport()
        with tempfile.TemporaryDirectory() as prepared, tempfile.TemporaryDirectory() as output:
            prepare_semantic_plan_benchmark(
                repository_root=ROOT,
                profile_path=PROFILE,
                output_dir=prepared,
            )
            summary = execute_protected_semantic_plan_benchmark(
                **_kwargs(prepared, output, transport=transport)
            )

        self.assertEqual(summary["decision"], "semantic-plan-qualified")
        schema = transport.request_body["response_format"]["json_schema"]["schema"]
        self.assertNotIn("const", json.dumps(schema, sort_keys=True))
        self.assertEqual(schema["properties"]["ok"], {"type": "boolean", "enum": [True]})

    def test_http_400_is_infrastructure_failure_with_sanitised_diagnostics(self) -> None:
        transport = _RouteTransport(
            status=400,
            message="invalid schema for test-secret",
            provider_code="400",
            error_type="invalid_request_error",
        )
        with tempfile.TemporaryDirectory() as prepared, tempfile.TemporaryDirectory() as output:
            prepare_semantic_plan_benchmark(
                repository_root=ROOT,
                profile_path=PROFILE,
                output_dir=prepared,
            )
            summary = execute_protected_semantic_plan_benchmark(
                **_kwargs(prepared, output, transport=transport)
            )
            stages = json.loads((Path(output) / "viability-stages.json").read_text())["stages"]
            retained = json.loads((Path(output) / "semantic-plan-summary.json").read_text())
            decision = (Path(output) / "semantic-plan-decision.md").read_text()

        self.assertEqual(summary["decision"], INFRASTRUCTURE_DECISION)
        self.assertFalse(summary["qualified"])
        self.assertEqual(summary["completed_corpus_runs"], 0)
        self.assertEqual(retained["decision"], INFRASTRUCTURE_DECISION)
        self.assertNotIn("semantic-plan-no-go", decision)
        self.assertIn("Model capability conclusion: `none`", decision)
        route_stage = next(row for row in stages if row["stage"] == "route_preflight")
        self.assertEqual(route_stage["http_status"], 400)
        self.assertEqual(route_stage["provider_code"], "400")
        self.assertEqual(route_stage["error_type"], "invalid_request_error")
        self.assertIn("[REDACTED]", route_stage["message"])
        self.assertNotIn("test-secret", route_stage["message"])

    def test_complete_rejected_corpus_remains_semantic_no_go(self) -> None:
        transport = _RouteTransport()
        with tempfile.TemporaryDirectory() as prepared, tempfile.TemporaryDirectory() as output:
            prepare_semantic_plan_benchmark(
                repository_root=ROOT,
                profile_path=PROFILE,
                output_dir=prepared,
            )
            summary = execute_protected_semantic_plan_benchmark(
                **_kwargs(prepared, output, transport=transport, reject=True)
            )

        self.assertEqual(summary["completed_corpus_runs"], 10)
        self.assertEqual(summary["decision"], "semantic-plan-no-go")
        self.assertNotIn("infrastructure_failure", summary)
        self.assertEqual(decision_exit_code(summary), 0)

    def test_infrastructure_decision_has_nonzero_command_exit(self) -> None:
        argv = [
            "semantic_plan_protected_runner",
            "run",
            "--prepared-dir",
            "prepared",
            "--output-dir",
            "output",
        ]
        with patch.object(sys, "argv", argv), patch.dict(
            os.environ,
            {"OPENROUTER_API_KEY": "test-secret"},
        ), patch(
            "llm_analysis.semantic_plan_protected_runner.execute_protected_semantic_plan_benchmark",
            return_value={"decision": INFRASTRUCTURE_DECISION},
        ):
            self.assertEqual(protected_main(), 3)


if __name__ == "__main__":
    unittest.main()
