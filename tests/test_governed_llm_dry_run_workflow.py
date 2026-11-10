from pathlib import Path
import unittest


class GovernedLlmDryRunWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = (
            Path(__file__).resolve().parents[1]
            / ".github"
            / "workflows"
            / "governed-llm-dry-run.yml"
        )
        cls.text = cls.path.read_text(encoding="utf-8")

    def test_trigger_is_manual_only(self):
        self.assertIn("workflow_dispatch:", self.text)
        for trigger in (
            "pull_request:",
            "push:",
            "schedule:",
            "workflow_run:",
        ):
            self.assertNotIn(trigger, self.text)

    def test_trusted_main_and_secret_environment_boundaries_are_explicit(self):
        self.assertIn("refs/heads/main", self.text)
        self.assertIn("ref: main", self.text)
        self.assertIn("ref: ${{ needs.prepare.outputs.trusted_sha }}", self.text)
        self.assertIn("persist-credentials: false", self.text)
        self.assertIn("environment: governed-llm-dry-run", self.text)
        self.assertIn(
            "OPENROUTER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}",
            self.text,
        )

    def test_permissions_are_read_only_and_workflow_has_no_write_side_effects(self):
        self.assertIn("permissions:\n  contents: read", self.text)
        for forbidden in (
            "contents: write",
            "pull-requests: write",
            "git push",
            "pulls.create",
            "pages: write",
            "deploy-pages",
        ):
            self.assertNotIn(forbidden, self.text)

    def test_failed_runs_still_upload_diagnostics_then_fail_closed(self):
        self.assertIn("continue-on-error: true", self.text)
        self.assertIn("if: always()", self.text)
        self.assertIn("actions/upload-artifact@v4", self.text)
        self.assertIn("steps.dry_run.outcome != 'success'", self.text)


if __name__ == "__main__":
    unittest.main()
