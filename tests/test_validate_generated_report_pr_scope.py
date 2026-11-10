from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_generated_report_pr_scope import ScopeValidationError, validate_changed_paths, validate_or_raise


class GeneratedReportPrScopeValidationTests(unittest.TestCase):
    def test_allows_generated_report_markdown_under_hourly_archive(self) -> None:
        result = validate_changed_paths(["reports/crypto/hourly/2026/07/08/1742_AEST.md"])
        self.assertTrue(result.passed)
        self.assertEqual(result.allowed_paths, ("reports/crypto/hourly/2026/07/08/1742_AEST.md",))
        self.assertEqual(result.rejected_paths, ())

    def test_rejects_site_output(self) -> None:
        result = validate_changed_paths(["_site/archive/2026/07/08/1742_AEST.html"])
        self.assertFalse(result.passed)
        self.assertEqual(result.rejected_paths, ("_site/archive/2026/07/08/1742_AEST.html",))

    def test_rejects_non_markdown_report_files(self) -> None:
        result = validate_changed_paths(["reports/crypto/hourly/2026/07/08/1742_AEST.json"])
        self.assertFalse(result.passed)
        self.assertEqual(result.rejected_paths, ("reports/crypto/hourly/2026/07/08/1742_AEST.json",))

    def test_rejects_unexpected_workflow_generator_config_data_and_site_paths(self) -> None:
        unexpected_paths = [
            ".github/workflows/generate-deterministic-crypto-report.yml",
            "scripts/generate_crypto_report.py",
            "config/crypto_sources.yml",
            "data/crypto/hourly/2026/07/08/1742_AEST_source_snapshot.json",
            "site/index.html",
        ]
        result = validate_changed_paths(unexpected_paths)
        self.assertFalse(result.passed)
        self.assertEqual(result.rejected_paths, tuple(unexpected_paths))

    def test_rejects_absolute_parent_and_empty_paths(self) -> None:
        result = validate_changed_paths([
            "/reports/crypto/hourly/2026/07/08/1742_AEST.md",
            "reports/crypto/hourly/2026/07/08/../1742_AEST.md",
            "",
        ])
        self.assertFalse(result.passed)
        self.assertEqual(
            result.rejected_paths,
            (
                "/reports/crypto/hourly/2026/07/08/1742_AEST.md",
                "reports/crypto/hourly/2026/07/08/../1742_AEST.md",
            ),
        )

    def test_validate_or_raise_reports_rejected_paths(self) -> None:
        with self.assertRaisesRegex(ScopeValidationError, "unexpected changed files"):
            validate_or_raise(["_site/index.html"])

    def test_cli_reads_paths_from_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            paths_file = Path(tmp) / "changed-files.txt"
            paths_file.write_text("reports/crypto/hourly/2026/07/08/1742_AEST.md\n", encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "validate_generated_report_pr_scope.py"),
                    "--from-file",
                    str(paths_file),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Generated report PR changed-file scope: passed", result.stdout)

    def test_cli_fails_for_unexpected_path(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "validate_generated_report_pr_scope.py"),
                "_site/index.html",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("_site/index.html", result.stderr)


if __name__ == "__main__":
    unittest.main()
