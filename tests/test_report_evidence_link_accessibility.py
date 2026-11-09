"""Prevent evidence links in report prose from relying on colour alone."""
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
CSS = ROOT / "site/assets/cryptopulse.css"
GENERATOR = ROOT / "scripts/build_pages_site.py"


class ReportEvidenceLinkAccessibilityTests(unittest.TestCase):
    def test_report_links_are_visually_distinct_without_colour(self):
        css = CSS.read_text(encoding="utf-8")
        rule = re.search(r"(?m)^\.report-body a\s*\{([^}]+)\}", css)
        self.assertIsNotNone(rule, "report-body links need a dedicated accessibility rule")
        self.assertRegex(rule.group(1), r"text-decoration\s*:\s*underline\s*;")
        self.assertNotRegex(rule.group(1), r"text-decoration\s*:\s*none")
        self.assertRegex(css, r"(?s)@media print\s*\{.*?a\s*\{[^}]*text-decoration:\s*underline")

    def test_generator_keeps_report_markdown_inside_styled_report_body(self):
        source = GENERATOR.read_text(encoding="utf-8")
        self.assertIn('<div class="report-body">', source)
        self.assertIn("{report.body_html}", source)


if __name__ == "__main__":
    unittest.main()
