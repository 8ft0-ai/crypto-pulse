from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from site_generator import temporal_evidence


ROOT = Path(__file__).resolve().parents[1]
COMMIT = "1" * 40


def _base(root: Path, out: Path) -> SimpleNamespace:
    site_src = root / "site"
    style = site_src / "assets" / temporal_evidence.STYLE_NAME
    if not style.exists():
        style.parent.mkdir(parents=True, exist_ok=True)
        style.write_text(".temporal-reader-summary{}\n", encoding="utf-8")
    return SimpleNamespace(
        ROOT=root,
        OUT=out,
        SITE_SRC=site_src,
        SITE_NAME="CryptoPulse Demo",
        demo_banner=lambda: '<section class="demo-banner">Demo</section>',
        nav=lambda: '<nav class="site-nav"><a href="index.html">Home</a></nav>',
        badges=lambda: '<div class="badges"><span>Demo</span></div>',
        footer=lambda: '<footer class="footer">Demo disclaimer</footer>',
    )


def _renderer_fragment() -> str:
    rows = "".join(
        f'<tr data-slot-utc="2026-08-21T{index:02d}:00:00Z"><th scope="row">{index}</th><td>evidence</td></tr>'
        for index in range(24)
    )
    return (
        '<section class="phase15-public-temporal-evidence">'
        '<div class="temporal-reader-summary" data-value-count="2" data-gap-count="22" '
        'data-degraded-value-count="1" data-continuous-pair-count="1" '
        'data-longest-continuous-run="2">reader summary</div>'
        '<svg role="img"><text>gap valid-degraded continuous</text></svg>'
        '<section class="temporal-evidence-inspect"><h2>Inspect the evidence</h2>'
        '<table class="temporal-evidence-table"><tbody>'
        + rows
        + "</tbody></table></section></section>\n"
    )


class Phase15SiteIntegrationTests(unittest.TestCase):
    def _modules(self, record: dict, rendered: str):
        phase15 = SimpleNamespace(build_public_temporal_evidence=mock.Mock(return_value=record))
        phase13 = SimpleNamespace(validate_observation_hour_series=mock.Mock(return_value=record))
        renderer = SimpleNamespace(render_observation_hour_series=mock.Mock(return_value=rendered))
        return phase15, phase13, renderer

    def test_success_uses_one_checkout_commit_copies_reader_style_and_couples_one_homepage_link(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "_site"
            out.mkdir()
            index = out / "index.html"
            index.write_text('<html><body><footer class="footer">Footer</footer></body></html>', encoding="utf-8")
            record = {"repository_context": {"commit_sha": COMMIT}}
            rendered = _renderer_fragment()
            phase15, phase13, renderer = self._modules(record, rendered)
            modules = {
                "phase15_public_temporal_evidence": phase15,
                "crypto_observation_hour_series": phase13,
                "render_crypto_observation_hour_series": renderer,
            }
            base = _base(root, out)

            with mock.patch.object(temporal_evidence, "resolve_checkout_commit", return_value=COMMIT), mock.patch.object(
                temporal_evidence, "_load_script_module", side_effect=lambda _root, name: modules[name]
            ):
                self.assertTrue(temporal_evidence.apply(base))

            phase15.build_public_temporal_evidence.assert_called_once_with(root, COMMIT)
            phase13.validate_observation_hour_series.assert_called_once_with(root, record)
            renderer.render_observation_hour_series.assert_called_once_with(root, record)

            page = (out / "temporal.html").read_text(encoding="utf-8")
            homepage = index.read_text(encoding="utf-8")
            self.assertEqual(homepage.count('class="temporal-evidence-discovery"'), 1)
            self.assertEqual(homepage.count('href="temporal.html"'), 1)
            self.assertEqual(page.count(rendered), 1)
            self.assertEqual(page.count("<tr data-slot-utc="), 24)
            self.assertIn("gap", page)
            self.assertIn("valid-degraded", page)
            self.assertIn("continuous", page)
            self.assertIn('data-value-count="2"', page)
            self.assertIn('data-continuous-pair-count="1"', page)
            self.assertLess(page.index("It is not a forecast"), page.index('<section class="phase15-public-temporal-evidence"'))
            self.assertIn(COMMIT, page)
            self.assertIn(f'assets/{temporal_evidence.STYLE_NAME}', page)
            self.assertTrue((out / "assets" / temporal_evidence.STYLE_NAME).exists())
            self.assertNotIn("<script", page.lower())
            self.assertNotIn('src="http', page.lower())

    def test_repeated_success_is_byte_deterministic_and_does_not_duplicate_discovery(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "_site"
            out.mkdir()
            index = out / "index.html"
            original = '<html><body><footer class="footer">Footer</footer></body></html>'
            index.write_text(original, encoding="utf-8")
            record = {"repository_context": {"commit_sha": COMMIT}}
            rendered = _renderer_fragment()
            phase15, phase13, renderer = self._modules(record, rendered)
            modules = {
                "phase15_public_temporal_evidence": phase15,
                "crypto_observation_hour_series": phase13,
                "render_crypto_observation_hour_series": renderer,
            }
            base = _base(root, out)

            with mock.patch.object(temporal_evidence, "resolve_checkout_commit", return_value=COMMIT), mock.patch.object(
                temporal_evidence, "_load_script_module", side_effect=lambda _root, name: modules[name]
            ):
                self.assertTrue(temporal_evidence.apply(base))
                first_page = (out / "temporal.html").read_bytes()
                first_home = index.read_bytes()
                first_style = (out / "assets" / temporal_evidence.STYLE_NAME).read_bytes()
                self.assertTrue(temporal_evidence.apply(base))
                self.assertEqual(first_page, (out / "temporal.html").read_bytes())
                self.assertEqual(first_home, index.read_bytes())
                self.assertEqual(first_style, (out / "assets" / temporal_evidence.STYLE_NAME).read_bytes())
                self.assertEqual(index.read_text(encoding="utf-8").count('href="temporal.html"'), 1)

    def test_current_checkout_materialises_trusted_evidence_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "_site"
            out.mkdir()
            index = out / "index.html"
            index.write_text('<html><body><footer class="footer">Footer</footer></body></html>', encoding="utf-8")
            commit_sha = temporal_evidence.resolve_checkout_commit(ROOT)
            script = """
from pathlib import Path
from types import SimpleNamespace
import sys
from site_generator import temporal_evidence
root = Path(sys.argv[1])
out = Path(sys.argv[2])
base = SimpleNamespace(
    ROOT=root,
    OUT=out,
    SITE_SRC=root / "site",
    SITE_NAME="CryptoPulse Demo",
    demo_banner=lambda: '<section class="demo-banner">Demo</section>',
    nav=lambda: '<nav class="site-nav"><a href="index.html">Home</a></nav>',
    badges=lambda: '<div class="badges"><span>Demo</span></div>',
    footer=lambda: '<footer class="footer">Demo disclaimer</footer>',
)
raise SystemExit(0 if temporal_evidence.apply(base) else 2)
"""
            subprocess.run(
                [sys.executable, "-c", script, str(ROOT), str(out)],
                cwd=ROOT,
                check=True,
                capture_output=True,
                text=True,
            )

            page = (out / "temporal.html").read_text(encoding="utf-8")
            homepage = index.read_text(encoding="utf-8")
            self.assertIn(commit_sha, page)
            self.assertEqual(page.count("<tr data-slot-utc="), 24)
            self.assertEqual(homepage.count('href="temporal.html"'), 1)
            self.assertLess(page.index("It is not a forecast"), page.index('<section class="phase15-public-temporal-evidence"'))
            self.assertIn("What this repository window contains", page)
            self.assertIn("Inspect the evidence", page)
            self.assertTrue((out / "assets" / temporal_evidence.STYLE_NAME).exists())

    def test_commit_mismatch_fails_closed_before_phase13_validation_or_rendering(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "_site"
            out.mkdir()
            index = out / "index.html"
            index.write_text('<footer class="footer">Footer</footer>', encoding="utf-8")
            record = {"repository_context": {"commit_sha": "2" * 40}}
            phase15, phase13, renderer = self._modules(record, _renderer_fragment())
            modules = {
                "phase15_public_temporal_evidence": phase15,
                "crypto_observation_hour_series": phase13,
                "render_crypto_observation_hour_series": renderer,
            }
            base = _base(root, out)

            with mock.patch.object(temporal_evidence, "resolve_checkout_commit", return_value=COMMIT), mock.patch.object(
                temporal_evidence, "_load_script_module", side_effect=lambda _root, name: modules[name]
            ):
                self.assertFalse(temporal_evidence.apply(base))

            self.assertFalse((out / "temporal.html").exists())
            self.assertFalse((out / "assets" / temporal_evidence.STYLE_NAME).exists())
            self.assertNotIn("temporal.html", index.read_text(encoding="utf-8"))
            phase13.validate_observation_hour_series.assert_not_called()
            renderer.render_observation_hour_series.assert_not_called()

    def test_all_contract_failures_remove_stale_page_discovery_and_style(self) -> None:
        scenarios = ("zero", "materialiser", "validator", "renderer", "commit")
        for scenario in scenarios:
            with self.subTest(scenario=scenario), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                out = root / "_site"
                out.mkdir()
                index = out / "index.html"
                index.write_text(
                    '<section class="temporal-evidence-discovery"><a href="temporal.html">stale</a></section>'
                    '<footer class="footer">Footer</footer>',
                    encoding="utf-8",
                )
                (out / "temporal.html").write_text("stale", encoding="utf-8")
                stale_style = out / "assets" / temporal_evidence.STYLE_NAME
                stale_style.parent.mkdir(parents=True)
                stale_style.write_text("stale", encoding="utf-8")
                record = {"repository_context": {"commit_sha": COMMIT}}
                phase15, phase13, renderer = self._modules(record, _renderer_fragment())
                if scenario == "zero":
                    phase15.build_public_temporal_evidence.return_value = None
                elif scenario == "materialiser":
                    phase15.build_public_temporal_evidence.side_effect = ValueError("candidate-set-unorderable")
                elif scenario == "validator":
                    phase13.validate_observation_hour_series.side_effect = ValueError("replay failed")
                elif scenario == "renderer":
                    renderer.render_observation_hour_series.side_effect = ValueError("render failed")

                modules = {
                    "phase15_public_temporal_evidence": phase15,
                    "crypto_observation_hour_series": phase13,
                    "render_crypto_observation_hour_series": renderer,
                }
                commit_patch = mock.patch.object(
                    temporal_evidence,
                    "resolve_checkout_commit",
                    side_effect=temporal_evidence.TemporalEvidenceIntegrationError("git")
                    if scenario == "commit"
                    else None,
                    return_value=None if scenario == "commit" else COMMIT,
                )
                base = _base(root, out)
                with commit_patch, mock.patch.object(
                    temporal_evidence, "_load_script_module", side_effect=lambda _root, name: modules[name]
                ):
                    self.assertFalse(temporal_evidence.apply(base))

                self.assertFalse((out / "temporal.html").exists())
                self.assertFalse((out / "assets" / temporal_evidence.STYLE_NAME).exists())
                homepage = index.read_text(encoding="utf-8")
                self.assertNotIn("temporal-evidence-discovery", homepage)
                self.assertNotIn('href="temporal.html"', homepage)


if __name__ == "__main__":
    unittest.main()
