#!/usr/bin/env python3
"""Build one canonical Phase 13 observation-hour temporal series."""

from __future__ import annotations

import argparse
from pathlib import Path

from crypto_observation_hour_series import (
    build_observation_hour_series,
    canonical_json_bytes,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build one crypto-observation-hour-series/v1 record."
    )
    parser.add_argument("repository_root")
    parser.add_argument("commit_sha")
    parser.add_argument("series_kind", choices=("metric", "source-status"))
    parser.add_argument("series_key")
    parser.add_argument("start_utc")
    parser.add_argument("end_utc")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    record = build_observation_hour_series(
        Path(args.repository_root),
        args.commit_sha,
        args.series_kind,
        args.series_key,
        args.start_utc,
        args.end_utc,
    )
    print(canonical_json_bytes(record).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
