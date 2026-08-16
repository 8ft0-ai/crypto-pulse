#!/usr/bin/env python3
"""Deterministic Phase 13 observation-hour temporal-series construction and validation."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from build_crypto_observation_hour_comparison_record import (
    COMPARISON_SCHEMA_VERSION,
    build_observation_hour_comparison,
)
from resolve_crypto_observation_hour_adjacency import (
    ADJACENCY_POLICY_VERSION,
    OBSERVATION_HOUR_CONTRACT_VERSION,
    SEMANTIC_CONTRACT_VERSION,
)

SERIES_SCHEMA_VERSION = "crypto-observation-hour-series/v1"
MAX_SLOTS = 168
LOWER_HEX_64 = re.compile(r"^[0-9a-f]{64}$")
CANONICAL_HOUR = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:00:00Z$")

METRIC_IDENTITIES = {
    "BTC.price_usd": ("market-asset", "BTC", "price_usd"),
    "BTC.market_cap_usd": ("market-asset", "BTC", "market_cap_usd"),
    "BTC.volume_24h_usd": ("market-asset", "BTC", "volume_24h_usd"),
    "ETH.price_usd": ("market-asset", "ETH", "price_usd"),
    "ETH.market_cap_usd": ("market-asset", "ETH", "market_cap_usd"),
    "ETH.volume_24h_usd": ("market-asset", "ETH", "volume_24h_usd"),
    "SOL.price_usd": ("market-asset", "SOL", "price_usd"),
    "SOL.market_cap_usd": ("market-asset", "SOL", "market_cap_usd"),
    "SOL.volume_24h_usd": ("market-asset", "SOL", "volume_24h_usd"),
    "defi.total_tvl_usd": ("defi-aggregate", None, "total_tvl_usd"),
    "USDT.circulating_usd": ("stablecoin", "USDT", "circulating_usd"),
    "USDC.circulating_usd": ("stablecoin", "USDC", "circulating_usd"),
}
SOURCE_IDENTITIES = (
    "coingecko",
    "defillama",
    "coinbase_exchange",
    "kraken",
    "okx",
    "binance",
    "bybit",
    "cryptocompare",
)
SOURCE_STATUSES = {"ok", "warning", "error", "skipped", "missing"}
COMPARISON_GAP_MAP = {
    status: f"phase13-{status}"
    for status in (
        "validation-contract-mismatch",
        "candidate-set-unorderable",
        "current-missing",
        "current-ambiguous",
        "current-identity-invalid",
        "current-invalid",
        "predecessor-missing",
        "predecessor-ambiguous",
        "predecessor-identity-invalid",
        "predecessor-invalid",
        "pair-schema-incompatible",
        "pair-semantics-incompatible",
    )
}
METRIC_GAP_MAP = {
    "unavailable-current": "metric-unavailable-current",
    "unavailable-predecessor": "metric-unavailable-predecessor",
    "invalid-current": "metric-invalid-current",
    "invalid-predecessor": "metric-invalid-predecessor",
}
GAP_REASONS = set(COMPARISON_GAP_MAP.values()) | set(METRIC_GAP_MAP.values())
CONTINUITY_STATUSES = {"window-start", "continuous", "discontinuous", "unavailable"}

TOP_LEVEL_KEYS = {
    "schema_version",
    "series_kind",
    "series_key",
    "window",
    "repository_context",
    "phase13",
    "entries",
    "series_id",
}
ENTRY_KEYS = {"slot_utc", "value", "gap", "continuity"}
VALUE_KEYS = {"datum", "comparison", "evidence"}
GAP_KEYS = {"reason", "comparison", "metric_evidence"}
CONTINUITY_KEYS = {"status", "previous_current", "current_predecessor"}


class ObservationHourSeriesError(ValueError):
    """Raised when a Phase 13 observation-hour series is invalid."""


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def series_id_for_record(record: dict[str, Any]) -> str:
    payload = copy.deepcopy(record)
    payload.pop("series_id", None)
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def _canonical_hour(value: Any, path: str) -> tuple[datetime, str]:
    if not isinstance(value, str) or CANONICAL_HOUR.fullmatch(value) is None:
        raise ObservationHourSeriesError(
            f"{path} must use canonical YYYY-MM-DDTHH:00:00Z"
        )
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00").astimezone(timezone.utc)
    except ValueError as exc:
        raise ObservationHourSeriesError(f"{path} is not a valid UTC hour") from exc
    canonical = parsed.isoformat().replace("+00:00", "Z")
    if canonical != value:
        raise ObservationHourSeriesError(f"{path} is not canonical")
    return parsed, canonical


def _window(start_utc: str, end_utc: str) -> tuple[str, str, list[str]]:
    start, start_text = _canonical_hour(start_utc, "window.start_utc")
    end, end_text = _canonical_hour(end_utc, "window.end_utc")
    if end < start:
        raise ObservationHourSeriesError(
            "window.end_utc must not precede window.start_utc"
        )
    count = int((end - start).total_seconds()) // 3600 + 1
    if count < 1 or count > MAX_SLOTS:
        raise ObservationHourSeriesError(
            f"window must contain between 1 and {MAX_SLOTS} hourly slots"
        )
    slots = [
        (start + timedelta(hours=index)).isoformat().replace("+00:00", "Z")
        for index in range(count)
    ]
    return start_text, end_text, slots


def _series_identity(series_kind: str, series_key: str) -> None:
    if series_kind == "metric" and series_key in METRIC_IDENTITIES:
        return
    if series_kind == "source-status" and series_key in SOURCE_IDENTITIES:
        return
    raise ObservationHourSeriesError("unsupported series kind/key")


def _metric_evidence(record: dict[str, Any], series_key: str) -> dict[str, Any]:
    target = METRIC_IDENTITIES[series_key]
    matches = [
        item
        for item in record.get("metric_comparisons", [])
        if isinstance(item, dict)
        and (item.get("family"), item.get("symbol"), item.get("field")) == target
    ]
    if len(matches) != 1:
        raise ObservationHourSeriesError("Phase 13 metric evidence identity mismatch")
    return copy.deepcopy(matches[0])


def _source_evidence(record: dict[str, Any], series_key: str) -> dict[str, Any]:
    matches = [
        item
        for item in record.get("source_availability_changes", [])
        if isinstance(item, dict) and item.get("source") == series_key
    ]
    if len(matches) != 1:
        raise ObservationHourSeriesError("Phase 13 source evidence identity mismatch")
    return copy.deepcopy(matches[0])


def _continuity(
    index: int,
    previous: dict[str, Any] | None,
    current: dict[str, Any],
) -> dict[str, Any]:
    if index == 0:
        return {
            "status": "window-start",
            "previous_current": None,
            "current_predecessor": None,
        }
    previous_current = (
        copy.deepcopy(previous.get("current")) if isinstance(previous, dict) else None
    )
    current_predecessor = copy.deepcopy(current.get("predecessor"))
    if previous_current is None or current_predecessor is None:
        status = "unavailable"
    elif previous_current == current_predecessor:
        status = "continuous"
    else:
        status = "discontinuous"
    return {
        "status": status,
        "previous_current": previous_current,
        "current_predecessor": current_predecessor,
    }


def _entry(
    series_kind: str,
    series_key: str,
    slot_utc: str,
    comparison: dict[str, Any],
    continuity: dict[str, Any],
) -> dict[str, Any]:
    status = comparison.get("comparison_status")
    if status != "comparison-available":
        reason = COMPARISON_GAP_MAP.get(status)
        if reason is None:
            raise ObservationHourSeriesError(
                f"unsupported Phase 13 comparison status: {status!r}"
            )
        return {
            "slot_utc": slot_utc,
            "value": None,
            "gap": {
                "reason": reason,
                "comparison": copy.deepcopy(comparison),
                "metric_evidence": None,
            },
            "continuity": continuity,
        }

    if series_kind == "metric":
        evidence = _metric_evidence(comparison, series_key)
        state = evidence.get("comparison_state")
        if state != "comparable":
            reason = METRIC_GAP_MAP.get(state)
            if reason is None:
                raise ObservationHourSeriesError(
                    f"unsupported metric state: {state!r}"
                )
            return {
                "slot_utc": slot_utc,
                "value": None,
                "gap": {
                    "reason": reason,
                    "comparison": copy.deepcopy(comparison),
                    "metric_evidence": evidence,
                },
                "continuity": continuity,
            }
        datum = copy.deepcopy(evidence["current"]["value"])
    else:
        evidence = _source_evidence(comparison, series_key)
        datum = evidence.get("current_status")
        if datum not in SOURCE_STATUSES:
            raise ObservationHourSeriesError(
                f"unsupported source status: {datum!r}"
            )

    return {
        "slot_utc": slot_utc,
        "value": {
            "datum": datum,
            "comparison": copy.deepcopy(comparison),
            "evidence": evidence,
        },
        "gap": None,
        "continuity": continuity,
    }


def build_observation_hour_series(
    repository_root: Path,
    commit_sha: str,
    series_kind: str,
    series_key: str,
    start_utc: str,
    end_utc: str,
) -> dict[str, Any]:
    """Build one canonical crypto-observation-hour-series/v1 record."""
    _series_identity(series_kind, series_key)
    start_text, end_text, slots = _window(start_utc, end_utc)
    root = Path(repository_root).resolve()

    comparisons = [
        build_observation_hour_comparison(root, commit_sha, slot) for slot in slots
    ]
    if not comparisons or not isinstance(
        comparisons[0].get("repository_context"), dict
    ):
        raise ObservationHourSeriesError("repository comparison context is unavailable")
    context = copy.deepcopy(comparisons[0]["repository_context"])
    for comparison in comparisons:
        if comparison.get("repository_context") != context:
            raise ObservationHourSeriesError(
                "comparison repository context changed within window"
            )

    entries: list[dict[str, Any]] = []
    previous: dict[str, Any] | None = None
    for index, (slot, comparison) in enumerate(zip(slots, comparisons)):
        continuity = _continuity(index, previous, comparison)
        entries.append(
            _entry(series_kind, series_key, slot, comparison, continuity)
        )
        previous = comparison

    record: dict[str, Any] = {
        "schema_version": SERIES_SCHEMA_VERSION,
        "series_kind": series_kind,
        "series_key": series_key,
        "window": {"start_utc": start_text, "end_utc": end_text},
        "repository_context": context,
        "phase13": {
            "comparison_schema_version": COMPARISON_SCHEMA_VERSION,
            "adjacency_policy_version": ADJACENCY_POLICY_VERSION,
            "observation_hour_contract_version": OBSERVATION_HOUR_CONTRACT_VERSION,
            "semantic_contract_version": SEMANTIC_CONTRACT_VERSION,
        },
        "entries": entries,
        "series_id": "",
    }
    record["series_id"] = series_id_for_record(record)
    return record


def _validate_json_native(value: Any, path: str = "$") -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ObservationHourSeriesError(f"{path} contains a non-finite number")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_json_native(item, f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ObservationHourSeriesError(
                    f"{path} contains a non-string key"
                )
            _validate_json_native(item, f"{path}.{key}")
        return
    raise ObservationHourSeriesError(f"{path} contains a non-JSON-native value")


def validate_observation_hour_series(
    repository_root: Path,
    record: Any,
) -> dict[str, Any]:
    """Validate exact shape, vocabulary, continuity and immutable replay."""
    _validate_json_native(record)
    if not isinstance(record, dict) or set(record) != TOP_LEVEL_KEYS:
        raise ObservationHourSeriesError(
            "top-level keys do not match frozen v1 contract"
        )
    _series_identity(record.get("series_kind"), record.get("series_key"))
    window = record.get("window")
    if not isinstance(window, dict) or set(window) != {"start_utc", "end_utc"}:
        raise ObservationHourSeriesError("window keys mismatch")
    start_text, end_text, slots = _window(
        window.get("start_utc"), window.get("end_utc")
    )
    if record.get("schema_version") != SERIES_SCHEMA_VERSION:
        raise ObservationHourSeriesError("schema_version mismatch")
    expected_phase13 = {
        "comparison_schema_version": COMPARISON_SCHEMA_VERSION,
        "adjacency_policy_version": ADJACENCY_POLICY_VERSION,
        "observation_hour_contract_version": OBSERVATION_HOUR_CONTRACT_VERSION,
        "semantic_contract_version": SEMANTIC_CONTRACT_VERSION,
    }
    if record.get("phase13") != expected_phase13:
        raise ObservationHourSeriesError("Phase 13 contract version mismatch")
    entries = record.get("entries")
    if not isinstance(entries, list) or len(entries) != len(slots):
        raise ObservationHourSeriesError(
            "entries must contain exactly one item per slot"
        )
    for index, (entry, slot) in enumerate(zip(entries, slots)):
        if not isinstance(entry, dict) or set(entry) != ENTRY_KEYS:
            raise ObservationHourSeriesError(f"entries[{index}] keys mismatch")
        if entry.get("slot_utc") != slot:
            raise ObservationHourSeriesError(
                f"entries[{index}].slot_utc mismatch"
            )
        if (entry.get("value") is None) == (entry.get("gap") is None):
            raise ObservationHourSeriesError(
                f"entries[{index}] must contain exactly one of value or gap"
            )
        continuity = entry.get("continuity")
        if not isinstance(continuity, dict) or set(continuity) != CONTINUITY_KEYS:
            raise ObservationHourSeriesError(
                f"entries[{index}].continuity keys mismatch"
            )
        if continuity.get("status") not in CONTINUITY_STATUSES:
            raise ObservationHourSeriesError(
                f"entries[{index}].continuity status invalid"
            )
        if entry.get("value") is not None:
            if not isinstance(entry["value"], dict) or set(entry["value"]) != VALUE_KEYS:
                raise ObservationHourSeriesError(
                    f"entries[{index}].value keys mismatch"
                )
        else:
            gap = entry["gap"]
            if (
                not isinstance(gap, dict)
                or set(gap) != GAP_KEYS
                or gap.get("reason") not in GAP_REASONS
            ):
                raise ObservationHourSeriesError(
                    f"entries[{index}].gap invalid"
                )
    if (
        not isinstance(record.get("series_id"), str)
        or LOWER_HEX_64.fullmatch(record["series_id"]) is None
    ):
        raise ObservationHourSeriesError("series_id must be lower-case SHA-256")
    if record["series_id"] != series_id_for_record(record):
        raise ObservationHourSeriesError("series_id mismatch")

    context = record.get("repository_context")
    if not isinstance(context, dict) or not isinstance(context.get("commit_sha"), str):
        raise ObservationHourSeriesError("repository_context is invalid")
    expected = build_observation_hour_series(
        Path(repository_root),
        context["commit_sha"],
        record["series_kind"],
        record["series_key"],
        start_text,
        end_text,
    )
    if canonical_json_bytes(record) != canonical_json_bytes(expected):
        raise ObservationHourSeriesError(
            "series does not match immutable Phase 13 replay"
        )
    return record
