from __future__ import annotations

import unittest
from pathlib import Path


class GovernedSemanticPlanModelCorrectiveScreenWorkflowTests(unittest.TestCase):
    def test_completed_corrective_screen_is_not_dispatchable(self) -> None:
        workflow = Path(
            ".github/workflows/governed-semantic-plan-model-corrective-screen.yml"
        )
        self.assertFalse(workflow.exists())

    def test_historical_corrective_assets_remain_auditable(self) -> None:
        for path in (
            Path("config/semantic-plan-model-corrective-screen.yml"),
            Path("llm_analysis/semantic_plan_model_prompt_v2_screen.py"),
            Path("prompts/crypto-market-claim-plan-v2.md"),
            Path("docs/governed-semantic-plan-model-corrective-screen.md"),
            Path("evaluation/phase-05/corrective-screen-29285569716.md"),
        ):
            with self.subTest(path=path):
                self.assertTrue(path.is_file())

    def test_reviewed_result_is_recorded_without_model_selection(self) -> None:
        text = Path(
            "evaluation/phase-05/corrective-screen-29285569716.md"
        ).read_text(encoding="utf-8")
        self.assertIn("Route probes completed:           3 / 3", text)
        self.assertIn("Full-contract calls completed:    3 / 3", text)
        self.assertIn("USD 0.0191477293", text)
        self.assertIn("No candidate from this screen advances", text)
        self.assertIn("No model has been selected", text)

    def test_documentation_marks_the_screen_completed_and_historical(self) -> None:
        text = Path(
            "docs/governed-semantic-plan-model-corrective-screen.md"
        ).read_text(encoding="utf-8")
        self.assertIn("completed historical experiment; not dispatchable", text)
        self.assertIn("Do not rerun this screen", text)
        self.assertIn("phase-06-deterministic-claim-selection.md", text)


if __name__ == "__main__":
    unittest.main()
