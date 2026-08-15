#!/usr/bin/env python3
"""Strict Slice 2 validator for deterministic CryptoPulse comparison records."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from datetime import datetime
from pathlib import PurePosixPath
from typing import Any

COMPARISON_SCHEMA_VERSION = "crypto-snapshot-comparison/v1"
PREDECESSOR_POLICY_VERSION = "phase10-predecessor-exact-hour/v1"
SEMANTIC_CONTRACT_VERSION = "phase10-snapshot-semantics-0.2/v1"
VALIDATOR_PATH = "scripts/validate_crypto_snapshot.py"
VALIDATOR_BLOB_SHA = "b8c7fcc850bf0f5076f7d084bb6be9c24a9b7d3a"
CONFIG_PATH = "config/crypto_sources.yml"
CONFIG_BLOB_SHA = "73c5a3f3db81954951801c7d348d09a4c6296d73"

SLICE2_STATUSES = {
    "validation-contract-mismatch",
    "current-invalid",
    "current-identity-invalid",
    "candidate-set-unorderable",
    "predecessor-missing",
    "predecessor-ambiguous",
    "predecessor-invalid",
    "predecessor-identity-invalid",
    "predecessor-out-of-window",
    "pair-schema-incompatible",
    "pair-semantics-incompatible",
    "comparison-ready",
}
VALID_QUALITY_STATUSES = {"valid-ok", "valid-degraded"}
LOWER_HEX_40 = re.compile(r"^[0-9a-f]{40}$")
LOWER_HEX_64 = re.compile(r"^[0-9a-f]{64}$")
TOP_LEVEL_KEYS = {
    "comparison_schema_version",
    "predecessor_policy_version",
    "semantic_contract_version",
    "repository_context",
    "current",
    "predecessor",
    "elapsed_seconds",
    "comparison_status",
    "metric_comparisons",
    "source_availability_changes",
    "comparison_id",
}
REPOSITORY_CONTEXT_KEYS = {"commit_sha", "tree_sha", "validator", "config"}
CONTRACT_REF_KEYS = {"path", "git_blob_sha"}
INPUT_KEYS = {
    "path",
    "sha256",
    "schema_version",
    "generated_at_utc",
    "quality_status",
    "non_blocking_warnings",
}


class ComparisonValidationError(ValueError):
    """Raised when a comparison record fails the Slice 2 contract."""


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def comparison_id_for_record(record: dict[str, Any]) -> str:
    payload = dict(record)
    payload.pop("comparison_id", None)
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def _require_exact_keys(value: Any, expected: set[str], path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ComparisonValidationError(f"{path} must be an object")
    actual = set(value)
    if actual != expected:
        missing = sorted(expected - actual)
        extra = sorted(actual - expected)
        details = []
        if missing:
            details.append("missing=" + ",".join(missing))
        if extra:
            details.append("extra=" + ",".join(extra))
        raise ComparisonValidationError(f"{path} keys mismatch: {'; '.join(details)}")
    return value


def _validate_json_native(value: Any, path: str = "$") -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ComparisonValidationError(f"{path} contains a non-finite number")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_json_native(item, f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ComparisonValidationError(f"{path} contains a non-string object key")
            _validate_json_native(item, f"{path}.{key}")
        return
    raise ComparisonValidationError(f"{path} contains a non-JSON-native value")


def _valid_snapshot_path(value: Any) -> bool:
    if not isinstance(value, str) or not value or "\\" in value:
        return False
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts:
        return False
    if len(path.parts) < 5 or path.parts[:3] != ("data", "crypto", "hourly"):
        return False
    return path.name.endswith("_source_snapshot.json")


def _validate_timestamp(value: Any, path: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ComparisonValidationError(f"{path} must be an ISO-8601 string")
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ComparisonValidationError(f"{path} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ComparisonValidationError(f"{path} must include a UTC offset")


def _validate_contract_ref(value: Any, expected_path: str, path: str) -> dict[str, Any]:
    ref = _require_exact_keys(value, CONTRACT_REF_KEYS, path)
    if ref["path"] != expected_path:
        raise ComparisonValidationError(f"{path}.path must be {expected_path}")
    blob = ref["git_blob_sha"]
    if blob is not None and (not isinstance(blob, str) or not LOWER_HEX_40.fullmatch(blob)):
        raise ComparisonValidationError(f"{path}.git_blob_sha must be a lower-case Git SHA-1 or null")
    return ref


def _validate_input(value: Any, path: str, *, allow_null: bool = False) -> dict[str, Any] | None:
    if value is None:
        if allow_null:
            return None
        raise ComparisonValidationError(f"{path} must be an object")
    item = _require_exact_keys(value, INPUT_KEYS, path)

    if item["path"] is not None and not _valid_snapshot_path(item["path"]):
        raise ComparisonValidationError(f"{path}.path is outside the repository snapshot boundary")
    if item["sha256"] is not None and (
        not isinstance(item["sha256"], str) or not LOWER_HEX_64.fullmatch(item["sha256"])
    ):
        raise ComparisonValidationError(f"{path}.sha256 must be a lower-case SHA-256 or null")
    if item["schema_version"] is not None and (
        not isinstance(item["schema_version"], str) or not item["schema_version"].strip()
    ):
        raise ComparisonValidationError(f"{path}.schema_version must be a non-empty string or null")
    if item["generated_at_utc"] is not None:
        _validate_timestamp(item["generated_at_utc"], f"{path}.generated_at_utc")
    if item["quality_status"] is not None and item["quality_status"] not in VALID_QUALITY_STATUSES:
        raise ComparisonValidationError(
            f"{path}.quality_status must be valid-ok, valid-degraded, or null"
        )
    warnings = item["non_blocking_warnings"]
    if warnings is not None and (
        not isinstance(warnings, list) or any(not isinstance(entry, str) for entry in warnings)
    ):
        raise ComparisonValidationError(f"{path}.non_blocking_warnings must be a string list or null")
    if item["quality_status"] is not None and warnings is None:
        raise ComparisonValidationError(f"{path}.non_blocking_warnings is required after validation")
    if item["quality_status"] == "valid-ok" and warnings:
        raise ComparisonValidationError(f"{path}.valid-ok cannot carry non-blocking warnings")
    if item["quality_status"] == "valid-degraded" and not warnings:
        raise ComparisonValidationError(f"{path}.valid-degraded must retain non-blocking warnings")
    return item


def _require_validated(item: dict[str, Any], path: str) -> None:
    required = ("path", "sha256", "schema_version", "generated_at_utc", "quality_status")
    if any(item.get(key) is None for key in required):
        raise ComparisonValidationError(f"{path} must contain a complete validated identity")


def _require_minimal_predecessor(item: dict[str, Any], path: str) -> None:
    required = ("path", "sha256", "schema_version", "generated_at_utc")
    if any(item.get(key) is None for key in required):
        raise ComparisonValidationError(f"{path} must contain the selected predecessor identity")


def validate_comparison_record(record: Any) -> dict[str, Any]:
    """Validate one Slice 2 comparison record and return it unchanged."""

    _validate_json_native(record)
    record = _require_exact_keys(record, TOP_LEVEL_KEYS, "$")
    if record["comparison_schema_version"] != COMPARISON_SCHEMA_VERSION:
        raise ComparisonValidationError("comparison_schema_version mismatch")
    if record["predecessor_policy_version"] != PREDECESSOR_POLICY_VERSION:
        raise ComparisonValidationError("predecessor_policy_version mismatch")
    if record["semantic_contract_version"] != SEMANTIC_CONTRACT_VERSION:
        raise ComparisonValidationError("semantic_contract_version mismatch")

    status = record["comparison_status"]
    if status not in SLICE2_STATUSES:
        raise ComparisonValidationError("comparison_status is not valid for Slice 2")
    if status == "comparison-available":
        raise ComparisonValidationError("comparison-available is reserved for the adapter slice")

    repository = _require_exact_keys(
        record["repository_context"], REPOSITORY_CONTEXT_KEYS, "repository_context"
    )
    for key in ("commit_sha", "tree_sha"):
        value = repository[key]
        if value is not None and (not isinstance(value, str) or not LOWER_HEX_40.fullmatch(value)):
            raise ComparisonValidationError(f"repository_context.{key} must be a lower-case Git SHA-1 or null")
    validator_ref = _validate_contract_ref(
        repository["validator"], VALIDATOR_PATH, "repository_context.validator"
    )
    config_ref = _validate_contract_ref(repository["config"], CONFIG_PATH, "repository_context.config")

    current = _validate_input(record["current"], "current")
    assert current is not None
    predecessor = _validate_input(record["predecessor"], "predecessor", allow_null=True)

    elapsed = record["elapsed_seconds"]
    if elapsed is not None and (
        isinstance(elapsed, bool) or not isinstance(elapsed, (int, float)) or not math.isfinite(float(elapsed))
    ):
        raise ComparisonValidationError("elapsed_seconds must be a finite number or null")
    if elapsed is not None and elapsed <= 0:
        raise ComparisonValidationError("elapsed_seconds must be positive when present")

    if not isinstance(record["metric_comparisons"], list) or record["metric_comparisons"]:
        raise ComparisonValidationError("metric_comparisons must remain an empty list in Slice 2")
    if not isinstance(record["source_availability_changes"], list) or record["source_availability_changes"]:
        raise ComparisonValidationError(
            "source_availability_changes must remain an empty list in Slice 2"
        )

    if status == "validation-contract-mismatch":
        if predecessor is not None or elapsed is not None:
            raise ComparisonValidationError("validation-contract-mismatch cannot carry predecessor evidence")
    else:
        if any(repository[key] is None for key in ("commit_sha", "tree_sha")):
            raise ComparisonValidationError("resolved records require commit_sha and tree_sha")
        if validator_ref["git_blob_sha"] != VALIDATOR_BLOB_SHA:
            raise ComparisonValidationError("resolved record validator blob does not match frozen identity")
        if config_ref["git_blob_sha"] != CONFIG_BLOB_SHA:
            raise ComparisonValidationError("resolved record config blob does not match frozen identity")

    if status == "current-invalid":
        if predecessor is not None or elapsed is not None or current["quality_status"] is not None:
            raise ComparisonValidationError("current-invalid field combination is inconsistent")
    elif status == "current-identity-invalid":
        if predecessor is not None or elapsed is not None:
            raise ComparisonValidationError("current-identity-invalid cannot carry predecessor evidence")
        if current["quality_status"] is not None:
            _require_validated(current, "current")
    elif status in {"candidate-set-unorderable", "predecessor-missing", "predecessor-ambiguous"}:
        _require_validated(current, "current")
        if predecessor is not None or elapsed is not None:
            raise ComparisonValidationError(f"{status} cannot carry a selected predecessor")
    elif status == "predecessor-invalid":
        _require_validated(current, "current")
        if predecessor is None:
            raise ComparisonValidationError("predecessor-invalid requires selected predecessor identity")
        _require_minimal_predecessor(predecessor, "predecessor")
        if predecessor["quality_status"] is not None or elapsed is not None:
            raise ComparisonValidationError("predecessor-invalid field combination is inconsistent")
    elif status == "predecessor-identity-invalid":
        _require_validated(current, "current")
        if predecessor is None:
            raise ComparisonValidationError("predecessor-identity-invalid requires predecessor")
        _require_minimal_predecessor(predecessor, "predecessor")
        if predecessor["quality_status"] is not None or predecessor["non_blocking_warnings"] is not None:
            raise ComparisonValidationError(
                "predecessor-identity-invalid must fail before predecessor quality classification"
            )
        if elapsed is not None:
            raise ComparisonValidationError("predecessor-identity-invalid must fail before elapsed time")
    elif status == "predecessor-out-of-window":
        _require_validated(current, "current")
        if predecessor is None:
            raise ComparisonValidationError("predecessor-out-of-window requires predecessor")
        _require_validated(predecessor, "predecessor")
        if elapsed is None or elapsed == 3600:
            raise ComparisonValidationError("predecessor-out-of-window requires a non-3600 interval")
    elif status == "pair-schema-incompatible":
        _require_validated(current, "current")
        if predecessor is None:
            raise ComparisonValidationError("pair-schema-incompatible requires predecessor")
        _require_validated(predecessor, "predecessor")
        if elapsed != 3600 or current["schema_version"] == predecessor["schema_version"]:
            raise ComparisonValidationError("pair-schema-incompatible requires exact-hour unequal schemas")
    elif status in {"pair-semantics-incompatible", "comparison-ready"}:
        _require_validated(current, "current")
        if predecessor is None:
            raise ComparisonValidationError(f"{status} requires predecessor")
        _require_validated(predecessor, "predecessor")
        if elapsed != 3600 or current["schema_version"] != predecessor["schema_version"]:
            raise ComparisonValidationError(f"{status} requires an exact-hour equal-schema pair")
        if status == "comparison-ready" and current["schema_version"] != "0.2":
            raise ComparisonValidationError("comparison-ready requires schema 0.2")

    comparison_id = record["comparison_id"]
    if not isinstance(comparison_id, str) or not LOWER_HEX_64.fullmatch(comparison_id):
        raise ComparisonValidationError("comparison_id must be a lower-case SHA-256")
    expected_id = comparison_id_for_record(record)
    if comparison_id != expected_id:
        raise ComparisonValidationError("comparison_id does not match canonical record content")
    return record


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate a Phase 10 Slice 2 comparison record.")
    parser.add_argument("path", help="Comparison record JSON file")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        with open(args.path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        validate_comparison_record(payload)
    except (OSError, json.JSONDecodeError, ComparisonValidationError) as exc:
        print(f"{args.path}: {exc}")
        return 1
    print(f"Validated comparison record: {args.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
