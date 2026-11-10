from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from llm_analysis.candidate_selection_model_comparison import (
    PREPARED_MANIFEST,
    _model_runtime,
    prepare_candidate_selection_comparison,
)
from llm_analysis.candidate_selection_model_comparison_config import (
    load_candidate_selection_comparison_plan,
)
from llm_analysis.candidate_selection_model_scoring import (
    apply_predeclared_decision,
    score_selection,
)
from llm_analysis.candidate_selector_compact_projection import (
    MAX_COMPACT_REQUEST_BYTES,
    build_compact_candidate_selector_request,
)
from llm_analysis.contracts import canonical_json_bytes
from llm_analysis.semantic_plan_benchmark import (
    _validate_profile_chain,
    load_semantic_plan_profile,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG = "config/candidate-selection-model-comparison.yml"


class CandidateSelectionModelComparisonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = load_candidate_selection_comparison_plan(ROOT, CONFIG)

    def test_configuration_is_the_exact_corrective_two_model_plan(self) -> None:
        plan = self.plan
        self.assertEqual(plan.maximum_logical_runs, 30)
        self.assertEqual(plan.maximum_substantive_generations, 60)
        self.assertEqual(plan.maximum_route_probes, 2)
        self.assertEqual(plan.maximum_semantic_repairs_per_run, 1)
        self.assertEqual(plan.maximum_fallbacks_before_decisive_failure, 2)
        self.assertEqual(plan.maximum_total_cost_usd, 5.0)
        self.assertEqual(
            [
                (
                    item.role,
                    item.model,
                    item.allowed_actual_provider,
                    item.maximum_generation_cost_usd,
                    item.maximum_model_cost_usd,
                    item.max_output_tokens,
                )
                for item in plan.models
            ],
            [
                (
                    "quality_benchmark",
                    "openai/gpt-5.6-sol",
                    "OpenAI",
                    0.15,
                    4.51,
                    1024,
                ),
                (
                    "deployment_candidate",
                    "nex-agi/nex-n2-mini",
                    "Nex AGI",
                    0.01,
                    0.31,
                    512,
                ),
            ],
        )
        self.assertTrue(all(item.repeats_per_case == 3 for item in plan.models))
        self.assertFalse(plan.quality_model.deployment_eligible)
        self.assertTrue(plan.deployment_model.deployment_eligible)

    def test_prepare_regenerates_baseline_and_compact_requests_fit(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = prepare_candidate_selection_comparison(
                repository_root=ROOT,
                config_path=CONFIG,
                output_dir=root,
            )
            manifest = json.loads(
                (root / PREPARED_MANIFEST).read_text(encoding="utf-8")
            )
            compact_sizes: dict[str, int] = {}
            for case in manifest["cases"]:
                canonical = json.loads(
                    (root / case["paths"]["selector_request"]).read_text(
                        encoding="utf-8"
                    )
                )
                compact = build_compact_candidate_selector_request(canonical)
                compact_again = build_compact_candidate_selector_request(
                    {**canonical, "candidates": list(canonical["candidates"])}
                )
                self.assertEqual(compact, compact_again)
                self.assertEqual(
                    [row[0] for row in compact["candidates"]],
                    [row["candidate_id"] for row in canonical["candidates"]],
                )
                self.assertNotIn("evidence_ids", json.dumps(compact))
                size = len(canonical_json_bytes(compact))
                compact_sizes[case["key"]] = size
                self.assertLessEqual(size, MAX_COMPACT_REQUEST_BYTES)
        self.assertEqual(result["provider_calls"], 0)
        self.assertEqual(result["case_count"], 5)
        self.assertEqual(result["baseline"]["selected_count"], 35)
        self.assertEqual(result["baseline"]["selected_useful_count"], 26)
        self.assertEqual(result["baseline"]["gold_useful_count"], 38)
        self.assertEqual(len(compact_sizes), 5)
        self.assertEqual(manifest["limits"]["maximum_fallbacks_before_decisive_failure"], 2)

    def test_runtime_overlay_preserves_policy_and_model_specific_output_caps(self) -> None:
        profile = load_semantic_plan_profile(ROOT, self.plan.base_profile)
        public_profile, base_plan, _ = _validate_profile_chain(ROOT, profile)
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            for model in self.plan.models:
                _, runtime = _model_runtime(
                    ROOT,
                    output,
                    self.plan,
                    public_profile,
                    profile,
                    base_plan,
                    model,
                )
                self.assertEqual(runtime.model, model.model)
                self.assertEqual(runtime.provider_policy.only, (model.allowed_actual_provider,))
                self.assertEqual(runtime.provider_policy.data_collection, "deny")
                self.assertFalse(runtime.provider_policy.zdr)
                self.assertFalse(runtime.provider_policy.allow_fallbacks)
                self.assertFalse(runtime.cross_model_fallback)
                self.assertEqual(runtime.retry_limit, 0)
                self.assertEqual(runtime.max_output_tokens, model.max_output_tokens)
                self.assertEqual(runtime.max_request_bytes, 5_000_000)
                self.assertEqual(runtime.max_cost_usd, model.maximum_generation_cost_usd)
                self.assertEqual(
                    runtime.provider_policy.max_request_price,
                    model.maximum_generation_cost_usd,
                )

    def test_fallback_receives_no_model_quality_credit(self) -> None:
        score = score_selection([], ["candidate-a", "candidate-b"])
        self.assertEqual(score["selected_count"], 0)
        self.assertEqual(score["useful_selected_count"], 0)
        self.assertEqual(score["precision"], 0.0)
        self.assertEqual(score["recall"], 0.0)
        self.assertEqual(score["f1"], 0.0)

    def test_two_quality_fallbacks_are_a_decisive_model_failure(self) -> None:
        decision = apply_predeclared_decision(
            self.plan,
            [
                {
                    "role": "quality_benchmark",
                    "completed_runs": 2,
                    "expected_runs": 15,
                    "decisive_acceptance_failure": True,
                    "observed_governance_pass": True,
                },
                {
                    "role": "deployment_candidate",
                    "completed_runs": 0,
                    "expected_runs": 15,
                    "route_pass": False,
                    "availability_pass": False,
                },
            ],
        )
        self.assertEqual(
            decision["outcome"], "remove-model-selector-from-active-roadmap"
        )
        self.assertTrue(decision["quality_gate"]["decisive_two_fallback_stop"])
        self.assertEqual(decision["deployment_gate"], {})

    def test_two_deployment_fallbacks_are_a_decisive_candidate_failure(self) -> None:
        quality = {
            "role": "quality_benchmark",
            "completed_runs": 15,
            "expected_runs": 15,
            "accepted_runs": 15,
            "prohibited_selected_count": 0,
            "precision": 0.90,
            "recall": 0.90,
            "f1": 0.90,
            "mean_pairwise_jaccard": 0.90,
            "governance_pass": True,
            "route_pass": True,
            "availability_pass": True,
            "cost_metadata_complete": True,
        }
        deployment = {
            "role": "deployment_candidate",
            "completed_runs": 2,
            "expected_runs": 15,
            "decisive_acceptance_failure": True,
            "observed_governance_pass": True,
        }
        decision = apply_predeclared_decision(self.plan, [quality, deployment])
        self.assertEqual(
            decision["outcome"], "research-only-no-deployment-selector"
        )
        self.assertTrue(
            decision["deployment_gate"]["decisive_two_fallback_stop"]
        )

    def test_infrastructure_failure_remains_inconclusive(self) -> None:
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
