#!/usr/bin/env python3
"""Resolve an immutable repository-owned predecessor for one crypto snapshot."""

from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import validate_crypto_snapshot as snapshot_validator
from validate_crypto_snapshot import ValidationError, load_config, parse_iso_timestamp, validate_snapshot

PREDECESSOR_POLICY_VERSION = "phase10-predecessor-exact-hour/v1"
SNAPSHOT_REPOSITORY_PREFIX = PurePosixPath("data/crypto/hourly")
EXACT_PREDECESSOR_SECONDS = 3600
PINNED_VALIDATOR_PATH = "scripts/validate_crypto_snapshot.py"
PINNED_VALIDATOR_BLOB_SHA = "b8c7fcc850bf0f5076f7d084bb6be9c24a9b7d3a"
PINNED_CONFIG_PATH = "config/crypto_sources.yml"
PINNED_CONFIG_BLOB_SHA = "73c5a3f3db81954951801c7d348d09a4c6296d73"


def _empty_identity() -> dict[str, Any]:
    return {
        "path": None,
        "sha256": None,
        "schema_version": None,
        "generated_at_utc": None,
        "quality_status": None,
        "non_blocking_warnings": None,
    }


def _empty_repository_context() -> dict[str, Any]:
    return {
        "commit_sha": None,
        "tree_sha": None,
        "validator": {
            "path": None,
            "git_blob_sha": None,
        },
        "config": {
            "path": None,
            "git_blob_sha": None,
        },
    }


def _normalise_repository_context(value: Any) -> dict[str, Any]:
    out = _empty_repository_context()
    if not isinstance(value, dict):
        return out
    for key in ("commit_sha", "tree_sha"):
        if isinstance(value.get(key), str):
            out[key] = value[key]
    for key in ("validator", "config"):
        nested = value.get(key)
        if not isinstance(nested, dict):
            continue
        for field in ("path", "git_blob_sha"):
            if isinstance(nested.get(field), str):
                out[key][field] = nested[field]
    return out


def _empty_result(repository_context: Any) -> dict[str, Any]:
    return {
        "predecessor_policy_version": PREDECESSOR_POLICY_VERSION,
        "repository_context": _normalise_repository_context(repository_context),
        "resolution_status": None,
        "current": _empty_identity(),
        "predecessor": None,
        "elapsed_seconds": None,
    }


def _canonical_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _git_blob_sha(raw: bytes) -> str:
    header = f"blob {len(raw)}\0".encode("ascii")
    return hashlib.sha1(header + raw).hexdigest()


def _run_git(repository_root: Path, *args: str) -> bytes:
    completed = subprocess.run(
        ["git", "-C", str(repository_root), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.stdout


def _git_text(repository_root: Path, *args: str) -> str:
    return _run_git(repository_root, *args).decode("utf-8").strip()


def _is_full_git_oid(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 40
        and value == value.lower()
        and all(ch in "0123456789abcdef" for ch in value)
    )


def _is_snapshot_path(value: Any) -> bool:
    if not isinstance(value, str) or not value:
        return False
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts:
        return False
    prefix = SNAPSHOT_REPOSITORY_PREFIX.parts
    return (
        len(path.parts) > len(prefix)
        and path.parts[: len(prefix)] == prefix
        and path.name.endswith("_source_snapshot.json")
    )


def _git_object_blob_sha(repository_root: Path, commit_sha: str, path: str) -> str:
    return _git_text(repository_root, "rev-parse", f"{commit_sha}:{path}")


def _git_object_bytes(repository_root: Path, commit_sha: str, path: str) -> bytes:
    return _run_git(repository_root, "cat-file", "blob", f"{commit_sha}:{path}")


def _validate_repository_context(
    repository_root: Path,
    repository_context: Any,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    context = _normalise_repository_context(repository_context)
    commit_sha = context["commit_sha"]
    tree_sha = context["tree_sha"]
    validator = context["validator"]
    config_ref = context["config"]

    if not (_is_full_git_oid(commit_sha) and _is_full_git_oid(tree_sha)):
        return None
    if validator != {
        "path": PINNED_VALIDATOR_PATH,
        "git_blob_sha": PINNED_VALIDATOR_BLOB_SHA,
    }:
        return None
    if config_ref != {
        "path": PINNED_CONFIG_PATH,
        "git_blob_sha": PINNED_CONFIG_BLOB_SHA,
    }:
        return None

    try:
        root = repository_root.resolve(strict=True)
        git_root = Path(_git_text(root, "rev-parse", "--show-toplevel")).resolve(strict=True)
        if git_root != root:
            return None
        if _git_text(root, "cat-file", "-t", commit_sha) != "commit":
            return None
        if _git_text(root, "rev-parse", f"{commit_sha}^{{tree}}") != tree_sha:
            return None
        if _git_object_blob_sha(root, commit_sha, PINNED_VALIDATOR_PATH) != PINNED_VALIDATOR_BLOB_SHA:
            return None
        if _git_object_blob_sha(root, commit_sha, PINNED_CONFIG_PATH) != PINNED_CONFIG_BLOB_SHA:
            return None
        config_bytes = _git_object_bytes(root, commit_sha, PINNED_CONFIG_PATH)
    except (OSError, UnicodeError, subprocess.CalledProcessError):
        return None

    runtime_validator_path = Path(snapshot_validator.__file__ or "")
    try:
        runtime_validator_bytes = runtime_validator_path.read_bytes()
    except OSError:
        return None
    if _git_blob_sha(runtime_validator_bytes) != PINNED_VALIDATOR_BLOB_SHA:
        return None

    try:
        __import__("yaml")
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "crypto_sources.yml"
            config_path.write_bytes(config_bytes)
            config = load_config(config_path)
    except (ImportError, OSError, UnicodeError, ValidationError):
        return None
    if not config:
        return None

    return context, config


def _load_snapshot_bytes(raw: bytes) -> dict[str, Any]:
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("snapshot root must be an object")
    return payload


def _raw_identity(path: str, raw: bytes, payload: dict[str, Any]) -> dict[str, Any]:
    identity = _empty_identity()
    identity["path"] = path
    identity["sha256"] = hashlib.sha256(raw).hexdigest()
    identity["schema_version"] = payload.get("schema_version")
    run = payload.get("run")
    if isinstance(run, dict):
        try:
            identity["generated_at_utc"] = _canonical_utc(
                parse_iso_timestamp(run.get("generated_at_utc"), "run.generated_at_utc")
            )
        except ValidationError:
            pass
    return identity


def _validated_identity(
    path: str,
    raw: bytes,
    payload: dict[str, Any],
    quality: dict[str, Any],
) -> dict[str, Any]:
    identity = _raw_identity(path, raw, payload)
    identity["quality_status"] = quality["status"]
    identity["non_blocking_warnings"] = list(quality["non_blocking_warnings"])
    return identity


def _parse_local_timestamp(value: Any) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("run.generated_at_local must be a non-empty string")
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("run.generated_at_local must contain an explicit UTC offset")
    return parsed


def _identity_is_consistent(repository_path: str, payload: dict[str, Any]) -> bool:
    try:
        path = PurePosixPath(repository_path)
        if not _is_snapshot_path(repository_path):
            return False

        run = payload["run"]
        utc_value = parse_iso_timestamp(run["generated_at_utc"], "run.generated_at_utc")
        local_value = _parse_local_timestamp(run["generated_at_local"])
        timezone_name = run["timezone"]
        if not isinstance(timezone_name, str) or not timezone_name.strip():
            return False
        zone = ZoneInfo(timezone_name)

        expected_local = utc_value.astimezone(zone)
        if local_value.astimezone(timezone.utc) != utc_value:
            return False
        if local_value.replace(tzinfo=None) != expected_local.replace(tzinfo=None):
            return False
        if local_value.utcoffset() != expected_local.utcoffset():
            return False

        timezone_abbreviation = run.get("timezone_abbreviation")
        if timezone_abbreviation is not None and timezone_abbreviation != expected_local.tzname():
            return False

        tz_name = expected_local.tzname() or "LOCAL"
        safe_tz = "".join(ch for ch in tz_name if ch.isalnum()) or "LOCAL"
        expected = (
            SNAPSHOT_REPOSITORY_PREFIX
            / f"{expected_local.year:04d}"
            / f"{expected_local.month:02d}"
            / f"{expected_local.day:02d}"
            / f"{expected_local.hour:02d}{expected_local.minute:02d}_{safe_tz}_source_snapshot.json"
        )
        return path == expected
    except (
        KeyError,
        TypeError,
        ValueError,
        ValidationError,
        ZoneInfoNotFoundError,
    ):
        return False


def _current_matches_supplied_identity(
    supplied: Any,
    path: str,
    raw: bytes,
    payload: dict[str, Any],
) -> bool:
    if not isinstance(supplied, dict):
        return False
    required = ("path", "sha256", "schema_version", "generated_at_utc")
    if any(not isinstance(supplied.get(key), str) for key in required):
        return False
    if supplied["path"] != path:
        return False
    if supplied["sha256"] != hashlib.sha256(raw).hexdigest():
        return False
    if supplied["schema_version"] != payload.get("schema_version"):
        return False
    run = payload.get("run")
    if not isinstance(run, dict) or supplied["generated_at_utc"] != run.get("generated_at_utc"):
        return False
    return True


def _validate_snapshot_bytes(raw: bytes, config: dict[str, Any]) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "source_snapshot.json"
        path.write_bytes(raw)
        return validate_snapshot(path, config)


def _candidate_paths(repository_root: Path, commit_sha: str) -> list[str]:
    output = _run_git(
        repository_root,
        "ls-tree",
        "-r",
        "--name-only",
        commit_sha,
        "--",
        SNAPSHOT_REPOSITORY_PREFIX.as_posix(),
    )
    paths = output.decode("utf-8").splitlines()
    return sorted(path for path in paths if _is_snapshot_path(path))


def _ordering_timestamp(raw: bytes) -> datetime:
    payload = _load_snapshot_bytes(raw)
    run = payload.get("run")
    if not isinstance(run, dict):
        raise ValueError("candidate run metadata is missing")
    return parse_iso_timestamp(run.get("generated_at_utc"), "run.generated_at_utc")


def _elapsed_seconds(current: datetime, predecessor: datetime) -> int | float:
    delta = current - predecessor
    total_microseconds = (
        (delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds
    )
    if total_microseconds % 1_000_000 == 0:
        return total_microseconds // 1_000_000
    return total_microseconds / 1_000_000


def resolve_predecessor(
    current: dict[str, Any],
    repository_root: Path,
    repository_context: dict[str, Any],
) -> dict[str, Any]:
    """Resolve one immutable predecessor under phase10-predecessor-exact-hour/v1."""

    repository_root = Path(repository_root)
    result = _empty_result(repository_context)

    validated_context = _validate_repository_context(repository_root, repository_context)
    if validated_context is None:
        result["resolution_status"] = "validation-contract-mismatch"
        return result
    context, config = validated_context
    result["repository_context"] = context
    commit_sha = context["commit_sha"]

    current_path = current.get("path") if isinstance(current, dict) else None
    if not _is_snapshot_path(current_path):
        result["resolution_status"] = "current-identity-invalid"
        return result

    try:
        current_raw = _git_object_bytes(repository_root, commit_sha, current_path)
        current_payload = _load_snapshot_bytes(current_raw)
    except (
        OSError,
        UnicodeError,
        ValueError,
        json.JSONDecodeError,
        subprocess.CalledProcessError,
    ):
        result["resolution_status"] = "current-identity-invalid"
        return result

    result["current"] = _raw_identity(current_path, current_raw, current_payload)
    if not _current_matches_supplied_identity(
        current, current_path, current_raw, current_payload
    ) or not _identity_is_consistent(current_path, current_payload):
        result["resolution_status"] = "current-identity-invalid"
        return result

    try:
        current_quality = _validate_snapshot_bytes(current_raw, config)
    except (ValidationError, OSError, UnicodeError, ValueError):
        result["resolution_status"] = "current-invalid"
        return result

    result["current"] = _validated_identity(
        current_path,
        current_raw,
        current_payload,
        current_quality,
    )
    current_utc = parse_iso_timestamp(
        current_payload["run"]["generated_at_utc"], "run.generated_at_utc"
    )

    try:
        candidates = _candidate_paths(repository_root, commit_sha)
    except (OSError, UnicodeError, subprocess.CalledProcessError):
        result["resolution_status"] = "candidate-set-unorderable"
        return result

    ordered: list[tuple[datetime, str]] = []
    for candidate_path in candidates:
        if candidate_path == current_path:
            continue
        try:
            candidate_raw = _git_object_bytes(repository_root, commit_sha, candidate_path)
            candidate_utc = _ordering_timestamp(candidate_raw)
        except (
            OSError,
            UnicodeError,
            ValueError,
            json.JSONDecodeError,
            ValidationError,
            subprocess.CalledProcessError,
        ):
            result["resolution_status"] = "candidate-set-unorderable"
            return result
        ordered.append((candidate_utc, candidate_path))

    prior = [(timestamp, path) for timestamp, path in ordered if timestamp < current_utc]
    if not prior:
        result["resolution_status"] = "predecessor-missing"
        return result

    greatest_prior = max(timestamp for timestamp, _ in prior)
    immediate = [path for timestamp, path in prior if timestamp == greatest_prior]
    if len(immediate) != 1:
        result["resolution_status"] = "predecessor-ambiguous"
        return result

    predecessor_path = immediate[0]
    try:
        predecessor_raw = _git_object_bytes(repository_root, commit_sha, predecessor_path)
        predecessor_payload = _load_snapshot_bytes(predecessor_raw)
    except (
        OSError,
        UnicodeError,
        ValueError,
        json.JSONDecodeError,
        subprocess.CalledProcessError,
    ):
        result["resolution_status"] = "predecessor-identity-invalid"
        return result

    result["predecessor"] = _raw_identity(
        predecessor_path, predecessor_raw, predecessor_payload
    )
    if not _identity_is_consistent(predecessor_path, predecessor_payload):
        result["resolution_status"] = "predecessor-identity-invalid"
        return result

    try:
        predecessor_quality = _validate_snapshot_bytes(predecessor_raw, config)
    except (ValidationError, OSError, UnicodeError, ValueError):
        result["resolution_status"] = "predecessor-invalid"
        return result

    result["predecessor"] = _validated_identity(
        predecessor_path,
        predecessor_raw,
        predecessor_payload,
        predecessor_quality,
    )
    predecessor_utc = parse_iso_timestamp(
        predecessor_payload["run"]["generated_at_utc"], "run.generated_at_utc"
    )
    elapsed = _elapsed_seconds(current_utc, predecessor_utc)
    result["elapsed_seconds"] = elapsed
    if elapsed != EXACT_PREDECESSOR_SECONDS:
        result["resolution_status"] = "predecessor-out-of-window"
        return result

    if current_payload["schema_version"] != predecessor_payload["schema_version"]:
        result["resolution_status"] = "pair-schema-incompatible"
        return result

    result["resolution_status"] = "predecessor-resolved"
    return result
