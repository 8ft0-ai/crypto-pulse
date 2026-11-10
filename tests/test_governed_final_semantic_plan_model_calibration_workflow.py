from __future__ import annotations

import unittest
from pathlib import Path


class GovernedFinalSemanticPlanModelCalibrationWorkflowTests(unittest.TestCase):
    def test_superseded_final_calibration_is_not_dispatchable(self) -> None:
        workflow = Path(
            ".github/workflows/governed-final-semantic-plan-model-calibration.yml"
        )
        self.assertFalse(workflow.exists())

    def test_historical_final_calibration_assets_remain_auditable(self) -> None:
        for path in (
            Path("config/semantic-plan-model-final-calibration-v2.yml"),
            Path("llm_analysis/semantic_plan_model_prompt_v2_screen.py"),
            Path("prompts/crypto-market-claim-plan-v2.md"),
            Path("docs/governed-final-semantic-plan-model-calibration.md"),
        ):
            with self.subTest(path=path):
                self.assertTrue(path.is_file())

    def test_documentation_marks_the_experiment_superseded(self) -> None:
        text = Path(
            "docs/governed-final-semantic-plan-model-calibration.md"
        ).read_text(encoding="utf-8")
        self.assertIn("superseded historical experiment; not dispatchable", text)
        self.assertIn("Do not dispatch the GPT-5.6 Sol/Nex full-plan calibration", text)
        self.assertIn("phase-06-deterministic-claim-selection.md", text)
        self.assertIn("No model was selected", text)

    def test_phase_6_replaces_full_plan_generation_with_candidate_selection(self) -> None:
        text = Path(
            "planning/roadmap/phase-06-deterministic-claim-selection.md"
        ).read_text(encoding="utf-8")
        self.assertIn("deterministic claim-candidate compiler", text)
        self.assertIn("selected_candidate_ids", text)
        self.assertIn("at most one semantic repair", text)
        self.assertIn("deterministic baseline fallback", text)


if __name__ == "__main__":
    unittest.main()
