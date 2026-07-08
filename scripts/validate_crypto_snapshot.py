#!/usr/bin/env python3
"""Validate and classify CryptoPulse source snapshot JSON files."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

VALID_SOURCE_STATUSES = {"ok", "warning", "error", "skipped"}
VALID_QUALITY_STATUSES = {"valid-ok", "valid-degraded", "invalid"}
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
DEFAULT_REQUIRED_SOURCES = ["coingecko", "defillama"]


class ValidationError(ValueError):
    """Raised when a snapshot fails schema or quality validation."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate CryptoPulse source snapshot JSON files.")
    parser.add_argument(
        "path",
        help="Snapshot file or directory containing *_source_snapshot.json files.",
    )
    parser.add_argument(
        "--config",
        default="config/crypto_sources.yml",
        help="Optional YAML source-quality config used to classify snapshots.",
    )
    return parser.parse_args()


def load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        import yaml
    except ImportError:
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValidationError(f"config must contain a YAML mapping: {path}")
    return data


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


def normalise_timestamp(value: str) -> str:
    if value.endswith("Z"):
        return value[:-1] + "+00:00"
    return value


def parse_iso_timestamp(value: Any, path: str) -> datetime:
    text = normalise_timestamp(require_string(value, path))
    try:
        return datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValidationError(f"{path} must be an ISO-8601 timestamp") from exc


def validate_iso_timestamp(value: Any, path: str) -> None:
    parse_iso_timestamp(value, path)


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
    if "strategy" in exchange:
        require_string(exchange["strategy"], "exchange_crosscheck.strategy")
    if "selected" in exchange and exchange["selected"] is not None:
        require_string(exchange["selected"], "exchange_crosscheck.selected")
    if "sources" in exchange:
        sources = require_mapping(exchange["sources"], "exchange_crosscheck.sources")
        for source_name, rows in sources.items():
            require_list(rows, f"exchange_crosscheck.sources.{source_name}")
        return

    # Backwards compatibility for snapshots produced before the source-quality contract.
    if "binance" not in exchange:
        raise ValidationError("exchange_crosscheck.sources or exchange_crosscheck.binance is required")
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


def configured_required_sources(config: dict[str, Any]) -> list[str]:
    sources = config.get("sources") if isinstance(config, dict) else None
    required: list[str] = []
    if isinstance(sources, dict):
        for name, payload in sources.items():
            if isinstance(payload, dict) and bool(payload.get("required")):
                required.append(str(name))
    return required or DEFAULT_REQUIRED_SOURCES.copy()


def configured_exchange_sources(config: dict[str, Any]) -> list[dict[str, Any]]:
    exchange = config.get("exchange_crosschecks") if isinstance(config, dict) else None
    if not isinstance(exchange, dict):
        return []
    rows = exchange.get("sources")
    if not isinstance(rows, list):
        return []
    result: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row, dict) and row.get("name"):
            result.append(row)
    return result


def enabled_optional_exchange_sources(config: dict[str, Any]) -> list[str]:
    return [str(row["name"]) for row in configured_exchange_sources(config) if bool(row.get("enabled", True))]


def disabled_exchange_sources(config: dict[str, Any]) -> list[str]:
    return [str(row["name"]) for row in configured_exchange_sources(config) if not bool(row.get("enabled", True))]


def classify_snapshot_quality(snapshot: dict[str, Any], config: dict[str, Any] | None = None) -> dict[str, Any]:
    """Classify a structurally parsed snapshot as valid-ok, degraded, or invalid.

    This contract deliberately covers source criticality only. Deeper freshness and
    numeric sanity checks are layered on by the validator hardening issue.
    """

    config = config or {}
    sources = snapshot.get("sources") if isinstance(snapshot.get("sources"), dict) else {}
    required_sources = configured_required_sources(config)
    optional_exchange_sources = enabled_optional_exchange_sources(config)
    disabled_sources = disabled_exchange_sources(config)
    blocking_issues: list[str] = []
    non_blocking_warnings: list[str] = []

    for source_name in required_sources:
        payload = sources.get(source_name)
        if not isinstance(payload, dict):
            blocking_issues.append(f"required source missing: {source_name}")
            continue
        status = payload.get("status")
        if status != "ok":
            blocking_issues.append(f"required source {source_name} has status: {status}")

    if optional_exchange_sources:
        ok_sources = []
        for source_name in optional_exchange_sources:
            payload = sources.get(source_name)
            if not isinstance(payload, dict):
                non_blocking_warnings.append(f"optional exchange source missing: {source_name}")
                continue
            status = payload.get("status")
            if status == "ok":
                ok_sources.append(source_name)
            elif status in {"warning", "error", "skipped"}:
                non_blocking_warnings.append(f"optional exchange source {source_name} has status: {status}")
            else:
                non_blocking_warnings.append(f"optional exchange source {source_name} has unknown status: {status}")

        exchange_required = bool((config.get("exchange_crosschecks") or {}).get("required", False))
        if exchange_required and not ok_sources:
            blocking_issues.append("required exchange cross-check strategy had no successful source")
        elif not ok_sources:
            non_blocking_warnings.append("no optional exchange cross-check source succeeded")

    snapshot_errors = snapshot.get("errors")
    if isinstance(snapshot_errors, list):
        for item in snapshot_errors:
            text = str(item)
            if any(text.startswith(f"{source_name} ") for source_name in required_sources):
                blocking_issues.append(text)
            elif text:
                non_blocking_warnings.append(text)

    if blocking_issues:
        status = "invalid"
    elif non_blocking_warnings:
        status = "valid-degraded"
    else:
        status = "valid-ok"

    return {
        "status": status,
        "required_sources": required_sources,
        "optional_exchange_sources": optional_exchange_sources,
        "disabled_sources": disabled_sources,
        "blocking_issues": blocking_issues,
        "non_blocking_warnings": non_blocking_warnings,
    }


def validate_quality(snapshot: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    computed = classify_snapshot_quality(snapshot, config)
    embedded = snapshot.get("quality")
    if embedded is not None:
        payload = require_mapping(embedded, "quality")
        status = require_string(payload.get("status"), "quality.status")
        if status not in VALID_QUALITY_STATUSES:
            raise ValidationError(
                f"quality.status must be one of: {', '.join(sorted(VALID_QUALITY_STATUSES))}"
            )
        if status != computed["status"]:
            raise ValidationError(
                f"quality.status is {status}, but computed quality status is {computed['status']}"
            )
        require_list(payload.get("blocking_issues", []), "quality.blocking_issues")
        require_list(payload.get("non_blocking_warnings", []), "quality.non_blocking_warnings")
    if computed["status"] == "invalid":
        raise ValidationError("snapshot quality is invalid: " + "; ".join(computed["blocking_issues"]))
    return computed


def validate_snapshot(path: Path, config: dict[str, Any] | None = None) -> dict[str, Any]:
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
    return validate_quality(snapshot, config or {})


def iter_snapshot_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    if path.is_dir():
        return sorted(path.rglob("*_source_snapshot.json"))
    raise SystemExit(f"Path not found: {path}")


def main() -> int:
    args = parse_args()
    try:
        config = load_config(Path(args.config))
    except ValidationError as exc:
        print(f"{args.config}: {exc}", file=sys.stderr)
        return 1

    files = iter_snapshot_files(Path(args.path))
    if not files:
        print(f"No *_source_snapshot.json files found under {args.path}", file=sys.stderr)
        return 1

    failures: list[str] = []
    quality_counts = {status: 0 for status in sorted(VALID_QUALITY_STATUSES)}
    for path in files:
        try:
            quality = validate_snapshot(path, config)
        except ValidationError as exc:
            failures.append(f"{path}: {exc}")
            continue
        quality_counts[quality["status"]] += 1

    if failures:
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1

    quality_summary = ", ".join(f"{name}={count}" for name, count in sorted(quality_counts.items()) if count)
    print(f"Validated {len(files)} source snapshot file(s). Quality: {quality_summary or 'none'}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
