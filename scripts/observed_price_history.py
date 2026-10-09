"""Immutable, sparse, standalone observed USD prices; never pairwise movement."""
from __future__ import annotations

import hashlib
import json
import math
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from resolve_crypto_observation_hour_adjacency import (
    prepare_observation_hour_replay_context,
    _identity_is_consistent,
    _git_blob_sha,
)
from validate_crypto_observation_hour import validate_observation_hour
from validate_crypto_snapshot import ValidationError, validate_snapshot

CONTRACT = "observed-price-history/v2-terminal"
ASSETS = ("BTC", "ETH", "SOL")
STATES = {"OBSERVED", "OBSERVED_DEGRADED", "MISSING", "AMBIGUOUS", "INVALID"}


class ObservedPriceError(ValueError):
    """No trustworthy complete evidence can be produced."""


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def _identity(path, raw, payload):
    run = payload.get("run") if isinstance(payload, dict) else None
    run = run if isinstance(run, dict) else {}
    return {
        "path": path,
        "git_blob_sha": _git_blob_sha(raw),
        "snapshot_sha256": hashlib.sha256(raw).hexdigest(),
        "observation_hour_utc": run.get("observation_hour_utc") if isinstance(run.get("observation_hour_utc"), str) else None,
        "generated_at_utc": run.get("generated_at_utc") if isinstance(run.get("generated_at_utc"), str) else None,
        "quality_status": None,
    }


def _project(payload):
    assets = payload["market"]["assets"]
    found = {}
    ids = {"BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana"}
    for asset in assets:
        symbol = asset.get("symbol")
        if symbol in ASSETS:
            if symbol in found or asset.get("id") != ids[symbol]:
                raise ValueError("duplicated or mismatched asset")
            value = asset.get("price_usd")
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValueError("invalid asset USD price")
            found[symbol] = value
    if set(found) != set(ASSETS):
        raise ValueError("required asset absent")
    return {name: found[name] for name in ASSETS}


def _classify(items, slot, config):
    entry = {
        "slot_utc": slot,
        "state": "MISSING",
        "candidates": [],
        "warnings": [],
        "prices_usd": {name: None for name in ASSETS},
        "blocked_reason": None,
    }
    if not items:
        return entry
    entry["candidates"] = [_identity(p, raw, payload) for p, raw, payload in sorted(items)]
    if len(items) > 1:
        entry.update(state="AMBIGUOUS", blocked_reason="duplicate-hour")
        return entry
    path, raw, payload = items[0]
    if not _identity_is_consistent(path, payload):
        entry.update(state="INVALID", blocked_reason="identity-invalid")
        return entry
    # A validator rejection is recoverable, but I/O/runtime errors are NOT.
    try:
        with tempfile.TemporaryDirectory() as tmp:
            local = Path(tmp) / "source_snapshot.json"
            local.write_bytes(raw)
            observed = validate_observation_hour(local, config)
            quality = validate_snapshot(local, config)
    except ValidationError:
        entry.update(state="INVALID", blocked_reason="phase12-invalid")
        return entry
    if observed["observation_hour_utc"] != slot:
        entry.update(state="INVALID", blocked_reason="identity-invalid")
        return entry
    entry["candidates"][0]["quality_status"] = quality["status"]
    entry["warnings"] = list(quality["non_blocking_warnings"])
    try:
        prices = _project(payload)
    except (KeyError, TypeError, ValueError):
        entry.update(state="INVALID", blocked_reason="projection-invalid")
        return entry
    entry.update(
        state="OBSERVED_DEGRADED" if quality["status"] == "valid-degraded" else "OBSERVED",
        prices_usd=prices,
    )
    return entry


def materialise(repository_root: Path, commit_sha: str):
    try:
        ctx = prepare_observation_hour_replay_context(Path(repository_root), commit_sha)
        population = ctx._population
        if not population:
            raise ObservedPriceError("no observation population")
        # Enumeration and validator authority must be established before selecting an hour.
        latest = max(population)
        end = datetime.fromisoformat(latest.replace("Z", "+00:00"))
        start = end - timedelta(hours=23)
        slots = [(start + timedelta(hours=i)).strftime("%Y-%m-%dT%H:00:00Z") for i in range(24)]
        entries = [_classify(population.get(slot, []), slot, ctx._config) for slot in slots]
        refs = ctx.repository_context()
        result = {
            "contract": CONTRACT,
            "repository_context": {
                "commit_sha": ctx.commit_sha,
                "tree_sha": ctx.tree_sha,
                "validation_refs": {name: refs[name] for name in ("config", "snapshot_validator", "observation_validator")},
            },
            "window": {"start_utc": slots[0], "end_utc": slots[-1], "slots": 24},
            "assets": list(ASSETS),
            "entries": entries,
        }
        result["record_id"] = hashlib.sha256(canonical(result)).hexdigest()
        return result
    except ObservedPriceError:
        raise
    except Exception as exc:
        raise ObservedPriceError("trusted observation materialisation failed") from exc


def validate_replay(repository_root: Path, candidate):
    """Reconstruct independently from the original commit and reject every altered byte."""
    if not isinstance(candidate, dict):
        raise ObservedPriceError("candidate must be an object")
    context = candidate.get("repository_context")
    if not isinstance(context, dict) or not isinstance(context.get("commit_sha"), str):
        raise ObservedPriceError("candidate commit unavailable")
    expected = materialise(repository_root, context["commit_sha"])
    try:
        if canonical(expected) != canonical(candidate):
            raise ObservedPriceError("canonical source replay mismatch")
    except (TypeError, ValueError) as exc:
        raise ObservedPriceError("noncanonical candidate") from exc
    return expected
