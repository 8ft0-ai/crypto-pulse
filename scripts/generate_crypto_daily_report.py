#!/usr/bin/env python3
"""Deterministic UTC-day consolidation of observations on protected main.

No external data fetch, LLM, backfill, interpolation, GitHub mutation or publication.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from validate_crypto_observation_hour import validate_observation_hour
from validate_crypto_snapshot import ValidationError, load_config

SCHEMA = "deterministic-crypto-daily-report/v1"
ROOT = Path(__file__).resolve().parents[1]
REPO = "https://github.com/8ft0-ai/crypto-pulse"
SHA_RE = re.compile(r"[0-9a-f]{40}")
SYMBOL_IDS = {"BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana"}


class DailyReportError(ValueError):
    pass


def git(root: Path, *args: str) -> bytes:
    result = subprocess.run(["git", "-C", str(root), *args], capture_output=True)
    if result.returncode:
        raise DailyReportError(result.stderr.decode("utf-8", "replace").strip()
                               or "Git source read failed")
    return result.stdout


def utc(value: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise DailyReportError("Timestamp must use UTC Z notation")
    try:
        result = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise DailyReportError("Invalid UTC timestamp") from exc
    if result.utcoffset() != timedelta(0):
        raise DailyReportError("Timestamp is not UTC")
    return result


def timestamp(value: datetime) -> str:
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")


def source_commit(root: Path, sha: str, cutoff: datetime) -> None:
    if SHA_RE.fullmatch(sha) is None:
        raise DailyReportError("Source commit must be an exact lowercase 40-hex SHA")
    if git(root, "rev-parse", f"{sha}^{{commit}}").decode().strip() != sha:
        raise DailyReportError("Source commit did not resolve exactly")
    # Freeze the protected-main first-parent tip that existed at the cut-off.
    # An unpublished feature commit merged after cut-off is not admissible even
    # when its original Git author/committer timestamp is older.
    at_cutoff = git(root, "rev-list", "--first-parent", "-n", "1",
                    "--before=" + timestamp(cutoff), "refs/remotes/origin/main"
                    ).decode().strip()
    if SHA_RE.fullmatch(at_cutoff) is None:
        raise DailyReportError("Protected-main ancestry at cut-off is unavailable")
    check = subprocess.run(["git", "-C", str(root), "merge-base", "--is-ancestor",
                            sha, at_cutoff], capture_output=True)
    if check.returncode:
        raise DailyReportError("Source commit was not on protected main at evidence cut-off")


def asset_prices(snapshot: dict[str, Any], capture: datetime) -> dict[str, Decimal]:
    if snapshot.get("sources", {}).get("coingecko", {}).get("status") != "ok":
        return {}
    assets = snapshot.get("market", {}).get("assets")
    if not isinstance(assets, list):
        return {}
    qualified: dict[str, Decimal] = {}
    for symbol, asset_id in SYMBOL_IDS.items():
        rows = [a for a in assets if isinstance(a, dict)
                and a.get("symbol") == symbol and a.get("id") == asset_id]
        if len(rows) != 1:
            continue
        try:
            price = Decimal(str(rows[0].get("price_usd")))
            last_updated = utc(rows[0].get("last_updated"))
        except (InvalidOperation, DailyReportError, TypeError):
            continue
        if price.is_finite() and price > 0 and last_updated <= capture:
            qualified[symbol] = price
    return qualified


def evidence(root: Path, sha: str, day: date, config: dict[str, Any]) -> list[dict[str, Any]]:
    start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    end = start + timedelta(days=1)
    paths = git(root, "ls-tree", "-r", "--name-only", sha, "--", "data/crypto/hourly").decode().splitlines()
    slots: dict[str, dict[str, Any]] = {}
    local_dates = {(day + timedelta(days=delta)).isoformat() for delta in (-1, 0, 1)}
    for path in paths:
        if not path.endswith("_source_snapshot.json"):
            continue
        parts = Path(path).parts
        if len(parts) < 7 or "-".join(parts[-4:-1]) not in local_dates:
            continue
        raw = git(root, "show", f"{sha}:{path}")
        try:
            snapshot = json.loads(raw)
            run = snapshot["run"]
            hour_text = run["observation_hour_utc"]
            actual = utc(run["generated_at_utc"])
            hour = utc(hour_text)
            if timestamp(hour) != hour_text or actual.replace(minute=0, second=0, microsecond=0) != hour:
                raise DailyReportError("Observation hour contradicts actual time")
        except (ValueError, TypeError, KeyError) as exc:
            raise DailyReportError(f"Unclassifiable source snapshot {path}") from exc
        if not start <= hour < end:
            continue
        if hour_text in slots:
            raise DailyReportError(f"Multiple trusted-main snapshots claim hour {hour_text}")
        record: dict[str, Any] = {"hour": hour_text, "actual": timestamp(actual),
                                  "path": path, "sha256": hashlib.sha256(raw).hexdigest(),
                                  "status": "rejected", "prices": {}}
        with tempfile.TemporaryDirectory(prefix="cryptopulse-daily-") as tmp:
            target = Path(tmp) / "source_snapshot.json"
            target.write_bytes(raw)
            try:
                validated = validate_observation_hour(target, config)
            except (ValidationError, ValueError, OSError) as exc:
                record["reason"] = str(exc).replace("\n", " ")
            else:
                record["status"] = validated["quality_status"]
                record["prices"] = asset_prices(snapshot, actual)
                record["sources"] = sorted(
                    name for name, item in snapshot["sources"].items()
                    if isinstance(item, dict) and item.get("status") == "ok"
                )
        slots[hour_text] = record
    return [
        slots.get(timestamp(start + timedelta(hours=i)),
                  {"hour": timestamp(start + timedelta(hours=i)), "status": "missing"})
        for i in range(24)
    ]


def render(day: date, sha: str, records: list[dict[str, Any]]) -> str:
    end = datetime(day.year, day.month, day.day, tzinfo=timezone.utc) + timedelta(days=1)
    cutoff = end + timedelta(hours=1)
    accepted = [r for r in records if r["status"] in ("valid-ok", "valid-degraded")]
    degraded = [r for r in records if r["status"] == "valid-degraded"]
    missing = [r for r in records if r["status"] == "missing"]
    rejected = [r for r in records if r["status"] == "rejected"]
    quality = "valid-ok" if len(accepted) == 24 and not degraded else "valid-degraded"
    lines = [
        "---",
        f'schema_version: "{SCHEMA}"',
        'report_type: "crypto_daily_consolidation"',
        f'reporting_date_utc: "{day.isoformat()}"',
        f'evidence_cutoff_utc: "{timestamp(cutoff)}"',
        f'report_reference_time_utc: "{timestamp(cutoff)}"',
        f'trusted_main_sha: "{sha}"',
        'cadence: "daily"',
        f'quality_status: "{quality}"',
        "no_investment_advice: true",
        "llm_generated: false",
        "---",
        f"# CryptoPulse daily evidence summary — {day.isoformat()} UTC",
        "",
        "## Product boundary and non-investment-advice notice",
        "",
        "This deterministic AI-produced demo report may be inaccurate, incomplete or stale. "
        "It is not financial advice, investment research, a recommendation, a trading signal, "
        "or a call to buy, sell, or hold any asset.",
        "",
        "## Daily coverage",
        "",
        f"Reporting interval: {day.isoformat()} 00:00 UTC to "
        f"{end:%Y-%m-%d %H:%M} UTC (end exclusive).",
        f"Fixed evidence cut-off: {timestamp(cutoff)}.",
        f"Source authority: protected-main ancestor commit {sha}. "
        "Unpublished candidate PRs and workflow artefacts are not counted.",
        "",
        f"- Accepted UTC hours: **{len(accepted)}/24**.",
        f"- Valid and non-degraded: **{len(accepted)-len(degraded)}**.",
        f"- Degraded accepted hours: **{len(degraded)}**.",
        f"- Missing hours: **{len(missing)}**.",
        f"- Rejected snapshots: **{len(rejected)}**.",
        "",
        "Missing: " + (", ".join(r["hour"][11:16] for r in missing) if missing else "none") + " UTC.",
        "Degraded: " + (", ".join(r["hour"][11:16] for r in degraded) if degraded else "none") + " UTC.",
        "Rejected: " + (", ".join(r["hour"][11:16] for r in rejected) if rejected else "none") + " UTC.",
        "",
        "## BTC, ETH and SOL — observed first-to-last comparisons",
        "",
        "These are price changes between the first and last qualified observations "
        "within this reporting day, NOT exchange open/close returns, forward "
        "predictions, or 24-hour source-reported changes. Coverage gaps remain gaps.",
        "",
        "| Asset | First UTC hour | Last UTC hour | Observations | First USD | Last USD | Change |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for symbol in SYMBOL_IDS:
        points = [(r["hour"], r["prices"][symbol]) for r in accepted
                  if symbol in r["prices"]]
        if len(points) < 2:
            lines.append(f"| {symbol} | — | — | {len(points)} | — | — | unavailable |")
        else:
            first, last = points[0], points[-1]
            change = (last[1] / first[1] - Decimal("1")) * 100
            lines.append(f"| {symbol} | {first[0][11:16]} | {last[0][11:16]} | "
                         f"{len(points)} | {first[1]:,.2f} | {last[1]:,.2f} | {change:+.2f}% |")
    lines += [
        "",
        "## Evidence and source status",
        "",
        "Each recorded snapshot is an immutable byte sequence at the cited trusted-main "
        "commit. Its SHA-256, actual capture time, quality and source identities are listed.",
        "",
        "| UTC hour | Disposition | Actual capture UTC | Sources with status ok | Snapshot SHA-256 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for r in records:
        if r["status"] == "missing":
            lines.append(f"| {r['hour'][11:16]} | missing | — | — | — |")
            continue
        path = r["path"]
        link = f"[{r['sha256']}]({REPO}/blob/{sha}/{path})"
        status = r["status"]
        if status == "rejected":
            status += " (validation refused)"
        source_names = ", ".join(r.get("sources", ())) or "unqualified"
        lines.append(f"| {r['hour'][11:16]} | {status} | {r['actual']} | {source_names} | {link} |")
    if rejected:
        lines.extend(["", "Validation refusals:"])
        for r in rejected:
            lines.append(f"- {r['hour']}: {r['reason']}")
    lines += [
        "",
        "## Scope limitations",
        "",
        "- Deterministic consolidation of trusted-main hourly source snapshots, "
        "not the latest hourly report relabelled.",
        "- Only source observations actually captured within the interval are compared; "
        "no interpolation, backfill or look-ahead.",
        "- No 30-day percentile, unusual-movement or market-rarity claim.",
        "- No LLM inference. Demonstration content, not financial advice, investment "
        "research, a recommendation or a trading signal.",
        "",
    ]
    return "\n".join(lines)


def output_path(day: date, output_root: Path) -> Path:
    return output_root / f"{day:%Y}" / f"{day:%m}" / f"{day:%d}" / f"{day.isoformat()}_UTC.md"


def generate(root: Path, sha: str, day: date, output_root: Path,
             config_path: Path, as_of: datetime) -> tuple[Path, list[dict[str, Any]]]:
    cutoff = datetime(day.year, day.month, day.day, tzinfo=timezone.utc) + timedelta(days=1, hours=1)
    if as_of < cutoff:
        raise DailyReportError("Fixed evidence cut-off has not elapsed")
    source_commit(root, sha, cutoff)
    config_relative = config_path.resolve().relative_to(root.resolve()).as_posix()
    if config_relative != "config/crypto_sources.yml":
        raise DailyReportError("Only the pinned CryptoPulse source-quality config is accepted")
    with tempfile.TemporaryDirectory(prefix="cryptopulse-daily-config-") as tmp:
        verified_config = Path(tmp) / "crypto_sources.yml"
        verified_config.write_bytes(git(root, "show", f"{sha}:{config_relative}"))
        config = load_config(verified_config)
    records = evidence(root, sha, day, config)
    destination = output_path(day, output_root)
    rendered = render(day, sha, records).encode("utf-8")
    if destination.exists():
        if destination.read_bytes() != rendered:
            raise DailyReportError(f"Daily report exists with different bytes: {destination}")
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(rendered)
    return destination, records


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-date", required=True, help="UTC YYYY-MM-DD")
    parser.add_argument("--trusted-main-sha", required=True)
    parser.add_argument("--root", default=str(ROOT))
    parser.add_argument("--output-root", default="reports/crypto/daily")
    parser.add_argument("--config", default="config/crypto_sources.yml")
    args = parser.parse_args()
    try:
        day = date.fromisoformat(args.report_date)
        if day.isoformat() != args.report_date:
            raise DailyReportError("Report date must be canonical YYYY-MM-DD")
        root = Path(args.root).resolve()
        output = Path(args.output_root)
        if not output.is_absolute():
            output = root / output
        config = Path(args.config)
        if not config.is_absolute():
            config = root / config
        now = datetime.now(timezone.utc)
        path, records = generate(root, args.trusted_main_sha, day, output, config, now)
        print(json.dumps({"path": str(path), "accepted": sum(
            r["status"] in ("valid-ok", "valid-degraded") for r in records),
            "missing": sum(r["status"] == "missing" for r in records),
            "degraded": sum(r["status"] == "valid-degraded" for r in records),
            "rejected": sum(r["status"] == "rejected" for r in records)}, sort_keys=True))
        return 0
    except (DailyReportError, ValidationError, OSError, ValueError) as exc:
        print(f"Daily consolidation refused: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
