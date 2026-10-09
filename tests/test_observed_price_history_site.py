"""Replay-validated static reader and accessibility checks."""
import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from observed_price_history import ObservedPriceError, materialise
from site_generator.observed_price_history import render

COMMIT = "cbaac787015cce6ecf9d2f07bba4a603d3f0f4c2"


class ObservedPriceSiteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.record = materialise(ROOT, COMMIT)

    def test_accessible_sparse_price_presentation(self):
        markup = render(ROOT, self.record)
        self.assertIn('role="img"', markup)
        self.assertEqual(markup.count("<circle "), 18)
        self.assertEqual(markup.count("<tr>"), 25)
        self.assertIn("not live market data or financial advice", markup)
        self.assertIn("not interpolated", markup)
        self.assertIn("not prove hourly price changes", markup)
        self.assertIn('scope="row"', markup)
        self.assertIn('2026-09-11T04:00:00Z', markup)
        self.assertIn("77086", markup)
        self.assertNotIn("<polyline", markup)
        self.assertNotIn("<script", markup)

    def test_renderer_rejects_forged_price_and_removed_gap(self):
        for operation in (
            lambda j: j["entries"][3]["prices_usd"].update(BTC=1),
            lambda j: j["entries"].pop(0),
            lambda j: j["repository_context"].update(commit_sha="0" * 40),
        ):
            with self.subTest(operation=operation):
                forged = copy.deepcopy(self.record)
                operation(forged)
                with self.assertRaises(ObservedPriceError):
                    render(ROOT, forged)

    def test_markup_escapes_untrusted_values_and_keeps_provenance(self):
        rendered = render(ROOT, self.record)
        self.assertIn("SHA-256", rendered)
        self.assertIn("Git blob", rendered)
        self.assertIn(self.record["repository_context"]["tree_sha"], rendered)


if __name__ == "__main__":
    unittest.main()
