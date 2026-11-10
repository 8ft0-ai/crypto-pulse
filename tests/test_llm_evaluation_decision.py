from __future__ import annotations

import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DECISION = ROOT / "evaluation/phase-05/decision.yml"
GENERATION_CONFIG = ROOT / "config/llm-generation.yml"


class EvaluationDecisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.decision = yaml.safe_load(DECISION.read_text(encoding="utf-8"))
        cls.generation = yaml.safe_load(GENERATION_CONFIG.read_text(encoding="utf-8"))

    def test_decision_is_a_complete_no_go_from_the_reviewed_run(self) -> None:
        self.assertEqual(self.decision["status"], "no-go")
        self.assertIsNone(self.decision["results"]["selected_model"])
        self.assertEqual(self.decision["source_run"]["run_id"], 29142348720)
        self.assertEqual(
            self.decision["source_run"]["trusted_main_sha"],
            "501d1f67852f5e022a4fb5661f2a26adbbe251a8",
        )
        self.assertEqual(self.decision["corpus"]["total_planned_runs"], 20)
        self.assertEqual(self.decision["corpus"]["completed_run_records"], 20)
        self.assertEqual(self.decision["results"]["accepted_model_outputs"], 0)

    def test_every_evaluated_configuration_is_disqualified(self) -> None:
        models = self.decision["models"]
        self.assertEqual(len(models), 2)
        self.assertTrue(all(model["disqualified"] for model in models))
        self.assertTrue(all(model["hard_passes"] == 0 for model in models))
        self.assertTrue(all(model["required_runs"] == 10 for model in models))
        self.assertEqual(models[0]["failure_counts"], {"ineligible_routing": 10})
        self.assertEqual(
            models[1]["failure_counts"],
            {"provider_error_unspecified": 4, "provider_rate_limit": 6},
        )

    def test_governance_boundaries_remain_fail_closed(self) -> None:
        boundaries = self.decision["boundaries"]
        self.assertTrue(boundaries["zero_data_retention_required"])
        self.assertFalse(boundaries["cross_model_fallback_enabled"])
        self.assertFalse(boundaries["paid_model_approved"])
        self.assertFalse(boundaries["automatic_generation_after_snapshot_merge_approved"])
        self.assertFalse(boundaries["rolling_report_generation_approved"])
        self.assertFalse(boundaries["evaluation_output_reused_as_evidence"])
        self.assertFalse(boundaries["raw_provider_output_committed"])
        self.assertFalse(boundaries["generated_site_output_committed"])

        self.assertTrue(self.generation["provider_policy"]["zdr"])
        self.assertFalse(self.generation["generation"]["cross_model_fallback"])

    def test_phase_close_out_is_explicitly_blocked(self) -> None:
        self.assertEqual(self.decision["next_step"]["issue_189_status"], "blocked")
        self.assertEqual(self.decision["results"]["model_quality_evidence"], "unavailable")
        self.assertEqual(self.decision["results"]["actual_providers_observed"], [])


if __name__ == "__main__":
    unittest.main()
