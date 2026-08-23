from __future__ import annotations

import copy
import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from crypto_observation_hour_series import ObservationHourSeriesError  # noqa: E402
from phase15_public_temporal_evidence import Phase15PublicTemporalEvidenceError  # noqa: E402
from render_crypto_observation_hour_series import (  # noqa: E402
    HEIGHT,
    WIDTH,
    _reader_projection,
    _render_validated_public_series,
    render_observation_hour_series,
)


def _slot(base: datetime, index: int) -> str:
    return (base + timedelta(hours=index)).isoformat().replace("+00:00", "Z")


def _identity(path: str, quality: str = "valid-ok") -> dict:
    return {
        "path": path,
        "sha256": "a" * 64,
        "schema_version": "0.2",
        "generated_at_utc": "2026-07-08T00:34:00Z",
        "observation_hour_utc": "2026-07-08T00:00:00Z",
        "quality_status": quality,
        "non_blocking_warnings": ["synthetic warning"] if quality == "valid-degraded" else [],
    }


def _record() -> dict:
    base = datetime(2026, 7, 8, tzinfo=timezone.utc)
    entries = []
    previous_current = None
    for index in range(24):
        slot = _slot(base, index)
        if index == 7:
            comparison = {
                "comparison_status": "current-missing",
                "comparison_id": "b" * 64,
                "current": None,
                "predecessor": copy.deepcopy(previous_current),
            }
            entries.append(
                {
                    "slot_utc": slot,
                    "value": None,
                    "gap": {
                        "reason": "phase13-current-missing",
                        "comparison": comparison,
                        "metric_evidence": None,
                    },
                    "continuity": {
                        "status": "unavailable",
                        "previous_current": copy.deepcopy(previous_current),
                        "current_predecessor": None,
                    },
                }
            )
            continue
        current = _identity(f"current-{index}", "valid-degraded" if index == 8 else "valid-ok")
        predecessor = copy.deepcopy(previous_current)
        comparison = {
            "comparison_status": "comparison-available",
            "comparison_id": f"{index:064x}"[-64:],
            "current": current,
            "predecessor": predecessor,
        }
        continuity = "window-start" if index == 0 else (
            "continuous" if predecessor is not None and index != 8 else "unavailable"
        )
        entries.append(
            {
                "slot_utc": slot,
                "value": {
                    "datum": f"{60000 + index}.2500",
                    "comparison": comparison,
                    "evidence": {
                        "family": "market-asset",
                        "symbol": "BTC",
                        "field": "price_usd",
                        "current": {"present": True, "value": f"{60000 + index}.2500"},
                        "predecessor": {"present": predecessor is not None, "value": None},
                        "comparison_state": "comparable",
                        "relation": "current-greater",
                    },
                },
                "gap": None,
                "continuity": {
                    "status": continuity,
                    "previous_current": copy.deepcopy(previous_current) if index else None,
                    "current_predecessor": copy.deepcopy(predecessor) if index else None,
                },
            }
        )
        previous_current = current
    return {
        "schema_version": "crypto-observation-hour-series/v1",
        "series_kind": "metric",
        "series_key": "BTC.price_usd",
        "window": {"start_utc": entries[0]["slot_utc"], "end_utc": entries[-1]["slot_utc"]},
        "repository_context": {"commit_sha": "1" * 40},
        "phase13": {},
        "entries": entries,
        "series_id": "c" * 64,
    }


def _set_gap(record: dict, index: int, reason: str = "phase13-current-missing") -> None:
    entry = record["entries"][index]
    payload = entry.get("value") or entry.get("gap") or {}
    comparison = copy.deepcopy(payload.get("comparison", {}))
    entry["value"] = None
    entry["gap"] = {
        "reason": reason,
        "comparison": comparison,
        "metric_evidence": None,
    }
    entry["continuity"]["status"] = "unavailable"


def _retain_values(record: dict, indices: set[int]) -> None:
    for index in range(24):
        if index not in indices:
            _set_gap(record, index)


class Phase15RendererTests(unittest.TestCase):
    def test_renderer_self_validates_before_any_shape_or_output_work(self) -> None:
        invalid = {"schema_version": "tampered"}
        with mock.patch(
            "render_crypto_observation_hour_series.validate_observation_hour_series",
            side_effect=ObservationHourSeriesError("immutable replay failed"),
        ) as validator, mock.patch(
            "render_crypto_observation_hour_series._enforce_public_series_shape"
        ) as shape, mock.patch(
            "render_crypto_observation_hour_series._render_validated_public_series"
        ) as pure:
            with self.assertRaises(ObservationHourSeriesError):
                render_observation_hour_series(Path("."), invalid)
            validator.assert_called_once_with(Path("."), invalid)
            shape.assert_not_called()
            pure.assert_not_called()

    def test_pure_renderer_is_deterministic_accessible_complete_and_reader_first(self) -> None:
        record = _record()
        first = _render_validated_public_series(record)
        second = _render_validated_public_series(record)
        self.assertEqual(first.encode(), second.encode())
        self.assertEqual(first.count("<svg "), 1)
        self.assertEqual(first.count("<table "), 1)
        self.assertEqual(first.count("<tr data-slot-utc="), 24)
        self.assertIn(f'width="{WIDTH}" height="{HEIGHT}"', first)
        self.assertIn('role="img"', first)
        self.assertIn('data-value-count="23"', first)
        self.assertIn('data-gap-count="1"', first)
        self.assertIn('data-degraded-value-count="2"', first)
        self.assertIn('data-continuous-pair-count="21"', first)
        self.assertIn('data-longest-continuous-run="16"', first)
        self.assertIn('data-gap-reason="phase13-current-missing"', first)
        self.assertIn("phase13-current-missing", first)
        self.assertIn("valid-degraded", first)
        self.assertIn("60000.2500", first)
        self.assertIn("lines require exact continuity", first)
        self.assertIn("No interpolation, aggregation, smoothing, backfill", first)
        self.assertIn("carry-forward", first)
        self.assertIn("Inspect the evidence", first)
        for forbidden in ("<script", "<canvas", "http://", "https://"):
            self.assertNotIn(forbidden, first.lower())

    def test_zero_values_render_truthful_empty_state_without_svg_or_synthetic_extrema(self) -> None:
        record = _record()
        for index in range(24):
            _set_gap(
                record,
                index,
                "phase13-current-missing" if index < 10 else "metric-unavailable-current",
            )

        projection = _reader_projection(record)
        self.assertEqual(
            projection,
            {
                "value_count": 0,
                "gap_count": 24,
                "gap_reasons": {
                    "metric-unavailable-current": 14,
                    "phase13-current-missing": 10,
                },
                "degraded_value_count": 0,
                "continuous_pair_count": 0,
                "longest_continuous_run": 0,
            },
        )
        output = _render_validated_public_series(record)
        self.assertNotIn("<svg ", output)
        self.assertNotIn("max 0", output)
        self.assertNotIn("min 0", output)
        self.assertIn('data-value-count="0"', output)
        self.assertIn('data-gap-count="24"', output)
        self.assertIn("no chart or numeric extrema are rendered", output)
        self.assertEqual(output.count("<tr data-slot-utc="), 24)

    def test_one_isolated_value_renders_point_only_without_line(self) -> None:
        record = _record()
        _retain_values(record, {4})
        record["entries"][4]["continuity"]["status"] = "unavailable"

        projection = _reader_projection(record)
        self.assertEqual(projection["value_count"], 1)
        self.assertEqual(projection["continuous_pair_count"], 0)
        self.assertEqual(projection["longest_continuous_run"], 1)

        output = _render_validated_public_series(record)
        self.assertIn('<svg ', output)
        self.assertIn('data-visual-mode="points"', output)
        self.assertIn('class="metric-point"', output)
        self.assertNotIn('class="metric-line"', output)
        self.assertIn("no connecting line is rendered", output)

    def test_two_continuous_values_create_exactly_one_continuous_pair(self) -> None:
        record = _record()
        _retain_values(record, {4, 5})
        record["entries"][4]["continuity"]["status"] = "unavailable"
        record["entries"][5]["continuity"]["status"] = "continuous"

        projection = _reader_projection(record)
        self.assertEqual(projection["value_count"], 2)
        self.assertEqual(projection["continuous_pair_count"], 1)
        self.assertEqual(projection["longest_continuous_run"], 2)

        output = _render_validated_public_series(record)
        self.assertIn('data-visual-mode="line"', output)
        self.assertEqual(output.count('class="metric-line"'), 1)

    def test_degradation_counts_current_predecessor_and_both_side_once_per_value(self) -> None:
        record = _record()
        _retain_values(record, {0, 1, 2})
        for index in (0, 1, 2):
            record["entries"][index]["continuity"]["status"] = (
                "window-start" if index == 0 else "discontinuous"
            )

        first = record["entries"][0]["value"]["comparison"]
        first["current"] = _identity("first-current", "valid-degraded")
        first["predecessor"] = _identity("first-predecessor", "valid-ok")

        second = record["entries"][1]["value"]["comparison"]
        second["current"] = _identity("second-current", "valid-ok")
        second["predecessor"] = _identity("second-predecessor", "valid-degraded")

        third = record["entries"][2]["value"]["comparison"]
        third["current"] = _identity("third-current", "valid-degraded")
        third["predecessor"] = _identity("third-predecessor", "valid-degraded")

        projection = _reader_projection(record)
        self.assertEqual(projection["value_count"], 3)
        self.assertEqual(projection["degraded_value_count"], 3)

    def test_gap_reason_counts_preserve_exact_retained_vocabulary(self) -> None:
        record = _record()
        for index in range(24):
            _set_gap(
                record,
                index,
                "phase13-current-ambiguous" if index % 3 == 0 else "metric-invalid-current",
            )
        projection = _reader_projection(record)
        self.assertEqual(
            projection["gap_reasons"],
            {
                "metric-invalid-current": 16,
                "phase13-current-ambiguous": 8,
            },
        )
        output = _render_validated_public_series(record)
        self.assertIn(
            '<li data-gap-reason="metric-invalid-current"><code>metric-invalid-current</code><span>16</span></li>',
            output,
        )
        self.assertIn(
            '<li data-gap-reason="phase13-current-ambiguous"><code>phase13-current-ambiguous</code><span>8</span></li>',
            output,
        )

    def test_gap_and_discontinuity_break_numeric_segments(self) -> None:
        output = _render_validated_public_series(_record())
        self.assertIn('class="gap-marker" data-slot-index="7"', output)
        self.assertGreaterEqual(output.count('class="metric-segment"'), 2)
        self.assertNotIn('data-slot-index="7" data-segment=', output)

    def test_zero_metric_value_fails_closed_instead_of_becoming_a_valid_point(self) -> None:
        record = _record()
        _retain_values(record, {3})
        record["entries"][3]["value"]["datum"] = "0"
        with self.assertRaisesRegex(
            Phase15PublicTemporalEvidenceError,
            "strictly positive",
        ):
            _render_validated_public_series(record)


if __name__ == "__main__":
    unittest.main()
