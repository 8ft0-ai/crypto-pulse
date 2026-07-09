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
            "Static site build:",
            "Rendered archive path:",
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

    def test_workflow_runs_site_preview_before_evidence_and_pr_creation(self) -> None:
        site_build_step = "- name: Build static site preview"
        rendered_path_step = "- name: Verify rendered report preview"
        evidence_step = "- name: Build PR evidence"
        pr_step = "- name: Open generated report PR"
        self.assertIn("python -m site_generator", self.body)
        self.assertLess(self.body.index(site_build_step), self.body.index(rendered_path_step))
        self.assertLess(self.body.index(rendered_path_step), self.body.index(evidence_step))
        self.assertLess(self.body.index(evidence_step), self.body.index(pr_step))

    def test_site_preview_proof_records_rendered_archive_path(self) -> None:
        required_markers = [
            "id: site_preview",
            "rendered_archive_path=$rendered_path",
            "RENDERED_ARCHIVE_PATH: ${{ steps.site_preview.outputs.rendered_archive_path }}",
            "Rendered archive path:",
            "Verified rendered report preview exists at",
        ]
        for marker in required_markers:
            with self.subTest(marker=marker):
                self.assertIn(marker, self.body)

    def test_workflow_keeps_site_output_uncommitted(self) -> None:
        required_markers = [
            "$2 !~ /^_site\\//",
            "Generated _site/ output must not be staged or committed.",
            "git add reports/crypto",
        ]
        for marker in required_markers:
            with self.subTest(marker=marker):
                self.assertIn(marker, self.body)

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
