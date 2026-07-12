from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs" / "reference" / "generated-report-pr-evidence.md"
LEGACY_CONTRACT = ROOT / "docs" / "report-self-proof-evidence-contract.md"


class SelfProofEvidenceContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.body = CONTRACT.read_text(encoding="utf-8")

    def test_contract_defines_required_evidence_fields(self) -> None:
        required_fields = [
            "Source snapshot",
            "Generated report",
            "Snapshot quality",
            "Required sources",
            "Optional exchange sources",
            "Selected exchange cross-check",
            "Report validation",
            "Advice-language check",
            "Unit tests",
            "Static-site build",
            "Rendered archive path",
            "Changed files",
            "`_site` committed",
            "Workflow run",
            "Scope limitations",
        ]
        for field in required_fields:
            with self.subTest(field=field):
                self.assertIn(field, self.body)

    def test_contract_defines_allowed_statuses(self) -> None:
        for status in ["`passed`", "`not run`", "`not required`", "`failed`"]:
            with self.subTest(status=status):
                self.assertIn(status, self.body)

    def test_contract_defines_required_failure_semantics(self) -> None:
        required_markers = [
            "must stop before branch or pull-request creation",
            "snapshot resolution or validation",
            "report validation",
            "advice-language validation",
            "unit tests",
            "static-site build",
            "rendered archive path",
            "changed-file scope",
            "`_site` exclusion",
        ]
        for marker in required_markers:
            with self.subTest(marker=marker):
                self.assertIn(marker, self.body)

    def test_contract_defines_required_scope_limitations(self) -> None:
        required_limitations = [
            "adds deterministic Markdown report source only",
            "does not call an LLM",
            "does not provide investment advice or trading recommendations",
            "does not publish or deploy the report",
            "does not auto-merge",
            "introduces no secret or paid API key",
            "does not commit generated `_site/` output",
        ]
        for limitation in required_limitations:
            with self.subTest(limitation=limitation):
                self.assertIn(limitation, self.body)

    def test_legacy_contract_path_points_to_canonical_reference(self) -> None:
        text = LEGACY_CONTRACT.read_text(encoding="utf-8")
        self.assertIn("reference/generated-report-pr-evidence.md", text)
        self.assertNotIn("Status: implementation record", text)


if __name__ == "__main__":
    unittest.main()
