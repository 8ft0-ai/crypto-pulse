#!/usr/bin/env python3
"""Build and validate deterministic Phase 18 multi-asset temporal evidence."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from crypto_observation_hour_series import (
    ObservationHourSeriesError,
    build_observation_hour_series,
    canonical_json_bytes,
    validate_observation_hour_series,
)
from phase15_public_temporal_evidence import (
    PUBLIC_SLOT_COUNT,
    Phase15PublicTemporalEvidenceError,
    build_public_temporal_evidence,
    canonical_public_evidence_bytes,
    select_public_temporal_evidence_window,
)
from resolve_crypto_observation_hour_adjacency import (
    ObservationHourReplayContext,
    ObservationHourReplayContextError,
    prepare_observation_hour_replay_context,
)

PHASE18_CONTRACT_VERSION = "phase18-public-multi-asset-price-evidence/v1"
PUBLIC_SERIES_KIND = "metric"
PUBLIC_SERIES_KEYS = ("BTC.price_usd", "ETH.price_usd", "SOL.price_usd")
TOP_LEVEL_KEYS = {"contract", "repository_context", "window", "series", "bundle_id"}
LOWER_HEX_64 = re.compile(r"^[0-9a-f]{64}$")
CANONICAL_HOUR = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:00:00Z$")


class Phase18MultiAssetTemporalEvidenceError(ValueError):
    """Raised when Phase 18 evidence cannot be built or validated safely."""


def _validate_json_native(value: Any, path: str = "$") -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise Phase18MultiAssetTemporalEvidenceError(
                f"{path} contains a non-finite number"
            )
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_json_native(item, f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise Phase18MultiAssetTemporalEvidenceError(
                    f"{path} contains a non-string key"
                )
            _validate_json_native(item, f"{path}.{key}")
        return
    raise Phase18MultiAssetTemporalEvidenceError(
        f"{path} contains a non-JSON-native value"
    )


def canonical_bundle_bytes(bundle: dict[str, Any]) -> bytes:
    """Return the frozen canonical UTF-8 JSON representation."""
    _validate_json_native(bundle)
    return json.dumps(
        bundle,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def bundle_id_for_record(bundle: dict[str, Any]) -> str:
    """Return SHA-256 over canonical bundle identity material."""
    payload = copy.deepcopy(bundle)
    payload.pop("bundle_id", None)
    return hashlib.sha256(canonical_bundle_bytes(payload)).hexdigest()


def _require_24_slot_window(window: Any) -> dict[str, str]:
    if not isinstance(window, dict) or set(window) != {"start_utc", "end_utc"}:
        raise Phase18MultiAssetTemporalEvidenceError("bundle window keys mismatch")
    start_text = window.get("start_utc")
    end_text = window.get("end_utc")
    if (
        not isinstance(start_text, str)
        or not isinstance(end_text, str)
        or CANONICAL_HOUR.fullmatch(start_text) is None
        or CANONICAL_HOUR.fullmatch(end_text) is None
    ):
        raise Phase18MultiAssetTemporalEvidenceError(
            "bundle window must use canonical UTC hours"
        )
    try:
        start = datetime.fromisoformat(start_text[:-1] + "+00:00").astimezone(timezone.utc)
        end = datetime.fromisoformat(end_text[:-1] + "+00:00").astimezone(timezone.utc)
    except ValueError as exc:
        raise Phase18MultiAssetTemporalEvidenceError("bundle window is invalid") from exc
    if start.isoformat().replace("+00:00", "Z") != start_text:
        raise Phase18MultiAssetTemporalEvidenceError("bundle start hour is not canonical")
    if end.isoformat().replace("+00:00", "Z") != end_text:
        raise Phase18MultiAssetTemporalEvidenceError("bundle end hour is not canonical")
    if int((end - start).total_seconds()) != (PUBLIC_SLOT_COUNT - 1) * 3600:
        raise Phase18MultiAssetTemporalEvidenceError(
            "bundle window is not exactly 24 canonical slots"
        )
    return {"start_utc": start_text, "end_utc": end_text}


def _enforce_member_shape(
    member: Any,
    expected_key: str,
    context: dict[str, Any],
    window: dict[str, str],
) -> dict[str, Any]:
    if not isinstance(member, dict):
        raise Phase18MultiAssetTemporalEvidenceError("bundle member is not an object")
    if member.get("series_kind") != PUBLIC_SERIES_KIND:
        raise Phase18MultiAssetTemporalEvidenceError("bundle member kind mismatch")
    if member.get("series_key") != expected_key:
        raise Phase18MultiAssetTemporalEvidenceError("bundle member identity/order mismatch")
    if member.get("repository_context") != context:
        raise Phase18MultiAssetTemporalEvidenceError(
            "bundle member repository context mismatch"
        )
    if member.get("window") != window:
        raise Phase18MultiAssetTemporalEvidenceError("bundle member window mismatch")
    entries = member.get("entries")
    if not isinstance(entries, list) or len(entries) != PUBLIC_SLOT_COUNT:
        raise Phase18MultiAssetTemporalEvidenceError(
            "bundle member is not exactly 24 slots"
        )
    return member


def _prepare_replay_context_or_legacy(
    repository_root: Path,
    commit_sha: str,
    replay_context: ObservationHourReplayContext | None,
) -> ObservationHourReplayContext | None:
    if replay_context is not None:
        if not replay_context.matches(repository_root, commit_sha):
            raise Phase18MultiAssetTemporalEvidenceError(
                "replay context repository identity mismatch"
            )
        return replay_context
    try:
        return prepare_observation_hour_replay_context(repository_root, commit_sha)
    except RuntimeError as exc:
        raise Phase18MultiAssetTemporalEvidenceError(
            "immutable replay execution failed"
        ) from exc
    except ObservationHourReplayContextError as exc:
        if exc.resolution_status == "validation-contract-mismatch":
            # Preserve only the frozen semantic compatibility path. Execution
            # failures remain RuntimeError and must never reach this retry.
            return None
        if exc.resolution_status == "candidate-set-unorderable":
            raise Phase15PublicTemporalEvidenceError(
                "candidate-set-unorderable"
            ) from exc
        raise Phase18MultiAssetTemporalEvidenceError(
            "replay context preparation failed"
        ) from exc


def build_multi_asset_temporal_evidence(
    repository_root: Path,
    commit_sha: str,
    *,
    replay_context: ObservationHourReplayContext | None = None,
) -> dict[str, Any] | None:
    """Build the canonical Phase 18 BTC/ETH/SOL price-evidence bundle."""
    root = Path(repository_root)
    context = _prepare_replay_context_or_legacy(root, commit_sha, replay_context)
    try:
        window = select_public_temporal_evidence_window(
            root,
            commit_sha,
            replay_context=context,
        )
    except Phase15PublicTemporalEvidenceError:
        raise
    if window is None:
        return None

    members: list[dict[str, Any]] = []
    try:
        for series_key in PUBLIC_SERIES_KEYS:
            member = build_observation_hour_series(
                root,
                commit_sha,
                PUBLIC_SERIES_KIND,
                series_key,
                window["start_utc"],
                window["end_utc"],
                replay_context=context,
            )
            validate_observation_hour_series(
                root,
                member,
                replay_context=context,
            )
            members.append(member)
    except ObservationHourSeriesError as exc:
        raise Phase18MultiAssetTemporalEvidenceError(
            "Phase 13 member construction or replay validation failed"
        ) from exc

    context_record = members[0].get("repository_context")
    if not isinstance(context_record, dict) or context_record.get("commit_sha") != commit_sha:
        raise Phase18MultiAssetTemporalEvidenceError(
            "bundle repository context is unavailable or commit-mismatched"
        )
    exact_window = _require_24_slot_window(window)
    for expected_key, member in zip(PUBLIC_SERIES_KEYS, members):
        _enforce_member_shape(member, expected_key, context_record, exact_window)

    try:
        phase15_btc = build_public_temporal_evidence(
            root,
            commit_sha,
            replay_context=context,
        )
    except Phase15PublicTemporalEvidenceError:
        raise
    if phase15_btc is None:
        raise Phase18MultiAssetTemporalEvidenceError(
            "Phase 15 BTC compatibility evidence is unavailable"
        )
    if canonical_json_bytes(members[0]) != canonical_public_evidence_bytes(phase15_btc):
        raise Phase18MultiAssetTemporalEvidenceError(
            "Phase 15 BTC canonical compatibility mismatch"
        )

    bundle: dict[str, Any] = {
        "contract": PHASE18_CONTRACT_VERSION,
        "repository_context": copy.deepcopy(context_record),
        "window": copy.deepcopy(exact_window),
        "series": members,
        "bundle_id": "",
    }
    bundle["bundle_id"] = bundle_id_for_record(bundle)
    return bundle


def validate_multi_asset_temporal_evidence(
    repository_root: Path,
    bundle: Any,
) -> dict[str, Any]:
    """Fail closed unless the bundle exactly replays from immutable repository evidence."""
    _validate_json_native(bundle)
    if not isinstance(bundle, dict) or set(bundle) != TOP_LEVEL_KEYS:
        raise Phase18MultiAssetTemporalEvidenceError("bundle top-level keys mismatch")
    if bundle.get("contract") != PHASE18_CONTRACT_VERSION:
        raise Phase18MultiAssetTemporalEvidenceError("bundle contract mismatch")

    context_record = bundle.get("repository_context")
    if not isinstance(context_record, dict) or not isinstance(context_record.get("commit_sha"), str):
        raise Phase18MultiAssetTemporalEvidenceError("bundle repository context is invalid")
    commit_sha = context_record["commit_sha"]
    window = _require_24_slot_window(bundle.get("window"))

    members = bundle.get("series")
    if not isinstance(members, list) or len(members) != len(PUBLIC_SERIES_KEYS):
        raise Phase18MultiAssetTemporalEvidenceError(
            "bundle must contain exactly BTC, ETH and SOL"
        )

    # Validation is a fresh replay pass. Delay context preparation until the
    # first member passes frozen-shape checks so malformed evidence retains the
    # same validation precedence as the pre-refactor implementation.
    replay_context: ObservationHourReplayContext | None = None
    for expected_key, member in zip(PUBLIC_SERIES_KEYS, members):
        member = _enforce_member_shape(member, expected_key, context_record, window)
        if replay_context is None:
            replay_context = _prepare_replay_context_or_legacy(
                Path(repository_root), commit_sha, None
            )
        try:
            validate_observation_hour_series(
                Path(repository_root),
                member,
                replay_context=replay_context,
            )
        except ObservationHourSeriesError as exc:
            raise Phase18MultiAssetTemporalEvidenceError(
                "bundle member immutable replay validation failed"
            ) from exc

    if (
        not isinstance(bundle.get("bundle_id"), str)
        or LOWER_HEX_64.fullmatch(bundle["bundle_id"]) is None
    ):
        raise Phase18MultiAssetTemporalEvidenceError(
            "bundle_id must be lower-case SHA-256"
        )
    if bundle["bundle_id"] != bundle_id_for_record(bundle):
        raise Phase18MultiAssetTemporalEvidenceError("bundle_id mismatch")

    try:
        phase15_btc = build_public_temporal_evidence(
            Path(repository_root),
            commit_sha,
            replay_context=replay_context,
        )
    except Phase15PublicTemporalEvidenceError as exc:
        raise Phase18MultiAssetTemporalEvidenceError(
            "Phase 15 BTC compatibility replay failed"
        ) from exc
    if phase15_btc is None or canonical_json_bytes(members[0]) != canonical_public_evidence_bytes(
        phase15_btc
    ):
        raise Phase18MultiAssetTemporalEvidenceError(
            "Phase 15 BTC canonical compatibility mismatch"
        )

    expected = build_multi_asset_temporal_evidence(
        Path(repository_root),
        commit_sha,
        replay_context=replay_context,
    )
    if expected is None or canonical_bundle_bytes(bundle) != canonical_bundle_bytes(expected):
        raise Phase18MultiAssetTemporalEvidenceError(
            "bundle does not match immutable Phase 18 replay"
        )
    return bundle
