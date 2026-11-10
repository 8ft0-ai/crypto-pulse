from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "pr-validation.yml"
DEV_ROOT = ROOT / "tools" / "dev"
sys.path.insert(0, str(DEV_ROOT))

from cryptopulse_dev.checks import EXPECTED_SITE_ARTIFACTS


class PrValidationWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.body = WORKFLOW.read_text(encoding="utf-8")

    def test_planning_and_dependency_changes_trigger_pr_validation(self) -> None:
        required_paths = [
            '"docs/**"',
            '"planning/**"',
            '"README.md"',
            '"requirements-dev.txt"',
            '"tests/**"',
        ]
        for marker in required_paths:
            with self.subTest(marker=marker):
                self.assertIn(marker, self.body)

    def test_ci_installs_repository_owned_development_dependencies(self) -> None:
        self.assertIn("python -m pip install -r requirements-dev.txt", self.body)
        self.assertNotIn("pip install pyyaml markdown", self.body)

    def test_validation_runs_local_reproducible_contract_directly(self) -> None:
        required_markers = [
            "python -m unittest discover -s tests",
            "python scripts/validate_documentation.py",
            "grep -E '^_site/'",
            "python -m site_generator",
        ]
        positions = []
        for marker in required_markers:
            with self.subTest(marker=marker):
                self.assertIn(marker, self.body)
            positions.append(self.body.index(marker))
        self.assertEqual(positions, sorted(positions))
        self.assertNotIn("cp-dev check", self.body)

    def test_validation_rejects_committed_site_output(self) -> None:
        required_markers = [
            "Reject committed generated site output",
            "grep -E '^_site/'",
            "Generated _site/ output must not be committed.",
        ]
        for marker in required_markers:
            with self.subTest(marker=marker):
                self.assertIn(marker, self.body)

    def test_expected_artifact_contract_matches_developer_mirror(self) -> None:
        workflow_artifacts = {
            line.strip().removeprefix("test -f ")
            for line in self.body.splitlines()
            if line.strip().startswith("test -f _site/")
        }
        self.assertEqual(workflow_artifacts, set(EXPECTED_SITE_ARTIFACTS))


if __name__ == "__main__":
    unittest.main()
