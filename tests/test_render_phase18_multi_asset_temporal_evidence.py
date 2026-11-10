from __future__ import annotations

import copy
import json
import re
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))

from phase15_public_temporal_evidence import Phase15PublicTemporalEvidenceError  # noqa: E402
from phase18_multi_asset_temporal_evidence import (  # noqa: E402
    PHASE18_CONTRACT_VERSION,
    PUBLIC_SERIES_KEYS,
    Phase18MultiAssetTemporalEvidenceError,
    build_multi_asset_temporal_evidence,
)
from render_phase18_multi_asset_temporal_evidence import (  # noqa: E402
    _render_validated_multi_asset_temporal_evidence,
    render_multi_asset_temporal_evidence,
)
from test_phase15_public_temporal_evidence_proof_corpus import (  # noqa: E402
    CORPUS_PATH,
    Phase15PublicTemporalEvidenceProofTests,
)
from test_render_crypto_observation_hour_series import (  # noqa: E402
    _record,
    _retain_values,
    _set_gap,
)


def _member(series_key: str, offset: int) -> dict:
    record = copy.deepcopy(_record())
    symbol = series_key.split(".", 1)[0]
    record["series_key"] = series_key
    record["series_id"] = f"{offset + 1:x}" * 64
    record["series_id"] = record["series_id"][:64]
    for index, entry in enumerate(record["entries"]):
        value = entry.get("value")
        if not isinstance(value, dict):
            continue
        datum = f"{1000 * (offset + 1) + index}.2500"
        value["datum"] = datum
        evidence = value["evidence"]
        evidence["symbol"] = symbol
        evidence["current"]["value"] = datum
    return record


def _bundle() -> dict:
    members = [
        _member("BTC.price_usd", 0),
        _member("ETH.price_usd", 1),
        _member("SOL.price_usd", 2),
    ]
    common_window = copy.deepcopy(members[0]["window"])
    context = copy.deepcopy(members[0]["repository_context"])
    for member in members:
        member["window"] = copy.deepcopy(common_window)
        member["repository_context"] = copy.deepcopy(context)
    return {
        "contract": PHASE18_CONTRACT_VERSION,
        "repository_context": context,
        "window": common_window,
        "series": members,
        "bundle_id": "d" * 64,
    }


def _asset_chart_section(output: str, symbol: str) -> str:
    key = f"{symbol}.price_usd"
    marker = f'<section class="phase18-asset-chart" data-series-key="{key}"'
    start = output.index(marker)
    end = output.index("</section>", start) + len("</section>")
    return output[start:end]


class Phase18RendererTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.seed_helper = Phase15PublicTemporalEvidenceProofTests(
            "test_corpus_contract_is_closed"
        )
        cls.seed_helper.corpus = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))

    def test_public_renderer_validates_before_any_pure_rendering(self) -> None:
        invalid = {"contract": "tampered"}
        with mock.patch(
            "render_phase18_multi_asset_temporal_evidence.validate_multi_asset_temporal_evidence",
            side_effect=Phase18MultiAssetTemporalEvidenceError("immutable replay failed"),
        ) as validator, mock.patch(
            "render_phase18_multi_asset_temporal_evidence._render_validated_multi_asset_temporal_evidence"
        ) as pure:
            with self.assertRaisesRegex(
                Phase18MultiAssetTemporalEvidenceError,
                "immutable replay",
            ):
                render_multi_asset_temporal_evidence(Path("."), invalid)
            validator.assert_called_once_with(Path("."), invalid)
            pure.assert_not_called()

    def test_repository_bound_valid_bundle_renders_three_assets_in_canonical_order(self) -> None:
        temporary, repository, commit = self.seed_helper._seed("deterministic-max-hour")
        try:
            bundle = build_multi_asset_temporal_evidence(repository, commit)
            self.assertIsNotNone(bundle)
            assert bundle is not None
            output = render_multi_asset_temporal_evidence(repository, bundle)
            positions = [
                output.index(f'data-series-key="{series_key}"')
                for series_key in PUBLIC_SERIES_KEYS
            ]
            self.assertEqual(positions, sorted(positions))
            self.assertEqual(output.count('class="phase18-asset-card"'), 3)
            self.assertIn(bundle["window"]["start_utc"], output)
            self.assertIn(bundle["window"]["end_utc"], output)
        finally:
            temporary.cleanup()

    def test_cards_use_exact_window_end_and_never_fallback(self) -> None:
        bundle = _bundle()
        eth = bundle["series"][1]
        previous = eth["entries"][-2]["value"]["datum"]
        _set_gap(eth, 23, "phase13-current-missing")
        output = _render_validated_multi_asset_temporal_evidence(bundle)
        eth_card_start = output.index(
            '<article class="phase18-asset-card" data-series-key="ETH.price_usd"'
        )
        eth_card_end = output.index("</article>", eth_card_start) + len("</article>")
        card = output[eth_card_start:eth_card_end]
        self.assertIn("Unavailable at window end", card)
        self.assertNotIn(previous, card)
        self.assertIn(bundle["window"]["end_utc"], card)

    def test_coverage_degradation_and_independent_empty_state_are_projection_derived(self) -> None:
        bundle = _bundle()
        eth = bundle["series"][1]
        for index in range(24):
            _set_gap(eth, index)
        output = _render_validated_multi_asset_temporal_evidence(bundle)
        eth_section = _asset_chart_section(output, "ETH")
        self.assertIn('data-reader-state="no-asserted-values"', output)
        self.assertIn('data-chart-state="no-asserted-values"', eth_section)
        self.assertIn("0 / 24", output)
        self.assertIn("no SVG or numeric extrema are rendered", eth_section)
        self.assertEqual(output.count("<svg "), 2)
        self.assertIn('data-series-key="BTC.price_usd"', output)
        self.assertIn('data-series-key="SOL.price_usd"', output)

    def test_isolated_continuous_gap_and_degraded_states_reuse_single_series_semantics(self) -> None:
        isolated = _bundle()
        _retain_values(isolated["series"][0], {4})
        isolated["series"][0]["entries"][4]["continuity"]["status"] = "unavailable"
        isolated_output = _render_validated_multi_asset_temporal_evidence(isolated)
        btc_chart = _asset_chart_section(isolated_output, "BTC")
        self.assertIn('data-chart-state="points-only"', btc_chart)
        self.assertNotIn('class="metric-line"', btc_chart)

        continuous = _bundle()
        _retain_values(continuous["series"][1], {4, 5})
        continuous["series"][1]["entries"][4]["continuity"]["status"] = "unavailable"
        continuous["series"][1]["entries"][5]["continuity"]["status"] = "continuous"
        continuous_output = _render_validated_multi_asset_temporal_evidence(continuous)
        eth_chart = _asset_chart_section(continuous_output, "ETH")
        self.assertIn('data-chart-state="continuous-segments"', eth_chart)
        self.assertEqual(eth_chart.count('class="metric-line"'), 1)

        broken = _bundle()
        _retain_values(broken["series"][2], {4, 5, 6})
        broken["series"][2]["entries"][4]["continuity"]["status"] = "unavailable"
        broken["series"][2]["entries"][5]["continuity"]["status"] = "continuous"
        _set_gap(broken["series"][2], 5)
        broken["series"][2]["entries"][6]["continuity"]["status"] = "unavailable"
        broken_output = _render_validated_multi_asset_temporal_evidence(broken)
        sol_chart = _asset_chart_section(broken_output, "SOL")
        self.assertNotIn('class="metric-line"', sol_chart)

        degraded = _bundle()
        degraded_output = _render_validated_multi_asset_temporal_evidence(degraded)
        self.assertIn("degraded-backed", degraded_output)
        self.assertIn('class="metric-point degraded"', degraded_output)

    def test_svg_accessibility_ids_are_deterministic_and_collision_free(self) -> None:
        output = _render_validated_multi_asset_temporal_evidence(_bundle())
        second = _render_validated_multi_asset_temporal_evidence(_bundle())
        self.assertEqual(output.encode(), second.encode())
        ids = re.findall(r'<(?:title|desc) id="([^"]+)"', output)
        self.assertEqual(len(ids), 6)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(any(identifier.startswith("phase18-btc-") for identifier in ids))
        self.assertTrue(any(identifier.startswith("phase18-eth-") for identifier in ids))
        self.assertTrue(any(identifier.startswith("phase18-sol-") for identifier in ids))
        self.assertEqual(output.count('role="img"'), 3)
        self.assertEqual(output.count("aria-labelledby="), 3)

    def test_compact_table_has_exact_24_common_rows_and_preserves_values_gaps(self) -> None:
        bundle = _bundle()
        _set_gap(bundle["series"][2], 12, "metric-unavailable-current")
        output = _render_validated_multi_asset_temporal_evidence(bundle)
        start = output.index('<table class="phase18-primary-evidence-table">')
        end = output.index("</table>", start) + len("</table>")
        table = output[start:end]
        self.assertEqual(table.count("<tr data-slot-utc="), 24)
        self.assertIn("<th scope=\"col\">BTC</th>", table)
        self.assertIn("<th scope=\"col\">ETH</th>", table)
        self.assertIn("<th scope=\"col\">SOL</th>", table)
        self.assertIn("Unavailable — <code>metric-unavailable-current</code>", table)
        self.assertIn("1000.2500", table)
        self.assertIn("2000.2500", table)

    def test_progressive_disclosure_retains_complete_per_asset_audit_evidence(self) -> None:
        output = _render_validated_multi_asset_temporal_evidence(_bundle())
        self.assertEqual(output.count('<details class="phase18-asset-audit"'), 3)
        self.assertEqual(output.count('<table class="temporal-evidence-table">'), 3)
        self.assertEqual(output.count("<tr data-slot-utc="), 96)
        for series_key in PUBLIC_SERIES_KEYS:
            self.assertIn(f"Complete 24-slot repository evidence for {series_key}", output)
        self.assertIn("comparison-available", output)
        self.assertIn("quality_status", output)
        self.assertIn("metric evidence", output.lower())

    def test_output_has_no_script_canvas_external_resource_or_cross_asset_analysis(self) -> None:
        output = _render_validated_multi_asset_temporal_evidence(_bundle())
        lowered = output.lower()
        for forbidden in (
            "<script",
            "<canvas",
            "http://",
            "https://",
            "percentage change",
            "ranking",
            "best performer",
            "worst performer",
            "relative performance",
            "rebasing",
            "normalisation",
            "normalization",
            "momentum",
        ):
            self.assertNotIn(forbidden, lowered)

    def test_fixed_asset_numeric_validation_remains_strictly_positive_and_finite(self) -> None:
        for index, series_key in enumerate(PUBLIC_SERIES_KEYS):
            with self.subTest(series_key=series_key):
                bundle = _bundle()
                member = bundle["series"][index]
                _retain_values(member, {3})
                member["entries"][3]["value"]["datum"] = "0"
                with self.assertRaisesRegex(
                    Phase15PublicTemporalEvidenceError,
                    "strictly positive",
                ):
                    _render_validated_multi_asset_temporal_evidence(bundle)

                bundle = _bundle()
                member = bundle["series"][index]
                _retain_values(member, {3})
                member["entries"][3]["value"]["datum"] = float("inf")
                with self.assertRaisesRegex(
                    Phase15PublicTemporalEvidenceError,
                    "finite",
                ):
                    _render_validated_multi_asset_temporal_evidence(bundle)

    def test_internal_renderer_rejects_reordered_or_unknown_member_identity(self) -> None:
        reordered = _bundle()
        reordered["series"][0], reordered["series"][1] = (
            reordered["series"][1],
            reordered["series"][0],
        )
        with self.assertRaisesRegex(
            Phase18MultiAssetTemporalEvidenceError,
            "identity/order",
        ):
            _render_validated_multi_asset_temporal_evidence(reordered)

        unknown = _bundle()
        unknown["series"][2]["series_key"] = "DOGE.price_usd"
        with self.assertRaisesRegex(
            Phase18MultiAssetTemporalEvidenceError,
            "identity/order",
        ):
            _render_validated_multi_asset_temporal_evidence(unknown)


if __name__ == "__main__":
    unittest.main()
