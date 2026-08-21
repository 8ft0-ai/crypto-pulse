#!/usr/bin/env python3
"""Select and materialise bounded Phase 15 public temporal evidence."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import timedelta
from pathlib import Path
from typing import Any

from crypto_observation_hour_series import (
    SERIES_SCHEMA_VERSION,
    ObservationHourSeriesError,
    build_observation_hour_series,
    validate_observation_hour_series,
)
from resolve_crypto_observation_hour_adjacency import (
    ObservationHourPopulationError,
    _canonical_slot,
    _parse_slot,
    load_observation_hour_population,
)

PUBLIC_TEMPORAL_EVIDENCE_CONTRACT_VERSION = "phase15-public-temporal-evidence/v1"
PUBLIC_SERIES_KIND = "metric"
PUBLIC_SERIES_KEY = "BTC.price_usd"
PUBLIC_SLOT_COUNT = 24


class Phase15PublicTemporalEvidenceError(ValueError):
    """Raised when Phase 15 cannot safely assert public temporal evidence."""


def select_public_temporal_evidence_window(
    repository_root: Path,
    commit_sha: str,
) -> dict[str, str] | None:
    """Select the deterministic 24-slot public window from Phase 13 participation.

    The anchor is the maximum canonical participating observation hour in the
    immutable commit. Zero participation intentionally yields no assertion.
    """
    try:
        population = load_observation_hour_population(Path(repository_root), commit_sha)
    except ObservationHourPopulationError as exc:
        raise Phase15PublicTemporalEvidenceError("candidate-set-unorderable") from exc

    if not population:
        return None

    try:
        end = max(_parse_slot(slot) for slot in population)
    except ValueError as exc:
        raise Phase15PublicTemporalEvidenceError("candidate-set-unorderable") from exc
    start = end - timedelta(hours=PUBLIC_SLOT_COUNT - 1)
    return {
        "start_utc": _canonical_slot(start),
        "end_utc": _canonical_slot(end),
    }


def _enforce_public_series_shape(record: Any) -> dict[str, Any]:
    if not isinstance(record, dict):
        raise Phase15PublicTemporalEvidenceError("Phase 13 series is not an object")
    if record.get("schema_version") != SERIES_SCHEMA_VERSION:
        raise Phase15PublicTemporalEvidenceError("Phase 13 series schema mismatch")
    if record.get("series_kind") != PUBLIC_SERIES_KIND:
        raise Phase15PublicTemporalEvidenceError("public series kind mismatch")
    if record.get("series_key") != PUBLIC_SERIES_KEY:
        raise Phase15PublicTemporalEvidenceError("public series key mismatch")
    entries = record.get("entries")
    if not isinstance(entries, list) or len(entries) != PUBLIC_SLOT_COUNT:
        raise Phase15PublicTemporalEvidenceError(
            f"public series must contain exactly {PUBLIC_SLOT_COUNT} hourly slots"
        )
    window = record.get("window")
    if not isinstance(window, dict):
        raise Phase15PublicTemporalEvidenceError("public series window is invalid")
    try:
        start = _parse_slot(window.get("start_utc"))
        end = _parse_slot(window.get("end_utc"))
    except ValueError as exc:
        raise Phase15PublicTemporalEvidenceError("public series window is invalid") from exc
    if end - start != timedelta(hours=PUBLIC_SLOT_COUNT - 1):
        raise Phase15PublicTemporalEvidenceError("public series window is not 24 canonical slots")
    return record


def build_public_temporal_evidence(
    repository_root: Path,
    commit_sha: str,
) -> dict[str, Any] | None:
    """Build the exact Phase 13 series selected by the Phase 15 contract."""
    root = Path(repository_root)
    window = select_public_temporal_evidence_window(root, commit_sha)
    if window is None:
        return None
    try:
        record = build_observation_hour_series(
            root,
            commit_sha,
            PUBLIC_SERIES_KIND,
            PUBLIC_SERIES_KEY,
            window["start_utc"],
            window["end_utc"],
        )
        validate_observation_hour_series(root, record)
    except ObservationHourSeriesError as exc:
        raise Phase15PublicTemporalEvidenceError(
            "Phase 13 series construction or immutable replay validation failed"
        ) from exc
    return _enforce_public_series_shape(record)


def canonical_public_evidence_bytes(record: dict[str, Any]) -> bytes:
    """Return deterministic JSON bytes for proof and hand-off surfaces."""
    _enforce_public_series_shape(record)
    return json.dumps(
        record,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Materialise phase15-public-temporal-evidence/v1 from one exact Git commit."
    )
    parser.add_argument("repository_root")
    parser.add_argument("commit_sha")
    args = parser.parse_args()

    try:
        record = build_public_temporal_evidence(Path(args.repository_root), args.commit_sha)
    except Phase15PublicTemporalEvidenceError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if record is None:
        return 3
    sys.stdout.buffer.write(canonical_public_evidence_bytes(record) + b"\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
