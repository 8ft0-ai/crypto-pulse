#!/usr/bin/env python3
"""Fetch and normalise CryptoPulse source evidence into a JSON snapshot.

This script intentionally produces source evidence only. It does not generate
market commentary, call an LLM, write Markdown reports, or rebuild the Pages
site.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from validate_crypto_snapshot import classify_snapshot_quality

try:
    import yaml
except ImportError as exc:  # pragma: no cover - exercised only without dependency
    raise SystemExit("PyYAML is required. Install with: pip install pyyaml") from exc

COINGECKO_BASE_URL = "https://api.coingecko.com/api/v3"
COINBASE_EXCHANGE_BASE_URL = "https://api.exchange.coinbase.com"
KRAKEN_BASE_URL = "https://api.kraken.com/0/public"
OKX_BASE_URL = "https://www.okx.com/api/v5/market"
DEFILLAMA_BASE_URL = "https://api.llama.fi"
STABLECOINS_BASE_URL = "https://stablecoins.llama.fi"
USER_AGENT = "CryptoPulse source ingestion MVP (https://github.com/8ft0-ai/crypto-pulse)"
SOURCE_STATUS_VALUES = {"ok", "warning", "error", "skipped"}
ExchangeFetcher = Callable[[dict[str, Any], int, int], tuple[list[dict[str, Any]], dict[str, Any]]]


class SourceFetchError(RuntimeError):
    """Raised when one source cannot be fetched or decoded."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch crypto market source evidence and write a timestamped JSON snapshot."
    )
    parser.add_argument(
        "--config",
        default="config/crypto_sources.yml",
        help="Path to the YAML source configuration file.",
    )
    parser.add_argument(
        "--output-root",
        default="data/crypto/hourly",
        help="Root directory for timestamped source snapshots.",
    )
    parser.add_argument(
        "--timezone",
        default="Australia/Sydney",
        help="IANA timezone used for local snapshot naming and metadata.",
    )
    parser.add_argument(
        "--now",
        default=None,
        help="Optional ISO timestamp override for deterministic local testing.",
    )
    return parser.parse_args()


def utc_now(now_override: str | None) -> datetime:
    if not now_override:
        return datetime.now(timezone.utc)
    value = now_override.strip()
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise SystemExit(f"Invalid --now timestamp: {now_override}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise SystemExit(f"Config file not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise SystemExit(f"Config file must contain a YAML mapping: {path}")
    return data


def config_list(config: dict[str, Any], *keys: str) -> list[str]:
    value: Any = config
    for key in keys:
        if not isinstance(value, dict):
            return []
        value = value.get(key)
    if value is None:
        return []
    if not isinstance(value, list):
        raise SystemExit(f"Expected list at config path: {'.'.join(keys)}")
    return [str(item) for item in value]


def config_bool(config: dict[str, Any], default: bool, *keys: str) -> bool:
    value: Any = config
    for key in keys:
        if not isinstance(value, dict):
            return default
        value = value.get(key)
    if value is None:
        return default
    return bool(value)


def config_int(config: dict[str, Any], default: int, *keys: str) -> int:
    value: Any = config
    for key in keys:
        if not isinstance(value, dict):
            return default
        value = value.get(key)
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise SystemExit(f"Expected integer at config path: {'.'.join(keys)}") from exc


def isoformat_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def observation_hour_utc(value: datetime) -> str:
    """Return the canonical UTC hour containing the actual generation time."""
    return (
        value.astimezone(timezone.utc)
        .replace(minute=0, second=0, microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def source_status(status: str, fetched_at_utc: datetime | None, **extra: Any) -> dict[str, Any]:
    if status not in SOURCE_STATUS_VALUES:
        raise ValueError(f"Invalid source status: {status}")
    payload: dict[str, Any] = {"status": status}
    if fetched_at_utc is not None:
        payload["fetched_at_utc"] = isoformat_utc(fetched_at_utc)
    payload.update(extra)
    return payload


def skipped_source_status(reason: str, **extra: Any) -> dict[str, Any]:
    return source_status("skipped", None, reason=reason, **extra)


def fetch_json(url: str, timeout_seconds: int, max_retries: int) -> Any:
    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        request = Request(url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                charset = response.headers.get_content_charset("utf-8")
                body = response.read().decode(charset)
            return json.loads(body)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt < max_retries:
                time.sleep(1 + attempt)
                continue
    raise SourceFetchError(str(last_error) if last_error else "unknown fetch failure")


def fetch_coingecko(config: dict[str, Any], timeout_seconds: int, max_retries: int) -> tuple[dict[str, Any], dict[str, Any]]:
    ids = config_list(config, "assets", "coingecko_ids")
    if not ids:
        return {}, source_status("warning", None, message="No CoinGecko asset ids configured", endpoints=[])

    vs_currency = str(config.get("coingecko", {}).get("vs_currency", "usd")).lower()
    params = {
        "vs_currency": vs_currency,
        "ids": ",".join(ids),
        "order": "market_cap_desc",
        "per_page": str(max(len(ids), 1)),
        "page": "1",
        "sparkline": "false",
        "price_change_percentage": "1h,24h,7d",
    }
    endpoint = "/coins/markets"
    url = f"{COINGECKO_BASE_URL}{endpoint}?{urlencode(params)}"
    fetched_at = datetime.now(timezone.utc)
    raw = fetch_json(url, timeout_seconds, max_retries)
    if not isinstance(raw, list):
        raise SourceFetchError("CoinGecko response was not a list")

    assets: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        assets.append(
            {
                "id": item.get("id"),
                "symbol": str(item.get("symbol", "")).upper(),
                "name": item.get("name"),
                "price_usd": item.get("current_price") if vs_currency == "usd" else None,
                "market_cap_usd": item.get("market_cap") if vs_currency == "usd" else None,
                "volume_24h_usd": item.get("total_volume") if vs_currency == "usd" else None,
                "change_1h_pct": item.get("price_change_percentage_1h_in_currency"),
                "change_24h_pct": item.get("price_change_percentage_24h"),
                "change_7d_pct": item.get("price_change_percentage_7d_in_currency"),
                "market_cap_rank": item.get("market_cap_rank"),
                "last_updated": item.get("last_updated"),
            }
        )

    return {"assets": assets}, source_status(
        "ok",
        fetched_at,
        endpoints=[endpoint],
        asset_ids=ids,
        vs_currency=vs_currency,
    )


def exchange_pairs(source_config: dict[str, Any]) -> dict[str, str]:
    pairs = source_config.get("pairs")
    if not isinstance(pairs, dict):
        return {}
    return {str(symbol).upper(): str(pair) for symbol, pair in pairs.items() if str(symbol).strip() and str(pair).strip()}


def exchange_quote(source_config: dict[str, Any]) -> str:
    return str(source_config.get("quote", "")).upper()


def exchange_row(symbol: str, pair: str, quote: str, price: Any, **extra: Any) -> dict[str, Any]:
    row: dict[str, Any] = {"symbol": symbol, "pair": pair, "quote": quote, "price": price}
    row.update({key: value for key, value in extra.items() if value is not None})
    return row


def fetch_coinbase_exchange(source_config: dict[str, Any], timeout_seconds: int, max_retries: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    pairs = exchange_pairs(source_config)
    quote = exchange_quote(source_config)
    if not pairs:
        return [], source_status("warning", None, message="No Coinbase Exchange pairs configured", endpoints=[])

    fetched_at = datetime.now(timezone.utc)
    endpoint_template = "/products/{product_id}/ticker"
    rows: list[dict[str, Any]] = []
    symbol_errors: list[dict[str, str]] = []
    for symbol, pair in pairs.items():
        endpoint = endpoint_template.format(product_id=pair)
        try:
            item = fetch_json(f"{COINBASE_EXCHANGE_BASE_URL}{endpoint}", timeout_seconds, max_retries)
        except SourceFetchError as exc:
            symbol_errors.append({"symbol": symbol, "pair": pair, "error": str(exc)})
            continue
        if not isinstance(item, dict) or item.get("price") in (None, ""):
            symbol_errors.append({"symbol": symbol, "pair": pair, "error": "ticker response did not include price"})
            continue
        rows.append(
            exchange_row(
                symbol,
                pair,
                quote,
                item.get("price"),
                bid=item.get("bid"),
                ask=item.get("ask"),
                volume_24h_base=item.get("volume"),
                trade_id=item.get("trade_id"),
                source_time=item.get("time"),
            )
        )

    return rows, exchange_fetch_status(
        "Coinbase Exchange",
        fetched_at,
        [endpoint_template],
        pairs,
        rows,
        symbol_errors,
    )


def fetch_kraken(source_config: dict[str, Any], timeout_seconds: int, max_retries: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    pairs = exchange_pairs(source_config)
    quote = exchange_quote(source_config)
    if not pairs:
        return [], source_status("warning", None, message="No Kraken pairs configured", endpoints=[])

    fetched_at = datetime.now(timezone.utc)
    endpoint = "/Ticker"
    rows: list[dict[str, Any]] = []
    symbol_errors: list[dict[str, str]] = []
    for symbol, pair in pairs.items():
        try:
            payload = fetch_json(f"{KRAKEN_BASE_URL}{endpoint}?{urlencode({'pair': pair})}", timeout_seconds, max_retries)
        except SourceFetchError as exc:
            symbol_errors.append({"symbol": symbol, "pair": pair, "error": str(exc)})
            continue
        if not isinstance(payload, dict):
            symbol_errors.append({"symbol": symbol, "pair": pair, "error": "response was not an object"})
            continue
        errors = payload.get("error")
        if isinstance(errors, list) and errors:
            symbol_errors.append({"symbol": symbol, "pair": pair, "error": "; ".join(str(error) for error in errors)})
            continue
        result = payload.get("result")
        ticker = next(iter(result.values())) if isinstance(result, dict) and result else None
        close = ticker.get("c") if isinstance(ticker, dict) else None
        price = close[0] if isinstance(close, list) and close else None
        if price in (None, ""):
            symbol_errors.append({"symbol": symbol, "pair": pair, "error": "ticker response did not include last close price"})
            continue
        volume = ticker.get("v") if isinstance(ticker, dict) else None
        rows.append(
            exchange_row(
                symbol,
                pair,
                quote,
                price,
                volume_24h_base=volume[1] if isinstance(volume, list) and len(volume) > 1 else None,
            )
        )

    return rows, exchange_fetch_status("Kraken", fetched_at, [endpoint], pairs, rows, symbol_errors)


def fetch_okx(source_config: dict[str, Any], timeout_seconds: int, max_retries: int) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    pairs = exchange_pairs(source_config)
    quote = exchange_quote(source_config)
    if not pairs:
        return [], source_status("warning", None, message="No OKX pairs configured", endpoints=[])

    fetched_at = datetime.now(timezone.utc)
    endpoint = "/ticker"
    rows: list[dict[str, Any]] = []
    symbol_errors: list[dict[str, str]] = []
    for symbol, pair in pairs.items():
        try:
            payload = fetch_json(f"{OKX_BASE_URL}{endpoint}?{urlencode({'instId': pair})}", timeout_seconds, max_retries)
        except SourceFetchError as exc:
            symbol_errors.append({"symbol": symbol, "pair": pair, "error": str(exc)})
            continue
        if not isinstance(payload, dict):
            symbol_errors.append({"symbol": symbol, "pair": pair, "error": "response was not an object"})
            continue
        if str(payload.get("code", "0")) != "0":
            symbol_errors.append({"symbol": symbol, "pair": pair, "error": str(payload.get("msg", "non-zero OKX response code"))})
            continue
        data = payload.get("data")
        item = data[0] if isinstance(data, list) and data and isinstance(data[0], dict) else None
        if not item or item.get("last") in (None, ""):
            symbol_errors.append({"symbol": symbol, "pair": pair, "error": "ticker response did not include last price"})
            continue
        rows.append(
            exchange_row(
                symbol,
                pair,
                quote,
                item.get("last"),
                bid=item.get("bidPx"),
                ask=item.get("askPx"),
                volume_24h_base=item.get("vol24h"),
                volume_24h_quote=item.get("volCcy24h"),
                source_time_ms=item.get("ts"),
            )
        )

    return rows, exchange_fetch_status("OKX", fetched_at, [endpoint], pairs, rows, symbol_errors)


def exchange_fetch_status(
    display_name: str,
    fetched_at: datetime,
    endpoints: list[str],
    pairs: dict[str, str],
    rows: list[dict[str, Any]],
    symbol_errors: list[dict[str, str]],
) -> dict[str, Any]:
    covered_symbols = {str(row.get("symbol")).upper() for row in rows if row.get("symbol")}
    required_symbols = set(pairs)
    missing_symbols = sorted(required_symbols - covered_symbols)
    if not rows:
        status = "error"
    elif symbol_errors or missing_symbols:
        status = "warning"
    else:
        status = "ok"
    return source_status(
        status,
        fetched_at,
        endpoints=endpoints,
        pairs=pairs,
        symbols=sorted(required_symbols),
        covered_symbols=sorted(covered_symbols),
        missing_symbols=missing_symbols,
        symbol_errors=symbol_errors,
        message=(
            f"{display_name} returned all configured exchange cross-check pairs"
            if status == "ok"
            else f"{display_name} returned incomplete exchange cross-check evidence"
        ),
    )


EXCHANGE_FETCHERS: dict[str, ExchangeFetcher] = {
    "coinbase_exchange": fetch_coinbase_exchange,
    "kraken": fetch_kraken,
    "okx": fetch_okx,
}


def exchange_source_configs(config: dict[str, Any]) -> list[dict[str, Any]]:
    exchange_config = config.get("exchange_crosschecks")
    sources = exchange_config.get("sources") if isinstance(exchange_config, dict) else None
    if not isinstance(sources, list):
        return []
    return [source for source in sources if isinstance(source, dict) and source.get("name")]


def exchange_strategy(config: dict[str, Any]) -> str:
    exchange_config = config.get("exchange_crosschecks")
    if isinstance(exchange_config, dict):
        return str(exchange_config.get("strategy", "first_successful"))
    return "first_successful"


def fetch_exchange_crosschecks(
    config: dict[str, Any], timeout_seconds: int, max_retries: int
) -> tuple[dict[str, Any], dict[str, dict[str, Any]], list[str]]:
    strategy = exchange_strategy(config)
    exchange_sources: dict[str, list[dict[str, Any]]] = {}
    source_statuses: dict[str, dict[str, Any]] = {}
    warnings: list[str] = []
    selected: str | None = None

    for source_config in exchange_source_configs(config):
        name = str(source_config["name"])
        exchange_sources[name] = []
        if not bool(source_config.get("enabled", True)):
            source_statuses[name] = skipped_source_status(str(source_config.get("reason", "disabled for MVP")))
            continue
        if selected and strategy == "first_successful":
            source_statuses[name] = skipped_source_status(
                f"not attempted after {selected} satisfied first_successful strategy"
            )
            continue

        fetcher = EXCHANGE_FETCHERS.get(name)
        if fetcher is None:
            source_statuses[name] = source_status(
                "warning",
                datetime.now(timezone.utc),
                message="Enabled exchange source is not implemented in this no-secrets MVP",
            )
            warnings.append(f"{name} exchange cross-check is enabled but not implemented")
            continue

        try:
            rows, status = fetcher(source_config, timeout_seconds, max_retries)
        except SourceFetchError as exc:
            rows = []
            status = source_status("error", datetime.now(timezone.utc), message=f"{name} exchange cross-check failed: {exc}")
        exchange_sources[name] = rows
        source_statuses[name] = status
        if status.get("status") == "ok":
            selected = name
        else:
            warnings.append(f"{name} exchange cross-check completed with status {status.get('status', 'unknown')}")

    return {"strategy": strategy, "selected": selected, "sources": exchange_sources}, source_statuses, warnings


def fetch_defillama(config: dict[str, Any], timeout_seconds: int, max_retries: int) -> tuple[dict[str, Any], dict[str, Any]]:
    include_total_tvl = config_bool(config, True, "defillama", "include_total_tvl")
    include_stablecoins = config_bool(config, True, "defillama", "include_stablecoins")
    stablecoin_limit = config_int(config, 10, "defillama", "stablecoin_limit")
    fetched_at = datetime.now(timezone.utc)
    endpoints: list[str] = []
    warnings: list[str] = []
    payload: dict[str, Any] = {"total_tvl_usd": None, "stablecoins": []}

    if include_total_tvl:
        endpoint = "/charts"
        endpoints.append(endpoint)
        charts = fetch_json(f"{DEFILLAMA_BASE_URL}{endpoint}", timeout_seconds, max_retries)
        if isinstance(charts, list) and charts:
            latest = charts[-1]
            if isinstance(latest, dict):
                payload["total_tvl_usd"] = latest.get("totalLiquidityUSD") or latest.get("tvl")
                payload["total_tvl_date"] = latest.get("date")
            else:
                warnings.append("Latest DefiLlama chart entry was not an object")
        else:
            warnings.append("DefiLlama charts response was empty or not a list")

    if include_stablecoins:
        endpoint = "/stablecoins"
        endpoints.append(endpoint)
        stablecoins = fetch_json(
            f"{STABLECOINS_BASE_URL}{endpoint}?{urlencode({'includePrices': 'true'})}",
            timeout_seconds,
            max_retries,
        )
        coins = stablecoins.get("peggedAssets") if isinstance(stablecoins, dict) else None
        if isinstance(coins, list):
            normalised = []
            for item in coins:
                if not isinstance(item, dict):
                    continue
                circulating = item.get("circulating") if isinstance(item.get("circulating"), dict) else {}
                normalised.append(
                    {
                        "id": item.get("id"),
                        "name": item.get("name"),
                        "symbol": item.get("symbol"),
                        "peg_type": item.get("pegType"),
                        "price_usd": item.get("price"),
                        "circulating_usd": circulating.get("peggedUSD"),
                        "change_1d_pct": item.get("change_1d"),
                        "change_7d_pct": item.get("change_7d"),
                    }
                )
            normalised.sort(key=lambda row: row.get("circulating_usd") or 0, reverse=True)
            payload["stablecoins"] = normalised[:stablecoin_limit]
        else:
            warnings.append("DefiLlama stablecoins response did not include peggedAssets")

    status = "ok" if not warnings else "warning"
    return payload, source_status(status, fetched_at, endpoints=endpoints, warnings=warnings)


def build_snapshot(config: dict[str, Any], now_utc: datetime, timezone_name: str) -> dict[str, Any]:
    try:
        local_zone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise SystemExit(f"Unknown timezone: {timezone_name}") from exc

    local_now = now_utc.astimezone(local_zone)
    timeout_seconds = config_int(config, 20, "limits", "request_timeout_seconds")
    max_retries = config_int(config, 2, "limits", "max_retries")

    snapshot: dict[str, Any] = {
        "schema_version": "0.2",
        "run": {
            "generated_at_utc": isoformat_utc(now_utc),
            "observation_hour_utc": observation_hour_utc(now_utc),
            "generated_at_local": local_now.replace(microsecond=0).isoformat(),
            "timezone": timezone_name,
            "timezone_abbreviation": local_now.tzname(),
            "cadence": "hourly",
            "producer": "scripts/ingest_crypto_sources.py",
        },
        "sources": {},
        "market": {"assets": []},
        "exchange_crosscheck": {"strategy": exchange_strategy(config), "selected": None, "sources": {}},
        "defi": {"total_tvl_usd": None, "stablecoins": []},
        "warnings": [],
        "errors": [],
    }

    for source_name, fetcher in (("coingecko", fetch_coingecko), ("defillama", fetch_defillama)):
        try:
            data, status = fetcher(config, timeout_seconds, max_retries)
        except SourceFetchError as exc:
            message = f"{source_name} fetch failed: {exc}"
            snapshot["sources"][source_name] = source_status("error", datetime.now(timezone.utc), message=message)
            snapshot["errors"].append(message)
            continue

        snapshot["sources"][source_name] = status
        if status.get("status") == "warning":
            snapshot["warnings"].append(f"{source_name} completed with warnings")

        if source_name == "coingecko":
            snapshot["market"].update(data)
        elif source_name == "defillama":
            snapshot["defi"].update(data)

    exchange_payload, exchange_statuses, exchange_warnings = fetch_exchange_crosschecks(config, timeout_seconds, max_retries)
    snapshot["exchange_crosscheck"].update(exchange_payload)
    snapshot["sources"].update(exchange_statuses)
    snapshot["warnings"].extend(exchange_warnings)
    snapshot["quality"] = classify_snapshot_quality(snapshot, config)

    return snapshot


def snapshot_path(output_root: Path, now_utc: datetime, timezone_name: str) -> Path:
    local_now = now_utc.astimezone(ZoneInfo(timezone_name))
    tz_name = local_now.tzname() or "LOCAL"
    safe_tz = "".join(ch for ch in tz_name if ch.isalnum()) or "LOCAL"
    return (
        output_root
        / f"{local_now.year:04d}"
        / f"{local_now.month:02d}"
        / f"{local_now.day:02d}"
        / f"{local_now.hour:02d}{local_now.minute:02d}_{safe_tz}_source_snapshot.json"
    )


def main() -> int:
    args = parse_args()
    config = load_config(Path(args.config))
    now = utc_now(args.now)
    snapshot = build_snapshot(config, now, args.timezone)
    output_path = snapshot_path(Path(args.output_root), now, args.timezone)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(output_path)
    if snapshot["errors"]:
        print(f"Snapshot written with {len(snapshot['errors'])} source error(s).", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
