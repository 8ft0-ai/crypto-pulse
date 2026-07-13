from __future__ import annotations

import unittest
from pathlib import Path


class GovernedSemanticPlanModelCorrectiveScreenWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.path = Path(
            ".github/workflows/governed-semantic-plan-model-corrective-screen.yml"
        )
        cls.text = cls.path.read_text(encoding="utf-8")

    def test_manual_trusted_main_read_only_boundary(self) -> None:
        self.assertIn(
            "name: Semantic plan correction — Luna + DeepSeek + Qwen", self.text
        )
        self.assertIn("workflow_dispatch:", self.text)
        self.assertIn("contents: read", self.text)
        self.assertIn("refs/heads/main", self.text)
        self.assertIn("persist-credentials: false", self.text)
        self.assertNotIn("pull_request:", self.text)
        self.assertNotIn("contents: write", self.text)

    def test_preflight_states_exact_contract_and_cost_boundary(self) -> None:
        self.assertIn("semantic-plan-model-corrective-screen/v1", self.text)
        self.assertIn("Prompt: crypto-market-claim-plan/v2", self.text)
        self.assertIn(
            "Candidates: openai/gpt-5.6-luna, deepseek/deepseek-v4-flash, qwen/qwen3.6-flash",
            self.text,
        )
        self.assertIn("Maximum route probes: 3", self.text)
        self.assertIn("Maximum substantive generations: 3", self.text)
        self.assertIn("Whole-run cost ceiling: USD 0.10", self.text)
        self.assertIn("DeepSeek route probe output allowance: 256 tokens", self.text)
        self.assertIn("Qwen full-contract output allowance: 8000 tokens", self.text)
        self.assertIn("One-source-subject-per-source_status rule: explicit", self.text)
        self.assertIn("Quality leaderboard: disabled", self.text)
        self.assertIn("Deployment selection: disabled", self.text)
        self.assertIn("Cross-model fallback: false", self.text)

    def test_workflow_runs_prompt_v2_screen_and_only_uploads_artefacts(self) -> None:
        self.assertIn("semantic_plan_model_evaluation prepare", self.text)
        self.assertIn("semantic_plan_model_prompt_v2_screen", self.text)
        self.assertIn("config/semantic-plan-model-corrective-screen.yml", self.text)
        self.assertIn("timeout-minutes: 30", self.text)
        self.assertIn("environment: governed-llm-dry-run", self.text)
        self.assertIn(
            "OPENROUTER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}", self.text
        )
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
