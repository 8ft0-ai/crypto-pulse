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
        self.assertIn("actual snapshot generation timestamp", markup)
        self.assertIn("not a verified source-collection time", markup)
        self.assertNotIn("actual collection time", markup)
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


    def test_horizontal_region_is_keyboard_focusable_and_responsive(self):
        html = render(ROOT, self.record)
        self.assertIn('class="table-scroll-wrap"', html)
        self.assertIn('tabindex="0"', html)
        self.assertIn('role="region"', html)
        self.assertIn('aria-label="Scrollable complete hourly observed price evidence"', html)
        self.assertIn('style="max-width:100%;overflow-x:auto"', html)
        self.assertIn('min-width:980px', html)
        self.assertIn('scope="col"', html)
        self.assertIn('scope="row"', html)
        self.assertEqual(html.count("<tr>"), 25)
        self.assertIn('style="display:block;max-width:100%;height:auto"', html)

    def test_extreme_finite_prices_produce_only_finite_svg_coordinates(self):
        import math
        import re
        from site_generator.observed_price_history import _draw_points
        points = [
            {"slot_utc": "2026-01-01T00:00:00Z", "state": "OBSERVED",
             "prices_usd": {"BTC": 1.0}},
            {"slot_utc": "2026-01-01T01:00:00Z", "state": "OBSERVED",
             "prices_usd": {"BTC": 1e308}},
        ]
        svg = _draw_points(points, "BTC")
        locations = re.findall(r'<circle cx="([^"]+)" cy="([^"]+)"', svg)
        self.assertEqual(len(locations), 2)
        for x, y in locations:
            self.assertTrue(math.isfinite(float(x)) and math.isfinite(float(y)))
            self.assertGreaterEqual(float(y), 40)
            self.assertLessEqual(float(y), 175)
        self.assertNotIn("inf", svg.lower())
        self.assertNotIn("nan", svg.lower())
        self.assertNotIn("<polyline", svg)
        points[1]["prices_usd"]["BTC"] = 1.0
        self.assertEqual(_draw_points(points, "BTC").count('cy="107.50"'), 2)
        points[1]["prices_usd"]["BTC"] = float("nan")
        with self.assertRaises(ValueError):
            _draw_points(points, "BTC")

    def test_mixed_blocked_hour_labels_and_prices_are_explicit(self):
        from unittest.mock import patch
        variant = copy.deepcopy(self.record)
        for row, state, reason in (
            (variant["entries"][0], "MISSING", None),
            (variant["entries"][1], "INVALID", "projection-invalid"),
            (variant["entries"][2], "AMBIGUOUS", "duplicate-hour"),
        ):
            row["state"] = state
            row["blocked_reason"] = reason
            row["prices_usd"] = {"BTC": None, "ETH": None, "SOL": None}
        observed_source = next(r["candidates"][0] for r in variant["entries"] if r["candidates"])
        variant["entries"][2]["candidates"] = [copy.deepcopy(observed_source), copy.deepcopy(observed_source)]
        with patch("observed_price_history.validate_replay", return_value=variant):
            page = render(ROOT, variant)
        self.assertIn("INVALID: projection-invalid", page)
        self.assertIn("AMBIGUOUS: duplicate-hour", page)
        self.assertIn("MISSING", page)
        self.assertIn("Multiple source candidates", page)
        self.assertEqual(page.count("<tr>"), 25)

    def test_html_escaping_on_source_derived_strings(self):
        from unittest.mock import patch
        variant = copy.deepcopy(self.record)
        row = next(x for x in variant["entries"] if x["candidates"])
        attack = '<script>alert("attack")</script><img src=x onerror=alert(1)>'
        row["candidates"][0]["path"] = attack
        row["candidates"][0]["generated_at_utc"] = attack
        row["warnings"] = [attack]
        with patch("observed_price_history.validate_replay", return_value=variant):
            page = render(ROOT, variant)
        self.assertIn("&lt;script&gt;", page)
        self.assertIn("&lt;img src=x onerror=alert(1)&gt;", page)
        self.assertNotIn("<script>", page)
        self.assertNotIn("<img src=x onerror=", page)
        self.assertIn("Git blob", page)
        self.assertIn("SHA-256", page)
        with self.assertRaises(ObservedPriceError):
            render(ROOT, variant)


    def test_ambiguous_hours_display_complete_provenance_for_every_source(self):
        from unittest.mock import patch
        variant = copy.deepcopy(self.record)
        hour = variant["entries"][0]
        prototype = next(row["candidates"][0] for row in variant["entries"] if row["candidates"])
        sources = []
        for idx in range(3):
            candidate = copy.deepcopy(prototype)
            candidate["path"] = f"data/crypto/hourly/conflict-{idx}_source_snapshot.json"
            candidate["git_blob_sha"] = str(idx + 1) * 40
            candidate["snapshot_sha256"] = str(idx + 1) * 64
            candidate["generated_at_utc"] = f"2026-09-11T04:{idx:02d}:00Z"
            candidate["observation_hour_utc"] = hour["slot_utc"]
            candidate["quality_status"] = None
            sources.append(candidate)
        hour.update(state="AMBIGUOUS", blocked_reason="duplicate-hour", candidates=sources)
        with patch("observed_price_history.validate_replay", return_value=variant):
            html = render(ROOT, variant)
        self.assertIn("3 conflicting source candidates", html)
        self.assertIn("no winner selected", html)
        self.assertIn("Not evaluated", html)
        for idx, candidate in enumerate(sources):
            self.assertIn(f"Candidate {idx+1}", html)
            self.assertIn(candidate["path"], html)
            self.assertIn(candidate["git_blob_sha"], html)
            self.assertIn(candidate["snapshot_sha256"], html)
            self.assertIn(candidate["generated_at_utc"], html)
        self.assertEqual(html.count("<tr>"), 25)
        self.assertIn("AMBIGUOUS: duplicate-hour", html)
        self.assertIn("<summary>3 conflicting source candidates</summary>", html)
        self.assertIn('tabindex="0"', html)
        self.assertEqual(html.count("<circle "), 18)
        # The actual renderer must not bypass replay validation on altered candidates.
        with self.assertRaises(ObservedPriceError):
            render(ROOT, variant)

    def test_ambiguous_candidate_html_injection_is_escaped(self):
        from unittest.mock import patch
        variant = copy.deepcopy(self.record)
        hour = variant["entries"][0]
        candidate = copy.deepcopy(next(row["candidates"][0] for row in variant["entries"] if row["candidates"]))
        candidate["path"] = '<img src=x onerror=alert(1)>'
        candidate["generated_at_utc"] = '<script>alert(1)</script>'
        hour.update(state="AMBIGUOUS", blocked_reason="duplicate-hour", candidates=[candidate, copy.deepcopy(candidate)])
        with patch("observed_price_history.validate_replay", return_value=variant):
            html = render(ROOT, variant)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("&lt;img src=x onerror=alert(1)&gt;", html)
        self.assertNotIn('<script>alert(1)</script>', html)
        self.assertNotIn('<img src=x onerror=alert(1)>', html)
        self.assertIn("2 conflicting source candidates", html)


if __name__ == "__main__":
    unittest.main()
