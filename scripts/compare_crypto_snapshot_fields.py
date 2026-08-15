#!/usr/bin/env python3
"""Pure deterministic Phase 10 metric and source comparison adapters."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
import math
from typing import Any

MARKET_ASSET_ORDER = ("BTC", "ETH", "SOL")
MARKET_FIELDS = (
    "price_usd",
    "market_cap_usd",
    "volume_24h_usd",
    "change_1h_pct",
    "change_24h_pct",
    "change_7d_pct",
    "market_cap_rank",
)
STABLECOIN_ORDER = ("USDT", "USDC")
STABLECOIN_FIELDS = ("price_usd", "circulating_usd")
SOURCE_ORDER = (
    "coingecko",
    "defillama",
    "coinbase_exchange",
    "kraken",
    "okx",
    "binance",
    "bybit",
    "cryptocompare",
)
VALID_SOURCE_STATUSES = {"ok", "warning", "error", "skipped"}
SOURCE_EVIDENCE_STATUSES = VALID_SOURCE_STATUSES | {"missing"}

METRIC_ITEM_KEYS = {
    "family",
    "symbol",
    "field",
    "predecessor",
    "current",
    "comparison_state",
    "relation",
}
SIDE_KEYS = {"present", "value"}
SOURCE_ITEM_KEYS = {
    "source",
    "predecessor_status",
    "current_status",
    "predecessor_available",
    "current_available",
    "status_changed",
    "availability_change",
}


class ComparisonAdapterError(ValueError):
    """Raised when adapter evidence cannot be produced deterministically."""


def metric_specs() -> tuple[tuple[str, str | None, str, str], ...]:
    specs: list[tuple[str, str | None, str, str]] = []
    for symbol in MARKET_ASSET_ORDER:
        for field in MARKET_FIELDS:
            rule = "positive" if field in {"price_usd", "market_cap_usd"} else (
                "nonnegative" if field == "volume_24h_usd" else "finite"
            )
            specs.append(("market-asset", symbol, field, rule))
    specs.append(("defi-aggregate", None, "total_tvl_usd", "positive"))
    for symbol in STABLECOIN_ORDER:
        for field in STABLECOIN_FIELDS:
            specs.append(("stablecoin", symbol, field, "positive"))
    return tuple(specs)


METRIC_SPECS = metric_specs()


def _decimal_number(value: Any) -> tuple[float, Decimal] | None:
    if isinstance(value, bool) or value is None:
        return None
    if not isinstance(value, (int, float, str)):
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        accepted = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(accepted):
        return None
    try:
        number = Decimal(text)
    except (InvalidOperation, ValueError):
        return None
    return (accepted, number) if number.is_finite() else None


def metric_number(value: Any, rule: str) -> Decimal | None:
    parsed = _decimal_number(value)
    if parsed is None:
        return None
    accepted, number = parsed
    if rule == "positive" and not accepted > 0:
        return None
    if rule == "nonnegative" and not accepted >= 0:
        return None
    if rule not in {"positive", "nonnegative", "finite"}:
        raise ComparisonAdapterError(f"unknown numeric rule: {rule}")
    return number


def classify_metric_evidence(
    current_present: bool,
    current_value: Any,
    predecessor_present: bool,
    predecessor_value: Any,
    rule: str,
) -> tuple[str, str | None]:
    if not current_present:
        return "unavailable-current", None
    if not predecessor_present:
        return "unavailable-predecessor", None

    current_number = metric_number(current_value, rule)
    predecessor_number = metric_number(predecessor_value, rule)
    if current_number is None:
        return "invalid-current", None
    if predecessor_number is None:
        return "invalid-predecessor", None

    if current_number > predecessor_number:
        return "comparable", "current-greater"
    if current_number < predecessor_number:
        return "comparable", "current-less"
    return "comparable", "equal"


def _rows_by_symbol(snapshot: dict[str, Any], family: str) -> dict[str, dict[str, Any]]:
    if family == "market-asset":
        parent = snapshot.get("market")
        rows = parent.get("assets") if isinstance(parent, dict) else None
    elif family == "stablecoin":
        parent = snapshot.get("defi")
        rows = parent.get("stablecoins") if isinstance(parent, dict) else None
    else:
        raise ComparisonAdapterError(f"unsupported row family: {family}")

    if not isinstance(rows, list):
        return {}
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        symbol = row.get("symbol")
        if not isinstance(symbol, str) or not symbol.strip():
            continue
        key = symbol.strip().upper()
        if key in result:
            raise ComparisonAdapterError(f"duplicate semantic identity: {family}:{key}")
        result[key] = row
    return result


def _metric_container(
    snapshot: dict[str, Any],
    family: str,
    symbol: str | None,
) -> dict[str, Any]:
    if family == "market-asset":
        return _rows_by_symbol(snapshot, family).get(symbol or "", {})
    if family == "stablecoin":
        return _rows_by_symbol(snapshot, family).get(symbol or "", {})
    if family == "defi-aggregate":
        defi = snapshot.get("defi")
        return defi if isinstance(defi, dict) else {}
    raise ComparisonAdapterError(f"unsupported metric family: {family}")


def build_metric_evidence(
    current_snapshot: dict[str, Any],
    predecessor_snapshot: dict[str, Any],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for family, symbol, field, rule in METRIC_SPECS:
        current_container = _metric_container(current_snapshot, family, symbol)
        predecessor_container = _metric_container(predecessor_snapshot, family, symbol)
        current_present = field in current_container
        predecessor_present = field in predecessor_container
        current_value = current_container.get(field) if current_present else None
        predecessor_value = predecessor_container.get(field) if predecessor_present else None
        state, relation = classify_metric_evidence(
            current_present,
            current_value,
            predecessor_present,
            predecessor_value,
            rule,
        )
        output.append(
            {
                "family": family,
                "symbol": symbol,
                "field": field,
                "predecessor": {
                    "present": predecessor_present,
                    "value": predecessor_value,
                },
                "current": {
                    "present": current_present,
                    "value": current_value,
                },
                "comparison_state": state,
                "relation": relation,
            }
        )
    return output


def source_status(snapshot: dict[str, Any], source: str) -> str:
    sources = snapshot.get("sources")
    if not isinstance(sources, dict) or source not in sources:
        return "missing"
    payload = sources[source]
    if not isinstance(payload, dict):
        raise ComparisonAdapterError(f"source {source} payload must be an object")
    status = payload.get("status")
    if status not in VALID_SOURCE_STATUSES:
        raise ComparisonAdapterError(f"source {source} status is invalid")
    return status


def build_source_evidence(
    current_snapshot: dict[str, Any],
    predecessor_snapshot: dict[str, Any],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for source in SOURCE_ORDER:
        predecessor_status = source_status(predecessor_snapshot, source)
        current_status = source_status(current_snapshot, source)
        predecessor_available = predecessor_status == "ok"
        current_available = current_status == "ok"
        if not predecessor_available and current_available:
            availability_change = "gained"
        elif predecessor_available and not current_available:
            availability_change = "lost"
        else:
            availability_change = "unchanged"
        output.append(
            {
                "source": source,
                "predecessor_status": predecessor_status,
                "current_status": current_status,
                "predecessor_available": predecessor_available,
                "current_available": current_available,
                "status_changed": predecessor_status != current_status,
                "availability_change": availability_change,
            }
        )
    return output


def build_metric_and_source_evidence(
    current_snapshot: dict[str, Any],
    predecessor_snapshot: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    return (
        build_metric_evidence(current_snapshot, predecessor_snapshot),
        build_source_evidence(current_snapshot, predecessor_snapshot),
    )
