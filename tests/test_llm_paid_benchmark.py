from __future__ import annotations

import json
import unittest
from pathlib import Path

from llm_analysis.evaluation import RunRecord, load_evaluation_plan
from llm_analysis.generation_config import load_generation_config
from llm_analysis.openrouter_client import CostLimitError, HttpResponse
from llm_analysis.paid_benchmark import (
    _apply_cost_guard,
    _paid_quota_summary,
    check_paid_model_availability,
    load_paid_benchmark_plan,
    paid_route_probe,
)

ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = "config/llm-evaluation-gpt-4o-mini.yml"


class FakeTransport:
    def __init__(self, cost: float) -> None:
        self.cost = cost

    def post(self, *_: object, **__: object) -> HttpResponse:
        payload = {
            "id": "gen-route",
            "model": "openai/gpt-4o-mini",
            "choices": [{"message": {"content": json.dumps({"ok": True})}}],
            "usage": {"cost": self.cost},
            "openrouter_metadata": {"attempts": [{"status": 200, "provider": "OpenAI"}]},
        }
        return HttpResponse(200, json.dumps(payload).encode("utf-8"), {})


def catalogue(*, prompt: str = "0.00000015", completion: str = "0.0000006", parameters: list[str] | None = None) -> dict:
    return {
        "data": [
            {
                "id": "openai/gpt-4o-mini",
                "pricing": {"prompt": prompt, "completion": completion},
                "supported_parameters": parameters or ["response_format", "structured_outputs", "tools"],
                "context_length": 128000,
                "top_provider": {"max_completion_tokens": 16384},
                "expiration_date": None,
            }
        ]
    }


def record(*, cost: float | None, hard_pass: bool = True, repeat: int = 1) -> RunRecord:
    return RunRecord(
        "gpt-4o-mini",
        "openai/gpt-4o-mini",
        "case",
        repeat,
        "accepted" if hard_pass else "failed",
        hard_pass,
        None if hard_pass else "failure",
        {"valid": hard_pass, "diagnostics": []},
        "openai/gpt-4o-mini",
        "OpenAI",
        False,
        False,
        10,
        100,
        100,
        200,
        cost,
        "generation",
        "a" * 64 if hard_pass else None,
        "b" * 64,
        5.0 if hard_pass else None,
        5.0 if hard_pass else None,
        6 if hard_pass else None,
        8 if hard_pass else None,
        "runs/test",
    )


class PaidBenchmarkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = load_paid_benchmark_plan(ROOT, PLAN_PATH)

    def test_source_controlled_plan_is_single_model_and_bounded(self) -> None:
        self.assertEqual(self.plan.model.model, "openai/gpt-4o-mini")
        self.assertEqual(self.plan.model.role, "current_candidate")
        self.assertEqual(self.plan.maximum_prompt_price_per_million, 0.15)
        self.assertEqual(self.plan.maximum_completion_price_per_million, 0.60)
        self.assertEqual(self.plan.maximum_generation_cost_usd, 0.01)
        self.assertEqual(self.plan.maximum_experiment_cost_usd, 0.15)
        self.assertEqual(self.plan.maximum_logical_calls, 12)

    def test_historical_free_plan_semantics_remain_unchanged(self) -> None:
        historical = load_evaluation_plan(ROOT, "config/llm-evaluation.yml")
        self.assertEqual(historical.version, 1)
        self.assertGreaterEqual(len(historical.models), 2)
        self.assertTrue(all(model.model.endswith(":free") for model in historical.models))

    def test_catalogue_accepts_exact_prices_and_required_parameters(self) -> None:
        result = check_paid_model_availability(self.plan, catalogue_loader=catalogue)
        self.assertTrue(result.availability.eligible)
        self.assertEqual(result.prompt_price_per_million, 0.15)
        self.assertEqual(result.completion_price_per_million, 0.60)

    def test_catalogue_rejects_price_or_parameter_drift(self) -> None:
        expensive = check_paid_model_availability(self.plan, catalogue_loader=lambda: catalogue(completion="0.00000061"))
        self.assertFalse(expensive.availability.eligible)
        self.assertIn("exceeds approved cap", expensive.availability.reason or "")
        unsupported = check_paid_model_availability(self.plan, catalogue_loader=lambda: catalogue(parameters=["response_format"]))
        self.assertFalse(unsupported.availability.eligible)
        self.assertIn("structured_outputs", unsupported.availability.reason or "")

    def test_quota_below_experiment_ceiling_stops_the_run(self) -> None:
        summary = _paid_quota_summary({"limit_remaining": 0.149, "limit": 10}, self.plan)
        self.assertEqual(summary["request_budget_assessment"], "insufficient")
        self.assertEqual(summary["maximum_logical_calls"], 12)

    def test_route_probe_retains_cost_and_enforces_per_generation_limit(self) -> None:
        config = load_generation_config(ROOT / "config/llm-generation-gpt-4o-mini-benchmark.yml")
        result = paid_route_probe(config, "secret", transport=FakeTransport(0.001))
        self.assertEqual(result["actual_model"], "openai/gpt-4o-mini")
        self.assertEqual(result["actual_provider"], "OpenAI")
        self.assertEqual(result["estimated_cost_usd"], 0.001)
        with self.assertRaises(CostLimitError):
            paid_route_probe(config, "secret", transport=FakeTransport(0.011))

    def test_complete_cost_evidence_can_qualify_but_missing_cost_fails_closed(self) -> None:
        base_summary = {
            "model_results": [{"disqualified": False}],
            "decision": {"decision": "retain", "selected_model": "openai/gpt-4o-mini", "reason": "qualified"},
        }
        smoke = record(cost=0.001)
        records = [record(cost=0.001, repeat=index + 1) for index in range(10)]
        qualified = _apply_cost_guard(dict(base_summary), plan=self.plan, route_cost=0.001, smoke_record=smoke, records=records)
        self.assertEqual(qualified["decision"]["selected_model"], "openai/gpt-4o-mini")
        self.assertTrue(qualified["paid_benchmark"]["cost_metadata_complete_for_qualification"])
        self.assertLess(qualified["paid_benchmark"]["total_cost_usd"], 0.15)

        missing = [*records[:-1], record(cost=None, repeat=10)]
        failed = _apply_cost_guard(
            {"model_results": [{"disqualified": False}], "decision": {"decision": "retain", "selected_model": "openai/gpt-4o-mini", "reason": "qualified"}},
            plan=self.plan,
            route_cost=0.001,
            smoke_record=smoke,
            records=missing,
        )
        self.assertEqual(failed["decision"]["decision"], "no-go")
        self.assertTrue(failed["model_results"][0]["disqualified"])


if __name__ == "__main__":
    unittest.main()
