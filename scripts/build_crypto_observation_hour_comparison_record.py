#!/usr/bin/env python3
"""Build canonical Phase 13 observation-hour comparison records."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from datetime import timedelta
from pathlib import Path
from typing import Any

from build_crypto_snapshot_comparison_record import _semantic_compatible
from compare_crypto_snapshot_fields import ComparisonAdapterError, build_metric_and_source_evidence
from resolve_crypto_observation_hour_adjacency import (
    ADJACENCY_POLICY_VERSION,
    OBSERVATION_HOUR_CONTRACT_VERSION,
    SEMANTIC_CONTRACT_VERSION,
    ObservationHourReplayContext,
    ObservationHourReplayContextError,
    _bytes_at_commit,
    _canonical_slot,
    _parse_payload,
    _parse_slot,
    prepare_observation_hour_replay_context,
    resolve_observation_hour_adjacency,
)

COMPARISON_SCHEMA_VERSION = "crypto-observation-hour-comparison/v1"


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


def _base_record(current_slot_utc: str) -> dict[str, Any]:
    return {
        "comparison_schema_version": COMPARISON_SCHEMA_VERSION,
        "adjacency_policy_version": ADJACENCY_POLICY_VERSION,
        "observation_hour_contract_version": OBSERVATION_HOUR_CONTRACT_VERSION,
        "semantic_contract_version": SEMANTIC_CONTRACT_VERSION,
        "repository_context": None,
        "current_slot_utc": current_slot_utc,
        "predecessor_slot_utc": None,
        "current_candidates": [],
        "predecessor_candidates": [],
        "current": None,
        "predecessor": None,
        "actual_elapsed_seconds": None,
        "comparison_status": "validation-contract-mismatch",
        "metric_comparisons": [],
        "source_availability_changes": [],
        "comparison_id": "",
    }


def _finalize(record: dict[str, Any]) -> dict[str, Any]:
    record["comparison_id"] = comparison_id_for_record(record)
    return record


def _finalize_and_cache(
    record: dict[str, Any],
    replay_context: ObservationHourReplayContext | None,
) -> dict[str, Any]:
    finalized = _finalize(record)
    if replay_context is not None:
        replay_context.cache_comparison(finalized["current_slot_utc"], finalized)
    return finalized


def _preparation_failure_record(
    current_slot_utc: str,
    exc: ObservationHourReplayContextError,
) -> dict[str, Any]:
    record = _base_record(current_slot_utc)
    current_slot = _parse_slot(current_slot_utc)
    record["predecessor_slot_utc"] = _canonical_slot(
        current_slot - timedelta(hours=1)
    )
    record["repository_context"] = copy.deepcopy(exc.repository_context)
    record["comparison_status"] = exc.resolution_status
    return _finalize(record)


def _build_observation_hour_comparison_uncached(
    repository_root: Path,
    commit_sha: str,
    current_slot_utc: str,
    *,
    replay_context: ObservationHourReplayContext | None,
) -> dict[str, Any]:
    record = _base_record(current_slot_utc)
    resolution = resolve_observation_hour_adjacency(
        repository_root,
        commit_sha,
        current_slot_utc,
        replay_context=replay_context,
    )
    for key in (
        "repository_context",
        "predecessor_slot_utc",
        "current_candidates",
        "predecessor_candidates",
        "current",
        "predecessor",
        "actual_elapsed_seconds",
    ):
        record[key] = resolution[key]

    status = resolution["resolution_status"]
    if status != "adjacency-resolved":
        record["comparison_status"] = status
        return _finalize_and_cache(record, replay_context)

    context = resolution["repository_context"]
    current = resolution["current"]
    predecessor = resolution["predecessor"]
    if not isinstance(context, dict) or not isinstance(current, dict) or not isinstance(predecessor, dict):
        record["comparison_status"] = "validation-contract-mismatch"
        return _finalize_and_cache(record, replay_context)

    if current.get("schema_version") != predecessor.get("schema_version"):
        record["comparison_status"] = "pair-schema-incompatible"
        return _finalize_and_cache(record, replay_context)

    exact_commit = context.get("commit_sha")
    current_path = current.get("path")
    predecessor_path = predecessor.get("path")
    if not all(isinstance(value, str) for value in (exact_commit, current_path, predecessor_path)):
        record["comparison_status"] = "pair-semantics-incompatible"
        return _finalize_and_cache(record, replay_context)

    try:
        if replay_context is not None:
            current_payload = replay_context.payload_for_path(current_path)
            predecessor_payload = replay_context.payload_for_path(predecessor_path)
        else:
            current_payload = _parse_payload(
                _bytes_at_commit(repository_root, exact_commit, current_path)
            )
            predecessor_payload = _parse_payload(
                _bytes_at_commit(repository_root, exact_commit, predecessor_path)
            )
    except (OSError, RuntimeError, UnicodeDecodeError):
        record["comparison_status"] = "pair-semantics-incompatible"
        return _finalize_and_cache(record, replay_context)

    if current_payload is None or predecessor_payload is None:
        record["comparison_status"] = "pair-semantics-incompatible"
        return _finalize_and_cache(record, replay_context)
    if not (_semantic_compatible(current_payload) and _semantic_compatible(predecessor_payload)):
        record["comparison_status"] = "pair-semantics-incompatible"
        return _finalize_and_cache(record, replay_context)

    try:
        metrics, sources = build_metric_and_source_evidence(
            current_payload, predecessor_payload
        )
    except ComparisonAdapterError:
        record["comparison_status"] = "pair-semantics-incompatible"
        return _finalize_and_cache(record, replay_context)

    record["metric_comparisons"] = metrics
    record["source_availability_changes"] = sources
    record["comparison_status"] = "comparison-available"
    return _finalize_and_cache(record, replay_context)


def build_observation_hour_comparison(
    repository_root: Path,
    commit_sha: str,
    current_slot_utc: str,
    *,
    replay_context: ObservationHourReplayContext | None = None,
) -> dict[str, Any]:
    """Build one deterministic crypto-observation-hour-comparison/v1 record."""

    repository_root = Path(repository_root).resolve()
    context = replay_context
    if context is not None and not context.matches(repository_root, commit_sha):
        return _preparation_failure_record(
            current_slot_utc,
            ObservationHourReplayContextError("validation-contract-mismatch"),
        )

    if context is None:
        try:
            context = prepare_observation_hour_replay_context(
                repository_root, commit_sha
            )
        except ObservationHourReplayContextError as exc:
            return _preparation_failure_record(current_slot_utc, exc)

    cached = context.cached_comparison(current_slot_utc)
    if cached is not None:
        return cached

    return _build_observation_hour_comparison_uncached(
        repository_root,
        commit_sha,
        current_slot_utc,
        replay_context=context,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build one crypto-observation-hour-comparison/v1 record."
    )
    parser.add_argument("repository_root", help="Local Git repository root")
    parser.add_argument("commit_sha", help="Exact immutable commit SHA")
    parser.add_argument("current_slot_utc", help="Canonical current observation hour")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    record = build_observation_hour_comparison(
        Path(args.repository_root), args.commit_sha, args.current_slot_utc
    )
    print(canonical_json_bytes(record).decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
