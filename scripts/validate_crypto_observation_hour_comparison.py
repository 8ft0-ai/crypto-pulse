#!/usr/bin/env python3
"""Repository-bound validation for Phase 13 observation-hour comparisons."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

from build_crypto_observation_hour_comparison_record import (
    COMPARISON_SCHEMA_VERSION,
    build_observation_hour_comparison,
    canonical_json_bytes,
    comparison_id_for_record,
)
from resolve_crypto_observation_hour_adjacency import (
    ADJACENCY_POLICY_VERSION,
    OBSERVATION_HOUR_CONTRACT_VERSION,
    SEMANTIC_CONTRACT_VERSION,
)

LOWER_HEX_64 = re.compile(r"^[0-9a-f]{64}$")
TOP_LEVEL_KEYS = {
    "comparison_schema_version",
    "adjacency_policy_version",
    "observation_hour_contract_version",
    "semantic_contract_version",
    "repository_context",
    "current_slot_utc",
    "predecessor_slot_utc",
    "current_candidates",
    "predecessor_candidates",
    "current",
    "predecessor",
    "actual_elapsed_seconds",
    "comparison_status",
    "metric_comparisons",
    "source_availability_changes",
    "comparison_id",
}


class ObservationHourComparisonValidationError(ValueError):
    """Raised when a Phase 13 comparison record cannot be replayed exactly."""


def _require_shape(record: Any) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise ObservationHourComparisonValidationError("comparison record must be an object")
    if set(record) != TOP_LEVEL_KEYS:
        raise ObservationHourComparisonValidationError("comparison record keys mismatch")
    expected_versions = {
        "comparison_schema_version": COMPARISON_SCHEMA_VERSION,
        "adjacency_policy_version": ADJACENCY_POLICY_VERSION,
        "observation_hour_contract_version": OBSERVATION_HOUR_CONTRACT_VERSION,
        "semantic_contract_version": SEMANTIC_CONTRACT_VERSION,
    }
    for key, expected in expected_versions.items():
        if record.get(key) != expected:
            raise ObservationHourComparisonValidationError(f"{key} must be {expected}")
    comparison_id = record.get("comparison_id")
    if not isinstance(comparison_id, str) or LOWER_HEX_64.fullmatch(comparison_id) is None:
        raise ObservationHourComparisonValidationError("comparison_id must be lower-case SHA-256")
    if comparison_id != comparison_id_for_record(record):
        raise ObservationHourComparisonValidationError("comparison_id does not match canonical record")
    context = record.get("repository_context")
    if not isinstance(context, dict):
        raise ObservationHourComparisonValidationError("repository_context must be an object")
    commit_sha = context.get("commit_sha")
    if not isinstance(commit_sha, str):
        raise ObservationHourComparisonValidationError("repository_context.commit_sha is required")
    slot = record.get("current_slot_utc")
    if not isinstance(slot, str):
        raise ObservationHourComparisonValidationError("current_slot_utc is required")
    return record


def validate_observation_hour_comparison(
    repository_root: Path,
    record: dict[str, Any],
) -> dict[str, Any]:
    """Replay the immutable repository and require byte-identical canonical evidence."""

    item = _require_shape(record)
    context = item["repository_context"]
    expected = build_observation_hour_comparison(
        Path(repository_root), context["commit_sha"], item["current_slot_utc"]
    )
    if canonical_json_bytes(expected) != canonical_json_bytes(item):
        raise ObservationHourComparisonValidationError(
            "comparison record does not match immutable repository replay"
        )
    return item


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate one crypto-observation-hour-comparison/v1 record."
    )
    parser.add_argument("repository_root", help="Local Git repository root")
    parser.add_argument("comparison_path", help="JSON comparison record")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        record = json.loads(Path(args.comparison_path).read_text(encoding="utf-8"))
        validate_observation_hour_comparison(Path(args.repository_root), record)
    except (OSError, json.JSONDecodeError, ObservationHourComparisonValidationError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    sys.stdout.buffer.write(canonical_json_bytes(record) + b"\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
