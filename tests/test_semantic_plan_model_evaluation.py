from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import yaml

from llm_analysis.evaluation import EvaluationConfigurationError
from llm_analysis.semantic_plan_model_evaluation import (
    CaseExpectation,
    _BodyTransformTransport,
    _jaccard,
    evaluate_expectation,
    load_selection_plan,
)


class _CaptureTransport:
    def __init__(self) -> None:
        self.body: bytes | None = None

    def post(self, url, *, headers, body, timeout_seconds):
        self.body = body
        return {"url": url, "timeout_seconds": timeout_seconds}


class SemanticPlanModelEvaluationTests(unittest.TestCase):
    def _config(self) -> dict:
        return {
            "version": 1,
            "base_profile": "config/llm-public-data-semantic-plan.yml",
            "viability_config": "config/llm-evaluation-viability.yml",
            "expectations_path": "evaluation/semantic-plan-model-selection/expectations.yml",
            "maximum_substantive_generations": 50,
            "maximum_total_cost_usd": 2.5,
            "candidates": [
                {
                    "key": "gpt-5-6-sol",
                    "model": "openai/gpt-5.6-sol",
                    "role": "quality_benchmark",
                    "deployment_eligible": False,
                    "repeats_per_case": 2,
                    "availability_checked_at": "2026-07-13",
                    "known_expiration_date": None,
                    "maximum_prompt_price_per_million": 6.0,
                    "maximum_completion_price_per_million": 36.0,
                    "maximum_generation_cost_usd": 0.1,
                    "maximum_model_cost_usd": 1.1,
                    "send_temperature": False,
                },
                {
                    "key": "nex-n2-mini",
                    "model": "nex-agi/nex-n2-mini",
                    "role": "primary_candidate",
                    "deployment_eligible": True,
                    "repeats_per_case": 4,
                    "availability_checked_at": "2026-07-13",
                    "known_expiration_date": None,
                    "maximum_prompt_price_per_million": 0.05,
                    "maximum_completion_price_per_million": 0.2,
                    "maximum_generation_cost_usd": 0.01,
                    "maximum_model_cost_usd": 0.21,
                    "send_temperature": True,
                },
                {
                    "key": "minimax-m3",
                    "model": "minimax/minimax-m3",
                    "role": "consistency_candidate",
                    "deployment_eligible": True,
                    "repeats_per_case": 4,
                    "availability_checked_at": "2026-07-13",
                    "known_expiration_date": None,
                    "maximum_prompt_price_per_million": 0.5,
                    "maximum_completion_price_per_million": 2.0,
                    "maximum_generation_cost_usd": 0.02,
                    "maximum_model_cost_usd": 0.42,
                    "send_temperature": True,
                },
            ],
            "excluded_models": [
                {
                    "model": "cohere/north-mini-code:free",
                    "reason": "Structured output is not advertised.",
                    "generation_allowed": False,
                }
            ],
        }

    def _write_config(self, root: Path, value: dict) -> Path:
        path = root / "selection.yml"
        path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")
        return path

    def test_loads_bounded_three_model_plan(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_config(root, self._config())
            plan = load_selection_plan(root, "selection.yml")
        self.assertEqual(plan.maximum_substantive_generations, 50)
        self.assertEqual([item.repeats_per_case for item in plan.candidates], [2, 4, 4])
        self.assertFalse(plan.candidates[0].deployment_eligible)
        self.assertEqual(plan.maximum_total_cost_usd, 2.5)

    def test_rejects_generation_count_drift(self) -> None:
        config = self._config()
        config["maximum_substantive_generations"] = 49
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._write_config(root, config)
            with self.assertRaisesRegex(EvaluationConfigurationError, "imply 50 generations"):
                load_selection_plan(root, "selection.yml")

    def test_case_expectation_requires_material_move_and_source_comparison(self) -> None:
        expectation = CaseExpectation(
            case_key="case",
            required_evidence_ids=("sol.change_24h",),
            forbidden_evidence_ids=("source.untrusted.note",),
            forbidden_data_quality_evidence_ids=("snapshot.generated_at",),
            required_source_disagreement_ids=("btc.source_a.price", "btc.source_b.price"),
            discouraged_evidence_ids=("sol.change_1h",),
            maximum_claims=5,
        )
        plan = {
            "sections": [
                {
                    "claims": [
                        {
                            "intent": "directional_observation",
                            "evidence_ids": ["sol.change_24h"],
                            "comparison_relation": "none",
                        },
                        {
                            "intent": "comparison",
                            "evidence_ids": ["btc.source_b.price", "btc.source_a.price"],
                            "comparison_relation": "greater_than",
                        },
                    ]
                }
            ]
        }
        result = evaluate_expectation(plan, expectation)
        self.assertTrue(result.hard_pass)
        self.assertEqual(result.semantic_coverage, 1.0)
        self.assertEqual(result.materiality, 1.0)
        self.assertEqual(result.restraint, 1.0)

    def test_trivial_movement_is_quality_deduction_not_hard_failure(self) -> None:
        expectation = CaseExpectation(
            case_key="case",
            required_evidence_ids=("sol.change_24h",),
            forbidden_evidence_ids=(),
            forbidden_data_quality_evidence_ids=(),
            required_source_disagreement_ids=(),
            discouraged_evidence_ids=("sol.change_1h",),
            maximum_claims=5,
        )
        plan = {
            "sections": [
                {
                    "claims": [
                        {"intent": "directional_observation", "evidence_ids": ["sol.change_24h"], "comparison_relation": "none"},
                        {"intent": "directional_observation", "evidence_ids": ["sol.change_1h"], "comparison_relation": "none"},
                    ]
                }
            ]
        }
        result = evaluate_expectation(plan, expectation)
        self.assertTrue(result.hard_pass)
        self.assertEqual(result.materiality, 0.0)

    def test_timestamp_cannot_support_data_quality_limitation(self) -> None:
        expectation = CaseExpectation(
            case_key="case",
            required_evidence_ids=(),
            forbidden_evidence_ids=(),
            forbidden_data_quality_evidence_ids=("snapshot.generated_at",),
            required_source_disagreement_ids=(),
            discouraged_evidence_ids=(),
            maximum_claims=5,
        )
        plan = {
            "sections": [
                {
                    "claims": [
                        {
                            "intent": "data_quality_limitation",
                            "evidence_ids": ["snapshot.generated_at"],
                            "comparison_relation": "none",
                        }
                    ]
                }
            ]
        }
        result = evaluate_expectation(plan, expectation)
        self.assertFalse(result.hard_pass)
        self.assertIn("unsupported_quality_selection:snapshot.generated_at", result.diagnostics)

    def test_standalone_prices_duplicate_a_comparison_as_soft_redundancy(self) -> None:
        expectation = CaseExpectation(
            case_key="case",
            required_evidence_ids=(),
            forbidden_evidence_ids=(),
            forbidden_data_quality_evidence_ids=(),
            required_source_disagreement_ids=("btc.a", "btc.b"),
            discouraged_evidence_ids=(),
            maximum_claims=10,
        )
        plan = {
            "sections": [
                {
                    "claims": [
                        {"intent": "comparison", "evidence_ids": ["btc.a", "btc.b"], "comparison_relation": "not_equal"},
                        {"intent": "absolute_observation", "evidence_ids": ["btc.a"], "comparison_relation": "none"},
                        {"intent": "absolute_observation", "evidence_ids": ["btc.b"], "comparison_relation": "none"},
                    ]
                }
            ]
        }
        result = evaluate_expectation(plan, expectation)
        self.assertTrue(result.hard_pass)
        self.assertEqual(result.redundant_claim_count, 2)
        self.assertAlmostEqual(result.restraint, 0.8)

    def test_request_transform_omits_temperature_only_when_configured(self) -> None:
        inner = _CaptureTransport()
        transport = _BodyTransformTransport(inner, send_temperature=False)
        transport.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={},
            body=json.dumps({"model": "openai/gpt-5.6-sol", "temperature": 0.2, "max_tokens": 10}).encode(),
            timeout_seconds=60,
        )
        self.assertIsNotNone(inner.body)
        payload = json.loads(inner.body.decode())
        self.assertNotIn("temperature", payload)
        self.assertEqual(payload["max_tokens"], 10)

    def test_jaccard_stability(self) -> None:
        self.assertEqual(_jaccard({"a", "b"}, {"a", "b"}), 1.0)
        self.assertEqual(_jaccard(set(), set()), 1.0)
        self.assertAlmostEqual(_jaccard({"a", "b"}, {"b", "c"}), 1 / 3)


if __name__ == "__main__":
    unittest.main()
