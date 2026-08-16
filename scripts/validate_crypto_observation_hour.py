#!/usr/bin/env python3
"""Validate Phase 12 canonical observation-hour evidence on source snapshots."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import timezone
from pathlib import Path
from typing import Any

from validate_crypto_snapshot import (
    ValidationError,
    iter_snapshot_files,
    load_config,
    parse_iso_timestamp,
    validate_snapshot,
)

CONTRACT_VERSION = "phase12-observation-hour/v1"
OBSERVATION_HOUR_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:00:00Z$")


def canonical_observation_hour(generated_at_utc: Any) -> str:
    generated = parse_iso_timestamp(generated_at_utc, "run.generated_at_utc")
    return (
        generated.astimezone(timezone.utc)
        .replace(minute=0, second=0, microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def validate_observation_hour(path: Path, config: dict[str, Any] | None = None) -> dict[str, str]:
    """Require ordinary snapshot validity, then validate Phase 12 slot identity."""
    quality = validate_snapshot(path, config or {})
    try:
        snapshot = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:  # already rejected by validate_snapshot; defensive only
        raise ValidationError(f"invalid JSON: {exc}") from exc

    run = snapshot.get("run")
    if not isinstance(run, dict):  # already rejected by validate_snapshot; defensive only
        raise ValidationError("run must be an object")

    value = run.get("observation_hour_utc")
    if not isinstance(value, str) or not value:
        raise ValidationError("run.observation_hour_utc is required for phase12-observation-hour/v1")
    if OBSERVATION_HOUR_RE.fullmatch(value) is None:
        raise ValidationError("run.observation_hour_utc must use canonical YYYY-MM-DDTHH:00:00Z form")

    # Parse after the exact syntax check so impossible dates/hours still fail deterministically.
    parse_iso_timestamp(value, "run.observation_hour_utc")
    expected = canonical_observation_hour(run.get("generated_at_utc"))
    if value != expected:
        raise ValidationError(
            f"run.observation_hour_utc must equal containing UTC hour {expected} derived from run.generated_at_utc"
        )

    return {
        "contract_version": CONTRACT_VERSION,
        "quality_status": quality["status"],
        "generated_at_utc": str(run["generated_at_utc"]),
        "observation_hour_utc": value,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate phase12-observation-hour/v1 evidence on source snapshot JSON files."
    )
    parser.add_argument("path", help="Snapshot file or directory containing *_source_snapshot.json files.")
    parser.add_argument(
        "--config",
        default="config/crypto_sources.yml",
        help="Existing source-quality config used by the frozen snapshot validator.",
    )
    return parser.parse_args()


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
    for path in files:
        try:
            validate_observation_hour(path, config)
        except ValidationError as exc:
            failures.append(f"{path}: {exc}")

    if failures:
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1

    print(f"Validated {len(files)} phase12-observation-hour/v1 snapshot file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
