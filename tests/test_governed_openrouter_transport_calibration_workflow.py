from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/governed-openrouter-transport-calibration.yml"


class GovernedOpenRouterTransportCalibrationWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = WORKFLOW.read_text(encoding="utf-8")

    def test_workflow_accepts_only_manual_main_or_the_exact_owner_nonce(self) -> None:
        text = self.text
        self.assertIn("workflow_dispatch:", text)
        self.assertIn("issue_comment:\n    types: [created]", text)
        self.assertNotIn("schedule:", text)
        self.assertNotIn("push:\n", text)
        self.assertIn("permissions:\n  contents: read", text)
        self.assertIn('if [[ "$EVENT_NAME" == "workflow_dispatch" ]]', text)
        self.assertIn('if [[ "$GITHUB_REF" != "refs/heads/main" ]]', text)
        self.assertIn('"$EVENT_NAME" != "issue_comment"', text)
        self.assertIn('"$EVENT_ACTION" != "created"', text)
        self.assertIn('"$ISSUE_NUMBER" != "325"', text)
        self.assertIn('"$COMMENT_AUTHOR" != "8ft0-ai"', text)
        self.assertIn(
            '"$COMMENT_BODY" != "/run-phase8-observable-transport-calibration-20260803"',
            text,
        )
        self.assertIn("ref: main", text)
        self.assertIn("persist-credentials: false", text)
        self.assertIn("ref: ${{ needs.prepare.outputs.trusted_sha }}", text)
        self.assertIn('test "$(git rev-parse HEAD)" = "$TRUSTED_SHA"', text)

    def test_prepare_is_secret_free_and_calibration_is_protected(self) -> None:
        prepare_section, calibrate_section = self.text.split("  calibrate:\n", 1)
        self.assertNotIn("OPENROUTER_API_KEY", prepare_section)
        self.assertIn("environment: governed-llm-dry-run", calibrate_section)
        self.assertIn("OPENROUTER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}", calibrate_section)
        self.assertIn("openrouter_transport_calibration_runner prepare", prepare_section)
        self.assertIn("openrouter_transport_calibration_runner run", calibrate_section)
        self.assertIn("continue-on-error: true", calibrate_section)
        self.assertIn("if: always()", calibrate_section)
        self.assertIn("retention-days: 30", calibrate_section)

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
        self.assertIn("config/openrouter-transport-calibration-v1.yml", text)
        self.assertIn("Run real-request discovery and reproduction", text)


if __name__ == "__main__":
    unittest.main()