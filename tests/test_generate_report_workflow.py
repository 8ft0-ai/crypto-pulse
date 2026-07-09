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

    def test_workflow_uses_report_evidence_builder(self) -> None:
        required_markers = [
            "from build_report_pr_evidence import build_report_pr_evidence",
            "evidence = build_report_pr_evidence(evidence_args)",
            "pr_body_path.write_text(evidence.to_markdown(), encoding=\"utf-8\")",
            "evidence.to_manifest()",
            "deterministic-crypto-report-pr-evidence.json",
        ]
        for marker in required_markers:
            with self.subTest(marker=marker):
                self.assertIn(marker, self.body)

    def test_generated_pr_body_builder_receives_required_report_evidence_fields(self) -> None:
        required_markers = [
            "source_snapshot=snapshot_path.as_posix()",
            "generated_report=report_path.as_posix()",
            "snapshot_quality=str(quality.get(\"status\", \"unknown\"))",
            "required_source=source_status_items",
            "optional_exchange_source=optional_exchange_sources",
            "selected_exchange_crosscheck=selected_exchange",
            "report_validation=",
            "advice_language_check=",
            "unit_tests=\"python -m unittest discover -s tests\"",
            "static_site_build=\"python -m site_generator\"",
            "rendered_archive_path=rendered_archive_path.as_posix()",
            "changed_file=changed_paths",
            "site_committed=\"no\"",
            "workflow_run=run_url",
        ]
        for marker in required_markers:
            with self.subTest(marker=marker):
                self.assertIn(marker, self.body)

    def test_generated_pr_body_builder_receives_passed_statuses(self) -> None:
        required_markers = [
            "source_snapshot_status=\"passed\"",
            "generated_report_status=\"passed\"",
            "snapshot_quality_status=\"passed\"",
            "required_sources_status=\"passed\"",
            "selected_exchange_status=\"passed\"",
            "report_validation_status=\"passed\"",
            "advice_language_status=\"passed\"",
            "unit_tests_status=\"passed\"",
            "static_site_build_status=\"passed\"",
            "rendered_archive_status=\"passed\"",
            "changed_files_status=\"passed\"",
            "site_committed_status=\"passed\"",
            "workflow_run_status=\"passed\"",
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
