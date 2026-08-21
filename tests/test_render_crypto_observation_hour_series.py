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
from render_crypto_observation_hour_series import (  # noqa: E402
    HEIGHT,
    WIDTH,
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

    def test_pure_renderer_is_deterministic_accessible_and_complete(self) -> None:
        record = _record()
        first = _render_validated_public_series(record)
        second = _render_validated_public_series(record)
        self.assertEqual(first.encode(), second.encode())
        self.assertEqual(first.count("<svg "), 1)
        self.assertEqual(first.count("<table "), 1)
        self.assertEqual(first.count("<tr data-slot-utc="), 24)
        self.assertIn(f'width="{WIDTH}" height="{HEIGHT}"', first)
        self.assertIn('role="img"', first)
        self.assertIn("phase13-current-missing", first)
        self.assertIn("valid-degraded", first)
        self.assertIn("60000.2500", first)
        self.assertIn("lines require exact continuity", first)
        self.assertIn("No interpolation, aggregation, smoothing, backfill", first)
        for forbidden in ("<script", "<canvas", "http://", "https://"):
            self.assertNotIn(forbidden, first.lower())

    def test_gap_and_discontinuity_break_numeric_segments(self) -> None:
        output = _render_validated_public_series(_record())
        self.assertIn('class="gap-marker" data-slot-index="7"', output)
        self.assertGreaterEqual(output.count('class="metric-segment"'), 2)
        self.assertNotIn('data-slot-index="7" data-segment=', output)


if __name__ == "__main__":
    unittest.main()
