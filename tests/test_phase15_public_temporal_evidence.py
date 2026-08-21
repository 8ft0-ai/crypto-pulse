from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from phase15_public_temporal_evidence import (  # noqa: E402
    PUBLIC_SERIES_KEY,
    PUBLIC_SERIES_KIND,
    PUBLIC_SLOT_COUNT,
    Phase15PublicTemporalEvidenceError,
    build_public_temporal_evidence,
    select_public_temporal_evidence_window,
)
from resolve_crypto_observation_hour_adjacency import ObservationHourPopulationError  # noqa: E402


class Phase15PublicTemporalEvidenceTests(unittest.TestCase):
    def test_contract_is_hard_frozen_to_btc_price_and_24_slots(self) -> None:
        self.assertEqual(PUBLIC_SERIES_KIND, "metric")
        self.assertEqual(PUBLIC_SERIES_KEY, "BTC.price_usd")
        self.assertEqual(PUBLIC_SLOT_COUNT, 24)

    def test_zero_participation_asserts_no_series_and_never_calls_builder(self) -> None:
        with mock.patch(
            "phase15_public_temporal_evidence.load_observation_hour_population",
            return_value={},
        ), mock.patch(
            "phase15_public_temporal_evidence.build_observation_hour_series"
        ) as builder:
            self.assertIsNone(build_public_temporal_evidence(Path("."), "a" * 40))
            builder.assert_not_called()

    def test_anchor_is_maximum_canonical_participating_hour_not_path_or_input_order(self) -> None:
        population = {
            "2026-07-08T03:00:00Z": [("z", b"", {})],
            "2026-07-08T09:00:00Z": [("a", b"", {})],
            "2026-07-08T05:00:00Z": [("m", b"", {})],
        }
        with mock.patch(
            "phase15_public_temporal_evidence.load_observation_hour_population",
            return_value=population,
        ):
            window = select_public_temporal_evidence_window(Path("."), "a" * 40)
        self.assertEqual(
            window,
            {
                "start_utc": "2026-07-07T10:00:00Z",
                "end_utc": "2026-07-08T09:00:00Z",
            },
        )

    def test_duplicate_latest_hour_remains_the_anchor(self) -> None:
        population = {
            "2026-07-08T08:00:00Z": [("a", b"", {})],
            "2026-07-08T09:00:00Z": [("b", b"", {}), ("c", b"", {})],
        }
        with mock.patch(
            "phase15_public_temporal_evidence.load_observation_hour_population",
            return_value=population,
        ):
            window = select_public_temporal_evidence_window(Path("."), "a" * 40)
        self.assertEqual(window["end_utc"], "2026-07-08T09:00:00Z")

    def test_unorderable_population_fails_before_series_construction(self) -> None:
        with mock.patch(
            "phase15_public_temporal_evidence.load_observation_hour_population",
            side_effect=ObservationHourPopulationError("bad"),
        ), mock.patch(
            "phase15_public_temporal_evidence.build_observation_hour_series"
        ) as builder:
            with self.assertRaisesRegex(
                Phase15PublicTemporalEvidenceError, "candidate-set-unorderable"
            ):
                build_public_temporal_evidence(Path("."), "a" * 40)
            builder.assert_not_called()

    def test_materialiser_uses_only_frozen_identity_and_selected_window(self) -> None:
        population = {"2026-07-08T09:00:00Z": [("a", b"", {})]}
        record = {
            "schema_version": "crypto-observation-hour-series/v1",
            "series_kind": PUBLIC_SERIES_KIND,
            "series_key": PUBLIC_SERIES_KEY,
            "window": {
                "start_utc": "2026-07-07T10:00:00Z",
                "end_utc": "2026-07-08T09:00:00Z",
            },
            "entries": [{} for _ in range(PUBLIC_SLOT_COUNT)],
        }
        with mock.patch(
            "phase15_public_temporal_evidence.load_observation_hour_population",
            return_value=population,
        ), mock.patch(
            "phase15_public_temporal_evidence.build_observation_hour_series",
            return_value=record,
        ) as builder, mock.patch(
            "phase15_public_temporal_evidence.validate_observation_hour_series",
            return_value=record,
        ) as validator:
            result = build_public_temporal_evidence(Path("."), "a" * 40)
        self.assertIs(result, record)
        builder.assert_called_once_with(
            Path("."),
            "a" * 40,
            "metric",
            "BTC.price_usd",
            "2026-07-07T10:00:00Z",
            "2026-07-08T09:00:00Z",
        )
        validator.assert_called_once_with(Path("."), record)


if __name__ == "__main__":
    unittest.main()
