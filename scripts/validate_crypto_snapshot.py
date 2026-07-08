#!/usr/bin/env python3
"""Validate CryptoPulse source snapshot JSON files."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

VALID_SOURCE_STATUSES = {"ok", "warning", "error"}
REQUIRED_TOP_LEVEL_KEYS = {
    "schema_version",
    "run",
    "sources",
    "market",
    "exchange_crosscheck",
    "defi",
    "warnings",
    "errors",
}
REQUIRED_RUN_KEYS = {
    "generated_at_utc",
    "generated_at_local",
    "timezone",
    "cadence",
}


class ValidationError(ValueError):
    """Raised when a snapshot fails schema validation."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate CryptoPulse source snapshot JSON files.")
    parser.add_argument(
        "path",
        help="Snapshot file or directory containing *_source_snapshot.json files.",
    )
    return parser.parse_args()


def require_mapping(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValidationError(f"{path} must be an object")
    return value


def require_list(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValidationError(f"{path} must be a list")
    return value


def require_string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{path} must be a non-empty string")
    return value


def validate_iso_timestamp(value: Any, path: str) -> None:
    text = require_string(value, path)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValidationError(f"{path} must be an ISO-8601 timestamp") from exc


def validate_source_status(source_name: str, status_payload: Any) -> None:
    payload = require_mapping(status_payload, f"sources.{source_name}")
    status = require_string(payload.get("status"), f"sources.{source_name}.status")
    if status not in VALID_SOURCE_STATUSES:
        raise ValidationError(
            f"sources.{source_name}.status must be one of: {', '.join(sorted(VALID_SOURCE_STATUSES))}"
        )
    if "fetched_at_utc" in payload:
        validate_iso_timestamp(payload["fetched_at_utc"], f"sources.{source_name}.fetched_at_utc")


def validate_market(snapshot: dict[str, Any]) -> None:
    market = require_mapping(snapshot.get("market"), "market")
    assets = require_list(market.get("assets"), "market.assets")
    for index, asset in enumerate(assets):
        item = require_mapping(asset, f"market.assets[{index}]")
        require_string(item.get("id"), f"market.assets[{index}].id")
        require_string(item.get("symbol"), f"market.assets[{index}].symbol")
        if "price_usd" not in item:
            raise ValidationError(f"market.assets[{index}].price_usd is required")


def validate_exchange_crosscheck(snapshot: dict[str, Any]) -> None:
    exchange = require_mapping(snapshot.get("exchange_crosscheck"), "exchange_crosscheck")
    if "binance" not in exchange:
        raise ValidationError("exchange_crosscheck.binance is required")
    binance = require_list(exchange["binance"], "exchange_crosscheck.binance")
    for index, row in enumerate(binance):
        item = require_mapping(row, f"exchange_crosscheck.binance[{index}]")
        require_string(item.get("symbol"), f"exchange_crosscheck.binance[{index}].symbol")
        if "last_price" not in item:
            raise ValidationError(f"exchange_crosscheck.binance[{index}].last_price is required")


def validate_defi(snapshot: dict[str, Any]) -> None:
    defi = require_mapping(snapshot.get("defi"), "defi")
    if "total_tvl_usd" not in defi:
        raise ValidationError("defi.total_tvl_usd is required")
    require_list(defi.get("stablecoins"), "defi.stablecoins")


def validate_snapshot(path: Path) -> None:
    try:
        snapshot = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValidationError(f"invalid JSON: {exc}") from exc

    snapshot = require_mapping(snapshot, "$")
    missing = sorted(REQUIRED_TOP_LEVEL_KEYS - set(snapshot))
    if missing:
        raise ValidationError(f"missing top-level keys: {', '.join(missing)}")

    require_string(snapshot.get("schema_version"), "schema_version")

    run = require_mapping(snapshot.get("run"), "run")
    missing_run_keys = sorted(REQUIRED_RUN_KEYS - set(run))
    if missing_run_keys:
        raise ValidationError(f"missing run keys: {', '.join(missing_run_keys)}")
    validate_iso_timestamp(run["generated_at_utc"], "run.generated_at_utc")
    validate_iso_timestamp(run["generated_at_local"], "run.generated_at_local")
    require_string(run["timezone"], "run.timezone")
    require_string(run["cadence"], "run.cadence")

    sources = require_mapping(snapshot.get("sources"), "sources")
    if not sources:
        raise ValidationError("sources must include at least one source status")
    for source_name, status_payload in sources.items():
        validate_source_status(source_name, status_payload)

    validate_market(snapshot)
    validate_exchange_crosscheck(snapshot)
    validate_defi(snapshot)
    require_list(snapshot.get("warnings"), "warnings")
    require_list(snapshot.get("errors"), "errors")


def iter_snapshot_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    if path.is_dir():
        return sorted(path.rglob("*_source_snapshot.json"))
    raise SystemExit(f"Path not found: {path}")


def main() -> int:
    args = parse_args()
    files = iter_snapshot_files(Path(args.path))
    if not files:
        print(f"No *_source_snapshot.json files found under {args.path}", file=sys.stderr)
        return 1

    failures: list[str] = []
    for path in files:
        try:
            validate_snapshot(path)
        except ValidationError as exc:
            failures.append(f"{path}: {exc}")

    if failures:
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1

    print(f"Validated {len(files)} source snapshot file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
