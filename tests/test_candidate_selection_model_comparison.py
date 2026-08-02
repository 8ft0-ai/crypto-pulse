from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from llm_analysis.candidate_selection_model_comparison import (
    PREPARED_MANIFEST,
    prepare_candidate_selection_comparison,
)
from llm_analysis.candidate_selection_model_comparison_config import (
    load_candidate_selection_comparison_plan,
)
from llm_analysis.candidate_selection_model_scoring import (
    apply_predeclared_decision,
    score_selection,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG = "config/candidate-selection-model-comparison.yml"


class CandidateSelectionModelComparisonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = load_candidate_selection_comparison_plan(ROOT, CONFIG)

    def test_configuration_is_the_exact_reviewed_two_model_plan(self) -> None:
        plan = self.plan
        self.assertEqual(plan.maximum_logical_runs, 30)
        self.assertEqual(plan.maximum_substantive_generations, 60)
        self.assertEqual(plan.maximum_route_probes, 2)
        self.assertEqual(plan.maximum_semantic_repairs_per_run, 1)
        self.assertEqual(plan.maximum_total_cost_usd, 4.0)
        self.assertEqual(
            [(item.role, item.model, item.allowed_actual_provider) for item in plan.models],
            [
                ("quality_benchmark", "openai/gpt-5.6-sol", "OpenAI"),
                ("deployment_candidate", "nex-agi/nex-n2-mini", "Nex AGI"),
            ],
        )
        self.assertTrue(all(item.repeats_per_case == 3 for item in plan.models))
        self.assertFalse(plan.quality_model.deployment_eligible)
        self.assertTrue(plan.deployment_model.deployment_eligible)
        self.assertEqual(
            plan.outcomes,
            {
                "quality_benchmark_failed": "remove-model-selector-from-active-roadmap",
                "deployment_candidate_failed": "research-only-no-deployment-selector",
                "both_passed": "retain-bounded-selector-candidate",
                "infrastructure_failure": "inconclusive-infrastructure",
            },
        )

    def test_secret_free_prepare_regenerates_the_reviewed_baseline(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            result = prepare_candidate_selection_comparison(
                repository_root=ROOT,
                config_path=CONFIG,
                output_dir=temporary,
            )
            manifest = json.loads(
                (Path(temporary) / PREPARED_MANIFEST).read_text(encoding="utf-8")
            )
        self.assertEqual(result["provider_calls"], 0)
        self.assertEqual(result["case_count"], 5)
        self.assertEqual(result["baseline"]["selected_count"], 35)
        self.assertEqual(result["baseline"]["selected_useful_count"], 26)
        self.assertEqual(result["baseline"]["gold_useful_count"], 38)
        self.assertEqual(len(manifest["cases"]), 5)
        self.assertEqual(manifest["limits"]["maximum_logical_runs"], 30)
        self.assertEqual(manifest["limits"]["maximum_substantive_generations"], 60)
        for case in manifest["cases"]:
            self.assertGreater(case["candidate_count"], 0)
            self.assertTrue(case["useful_candidate_ids"])
            self.assertEqual(case["prohibited_candidate_ids"], [])
            self.assertEqual(len(case["baseline_selected_candidate_ids"]), 7)

    def test_fallback_receives_no_model_quality_credit(self) -> None:
        score = score_selection([], ["candidate-a", "candidate-b"])
        self.assertEqual(score["selected_count"], 0)
        self.assertEqual(score["useful_selected_count"], 0)
        self.assertEqual(score["precision"], 0.0)
        self.assertEqual(score["recall"], 0.0)
        self.assertEqual(score["f1"], 0.0)

    def test_predeclared_decision_stops_when_quality_upper_bound_fails(self) -> None:
        summaries = [
            {
                "role": "quality_benchmark",
                "completed_runs": 15,
                "expected_runs": 15,
                "accepted_runs": 13,
                "prohibited_selected_count": 0,
                "precision": 0.90,
                "recall": 0.90,
                "f1": 0.90,
                "mean_pairwise_jaccard": 0.90,
                "governance_pass": True,
                "route_pass": True,
                "availability_pass": True,
            },
            {
                "role": "deployment_candidate",
                "completed_runs": 15,
                "expected_runs": 15,
                "accepted_runs": 15,
                "prohibited_selected_count": 0,
                "precision": 0.90,
                "recall": 0.90,
                "f1": 0.90,
                "mean_pairwise_jaccard": 0.90,
                "logical_latency_ms": {"p95": 1000},
                "mean_cost_per_accepted_selection_usd": 0.001,
                "governance_pass": True,
                "route_pass": True,
                "availability_pass": True,
            },
        ]
        decision = apply_predeclared_decision(self.plan, summaries)
        self.assertEqual(
            decision["outcome"], "remove-model-selector-from-active-roadmap"
        )
        self.assertFalse(decision["quality_gate"]["minimum_accepted_runs"])
        self.assertEqual(decision["deployment_gate"], {})

    def test_incomplete_corpus_is_infrastructure_not_model_quality(self) -> None:
        decision = apply_predeclared_decision(
            self.plan,
            [
                {
                    "role": "quality_benchmark",
                    "completed_runs": 0,
                    "expected_runs": 15,
                    "route_pass": False,
                    "availability_pass": True,
                },
                {
                    "role": "deployment_candidate",
                    "completed_runs": 0,
                    "expected_runs": 15,
                    "route_pass": False,
                    "availability_pass": True,
                },
            ],
        )
        self.assertEqual(decision["outcome"], "inconclusive-infrastructure")
        self.assertEqual(decision["status"], "inconclusive")


if __name__ == "__main__":
    unittest.main()
