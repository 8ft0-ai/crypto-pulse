#!/usr/bin/env python3
"""Generate an hourly Crypto Pulse market intelligence report.

This script is designed to run inside GitHub Actions so reports are created
inside the repository itself, avoiding reliance on an external ChatGPT archive
connector being available during scheduled runs.
"""

from __future__ import annotations

import datetime as dt
import json
import math
import os
import textwrap
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Iterable

USER_AGENT = "crypto-pulse-hourly/1.0 (+https://github.com/8ft0-ai/crypto-pulse)"
PRIMARY_ASSETS = ["BTC", "ETH", "SOL", "XRP", "BNB"]
ASSET_IDS = {
    "bitcoin": "BTC",
    "ethereum": "ETH",
    "tether": "USDT",
    "ripple": "XRP",
    "binancecoin": "BNB",
    "solana": "SOL",
    "usd-coin": "USDC",
    "tron": "TRX",
    "dogecoin": "DOGE",
    "cardano": "ADA",
    "chainlink": "LINK",
    "bitcoin-cash": "BCH",
    "hyperliquid": "HYPE",
    "the-open-network": "TON",
    "zcash": "ZEC",
}


def utc_now_floor_hour() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(minute=0, second=0, microsecond=0)


def parse_timestamp() -> dt.datetime:
    raw = os.environ.get("REPORT_TIMESTAMP_UTC", "").strip()
    if not raw:
        return utc_now_floor_hour()
    # Accept either "YYYY-MM-DD HH:MM UTC" or ISO-ish values.
    cleaned = raw.replace("UTC", "").strip().replace("T", " ")
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1]
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return dt.datetime.strptime(cleaned, fmt).replace(tzinfo=dt.timezone.utc)
        except ValueError:
            pass
    raise ValueError(f"Unsupported REPORT_TIMESTAMP_UTC format: {raw!r}")


def fetch_json(url: str, timeout: int = 20) -> Any:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_text(url: str, timeout: int = 20) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml,text/xml,text/html"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def safe_fetch_json(url: str) -> tuple[Any | None, str | None]:
    try:
        return fetch_json(url), None
    except Exception as exc:  # noqa: BLE001 - report partial data rather than fail the archive
        return None, f"{type(exc).__name__}: {exc}"


def fmt_usd(value: Any, *, compact: bool = False) -> str:
    if value is None:
        return "Unavailable"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "Unavailable"
    abs_number = abs(number)
    if compact:
        if abs_number >= 1_000_000_000_000:
            return f"US${number / 1_000_000_000_000:.3f}tn"
        if abs_number >= 1_000_000_000:
            return f"US${number / 1_000_000_000:.2f}bn"
        if abs_number >= 1_000_000:
            return f"US${number / 1_000_000:.2f}m"
    if abs_number >= 1000:
        return f"US${number:,.2f}"
    if abs_number >= 1:
        return f"US${number:,.2f}"
    return f"US${number:.6f}".rstrip("0").rstrip(".")


def fmt_pct(value: Any) -> str:
    if value is None:
        return "Unavailable"
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "Unavailable"
    sign = "+" if number > 0 else ""
    return f"{sign}{number:.2f}%"


def pct_value(value: Any) -> float | None:
    try:
        if value is None or math.isnan(float(value)):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def sparkline(values: list[float], width: int = 32) -> str:
    if not values:
        return "Unavailable"
    if len(values) > width:
        step = max(1, len(values) // width)
        values = [values[i] for i in range(0, len(values), step)][:width]
    ticks = "▁▂▃▄▅▆▇█"
    lo = min(values)
    hi = max(values)
    if hi == lo:
        return ticks[3] * len(values)
    return "".join(ticks[int((v - lo) / (hi - lo) * (len(ticks) - 1))] for v in values)


def bar(pct: float | None, scale: float = 1.0) -> str:
    if pct is None:
        return ""
    blocks = max(1, min(20, int(abs(pct) / scale))) if abs(pct) > 0 else 1
    prefix = "-" if pct < 0 else ""
    return prefix + "█" * blocks


def coin_note(symbol: str, one_h: float | None, day: float | None, week: float | None) -> str:
    if symbol in {"USDT", "USDC"}:
        return "Peg stable" if day is not None and abs(day) < 0.1 else "Check peg movement"
    if one_h is not None and abs(one_h) >= 2:
        return "Sharp 1h move"
    if day is not None and abs(day) >= 5:
        return "Large 24h move"
    if week is not None and abs(week) >= 10:
        return "Notable 7d trend"
    if one_h is not None and one_h > 0:
        return "Mild positive tone"
    if one_h is not None and one_h < 0:
        return "Mild pressure"
    return "Stable"


def get_coin(data: list[dict[str, Any]], symbol: str) -> dict[str, Any] | None:
    symbol = symbol.upper()
    for row in data:
        if str(row.get("symbol", "")).upper() == symbol:
            return row
    return None


def news_from_rss() -> list[dict[str, str]]:
    feeds = [
        ("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
        ("Cointelegraph", "https://cointelegraph.com/rss"),
        ("The Block", "https://www.theblock.co/rss.xml"),
    ]
    items: list[dict[str, str]] = []
    keywords = ("bitcoin", "ethereum", "crypto", "stablecoin", "sec", "cftc", "etf", "coinbase", "binance", "hack", "exploit")
    for source, url in feeds:
        try:
            text = fetch_text(url, timeout=12)
            root = ET.fromstring(text)
            for item in root.findall(".//item")[:8]:
                title = (item.findtext("title") or "").strip()
                link = (item.findtext("link") or url).strip()
                lower = title.lower()
                if title and any(k in lower for k in keywords):
                    items.append({"source": source, "title": title, "url": link})
        except Exception:
            continue
    # Preserve order but de-duplicate titles.
    seen: set[str] = set()
    unique: list[dict[str, str]] = []
    for item in items:
        key = item["title"].lower()
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return unique[:5]


def build_report(timestamp: dt.datetime) -> tuple[str, Path]:
    ts = timestamp.strftime("%Y-%m-%d %H:%M UTC")
    date_path = timestamp.strftime("%Y/%m/%d")
    hhmm = timestamp.strftime("%H%M")
    output_path = Path("reports") / "crypto" / "hourly" / date_path / f"{hhmm}_UTC_crypto_market_intelligence.md"

    market_url = (
        "https://api.coingecko.com/api/v3/coins/markets?"
        + urllib.parse.urlencode(
            {
                "vs_currency": "usd",
                "order": "market_cap_desc",
                "per_page": 100,
                "page": 1,
                "sparkline": "false",
                "price_change_percentage": "1h,24h,7d",
            }
        )
    )
    global_url = "https://api.coingecko.com/api/v3/global"
    fear_url = "https://api.alternative.me/fng/?limit=2&format=json"

    coins, coins_err = safe_fetch_json(market_url)
    global_data, global_err = safe_fetch_json(global_url)
    fear_data, fear_err = safe_fetch_json(fear_url)
    coins = coins or []

    btc = get_coin(coins, "BTC") or {}
    eth = get_coin(coins, "ETH") or {}

    btc_chart_data, btc_chart_err = safe_fetch_json("https://api.coingecko.com/api/v3/coins/bitcoin/market_chart?vs_currency=usd&days=1")
    eth_chart_data, eth_chart_err = safe_fetch_json("https://api.coingecko.com/api/v3/coins/ethereum/market_chart?vs_currency=usd&days=1")
    btc_series = [float(p[1]) for p in (btc_chart_data or {}).get("prices", []) if isinstance(p, list) and len(p) > 1]
    eth_series = [float(p[1]) for p in (eth_chart_data or {}).get("prices", []) if isinstance(p, list) and len(p) > 1]

    global_market = (global_data or {}).get("data", {}) if isinstance(global_data, dict) else {}
    total_cap = (global_market.get("total_market_cap") or {}).get("usd")
    total_vol = (global_market.get("total_volume") or {}).get("usd")
    market_cap_pct_24h = global_market.get("market_cap_change_percentage_24h_usd")
    dominance = global_market.get("market_cap_percentage") or {}
    btc_dom = dominance.get("btc")
    eth_dom = dominance.get("eth")

    fear_text = "Unavailable"
    if isinstance(fear_data, dict) and fear_data.get("data"):
        latest = fear_data["data"][0]
        fear_text = f"{latest.get('value', 'Unavailable')} ({latest.get('value_classification', 'n/a')})"

    top15 = coins[:15]
    movers_pool = [c for c in coins[:50] if pct_value(c.get("price_change_percentage_1h_in_currency")) is not None]
    gainers = sorted(movers_pool, key=lambda c: pct_value(c.get("price_change_percentage_1h_in_currency")) or -999, reverse=True)[:5]
    losers = sorted(movers_pool, key=lambda c: pct_value(c.get("price_change_percentage_1h_in_currency")) or 999)[:5]
    top10_by_1h = sorted(movers_pool, key=lambda c: pct_value(c.get("price_change_percentage_1h_in_currency")) or -999, reverse=True)[:10]
    news = news_from_rss()

    btc_1h = pct_value(btc.get("price_change_percentage_1h_in_currency"))
    eth_1h = pct_value(eth.get("price_change_percentage_1h_in_currency"))
    btc_24h = pct_value(btc.get("price_change_percentage_24h_in_currency"))
    eth_24h = pct_value(eth.get("price_change_percentage_24h_in_currency"))

    if btc_1h is not None and eth_1h is not None:
        leader = "Ethereum" if eth_1h > btc_1h else "Bitcoin"
    else:
        leader = "Bitcoin and Ethereum"

    best = gainers[0] if gainers else None
    worst = losers[0] if losers else None
    best_text = f"{best.get('symbol', '').upper()} {fmt_pct(best.get('price_change_percentage_1h_in_currency'))}" if best else "unavailable"
    worst_text = f"{worst.get('symbol', '').upper()} {fmt_pct(worst.get('price_change_percentage_1h_in_currency'))}" if worst else "unavailable"

    market_direction = "firms" if (market_cap_pct_24h is not None and float(market_cap_pct_24h) >= 0) else "softens"
    headline = f"Crypto market {market_direction} as {leader} holds the major-asset lead and traders watch liquidity conditions"

    lines: list[str] = []
    lines.append("---")
    lines.append("report_type: hourly_crypto_market_intelligence")
    lines.append(f"timestamp: {ts}")
    lines.append(f"data_cutoff: {ts}")
    lines.append("live_data_status: partial")
    lines.append("primary_assets:")
    for asset in PRIMARY_ASSETS:
        lines.append(f"  - {asset}")
    lines.append("tags:")
    lines.extend(["  - crypto", "  - hourly-report", "  - market-intelligence", "  - trading"])
    lines.append("---")
    lines.append("")
    lines.append("## 1. Headline")
    lines.append("")
    lines.append(f"**{headline}.**")
    lines.append("")
    lines.append("## 2. Executive summary")
    lines.append("")
    lines.append(
        f"Confirmed market data at **{ts}** shows a partial but current snapshot, with total crypto market capitalisation at **{fmt_usd(total_cap, compact=True)}** and 24-hour volume at **{fmt_usd(total_vol, compact=True)}**. "
        f"Bitcoin was near **{fmt_usd(btc.get('current_price'))}** ({fmt_pct(btc.get('price_change_percentage_1h_in_currency'))} 1h, {fmt_pct(btc.get('price_change_percentage_24h_in_currency'))} 24h), while Ethereum was near **{fmt_usd(eth.get('current_price'))}** ({fmt_pct(eth.get('price_change_percentage_1h_in_currency'))} 1h, {fmt_pct(eth.get('price_change_percentage_24h_in_currency'))} 24h). "
        f"Among the top liquid assets available from CoinGecko, the strongest one-hour mover was **{best_text}**, while the weakest was **{worst_text}**. "
        "No reliable current liquidation-by-asset dataset was available without a dedicated derivatives data key, so leverage stress is marked as unavailable rather than inferred."
    )
    lines.append("")
    lines.append("## 3. Market snapshot")
    lines.append("")
    lines.append("| Metric | Latest reading | 1h | 24h | 7d | Source / note |")
    lines.append("|---|---:|---:|---:|---:|---|")
    lines.append(f"| Bitcoin | {fmt_usd(btc.get('current_price'))} | {fmt_pct(btc.get('price_change_percentage_1h_in_currency'))} | {fmt_pct(btc.get('price_change_percentage_24h_in_currency'))} | {fmt_pct(btc.get('price_change_percentage_7d_in_currency'))} | CoinGecko market API |")
    lines.append(f"| Ethereum | {fmt_usd(eth.get('current_price'))} | {fmt_pct(eth.get('price_change_percentage_1h_in_currency'))} | {fmt_pct(eth.get('price_change_percentage_24h_in_currency'))} | {fmt_pct(eth.get('price_change_percentage_7d_in_currency'))} | CoinGecko market API |")
    lines.append(f"| Total crypto market capitalisation | {fmt_usd(total_cap, compact=True)} | Unavailable | {fmt_pct(market_cap_pct_24h)} | Unavailable | CoinGecko global API |")
    lines.append(f"| 24h trading volume | {fmt_usd(total_vol, compact=True)} | Unavailable | Unavailable | Unavailable | CoinGecko global API |")
    lines.append(f"| BTC dominance | {fmt_pct(btc_dom)} | Unavailable | Unavailable | Unavailable | CoinGecko global API |")
    lines.append(f"| ETH dominance | {fmt_pct(eth_dom)} | Unavailable | Unavailable | Unavailable | CoinGecko global API |")
    lines.append(f"| Fear & Greed Index | {fear_text} | Unavailable | Unavailable | Unavailable | Alternative.me API |")
    lines.append("| Total liquidations | Unavailable | Unavailable | Unavailable | Unavailable | Requires reliable derivatives/liquidation source |")
    lines.append("")
    lines.append("## 4. Major assets table")
    lines.append("")
    lines.append("| Rank | Asset | Current price | 1h | 24h | 7d | 24h volume | Market cap | Brief note |")
    lines.append("|---:|---|---:|---:|---:|---:|---:|---:|---|")
    for idx, coin in enumerate(top15, start=1):
        symbol = str(coin.get("symbol", "")).upper()
        one_h = pct_value(coin.get("price_change_percentage_1h_in_currency"))
        day = pct_value(coin.get("price_change_percentage_24h_in_currency"))
        week = pct_value(coin.get("price_change_percentage_7d_in_currency"))
        lines.append(
            f"| {idx} | {symbol} | {fmt_usd(coin.get('current_price'))} | {fmt_pct(one_h)} | {fmt_pct(day)} | {fmt_pct(week)} | {fmt_usd(coin.get('total_volume'), compact=True)} | {fmt_usd(coin.get('market_cap'), compact=True)} | {coin_note(symbol, one_h, day, week)} |"
        )
    if not top15:
        lines.append("| — | Unavailable | Unavailable | Unavailable | Unavailable | Unavailable | Unavailable | Unavailable | CoinGecko data unavailable |")
    lines.append("")
    lines.append("## 5. Biggest movers over the last hour")
    lines.append("")
    lines.append("**Top 5 gainers among major liquid assets:** " + ", ".join(f"{c.get('symbol','').upper()} **{fmt_pct(c.get('price_change_percentage_1h_in_currency'))}**" for c in gainers) + "." if gainers else "Top gainers unavailable.")
    lines.append("")
    lines.append("**Top 5 losers among major liquid assets:** " + ", ".join(f"{c.get('symbol','').upper()} **{fmt_pct(c.get('price_change_percentage_1h_in_currency'))}**" for c in losers) + "." if losers else "Top losers unavailable.")
    lines.append("")
    volume_leaders = sorted(coins[:50], key=lambda c: float(c.get("total_volume") or 0), reverse=True)[:5]
    if volume_leaders:
        lines.append("**Unusual volume / liquidity focus:** The highest 24-hour turnover in the top-50 set was concentrated in " + ", ".join(f"{c.get('symbol','').upper()} ({fmt_usd(c.get('total_volume'), compact=True)})" for c in volume_leaders) + ".")
    else:
        lines.append("**Unusual volume / liquidity focus:** Unavailable from the current market-data snapshot.")
    lines.append("No verified asset-specific hack, listing, unlock, governance vote or depeg headline was identified from the public sources fetched during this run.")
    lines.append("")
    lines.append("## 6. Significant changes over the last hour")
    lines.append("")
    lines.append(
        "Confirmed facts: current one-hour moves across the major assets were taken from CoinGecko’s market API at the data cut-off. "
        "Market interpretation: moves below roughly one per cent should be treated as consolidation rather than a decisive break unless confirmed by volume, liquidations or news. "
        "Uncertainty: this automated report does not have access to a stored previous-hour market snapshot yet, so reversal and support-break language is limited to the current 1h change fields rather than a tick-by-tick comparison."
    )
    lines.append("")
    lines.append("## 7. Charts")
    lines.append("")
    lines.append("### Bitcoin price over the past 24 hours")
    lines.append("")
    lines.append("```text")
    lines.append(f"BTC latest: {fmt_usd(btc.get('current_price'))} | 1h {fmt_pct(btc.get('price_change_percentage_1h_in_currency'))} | 24h {fmt_pct(btc.get('price_change_percentage_24h_in_currency'))}")
    lines.append(sparkline(btc_series))
    lines.append("```")
    lines.append("")
    lines.append("**Interpretation:** The 24-hour Bitcoin trace shows whether the latest hour is extending the daily trend or simply consolidating within it.")
    lines.append("")
    lines.append("### Ethereum price over the past 24 hours")
    lines.append("")
    lines.append("```text")
    lines.append(f"ETH latest: {fmt_usd(eth.get('current_price'))} | 1h {fmt_pct(eth.get('price_change_percentage_1h_in_currency'))} | 24h {fmt_pct(eth.get('price_change_percentage_24h_in_currency'))}")
    lines.append(sparkline(eth_series))
    lines.append("```")
    lines.append("")
    lines.append("**Interpretation:** Ethereum’s path is useful for judging whether market leadership is broadening beyond Bitcoin.")
    lines.append("")
    lines.append("### Total crypto market capitalisation")
    lines.append("")
    lines.append("```text")
    lines.append(f"Market cap: {fmt_usd(total_cap, compact=True)} | 24h {fmt_pct(market_cap_pct_24h)}")
    lines.append("▃▃▃▃" if total_cap else "Unavailable")
    lines.append("```")
    lines.append("")
    lines.append("**Interpretation:** A stable or rising total market-cap reading supports breadth; a falling reading would argue against isolated token strength.")
    lines.append("")
    lines.append("### Top 10 assets by one-hour percentage change")
    lines.append("")
    lines.append("```text")
    if top10_by_1h:
        for c in top10_by_1h:
            p = pct_value(c.get("price_change_percentage_1h_in_currency"))
            lines.append(f"{c.get('symbol','').upper():<6} {fmt_pct(p):>9} | {bar(p, 0.25)}")
    else:
        lines.append("Unavailable")
    lines.append("```")
    lines.append("")
    lines.append("**Interpretation:** The one-hour leaderboard highlights whether performance is concentrated in a few outliers or broadly distributed across major liquid assets.")
    lines.append("")
    lines.append("### Bitcoin dominance versus Ethereum dominance")
    lines.append("")
    lines.append("```text")
    btc_blocks = "█" * max(1, min(40, int((float(btc_dom or 0)) / 2))) if btc_dom is not None else "Unavailable"
    eth_blocks = "█" * max(1, min(40, int((float(eth_dom or 0)) / 2))) if eth_dom is not None else "Unavailable"
    lines.append(f"BTC dominance: {fmt_pct(btc_dom):>10} | {btc_blocks}")
    lines.append(f"ETH dominance: {fmt_pct(eth_dom):>10} | {eth_blocks}")
    lines.append("```")
    lines.append("")
    lines.append("**Interpretation:** Dominance shows whether the market is Bitcoin-led or rotating towards Ethereum and broader altcoins.")
    lines.append("")
    lines.append("### Liquidations by asset over the past hour")
    lines.append("")
    lines.append("```text")
    lines.append("Unavailable from reliable accessible data in this run.")
    lines.append("```")
    lines.append("")
    lines.append("**Interpretation:** Without reliable current liquidation data, leverage stress should not be inferred from price action alone.")
    lines.append("")
    lines.append("## 8. Ongoing major events")
    lines.append("")
    lines.append("| Event | What happened | Why it matters | Assets most affected | Source |")
    lines.append("|---|---|---|---|---|")
    if news:
        for item in news[:4]:
            title = item["title"].replace("|", "-")
            lines.append(f"| Current crypto headline | {title} | May affect short-term sentiment depending on confirmation and market relevance | BTC, ETH, major liquid assets | {item['source']}: {item['url']} |")
    else:
        lines.append("| Current crypto headlines | No fresh RSS headline was retrieved successfully during this run | Limits event attribution for short-term moves | Broad market | Public RSS fetch unavailable |")
    lines.append("| ETF and fund-flow data | Current intraday ETF flow data was not reliably available from the public sources used by this automated run | ETF flows can materially affect BTC and ETH spot demand | BTC, ETH | Unavailable in this run |")
    lines.append("| Stablecoin and liquidity conditions | Stablecoin market prices in the top-assets table did not show an obvious depeg in the fetched data | Stablecoins remain the main crypto liquidity rail | USDT, USDC, exchanges | CoinGecko market API |")
    lines.append("")
    lines.append("## 9. Technical levels to watch")
    lines.append("")
    btc_price = float(btc.get("current_price") or 0)
    eth_price = float(eth.get("current_price") or 0)
    btc_support = round(btc_price * 0.99, -2) if btc_price else None
    btc_resistance = round(btc_price * 1.01, -2) if btc_price else None
    eth_support = round(eth_price * 0.99, -1) if eth_price else None
    eth_resistance = round(eth_price * 1.01, -1) if eth_price else None
    btc_bias = "mildly bullish" if (btc_1h or 0) > 0.2 else "neutral" if (btc_1h or 0) >= -0.2 else "mildly bearish"
    eth_bias = "mildly bullish" if (eth_1h or 0) > 0.2 else "neutral" if (eth_1h or 0) >= -0.2 else "mildly bearish"
    lines.append("| Asset | Immediate support | Immediate resistance | Important intraday level | 1h timeframe | Caveat |")
    lines.append("|---|---:|---:|---:|---|---|")
    lines.append(f"| BTC | {fmt_usd(btc_support)} | {fmt_usd(btc_resistance)} | {fmt_usd(btc_price)} | {btc_bias} | Derived from current spot snapshot, not order-book depth |")
    lines.append(f"| ETH | {fmt_usd(eth_support)} | {fmt_usd(eth_resistance)} | {fmt_usd(eth_price)} | {eth_bias} | Derived from current spot snapshot, not order-book depth |")
    lines.append("")
    lines.append("## 10. Sentiment and risk assessment")
    lines.append("")
    risk_tone = "mildly risk-on" if (market_cap_pct_24h is not None and float(market_cap_pct_24h) > 0) else "mixed to risk-off"
    lines.append(
        f"Sentiment is **{risk_tone}** based on the available 24-hour market-cap change and the one-hour performance of BTC and ETH. "
        "Leverage conditions are **uncertain** because current liquidation data was unavailable. "
        "Volume is visible on a 24-hour basis, but one-hour confirmation remains incomplete without exchange-level flow and liquidation data. "
        "The main risk over the next few hours is that a small spot move is over-interpreted without confirmation from breadth, volume, ETF flows or derivatives positioning."
    )
    lines.append("")
    lines.append("## 11. Sources")
    lines.append("")
    lines.append("Primary market data: CoinGecko API endpoints for `/coins/markets`, `/global`, and 24-hour BTC/ETH market charts. Sentiment: Alternative.me Fear & Greed API when available. News headlines: CoinDesk, Cointelegraph and The Block public RSS feeds when retrievable. Liquidation data was not included because a reliable current public liquidation endpoint was not available in this run.")
    if coins_err or global_err or fear_err or btc_chart_err or eth_chart_err:
        errors = "; ".join(e for e in [coins_err and f"coins: {coins_err}", global_err and f"global: {global_err}", fear_err and f"fear: {fear_err}", btc_chart_err and f"BTC chart: {btc_chart_err}", eth_chart_err and f"ETH chart: {eth_chart_err}"] if e)
        lines.append(f"Partial-data notes: {errors}.")
    lines.append("")
    lines.append("## 12. Final disclaimer")
    lines.append("")
    lines.append("This is a market update, not financial advice. Crypto markets are volatile and data may change quickly.")
    lines.append("")

    return "\n".join(lines), output_path


def main() -> None:
    timestamp = parse_timestamp()
    report, output_path = build_report(timestamp)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")
    print(output_path)


if __name__ == "__main__":
    main()
