from __future__ import annotations

import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/governed-llm-evaluation.yml"


class GovernedLlmEvaluationWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = WORKFLOW.read_text(encoding="utf-8")
        cls.workflow = yaml.safe_load(cls.text)

    def test_manual_only_and_trusted_main(self) -> None:
        trigger = self.workflow.get("on", self.workflow.get(True))
        self.assertEqual(set(trigger), {"workflow_dispatch"})
        self.assertIn('if [[ "$GITHUB_REF" != "refs/heads/main" ]]', self.text)
        self.assertIn("ref: main", self.text)
        self.assertIn("ref: ${{ needs.prepare.outputs.trusted_sha }}", self.text)

    def test_read_only_and_no_repository_write_actions(self) -> None:
        self.assertEqual(self.workflow["permissions"], {"contents": "read"})
        forbidden = ["contents: write", "pull-requests: write", "git push", "gh pr", "github.rest.pulls", "create-pull-request", "pages: write", "deployments: write"]
        for value in forbidden:
            self.assertNotIn(value, self.text)

    def test_secret_is_limited_to_controlled_evaluation_step(self) -> None:
        self.assertEqual(self.text.count("OPENROUTER_API_KEY"), 2)
        self.assertIn("environment: governed-llm-dry-run", self.text)
        self.assertIn("OPENROUTER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}", self.text)
        self.assertNotIn("OPENROUTER_API_KEY", self.text.split("Run controlled evaluation")[0])
        self.assertEqual(self.text.count("persist-credentials: false"), 2)

    def test_prepared_and_raw_outputs_are_artifacts_only(self) -> None:
        self.assertIn("actions/upload-artifact@v4", self.text)
        self.assertIn("governed-llm-evaluation-prepared", self.text)
        self.assertIn("governed-llm-evaluation-${{ github.run_id }}", self.text)
        self.assertNotIn("reports/crypto", self.text)
        self.assertNotIn("analysis/crypto", self.text)

    def test_exact_source_controlled_plan_and_viability_policy_are_used(self) -> None:
        self.assertIn("--config config/llm-evaluation.yml", self.text)
        self.assertIn("--viability-config config/llm-evaluation-viability.yml", self.text)
        self.assertIn("python -m llm_analysis.evaluation prepare", self.text)
        self.assertIn("python -m llm_analysis.evaluation_runner", self.text)
        self.assertNotIn("python -m llm_analysis.evaluation run", self.text)
        self.assertNotIn("openrouter/free", self.text)
        self.assertNotIn("openrouter/auto", self.text)

    def test_protected_run_is_time_bounded_and_single_job(self) -> None:
        evaluate = self.workflow["jobs"]["evaluate"]
        self.assertEqual(evaluate["timeout-minutes"], 30)
        self.assertEqual(self.workflow["concurrency"]["cancel-in-progress"], False)
        self.assertEqual(evaluate["permissions"] if "permissions" in evaluate else self.workflow["permissions"], {"contents": "read"})


if __name__ == "__main__":
    unittest.main()
