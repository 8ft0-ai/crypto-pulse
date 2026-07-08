from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "generate-deterministic-crypto-report.yml"


class DeterministicReportWorkflowEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.body = WORKFLOW.read_text(encoding="utf-8")

    def test_generated_pr_body_contains_required_report_evidence_fields(self) -> None:
        required_markers = [
            "## Report evidence",
            "Source snapshot:",
            "Generated report:",
            "Snapshot quality:",
            "Required sources:",
            "Selected exchange cross-check:",
            "Report validation:",
            "Advice-language check:",
            "Changed files:",
            "_site committed:",
            "Workflow run:",
        ]
        for marker in required_markers:
            with self.subTest(marker=marker):
                self.assertIn(marker, self.body)

    def test_generated_pr_body_contains_required_scope_limitations(self) -> None:
        required_markers = [
            "This PR adds a deterministic Markdown report only.",
            "This PR does not call an LLM.",
            "This PR does not provide investment advice or trading recommendations.",
            "This PR does not publish or deploy the report.",
            "This PR does not auto-merge.",
        ]
        for marker in required_markers:
            with self.subTest(marker=marker):
                self.assertIn(marker, self.body)

    def test_workflow_runs_report_validator_before_evidence_and_pr_creation(self) -> None:
        validator = 'python scripts/validate_crypto_report.py "$REPORT_PATH" --root .'
        evidence_step = "- name: Build PR evidence"
        pr_step = "- name: Open generated report PR"
        self.assertIn(validator, self.body)
        self.assertLess(self.body.index(validator), self.body.index(evidence_step))
        self.assertLess(self.body.index(evidence_step), self.body.index(pr_step))

    def test_advice_evidence_mentions_prohibited_language_classes(self) -> None:
        prohibited_markers = [
            "buy/sell/hold recommendations",
            "target prices",
            "trading signals",
            "entry/exit points",
            "stop-loss/take-profit language",
            "position guidance",
        ]
        for marker in prohibited_markers:
            with self.subTest(marker=marker):
                self.assertIn(marker, self.body)


if __name__ == "__main__":
    unittest.main()
