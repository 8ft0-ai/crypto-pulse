#!/usr/bin/env python3
"""Generate deterministic Markdown reports from validated CryptoPulse snapshots.

This script intentionally uses only one validated snapshot. It does not call an
LLM, fetch live sources, rebuild `_site/`, or publish output.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from validate_crypto_snapshot import ValidationError, load_config, validate_snapshot

REPORT_SCHEMA_VERSION = "deterministic-crypto-report/v1"
DEFAULT_CONFIG_PATH = Path("config/crypto_sources.yml")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate one deterministic crypto Markdown report from one validated snapshot.")
    parser.add_argument("--snapshot", required=True, help="Path to a source snapshot JSON file.")
    parser.add_argument("--output-root", default="reports/crypto", help="Root directory for generated raw Markdown reports.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH), help="Snapshot validation config path.")
    return parser.parse_args()


def load_snapshot(snapshot_path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValidationError(f"invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValidationError("snapshot root must be an object")
    return payload


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def safe_text(value: Any, fallback: str = "not recorded") -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text if text else fallback


def yaml_quote(value: Any) -> str:
    text = safe_text(value, "")
    escaped = text.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def yaml_scalar(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    return yaml_quote(value)


def yaml_list(name: str, values: list[Any]) -> list[str]:
    lines = [f"{name}:"]
    if not values:
        lines.append("  []")
        return lines
    for value in values:
        lines.append(f"  - {yaml_quote(value)}")
    return lines


def num(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out


def money(value: Any) -> str:
    amount = num(value)
    if amount is None:
        return "not recorded"
    return f"{amount:,.2f}"


def integer_money(value: Any) -> str:
    amount = num(value)
    if amount is None:
        return "not recorded"
    return f"{amount:,.0f}"


def percent(value: Any) -> str:
    amount = num(value)
    if amount is None:
        return "not recorded"
    return f"{amount:.2f}%"


def source_status(snapshot: dict[str, Any], name: str) -> str:
    payload = as_dict(as_dict(snapshot.get("sources")).get(name))
    return safe_text(payload.get("status"), "missing")


def bullet_list(values: list[Any]) -> str:
    if not values:
        return "- None recorded."
    return "\n".join(f"- {safe_text(value)}" for value in values)


def front_matter(snapshot: dict[str, Any], snapshot_path: Path, quality: dict[str, Any]) -> str:
    run = as_dict(snapshot.get("run"))
    exchange = as_dict(snapshot.get("exchange_crosscheck"))
    lines = ["---"]
    scalar_fields: list[tuple[str, Any]] = [
        ("schema_version", REPORT_SCHEMA_VERSION),
        ("report_type", "crypto_market_snapshot"),
        ("source_snapshot", snapshot_path.as_posix()),
        ("generated_at_utc", run.get("generated_at_utc")),
        ("generated_at_local", run.get("generated_at_local")),
        ("timezone", run.get("timezone")),
        ("timezone_abbreviation", run.get("timezone_abbreviation")),
        ("cadence", run.get("cadence")),
        ("quality_status", quality.get("status")),
    ]
    for key, value in scalar_fields:
        lines.append(f"{key}: {yaml_scalar(value)}")
    lines.extend(yaml_list("required_sources", [str(value) for value in as_list(quality.get("required_sources"))]))
    lines.extend(yaml_list("optional_exchange_sources", [str(value) for value in as_list(quality.get("optional_exchange_sources"))]))
    lines.append(f"selected_exchange_crosscheck: {yaml_scalar(exchange.get('selected'))}")
    lines.extend(yaml_list("disabled_sources", [str(value) for value in as_list(quality.get("disabled_sources"))]))
    lines.append("no_investment_advice: true")
    lines.append("llm_generated: false")
    lines.append("---")
    return "\n".join(lines)


def report_output_path(snapshot: dict[str, Any], snapshot_path: Path, output_root: Path) -> Path:
    run = as_dict(snapshot.get("run"))
    local_text = safe_text(run.get("generated_at_local"), "")
    try:
        local_dt = datetime.fromisoformat(local_text)
    except ValueError:
        local_dt = None
    if local_dt is not None:
        year = f"{local_dt.year:04d}"
        month = f"{local_dt.month:02d}"
        day = f"{local_dt.day:02d}"
    else:
        parts = snapshot_path.parts
        year, month, day = parts[-4], parts[-3], parts[-2]
    stem = snapshot_path.stem
    if stem.endswith("_source_snapshot"):
        stem = stem.removesuffix("_source_snapshot")
    return output_root / year / month / day / f"{stem}.md"


def title(snapshot: dict[str, Any]) -> str:
    run = as_dict(snapshot.get("run"))
    local_text = safe_text(run.get("generated_at_local"), "")
    tz = safe_text(run.get("timezone_abbreviation"), "local time")
    try:
        local_dt = datetime.fromisoformat(local_text)
        return f"# Crypto market evidence snapshot — {local_dt.day} {local_dt.strftime('%B %Y')}, {local_dt.hour:02d}:{local_dt.minute:02d} {tz}"
    except ValueError:
        return "# Crypto market evidence snapshot"


def market_section(snapshot: dict[str, Any]) -> str:
    assets = as_list(as_dict(snapshot.get("market")).get("assets"))
    rows = [
        "## Market summary",
        "",
        "| Asset | Price USD | 1h | 24h | 7d | Market cap USD | 24h volume USD | Rank | Updated |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for asset in assets:
        item = as_dict(asset)
        rows.append(
            "| {symbol} | {price} | {h1} | {h24} | {d7} | {cap} | {volume} | {rank} | {updated} |".format(
                symbol=safe_text(item.get("symbol")),
                price=money(item.get("price_usd")),
                h1=percent(item.get("change_1h_pct")),
                h24=percent(item.get("change_24h_pct")),
                d7=percent(item.get("change_7d_pct")),
                cap=integer_money(item.get("market_cap_usd")),
                volume=integer_money(item.get("volume_24h_usd")),
                rank=safe_text(item.get("market_cap_rank")),
                updated=safe_text(item.get("last_updated")),
            )
        )
    rows.extend([
        "",
        "This section records the validated snapshot values only. It does not infer entry points, exit points, targets, or trade direction.",
    ])
    return "\n".join(rows)


def defi_section(snapshot: dict[str, Any]) -> str:
    defi = as_dict(snapshot.get("defi"))
    rows = [
        "## DeFi and stablecoin summary",
        "",
        f"Total DeFi TVL: USD {integer_money(defi.get('total_tvl_usd'))}.",
        "",
        "| Stablecoin | Price USD | Circulating USD |",
        "| --- | ---: | ---: |",
    ]
    for coin in as_list(defi.get("stablecoins")):
        item = as_dict(coin)
        rows.append(
            f"| {safe_text(item.get('symbol'))} | {money(item.get('price_usd'))} | {integer_money(item.get('circulating_usd'))} |"
        )
    return "\n".join(rows)


def exchange_section(snapshot: dict[str, Any], quality: dict[str, Any]) -> str:
    exchange = as_dict(snapshot.get("exchange_crosscheck"))
    selected = exchange.get("selected")
    sources = as_dict(exchange.get("sources"))
    rows = [
        "## Exchange cross-check summary",
        "",
        f"Strategy: `{safe_text(exchange.get('strategy'))}`",
        "",
        f"Selected exchange cross-check: `{safe_text(selected, 'none')}`",
        "",
        "| Source | Status | Notes |",
        "| --- | --- | --- |",
    ]
    configured = [str(value) for value in as_list(quality.get("optional_exchange_sources"))]
    for name in configured:
        status_payload = as_dict(as_dict(snapshot.get("sources")).get(name))
        rows.append(f"| {name} | {safe_text(status_payload.get('status'))} | {safe_text(status_payload.get('reason') or status_payload.get('message'), '')} |")
    disabled = [str(value) for value in as_list(quality.get("disabled_sources"))]
    for name in disabled:
        status_payload = as_dict(as_dict(snapshot.get("sources")).get(name))
        rows.append(f"| {name} | {safe_text(status_payload.get('status'), 'disabled')} | {safe_text(status_payload.get('reason'), '')} |")

    selected_rows = as_list(sources.get(str(selected))) if selected else []
    if selected_rows:
        rows.extend([
            "",
            "Selected exchange rows:",
            "",
            "| Asset | Pair | Quote | Price |",
            "| --- | --- | --- | ---: |",
        ])
        for item in selected_rows:
            row = as_dict(item)
            rows.append(
                f"| {safe_text(row.get('symbol'))} | {safe_text(row.get('pair'))} | {safe_text(row.get('quote'))} | {money(row.get('price'))} |"
            )
    return "\n".join(rows)


def quality_section(snapshot: dict[str, Any], quality: dict[str, Any]) -> str:
    status = safe_text(quality.get("status"))
    required = [str(value) for value in as_list(quality.get("required_sources"))]
    optional = [str(value) for value in as_list(quality.get("optional_exchange_sources"))]
    lines = [
        "## Snapshot quality",
        "",
        f"Status: `{status}`",
        "",
    ]
    if status == "valid-degraded":
        lines.extend(["This report is visibly degraded. Required sources validated, but non-blocking warnings remain.", ""])
    lines.extend(["Required sources:"])
    lines.extend(f"- `{name}`: `{source_status(snapshot, name)}`" for name in required)
    lines.extend(["", "Optional exchange sources:"])
    lines.extend(f"- `{name}`: `{source_status(snapshot, name)}`" for name in optional)
    lines.extend([
        "",
        "Blocking issues:",
        bullet_list(as_list(quality.get("blocking_issues"))),
        "",
        "Non-blocking warnings:",
        bullet_list(as_list(quality.get("non_blocking_warnings"))),
    ])
    return "\n".join(lines)


def evidence_section(snapshot: dict[str, Any], snapshot_path: Path) -> str:
    lines = [
        "## Evidence and source status",
        "",
        f"Source snapshot: `{snapshot_path.as_posix()}`",
        "",
        "| Source | Status | Fetched at | Notes |",
        "| --- | --- | --- | --- |",
    ]
    for name, payload in sorted(as_dict(snapshot.get("sources")).items()):
        item = as_dict(payload)
        note = item.get("reason") or item.get("message") or ""
        lines.append(
            f"| {name} | {safe_text(item.get('status'))} | {safe_text(item.get('fetched_at_utc'), '')} | {safe_text(note, '')} |"
        )
    return "\n".join(lines)


def scope_limitations() -> str:
    return "\n".join(
        [
            "## Scope limitations",
            "",
            "- This report is generated from one validated source snapshot.",
            "- This report made no LLM calls and used no hidden enrichment.",
            "- This report is not financial advice, investment research, a recommendation, a trading signal, or a call to buy, sell, or hold any asset.",
            "- This report may contain stale, missing, degraded, or erroneous source data if the validated snapshot records those conditions.",
        ]
    )


def render_report(snapshot: dict[str, Any], snapshot_path: Path, quality: dict[str, Any]) -> str:
    parts = [
        front_matter(snapshot, snapshot_path, quality),
        title(snapshot),
        "",
        "## Product boundary and non-investment-advice notice",
        "",
        "This report is deterministic demonstration content generated from one validated source snapshot. It is not financial advice, investment research, a recommendation, a trading signal, or a call to buy, sell, or hold any asset.",
        "",
        quality_section(snapshot, quality),
        "",
        market_section(snapshot),
        "",
        defi_section(snapshot),
        "",
        exchange_section(snapshot, quality),
        "",
        evidence_section(snapshot, snapshot_path),
        "",
        scope_limitations(),
    ]
    return "\n".join(parts).rstrip() + "\n"


def generate_report(snapshot_path: Path, output_root: Path, config_path: Path) -> Path:
    config = load_config(config_path)
    quality = validate_snapshot(snapshot_path, config)
    snapshot = load_snapshot(snapshot_path)
    output_path = report_output_path(snapshot, snapshot_path, output_root)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_report(snapshot, snapshot_path, quality), encoding="utf-8")
    return output_path


def main() -> int:
    args = parse_args()
    try:
        output_path = generate_report(Path(args.snapshot), Path(args.output_root), Path(args.config))
    except ValidationError as exc:
        print(f"Cannot generate report: {exc}", file=sys.stderr)
        return 1
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
