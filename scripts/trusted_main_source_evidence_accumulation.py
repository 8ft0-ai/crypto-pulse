#!/usr/bin/env python3
"""Deterministic Phase 17 Slice A source-evidence accumulation helpers."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, Sequence

from deterministic_site_publication import (
    CONTRACT as PUBLICATION_CONTRACT,
    EXPECTED_SOURCE_WORKFLOW_PATH,
    PublicationPolicyError,
    verify_publication_intent,
)
from resolve_crypto_observation_hour_adjacency import (
    ObservationHourPopulationError,
    load_observation_hour_population,
    resolve_observation_hour_adjacency,
)
from validate_crypto_observation_hour import canonical_observation_hour, validate_observation_hour
from validate_crypto_snapshot import ValidationError, load_config

CONTRACT = "trusted-main-source-evidence-accumulation/v1.1"
RECOVERY_CONTRACT = "trusted-main-source-evidence-recovery-decision/v1"
RECOVERY_DISPOSITION = "exclude-from-accumulation"
RECOVERY_PROHIBITIONS = (
    "do-not-promote-excluded-bytes",
    "do-not-elect-duplicate-winner",
    "do-not-reconstruct-or-backfill",
    "do-not-infer-missing-observation-hour",
)
EXPECTED_REPOSITORY = "8ft0-ai/crypto-pulse"
EXPECTED_WORKFLOW_PATH = EXPECTED_SOURCE_WORKFLOW_PATH
EXPECTED_EVENT = "schedule"
EXPECTED_CONCLUSION = "success"
ARTIFACT_PREFIX = "deterministic-publication-intent"
SNAPSHOT_PREFIX = PurePosixPath("data/crypto/hourly")
SNAPSHOT_SUFFIX = "_source_snapshot.json"
CONFIG_PATH = "config/crypto_sources.yml"
OWNER_LOGIN = "8ft0-ai"
WINDOW_HOURS = 25
SHA1_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class AccumulationError(ValueError):
    """Raised when immutable repository identity cannot be established."""


def canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _candidate_id(manifest: Mapping[str, Any]) -> str:
    identity = {
        key: value
        for key, value in manifest.items()
        if key not in {"candidate_id", "operational_diagnostics"}
    }
    return sha256_bytes(canonical_json_bytes(identity))


def git_blob_sha(raw: bytes) -> str:
    header = f"blob {len(raw)}\0".encode("ascii")
    return hashlib.sha1(header + raw).hexdigest()


def _git(repository_root: Path, *args: str, input_bytes: bytes | None = None) -> bytes:
    env = os.environ.copy()
    env.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_OPTIONAL_LOCKS": "0", "LC_ALL": "C"})
    completed = subprocess.run(
        ["git", "-C", str(repository_root), *args],
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        env=env,
    )
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise AccumulationError(detail or f"git {' '.join(args)} failed")
    return completed.stdout


def _git_text(repository_root: Path, *args: str) -> str:
    return _git(repository_root, *args).decode("utf-8", errors="strict").strip()


def _require_exact_commit(repository_root: Path, commit_sha: str) -> tuple[str, str]:
    if not isinstance(commit_sha, str) or SHA1_RE.fullmatch(commit_sha) is None:
        raise AccumulationError("exact_base_sha must be a 40-character lowercase Git SHA")
    resolved = _git_text(repository_root, "rev-parse", f"{commit_sha}^{{commit}}")
    if resolved != commit_sha:
        raise AccumulationError("exact_base_sha must resolve to itself exactly")
    tree = _git_text(repository_root, "rev-parse", f"{commit_sha}^{{tree}}")
    if SHA1_RE.fullmatch(tree) is None:
        raise AccumulationError("base tree identity is invalid")
    return resolved, tree


def _git_bytes_at(repository_root: Path, commit_sha: str, path: str) -> bytes | None:
    probe = subprocess.run(
        ["git", "-C", str(repository_root), "cat-file", "-e", f"{commit_sha}:{path}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
        env={**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_OPTIONAL_LOCKS": "0", "LC_ALL": "C"},
    )
    if probe.returncode != 0:
        return None
    return _git(repository_root, "show", f"{commit_sha}:{path}")


def _canonical_hour(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("observation hour must be a string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("observation hour must be timezone-aware")
    parsed = parsed.astimezone(timezone.utc)
    if parsed.minute or parsed.second or parsed.microsecond:
        raise ValueError("observation hour must identify the start of an hour")
    canonical = parsed.strftime("%Y-%m-%dT%H:00:00Z")
    if value != canonical:
        raise ValueError("observation hour must use canonical UTC Z notation")
    return canonical


def _hour_add(value: str, hours: int) -> str:
    parsed = datetime.fromisoformat(_canonical_hour(value).replace("Z", "+00:00"))
    return (parsed + timedelta(hours=hours)).strftime("%Y-%m-%dT%H:00:00Z")


def _safe_snapshot_path(value: Any) -> bool:
    text = str(value or "").replace("\\", "/")
    path = PurePosixPath(text)
    return bool(
        text
        and not text.startswith("/")
        and ".." not in path.parts
        and path.parts[:3] == SNAPSHOT_PREFIX.parts
        and text.endswith(SNAPSHOT_SUFFIX)
    )


def _int(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a positive integer")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a positive integer") from exc
    if result <= 0 or str(result) != str(value).strip():
        raise ValueError(f"{field} must be a positive integer")
    return result


def _bytes(value: Any, field: str) -> bytes:
    if not isinstance(value, (bytes, bytearray)):
        raise ValueError(f"{field} must be exact bytes")
    return bytes(value)


def _identity(input_record: Mapping[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    scalar_fields = (
        "repository",
        "workflow_path",
        "workflow_id",
        "event",
        "conclusion",
        "run_id",
        "run_attempt",
        "workflow_head_sha",
        "artifact_name",
    )
    for field in scalar_fields:
        if field in input_record:
            value = input_record[field]
            if isinstance(value, (str, int)) and not isinstance(value, bool):
                out[field] = value
            else:
                out[field] = str(value)
    for field in ("publication_intent_bytes", "snapshot_bytes"):
        value = input_record.get(field)
        if isinstance(value, (bytes, bytearray)):
            out[field.replace("_bytes", "_sha256")] = sha256_bytes(bytes(value))
    return out


def _input_sort_key(record: Mapping[str, Any]) -> tuple[Any, ...]:
    identity = _identity(record)
    return (
        str(identity.get("repository", "")),
        str(identity.get("workflow_path", "")),
        int(identity.get("run_id", 0)) if str(identity.get("run_id", "")).isdigit() else 0,
        int(identity.get("run_attempt", 0)) if str(identity.get("run_attempt", "")).isdigit() else 0,
        str(identity.get("artifact_name", "")),
        str(identity.get("publication_intent_sha256", "")),
        str(identity.get("snapshot_sha256", "")),
    )


def _blocker(
    blocker_class: str,
    input_identities: Sequence[Mapping[str, Any]],
    canonical_hour: str | None,
    **details: Any,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "blocker_class": blocker_class,
        "canonical_observation_hour_utc": canonical_hour,
        "input_identities": [dict(item) for item in input_identities],
    }
    body.update(details)
    body["input_identities"].sort(key=canonical_json_bytes)
    fingerprint_body = dict(body)
    body["blocker_fingerprint"] = sha256_bytes(canonical_json_bytes(fingerprint_body))
    return body


def _diagnostic(kind: str, identity: Mapping[str, Any], **details: Any) -> dict[str, Any]:
    result = {"kind": kind, "input_identity": dict(identity)}
    result.update(details)
    return result


def _load_base_config(repository_root: Path, base_sha: str) -> dict[str, Any]:
    raw = _git_bytes_at(repository_root, base_sha, CONFIG_PATH)
    if raw is None:
        raise AccumulationError(f"trusted base is missing {CONFIG_PATH}")
    with tempfile.TemporaryDirectory(prefix="phase17-config-") as temporary:
        path = Path(temporary) / "crypto_sources.yml"
        path.write_bytes(raw)
        return load_config(path)


def _resolve_anchor(repository_root: Path, base_sha: str) -> str | None:
    try:
        population = load_observation_hour_population(repository_root, base_sha)
    except ObservationHourPopulationError:
        return None
    slots: list[str] = []
    for value in population:
        try:
            slots.append(_canonical_hour(value))
        except (TypeError, ValueError):
            continue
    for slot in sorted(set(slots), reverse=True):
        result = resolve_observation_hour_adjacency(repository_root, base_sha, slot)
        current = result.get("current")
        if not isinstance(current, dict):
            continue
        if current.get("observation_hour_utc") != slot:
            continue
        quality_status = current.get("quality_status")
        if not isinstance(quality_status, str) or not quality_status:
            continue
        return slot
    return None


def _verify_source(
    repository_root: Path,
    base_sha: str,
    config: dict[str, Any],
    source: Mapping[str, Any],
) -> dict[str, Any]:
    repository = str(source.get("repository", ""))
    workflow_path = str(source.get("workflow_path", ""))
    event = str(source.get("event", ""))
    conclusion = str(source.get("conclusion", ""))
    workflow_id = _int(source.get("workflow_id"), "workflow_id")
    run_id = _int(source.get("run_id"), "run_id")
    run_attempt = _int(source.get("run_attempt"), "run_attempt")
    workflow_head_sha = str(source.get("workflow_head_sha", ""))
    artifact_name = str(source.get("artifact_name", ""))
    intent_bytes = _bytes(source.get("publication_intent_bytes"), "publication_intent_bytes")
    snapshot_bytes = _bytes(source.get("snapshot_bytes"), "snapshot_bytes")

    if repository != EXPECTED_REPOSITORY:
        raise ValueError("repository mismatch")
    if workflow_path != EXPECTED_WORKFLOW_PATH:
        raise ValueError("workflow mismatch")
    if event != EXPECTED_EVENT:
        raise ValueError("event mismatch")
    if conclusion != EXPECTED_CONCLUSION:
        raise ValueError("conclusion mismatch")
    if SHA1_RE.fullmatch(workflow_head_sha) is None:
        raise ValueError("workflow_head_sha is invalid")
    expected_artifact = f"{ARTIFACT_PREFIX}-{run_id}-{run_attempt}"
    if artifact_name != expected_artifact:
        raise ValueError("artifact name does not match run identity")

    try:
        intent = json.loads(intent_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("publication intent is not valid UTF-8 JSON") from exc
    if not isinstance(intent, dict):
        raise ValueError("publication intent root must be an object")
    if intent.get("publication_contract") != PUBLICATION_CONTRACT:
        raise ValueError("publication intent contract mismatch")
    try:
        verify_publication_intent(
            intent,
            snapshot_bytes,
            expected_source_workflow_id=workflow_id,
            expected_source_run_id=run_id,
            expected_source_run_attempt=run_attempt,
        )
    except PublicationPolicyError as exc:
        raise ValueError(str(exc)) from exc
    if intent.get("source_workflow_head_sha") != workflow_head_sha:
        raise ValueError("workflow head SHA does not match publication intent")

    snapshot_commit_sha = str(intent.get("snapshot_commit_sha", ""))
    snapshot_path = str(intent.get("snapshot_path", ""))
    if SHA1_RE.fullmatch(snapshot_commit_sha) is None:
        raise ValueError("snapshot_commit_sha is invalid")
    if not _safe_snapshot_path(snapshot_path):
        raise ValueError("snapshot path is outside trusted hourly scope")
    committed_bytes = _git_bytes_at(repository_root, snapshot_commit_sha, snapshot_path)
    if committed_bytes is None:
        raise ValueError("snapshot_commit_sha:path is unavailable locally")
    if committed_bytes != snapshot_bytes:
        raise ValueError("snapshot_commit_sha:path bytes do not match artifact snapshot bytes")

    with tempfile.TemporaryDirectory(prefix="phase17-snapshot-") as temporary:
        path = Path(temporary) / "source_snapshot.json"
        path.write_bytes(snapshot_bytes)
        try:
            validation = validate_observation_hour(path, config)
        except (ValidationError, OSError, ValueError) as exc:
            raise ValueError("snapshot fails current-base Phase 12 validation") from exc

    try:
        snapshot = json.loads(snapshot_bytes.decode("utf-8"))
        run = snapshot["run"]
        hour = canonical_observation_hour(run["generated_at_utc"])
    except (KeyError, TypeError, UnicodeDecodeError, json.JSONDecodeError, ValidationError) as exc:
        raise ValueError("canonical hour cannot be derived from validated run.generated_at_utc") from exc
    if validation.get("observation_hour_utc") != hour:
        raise ValueError("validated observation hour disagrees with generated_at_utc")

    return {
        "input_identity": _identity(source),
        "workflow_id": workflow_id,
        "run_id": run_id,
        "run_attempt": run_attempt,
        "workflow_head_sha": workflow_head_sha,
        "artifact_name": artifact_name,
        "publication_intent_sha256": sha256_bytes(intent_bytes),
        "snapshot_sha256": sha256_bytes(snapshot_bytes),
        "snapshot_git_blob_sha": git_blob_sha(snapshot_bytes),
        "snapshot_commit_sha": snapshot_commit_sha,
        "snapshot_path": snapshot_path,
        "canonical_observation_hour_utc": hour,
        "quality_status": validation.get("quality_status"),
        "snapshot_bytes": snapshot_bytes,
    }


def _source_public(record: Mapping[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in record.items() if key != "snapshot_bytes"}


def _parse_recovery_body(body: str) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    try:
        payload = json.loads(body)
        if isinstance(payload, dict):
            candidates.append(payload)
    except json.JSONDecodeError:
        pass
    for match in re.finditer(r"```(?:json)?\s*\n(.*?)\n```", body, flags=re.IGNORECASE | re.DOTALL):
        try:
            payload = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            candidates.append(payload)
    if len(candidates) != 1:
        raise ValueError("recovery comment must contain exactly one machine-readable object")
    return candidates[0]


def _recovery_sort_key(carrier: Mapping[str, Any]) -> tuple[str, str, str, str]:
    raw = carrier.get("body_bytes")
    body_sha = sha256_bytes(bytes(raw)) if isinstance(raw, (bytes, bytearray)) else ""
    return (
        str(carrier.get("issue_number", "")),
        str(carrier.get("comment_id", "")),
        str(carrier.get("author_login", "")),
        body_sha,
    )


def _apply_recoveries(
    blockers: Sequence[Mapping[str, Any]],
    recovery_comment_inputs: Sequence[Mapping[str, Any]],
    allowed_recovery_issue_numbers: set[int],
) -> tuple[set[str], list[dict[str, Any]], list[dict[str, Any]]]:
    by_fingerprint = {str(item["blocker_fingerprint"]): dict(item) for item in blockers}
    recovered: set[str] = set()
    applied: list[dict[str, Any]] = []
    recovery_blockers: list[dict[str, Any]] = []

    for carrier in sorted(recovery_comment_inputs, key=_recovery_sort_key):
        raw_body = carrier.get("body_bytes")
        body_sha = sha256_bytes(bytes(raw_body)) if isinstance(raw_body, (bytes, bytearray)) else None
        carrier_identity = {
            "issue_number": carrier.get("issue_number"),
            "comment_id": carrier.get("comment_id"),
            "author_login": carrier.get("author_login"),
            "body_sha256": body_sha,
        }
        try:
            issue_number = _int(carrier.get("issue_number"), "issue_number")
            comment_id = _int(carrier.get("comment_id"), "comment_id")
            author = str(carrier.get("author_login", ""))
            exact_body = _bytes(raw_body, "body_bytes")
            try:
                body = exact_body.decode("utf-8", errors="strict")
            except UnicodeDecodeError as exc:
                raise ValueError("recovery comment body must be exact UTF-8 bytes") from exc
            assert body_sha is not None
            if issue_number not in allowed_recovery_issue_numbers:
                raise ValueError("recovery carrier issue is not allowed")
            if author != OWNER_LOGIN:
                raise ValueError("recovery carrier author is not the repository owner")
            record = _parse_recovery_body(body)
            if record.get("contract") != RECOVERY_CONTRACT:
                raise ValueError("recovery decision contract mismatch")
            if record.get("repository") != EXPECTED_REPOSITORY:
                raise ValueError("recovery decision repository mismatch")
            if record.get("disposition") != RECOVERY_DISPOSITION:
                raise ValueError("recovery decision disposition mismatch")
            prohibitions = record.get("prohibitions")
            if (
                not isinstance(prohibitions, list)
                or any(not isinstance(value, str) for value in prohibitions)
                or len(prohibitions) != len(RECOVERY_PROHIBITIONS)
                or set(prohibitions) != set(RECOVERY_PROHIBITIONS)
            ):
                raise ValueError("recovery decision prohibitions do not match the exact v1.1 set")
            blocker_class = str(record.get("blocker_class", ""))
            fingerprint = str(record.get("blocker_fingerprint", ""))
            if SHA256_RE.fullmatch(fingerprint) is None:
                raise ValueError("recovery blocker_fingerprint is invalid")
            reason = str(record.get("reason", "")).strip()
            if not reason:
                raise ValueError("recovery reason is required")
            target = by_fingerprint.get(fingerprint)
            if target is None:
                raise ValueError("recovery decision is stale or does not match a current blocker")
            if blocker_class != target.get("blocker_class"):
                raise ValueError("recovery blocker_class does not match current blocker")
            canonical_hour = record.get("canonical_observation_hour_utc")
            if canonical_hour != target.get("canonical_observation_hour_utc"):
                raise ValueError("recovery canonical hour does not match current blocker")
            input_identities = record.get("input_identities")
            if not isinstance(input_identities, list):
                raise ValueError("recovery input_identities must be a list")
            expected_identities = target.get("input_identities")
            if canonical_json_bytes(input_identities) != canonical_json_bytes(expected_identities):
                raise ValueError("recovery input identities do not match current blocker")
            if fingerprint in recovered:
                raise ValueError("multiple recovery decisions target the same blocker")
            recovered.add(fingerprint)
            applied.append(
                {
                    "contract": RECOVERY_CONTRACT,
                    "repository": EXPECTED_REPOSITORY,
                    "disposition": RECOVERY_DISPOSITION,
                    "prohibitions": list(RECOVERY_PROHIBITIONS),
                    "blocker_class": blocker_class,
                    "blocker_fingerprint": fingerprint,
                    "canonical_observation_hour_utc": canonical_hour,
                    "input_identities": input_identities,
                    "reason": reason,
                    "carrier": {
                        "issue_number": issue_number,
                        "comment_id": comment_id,
                        "author_login": author,
                        "body_sha256": body_sha,
                    },
                }
            )
        except (TypeError, ValueError) as exc:
            recovery_blockers.append(
                _blocker(
                    "recovery-decision-invalid",
                    [],
                    None,
                    carrier=carrier_identity,
                    reason=str(exc),
                )
            )
    return recovered, applied, recovery_blockers


def build_accumulation_manifest(
    repository_root: Path,
    exact_base_sha: str,
    source_inputs: Sequence[Mapping[str, Any]],
    recovery_comment_inputs: Sequence[Mapping[str, Any]] = (),
    allowed_recovery_issue_numbers: Iterable[int] = (),
) -> dict[str, Any]:
    """Build one deterministic Phase 17 Slice A accumulation manifest."""
    repository_root = Path(repository_root)
    base_sha, base_tree_sha = _require_exact_commit(repository_root, exact_base_sha)
    config = _load_base_config(repository_root, base_sha)
    anchor = _resolve_anchor(repository_root, base_sha)

    if anchor is None:
        finding = _blocker("anchor-unavailable", [], None, reason="no Phase 13 validated current candidate")
        manifest: dict[str, Any] = {
            "contract": CONTRACT,
            "repository": EXPECTED_REPOSITORY,
            "base_sha": base_sha,
            "base_tree_sha": base_tree_sha,
            "anchor_observation_hour_utc": None,
            "window": None,
            "hours": [],
            "verified_source_inputs": [],
            "supersession_records": [],
            "operational_diagnostics": [],
            "input_level_blockers": [finding],
            "hour_level_blockers": [],
            "applied_recovery_decisions": [],
            "blocking_findings": [finding],
            "added_paths": [],
        }
        manifest["candidate_id"] = _candidate_id(manifest)
        return manifest

    window = [_hour_add(anchor, offset) for offset in range(1, WINDOW_HOURS + 1)]
    window_set = set(window)
    diagnostics: list[dict[str, Any]] = []
    supersession: list[dict[str, Any]] = []
    input_blockers: list[dict[str, Any]] = []

    scheduled_success: dict[int, list[Mapping[str, Any]]] = {}
    for source in sorted(source_inputs, key=_input_sort_key):
        identity = _identity(source)
        if source.get("event") != EXPECTED_EVENT:
            diagnostics.append(_diagnostic("non-schedule-input", identity))
            continue
        if source.get("conclusion") != EXPECTED_CONCLUSION:
            diagnostics.append(_diagnostic("non-success-input", identity))
            continue
        try:
            run_id = _int(source.get("run_id"), "run_id")
            _int(source.get("run_attempt"), "run_attempt")
        except ValueError as exc:
            input_blockers.append(_blocker("source-input-identity-invalid", [identity], None, reason=str(exc)))
            continue
        scheduled_success.setdefault(run_id, []).append(source)

    winners: list[Mapping[str, Any]] = []
    for run_id in sorted(scheduled_success):
        rows = scheduled_success[run_id]
        by_attempt: dict[int, list[Mapping[str, Any]]] = {}
        for row in rows:
            attempt = _int(row.get("run_attempt"), "run_attempt")
            by_attempt.setdefault(attempt, []).append(row)
        highest = max(by_attempt)
        for attempt in sorted(by_attempt):
            if attempt < highest:
                for row in by_attempt[attempt]:
                    supersession.append(
                        {
                            "run_id": run_id,
                            "superseded_run_attempt": attempt,
                            "selected_run_attempt": highest,
                            "input_identity": _identity(row),
                        }
                    )
        highest_rows = by_attempt[highest]
        if len(highest_rows) > 1:
            raw_identities = [_identity(row) for row in highest_rows]
            exact_payloads = {
                canonical_json_bytes(
                    {
                        **_identity(row),
                        "publication_intent_sha256": sha256_bytes(_bytes(row.get("publication_intent_bytes"), "publication_intent_bytes"))
                        if isinstance(row.get("publication_intent_bytes"), (bytes, bytearray))
                        else None,
                        "snapshot_sha256": sha256_bytes(_bytes(row.get("snapshot_bytes"), "snapshot_bytes"))
                        if isinstance(row.get("snapshot_bytes"), (bytes, bytearray))
                        else None,
                    }
                )
                for row in highest_rows
            }
            if len(exact_payloads) == 1:
                diagnostics.append(_diagnostic("duplicate-carrier-collapsed", raw_identities[0], count=len(highest_rows)))
                winners.append(highest_rows[0])
            else:
                input_blockers.append(
                    _blocker(
                        "duplicate-run-attempt",
                        raw_identities,
                        None,
                        run_id=run_id,
                        run_attempt=highest,
                    )
                )
            continue
        winners.append(highest_rows[0])

    verified: list[dict[str, Any]] = []
    for source in sorted(winners, key=_input_sort_key):
        identity = _identity(source)
        try:
            candidate = _verify_source(repository_root, base_sha, config, source)
        except (AccumulationError, TypeError, ValueError) as exc:
            input_blockers.append(
                _blocker("source-input-unverifiable", [identity], None, reason=str(exc))
            )
            continue
        if candidate["canonical_observation_hour_utc"] not in window_set:
            diagnostics.append(
                _diagnostic(
                    "verified-input-outside-window",
                    candidate["input_identity"],
                    canonical_observation_hour_utc=candidate["canonical_observation_hour_utc"],
                )
            )
            continue
        verified.append(candidate)

    by_hour: dict[str, list[dict[str, Any]]] = {hour: [] for hour in window}
    for candidate in verified:
        hour = candidate["canonical_observation_hour_utc"]
        if hour in by_hour:
            by_hour[hour].append(candidate)

    hours: list[dict[str, Any]] = []
    hour_blockers: list[dict[str, Any]] = []
    eligible_by_path: dict[str, dict[str, Any]] = {}

    for hour in window:
        candidates = sorted(
            by_hour[hour],
            key=lambda item: (
                item["run_id"],
                item["run_attempt"],
                item["snapshot_sha256"],
                item["snapshot_path"],
            ),
        )
        public_candidates = [_source_public(item) for item in candidates]
        record: dict[str, Any] = {
            "canonical_observation_hour_utc": hour,
            "disposition": "no-promotable-observation",
            "source_candidates": public_candidates,
        }
        if len(candidates) > 1:
            blocker = _blocker(
                "duplicate-observation-hour",
                [item["input_identity"] for item in candidates],
                hour,
                candidate_paths=[item["snapshot_path"] for item in candidates],
                candidate_sha256s=[item["snapshot_sha256"] for item in candidates],
            )
            hour_blockers.append(blocker)
            record["disposition"] = "duplicate"
            record["blocker_fingerprint"] = blocker["blocker_fingerprint"]
        elif len(candidates) == 1:
            candidate = candidates[0]
            trusted = _git_bytes_at(repository_root, base_sha, candidate["snapshot_path"])
            if trusted is None:
                record["disposition"] = "eligible"
                record["eligible_source"] = _source_public(candidate)
                eligible_by_path[candidate["snapshot_path"]] = candidate
            elif trusted == candidate["snapshot_bytes"]:
                record["disposition"] = "already-trusted"
                record["trusted_path"] = candidate["snapshot_path"]
                record["trusted_sha256"] = sha256_bytes(trusted)
            else:
                blocker = _blocker(
                    "trusted-path-conflict",
                    [candidate["input_identity"]],
                    hour,
                    staged_snapshot_identity={
                        "path": candidate["snapshot_path"],
                        "sha256": candidate["snapshot_sha256"],
                        "git_blob_sha": candidate["snapshot_git_blob_sha"],
                        "snapshot_commit_sha": candidate["snapshot_commit_sha"],
                    },
                    trusted_main_identity={
                        "base_sha": base_sha,
                        "base_tree_sha": base_tree_sha,
                        "path": candidate["snapshot_path"],
                        "sha256": sha256_bytes(trusted),
                        "git_blob_sha": git_blob_sha(trusted),
                    },
                )
                hour_blockers.append(blocker)
                record["disposition"] = "path-conflict"
                record["blocker_fingerprint"] = blocker["blocker_fingerprint"]
        hours.append(record)

    original_blockers = sorted(
        [*input_blockers, *hour_blockers],
        key=lambda item: (str(item.get("canonical_observation_hour_utc") or ""), item["blocker_class"], item["blocker_fingerprint"]),
    )
    recovered, applied, recovery_blockers = _apply_recoveries(
        original_blockers,
        recovery_comment_inputs,
        {int(value) for value in allowed_recovery_issue_numbers},
    )

    for record in hours:
        fingerprint = record.get("blocker_fingerprint")
        if fingerprint in recovered:
            record["disposition"] = "terminal-excluded"
            record["recovered_blocker_fingerprint"] = fingerprint
            record.pop("blocker_fingerprint", None)

    unrecovered = [item for item in original_blockers if item["blocker_fingerprint"] not in recovered]
    blocking_findings = sorted(
        [*unrecovered, *recovery_blockers],
        key=lambda item: (str(item.get("canonical_observation_hour_utc") or ""), item["blocker_class"], item["blocker_fingerprint"]),
    )

    added_paths: list[dict[str, Any]] = []
    if not blocking_findings:
        for record in hours:
            if record["disposition"] != "eligible":
                continue
            candidate = eligible_by_path[record["eligible_source"]["snapshot_path"]]
            added_paths.append(
                {
                    "path": candidate["snapshot_path"],
                    "sha256": candidate["snapshot_sha256"],
                    "git_blob_sha": candidate["snapshot_git_blob_sha"],
                    "canonical_observation_hour_utc": candidate["canonical_observation_hour_utc"],
                    "source_run_id": candidate["run_id"],
                    "source_run_attempt": candidate["run_attempt"],
                }
            )
        added_paths.sort(key=lambda item: item["path"])

    manifest = {
        "contract": CONTRACT,
        "repository": EXPECTED_REPOSITORY,
        "base_sha": base_sha,
        "base_tree_sha": base_tree_sha,
        "anchor_observation_hour_utc": anchor,
        "window": {"start_utc": window[0], "end_utc": window[-1], "hours": WINDOW_HOURS},
        "hours": hours,
        "verified_source_inputs": sorted(
            [_source_public(item) for item in verified],
            key=lambda item: (item["canonical_observation_hour_utc"], item["run_id"], item["run_attempt"]),
        ),
        "supersession_records": sorted(
            supersession,
            key=lambda item: (item["run_id"], item["superseded_run_attempt"], canonical_json_bytes(item["input_identity"])),
        ),
        "operational_diagnostics": sorted(diagnostics, key=canonical_json_bytes),
        "input_level_blockers": sorted(input_blockers, key=lambda item: item["blocker_fingerprint"]),
        "hour_level_blockers": sorted(hour_blockers, key=lambda item: item["blocker_fingerprint"]),
        "applied_recovery_decisions": sorted(applied, key=lambda item: item["blocker_fingerprint"]),
        "blocking_findings": blocking_findings,
        "added_paths": added_paths,
    }
    manifest["candidate_id"] = _candidate_id(manifest)
    return manifest


def decode_source_input(record: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(record)
    for field in ("publication_intent", "snapshot"):
        key = f"{field}_base64"
        target = f"{field}_bytes"
        if key in result:
            try:
                result[target] = base64.b64decode(str(result.pop(key)), validate=True)
            except (ValueError, base64.binascii.Error) as exc:
                raise AccumulationError(f"{key} is not valid base64") from exc
    return result


def decode_recovery_input(record: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(record)
    if "body_base64" in result:
        try:
            result["body_bytes"] = base64.b64decode(str(result.pop("body_base64")), validate=True)
        except (ValueError, base64.binascii.Error) as exc:
            raise AccumulationError("body_base64 is not valid base64") from exc
    return result


def _load_input_file(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise AccumulationError(f"cannot read input JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise AccumulationError("input JSON root must be an object")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Phase 17 trusted-main source-evidence accumulation manifest.")
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--base-sha", required=True)
    parser.add_argument("--input-json", required=True)
    parser.add_argument("--output")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        payload = _load_input_file(Path(args.input_json))
        sources_raw = payload.get("source_inputs", [])
        recoveries = payload.get("recovery_comment_inputs", [])
        allowed = payload.get("allowed_recovery_issue_numbers", [])
        if not isinstance(sources_raw, list) or not isinstance(recoveries, list) or not isinstance(allowed, list):
            raise AccumulationError("input arrays are malformed")
        manifest = build_accumulation_manifest(
            Path(args.repository_root),
            args.base_sha,
            [decode_source_input(item) for item in sources_raw if isinstance(item, dict)],
            [decode_recovery_input(item) for item in recoveries if isinstance(item, dict)],
            [int(item) for item in allowed],
        )
        raw = canonical_json_bytes(manifest) + b"\n"
        if args.output:
            Path(args.output).write_bytes(raw)
        else:
            sys.stdout.buffer.write(raw)
        return 0 if not manifest["blocking_findings"] else 2
    except (AccumulationError, OSError, TypeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())