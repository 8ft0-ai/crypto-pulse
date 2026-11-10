from __future__ import annotations

import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import ingest_crypto_sources as ingest


def config() -> dict:
    return {
        "exchange_crosschecks": {
            "required": False,
            "strategy": "first_successful",
            "sources": [
                {
                    "name": "coinbase_exchange",
                    "enabled": True,
                    "quote": "USD",
                    "pairs": {"BTC": "BTC-USD", "ETH": "ETH-USD", "SOL": "SOL-USD"},
                },
                {
                    "name": "kraken",
                    "enabled": True,
                    "quote": "USD",
                    "pairs": {"BTC": "XBTUSD", "ETH": "ETHUSD", "SOL": "SOLUSD"},
                },
                {
                    "name": "okx",
                    "enabled": True,
                    "quote": "USDT",
                    "pairs": {"BTC": "BTC-USDT", "ETH": "ETH-USDT", "SOL": "SOL-USDT"},
                },
                {
                    "name": "binance",
                    "enabled": False,
                    "quote": "USDT",
                    "reason": "GitHub-hosted runners returned HTTP 451",
                },
            ],
        }
    }


class ExchangeCrosscheckIngestionTests(unittest.TestCase):
    def test_first_successful_selects_coinbase_and_skips_later_enabled_sources(self) -> None:
        def fake_fetch_json(url: str, timeout_seconds: int, max_retries: int) -> dict:
            pair = url.split("/products/", 1)[1].split("/ticker", 1)[0]
            prices = {"BTC-USD": "60000", "ETH-USD": "3000", "SOL-USD": "100"}
            return {"price": prices[pair], "bid": prices[pair], "ask": prices[pair], "volume": "123"}

        with patch.object(ingest, "fetch_json", side_effect=fake_fetch_json):
            payload, statuses, warnings = ingest.fetch_exchange_crosschecks(config(), 1, 0)

        self.assertEqual(payload["selected"], "coinbase_exchange")
        self.assertEqual(statuses["coinbase_exchange"]["status"], "ok")
        self.assertEqual(statuses["kraken"]["status"], "skipped")
        self.assertIn("satisfied first_successful strategy", statuses["kraken"]["reason"])
        self.assertEqual(statuses["okx"]["status"], "skipped")
        self.assertEqual(statuses["binance"]["status"], "skipped")
        self.assertEqual(len(payload["sources"]["coinbase_exchange"]), 3)
        self.assertEqual(warnings, [])

    def test_all_enabled_exchanges_degrade_without_selecting_source(self) -> None:
        def fake_fetch_json(url: str, timeout_seconds: int, max_retries: int) -> dict:
            raise ingest.SourceFetchError("synthetic exchange outage")

        with patch.object(ingest, "fetch_json", side_effect=fake_fetch_json):
            payload, statuses, warnings = ingest.fetch_exchange_crosschecks(config(), 1, 0)

        self.assertIsNone(payload["selected"])
        self.assertEqual(statuses["coinbase_exchange"]["status"], "error")
        self.assertEqual(statuses["kraken"]["status"], "error")
        self.assertEqual(statuses["okx"]["status"], "error")
        self.assertEqual(statuses["binance"]["status"], "skipped")
        self.assertEqual(payload["sources"]["coinbase_exchange"], [])
        self.assertEqual(payload["sources"]["kraken"], [])
        self.assertEqual(payload["sources"]["okx"], [])
        self.assertEqual(len(warnings), 3)

    def test_observation_hour_uses_containing_utc_hour(self) -> None:
        cases = [
            (datetime(2026, 7, 10, 8, 0, 0, tzinfo=timezone.utc), "2026-07-10T08:00:00Z"),
            (datetime(2026, 7, 10, 8, 17, 45, tzinfo=timezone.utc), "2026-07-10T08:00:00Z"),
            (datetime(2026, 7, 10, 8, 59, 59, tzinfo=timezone.utc), "2026-07-10T08:00:00Z"),
        ]
        for value, expected in cases:
            with self.subTest(value=value):
                self.assertEqual(ingest.observation_hour_utc(value), expected)

        offset_value = ingest.utc_now("2026-07-10T19:17:45+10:00")
        self.assertEqual(ingest.isoformat_utc(offset_value), "2026-07-10T09:17:45Z")
        self.assertEqual(ingest.observation_hour_utc(offset_value), "2026-07-10T09:00:00Z")

    def test_build_snapshot_embeds_computed_quality(self) -> None:
        market = {
            "assets": [
                {
                    "id": "bitcoin",
                    "symbol": "BTC",
                    "name": "Bitcoin",
                    "price_usd": 60000,
                    "market_cap_usd": 1200000000000,
                    "volume_24h_usd": 10000000000,
                    "change_1h_pct": 0.1,
                    "change_24h_pct": 1.2,
                    "change_7d_pct": 2.3,
                    "market_cap_rank": 1,
                    "last_updated": "2026-07-08T04:34:00Z",
                },
                {
                    "id": "ethereum",
                    "symbol": "ETH",
                    "name": "Ethereum",
                    "price_usd": 3000,
                    "market_cap_usd": 360000000000,
                    "volume_24h_usd": 5000000000,
                    "change_1h_pct": 0.2,
                    "change_24h_pct": 1.3,
                    "change_7d_pct": 2.4,
                    "market_cap_rank": 2,
                    "last_updated": "2026-07-08T04:34:00Z",
                },
                {
                    "id": "solana",
                    "symbol": "SOL",
                    "name": "Solana",
                    "price_usd": 100,
                    "market_cap_usd": 55000000000,
                    "volume_24h_usd": 1000000000,
                    "change_1h_pct": 0.3,
                    "change_24h_pct": 1.4,
                    "change_7d_pct": 2.5,
                    "market_cap_rank": 5,
                    "last_updated": "2026-07-08T04:34:00Z",
                },
            ]
        }
        defi = {
            "total_tvl_usd": 100000000000,
            "stablecoins": [
                {"symbol": "USDT", "name": "Tether", "price_usd": 1.0, "circulating_usd": 100000000000},
                {"symbol": "USDC", "name": "USD Coin", "price_usd": 1.0, "circulating_usd": 50000000000},
            ],
        }
        exchange_payload = {
            "strategy": "first_successful",
            "selected": "coinbase_exchange",
            "sources": {"coinbase_exchange": [{"symbol": "BTC", "pair": "BTC-USD", "quote": "USD", "price": "60000"}]},
        }
        exchange_statuses = {
            "coinbase_exchange": {"status": "ok", "fetched_at_utc": "2026-07-08T04:34:52Z"},
            "kraken": {"status": "skipped", "reason": "not attempted after coinbase_exchange satisfied first_successful strategy"},
            "okx": {"status": "skipped", "reason": "not attempted after coinbase_exchange satisfied first_successful strategy"},
            "binance": {"status": "skipped", "reason": "GitHub-hosted runners returned HTTP 451"},
        }

        with (
            patch.object(ingest, "fetch_coingecko", return_value=(market, {"status": "ok", "fetched_at_utc": "2026-07-08T04:34:52Z"})),
            patch.object(ingest, "fetch_defillama", return_value=(defi, {"status": "ok", "fetched_at_utc": "2026-07-08T04:34:52Z"})),
            patch.object(ingest, "fetch_exchange_crosschecks", return_value=(exchange_payload, exchange_statuses, [])),
        ):
            snapshot = ingest.build_snapshot(config(), datetime(2026, 7, 8, 4, 34, 52, tzinfo=timezone.utc), "Australia/Sydney")

        self.assertEqual(snapshot["schema_version"], "0.2")
        self.assertEqual(snapshot["run"]["generated_at_utc"], "2026-07-08T04:34:52Z")
        self.assertEqual(snapshot["run"]["observation_hour_utc"], "2026-07-08T04:00:00Z")
        self.assertEqual(snapshot["sources"]["coingecko"]["fetched_at_utc"], "2026-07-08T04:34:52Z")
        self.assertEqual(snapshot["sources"]["defillama"]["fetched_at_utc"], "2026-07-08T04:34:52Z")
        self.assertEqual(snapshot["sources"]["coinbase_exchange"]["fetched_at_utc"], "2026-07-08T04:34:52Z")
        self.assertIn("quality", snapshot)
        self.assertEqual(snapshot["quality"]["status"], "valid-ok")
        self.assertEqual(snapshot["quality"]["blocking_issues"], [])
        self.assertEqual(snapshot["quality"]["non_blocking_warnings"], [])


if __name__ == "__main__":
    unittest.main()
