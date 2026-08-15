from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any, Mapping

from llm_analysis import gpt_oss_quality_comparison as core
from llm_analysis.gpt_oss_quality_comparison import PREPARED_MANIFEST
from llm_analysis.gpt_oss_quality_comparison_config import DEFAULT_CONFIG
from llm_analysis.gpt_oss_quality_comparison_runner import (
    execute_gpt_oss_quality_comparison,
    prepare_gpt_oss_quality_comparison,
)
from llm_analysis.openrouter_client import HttpResponse

ROOT = Path(__file__).resolve().parents[1]


def catalogue() -> dict[str, Any]:
    return {
        "data": [
            {
                "id": "openai/gpt-oss-120b",
                "supported_parameters": ["response_format", "structured_outputs"],
                "pricing": {
                    "prompt": "0.00000005",
                    "completion": "0.00000025",
                },
                "context_length": 131072,
                "top_provider": {"max_completion_tokens": 8192},
            }
        ]
    }


class ScalarMetadataTransport:
    def __init__(self, selections: list[list[str]]) -> None:
        self.selections = list(selections)
        self.calls = 0
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
        self.calls += 1
        if headers.get("X-OpenRouter-Metadata") != "enabled":
            raise AssertionError("router metadata must be enabled")
        request = json.loads(body.decode("utf-8"))
        self.requests.append(request)
        content = json.dumps(
            {"selected_candidate_ids": self.selections[self.calls - 1]},
            separators=(",", ":"),
        )
        payload = {
            "id": f"gen-{self.calls}",
            "model": "openai/gpt-oss-120b",
            "choices": [
                {"finish_reason": "stop", "message": {"content": content}}
            ],
            "usage": {
                "prompt_tokens": 1433,
                "completion_tokens": 34,
                "total_tokens": 1467,
                "cost": 0.000319,
                "completion_tokens_details": {"reasoning_tokens": 32},
            },
            "openrouter_metadata": {
                "attempt": 1,
                "strategy": "direct",
                "endpoints": {
                    "available": [
                        {"provider": "DeepInfra", "selected": True}
                    ]
                },
            },
        }
        return HttpResponse(
            200,
            json.dumps(payload).encode(),
            {"Content-Type": "application/json", "X-Request-Id": f"req-{self.calls}"},
        )


class RouterEvidenceTests(unittest.TestCase):
    def test_scalar_attempt_matches_retained_run_shape(self) -> None:
        evidence = core._router_evidence(
            {
                "attempt": 1,
                "strategy": "direct",
                "endpoints": {
                    "available": [
                        {"provider": "DeepInfra", "selected": True}
                    ]
                },
            },
            required_provider_slug="deepinfra",
        )
        self.assertFalse(evidence["attempts_present"])
        self.assertEqual(evidence["router_attempt_count"], 1)
        self.assertTrue(evidence["exact_one_attempt"])
        self.assertEqual(evidence["actual_provider"], "DeepInfra")
        self.assertEqual(evidence["provider_slug"], "deepinfra")
        self.assertFalse(evidence["provider_ambiguous"])
        self.assertFalse(evidence["provider_fallback_used"])

    def test_existing_single_attempt_array_remains_valid(self) -> None:
        evidence = core._router_evidence(
            {
                "attempt": 1,
                "endpoints": {
                    "available": [
                        {"provider": "DeepInfra", "selected": True}
                    ]
                },
                "attempts": [
                    {"provider": "DeepInfra", "status": 200}
                ],
            },
            required_provider_slug="deepinfra",
        )
        self.assertTrue(evidence["attempts_present"])
        self.assertTrue(evidence["exact_one_attempt"])
        self.assertTrue(evidence["explicit_attempt_valid"])
        self.assertFalse(evidence["provider_fallback_used"])

    def test_scalar_second_attempt_fails_closed(self) -> None:
        evidence = core._router_evidence(
            {
                "attempt": 2,
                "endpoints": {
                    "available": [
                        {"provider": "DeepInfra", "selected": True}
                    ]
                },
            },
            required_provider_slug="deepinfra",
        )
        self.assertEqual(evidence["router_attempt_count"], 2)
        self.assertFalse(evidence["exact_one_attempt"])
        self.assertTrue(evidence["provider_fallback_used"])

    def test_conflicting_scalar_and_attempt_array_fail_closed(self) -> None:
        evidence = core._router_evidence(
            {
                "attempt": 2,
                "endpoints": {
                    "available": [
                        {"provider": "DeepInfra", "selected": True}
                    ]
                },
                "attempts": [
                    {"provider": "DeepInfra", "status": 200}
                ],
            },
            required_provider_slug="deepinfra",
        )
        self.assertFalse(evidence["exact_one_attempt"])
        self.assertTrue(evidence["provider_fallback_used"])

    def test_explicit_empty_attempt_array_conflicts_with_scalar_attempt(self) -> None:
        evidence = core._router_evidence(
            {
                "attempt": 1,
                "endpoints": {
                    "available": [
                        {"provider": "DeepInfra", "selected": True}
                    ]
                },
                "attempts": [],
            },
            required_provider_slug="deepinfra",
        )
        self.assertTrue(evidence["attempts_present"])
        self.assertFalse(evidence["exact_one_attempt"])
        self.assertTrue(evidence["provider_fallback_used"])

    def test_multiple_selected_endpoints_are_ambiguous(self) -> None:
        evidence = core._router_evidence(
            {
                "attempt": 1,
                "endpoints": {
                    "available": [
                        {"provider": "DeepInfra", "selected": True},
                        {"provider": "OtherProvider", "selected": True},
                    ]
                },
            },
            required_provider_slug="deepinfra",
        )
        self.assertTrue(evidence["exact_one_attempt"])
        self.assertTrue(evidence["provider_ambiguous"])
        self.assertIsNone(evidence["actual_provider"])
        self.assertIsNone(evidence["provider_slug"])

    def test_failed_explicit_attempt_remains_invalid(self) -> None:
        evidence = core._router_evidence(
            {
                "attempt": 1,
                "endpoints": {
                    "available": [
                        {"provider": "DeepInfra", "selected": True}
                    ]
                },
                "attempts": [
                    {"provider": "DeepInfra", "status": 500}
                ],
            },
            required_provider_slug="deepinfra",
        )
        self.assertTrue(evidence["exact_one_attempt"])
        self.assertFalse(evidence["explicit_attempt_valid"])

    def test_scalar_metadata_executes_without_manufacturing_attempt_array(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prepared = root / "prepared"
            prepare_gpt_oss_quality_comparison(
                repository_root=ROOT,
                config_path=DEFAULT_CONFIG,
                output_dir=prepared,
            )
            manifest = json.loads((prepared / PREPARED_MANIFEST).read_text())
            cases = {row["key"]: row for row in manifest["cases"]}
            selections = [
                list(cases[item["case_key"]]["baseline_selected_candidate_ids"])
                for item in manifest["planned_schedule"]
            ]
            transport = ScalarMetadataTransport(selections)
            output = root / "output"
            summary = execute_gpt_oss_quality_comparison(
                repository_root=ROOT,
                config_path=DEFAULT_CONFIG,
                prepared_dir=prepared,
                output_dir=output,
                api_key="test-secret",
                trusted_main_sha="a" * 40,
                catalogue_loader=catalogue,
                transport_factory=lambda: transport,
            )

            self.assertEqual(transport.calls, 15)
            self.assertEqual(summary["completed_paid_calls"], 15)
            self.assertEqual(summary["status"], "complete-adjudicable")
            first = json.loads(
                (
                    output
                    / "runs/repeat-1/historical-degraded-sparse/interpreted-response.json"
                ).read_text()
            )
            self.assertEqual(first["router_attempt_count"], 1)
            self.assertFalse(first["provider_fallback_used"])
            self.assertEqual(first["actual_provider"], "DeepInfra")
            self.assertNotIn("attempts", first["openrouter_metadata"])

            for request in transport.requests:
                self.assertEqual(request["model"], "openai/gpt-oss-120b")
                self.assertEqual(request["provider"]["only"], ["deepinfra"])
                self.assertFalse(request["provider"]["allow_fallbacks"])


if __name__ == "__main__":
    unittest.main()
