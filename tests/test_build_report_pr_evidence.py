from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_report_pr_evidence import (
    ALLOWED_STATUSES,
    REQUIRED_SCOPE_LIMITATIONS,
    build_parser,
    build_report_pr_evidence,
    evidence_field,
)


BASE_ARGS = [
    "--source-snapshot",
    "data/crypto/hourly/2026/07/08/1742_AEST_source_snapshot.json",
    "--generated-report",
    "reports/crypto/hourly/2026/07/08/1742_AEST.md",
    "--snapshot-quality",
    "valid-ok",
    "--required-source",
    "coingecko: ok",
    "--required-source",
    "defillama: ok",
    "--optional-exchange-source",
    "coinbase_exchange: ok",
    "--selected-exchange-crosscheck",
    "coinbase_exchange",
    "--rendered-archive-path",
    "_site/archive/2026/07/08/1742_AEST.html",
    "--changed-file",
    "reports/crypto/hourly/2026/07/08/1742_AEST.md",
    "--workflow-run",
    "https://github.com/8ft0-ai/crypto-pulse/actions/runs/123",
]


class ReportPrEvidenceBuilderTests(unittest.TestCase):
    def build_evidence(self):
        args = build_parser().parse_args(BASE_ARGS)
        return build_report_pr_evidence(args)

    def test_allowed_statuses_match_contract(self) -> None:
        self.assertEqual(ALLOWED_STATUSES, {"passed", "not run", "not required", "failed"})

    def test_rejects_unsupported_status(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unsupported evidence status"):
            evidence_field("Report validation", "skipped", "not executed")

    def test_manifest_contains_required_fields(self) -> None:
        manifest = self.build_evidence().to_manifest()
        field_names = {field["name"] for field in manifest["fields"]}
        required_names = {
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
            "_site committed",
            "Workflow run",
            "Scope limitations",
        }
        self.assertEqual(field_names, required_names)

    def test_markdown_contains_scope_limitations(self) -> None:
        markdown = self.build_evidence().to_markdown()
        for limitation in REQUIRED_SCOPE_LIMITATIONS:
            with self.subTest(limitation=limitation):
                self.assertIn(limitation, markdown)

    def test_markdown_renders_statuses_and_values(self) -> None:
        markdown = self.build_evidence().to_markdown()
        required_markers = [
            "## Report evidence",
            "Source snapshot: `passed`",
            "Generated report: `passed`",
            "Snapshot quality: `passed` — valid-ok",
            "Required sources: `passed` — coingecko: ok, defillama: ok",
            "Optional exchange sources: `not required` — coinbase_exchange: ok",
            "Static site build: `passed` — python -m site_generator",
            "Rendered archive path: `passed` — _site/archive/2026/07/08/1742_AEST.html",
            "Changed files: `passed` — reports/crypto/hourly/2026/07/08/1742_AEST.md",
            "_site committed: `passed` — no",
        ]
        for marker in required_markers:
            with self.subTest(marker=marker):
                self.assertIn(marker, markdown)

    def test_cli_writes_markdown_and_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            markdown_path = Path(tmp) / "evidence.md"
            json_path = Path(tmp) / "evidence.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "build_report_pr_evidence.py"),
                    *BASE_ARGS,
                    "--markdown-output",
                    str(markdown_path),
                    "--json-output",
                    str(json_path),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            markdown = markdown_path.read_text(encoding="utf-8")
            manifest = json.loads(json_path.read_text(encoding="utf-8"))

        self.assertIn("## Report evidence", markdown)
        self.assertEqual(manifest["summary"], "Adds one deterministic raw Markdown crypto report generated from one validated source snapshot.")
        self.assertIn("scope_limitations", manifest)


if __name__ == "__main__":
    unittest.main()
