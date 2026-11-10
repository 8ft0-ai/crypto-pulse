#!/usr/bin/env python3
"""Validate one canonical Phase 13 observation-hour temporal series."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from crypto_observation_hour_series import (
    ObservationHourSeriesError,
    validate_observation_hour_series,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate one crypto-observation-hour-series/v1 JSON record."
    )
    parser.add_argument("repository_root")
    parser.add_argument("record_path")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        record = json.loads(Path(args.record_path).read_text(encoding="utf-8"))
        validate_observation_hour_series(Path(args.repository_root), record)
    except (OSError, json.JSONDecodeError, ObservationHourSeriesError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print("Validated crypto-observation-hour-series/v1 record.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
