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
    ObservationHourReplayContext,
    ObservationHourReplayContextError,
    _canonical_slot,
    _parse_slot,
    load_observation_hour_population,
    prepare_observation_hour_replay_context,
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
    *,
    replay_context: ObservationHourReplayContext | None = None,
) -> dict[str, str] | None:
    """Select the deterministic 24-slot public window from Phase 13 participation.

    The anchor is the maximum canonical participating observation hour in the
    immutable commit. Zero participation intentionally yields no assertion.
    """
    if replay_context is not None:
        if not replay_context.matches(Path(repository_root), commit_sha):
            raise Phase15PublicTemporalEvidenceError("candidate-set-unorderable")
        hours = replay_context.observation_hours()
    else:
        try:
            population = load_observation_hour_population(
                Path(repository_root), commit_sha
            )
        except ObservationHourPopulationError as exc:
            raise Phase15PublicTemporalEvidenceError("candidate-set-unorderable") from exc
        hours = tuple(population)

    if not hours:
        return None

    try:
        end = max(_parse_slot(slot) for slot in hours)
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
    *,
    replay_context: ObservationHourReplayContext | None = None,
) -> dict[str, Any] | None:
    """Build the exact Phase 13 series selected by the Phase 15 contract."""
    root = Path(repository_root)
    context = replay_context
    if context is not None and not context.matches(root, commit_sha):
        raise Phase15PublicTemporalEvidenceError("candidate-set-unorderable")

    if context is None:
        try:
            context = prepare_observation_hour_replay_context(root, commit_sha)
        except RuntimeError as exc:
            raise Phase15PublicTemporalEvidenceError(
                "immutable replay execution failed"
            ) from exc
        except ObservationHourReplayContextError as exc:
            if exc.resolution_status == "candidate-set-unorderable":
                raise Phase15PublicTemporalEvidenceError(
                    "candidate-set-unorderable"
                ) from exc
            if exc.resolution_status != "validation-contract-mismatch":
                raise Phase15PublicTemporalEvidenceError(
                    "replay context preparation failed"
                ) from exc
            # Preserve legacy validation-contract behaviour: window selection is
            # population-only and the resulting Phase 13 series retains explicit
            # validation-contract gaps rather than changing the public contract.
            context = None

    window = select_public_temporal_evidence_window(
        root,
        commit_sha,
        replay_context=context,
    )
    if window is None:
        return None
    try:
        if context is None:
            record = build_observation_hour_series(
                root,
                commit_sha,
                PUBLIC_SERIES_KIND,
                PUBLIC_SERIES_KEY,
                window["start_utc"],
                window["end_utc"],
            )
            validate_observation_hour_series(root, record)
        else:
            record = build_observation_hour_series(
                root,
                commit_sha,
                PUBLIC_SERIES_KIND,
                PUBLIC_SERIES_KEY,
                window["start_utc"],
                window["end_utc"],
                replay_context=context,
            )
            validate_observation_hour_series(
                root,
                record,
                replay_context=context,
            )
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