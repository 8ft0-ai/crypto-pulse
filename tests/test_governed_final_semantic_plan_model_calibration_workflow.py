from __future__ import annotations

import unittest
from pathlib import Path


class GovernedFinalSemanticPlanModelCalibrationWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.path = Path(
            ".github/workflows/governed-final-semantic-plan-model-calibration.yml"
        )
        cls.old_path = Path(
            ".github/workflows/governed-semantic-plan-model-calibration.yml"
        )
        cls.text = cls.path.read_text(encoding="utf-8")

    def test_manual_trusted_main_read_only_boundary(self) -> None:
        self.assertIn("workflow_dispatch:", self.text)
        self.assertIn("contents: read", self.text)
        self.assertIn("refs/heads/main", self.text)
        self.assertIn("persist-credentials: false", self.text)
        self.assertNotIn("pull_request:", self.text)
        self.assertNotIn("contents: write", self.text)

    def test_exact_trusted_sha_and_protected_environment(self) -> None:
        self.assertIn("ref: ${{ needs.prepare.outputs.trusted_sha }}", self.text)
        self.assertIn("environment: governed-llm-dry-run", self.text)
        self.assertIn(
            "OPENROUTER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}", self.text
        )

    def test_workflow_name_and_preflight_make_the_experiment_unambiguous(self) -> None:
        self.assertIn(
            "name: Semantic plan calibration — GPT-5.6 + Nex only", self.text
        )
        self.assertIn("Publish final calibration preflight", self.text)
        self.assertIn("semantic-plan-model-final-calibration/v2", self.text)
        self.assertIn("Prompt: crypto-market-claim-plan/v2", self.text)
        self.assertIn(
            "Candidates: openai/gpt-5.6-sol, nex-agi/nex-n2-mini", self.text
        )
        self.assertIn("Maximum route probes: 2", self.text)
        self.assertIn("Maximum substantive generations: 2", self.text)
        self.assertIn("Whole-run cost ceiling: USD 0.25", self.text)
        self.assertIn("One-source-subject-per-source_status rule: explicit", self.text)
        self.assertIn("MiniMax M3 included: false", self.text)

    def test_superseded_three_model_workflow_is_not_dispatchable(self) -> None:
        self.assertFalse(self.old_path.exists())

    def test_workflow_runs_prompt_v2_calibration_and_only_uploads_artefacts(self) -> None:
        self.assertIn("semantic_plan_model_evaluation prepare", self.text)
        self.assertIn("semantic_plan_model_prompt_v2_screen", self.text)
        self.assertIn("config/semantic-plan-model-final-calibration-v2.yml", self.text)
        self.assertIn("Run final two-call prompt-v2 calibration", self.text)
        self.assertIn("timeout-minutes: 20", self.text)
        self.assertIn("actions/upload-artifact@v4", self.text)
        for prohibited in (
            "git push",
            "gh pr",
            "actions/deploy-pages",
            "pages: write",
            "id-token: write",
        ):
            self.assertNotIn(prohibited, self.text)


if __name__ == "__main__":
    unittest.main()
