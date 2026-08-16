#!/usr/bin/env python3
"""Resolve exact adjacent Phase 13 observation-hour snapshot evidence."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import build_crypto_snapshot_comparison_record as semantic_profile
import compare_crypto_snapshot_fields as comparison_adapter
import validate_crypto_observation_hour as observation_validator
import validate_crypto_snapshot as snapshot_validator
from validate_crypto_snapshot import ValidationError, load_config, parse_iso_timestamp

ADJACENCY_POLICY_VERSION = "phase13-observation-hour-adjacency/v1"
OBSERVATION_HOUR_CONTRACT_VERSION = "phase12-observation-hour/v1"
SEMANTIC_CONTRACT_VERSION = "phase10-snapshot-semantics-0.2/v1"
SNAPSHOT_PREFIX = PurePosixPath("data/crypto/hourly")
SNAPSHOT_SUFFIX = "_source_snapshot.json"
OBSERVATION_HOUR_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:00:00Z$")
GIT_SHA1_RE = re.compile(r"^[0-9a-f]{40}$")

PINNED_REFS = {
    "snapshot_validator": {
        "path": "scripts/validate_crypto_snapshot.py",
        "git_blob_sha": "b8c7fcc850bf0f5076f7d084bb6be9c24a9b7d3a",
    },
    "config": {
        "path": "config/crypto_sources.yml",
        "git_blob_sha": "73c5a3f3db81954951801c7d348d09a4c6296d73",
    },
    "observation_validator": {
        "path": "scripts/validate_crypto_observation_hour.py",
        "git_blob_sha": "21e18835c1047243ebda4b5ec7760fd9df793356",
    },
    "comparison_adapter": {
        "path": "scripts/compare_crypto_snapshot_fields.py",
        "git_blob_sha": "7a721cda7ab3d77b3c9291ff8373e5300bf00643",
    },
    "semantic_profile": {
        "path": "scripts/build_crypto_snapshot_comparison_record.py",
        "git_blob_sha": "8fe3347ed0574e40e564e6fc3e1842ada2be4c81",
    },
}


def _git_blob_sha(raw: bytes) -> str:
    return hashlib.sha1(f"blob {len(raw)}\0".encode("ascii") + raw).hexdigest()


def _git(repository_root: Path, *args: str) -> bytes:
    completed = subprocess.run(
        ["git", "-C", str(repository_root), *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(detail or f"git {' '.join(args)} failed")
    return completed.stdout


def _git_text(repository_root: Path, *args: str) -> str:
    return _git(repository_root, *args).decode("utf-8", errors="strict").strip()


def _is_snapshot_path(value: Any) -> bool:
    if not isinstance(value, str) or not value or "\\" in value:
        return False
    path = PurePosixPath(value)
    return (
        not path.is_absolute()
        and ".." not in path.parts
        and len(path.parts) >= 5
        and path.parts[:3] == SNAPSHOT_PREFIX.parts
        and path.name.endswith(SNAPSHOT_SUFFIX)
    )


def _empty_identity() -> dict[str, Any]:
    return {
        "path": None,
        "sha256": None,
        "schema_version": None,
        "generated_at_utc": None,
        "observation_hour_utc": None,
        "quality_status": None,
        "non_blocking_warnings": None,
    }


def _raw_identity(path: str, raw: bytes, payload: dict[str, Any]) -> dict[str, Any]:
    out = _empty_identity()
    out["path"] = path
    out["sha256"] = hashlib.sha256(raw).hexdigest()
    schema = payload.get("schema_version")
    out["schema_version"] = schema if isinstance(schema, str) and schema else None
    run = payload.get("run")
    if isinstance(run, dict):
        generated = run.get("generated_at_utc")
        slot = run.get("observation_hour_utc")
        out["generated_at_utc"] = generated if isinstance(generated, str) else None
        out["observation_hour_utc"] = slot if isinstance(slot, str) else None
    return out


def _context_template() -> dict[str, Any]:
    return {
        "commit_sha": None,
        "tree_sha": None,
        **{
            name: {"path": ref["path"], "git_blob_sha": None}
            for name, ref in PINNED_REFS.items()
        },
    }


def _runtime_module_matches(module: Any, expected_blob: str) -> bool:
    try:
        path = Path(module.__file__ or "")
        return _git_blob_sha(path.read_bytes()) == expected_blob
    except OSError:
        return False


def _resolve_repository_context(
    repository_root: Path, commit_sha: str
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    context = _context_template()
    if not isinstance(commit_sha, str) or GIT_SHA1_RE.fullmatch(commit_sha) is None:
        return context, None
    root = Path(repository_root)
    try:
        root = root.resolve(strict=True)
        if Path(_git_text(root, "rev-parse", "--show-toplevel")).resolve(strict=True) != root:
            return context, None
        resolved = _git_text(root, "rev-parse", "--verify", f"{commit_sha}^{{commit}}").lower()
        if resolved != commit_sha:
            return context, None
        context["commit_sha"] = resolved
        context["tree_sha"] = _git_text(root, "rev-parse", f"{resolved}^{{tree}}").lower()
        for name, ref in PINNED_REFS.items():
            context[name]["git_blob_sha"] = _git_text(
                root, "rev-parse", f"{resolved}:{ref['path']}"
            ).lower()
        if any(
            context[name]["git_blob_sha"] != ref["git_blob_sha"]
            for name, ref in PINNED_REFS.items()
        ):
            return context, None
        config_bytes = _git(root, "cat-file", "blob", f"{resolved}:{PINNED_REFS['config']['path']}")
    except (OSError, RuntimeError, UnicodeDecodeError):
        return context, None

    runtime_pairs = (
        (snapshot_validator, PINNED_REFS["snapshot_validator"]["git_blob_sha"]),
        (observation_validator, PINNED_REFS["observation_validator"]["git_blob_sha"]),
        (comparison_adapter, PINNED_REFS["comparison_adapter"]["git_blob_sha"]),
        (semantic_profile, PINNED_REFS["semantic_profile"]["git_blob_sha"]),
    )
    if any(not _runtime_module_matches(module, blob) for module, blob in runtime_pairs):
        return context, None

    try:
        with tempfile.TemporaryDirectory() as tmp:
            config_path = Path(tmp) / "crypto_sources.yml"
            config_path.write_bytes(config_bytes)
            config = load_config(config_path)
    except (OSError, ValidationError):
        return context, None
    return context, config


def _candidate_paths(repository_root: Path, commit_sha: str) -> list[str]:
    raw = _git(
        repository_root,
        "ls-tree",
        "-r",
        "-z",
        "--name-only",
        commit_sha,
        "--",
        SNAPSHOT_PREFIX.as_posix(),
    )
    paths = [part.decode("utf-8") for part in raw.split(b"\0") if part]
    return sorted(path for path in paths if _is_snapshot_path(path))


def _bytes_at_commit(repository_root: Path, commit_sha: str, path: str) -> bytes:
    return _git(repository_root, "cat-file", "blob", f"{commit_sha}:{path}")


def _parse_payload(raw: bytes) -> dict[str, Any] | None:
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _parse_slot(value: Any) -> datetime:
    if not isinstance(value, str) or OBSERVATION_HOUR_RE.fullmatch(value) is None:
        raise ValueError("observation hour must use canonical YYYY-MM-DDTHH:00:00Z form")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError("observation hour is invalid") from exc
    return parsed.astimezone(timezone.utc)


def _canonical_slot(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


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
        abbreviation = run.get("timezone_abbreviation")
        if abbreviation is not None and abbreviation != expected_local.tzname():
            return False
        tz_name = expected_local.tzname() or "LOCAL"
        safe_tz = "".join(ch for ch in tz_name if ch.isalnum()) or "LOCAL"
        expected = (
            SNAPSHOT_PREFIX
            / f"{expected_local.year:04d}"
            / f"{expected_local.month:02d}"
            / f"{expected_local.day:02d}"
            / f"{expected_local.hour:02d}{expected_local.minute:02d}_{safe_tz}_source_snapshot.json"
        )
        return path == expected
    except (KeyError, TypeError, ValueError, ValidationError, ZoneInfoNotFoundError):
        return False


def _validated_identity(
    path: str,
    raw: bytes,
    payload: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    try:
        with tempfile.TemporaryDirectory() as tmp:
            snapshot_path = Path(tmp) / "source_snapshot.json"
            snapshot_path.write_bytes(raw)
            observation_validator.validate_observation_hour(snapshot_path, config)
            quality = snapshot_validator.validate_snapshot(snapshot_path, config)
    except (OSError, ValidationError, ValueError) as exc:
        raise ValidationError("candidate failed Phase 12 validation") from exc
    out = _raw_identity(path, raw, payload)
    out["quality_status"] = quality["status"]
    out["non_blocking_warnings"] = list(quality["non_blocking_warnings"])
    return out


def _elapsed_seconds(current: datetime, predecessor: datetime) -> int | float:
    delta = current - predecessor
    micros = (delta.days * 86400 + delta.seconds) * 1_000_000 + delta.microseconds
    return micros // 1_000_000 if micros % 1_000_000 == 0 else micros / 1_000_000


def resolve_observation_hour_adjacency(
    repository_root: Path,
    commit_sha: str,
    current_slot_utc: str,
) -> dict[str, Any]:
    """Resolve current H and predecessor H-1h from one immutable Git tree."""

    current_slot = _parse_slot(current_slot_utc)
    predecessor_slot_utc = _canonical_slot(current_slot - timedelta(hours=1))
    result: dict[str, Any] = {
        "adjacency_policy_version": ADJACENCY_POLICY_VERSION,
        "repository_context": _context_template(),
        "current_slot_utc": current_slot_utc,
        "predecessor_slot_utc": predecessor_slot_utc,
        "resolution_status": "validation-contract-mismatch",
        "current_candidates": [],
        "predecessor_candidates": [],
        "current": None,
        "predecessor": None,
        "actual_elapsed_seconds": None,
    }

    context, config = _resolve_repository_context(Path(repository_root), commit_sha)
    result["repository_context"] = context
    if config is None:
        return result
    exact_commit = context["commit_sha"]
    assert isinstance(exact_commit, str)

    try:
        indexed: dict[str, list[tuple[str, bytes, dict[str, Any]]]] = {}
        for path in _candidate_paths(Path(repository_root), exact_commit):
            raw = _bytes_at_commit(Path(repository_root), exact_commit, path)
            payload = _parse_payload(raw)
            if payload is None:
                if b'"observation_hour_utc"' in raw:
                    result["resolution_status"] = "candidate-set-unorderable"
                    return result
                continue
            run = payload.get("run")
            if not isinstance(run, dict) or "observation_hour_utc" not in run:
                continue
            slot_value = run.get("observation_hour_utc")
            try:
                _parse_slot(slot_value)
            except ValueError:
                result["resolution_status"] = "candidate-set-unorderable"
                return result
            indexed.setdefault(slot_value, []).append((path, raw, payload))
    except (OSError, RuntimeError, UnicodeDecodeError):
        result["resolution_status"] = "candidate-set-unorderable"
        return result

    current_items = indexed.get(current_slot_utc, [])
    predecessor_items = indexed.get(predecessor_slot_utc, [])
    result["current_candidates"] = [
        _raw_identity(path, raw, payload) for path, raw, payload in current_items
    ]
    result["predecessor_candidates"] = [
        _raw_identity(path, raw, payload) for path, raw, payload in predecessor_items
    ]

    if not current_items:
        result["resolution_status"] = "current-missing"
        return result
    if len(current_items) > 1:
        result["resolution_status"] = "current-ambiguous"
        return result

    current_path, current_raw, current_payload = current_items[0]
    result["current"] = _raw_identity(current_path, current_raw, current_payload)
    if not _identity_is_consistent(current_path, current_payload):
        result["resolution_status"] = "current-identity-invalid"
        return result
    try:
        result["current"] = _validated_identity(
            current_path, current_raw, current_payload, config
        )
    except ValidationError:
        result["resolution_status"] = "current-invalid"
        return result

    if not predecessor_items:
        result["resolution_status"] = "predecessor-missing"
        return result
    if len(predecessor_items) > 1:
        result["resolution_status"] = "predecessor-ambiguous"
        return result

    predecessor_path, predecessor_raw, predecessor_payload = predecessor_items[0]
    result["predecessor"] = _raw_identity(
        predecessor_path, predecessor_raw, predecessor_payload
    )
    if not _identity_is_consistent(predecessor_path, predecessor_payload):
        result["resolution_status"] = "predecessor-identity-invalid"
        return result
    try:
        result["predecessor"] = _validated_identity(
            predecessor_path, predecessor_raw, predecessor_payload, config
        )
    except ValidationError:
        result["resolution_status"] = "predecessor-invalid"
        return result

    current_utc = parse_iso_timestamp(
        current_payload["run"]["generated_at_utc"], "run.generated_at_utc"
    )
    predecessor_utc = parse_iso_timestamp(
        predecessor_payload["run"]["generated_at_utc"], "run.generated_at_utc"
    )
    result["actual_elapsed_seconds"] = _elapsed_seconds(current_utc, predecessor_utc)
    result["resolution_status"] = "adjacency-resolved"
    return result
