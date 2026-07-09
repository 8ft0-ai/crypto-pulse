from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "docs" / "report-self-proof-evidence-contract.md"


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
            "Static site build",
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
            "must not be opened if any required pre-PR proof is `failed` or `not run`",
            "The generating workflow must fail before opening a PR",
            "source snapshot resolution or validation",
            "generated report validation",
            "advice-language check",
            "relevant unit tests",
            "static site build",
            "rendered archive path proof",
            "changed-file scope validation",
            "`_site` exclusion proof",
        ]
        for marker in required_markers:
            with self.subTest(marker=marker):
                self.assertIn(marker, self.body)

    def test_contract_defines_required_scope_limitations(self) -> None:
        required_limitations = [
            "This PR adds a deterministic Markdown report only.",
            "This PR does not call an LLM.",
            "This PR does not provide investment advice or trading recommendations.",
            "This PR does not publish or deploy the report.",
            "This PR does not auto-merge.",
            "This PR does not introduce secrets or paid API keys.",
            "This PR does not commit generated `_site/` output.",
        ]
        for limitation in required_limitations:
            with self.subTest(limitation=limitation):
                self.assertIn(limitation, self.body)


if __name__ == "__main__":
    unittest.main()
