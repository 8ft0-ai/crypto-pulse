from __future__ import annotations

import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
DECISION = ROOT / "evaluation/phase-05/public-demo-decision.yml"
PUBLIC_PROFILE = ROOT / "config/llm-public-data-demo.yml"
DEFAULT_GENERATION = ROOT / "config/llm-generation.yml"
FREE_DECISION = ROOT / "evaluation/phase-05/free-proof-decision.yml"


class PublicDemoDecisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.decision = yaml.safe_load(DECISION.read_text(encoding="utf-8"))
        cls.profile = yaml.safe_load(PUBLIC_PROFILE.read_text(encoding="utf-8"))
        cls.default_generation = yaml.safe_load(
            DEFAULT_GENERATION.read_text(encoding="utf-8")
        )
        cls.free_decision = yaml.safe_load(FREE_DECISION.read_text(encoding="utf-8"))

    def test_decision_records_the_reviewed_diagnostic_run(self) -> None:
        self.assertEqual(self.decision["status"], "public-demo-no-go")
        self.assertEqual(self.decision["issue"], 210)
        self.assertEqual(self.decision["diagnostic_issue"], 224)
        self.assertEqual(self.decision["architecture_follow_up_issue"], 228)
        self.assertEqual(self.decision["source_run"]["run_id"], 29151358149)
        self.assertEqual(self.decision["source_run"]["evaluation_job_id"], 86541288102)
        self.assertEqual(
            self.decision["source_run"]["trusted_main_sha"],
            "96f1c680c700318b0ed1d26203d2cd0555f5f5ac",
        )
        self.assertEqual(
            self.decision["source_run"]["artifact"]["artifact_id"],
            8248289872,
        )
        self.assertEqual(
            self.decision["source_run"]["artifact"]["digest"],
            "sha256:9e8d6187c3ec701040cd2f2021002a5966cf0aec333f1b2a15f4d56bffa7c282",
        )

    def test_complete_bounded_corpus_and_cost_evidence_are_recorded(self) -> None:
        execution = self.decision["execution"]
        self.assertEqual(execution["maximum_logical_calls"], 12)
        self.assertEqual(execution["completed_logical_calls"], 12)
        self.assertEqual(execution["http_attempts"], 12)
        self.assertEqual(execution["route_preflight_passes"], 1)
        self.assertEqual(execution["corpus_runs_completed"], 10)
        self.assertEqual(execution["hard_passes"], 1)
        self.assertEqual(execution["required_hard_passes"], 10)
        self.assertEqual(execution["actual_provider_counts"], {"OpenAI": 10})
        self.assertEqual(execution["provider_fallback_runs"], 0)
        self.assertEqual(execution["cross_model_fallback_runs"], 0)
        self.assertAlmostEqual(execution["total_cost_usd"], 0.0185832)
        self.assertTrue(execution["cost_metadata_complete"])
        self.assertFalse(execution["cost_ceiling_exceeded"])

    def test_capability_passes_are_distinguished_from_contract_qualification(self) -> None:
        scope = self.decision["scope"]
        self.assertTrue(scope["governed_llm_capability_proved"])
        self.assertFalse(scope["model_intrinsically_rejected"])
        results = self.decision["contract_results"]
        self.assertEqual(results["provider_completions"], 10)
        self.assertEqual(results["structured_output_passes"], 10)
        self.assertEqual(results["canonical_schema_passes"], 10)
        self.assertEqual(results["referential_passes"], 10)
        self.assertEqual(results["policy_passes"], 10)
        self.assertEqual(results["prompt_injection_safe_runs"], 2)
        self.assertEqual(results["source_disagreement_safe_or_silent_runs"], 2)
        self.assertEqual(results["accepted_outputs"], 1)
        self.assertEqual(results["rejected_outputs"], 9)
        review = self.decision["review_decision"]
        self.assertEqual(review["current_contract"], "public-demo-no-go")
        self.assertEqual(review["capability_proof"], "achieved")
        self.assertIsNone(review["selected_model"])
        self.assertEqual(
            review["next_architecture"],
            "semantic-claim-plan-plus-deterministic-renderer",
        )
        self.assertEqual(review["architecture_issue"], 228)

    def test_failure_distribution_is_bounded_and_not_reframed_as_model_failure(self) -> None:
        failures = {
            item["class"]: item for item in self.decision["failure_distribution"]
        }
        self.assertEqual(
            failures["rounded-negative-magnitude-without-approximation-wording"][
                "affected_runs"
            ],
            6,
        )
        self.assertEqual(
            failures["rounded-negative-magnitude-without-approximation-wording"][
                "diagnostic_count"
            ],
            16,
        )
        self.assertEqual(
            failures["timestamp-observation-assigned-data-quality-limitation"][
                "affected_runs"
            ],
            2,
        )
        self.assertEqual(
            failures["selected-source-observation-assigned-data-quality-limitation"][
                "affected_runs"
            ],
            1,
        )
        self.assertEqual(
            failures["humanised-string-value-alias"]["assessment"],
            "validator_prompt_mismatch_attached_to_already_invalid_claim",
        )

    def test_public_exception_and_default_fail_closed_boundaries_are_preserved(self) -> None:
        configuration = self.decision["configuration"]
        self.assertFalse(configuration["zero_data_retention"])
        self.assertEqual(configuration["data_collection"], "deny")
        self.assertFalse(configuration["cross_model_fallback_enabled"])
        self.assertFalse(configuration["automatic_generation_enabled"])
        self.assertFalse(configuration["publication_enabled"])

        self.assertFalse(self.profile["provider_policy"]["zdr"])
        self.assertEqual(self.profile["provider_policy"]["data_collection"], "deny")
        self.assertFalse(self.profile["request_policy"]["cross_model_fallback"])
        self.assertFalse(self.profile["request_policy"]["automatic_generation"])
        self.assertFalse(self.profile["request_policy"]["publication"])

        self.assertTrue(self.default_generation["provider_policy"]["zdr"])
        self.assertEqual(
            self.default_generation["provider_policy"]["data_collection"], "deny"
        )
        self.assertFalse(
            self.default_generation["generation"]["cross_model_fallback"]
        )

        boundaries = self.decision["boundaries"]
        self.assertTrue(boundaries["default_generation_zero_data_retention_unchanged"])
        self.assertTrue(boundaries["public_demo_only_policy_exception"])
        self.assertFalse(boundaries["automatic_generation_approved"])
        self.assertFalse(boundaries["publication_approved"])
        self.assertFalse(boundaries["raw_provider_output_committed"])
        self.assertFalse(boundaries["secrets_committed"])
        self.assertFalse(boundaries["generated_site_output_committed"])

    def test_historical_free_no_go_remains_unchanged(self) -> None:
        self.assertEqual(self.free_decision["status"], "free-proof-no-go")
        self.assertEqual(self.free_decision["source_run"]["run_id"], 29144514292)
        self.assertIsNone(self.free_decision["results"]["selected_model"])


if __name__ == "__main__":
    unittest.main()
