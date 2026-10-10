"""Immutable, sparse, standalone observed USD prices; never pairwise movement."""
from __future__ import annotations

import hashlib
import json
import linecache
import math
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

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


class CandidateProjectionInvalid(ValueError):
    """One fully inspected candidate contains unusable required asset evidence."""


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
    # Phase 12 must have accepted the complete candidate. Only explicitly
    # identified source-data defects may be downgraded to an INVALID hour.
    market = payload.get("market") if isinstance(payload, dict) else None
    assets = market.get("assets") if isinstance(market, dict) else None
    if not isinstance(assets, list):
        raise CandidateProjectionInvalid("asset list absent")
    found = {}
    ids = {"BTC": "bitcoin", "ETH": "ethereum", "SOL": "solana"}
    for asset in assets:
        if not isinstance(asset, dict):
            raise CandidateProjectionInvalid("asset entry is not an object")
        symbol = asset.get("symbol")
        if symbol in ASSETS:
            if symbol in found or asset.get("id") != ids[symbol]:
                raise CandidateProjectionInvalid("duplicated or mismatched asset")
            value = asset.get("price_usd")
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise CandidateProjectionInvalid("invalid asset USD price")
            found[symbol] = value
    if set(found) != set(ASSETS):
        raise CandidateProjectionInvalid("required asset absent")
    return {name: found[name] for name in ASSETS}


def _explicit_phase12_source_rejection(error):
    """Require an actual validator source-rejection raise site, not just its type.

    These two pinned Phase 12 modules own explicit ValidationError rejections.
    Exceptions injected by wrappers or other code cannot impersonate them by
    choosing ValidationError or reusing its message.
    """
    tb = error.__traceback__
    if tb is None:
        return False
    while tb.tb_next is not None:
        tb = tb.tb_next
    frame = tb.tb_frame
    return (
        frame.f_globals.get("__name__") in
        ("validate_crypto_snapshot", "validate_crypto_observation_hour")
        and "raise ValidationError(" in
        linecache.getline(frame.f_code.co_filename, tb.tb_lineno)
    )


def _wrapped_execution_failure(error):
    """Fail closed unless all wrapped causes are recognised source-parse rejections."""
    pending = [(error, error.__cause__), (error, error.__context__)]
    seen = set()
    while pending:
        parent, current = pending.pop()
        if current is None or id(current) in seen:
            continue
        seen.add(id(current))
        # Phase 12 explicitly wraps JSON decoding and datetime parsing in
        # ValidationError. An unrelated KeyError/TypeError/OS/runtime failure
        # (including one nested beneath another ValidationError) is terminal.
        source_parse_error = (
            isinstance(current, (ValidationError, json.JSONDecodeError))
            or (
                type(current) is ValueError
                and isinstance(parent, ValidationError)
                and str(parent).endswith("must be an ISO-8601 timestamp")
            )
        )
        if isinstance(current, ValidationError) and not _explicit_phase12_source_rejection(current):
            return True
        if not source_parse_error:
            return True
        pending.extend(((current, current.__cause__), (current, current.__context__)))
    # Every ValidationError, chained or bare, must originate at a pinned
    # Phase 12 source-rejection statement; type and message alone are insufficient.
    return not _explicit_phase12_source_rejection(error)


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
    # The shared identity helper catches ZoneInfoNotFoundError and returns False.
    # Resolve this dependency explicitly first: an unavailable zone must abort,
    # not be misreported as a bad candidate. Do not modify Phase 13 semantics.
    run = payload.get("run") if isinstance(payload, dict) else None
    timezone_name = run.get("timezone") if isinstance(run, dict) else None
    if isinstance(timezone_name, str) and timezone_name.strip():
        ZoneInfo(timezone_name)
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
    except ValidationError as exc:
        if _wrapped_execution_failure(exc):
            raise
        entry.update(state="INVALID", blocked_reason="phase12-invalid")
        return entry
    if observed["observation_hour_utc"] != slot:
        entry.update(state="INVALID", blocked_reason="identity-invalid")
        return entry
    entry["candidates"][0]["quality_status"] = quality["status"]
    entry["warnings"] = list(quality["non_blocking_warnings"])
    try:
        prices = _project(payload)
    except CandidateProjectionInvalid:
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
