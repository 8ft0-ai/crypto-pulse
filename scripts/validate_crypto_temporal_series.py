#!/usr/bin/env python3
"""CLI for repository-bound validation of crypto-temporal-series/v1 records."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from crypto_temporal_series import canonical_json_bytes, validate_temporal_series


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate one crypto-temporal-series/v1 record.")
    parser.add_argument("repository_root", help="Local Git repository root")
    parser.add_argument("series_path", help="JSON series record to validate")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    record = json.loads(Path(args.series_path).read_text(encoding="utf-8"))
    validate_temporal_series(Path(args.repository_root), record)
    sys.stdout.buffer.write(canonical_json_bytes(record) + b"\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
