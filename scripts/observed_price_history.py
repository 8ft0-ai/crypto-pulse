"""Immutable, sparse, standalone observed USD prices; never pairwise movement."""
from __future__ import annotations

import hashlib
import json
import inspect
import ast
import sys
import math
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from zoneinfo import ZoneInfo

from resolve_crypto_observation_hour_adjacency import (
    prepare_observation_hour_replay_context,
    _identity_is_consistent,
    _git_blob_sha,
)
from validate_crypto_observation_hour import validate_observation_hour
from validate_crypto_snapshot import ValidationError, validate_snapshot
import validate_crypto_snapshot as _snapshot_module
import validate_crypto_observation_hour as _observation_module
import resolve_crypto_observation_hour_adjacency as _adjacency_module
import json.decoder as _json_decoder_module

# These are process-local import baselines; the frozen Git blobs remain the
# source authority. Guard mutable call targets and parser bindings as well.
_IMPORTED_VALIDATORS = {
    "validate_crypto_snapshot": _snapshot_module,
    "validate_crypto_observation_hour": _observation_module,
}
_IMPORTED_JSON_LOADS = json.loads
_IMPORTED_JSON_DECODE_ERROR = json.JSONDecodeError
_IMPORTED_JSON_LOADS_CODE = json.loads.__code__
_IMPORTED_DEFAULT_DECODER = json._default_decoder
_IMPORTED_DECODER_TYPE = type(_IMPORTED_DEFAULT_DECODER)
# Immutable snapshots, not aliases to mutable decoder attributes.
_IMPORTED_DECODER_ATTRS = tuple(vars(_IMPORTED_DEFAULT_DECODER).items())
_IMPORTED_DECODER_METHODS = {
    name: (getattr(_IMPORTED_DECODER_TYPE, name),
           getattr(_IMPORTED_DECODER_TYPE, name).__code__)
    for name in ("__init__", "decode", "raw_decode")
}
_IMPORTED_DECODER_CONSTANTS = tuple(sorted(
    (key, repr(value)) for key, value in _json_decoder_module._CONSTANTS.items()
))
_IMPORTED_ADJACENCY = _adjacency_module
_IMPORTED_IDENTITY = _identity_is_consistent
_IMPORTED_ADJACENCY_ZONEINFO = _adjacency_module.ZoneInfo
_IMPORTED_GIT_RUN = _adjacency_module.subprocess.run
_IMPORTED_GIT_RUN_CODE = _IMPORTED_GIT_RUN.__code__
_IMPORTED_REPLAY_CONTEXT_TYPE = _adjacency_module.ObservationHourReplayContext
_IMPORTED_REPLAY_CONTEXT_INIT = _IMPORTED_REPLAY_CONTEXT_TYPE.__init__
_IMPORTED_REPLAY_CONTEXT_INIT_CODE = _IMPORTED_REPLAY_CONTEXT_INIT.__code__
_IMPORTED_REPLAY_CONTEXT_REFS = _IMPORTED_REPLAY_CONTEXT_TYPE.repository_context
_IMPORTED_REPLAY_CONTEXT_REFS_CODE = _IMPORTED_REPLAY_CONTEXT_REFS.__code__
_PINNED_ADJACENCY_BLOB = "d7ca33806c1d2cdbf113c40d0b158efdabfe4ca9"

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


# Frozen Phase 12 explicit rejection sites (module, function, source line).
# Every site was independently enumerated from the exact frozen validator blobs.
# Do not derive this allowlist dynamically from runtime source or linecache.
_PINNED_REJECTION_SITES = {
    "validate_crypto_snapshot": {
        "require_mapping": {36}, "require_list": {40}, "require_string": {44},
        "parse_iso_timestamp": {52}, "validate_source_status": {108},
        "validate_market_shape": {116}, "validate_exchange_shape": {127, 129, 132},
        "validate_defi_shape": {136}, "validate_quality": {229, 230, 232},
        "validate_snapshot": {237, 239, 242, 246},
    },
    "validate_crypto_observation_hour": {
        "validate_observation_hour": {42, 46, 50, 52, 58},
    },
}
_PINNED_VALIDATOR_BLOBS = {
    "validate_crypto_snapshot": "b8c7fcc850bf0f5076f7d084bb6be9c24a9b7d3a",
    "validate_crypto_observation_hour": "21e18835c1047243ebda4b5ec7760fd9df793356",
}


def _authenticate_json_decoder():
    """Reject changes to the JSON decoder actually invoked by json.loads.

    A preserved json.loads function is insufficient: it delegates to the
    mutable json._default_decoder and its scanner/methods by default.
    """
    decoder = json._default_decoder
    if (json.loads is not _IMPORTED_JSON_LOADS
            or json.loads.__code__ != _IMPORTED_JSON_LOADS_CODE
            or decoder is not _IMPORTED_DEFAULT_DECODER
            or type(decoder) is not _IMPORTED_DECODER_TYPE):
        raise ObservedPriceError("JSON decoder authority changed")
    actual = vars(decoder)
    if actual.keys() != {key for key, _ in _IMPORTED_DECODER_ATTRS}:
        raise ObservedPriceError("JSON decoder attributes changed")
    for key, original in _IMPORTED_DECODER_ATTRS:
        current = actual[key]
        if key == "memo":
            if current is not original or current != {}:
                raise ObservedPriceError("JSON decoder memo changed")
        elif current is not original:
            raise ObservedPriceError("JSON decoder parse binding changed")
    for name, (method, code) in _IMPORTED_DECODER_METHODS.items():
        current = getattr(_IMPORTED_DECODER_TYPE, name, None)
        if current is not method or current.__code__ != code:
            raise ObservedPriceError("JSON decoder implementation changed")
    if tuple(sorted((key, repr(value)) for key, value
                    in _json_decoder_module._CONSTANTS.items())) != _IMPORTED_DECODER_CONSTANTS:
        raise ObservedPriceError("JSON decoder constants changed")


def _authenticate_adjacency_identity(snapshot):
    """Validate frozen Phase 13 identity parsing without editing Phase 13."""
    module = sys.modules.get("resolve_crypto_observation_hour_adjacency")
    source = Path(__file__).resolve().with_name("resolve_crypto_observation_hour_adjacency.py")
    if (module is not _IMPORTED_ADJACENCY
            or Path(getattr(module, "__file__", "")).resolve() != source):
        raise ObservedPriceError("Phase 13 identity module changed")
    try:
        raw = source.read_bytes()
    except OSError as exc:
        raise ObservedPriceError("Phase 13 identity source unavailable") from exc
    if _git_blob_sha(raw) != _PINNED_ADJACENCY_BLOB:
        raise ObservedPriceError("Phase 13 identity source changed")
    compiled = compile(raw, str(source), "exec")
    # Every source-defined Phase 13 helper is part of the inherited replay
    # graph. Attesting only the entry point missed mutable enumeration and
    # committed-byte readers that can forge apparently valid replay records.
    parsed = ast.parse(raw)
    needed = {
        node.name for node in parsed.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    for node in parsed.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        try:
            literal = ast.literal_eval(node.value)
        except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
            continue
        actual = getattr(module, target.id, None)
        if type(actual) is not type(literal) or actual != literal:
            raise ObservedPriceError("Phase 13 population policy constant changed")
    expected = {code.co_name: code for code in compiled.co_consts
                if inspect.iscode(code) and code.co_name in needed}
    if set(expected) != needed:
        raise ObservedPriceError("Phase 13 identity inventory changed")
    for name, code in expected.items():
        function = getattr(module, name, None)
        if (not inspect.isfunction(function)
                or function.__globals__ is not module.__dict__
                or function.__closure__ is not None
                or function.__code__ != code):
            raise ObservedPriceError("Phase 13 identity execution changed")
    bindings = (
        (prepare_observation_hour_replay_context, module.prepare_observation_hour_replay_context),
        (_git_blob_sha, module._git_blob_sha),
        (_identity_is_consistent, _IMPORTED_IDENTITY),
        (_identity_is_consistent, module._identity_is_consistent),
        (module.parse_iso_timestamp, snapshot.parse_iso_timestamp),
        (module.load_config, snapshot.load_config),
        (module.ValidationError, snapshot.ValidationError),
        (module.ZoneInfo, _IMPORTED_ADJACENCY_ZONEINFO),
        (module.json, json),
        (module.datetime, datetime),
        (module.timezone, timezone),
        (module.PurePosixPath, PurePosixPath),
        (module.Path, Path),
    )
    if any(actual is not expected for actual, expected in bindings):
        raise ObservedPriceError("Phase 13 identity parser binding changed")
    context_type = module.ObservationHourReplayContext
    if (context_type is not _IMPORTED_REPLAY_CONTEXT_TYPE
            or context_type.__init__ is not _IMPORTED_REPLAY_CONTEXT_INIT
            or context_type.__init__.__code__ != _IMPORTED_REPLAY_CONTEXT_INIT_CODE
            or context_type.repository_context is not _IMPORTED_REPLAY_CONTEXT_REFS
            or context_type.repository_context.__code__ != _IMPORTED_REPLAY_CONTEXT_REFS_CODE):
        raise ObservedPriceError("Phase 13 replay context implementation changed")
    if (module.subprocess.run is not _IMPORTED_GIT_RUN
            or module.subprocess.run.__code__ != _IMPORTED_GIT_RUN_CODE):
        raise ObservedPriceError("Phase 13 Git invocation changed")
    if (module.SNAPSHOT_PREFIX != PurePosixPath("data/crypto/hourly")
            or module.SNAPSHOT_SUFFIX != "_source_snapshot.json"):
        raise ObservedPriceError("Phase 13 identity path policy changed")


def _source_identity_is_consistent(path, payload):
    """Independent source-rejection witness for the frozen boolean helper.

    Distinguish genuine malformed source/path from an unexplained False
    returned after the inherited helper swallows a parser execution error.
    """
    if not isinstance(path, str) or not _adjacency_module._is_snapshot_path(path):
        return False
    if not isinstance(payload, dict) or not isinstance(payload.get("run"), dict):
        return False
    run = payload["run"]
    utc_text = run.get("generated_at_utc")
    if not isinstance(utc_text, str) or not utc_text.strip():
        return False
    try:
        utc = _snapshot_module.parse_iso_timestamp(utc_text, "run.generated_at_utc")
    except ValidationError as exc:
        if _wrapped_execution_failure(exc):
            raise
        return False
    try:
        local = _adjacency_module._parse_local_timestamp(run.get("generated_at_local"))
    except ValueError:
        return False
    timezone_name = run.get("timezone")
    if not isinstance(timezone_name, str) or not timezone_name.strip():
        return False
    # An unavailable timezone database is an execution failure, not bad data.
    zone = ZoneInfo(timezone_name)
    expected_local = utc.astimezone(zone)
    if local.astimezone(timezone.utc) != utc:
        return False
    if local.replace(tzinfo=None) != expected_local.replace(tzinfo=None):
        return False
    if local.utcoffset() != expected_local.utcoffset():
        return False
    abbreviation = run.get("timezone_abbreviation")
    if abbreviation is not None and abbreviation != expected_local.tzname():
        return False
    name = expected_local.tzname() or "LOCAL"
    safe_name = "".join(ch for ch in name if ch.isalnum()) or "LOCAL"
    expected = (PurePosixPath("data/crypto/hourly")
                / f"{expected_local.year:04d}"
                / f"{expected_local.month:02d}"
                / f"{expected_local.day:02d}"
                / f"{expected_local.hour:02d}{expected_local.minute:02d}_{safe_name}_source_snapshot.json")
    return PurePosixPath(path) == expected


def _authenticated_validator_modules(validation_refs=None):
    """Authenticate on-disk validators and their runtime function code origins."""
    _authenticate_json_decoder()
    result = {}
    for name, expected_blob in _PINNED_VALIDATOR_BLOBS.items():
        module = sys.modules.get(name)
        source = Path(__file__).resolve().with_name(name + ".py")
        if (module is not _IMPORTED_VALIDATORS[name]
                or Path(getattr(module, "__file__", "")).resolve() != source):
            raise ObservedPriceError("pinned validator module identity mismatch")
        try:
            actual = _git_blob_sha(source.read_bytes())
        except OSError as exc:
            raise ObservedPriceError("pinned validator source unavailable") from exc
        if actual != expected_blob:
            raise ObservedPriceError("pinned validator source differs from authorised blob")
        # Compare the running validator functions with freshly compiled pinned
        # source, rather than trusting filenames, linecache or monkeypatched names.
        compiled = compile(source.read_bytes(), str(source), "exec")
        # Only module-level function definitions qualify; class bodies also
        # compile into code objects (notably ValidationError) but are not
        # function call targets and must not be mistaken for them.
        parsed = ast.parse(source.read_bytes())
        function_names = {
            node.name for node in parsed.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        # Code and import checks alone cannot protect mutable validator policy
        # constants. Derive their literal values from the same pinned source.
        for node in parsed.body:
            if not isinstance(node, ast.Assign) or len(node.targets) != 1:
                continue
            target = node.targets[0]
            if not isinstance(target, ast.Name):
                continue
            try:
                literal = ast.literal_eval(node.value)
            except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
                continue
            actual_literal = getattr(module, target.id, None)
            if type(actual_literal) is not type(literal) or actual_literal != literal:
                raise ObservedPriceError("loaded validator policy constant differs from pinned source")
        expected_functions = {
            obj.co_name: obj for obj in compiled.co_consts
            if inspect.iscode(obj) and obj.co_name in function_names
        }
        if set(expected_functions) != function_names:
            raise ObservedPriceError("pinned validator function inventory mismatch")
        # Authenticate the complete source-defined function surface: authentic
        # entry-point code could otherwise call a replaced nested helper.
        for function_name, expected_code in expected_functions.items():
            function = getattr(module, function_name, None)
            if (not inspect.isfunction(function)
                    or function.__globals__ is not module.__dict__
                    or function.__closure__ is not None
                    or function.__code__ != expected_code):
                raise ObservedPriceError("loaded validator function differs from pinned source")
        if not _PINNED_REJECTION_SITES[name].keys() <= expected_functions.keys():
            raise ObservedPriceError("pinned rejection function missing")
        if validation_refs is not None:
            ref_name = "snapshot_validator" if name == "validate_crypto_snapshot" else "observation_validator"
            if validation_refs.get(ref_name, {}).get("git_blob_sha") != expected_blob:
                raise ObservedPriceError("replay validator authority differs from pinned source")
        result[name] = (module, source)

    # Loaded source blobs and function code do not authenticate the globals
    # those functions resolve at call time. Check the actual top-level targets,
    # cross-module imports and the mutable JSON parser binding before use.
    snapshot = result["validate_crypto_snapshot"][0]
    observation = result["validate_crypto_observation_hour"][0]
    required_bindings = (
        (validate_snapshot, snapshot.validate_snapshot),
        (validate_observation_hour, observation.validate_observation_hour),
        (ValidationError, snapshot.ValidationError),
        (observation.ValidationError, snapshot.ValidationError),
        (observation.validate_snapshot, snapshot.validate_snapshot),
        (observation.parse_iso_timestamp, snapshot.parse_iso_timestamp),
        (snapshot.json, json),
        (observation.json, json),
        (snapshot.math, math),
        (snapshot.datetime, datetime),
        (snapshot.timezone, timezone),
        (observation.timezone, timezone),
        (snapshot.Path, Path),
        (observation.Path, Path),
        (json.loads, _IMPORTED_JSON_LOADS),
        (json.JSONDecodeError, _IMPORTED_JSON_DECODE_ERROR),
    )
    if any(actual is not expected for actual, expected in required_bindings):
        raise ObservedPriceError("validator call target or import binding differs from pinned authority")
    if observation.OBSERVATION_HOUR_RE.pattern != r"^\d{4}-\d{2}-\d{2}T\d{2}:00:00Z$":
        raise ObservedPriceError("canonical observation-hour parser changed")
    _authenticate_adjacency_identity(snapshot)
    return result


def _explicit_phase12_source_rejection(error):
    """Allow only an authentic validator function's explicitly pinned raise site."""
    modules = _authenticated_validator_modules()
    tb = error.__traceback__
    if tb is None:
        return False
    while tb.tb_next is not None:
        tb = tb.tb_next
    frame = tb.tb_frame
    name = frame.f_globals.get("__name__")
    if name not in _PINNED_REJECTION_SITES:
        return False
    module, source = modules[name]
    if Path(frame.f_code.co_filename).resolve() != source:
        return False
    function = getattr(module, frame.f_code.co_name, None)
    if not inspect.isfunction(function) or function.__code__ is not frame.f_code:
        return False
    return tb.tb_lineno in _PINNED_REJECTION_SITES[name].get(function.__name__, ())


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
    # Also protect direct _classify callers, not only materialise().
    _authenticated_validator_modules()
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
    witness = _source_identity_is_consistent(path, payload)
    if _identity_is_consistent(path, payload) != witness:
        raise ObservedPriceError("unproven inherited identity rejection")
    if not witness:
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


def _record_from_context(ctx):
    """Assemble a record from a prepared, authenticated replay context."""
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


def materialise(repository_root: Path, commit_sha: str):
    try:
        # Authenticate before Phase 13 population loading/JSON decoding begins.
        _authenticated_validator_modules()
        ctx = prepare_observation_hour_replay_context(Path(repository_root), commit_sha)
        _authenticated_validator_modules(ctx.repository_context())
        return _record_from_context(ctx)
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
