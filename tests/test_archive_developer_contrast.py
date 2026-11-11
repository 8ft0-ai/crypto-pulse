"""Contrast regression for the four Archive developer-output links."""
from __future__ import annotations

import re
import unittest
from pathlib import Path
from types import SimpleNamespace

from site_generator import archive_reader


ROOT = Path(__file__).resolve().parents[1]


def css_rule(stylesheet: str, selector: str) -> str:
    rules = re.findall(r"(?m)^" + re.escape(selector) + r"\s*\{([^}]+)\}", stylesheet)
    if len(rules) != 1:
        raise AssertionError(f"Expected one CSS rule for {selector!r}; found {len(rules)}")
    return rules[0]


def colour(css: str, property_name: str) -> str:
    match = re.search(
        rf"(?:^|;)\s*{re.escape(property_name)}\s*:\s*(#[0-9a-fA-F]{{6}})\s*(?:;|$)",
        css,
    )
    if match is None:
        raise AssertionError(f"Missing explicit {property_name} hex colour")
    return match.group(1)


def luminance(hex_colour: str) -> float:
    components = [int(hex_colour[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in components]
    return sum(c * w for c, w in zip(linear, (0.2126, 0.7152, 0.0722)))


def contrast(foreground: str, background: str) -> float:
    high, low = sorted((luminance(foreground), luminance(background)), reverse=True)
    return (high + 0.05) / (low + 0.05)


class ArchiveDeveloperContrastTests(unittest.TestCase):
    def test_footer_scoped_links_are_underlined_and_meet_aa_text_contrast(self):
        base = (ROOT / "site/assets/cryptopulse.css").read_text(encoding="utf-8")
        archive = (ROOT / "site/assets/cryptopulse-archive-reader.css").read_text(encoding="utf-8")
        brand_match = re.search(r"--brand:\s*(#[0-9a-fA-F]{6})\s*;", base)
        self.assertIsNotNone(brand_match)
        self.assertIn("background: var(--brand)", css_rule(base, ".footer"))
        link_style = css_rule(archive, ".footer .archive-reader-developer a")
        link_colour = colour(link_style, "color")
        self.assertGreaterEqual(contrast(link_colour, brand_match.group(1)), 4.5)
        self.assertRegex(link_style, r"text-decoration:\s*underline\s*;")
        self.assertNotIn("!important", link_style)
        focus_style = css_rule(archive, ".footer .archive-reader-developer a:focus-visible")
        self.assertRegex(focus_style, r"outline:\s*2px solid currentColor\s*;")

    def test_four_links_are_inside_scoped_native_disclosure(self):
        rendered = archive_reader._developer_details(
            SimpleNamespace(GITHUB_URL="https://github.com/8ft0-ai/crypto-pulse")
        )
        self.assertIn('<details class="archive-reader-developer">', rendered)
        self.assertIn("<summary>Developer outputs</summary>", rendered)
        self.assertEqual(rendered.count("<li><a "), 4)
        for label in ("Search index JSON", "RSS", "Manifest", "Pages workflow"):
            self.assertIn(label + "</a>", rendered)


if __name__ == "__main__":
    unittest.main()
