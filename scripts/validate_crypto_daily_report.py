#!/usr/bin/env python3
"""Independently re-render and validate an unpublished daily report candidate."""
from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import yaml

from generate_crypto_daily_report import DailyReportError, evidence, render, source_commit
from validate_crypto_snapshot import ValidationError, load_config


def validate_daily(path: Path, root: Path) -> None:
    if not path.is_file():
        raise DailyReportError("Daily report candidate is unavailable")
    raw = path.read_bytes()
    if not raw.startswith(b"---\n"):
        raise DailyReportError("Daily report has no front matter")
    pieces = raw.decode("utf-8").split("---\n", 2)
    if len(pieces) != 3:
        raise DailyReportError("Malformed daily report front matter")
    metadata = yaml.safe_load(pieces[1])
    if not isinstance(metadata, dict):
        raise DailyReportError("Daily report metadata must be a mapping")
    if metadata.get("report_type") != "crypto_daily_consolidation":
        raise DailyReportError("Unexpected daily report type")
    try:
        day = date.fromisoformat(metadata["reporting_date_utc"])
        sha = metadata["trusted_main_sha"]
        expected = (root / "reports/crypto/daily" / f"{day:%Y}" / f"{day:%m}" /
                    f"{day:%d}" / f"{day.isoformat()}_UTC.md")
    except (ValueError, TypeError, KeyError) as exc:
        raise DailyReportError("Invalid daily report identity") from exc
    if path.resolve() != expected.resolve():
        raise DailyReportError("Daily report path is not canonical")
    cutoff = datetime(day.year, day.month, day.day, tzinfo=timezone.utc) + timedelta(days=1, hours=1)
    source_commit(root, sha, cutoff)
    # Import configuration from the same protected-main source commit.
    import tempfile
    from generate_crypto_daily_report import git
    with tempfile.TemporaryDirectory(prefix="cryptopulse-daily-validate-") as tmp:
        file = Path(tmp) / "crypto_sources.yml"
        file.write_bytes(git(root, "show", f"{sha}:config/crypto_sources.yml"))
        config = load_config(file)
    records = evidence(root, sha, day, config)
    if render(day, sha, records).encode("utf-8") != raw:
        raise DailyReportError("Candidate bytes differ from independently re-rendered protected-main evidence")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        validate_daily(args.path, args.root.resolve())
    except (DailyReportError, ValidationError, OSError, ValueError) as exc:
        print(f"Daily validation refused: {exc}", file=sys.stderr)
        return 1
    print("DAILY_REPORT_VALIDATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
