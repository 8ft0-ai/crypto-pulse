from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "pr-validation.yml"


class PrValidationWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.body = WORKFLOW.read_text(encoding="utf-8")

    def test_planning_changes_trigger_pr_validation(self) -> None:
        required_paths = [
            '"docs/**"',
            '"planning/**"',
            '"README.md"',
            '"tests/**"',
        ]
        for marker in required_paths:
            with self.subTest(marker=marker):
                self.assertIn(marker, self.body)

    def test_validation_runs_unit_tests_before_site_build(self) -> None:
        unit_test_marker = "python -m unittest discover -s tests"
        site_build_marker = "python -m site_generator"
        self.assertIn(unit_test_marker, self.body)
        self.assertIn(site_build_marker, self.body)
        self.assertLess(self.body.index(unit_test_marker), self.body.index(site_build_marker))

    def test_validation_rejects_committed_site_output(self) -> None:
        required_markers = [
            "Reject committed generated site output",
            "grep -E '^_site/'",
            "Generated _site/ output must not be committed.",
        ]
        for marker in required_markers:
            with self.subTest(marker=marker):
                self.assertIn(marker, self.body)


if __name__ == "__main__":
    unittest.main()
