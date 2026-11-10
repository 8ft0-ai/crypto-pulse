#!/usr/bin/env python3
"""Deterministic Phase 11 temporal-series construction and validation."""

from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import re
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from build_crypto_snapshot_comparison_record import build_comparison_record
from validate_crypto_snapshot import ValidationError, parse_iso_timestamp
from validate_crypto_snapshot_comparison import (
    COMPARISON_SCHEMA_VERSION,
    CONFIG_BLOB_SHA,
    CONFIG_PATH,
    PREDECESSOR_POLICY_VERSION,
    SEMANTIC_CONTRACT_VERSION,
    VALIDATOR_BLOB_SHA,
    VALIDATOR_PATH,
)

SERIES_SCHEMA_VERSION = "crypto-temporal-series/v1"
PHASE10_COMPARISON_SCHEMA_VERSION = "crypto-snapshot-comparison/v1"
PHASE10_PREDECESSOR_POLICY_VERSION = "phase10-predecessor-exact-hour/v1"
PHASE10_SEMANTIC_CONTRACT_VERSION = "phase10-snapshot-semantics-0.2/v1"
PHASE10_VALIDATOR_PATH = "scripts/validate_crypto_snapshot.py"
PHASE10_VALIDATOR_BLOB_SHA = "b8c7fcc850bf0f5076f7d084bb6be9c24a9b7d3a"
PHASE10_CONFIG_PATH = "config/crypto_sources.yml"
PHASE10_CONFIG_BLOB_SHA = "73c5a3f3db81954951801c7d348d09a4c6296d73"
SNAPSHOT_PREFIX = PurePosixPath("data/crypto/hourly")
SNAPSHOT_SUFFIX = "_source_snapshot.json"
MAX_SLOTS = 168
LOWER_HEX_40 = re.compile(r"^[0-9a-f]{40}$")
LOWER_HEX_64 = re.compile(r"^[0-9a-f]{64}$")

METRIC_IDENTITIES: dict[str, tuple[str, str | None, str]] = {
    "BTC.price_usd": ("market-asset", "BTC", "price_usd"),
    "BTC.market_cap_usd": ("market-asset", "BTC", "market_cap_usd"),
    "BTC.volume_24h_usd": ("market-asset", "BTC", "volume_24h_usd"),
    "ETH.price_usd": ("market-asset", "ETH", "price_usd"),
    "ETH.market_cap_usd": ("market-asset", "ETH", "market_cap_usd"),
    "ETH.volume_24h_usd": ("market-asset", "ETH", "volume_24h_usd"),
    "SOL.price_usd": ("market-asset", "SOL", "price_usd"),
    "SOL.market_cap_usd": ("market-asset", "SOL", "market_cap_usd"),
    "SOL.volume_24h_usd": ("market-asset", "SOL", "volume_24h_usd"),
    "defi.total_tvl_usd": ("defi-aggregate", None, "total_tvl_usd"),
    "USDT.circulating_usd": ("stablecoin", "USDT", "circulating_usd"),
    "USDC.circulating_usd": ("stablecoin", "USDC", "circulating_usd"),
}
SOURCE_IDENTITIES = (
    "coingecko",
    "defillama",
    "coinbase_exchange",
    "kraken",
    "okx",
    "binance",
    "bybit",
    "cryptocompare",
)
SOURCE_STATUSES = {"ok", "warning", "error", "skipped", "missing"}
PHASE10_GAP_MAP = {
    "validation-contract-mismatch": "phase10-validation-contract-mismatch",
    "current-invalid": "phase10-current-invalid",
    "current-identity-invalid": "phase10-current-identity-invalid",
    "candidate-set-unorderable": "phase10-candidate-set-unorderable",
    "predecessor-missing": "phase10-predecessor-missing",
    "predecessor-ambiguous": "phase10-predecessor-ambiguous",
    "predecessor-invalid": "phase10-predecessor-invalid",
    "predecessor-identity-invalid": "phase10-predecessor-identity-invalid",
    "predecessor-out-of-window": "phase10-predecessor-out-of-window",
    "pair-schema-incompatible": "phase10-pair-schema-incompatible",
    "pair-semantics-incompatible": "phase10-pair-semantics-incompatible",
    "comparison-ready": "phase10-comparison-ready",
}
METRIC_GAP_MAP = {
    "unavailable-current": "metric-unavailable-current",
    "unavailable-predecessor": "metric-unavailable-predecessor",
    "invalid-current": "metric-invalid-current",
    "invalid-predecessor": "metric-invalid-predecessor",
}
GAP_REASONS = {"current-missing", "current-ambiguous", *PHASE10_GAP_MAP.values(), *METRIC_GAP_MAP.values()}

TOP_LEVEL_KEYS = {
    "schema_version",
    "series_kind",
    "series_key",
    "window",
    "repository_context",
    "phase10",
    "entries",
    "series_id",
}
WINDOW_KEYS = {"start_utc", "end_utc"}
REPOSITORY_KEYS = {"commit_sha", "tree_sha", "validator", "config"}
CONTRACT_REF_KEYS = {"path", "git_blob_sha"}
PHASE10_KEYS = {
    "comparison_schema_version",
    "predecessor_policy_version",
    "semantic_contract_version",
}
ENTRY_KEYS = {"slot_utc", "value", "gap"}
VALUE_KEYS = {"datum", "comparison_id", "current", "predecessor", "evidence"}
CANDIDATE_KEYS = {"path", "sha256", "schema_version", "generated_at_utc"}


class TemporalSeriesError(ValueError):
    """Raised when a Phase 11 series cannot be constructed or validated."""


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def series_id_for_record(record: dict[str, Any]) -> str:
    payload = copy.deepcopy(record)
    payload.pop("series_id", None)
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def _git(repository_root: Path, *args: str) -> bytes:
    env = os.environ.copy()
    env["GIT_OPTIONAL_LOCKS"] = "0"
    env["LC_ALL"] = "C"
    completed = subprocess.run(
        ["git", "-C", str(repository_root), *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise TemporalSeriesError(detail or f"git {' '.join(args)} failed")
    return completed.stdout


def _git_text(repository_root: Path, *args: str) -> str:
    return _git(repository_root, *args).decode("utf-8", errors="strict").strip()


def _git_oid(repository_root: Path, spec: str) -> str:
    value = _git_text(repository_root, "rev-parse", "--verify", spec).lower()
    if not LOWER_HEX_40.fullmatch(value):
        raise TemporalSeriesError(f"invalid git object identity for {spec}")
    return value


def _assert_phase10_runtime_contract() -> None:
    expected = (
        PHASE10_COMPARISON_SCHEMA_VERSION,
        PHASE10_PREDECESSOR_POLICY_VERSION,
        PHASE10_SEMANTIC_CONTRACT_VERSION,
        PHASE10_VALIDATOR_PATH,
        PHASE10_VALIDATOR_BLOB_SHA,
        PHASE10_CONFIG_PATH,
        PHASE10_CONFIG_BLOB_SHA,
    )
    actual = (
        COMPARISON_SCHEMA_VERSION,
        PREDECESSOR_POLICY_VERSION,
        SEMANTIC_CONTRACT_VERSION,
        VALIDATOR_PATH,
        VALIDATOR_BLOB_SHA,
        CONFIG_PATH,
        CONFIG_BLOB_SHA,
    )
    if actual != expected:
        raise TemporalSeriesError("runtime Phase 10 contract differs from frozen Phase 11 binding")


def _repository_context(repository_root: Path, commit_sha: str) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    _assert_phase10_runtime_contract()
    if not isinstance(commit_sha, str) or not LOWER_HEX_40.fullmatch(commit_sha.strip().lower()):
        raise TemporalSeriesError("commit_sha must be an exact 40-character Git SHA-1")
    supplied = commit_sha.strip().lower()
    resolved = _git_oid(root, f"{supplied}^{{commit}}")
    if resolved != supplied:
        raise TemporalSeriesError("commit_sha must resolve to itself exactly")
    try:
        git_root = Path(_git_text(root, "rev-parse", "--show-toplevel")).resolve(strict=True)
    except OSError as exc:
        raise TemporalSeriesError("repository_root must resolve to a Git work tree") from exc
    if git_root != root:
        raise TemporalSeriesError("repository_root must be the Git work-tree root")
    tree_sha = _git_oid(root, f"{resolved}^{{tree}}")
    validator_blob = _git_oid(root, f"{resolved}:{PHASE10_VALIDATOR_PATH}")
    config_blob = _git_oid(root, f"{resolved}:{PHASE10_CONFIG_PATH}")
    if validator_blob != PHASE10_VALIDATOR_BLOB_SHA or config_blob != PHASE10_CONFIG_BLOB_SHA:
        raise TemporalSeriesError("immutable Phase 10 validator/config identity mismatch")
    return {
        "commit_sha": resolved,
        "tree_sha": tree_sha,
        "validator": {"path": PHASE10_VALIDATOR_PATH, "git_blob_sha": validator_blob},
        "config": {"path": PHASE10_CONFIG_PATH, "git_blob_sha": config_blob},
    }


def _canonical_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_window_timestamp(value: Any, path: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise TemporalSeriesError(f"{path} must be a non-empty UTC timestamp")
    text = value.strip()
    normalized = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise TemporalSeriesError(f"{path} must be an ISO-8601 UTC timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise TemporalSeriesError(f"{path} must include an explicit UTC offset")
    return parsed.astimezone(timezone.utc)


def _window(start_utc: str, end_utc: str) -> tuple[datetime, datetime, list[datetime]]:
    start = _parse_window_timestamp(start_utc, "window.start_utc")
    end = _parse_window_timestamp(end_utc, "window.end_utc")
    for name, value in (("start_utc", start), ("end_utc", end)):
        if value.minute or value.second or value.microsecond:
            raise TemporalSeriesError(f"window.{name} must be aligned to an exact UTC hour")
    if end < start:
        raise TemporalSeriesError("window.end_utc must not precede window.start_utc")
    seconds = int((end - start).total_seconds())
    if seconds % 3600:
        raise TemporalSeriesError("window must contain exact hourly slots")
    count = seconds // 3600 + 1
    if count < 1 or count > MAX_SLOTS:
        raise TemporalSeriesError(f"window must contain between 1 and {MAX_SLOTS} hourly slots")
    slots = [start + timedelta(hours=index) for index in range(count)]
    return start, end, slots


def _series_identity(series_kind: str, series_key: str) -> None:
    if series_kind == "metric":
        if series_key not in METRIC_IDENTITIES:
            raise TemporalSeriesError("unsupported metric series_key")
        return
    if series_kind == "source-status":
        if series_key not in SOURCE_IDENTITIES:
            raise TemporalSeriesError("unsupported source-status series_key")
        return
    raise TemporalSeriesError("series_kind must be metric or source-status")


def _is_snapshot_path(value: str) -> bool:
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
    paths: list[str] = []
    for item in raw.split(b"\0"):
        if not item:
            continue
        try:
            path = item.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise TemporalSeriesError("immutable candidate set contains a non-UTF-8 path") from exc
        if _is_snapshot_path(path):
            paths.append(path)
    return sorted(paths)


def _candidate_identity(repository_root: Path, commit_sha: str, path: str) -> tuple[datetime, dict[str, Any]]:
    raw = _git(repository_root, "show", f"{commit_sha}:{path}")
    try:
        payload = json.loads(raw.decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TemporalSeriesError(f"candidate set is unorderable at {path}") from exc
    if not isinstance(payload, dict):
        raise TemporalSeriesError(f"candidate set is unorderable at {path}")
    run = payload.get("run")
    if not isinstance(run, dict):
        raise TemporalSeriesError(f"candidate set is unorderable at {path}")
    try:
        generated = parse_iso_timestamp(run.get("generated_at_utc"), "run.generated_at_utc")
    except ValidationError as exc:
        raise TemporalSeriesError(f"candidate set is unorderable at {path}") from exc
    schema = payload.get("schema_version")
    identity = {
        "path": path,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "schema_version": schema if isinstance(schema, str) and schema.strip() else None,
        "generated_at_utc": _canonical_utc(generated),
    }
    return generated, identity


def _candidate_index(repository_root: Path, commit_sha: str) -> dict[datetime, list[dict[str, Any]]]:
    index: dict[datetime, list[dict[str, Any]]] = {}
    for path in _candidate_paths(repository_root, commit_sha):
        generated, identity = _candidate_identity(repository_root, commit_sha, path)
        index.setdefault(generated, []).append(identity)
    for identities in index.values():
        identities.sort(key=lambda item: (item["path"], item["sha256"]))
    return index


def _metric_evidence(record: dict[str, Any], series_key: str) -> dict[str, Any]:
    target = METRIC_IDENTITIES[series_key]
    matches = [
        item
        for item in record.get("metric_comparisons", [])
        if isinstance(item, dict)
        and (item.get("family"), item.get("symbol"), item.get("field")) == target
    ]
    if len(matches) != 1:
        raise TemporalSeriesError("Phase 10 metric evidence identity mismatch")
    return copy.deepcopy(matches[0])


def _source_evidence(record: dict[str, Any], series_key: str) -> dict[str, Any]:
    matches = [
        item
        for item in record.get("source_availability_changes", [])
        if isinstance(item, dict) and item.get("source") == series_key
    ]
    if len(matches) != 1:
        raise TemporalSeriesError("Phase 10 source evidence identity mismatch")
    return copy.deepcopy(matches[0])


def _comparison_gap(record: dict[str, Any]) -> dict[str, Any]:
    status = record.get("comparison_status")
    reason = PHASE10_GAP_MAP.get(status)
    if reason is None:
        raise TemporalSeriesError(f"unsupported Phase 10 comparison_status: {status!r}")
    return {
        "reason": reason,
        "comparison_status": status,
        "comparison_id": record.get("comparison_id"),
        "current": copy.deepcopy(record.get("current")),
        "predecessor": copy.deepcopy(record.get("predecessor")),
    }


def _entry_for_unique_candidate(
    repository_root: Path,
    commit_sha: str,
    series_kind: str,
    series_key: str,
    slot: datetime,
    candidate: dict[str, Any],
) -> dict[str, Any]:
    record = build_comparison_record(repository_root, commit_sha, candidate["path"])
    status = record.get("comparison_status")
    slot_utc = _canonical_utc(slot)
    if status != "comparison-available":
        return {"slot_utc": slot_utc, "value": None, "gap": _comparison_gap(record)}

    if series_kind == "metric":
        evidence = _metric_evidence(record, series_key)
        state = evidence.get("comparison_state")
        if state != "comparable":
            reason = METRIC_GAP_MAP.get(state)
            if reason is None:
                raise TemporalSeriesError(f"unsupported Phase 10 metric state: {state!r}")
            return {
                "slot_utc": slot_utc,
                "value": None,
                "gap": {
                    "reason": reason,
                    "comparison_id": record["comparison_id"],
                    "current": copy.deepcopy(record["current"]),
                    "predecessor": copy.deepcopy(record["predecessor"]),
                    "metric_evidence": evidence,
                },
            }
        datum = copy.deepcopy(evidence["current"]["value"])
    else:
        evidence = _source_evidence(record, series_key)
        datum = evidence.get("current_status")
        if datum not in SOURCE_STATUSES:
            raise TemporalSeriesError(f"unsupported Phase 10 source status: {datum!r}")

    return {
        "slot_utc": slot_utc,
        "value": {
            "datum": datum,
            "comparison_id": record["comparison_id"],
            "current": copy.deepcopy(record["current"]),
            "predecessor": copy.deepcopy(record["predecessor"]),
            "evidence": evidence,
        },
        "gap": None,
    }


def build_temporal_series(
    repository_root: Path,
    commit_sha: str,
    series_kind: str,
    series_key: str,
    start_utc: str,
    end_utc: str,
) -> dict[str, Any]:
    """Build one canonical Phase 11 temporal-series record."""

    root = Path(repository_root).resolve()
    _series_identity(series_kind, series_key)
    start, end, slots = _window(start_utc, end_utc)
    context = _repository_context(root, commit_sha)
    candidates = _candidate_index(root, context["commit_sha"])

    entries: list[dict[str, Any]] = []
    for slot in slots:
        current = candidates.get(slot, [])
        if not current:
            entries.append(
                {
                    "slot_utc": _canonical_utc(slot),
                    "value": None,
                    "gap": {"reason": "current-missing", "current_candidates": []},
                }
            )
            continue
        if len(current) > 1:
            entries.append(
                {
                    "slot_utc": _canonical_utc(slot),
                    "value": None,
                    "gap": {
                        "reason": "current-ambiguous",
                        "current_candidates": copy.deepcopy(current),
                    },
                }
            )
            continue
        entries.append(
            _entry_for_unique_candidate(
                root,
                context["commit_sha"],
                series_kind,
                series_key,
                slot,
                current[0],
            )
        )

    record: dict[str, Any] = {
        "schema_version": SERIES_SCHEMA_VERSION,
        "series_kind": series_kind,
        "series_key": series_key,
        "window": {"start_utc": _canonical_utc(start), "end_utc": _canonical_utc(end)},
        "repository_context": context,
        "phase10": {
            "comparison_schema_version": PHASE10_COMPARISON_SCHEMA_VERSION,
            "predecessor_policy_version": PHASE10_PREDECESSOR_POLICY_VERSION,
            "semantic_contract_version": PHASE10_SEMANTIC_CONTRACT_VERSION,
        },
        "entries": entries,
        "series_id": "",
    }
    record["series_id"] = series_id_for_record(record)
    return record


def _validate_json_native(value: Any, path: str = "$") -> None:
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise TemporalSeriesError(f"{path} contains a non-finite number")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_json_native(item, f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise TemporalSeriesError(f"{path} contains a non-string key")
            _validate_json_native(item, f"{path}.{key}")
        return
    raise TemporalSeriesError(f"{path} contains a non-JSON-native value")


def _exact_object(value: Any, expected: set[str], path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TemporalSeriesError(f"{path} must be an object")
    if set(value) != expected:
        raise TemporalSeriesError(f"{path} keys do not match the frozen v1 contract")
    return value


def _shape_validate(record: Any) -> dict[str, Any]:
    _validate_json_native(record)
    top = _exact_object(record, TOP_LEVEL_KEYS, "$")
    if top["schema_version"] != SERIES_SCHEMA_VERSION:
        raise TemporalSeriesError("schema_version mismatch")
    _series_identity(top["series_kind"], top["series_key"])
    window = _exact_object(top["window"], WINDOW_KEYS, "window")
    _window(window["start_utc"], window["end_utc"])
    repository = _exact_object(top["repository_context"], REPOSITORY_KEYS, "repository_context")
    if not LOWER_HEX_40.fullmatch(str(repository["commit_sha"])):
        raise TemporalSeriesError("repository_context.commit_sha is invalid")
    if not LOWER_HEX_40.fullmatch(str(repository["tree_sha"])):
        raise TemporalSeriesError("repository_context.tree_sha is invalid")
    for name, expected_path, expected_blob in (
        ("validator", PHASE10_VALIDATOR_PATH, PHASE10_VALIDATOR_BLOB_SHA),
        ("config", PHASE10_CONFIG_PATH, PHASE10_CONFIG_BLOB_SHA),
    ):
        ref = _exact_object(repository[name], CONTRACT_REF_KEYS, f"repository_context.{name}")
        if ref != {"path": expected_path, "git_blob_sha": expected_blob}:
            raise TemporalSeriesError(f"repository_context.{name} does not match the frozen Phase 10 identity")
    phase10 = _exact_object(top["phase10"], PHASE10_KEYS, "phase10")
    if phase10 != {
        "comparison_schema_version": PHASE10_COMPARISON_SCHEMA_VERSION,
        "predecessor_policy_version": PHASE10_PREDECESSOR_POLICY_VERSION,
        "semantic_contract_version": PHASE10_SEMANTIC_CONTRACT_VERSION,
    }:
        raise TemporalSeriesError("Phase 10 contract version mismatch")
    entries = top["entries"]
    if not isinstance(entries, list):
        raise TemporalSeriesError("entries must be a list")
    _, _, expected_slots = _window(window["start_utc"], window["end_utc"])
    if len(entries) != len(expected_slots):
        raise TemporalSeriesError("entries must contain exactly one item per hourly slot")
    for index, (entry, slot) in enumerate(zip(entries, expected_slots)):
        item = _exact_object(entry, ENTRY_KEYS, f"entries[{index}]")
        if item["slot_utc"] != _canonical_utc(slot):
            raise TemporalSeriesError(f"entries[{index}].slot_utc mismatch")
        if (item["value"] is None) == (item["gap"] is None):
            raise TemporalSeriesError(f"entries[{index}] must contain exactly one of value or gap")
        if item["value"] is not None:
            _exact_object(item["value"], VALUE_KEYS, f"entries[{index}].value")
        else:
            gap = item["gap"]
            if not isinstance(gap, dict) or gap.get("reason") not in GAP_REASONS:
                raise TemporalSeriesError(f"entries[{index}].gap reason is invalid")
            if gap["reason"] in {"current-missing", "current-ambiguous"}:
                if set(gap) != {"reason", "current_candidates"}:
                    raise TemporalSeriesError(f"entries[{index}].gap keys mismatch")
                candidates = gap["current_candidates"]
                if not isinstance(candidates, list):
                    raise TemporalSeriesError(f"entries[{index}].current_candidates must be a list")
                for candidate_index, candidate in enumerate(candidates):
                    identity = _exact_object(
                        candidate,
                        CANDIDATE_KEYS,
                        f"entries[{index}].current_candidates[{candidate_index}]",
                    )
                    if not isinstance(identity["path"], str) or not _is_snapshot_path(identity["path"]):
                        raise TemporalSeriesError("ambiguous candidate path is invalid")
                    if not isinstance(identity["sha256"], str) or not LOWER_HEX_64.fullmatch(identity["sha256"]):
                        raise TemporalSeriesError("ambiguous candidate sha256 is invalid")
    if not isinstance(top["series_id"], str) or not LOWER_HEX_64.fullmatch(top["series_id"]):
        raise TemporalSeriesError("series_id must be lower-case SHA-256")
    if top["series_id"] != series_id_for_record(top):
        raise TemporalSeriesError("series_id mismatch")
    return top


def validate_temporal_series(repository_root: Path, record: Any) -> dict[str, Any]:
    """Replay immutable Phase 10 evidence and validate one Phase 11 series exactly."""

    supplied = _shape_validate(copy.deepcopy(record))
    context = supplied["repository_context"]
    expected = build_temporal_series(
        Path(repository_root),
        context["commit_sha"],
        supplied["series_kind"],
        supplied["series_key"],
        supplied["window"]["start_utc"],
        supplied["window"]["end_utc"],
    )
    if canonical_json_bytes(supplied) != canonical_json_bytes(expected):
        raise TemporalSeriesError("series does not match immutable Phase 10 replay")
    return record
