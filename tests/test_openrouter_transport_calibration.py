from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any, Mapping

from llm_analysis.candidate_selector_stage0 import STAGE0_PREPARED_MANIFEST
from llm_analysis.openrouter_client import HttpResponse
from llm_analysis.openrouter_transport_calibration import (
    DEFAULT_CONFIG,
    execute_transport_calibration,
    load_calibration_plan,
    prepare_transport_calibration,
)

ROOT = Path(__file__).resolve().parents[1]


class _CalibrationTransport:
    def __init__(self, selected_id: str, modes: list[str] | None = None) -> None:
        self.selected_id = selected_id
        self.modes = list(modes or [])
        self.requests: list[dict[str, Any]] = []

    def post(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        body: bytes,
        timeout_seconds: float,
    ) -> HttpResponse:
        del url, timeout_seconds
        self.assert_metadata_header(headers)
        request = json.loads(body.decode("utf-8"))
        self.requests.append(request)
        mode = self.modes.pop(0) if self.modes else "success"
        model = request["model"]
        provider = {
            "inception/mercury-2": "Inception",
            "openai/gpt-oss-120b": "DeepInfra",
        }[model]
        if mode == "http-error":
            return HttpResponse(
                503,
                json.dumps(
                    {
                        "error": {
                            "code": 503,
                            "message": "provider warming up",
                            "metadata": {"error_type": "provider_unavailable"},
                        },
                        "openrouter_metadata": {
                            "attempt": 1,
                            "attempts": [{"provider": provider, "status": 503}],
                        },
                    }
                ).encode("utf-8"),
                {"Content-Type": "application/json", "X-Secret": "not-retained"},
            )
        content: str | None = json.dumps(
            {"selected_candidate_ids": [self.selected_id]}, separators=(",", ":")
        )
        finish_reason = "stop"
        message: dict[str, Any] = {"content": content}
        if mode == "empty-content":
            message = {
                "content": None,
                "reasoning": "bounded hidden reasoning",
                "reasoning_details": [{"type": "summary", "text": "thinking"}],
            }
            finish_reason = "length"
        payload = {
            "id": f"gen-{len(self.requests)}",
            "model": model,
            "choices": [
                {
                    "finish_reason": finish_reason,
                    "message": message,
                }
            ],
            "usage": {
                "prompt_tokens": 1000,
                "completion_tokens": 40,
                "total_tokens": 1040,
                "cost": 0.004,
                "completion_tokens_details": {"reasoning_tokens": 12},
            },
            "openrouter_metadata": {
                "attempt": 1,
                "summary": f"selected={provider}",
                "endpoints": {
                    "available": [
                        {
                            "provider": provider,
                            "model": model,
                            "selected": True,
                        }
                    ]
                },
                "attempts": [{"provider": provider, "model": model, "status": 200}],
            },
        }
        return HttpResponse(
            200,
            json.dumps(payload).encode("utf-8"),
            {"Content-Type": "application/json", "X-Request-Id": "req-test"},
        )

    @staticmethod
    def assert_metadata_header(headers: Mapping[str, str]) -> None:
        if headers.get("X-OpenRouter-Metadata") != "enabled":
            raise AssertionError("router metadata header was not enabled")


class OpenRouterTransportCalibrationTests(unittest.TestCase):
    def _prepare(self, directory: Path) -> tuple[Path, str]:
        prepared = directory / "prepared"
        result = prepare_transport_calibration(
            repository_root=ROOT,
            config_path=DEFAULT_CONFIG,
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

    def test_configuration_preserves_the_reviewed_small_experiment(self) -> None:
        plan = load_calibration_plan(ROOT, DEFAULT_CONFIG)
        self.assertEqual(plan.case_key, "historical-degraded-sparse")
        self.assertEqual(plan.expected_candidate_count, 201)
        self.assertEqual(plan.max_output_tokens, 2048)
        self.assertEqual(plan.reasoning_effort, "minimal")
        self.assertEqual(plan.maximum_discovery_calls, 2)
        self.assertEqual(plan.maximum_reproduction_calls, 1)
        self.assertEqual(plan.maximum_paid_calls, 3)
        self.assertEqual(plan.maximum_semantic_repairs, 0)
        self.assertEqual(plan.maximum_network_retries, 0)
        self.assertAlmostEqual(plan.maximum_call_cost_usd, 0.025)
        self.assertAlmostEqual(plan.maximum_total_cost_usd, 0.060)
        self.assertEqual(
            [item.model for item in plan.models],
            ["inception/mercury-2", "openai/gpt-oss-120b"],
        )

    def test_prepare_reuses_the_real_201_candidate_compact_request(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            prepared, _ = self._prepare(Path(temporary))
            manifest = json.loads(
                (prepared / STAGE0_PREPARED_MANIFEST).read_text(encoding="utf-8")
            )
            self.assertEqual(manifest["candidate_count"], 201)
            self.assertEqual(manifest["case_key"], "historical-degraded-sparse")
            self.assertLessEqual(manifest["compact_request_bytes"], 65_536)

    def test_mercury_discovery_and_pinned_reproduction_answer_yes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prepared, selected_id = self._prepare(root)
            transport = _CalibrationTransport(selected_id)
            output = root / "output"
            summary = execute_transport_calibration(
                repository_root=ROOT,
                config_path=DEFAULT_CONFIG,
                prepared_dir=prepared,
                output_dir=output,
                api_key="test-secret",
                trusted_main_sha="a" * 40,
                transport_factory=lambda: transport,
            )
            self.assertTrue(summary["decision_question_answered"])
            self.assertEqual(summary["operable_route"]["model"], "inception/mercury-2")
            self.assertEqual(summary["operable_route"]["provider_slug"], "inception")
            self.assertEqual(summary["completed_paid_calls"], 2)
            self.assertEqual(summary["completed_discovery_calls"], 1)
            self.assertEqual(summary["completed_reproduction_calls"], 1)
            self.assertAlmostEqual(summary["observed_total_cost_usd"], 0.008)
            self.assertEqual(len(transport.requests), 2)

            discovery, reproduction = transport.requests
            self.assertNotIn("only", discovery["provider"])
            self.assertTrue(discovery["provider"]["allow_fallbacks"])
            self.assertEqual(discovery["provider"]["order"], ["inception"])
            self.assertEqual(reproduction["provider"]["only"], ["inception"])
            self.assertFalse(reproduction["provider"]["allow_fallbacks"])
            for request in transport.requests:
                self.assertEqual(request["max_tokens"], 2048)
                self.assertEqual(
                    request["reasoning"], {"effort": "minimal", "exclude": True}
                )
                self.assertEqual(request["response_format"]["type"], "json_schema")
                self.assertTrue(request["response_format"]["json_schema"]["strict"])
                self.assertTrue(request["provider"]["require_parameters"])
                self.assertEqual(request["provider"]["data_collection"], "deny")

            raw = json.loads(
                (
                    output
                    / "models/mercury-2/discovery/http-response.json"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(raw["http_status"], 200)
            self.assertIn("raw_body_utf8", raw)
            self.assertIn("raw_body_sha256", raw)
            self.assertEqual(raw["response_headers"], {"content-type": "application/json", "x-request-id": "req-test"})

    def test_failed_mercury_discovery_allows_gpt_discovery_and_reproduction(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prepared, selected_id = self._prepare(root)
            transport = _CalibrationTransport(
                selected_id,
                modes=["http-error", "success", "success"],
            )
            summary = execute_transport_calibration(
                repository_root=ROOT,
                config_path=DEFAULT_CONFIG,
                prepared_dir=prepared,
                output_dir=root / "output",
                api_key="test-secret",
                transport_factory=lambda: transport,
            )
            self.assertTrue(summary["decision_question_answered"])
            self.assertEqual(summary["operable_route"]["model"], "openai/gpt-oss-120b")
            self.assertEqual(summary["operable_route"]["provider_slug"], "deepinfra")
            self.assertEqual(summary["completed_paid_calls"], 3)
            self.assertEqual(
                [row["classification"] for row in summary["calls"]],
                ["http-error", "completed", "completed"],
            )
            self.assertAlmostEqual(summary["observed_total_cost_usd"], 0.033)

    def test_empty_content_retains_reasoning_and_does_not_hide_the_response(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prepared, selected_id = self._prepare(root)
            transport = _CalibrationTransport(
                selected_id,
                modes=["empty-content", "success", "success"],
            )
            output = root / "output"
            summary = execute_transport_calibration(
                repository_root=ROOT,
                config_path=DEFAULT_CONFIG,
                prepared_dir=prepared,
                output_dir=output,
                api_key="test-secret",
                transport_factory=lambda: transport,
            )
            self.assertEqual(summary["calls"][0]["classification"], "empty-content")
            interpreted = json.loads(
                (
                    output
                    / "models/mercury-2/discovery/interpreted-response.json"
                ).read_text(encoding="utf-8")
            )
            self.assertFalse(interpreted["content_present"])
            self.assertEqual(interpreted["finish_reason"], "length")
            self.assertEqual(interpreted["reasoning"], "bounded hidden reasoning")
            self.assertEqual(interpreted["usage"]["cost"], 0.004)
            self.assertTrue(summary["decision_question_answered"])


if __name__ == "__main__":
    unittest.main()
