from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from site_generator import reader_evidence

COMMIT = "1" * 40
TREE = "2" * 40
PATH = "data/crypto/hourly/2026/08/21/1549_AEST_source_snapshot.json"
SLOT = "2026-08-21T05:00:00Z"


def _payload() -> dict:
    return {
        "market": {
            "assets": [
                {"symbol": "BTC", "price_usd": 75199, "change_1h_pct": 0.5, "change_24h_pct": 8.4, "change_7d_pct": 18.4},
                {"symbol": "ETH", "price_usd": 2352.5, "change_1h_pct": 0.3, "change_24h_pct": 4.6, "change_7d_pct": 25.0},
                {"symbol": "SOL", "price_usd": 90.17, "change_1h_pct": 0.2, "change_24h_pct": 5.8, "change_7d_pct": 17.9},
            ]
        },
        "quality": {
            "required_sources": ["coingecko", "defillama"],
            "disabled_sources": ["binance"],
        },
        "run": {
            "generated_at_utc": "2026-08-21T05:49:38Z",
            "generated_at_local": "2026-08-21T15:49:38+10:00",
            "timezone_abbreviation": "AEST",
            "observation_hour_utc": SLOT,
        },
        "sources": {"coingecko": {"status": "ok"}, "defillama": {"status": "ok"}, "binance": {"status": "skipped"}},
    }


def _identity(raw: bytes) -> dict:
    return {
        "path": PATH,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "generated_at_utc": "2026-08-21T05:49:38Z",
        "observation_hour_utc": SLOT,
        "quality_status": "valid-ok",
        "non_blocking_warnings": [],
    }


class Phase16ReaderEvidenceTests(unittest.TestCase):
    def test_valid_newest_observation_survives_missing_predecessor(self) -> None:
        raw = json.dumps(_payload()).encode()
        resolver = SimpleNamespace(
            ObservationHourPopulationError=ValueError,
            load_observation_hour_population=mock.Mock(return_value={"2026-08-21T04:00:00Z": [object()], SLOT: [object()]}),
            resolve_observation_hour_adjacency=mock.Mock(
                return_value={"resolution_status": "predecessor-missing", "current": _identity(raw)}
            ),
        )
        with mock.patch.object(reader_evidence, "_load_script_module", return_value=resolver), mock.patch.object(
            reader_evidence, "_git", return_value=raw
        ):
            observation = reader_evidence.resolve_current_observation(Path("/repo"), COMMIT)

        resolver.resolve_observation_hour_adjacency.assert_called_once_with(Path("/repo"), COMMIT, SLOT)
        self.assertIsNotNone(observation)
        self.assertEqual([asset["symbol"] for asset in observation["assets"]], ["BTC", "ETH", "SOL"])
        self.assertEqual(observation["assets"][0]["price_usd"], 75199)
        self.assertEqual(observation["resolution_status"], "predecessor-missing")


    def test_unorderable_population_yields_no_observation_instead_of_older_fallback(self) -> None:
        resolver = SimpleNamespace(
            ObservationHourPopulationError=ValueError,
            load_observation_hour_population=mock.Mock(side_effect=ValueError("unorderable")),
            resolve_observation_hour_adjacency=mock.Mock(),
        )
        with mock.patch.object(reader_evidence, "_load_script_module", return_value=resolver):
            observation = reader_evidence.resolve_current_observation(Path("/repo"), COMMIT)
        self.assertIsNone(observation)
        resolver.resolve_observation_hour_adjacency.assert_not_called()

    def test_invalid_newest_observation_does_not_fallback(self) -> None:
        resolver = SimpleNamespace(
            ObservationHourPopulationError=ValueError,
            load_observation_hour_population=mock.Mock(return_value={"2026-08-21T04:00:00Z": [object()], SLOT: [object()]}),
            resolve_observation_hour_adjacency=mock.Mock(
                return_value={"resolution_status": "current-invalid", "current": {"observation_hour_utc": SLOT, "quality_status": None}}
            ),
        )
        with mock.patch.object(reader_evidence, "_load_script_module", return_value=resolver):
            observation = reader_evidence.resolve_current_observation(Path("/repo"), COMMIT)
        self.assertIsNone(observation)
        resolver.resolve_observation_hour_adjacency.assert_called_once_with(Path("/repo"), COMMIT, SLOT)

    def test_snapshot_identity_mismatch_fails_closed(self) -> None:
        raw = json.dumps(_payload()).encode()
        identity = _identity(raw)
        identity["sha256"] = "0" * 64
        resolver = SimpleNamespace(
            ObservationHourPopulationError=ValueError,
            load_observation_hour_population=mock.Mock(return_value={SLOT: [object()]}),
            resolve_observation_hour_adjacency=mock.Mock(
                return_value={"resolution_status": "predecessor-missing", "current": identity}
            ),
        )
        with mock.patch.object(reader_evidence, "_load_script_module", return_value=resolver), mock.patch.object(
            reader_evidence, "_git", return_value=raw
        ):
            with self.assertRaises(reader_evidence.ReaderEvidenceIntegrationError):
                reader_evidence.resolve_current_observation(Path("/repo"), COMMIT)

    def test_context_associates_report_only_by_exact_source_snapshot_path(self) -> None:
        report = SimpleNamespace(
            title="Archived",
            headline="Headline",
            timestamp="2026-07-08 20:31 AEST",
            url="archive/report.html",
            metadata={"schema_version": "deterministic-crypto-report/v1", "source_snapshot": PATH},
            source_items=[],
            report_time_utc="2026-07-08T10:31:48Z",
        )
        observation = {"identity": {"path": PATH}}
        base = SimpleNamespace(ROOT=Path("/repo"), collect_reports=lambda: [report])
        with mock.patch.object(reader_evidence, "resolve_checkout_context", return_value={"commit_sha": COMMIT, "tree_sha": TREE}), mock.patch.object(
            reader_evidence, "resolve_current_observation", return_value=observation
        ):
            context = reader_evidence.build_reader_evidence_context(base)
        self.assertEqual(context["report_observation_relation"], "exact-source-snapshot-match")

        observation = {"identity": {"path": "data/crypto/hourly/other.json"}}
        with mock.patch.object(reader_evidence, "resolve_checkout_context", return_value={"commit_sha": COMMIT, "tree_sha": TREE}), mock.patch.object(
            reader_evidence, "resolve_current_observation", return_value=observation
        ):
            context = reader_evidence.build_reader_evidence_context(base)
        self.assertEqual(context["report_observation_relation"], "different-evidence-objects")

    def test_report_only_fallback_keeps_market_cards_absent(self) -> None:
        report = SimpleNamespace(
            title="Legacy report",
            headline="Historical headline",
            timestamp="2026-05-09 18:48 AEST",
            url="archive/legacy.html",
            metadata={},
            source_items=[],
            sort_key="2026-05-09T08:48:00Z",
        )
        base = SimpleNamespace(ROOT=Path("/repo"), collect_reports=lambda: [report])
        with mock.patch.object(reader_evidence, "resolve_checkout_context", return_value={"commit_sha": COMMIT, "tree_sha": TREE}), mock.patch.object(
            reader_evidence, "resolve_current_observation", return_value=None
        ):
            context = reader_evidence.build_reader_evidence_context(base)
        rendered = reader_evidence.render_reader_panel(context, surface="home")
        self.assertIn("Deterministic observation unavailable", rendered)
        self.assertNotIn("reader-market-card", rendered)
        self.assertIn("Legacy report", rendered)
        self.assertIn("AI-generated historical report", rendered)


if __name__ == "__main__":
    unittest.main()
