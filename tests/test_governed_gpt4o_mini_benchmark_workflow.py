from __future__ import annotations

import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/governed-gpt4o-mini-benchmark.yml"


class GovernedGpt4oMiniBenchmarkWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = WORKFLOW.read_text(encoding="utf-8")
        cls.workflow = yaml.safe_load(cls.text)

    def test_manual_only_trusted_main_and_read_only(self) -> None:
        trigger = self.workflow.get("on", self.workflow.get(True))
        self.assertEqual(set(trigger), {"workflow_dispatch"})
        self.assertEqual(self.workflow["permissions"], {"contents": "read"})
        self.assertIn('if [[ "$GITHUB_REF" != "refs/heads/main" ]]', self.text)
        self.assertIn("ref: main", self.text)
        self.assertIn("ref: ${{ needs.prepare.outputs.trusted_sha }}", self.text)
        self.assertEqual(self.text.count("persist-credentials: false"), 2)

    def test_exact_paid_plan_and_protected_secret_boundary(self) -> None:
        self.assertIn("config/llm-evaluation-gpt-4o-mini.yml", self.text)
        self.assertIn("config/llm-evaluation-viability.yml", self.text)
        self.assertIn("python -m llm_analysis.paid_benchmark prepare", self.text)
        self.assertIn("python -m llm_analysis.paid_benchmark run", self.text)
        self.assertIn("environment: governed-llm-dry-run", self.text)
        self.assertEqual(self.text.count("OPENROUTER_API_KEY"), 2)
        self.assertNotIn("OPENROUTER_API_KEY", self.text.split("Run controlled paid benchmark")[0])

    def test_no_repository_or_publication_writes(self) -> None:
        forbidden = [
            "contents: write",
            "pull-requests: write",
            "git push",
            "gh pr",
            "create-pull-request",
            "pages: write",
            "reports/crypto",
            "analysis/crypto",
        ]
        for value in forbidden:
            self.assertNotIn(value, self.text)
        self.assertIn("actions/upload-artifact@v4", self.text)
        self.assertIn("governed-gpt4o-mini-benchmark", self.text)

    def test_benchmark_is_time_bounded(self) -> None:
        evaluate = self.workflow["jobs"]["evaluate"]
        self.assertEqual(evaluate["timeout-minutes"], 30)
        self.assertFalse(self.workflow["concurrency"]["cancel-in-progress"])


if __name__ == "__main__":
    unittest.main()
