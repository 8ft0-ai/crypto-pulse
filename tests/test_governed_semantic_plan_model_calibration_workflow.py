from __future__ import annotations

import unittest
from pathlib import Path


class GovernedSemanticPlanModelCalibrationWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.path = Path(".github/workflows/governed-semantic-plan-model-calibration.yml")
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
        self.assertIn("OPENROUTER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}", self.text)

    def test_workflow_runs_three_call_calibration_and_only_uploads_artefacts(self) -> None:
        self.assertIn("semantic_plan_model_evaluation prepare", self.text)
        self.assertIn("semantic_plan_model_calibration", self.text)
        self.assertIn("timeout-minutes: 30", self.text)
        self.assertIn("actions/upload-artifact@v4", self.text)
        self.assertNotIn("git push", self.text)
        self.assertNotIn("gh pr", self.text)
        self.assertNotIn("deploy", self.text.lower())


if __name__ == "__main__":
    unittest.main()
