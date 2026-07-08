#!/usr/bin/env python3
"""Probe public crypto cross-check data sources from a runner context.

This script is intentionally a discovery helper. It does not alter ingestion,
produce reports, call an LLM, or write generated site output.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

USER_AGENT = "CryptoPulse cross-check discovery (https://github.com/8ft0-ai/crypto-pulse)"
TIMEOUT_SECONDS = 20

TESTS: list[dict[str, Any]] = [
    {
        "name": "coinbase_exchange",
        "label": "Coinbase Exchange public ticker",
        "urls": {
            "BTC-USD": "https://api.exchange.coinbase.com/products/BTC-USD/ticker",
            "ETH-USD": "https://api.exchange.coinbase.com/products/ETH-USD/ticker",
            "SOL-USD": "https://api.exchange.coinbase.com/products/SOL-USD/ticker",
        },
        "expected_fields": ["price", "volume", "time"],
    },
    {
        "name": "kraken",
        "label": "Kraken public ticker",
        "urls": {
            "BTC-USD/ETH-USD/SOL-USD": "https://api.kraken.com/0/public/Ticker?pair=XBTUSD,ETHUSD,SOLUSD",
        },
        "expected_fields": ["result"],
    },
    {
        "name": "okx",
        "label": "OKX public spot ticker",
        "urls": {
            "BTC-USDT": "https://www.okx.com/api/v5/market/ticker?instId=BTC-USDT",
            "ETH-USDT": "https://www.okx.com/api/v5/market/ticker?instId=ETH-USDT",
            "SOL-USDT": "https://www.okx.com/api/v5/market/ticker?instId=SOL-USDT",
        },
        "expected_fields": ["code", "data"],
    },
    {
        "name": "bybit",
        "label": "Bybit public spot ticker",
        "urls": {
            "BTCUSDT": "https://api.bybit.com/v5/market/tickers?category=spot&symbol=BTCUSDT",
            "ETHUSDT": "https://api.bybit.com/v5/market/tickers?category=spot&symbol=ETHUSDT",
            "SOLUSDT": "https://api.bybit.com/v5/market/tickers?category=spot&symbol=SOLUSDT",
        },
        "expected_fields": ["retCode", "result"],
    },
    {
        "name": "cryptocompare",
        "label": "CryptoCompare price multi full",
        "urls": {
            "BTC/ETH/SOL-USD": "https://min-api.cryptocompare.com/data/pricemultifull?fsyms=BTC,ETH,SOL&tsyms=USD",
        },
        "expected_fields": ["RAW"],
    },
    {
        "name": "binance",
        "label": "Binance public 24h ticker baseline",
        "urls": {
            "BTCUSDT": "https://api.binance.com/api/v3/ticker/24hr?symbol=BTCUSDT",
            "ETHUSDT": "https://api.binance.com/api/v3/ticker/24hr?symbol=ETHUSDT",
            "SOLUSDT": "https://api.binance.com/api/v3/ticker/24hr?symbol=SOLUSDT",
        },
        "expected_fields": ["lastPrice", "quoteVolume", "priceChangePercent"],
    },
]


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def fetch_json(url: str) -> tuple[str, int | None, Any | None, str | None, float]:
    start = time.monotonic()
    request = Request(url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            status = getattr(response, "status", None)
            charset = response.headers.get_content_charset("utf-8")
            body = response.read().decode(charset)
        elapsed = time.monotonic() - start
        return "ok", status, json.loads(body), None, elapsed
    except HTTPError as exc:
        elapsed = time.monotonic() - start
        return "error", exc.code, None, f"HTTP Error {exc.code}: {exc.reason}", elapsed
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        elapsed = time.monotonic() - start
        return "error", None, None, str(exc), elapsed


def preview_payload(payload: Any) -> Any:
    if isinstance(payload, dict):
        preview: dict[str, Any] = {}
        for key, value in list(payload.items())[:8]:
            if isinstance(value, (str, int, float, bool)) or value is None:
                preview[key] = value
            elif isinstance(value, list):
                preview[key] = f"list[{len(value)}]"
            elif isinstance(value, dict):
                preview[key] = f"object[{len(value)}]"
            else:
                preview[key] = type(value).__name__
        return preview
    if isinstance(payload, list):
        return f"list[{len(payload)}]"
    return payload


def source_result(test: dict[str, Any]) -> dict[str, Any]:
    probes = []
    for symbol, url in test["urls"].items():
        status, http_status, payload, error, elapsed = fetch_json(url)
        probes.append(
            {
                "symbol": symbol,
                "url": url,
                "status": status,
                "http_status": http_status,
                "elapsed_seconds": round(elapsed, 3),
                "error": error,
                "payload_preview": preview_payload(payload),
            }
        )
    ok_count = sum(1 for probe in probes if probe["status"] == "ok")
    if ok_count == len(probes):
        overall = "ok"
    elif ok_count:
        overall = "partial"
    else:
        overall = "failed"
    return {
        "name": test["name"],
        "label": test["label"],
        "overall_status": overall,
        "expected_fields": test["expected_fields"],
        "probes": probes,
    }


def markdown_report(results: dict[str, Any]) -> str:
    lines = [
        "# Crypto source cross-check discovery results",
        "",
        f"Generated at: `{results['generated_at_utc']}`",
        "",
        "These results were produced from the GitHub Actions runner context for issue #64.",
        "",
        "## Summary",
        "",
        "| Source | Overall status | Notes |",
        "| --- | --- | --- |",
    ]
    for source in results["sources"]:
        notes = []
        for probe in source["probes"]:
            if probe["status"] != "ok":
                notes.append(f"{probe['symbol']}: {probe['error'] or probe['http_status']}")
        note_text = "; ".join(notes) if notes else "All probes returned JSON."
        lines.append(f"| {source['label']} | `{source['overall_status']}` | {note_text} |")

    lines.extend(["", "## Probe details", ""])
    for source in results["sources"]:
        lines.extend([f"### {source['label']}", ""])
        for probe in source["probes"]:
            lines.append(f"- `{probe['symbol']}`: `{probe['status']}` HTTP `{probe['http_status']}` in `{probe['elapsed_seconds']}`s")
            if probe["error"]:
                lines.append(f"  - error: `{probe['error']}`")
            if probe["payload_preview"] is not None:
                lines.append(f"  - payload preview: `{json.dumps(probe['payload_preview'], sort_keys=True)}`")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    results = {
        "generated_at_utc": utc_timestamp(),
        "runner_context": "GitHub Actions or local equivalent",
        "sources": [source_result(test) for test in TESTS],
    }
    output_dir = Path("tmp/crypto-crosscheck-discovery")
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "results.json").write_text(json.dumps(results, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_dir / "results.md").write_text(markdown_report(results), encoding="utf-8")

    print(markdown_report(results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
