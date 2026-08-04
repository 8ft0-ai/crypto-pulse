from __future__ import annotations

import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/governed-gpt-oss-quality-comparison.yml"


class GovernedGPTOSSQualityComparisonWorkflowTests(unittest.TestCase):
    def test_workflow_is_manual_read_only_and_trusted_main(self) -> None:
        raw = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
        trigger = raw.get("on") if "on" in raw else raw.get(True)
        self.assertEqual(set(trigger), {"workflow_dispatch"})
        self.assertEqual(raw["permissions"], {"contents": "read"})
        self.assertIn("GITHUB_REF", WORKFLOW.read_text())
        self.assertIn("refs/heads/main", WORKFLOW.read_text())
        self.assertNotIn("issue_comment", WORKFLOW.read_text())
        self.assertNotIn("schedule:", WORKFLOW.read_text())

    def test_preparation_has_no_secret_and_execution_is_protected(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        prepare = text.split("  compare:", 1)[0]
        compare = text.split("  compare:", 1)[1]
        self.assertNotIn("OPENROUTER_API_KEY", prepare)
        self.assertIn("environment: governed-llm-dry-run", compare)
        self.assertIn("OPENROUTER_API_KEY", compare)
        self.assertIn("persist-credentials: false", text)
        self.assertIn("--trusted-main-sha", compare)

    def test_workflow_has_no_repository_write_or_automatic_trigger(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        for prohibited in ("contents: write", "pull-requests: write", "git push", "gh pr", "repository_dispatch"):
            self.assertNotIn(prohibited, text)
        self.assertIn("gpt-oss-quality-comparison-prepared", text)
        self.assertIn("gpt-oss-quality-comparison-${{ github.run_id }}", text)


if __name__ == "__main__":
    unittest.main()
