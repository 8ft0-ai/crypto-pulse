from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/governed-candidate-selection-model-comparison.yml"


class GovernedCandidateSelectionModelComparisonWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_workflow_is_manual_trusted_main_and_read_only(self) -> None:
        text = self.text
        self.assertIn("workflow_dispatch:", text)
        self.assertNotIn("schedule:", text)
        self.assertNotIn("push:", text)
        self.assertIn("permissions:\n  contents: read", text)
        self.assertIn('if [[ "$GITHUB_REF" != "refs/heads/main" ]]', text)
        self.assertIn("ref: main", text)
        self.assertIn("persist-credentials: false", text)
        self.assertIn("ref: ${{ needs.prepare.outputs.trusted_sha }}", text)
        self.assertIn('test "$(git rev-parse HEAD)" = "$TRUSTED_SHA"', text)

    def test_prepare_is_secret_free_and_evaluate_is_protected(self) -> None:
        text = self.text
        prepare_section, evaluate_section = text.split("  evaluate:\n", 1)
        self.assertNotIn("OPENROUTER_API_KEY", prepare_section)
        self.assertIn("environment: governed-llm-dry-run", evaluate_section)
        self.assertIn("OPENROUTER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}", evaluate_section)
        self.assertIn(
            "python -m llm_analysis.candidate_selection_model_comparison_runner prepare",
            prepare_section,
        )
        self.assertIn(
            "python -m llm_analysis.candidate_selection_model_comparison_runner run",
            evaluate_section,
        )
        self.assertIn(
            "CRYPTOPULSE_SELECTOR_EVIDENCE_DIR: ${{ runner.temp }}/candidate-selection-model-comparison/provider-evidence",
            evaluate_section,
        )
        self.assertIn("continue-on-error: true", evaluate_section)
        self.assertIn("if: always()", evaluate_section)
        self.assertIn("retention-days: 30", evaluate_section)
        self.assertIn(
            "path: ${{ runner.temp }}/candidate-selection-model-comparison/",
            evaluate_section,
        )

    def test_workflow_cannot_publish_or_write_repository_state(self) -> None:
        text = self.text
        for prohibited in (
            "contents: write",
            "pull-requests: write",
            "git push",
            "gh pr",
            "site_generator",
            "_site/",
        ):
            self.assertNotIn(prohibited, text)
        self.assertIn(
            "config/candidate-selection-model-comparison.yml",
            text,
        )


if __name__ == "__main__":
    unittest.main()
