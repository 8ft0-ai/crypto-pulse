#!/usr/bin/env python3
"""CLI for deterministic Phase 11 temporal-series construction."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from crypto_temporal_series import build_temporal_series, canonical_json_bytes


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build one crypto-temporal-series/v1 record.")
    parser.add_argument("repository_root", help="Local Git repository root")
    parser.add_argument("commit_sha", help="Exact immutable commit SHA")
    parser.add_argument("series_kind", choices=("metric", "source-status"))
    parser.add_argument("series_key", help="Frozen Phase 11 metric or source identity")
    parser.add_argument("start_utc", help="Inclusive exact UTC-hour start")
    parser.add_argument("end_utc", help="Inclusive exact UTC-hour end")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    record = build_temporal_series(
        Path(args.repository_root),
        args.commit_sha,
        args.series_kind,
        args.series_key,
        args.start_utc,
        args.end_utc,
    )
    sys.stdout.buffer.write(canonical_json_bytes(record) + b"\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
