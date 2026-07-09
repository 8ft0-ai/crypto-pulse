from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "generate-deterministic-crypto-report.yml"


class DeterministicReportWorkflowEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.body = WORKFLOW.read_text(encoding="utf-8")

    def assert_ordered(self, *markers: str) -> None:
        for marker in markers:
            self.assertIn(marker, self.body)
        positions = [self.body.index(marker) for marker in markers]
        self.assertEqual(positions, sorted(positions), markers)

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

    def test_source_snapshot_validation_runs_before_report_generation(self) -> None:
        self.assert_ordered(
            "- name: Validate source snapshot",
            "- name: Generate deterministic Markdown report",
        )

    def test_report_validation_tests_and_site_preview_run_before_evidence(self) -> None:
        self.assert_ordered(
            "- name: Validate generated Markdown report",
            "- name: Run unit tests",
            "- name: Build static site preview",
            "- name: Verify rendered report preview",
            "- name: Build PR evidence",
        )

    def test_evidence_scope_validation_and_pr_creation_order(self) -> None:
        self.assert_ordered(
            "- name: Build PR evidence",
            "- name: Inspect generated report changes",
            "- name: Validate generated report changed-file scope",
            "- name: Create automation branch",
            "- name: Commit generated report",
            "- name: Push automation branch",
            "- name: Open generated report PR",
        )

    def test_unit_tests_are_run_before_pr_creation(self) -> None:
        self.assert_ordered(
            "python -m unittest discover -s tests",
            "- name: Open generated report PR",
        )

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

    def test_changed_file_scope_validator_runs_before_branch_creation(self) -> None:
        required_markers = [
            "- name: Validate generated report changed-file scope",
            "python scripts/validate_generated_report_pr_scope.py --from-file",
            "generated-report-changed-files.txt",
        ]
        for marker in required_markers:
            with self.subTest(marker=marker):
                self.assertIn(marker, self.body)
        self.assert_ordered(
            "- name: Validate generated report changed-file scope",
            "- name: Create automation branch",
        )

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
