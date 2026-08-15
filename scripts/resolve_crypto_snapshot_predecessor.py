#!/usr/bin/env python3
"""Deterministically resolve the immediate prior CryptoPulse source snapshot."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from validate_crypto_snapshot import ValidationError, parse_iso_timestamp, validate_snapshot

PREDECESSOR_POLICY_VERSION = "phase10-predecessor-exact-hour/v1"
REPOSITORY_SNAPSHOT_PREFIX = PurePosixPath("data/crypto/hourly")
SNAPSHOT_GLOB = "*_source_snapshot.json"


def _empty_input_record() -> dict[str, Any]:
    return {
        "path": None,
        "sha256": None,
        "schema_version": None,
        "generated_at_utc": None,
        "quality_status": None,
        "non_blocking_warnings": None,
    }


def _result(status: str) -> dict[str, Any]:
    return {
        "predecessor_policy_version": PREDECESSOR_POLICY_VERSION,
        "resolution_status": status,
        "current": _empty_input_record(),
        "predecessor": None,
        "elapsed_seconds": None,
    }


def _read_bytes(path: Path) -> bytes:
    return path.read_bytes()


def _parse_snapshot_bytes(raw: bytes) -> dict[str, Any]:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationError(f"invalid snapshot bytes: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValidationError("snapshot root must be an object")
    return payload


def _relative_snapshot_path(path: Path, snapshot_root: Path) -> Path:
    try:
        return path.resolve().relative_to(snapshot_root.resolve())
    except (OSError, ValueError) as exc:
        raise ValidationError("snapshot path is outside the repository snapshot root") from exc


def _repository_path(relative_path: Path) -> str:
    return str(REPOSITORY_SNAPSHOT_PREFIX / PurePosixPath(relative_path.as_posix()))


def _safe_timezone_abbreviation(value: str | None) -> str:
    return "".join(ch for ch in (value or "LOCAL") if ch.isalnum()) or "LOCAL"


def _parse_local_with_explicit_offset(value: Any) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError("run.generated_at_local must be a non-empty string")
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValidationError("run.generated_at_local must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValidationError("run.generated_at_local must contain an explicit UTC offset")
    return parsed


def _identity_consistent(
    snapshot: dict[str, Any],
    relative_path: Path,
    generated_at: datetime,
) -> bool:
    run = snapshot.get("run")
    if not isinstance(run, dict):
        return False

    try:
        local_time = _parse_local_with_explicit_offset(run.get("generated_at_local"))
        timezone_name = run.get("timezone")
        if not isinstance(timezone_name, str) or not timezone_name.strip():
            return False
        zone = ZoneInfo(timezone_name)
    except (ValidationError, ZoneInfoNotFoundError, ValueError):
        return False

    generated_utc = generated_at.astimezone(timezone.utc)
    if local_time.astimezone(timezone.utc) != generated_utc:
        return False

    zoned = generated_utc.astimezone(zone)
    local_wall = (
        local_time.year,
        local_time.month,
        local_time.day,
        local_time.hour,
        local_time.minute,
    )
    zoned_wall = (
        zoned.year,
        zoned.month,
        zoned.day,
        zoned.hour,
        zoned.minute,
    )
    if local_wall != zoned_wall or local_time.utcoffset() != zoned.utcoffset():
        return False

    timezone_abbreviation = run.get("timezone_abbreviation")
    expected_abbreviation = zoned.tzname() or "LOCAL"
    if timezone_abbreviation is not None:
        if not isinstance(timezone_abbreviation, str) or timezone_abbreviation != expected_abbreviation:
            return False

    safe_tz = _safe_timezone_abbreviation(expected_abbreviation)
    expected_relative = Path(
        f"{zoned.year:04d}",
        f"{zoned.month:02d}",
        f"{zoned.day:02d}",
        f"{zoned.hour:02d}{zoned.minute:02d}_{safe_tz}_source_snapshot.json",
    )
    return relative_path.as_posix() == expected_relative.as_posix()


def _populate_validated_record(
    record: dict[str, Any],
    snapshot: dict[str, Any],
    quality: dict[str, Any],
) -> datetime:
    run = snapshot.get("run")
    if not isinstance(run, dict):
        raise ValidationError("run must be an object")

    generated_raw = run.get("generated_at_utc")
    generated_at = parse_iso_timestamp(generated_raw, "run.generated_at_utc")
    record["schema_version"] = snapshot.get("schema_version")
    record["generated_at_utc"] = generated_raw
    record["quality_status"] = quality.get("status")
    warnings = quality.get("non_blocking_warnings")
    record["non_blocking_warnings"] = list(warnings) if isinstance(warnings, list) else []
    return generated_at


def _minimal_candidate(
    path: Path,
    relative_path: Path,
) -> tuple[dict[str, Any], bytes, dict[str, Any], datetime]:
    raw = _read_bytes(path)
    snapshot = _parse_snapshot_bytes(raw)
    run = snapshot.get("run")
    if not isinstance(run, dict):
        raise ValidationError("candidate run must be an object")
    generated_at = parse_iso_timestamp(run.get("generated_at_utc"), "run.generated_at_utc")

    record = _empty_input_record()
    record["path"] = _repository_path(relative_path)
    record["sha256"] = hashlib.sha256(raw).hexdigest()
    record["schema_version"] = snapshot.get("schema_version")
    record["generated_at_utc"] = run.get("generated_at_utc")
    return record, raw, snapshot, generated_at


def resolve_predecessor(
    current_path: Path,
    snapshot_root: Path,
    config: dict[str, Any],
) -> dict[str, Any]:
    """Resolve one immediate predecessor under ``phase10-predecessor-exact-hour/v1``.

    ``snapshot_root`` must represent the repository-owned ``data/crypto/hourly``
    tree from the caller's governed repository context. This function performs
    no network access and writes no files.
    """

    current_path = Path(current_path)
    snapshot_root = Path(snapshot_root)
    result = _result("current-invalid")

    try:
        current_raw = _read_bytes(current_path)
    except (OSError, UnicodeError):
        return result

    result["current"]["sha256"] = hashlib.sha256(current_raw).hexdigest()

    try:
        current_relative = _relative_snapshot_path(current_path, snapshot_root)
    except ValidationError:
        current_relative = None
    if current_relative is not None:
        result["current"]["path"] = _repository_path(current_relative)

    try:
        current_quality = validate_snapshot(current_path, config)
        current_snapshot = _parse_snapshot_bytes(current_raw)
        current_generated_at = _populate_validated_record(
            result["current"], current_snapshot, current_quality
        )
    except (ValidationError, OSError, UnicodeError):
        return result

    if current_relative is None or not _identity_consistent(
        current_snapshot, current_relative, current_generated_at
    ):
        result["resolution_status"] = "current-identity-invalid"
        return result

    try:
        candidates = sorted(
            (
                candidate
                for candidate in snapshot_root.rglob(SNAPSHOT_GLOB)
                if candidate.resolve() != current_path.resolve()
            ),
            key=lambda candidate: _relative_snapshot_path(candidate, snapshot_root).as_posix(),
        )
    except (OSError, ValidationError):
        result["resolution_status"] = "candidate-set-unorderable"
        return result

    ordered: list[
        tuple[Path, Path, dict[str, Any], bytes, dict[str, Any], datetime]
    ] = []
    for candidate in candidates:
        try:
            relative = _relative_snapshot_path(candidate, snapshot_root)
            record, raw, snapshot, generated_at = _minimal_candidate(candidate, relative)
        except (ValidationError, OSError, UnicodeError):
            result["resolution_status"] = "candidate-set-unorderable"
            return result
        ordered.append((candidate, relative, record, raw, snapshot, generated_at))

    prior = [item for item in ordered if item[5] < current_generated_at]
    if not prior:
        result["resolution_status"] = "predecessor-missing"
        return result

    greatest_prior = max(item[5] for item in prior)
    immediate = [item for item in prior if item[5] == greatest_prior]
    if len(immediate) != 1:
        result["resolution_status"] = "predecessor-ambiguous"
        return result

    (
        predecessor_path,
        predecessor_relative,
        predecessor_record,
        _predecessor_raw,
        predecessor_snapshot,
        predecessor_generated_at,
    ) = immediate[0]
    result["predecessor"] = predecessor_record

    try:
        predecessor_quality = validate_snapshot(predecessor_path, config)
        predecessor_generated_at = _populate_validated_record(
            predecessor_record, predecessor_snapshot, predecessor_quality
        )
    except (ValidationError, OSError, UnicodeError):
        result["resolution_status"] = "predecessor-invalid"
        return result

    if not _identity_consistent(
        predecessor_snapshot, predecessor_relative, predecessor_generated_at
    ):
        result["resolution_status"] = "predecessor-identity-invalid"
        return result

    elapsed = current_generated_at - predecessor_generated_at
    total_seconds = elapsed.total_seconds()
    result["elapsed_seconds"] = int(total_seconds) if total_seconds.is_integer() else total_seconds
    if elapsed != timedelta(seconds=3600):
        result["resolution_status"] = "predecessor-out-of-window"
        return result

    if result["current"]["schema_version"] != predecessor_record["schema_version"]:
        result["resolution_status"] = "pair-schema-incompatible"
        return result

    result["resolution_status"] = "predecessor-resolved"
    return result
