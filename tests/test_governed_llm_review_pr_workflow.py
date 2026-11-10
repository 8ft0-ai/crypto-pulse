from __future__ import annotations

import unittest
from pathlib import Path


class GovernedReviewPrWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = (
            Path(__file__).parents[1]
            / ".github/workflows/governed-llm-review-pr.yml"
        )
        cls.text = cls.path.read_text(encoding="utf-8")

    def test_manual_only_and_trusted_main(self):
        self.assertIn("workflow_dispatch:", self.text)
        self.assertNotRegex(self.text, r"(?m)^\s*(schedule|push|pull_request):")
        self.assertIn('GITHUB_REF" != "refs/heads/main', self.text)
        self.assertIn("ref: main", self.text)
        self.assertIn("ref: ${{ needs.prepare.outputs.trusted_sha }}", self.text)

    def test_secret_is_only_in_generation_job_and_protected_environment(self):
        self.assertEqual(self.text.count("OPENROUTER_API_KEY"), 2)
        self.assertIn("environment: governed-llm-dry-run", self.text)
        secret_pos = self.text.index("OPENROUTER_API_KEY")
        publish_pos = self.text.index("prove-and-publish:")
        self.assertLess(secret_pos, publish_pos)

    def test_rolling_branch_and_pr_are_bounded(self):
        self.assertIn("automation/governed-llm-analysis-rolling", self.text)
        self.assertIn("pull-requests: write", self.text)
        self.assertIn("contents: write", self.text)
        self.assertIn("git push --force-with-lease", self.text)
        self.assertIn("pulls.list", self.text)
        self.assertIn("pulls.update", self.text)
        self.assertIn("pulls.create", self.text)
        self.assertNotIn("enable_auto_merge", self.text)
        self.assertNotIn("pulls.merge", self.text)

    def test_self_proof_precedes_push(self):
        tests = self.text.index("Run full repository unit tests before push")
        site = self.text.index("Build static site before push")
        push = self.text.index("Commit and push rolling branch")
        self.assertLess(tests, push)
        self.assertLess(site, push)
        self.assertIn("validate_changed_files", self.text)
        self.assertIn("No material source-controlled change", self.text)

    def test_raw_provider_output_is_not_staged(self):
        self.assertIn('manifest["changed_files"]', self.text)
        self.assertNotRegex(self.text, r"git add\s+-A")
        self.assertNotRegex(self.text, r"git add\s+\.($|\s)")


if __name__ == "__main__":
    unittest.main()
