from __future__ import annotations

import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
FREE_PROOF_DECISION = ROOT / "evaluation/phase-05/free-proof-decision.yml"
HISTORICAL_DECISION = ROOT / "evaluation/phase-05/decision.yml"
GENERATION_CONFIG = ROOT / "config/llm-generation.yml"


class FreeProofDecisionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.decision = yaml.safe_load(FREE_PROOF_DECISION.read_text(encoding="utf-8"))
        cls.historical = yaml.safe_load(HISTORICAL_DECISION.read_text(encoding="utf-8"))
        cls.generation = yaml.safe_load(GENERATION_CONFIG.read_text(encoding="utf-8"))

    def test_decision_records_the_reviewed_protected_run(self) -> None:
        self.assertEqual(self.decision["status"], "free-proof-no-go")
        self.assertIsNone(self.decision["results"]["selected_model"])
        self.assertEqual(self.decision["source_run"]["run_id"], 29144514292)
        self.assertEqual(self.decision["source_run"]["comparison_job_id"], 86523647793)
        self.assertEqual(
            self.decision["source_run"]["trusted_main_sha"],
            "bf25c6c4ff2924f18bd28050d5b6016676045192",
        )
        self.assertEqual(self.decision["source_run"]["artifact"]["artifact_id"], 8246302011)
        self.assertEqual(
            self.decision["source_run"]["artifact"]["digest"],
            "sha256:a51f829291bf823c7c4d7b5c626b24cacd856986c9841db07552811a8fc066a8",
        )

    def test_funnel_stopped_before_smoke_and_full_corpus(self) -> None:
        experiment = self.decision["experiment"]
        self.assertEqual(experiment["maximum_logical_calls"], 26)
        self.assertEqual(experiment["completed_logical_calls"], 3)
        self.assertEqual(experiment["http_attempts"], 5)
        self.assertEqual(experiment["route_preflight_candidates"], 3)
        self.assertEqual(experiment["route_preflight_passes"], 0)
        self.assertEqual(experiment["smoke_test_passes"], 0)
        self.assertEqual(experiment["full_corpus_finalists"], [])
        self.assertEqual(experiment["full_corpus_runs"], 0)
        self.assertEqual(experiment["accepted_model_outputs"], 0)

    def test_exact_candidate_failures_are_recorded(self) -> None:
        models = {item["key"]: item for item in self.decision["models"]}
        self.assertEqual(set(models), {
            "nemotron-nano-9b-v2",
            "gpt-oss-20b",
            "venice-dolphin-mistral-24b",
        })
        self.assertEqual(models["nemotron-nano-9b-v2"]["failure_code"], "ineligible_routing")
        self.assertEqual(models["nemotron-nano-9b-v2"]["http_attempts"], 1)
        self.assertEqual(models["gpt-oss-20b"]["failure_code"], "ineligible_routing")
        self.assertEqual(models["gpt-oss-20b"]["http_attempts"], 1)
        self.assertEqual(models["venice-dolphin-mistral-24b"]["failure_code"], "rate_limited")
        self.assertEqual(models["venice-dolphin-mistral-24b"]["http_attempts"], 3)
        self.assertTrue(all(item["smoke_test"] == "not_run" for item in models.values()))
        self.assertTrue(all(item["full_corpus"] == "not_run" for item in models.values()))
        self.assertTrue(all(item["actual_provider"] is None for item in models.values()))

    def test_pacing_and_retry_after_evidence_is_complete(self) -> None:
        pacing = self.decision["pacing_evidence"]
        attempts = pacing["attempts"]
        self.assertEqual(pacing["minimum_interval_seconds"], 10)
        self.assertEqual(pacing["maximum_attempts"], 3)
        self.assertEqual(len(attempts), 5)
        self.assertGreaterEqual(attempts[1]["delay_before_seconds"], 10)
        self.assertGreaterEqual(attempts[2]["delay_before_seconds"], 10)
        self.assertEqual(attempts[3]["delay_source"], "retry_after+jitter")
        self.assertEqual(attempts[4]["delay_source"], "retry_after+jitter")
        self.assertEqual([attempts[2]["response_status"], attempts[3]["response_status"], attempts[4]["response_status"]], [429, 429, 429])

    def test_governance_and_planning_boundaries_remain_fail_closed(self) -> None:
        boundaries = self.decision["boundaries"]
        self.assertTrue(boundaries["zero_data_retention_required"])
        self.assertTrue(boundaries["data_collection_denied"])
        self.assertTrue(boundaries["required_parameters_enforced"])
        self.assertFalse(boundaries["cross_model_fallback_enabled"])
        self.assertFalse(boundaries["paid_model_approved"])
        self.assertFalse(boundaries["automatic_generation_after_snapshot_merge_approved"])
        self.assertFalse(boundaries["rolling_report_generation_approved"])
        self.assertFalse(boundaries["evaluation_output_reused_as_evidence"])
        self.assertFalse(boundaries["raw_provider_output_committed"])
        self.assertFalse(boundaries["secrets_committed"])
        self.assertFalse(boundaries["generated_site_output_committed"])

        planning = self.decision["planning_effect"]
        self.assertEqual(planning["free_model_option"], "closed")
        self.assertEqual(planning["issue_199_remaining_choices"], ["paid-proof", "park-and-close"])
        self.assertEqual(planning["issue_189_status"], "blocked")
        self.assertEqual(planning["further_free_model_testing_in_phase_5"], "prohibited")

        self.assertTrue(self.generation["provider_policy"]["zdr"])
        self.assertEqual(self.generation["provider_policy"]["data_collection"], "deny")
        self.assertFalse(self.generation["generation"]["cross_model_fallback"])

    def test_historical_no_go_is_not_rewritten(self) -> None:
        self.assertEqual(self.historical["status"], "no-go")
        self.assertEqual(self.historical["source_run"]["run_id"], 29142348720)
        self.assertEqual(self.historical["corpus"]["completed_run_records"], 20)
        self.assertIsNone(self.historical["results"]["selected_model"])


if __name__ == "__main__":
    unittest.main()
