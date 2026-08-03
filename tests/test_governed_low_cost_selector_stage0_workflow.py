from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/governed-low-cost-selector-stage-0.yml"


class GovernedLowCostSelectorStage0WorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_workflow_is_manual_trusted_main_and_read_only(self) -> None:
        text = self.text
        self.assertIn("workflow_dispatch:", text)
        self.assertNotIn("schedule:", text)
        self.assertNotIn("push:", text)
        self.assertNotIn("issue_comment:", text)
        self.assertIn("permissions:\n  contents: read", text)
        self.assertIn('if [[ "$GITHUB_REF" != "refs/heads/main" ]]', text)
        self.assertIn("ref: main", text)
        self.assertIn("persist-credentials: false", text)
        self.assertIn("ref: ${{ needs.prepare.outputs.trusted_sha }}", text)
        self.assertIn('test "$(git rev-parse HEAD)" = "$TRUSTED_SHA"', text)

    def test_prepare_is_secret_free_and_evaluate_is_protected(self) -> None:
        prepare_section, evaluate_section = self.text.split("  evaluate:\n", 1)
        self.assertNotIn("OPENROUTER_API_KEY", prepare_section)
        self.assertIn("environment: governed-llm-dry-run", evaluate_section)
        self.assertIn("OPENROUTER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}", evaluate_section)
        self.assertIn("candidate_selector_stage0_runner prepare", prepare_section)
        self.assertIn("candidate_selector_stage0_runner run", evaluate_section)
        self.assertIn("continue-on-error: true", evaluate_section)
        self.assertIn("if: always()", evaluate_section)
        self.assertIn("retention-days: 30", evaluate_section)
        self.assertIn("low-cost-selector-stage-0/", evaluate_section)

    def test_workflow_cannot_write_publish_or_retry(self) -> None:
        text = self.text
        for prohibited in (
            "contents: write",
            "pull-requests: write",
            "git push",
            "gh pr",
            "site_generator",
            "_site/",
            "repository_dispatch",
        ):
            self.assertNotIn(prohibited, text)
        self.assertIn("config/low-cost-candidate-selector-stage-0.yml", text)
        self.assertIn("Run exact three-model compatibility screen", text)


if __name__ == "__main__":
    unittest.main()
