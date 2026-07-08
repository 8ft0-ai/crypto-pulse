from __future__ import annotations

import sys
import unittest
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


if __name__ == "__main__":
    unittest.main()
