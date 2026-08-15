#!/usr/bin/env python3
"""Build the Phase 10 Slice 2 comparison-record envelope and semantic gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any

from resolve_crypto_snapshot_predecessor import resolve_predecessor
from validate_crypto_snapshot_comparison import (
    COMPARISON_SCHEMA_VERSION,
    CONFIG_BLOB_SHA,
    CONFIG_PATH,
    PREDECESSOR_POLICY_VERSION,
    SEMANTIC_CONTRACT_VERSION,
    VALIDATOR_BLOB_SHA,
    VALIDATOR_PATH,
    comparison_id_for_record,
    validate_comparison_record,
)

SNAPSHOT_PREFIX = PurePosixPath("data/crypto/hourly")
SNAPSHOT_SUFFIX = "_source_snapshot.json"
EXPECTED_PRODUCER = "scripts/ingest_crypto_sources.py"
EXPECTED_CADENCE = "hourly"
EXPECTED_SCHEMA = "0.2"
SUPPORTED_ASSET_ORDER = ("BTC", "ETH", "SOL")
SUPPORTED_STABLECOIN_ORDER = ("USDT", "USDC")
SUPPORTED_SOURCE_ORDER = (
    "coingecko",
    "defillama",
    "coinbase_exchange",
    "kraken",
    "okx",
    "binance",
    "bybit",
    "cryptocompare",
)
GIT_SHA1 = re.compile(r"^[0-9a-fA-F]{40}$")


def _empty_input() -> dict[str, Any]:
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
        "validator": {"path": VALIDATOR_PATH, "git_blob_sha": None},
        "config": {"path": CONFIG_PATH, "git_blob_sha": None},
    }


def _base_record() -> dict[str, Any]:
    return {
        "comparison_schema_version": COMPARISON_SCHEMA_VERSION,
        "predecessor_policy_version": PREDECESSOR_POLICY_VERSION,
        "semantic_contract_version": SEMANTIC_CONTRACT_VERSION,
        "repository_context": _empty_repository_context(),
        "current": _empty_input(),
        "predecessor": None,
        "elapsed_seconds": None,
        "comparison_status": "validation-contract-mismatch",
        "metric_comparisons": [],
        "source_availability_changes": [],
        "comparison_id": "",
    }


def _finalize(record: dict[str, Any]) -> dict[str, Any]:
    record["comparison_id"] = comparison_id_for_record(record)
    validate_comparison_record(record)
    return record


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
        raise RuntimeError(detail or f"git {' '.join(args)} failed")
    return completed.stdout


def _git_text(repository_root: Path, *args: str) -> str:
    return _git(repository_root, *args).decode("utf-8", errors="strict").strip()


def _git_object_id(repository_root: Path, spec: str) -> str | None:
    try:
        value = _git_text(repository_root, "rev-parse", "--verify", spec)
    except (RuntimeError, UnicodeDecodeError):
        return None
    return value.lower() if GIT_SHA1.fullmatch(value) else None


def _resolve_repository_context(repository_root: Path, commit_sha: str) -> dict[str, Any]:
    context = _empty_repository_context()
    if not isinstance(commit_sha, str) or not GIT_SHA1.fullmatch(commit_sha.strip()):
        return context

    supplied = commit_sha.strip().lower()
    resolved = _git_object_id(repository_root, f"{supplied}^{{commit}}")
    if resolved is None or resolved != supplied:
        return context

    context["commit_sha"] = resolved
    context["tree_sha"] = _git_object_id(repository_root, f"{resolved}^{{tree}}")
    context["validator"]["git_blob_sha"] = _git_object_id(
        repository_root, f"{resolved}:{VALIDATOR_PATH}"
    )
    context["config"]["git_blob_sha"] = _git_object_id(
        repository_root, f"{resolved}:{CONFIG_PATH}"
    )
    return context


def _context_matches_frozen_contract(context: dict[str, Any]) -> bool:
    return bool(
        context["commit_sha"]
        and context["tree_sha"]
        and context["validator"]["git_blob_sha"] == VALIDATOR_BLOB_SHA
        and context["config"]["git_blob_sha"] == CONFIG_BLOB_SHA
    )


def _is_snapshot_repository_path(value: str) -> bool:
    if not isinstance(value, str) or not value or "\\" in value:
        return False
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts:
        return False
    return (
        len(path.parts) >= 5
        and path.parts[:3] == SNAPSHOT_PREFIX.parts
        and path.name.endswith(SNAPSHOT_SUFFIX)
    )


def _snapshot_paths_at_commit(repository_root: Path, commit_sha: str) -> list[str]:
    raw = _git(
        repository_root,
        "ls-tree",
        "-r",
        "-z",
        "--name-only",
        commit_sha,
        "--",
        str(SNAPSHOT_PREFIX),
    )
    paths = []
    for item in raw.split(b"\0"):
        if not item:
            continue
        path = item.decode("utf-8", errors="strict")
        if _is_snapshot_repository_path(path):
            paths.append(path)
    return sorted(paths)


def _bytes_at_commit(repository_root: Path, commit_sha: str, repository_path: str) -> bytes:
    return _git(repository_root, "show", f"{commit_sha}:{repository_path}")


def _parse_snapshot(raw: bytes) -> dict[str, Any] | None:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _normalised_symbols(rows: Any) -> tuple[list[str], bool]:
    if not isinstance(rows, list):
        return [], False
    symbols: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            return [], False
        symbol = row.get("symbol")
        if not isinstance(symbol, str) or not symbol.strip():
            return [], False
        symbols.append(symbol.strip().upper())
    return symbols, len(symbols) == len(set(symbols))


def _semantic_compatible(snapshot: dict[str, Any]) -> bool:
    if snapshot.get("schema_version") != EXPECTED_SCHEMA:
        return False
    run = snapshot.get("run")
    if not isinstance(run, dict):
        return False
    if run.get("cadence") != EXPECTED_CADENCE or run.get("producer") != EXPECTED_PRODUCER:
        return False

    market = snapshot.get("market")
    defi = snapshot.get("defi")
    sources = snapshot.get("sources")
    if not isinstance(market, dict) or not isinstance(defi, dict) or not isinstance(sources, dict):
        return False

    asset_symbols, assets_unique = _normalised_symbols(market.get("assets"))
    stablecoin_symbols, stablecoins_unique = _normalised_symbols(defi.get("stablecoins"))
    if not assets_unique or not stablecoins_unique:
        return False
    if not set(SUPPORTED_ASSET_ORDER).issubset(asset_symbols):
        return False
    if not set(SUPPORTED_STABLECOIN_ORDER).issubset(stablecoin_symbols):
        return False
    if any(not isinstance(key, str) or key not in SUPPORTED_SOURCE_ORDER for key in sources):
        return False
    return True


def build_comparison_record(
    repository_root: Path,
    commit_sha: str,
    current_repository_path: str,
) -> dict[str, Any]:
    """Build one deterministic, read-only Slice 2 comparison record."""

    repository_root = Path(repository_root).resolve()
    record = _base_record()
    context = _resolve_repository_context(repository_root, commit_sha)
    record["repository_context"] = context

    if not _context_matches_frozen_contract(context):
        return _finalize(record)

    exact_commit = context["commit_sha"]
    assert isinstance(exact_commit, str)

    if not _is_snapshot_repository_path(current_repository_path):
        record["comparison_status"] = "current-identity-invalid"
        return _finalize(record)

    try:
        snapshot_paths = _snapshot_paths_at_commit(repository_root, exact_commit)
    except (RuntimeError, UnicodeDecodeError):
        return _finalize(record)

    if current_repository_path not in snapshot_paths:
        record["current"]["path"] = current_repository_path
        record["comparison_status"] = "current-identity-invalid"
        return _finalize(record)

    try:
        snapshot_bytes = {
            path: _bytes_at_commit(repository_root, exact_commit, path)
            for path in snapshot_paths
        }
    except (RuntimeError, UnicodeDecodeError, OSError):
        return _finalize(record)

    current_raw = snapshot_bytes[current_repository_path]
    current_snapshot = _parse_snapshot(current_raw)
    if current_snapshot is None:
        record["current"]["path"] = current_repository_path
        record["comparison_status"] = "current-identity-invalid"
        return _finalize(record)

    run = current_snapshot.get("run")
    current_identity = {
        "path": current_repository_path,
        "sha256": hashlib.sha256(current_raw).hexdigest(),
        "schema_version": current_snapshot.get("schema_version"),
        "generated_at_utc": run.get("generated_at_utc") if isinstance(run, dict) else None,
    }
    resolution = resolve_predecessor(current_identity, repository_root, context)

    record["current"] = resolution["current"]
    record["predecessor"] = resolution["predecessor"]
    record["elapsed_seconds"] = resolution["elapsed_seconds"]

    resolution_status = resolution["resolution_status"]
    if resolution_status != "predecessor-resolved":
        record["comparison_status"] = resolution_status
        return _finalize(record)

    predecessor = resolution["predecessor"]
    predecessor_path = predecessor.get("path") if isinstance(predecessor, dict) else None
    if not isinstance(predecessor_path, str) or predecessor_path not in snapshot_bytes:
        record["comparison_status"] = "pair-semantics-incompatible"
        return _finalize(record)

    predecessor_snapshot = _parse_snapshot(snapshot_bytes[predecessor_path])
    if predecessor_snapshot is None:
        record["comparison_status"] = "pair-semantics-incompatible"
        return _finalize(record)

    if _semantic_compatible(current_snapshot) and _semantic_compatible(predecessor_snapshot):
        record["comparison_status"] = "comparison-ready"
    else:
        record["comparison_status"] = "pair-semantics-incompatible"
    return _finalize(record)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a Phase 10 Slice 2 comparison record.")
    parser.add_argument("repository_root", help="Local Git repository root")
    parser.add_argument("commit_sha", help="Exact 40-character commit SHA")
    parser.add_argument("current_repository_path", help="Repository-relative current snapshot path")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    record = build_comparison_record(
        Path(args.repository_root), args.commit_sha, args.current_repository_path
    )
    print(json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())