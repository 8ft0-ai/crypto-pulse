from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any, Mapping

from llm_analysis.candidate_selector_stage0 import (
    STAGE0_PREPARED_MANIFEST,
    execute_stage0,
    prepare_stage0,
)
from llm_analysis.candidate_selector_stage0_config import load_stage0_plan
from llm_analysis.openrouter_client import HttpResponse

ROOT = Path(__file__).resolve().parents[1]
CONFIG = "config/low-cost-candidate-selector-stage-0.yml"


class _SelectorTransport:
    def __init__(self, selected_id: str) -> None:
        self.selected_id = selected_id
        self.calls: list[dict[str, Any]] = []

    def post(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        body: bytes,
        timeout_seconds: float,
    ) -> HttpResponse:
        request = json.loads(body.decode("utf-8"))
        self.calls.append(request)
        model = request["model"]
        provider = {
            "deepseek/deepseek-v4-flash-0731": "DeepSeek",
            "openai/gpt-oss-120b": "DeepInfra",
            "inception/mercury-2": "Inception",
        }[model]
        cost = {
            "deepseek/deepseek-v4-flash-0731": 0.004,
            "openai/gpt-oss-120b": 0.003,
            "inception/mercury-2": 0.012,
        }[model]
        content = json.dumps(
            {"selected_candidate_ids": [self.selected_id]},
            separators=(",", ":"),
        )
        payload = {
            "id": f"fake-{provider}",
            "model": model,
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"content": content},
                }
            ],
            "usage": {
                "prompt_tokens": 100,
                "completion_tokens": 20,
                "total_tokens": 120,
                "cost": cost,
                "completion_tokens_details": {"reasoning_tokens": 0},
            },
            "openrouter_metadata": {
                "attempt": 1,
                "endpoints": {
                    "available": [
                        {"selected": True, "provider": provider},
                    ]
                },
            },
        }
        return HttpResponse(200, json.dumps(payload).encode("utf-8"), {})


class CandidateSelectorStage0Tests(unittest.TestCase):
    @staticmethod
    def _catalogue() -> dict[str, Any]:
        return {
            "data": [
                {
                    "id": "deepseek/deepseek-v4-flash-0731",
                    "context_length": 1_048_576,
                    "supported_parameters": ["response_format", "structured_outputs"],
                    "pricing": {"prompt": "0.00000009", "completion": "0.00000018"},
                    "top_provider": {"max_completion_tokens": 8192},
                },
                {
                    "id": "openai/gpt-oss-120b",
                    "context_length": 131_072,
                    "supported_parameters": ["response_format", "structured_outputs"],
                    "pricing": {"prompt": "0.000000037", "completion": "0.00000017"},
                    "top_provider": {"max_completion_tokens": 8192},
                },
                {
                    "id": "inception/mercury-2",
                    "context_length": 128_000,
                    "supported_parameters": ["response_format", "structured_outputs"],
                    "pricing": {"prompt": "0.00000025", "completion": "0.00000075"},
                    "top_provider": {"max_completion_tokens": 8192},
                },
            ]
        }

    @staticmethod
    def _route_probe(config: Any, api_key: str, *, transport: Any = None) -> dict[str, Any]:
        del api_key, transport
        return {
            "requested_model": config.model,
            "actual_model": config.model,
            "actual_provider": config.provider_policy.only[0],
            "generation_id": f"route-{config.model}",
            "estimated_cost_usd": 0.0001,
            "metering_status": "reported",
            "probe_status": "passed",
        }

    def _prepare(self, directory: Path) -> tuple[Path, str]:
        prepared = directory / "prepared"
        result = prepare_stage0(
            repository_root=ROOT,
            config_path=CONFIG,
            output_dir=prepared,
        )
        self.assertEqual(result["provider_calls"], 0)
        manifest = json.loads(
            (prepared / STAGE0_PREPARED_MANIFEST).read_text(encoding="utf-8")
        )
        baseline = json.loads(
            (prepared / manifest["paths"]["baseline_selection"]).read_text(
                encoding="utf-8"
            )
        )
        return prepared, baseline["selected_candidate_ids"][0]

    def test_configuration_is_exact_and_bounded(self) -> None:
        plan = load_stage0_plan(ROOT, CONFIG)
        self.assertEqual(
            [item.model for item in plan.models],
            [
                "deepseek/deepseek-v4-flash-0731",
                "openai/gpt-oss-120b",
                "inception/mercury-2",
            ],
        )
        self.assertEqual(
            [item.allowed_actual_provider for item in plan.models],
            ["DeepSeek", "DeepInfra", "Inception"],
        )
        self.assertEqual(plan.case_key, "historical-degraded-sparse")
        self.assertEqual(plan.expected_candidate_count, 201)
        self.assertEqual(plan.maximum_route_probes, 3)
        self.assertEqual(plan.maximum_selector_generations, 3)
        self.assertEqual(plan.maximum_paid_calls, 6)
        self.assertEqual(plan.maximum_semantic_repairs, 0)
        self.assertEqual(plan.maximum_network_retries, 0)
        self.assertAlmostEqual(plan.maximum_total_cost_usd, 0.06)

    def test_prepare_uses_real_compact_201_candidate_request_without_calls(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            prepared, _ = self._prepare(Path(temporary))
            manifest = json.loads(
                (prepared / STAGE0_PREPARED_MANIFEST).read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["case_key"], "historical-degraded-sparse")
            self.assertEqual(manifest["candidate_count"], 201)
            self.assertLessEqual(manifest["compact_request_bytes"], 65_536)
            compact = json.loads(
                (prepared / manifest["paths"]["compact_request"]).read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(len(compact["candidates"]), 201)
            self.assertEqual(compact["canonical_request_id"], manifest["canonical_request_id"])

    def test_all_three_models_can_complete_one_strict_call_without_repairs(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prepared, selected_id = self._prepare(root)
            transport = _SelectorTransport(selected_id)
            summary = execute_stage0(
                repository_root=ROOT,
                config_path=CONFIG,
                prepared_dir=prepared,
                output_dir=root / "output",
                api_key="test-secret",
                trusted_main_sha="a" * 40,
                catalogue_loader=self._catalogue,
                route_probe=self._route_probe,
                transport_factory=lambda: transport,
            )
            self.assertEqual(summary["completed_route_probes"], 3)
            self.assertEqual(summary["completed_selector_generations"], 3)
            self.assertEqual(summary["completed_paid_calls"], 6)
            self.assertEqual(
                [row["classification"] for row in summary["models"]],
                ["compatible", "compatible", "compatible"],
            )
            self.assertFalse(summary["stage1_authorized"])
            self.assertFalse(summary["winner_selected"])
            self.assertEqual(summary["semantic_repairs"], 0)
            self.assertEqual(summary["network_retries"], 0)
            self.assertEqual(len(transport.calls), 3)
            for request in transport.calls:
                self.assertEqual(request["provider"]["allow_fallbacks"], False)
                self.assertEqual(request["provider"]["require_parameters"], True)
                self.assertEqual(request["provider"]["data_collection"], "deny")
                self.assertEqual(len(request["provider"]["only"]), 1)
                self.assertEqual(request["response_format"]["type"], "json_schema")
                self.assertEqual(request["response_format"]["json_schema"]["strict"], True)

    def test_invalid_model_output_is_terminal_and_never_repaired(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prepared, _ = self._prepare(root)
            unknown = "claim-candidate:sha256:" + "0" * 64
            transport = _SelectorTransport(unknown)
            summary = execute_stage0(
                repository_root=ROOT,
                config_path=CONFIG,
                prepared_dir=prepared,
                output_dir=root / "output",
                api_key="test-secret",
                catalogue_loader=self._catalogue,
                route_probe=self._route_probe,
                transport_factory=lambda: transport,
            )
            self.assertEqual(
                [row["classification"] for row in summary["models"]],
                ["model-output-invalid"] * 3,
            )
            self.assertEqual(summary["completed_selector_generations"], 3)
            self.assertEqual(summary["semantic_repairs"], 0)
            self.assertEqual(len(transport.calls), 3)

    def test_route_ineligible_models_never_receive_selector_calls(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prepared, selected_id = self._prepare(root)
            transport = _SelectorTransport(selected_id)

            def failed_route(config: Any, api_key: str, *, transport: Any = None) -> dict[str, Any]:
                del api_key, transport
                return {
                    "requested_model": config.model,
                    "actual_model": None,
                    "actual_provider": None,
                    "estimated_cost_usd": config.max_cost_usd,
                    "metering_status": "reserved-maximum",
                    "probe_status": "failed",
                    "failure_code": "ineligible_routing",
                    "message": "No endpoints found for the exact provider route",
                }

            summary = execute_stage0(
                repository_root=ROOT,
                config_path=CONFIG,
                prepared_dir=prepared,
                output_dir=root / "output",
                api_key="test-secret",
                catalogue_loader=self._catalogue,
                route_probe=failed_route,
                transport_factory=lambda: transport,
            )
            self.assertEqual(
                [row["classification"] for row in summary["models"]],
                ["route-ineligible"] * 3,
            )
            self.assertEqual(summary["completed_route_probes"], 3)
            self.assertEqual(summary["completed_selector_generations"], 0)
            self.assertEqual(summary["completed_paid_calls"], 3)
            self.assertEqual(transport.calls, [])


if __name__ == "__main__":
    unittest.main()
