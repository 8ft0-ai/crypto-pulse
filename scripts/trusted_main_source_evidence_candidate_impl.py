#!/usr/bin/env python3
"""Deterministic Phase 17 Slice B source-candidate helpers.

This module is deliberately credential-free. GitHub API collection and remote
mutation belong to the workflow; this helper validates captured metadata,
constructs/replays the Slice A inputs, packs immutable prepared evidence, and
verifies local candidate/PR identities.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping, Sequence

import trusted_main_source_evidence_accumulation as accumulation

EXPECTED_REPOSITORY = accumulation.EXPECTED_REPOSITORY
EXPECTED_WORKFLOW_PATH = accumulation.EXPECTED_WORKFLOW_PATH
EXPECTED_OWNER = accumulation.OWNER_LOGIN
EXPECTED_EVENT = "schedule"
EXPECTED_SUCCESS = "success"
EXPECTED_BRANCH = "automation/source-evidence-accumulation"
ALLOWED_RECOVERY_ISSUES = (523,)
CLOSURE_CONTRACT = "phase17-slice-b-source-population-closure/v1"
EVIDENCE_CONTRACT = "phase17-slice-b-candidate-evidence/v1"
BUNDLE_HASH_CONTRACT = "phase17-slice-b-bundle-sha256/v1"
SHA1_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
ARTIFACT_RE = re.compile(r"^deterministic-publication-intent-(\d+)-(\d+)$")
SOURCE_PREFIX = PurePosixPath("data/crypto/hourly")


class CandidateError(ValueError):
    """Raised when Slice B evidence cannot be proved exactly."""


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _read_json(path: Path) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CandidateError(f"cannot read JSON {path}: {exc}") from exc


def _write_json(path: Path, payload: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(payload) + b"\n")


def _positive_int(value: Any, field: str) -> int:
    if isinstance(value, bool):
        raise CandidateError(f"{field} must be a positive integer")
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise CandidateError(f"{field} must be a positive integer") from exc
    if result <= 0 or str(result) != str(value).strip():
        raise CandidateError(f"{field} must be a positive integer")
    return result


def _sha1(value: Any, field: str) -> str:
    text = str(value or "")
    if SHA1_RE.fullmatch(text) is None:
        raise CandidateError(f"{field} must be a 40-character lowercase SHA")
    return text


def _sha256(value: Any, field: str) -> str:
    text = str(value or "")
    if SHA256_RE.fullmatch(text) is None:
        raise CandidateError(f"{field} must be a lowercase SHA-256")
    return text


def _utc(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise CandidateError(f"{field} must be an ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CandidateError(f"{field} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise CandidateError(f"{field} must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _utc_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def census_bounds(window: Mapping[str, Any]) -> dict[str, str]:
    start = _utc(window.get("start_utc"), "window.start_utc")
    end = _utc(window.get("end_utc"), "window.end_utc")
    if end < start:
        raise CandidateError("window end precedes start")
    return {
        "start_utc": _utc_text(start - timedelta(days=31)),
        "end_utc": _utc_text(end + timedelta(hours=1)),
    }


def derive_window(repository_root: Path, base_sha: str) -> dict[str, Any]:
    base_sha = _sha1(base_sha, "base_sha")
    manifest = accumulation.build_accumulation_manifest(Path(repository_root), base_sha, [])
    if manifest.get("anchor_observation_hour_utc") is None or not isinstance(manifest.get("window"), dict):
        raise CandidateError("protected-main anchor is unavailable")
    window = dict(manifest["window"])
    return {
        "base_sha": base_sha,
        "base_tree_sha": manifest["base_tree_sha"],
        "anchor_observation_hour_utc": manifest["anchor_observation_hour_utc"],
        "window": window,
        "census": census_bounds(window),
    }


def _artifact_public(artifact: Mapping[str, Any]) -> dict[str, Any]:
    run = artifact.get("workflow_run") if isinstance(artifact.get("workflow_run"), dict) else {}
    return {
        "id": _positive_int(artifact.get("id"), "artifact.id"),
        "name": str(artifact.get("name", "")),
        "expired": bool(artifact.get("expired", False)),
        "size_in_bytes": int(artifact.get("size_in_bytes", 0) or 0),
        "digest": artifact.get("digest") if isinstance(artifact.get("digest"), str) else None,
        "created_at": artifact.get("created_at") if isinstance(artifact.get("created_at"), str) else None,
        "updated_at": artifact.get("updated_at") if isinstance(artifact.get("updated_at"), str) else None,
        "expires_at": artifact.get("expires_at") if isinstance(artifact.get("expires_at"), str) else None,
        "workflow_run": {
            "id": int(run.get("id", 0) or 0),
            "head_sha": run.get("head_sha") if isinstance(run.get("head_sha"), str) else None,
        },
    }


def _attempt_public(attempt: Mapping[str, Any], run_id: int, attempt_number: int) -> dict[str, Any]:
    if _positive_int(attempt.get("id"), "attempt.id") != run_id:
        raise CandidateError("attempt run id does not match parent run")
    if _positive_int(attempt.get("run_attempt"), "attempt.run_attempt") != attempt_number:
        raise CandidateError("attempt number does not match contiguous population")
    event = str(attempt.get("event", ""))
    workflow_id = _positive_int(attempt.get("workflow_id"), "attempt.workflow_id")
    head_sha = _sha1(attempt.get("head_sha"), "attempt.head_sha")
    return {
        "run_id": run_id,
        "run_attempt": attempt_number,
        "workflow_id": workflow_id,
        "event": event,
        "status": str(attempt.get("status", "")),
        "conclusion": attempt.get("conclusion") if isinstance(attempt.get("conclusion"), str) else None,
        "head_sha": head_sha,
        "head_branch": attempt.get("head_branch") if isinstance(attempt.get("head_branch"), str) else None,
        "created_at": attempt.get("created_at") if isinstance(attempt.get("created_at"), str) else None,
        "run_started_at": attempt.get("run_started_at") if isinstance(attempt.get("run_started_at"), str) else None,
        "updated_at": attempt.get("updated_at") if isinstance(attempt.get("updated_at"), str) else None,
    }


def _resolve_artifact(artifacts: Sequence[Mapping[str, Any]], run_id: int, attempt_number: int) -> dict[str, Any]:
    expected_name = f"deterministic-publication-intent-{run_id}-{attempt_number}"
    exact = [_artifact_public(item) for item in artifacts if str(item.get("name", "")) == expected_name]
    exact.sort(key=lambda item: (item["id"], canonical_json_bytes(item)))
    if len(exact) > 1:
        raise CandidateError(f"ambiguous exact artifact carrier for run {run_id} attempt {attempt_number}")
    if not exact:
        return {"expected_name": expected_name, "availability": "unavailable", "artifact": None}
    artifact = exact[0]
    if artifact["workflow_run"]["id"] not in {0, run_id}:
        raise CandidateError("artifact workflow_run id does not match run")
    return {
        "expected_name": expected_name,
        "availability": "unavailable" if artifact["expired"] else "retained",
        "artifact": artifact,
    }


def build_source_population_closure(capture: Mapping[str, Any]) -> dict[str, Any]:
    if capture.get("repository") != EXPECTED_REPOSITORY:
        raise CandidateError("capture repository mismatch")
    if capture.get("workflow_path") != EXPECTED_WORKFLOW_PATH:
        raise CandidateError("capture workflow path mismatch")
    expected_main_sha = _sha1(capture.get("expected_main_sha"), "capture.expected_main_sha")
    census = capture.get("census")
    if not isinstance(census, dict):
        raise CandidateError("capture census is missing")
    census_public = {
        "start_utc": _utc_text(_utc(census.get("start_utc"), "census.start_utc")),
        "end_utc": _utc_text(_utc(census.get("end_utc"), "census.end_utc")),
    }
    if _utc(census_public["end_utc"], "census.end_utc") < _utc(census_public["start_utc"], "census.start_utc"):
        raise CandidateError("census end precedes start")

    extension_raw = capture.get("retained_artifact_extension_run_ids", [])
    if not isinstance(extension_raw, list):
        raise CandidateError("retained artifact extension run ids must be a list")
    extension_ids = sorted({_positive_int(value, "retained artifact extension run id") for value in extension_raw})

    runs = capture.get("runs")
    if not isinstance(runs, list):
        raise CandidateError("capture runs must be a list")
    seen: set[int] = set()
    closed_runs: list[dict[str, Any]] = []
    for raw_run in runs:
        if not isinstance(raw_run, dict):
            raise CandidateError("capture run must be an object")
        run_id = _positive_int(raw_run.get("run_id"), "run.run_id")
        if run_id in seen:
            raise CandidateError("duplicate run id in capture")
        seen.add(run_id)
        latest_attempt = _positive_int(raw_run.get("latest_run_attempt"), "run.latest_run_attempt")
        attempts_raw = raw_run.get("attempts")
        artifacts_raw = raw_run.get("artifacts")
        if not isinstance(attempts_raw, list) or not isinstance(artifacts_raw, list):
            raise CandidateError("run attempts/artifacts must be lists")
        by_attempt: dict[int, Mapping[str, Any]] = {}
        for raw_attempt in attempts_raw:
            if not isinstance(raw_attempt, dict):
                raise CandidateError("attempt must be an object")
            number = _positive_int(raw_attempt.get("run_attempt"), "attempt.run_attempt")
            if number in by_attempt:
                raise CandidateError("duplicate attempt in capture")
            by_attempt[number] = raw_attempt
        expected_numbers = list(range(1, latest_attempt + 1))
        if sorted(by_attempt) != expected_numbers:
            raise CandidateError(f"run {run_id} attempt enumeration is incomplete")
        artifacts = [item for item in artifacts_raw if isinstance(item, dict)]
        closed_attempts: list[dict[str, Any]] = []
        for number in expected_numbers:
            attempt = _attempt_public(by_attempt[number], run_id, number)
            artifact = _resolve_artifact(artifacts, run_id, number) if attempt["conclusion"] == EXPECTED_SUCCESS else {
                "expected_name": f"deterministic-publication-intent-{run_id}-{number}",
                "availability": "not-required",
                "artifact": None,
            }
            closed_attempts.append({**attempt, "artifact": artifact})
        closed_runs.append(
            {
                "run_id": run_id,
                "latest_run_attempt": latest_attempt,
                "discovery_sources": sorted(str(value) for value in raw_run.get("discovery_sources", []) if str(value)),
                "attempts": closed_attempts,
            }
        )
    closed_runs.sort(key=lambda item: item["run_id"])
    discovered = [item["run_id"] for item in closed_runs]
    if any(run_id not in seen for run_id in extension_ids):
        raise CandidateError("retained artifact extension run is missing from captured runs")

    closure: dict[str, Any] = {
        "contract": CLOSURE_CONTRACT,
        "repository": EXPECTED_REPOSITORY,
        "workflow_path": EXPECTED_WORKFLOW_PATH,
        "expected_main_sha": expected_main_sha,
        "census": census_public,
        "discovered_run_ids": discovered,
        "retained_artifact_extension_run_ids": extension_ids,
        "runs": closed_runs,
    }
    closure["sha256"] = sha256_bytes(canonical_json_bytes(closure))
    return closure


def _artifact_files(artifact_root: Path, run_id: int, attempt: int) -> tuple[Path, Path]:
    base = Path(artifact_root) / str(run_id) / str(attempt)
    return base / "deterministic-publication-intent.json", base / "payload" / "snapshot.json"


def source_inputs_from_capture(capture: Mapping[str, Any], artifact_root: Path) -> list[dict[str, Any]]:
    closure = build_source_population_closure(capture)
    inputs: list[dict[str, Any]] = []
    for run in closure["runs"]:
        for attempt in run["attempts"]:
            source: dict[str, Any] = {
                "repository": EXPECTED_REPOSITORY,
                "workflow_path": EXPECTED_WORKFLOW_PATH,
                "workflow_id": attempt["workflow_id"],
                "event": attempt["event"],
                "conclusion": attempt["conclusion"],
                "run_id": attempt["run_id"],
                "run_attempt": attempt["run_attempt"],
                "workflow_head_sha": attempt["head_sha"],
                "artifact_name": attempt["artifact"]["expected_name"],
            }
            if attempt["conclusion"] == EXPECTED_SUCCESS and attempt["artifact"]["availability"] == "retained":
                intent, snapshot = _artifact_files(artifact_root, attempt["run_id"], attempt["run_attempt"])
                if intent.is_file() and snapshot.is_file():
                    source["publication_intent_bytes"] = intent.read_bytes()
                    source["snapshot_bytes"] = snapshot.read_bytes()
                else:
                    source["publication_intent_bytes"] = None
                    source["snapshot_bytes"] = None
            elif attempt["conclusion"] == EXPECTED_SUCCESS:
                source["publication_intent_bytes"] = None
                source["snapshot_bytes"] = None
            inputs.append(source)
    return inputs


def decode_recovery_capture(payload: Any) -> list[dict[str, Any]]:
    if payload is None:
        payload = []
    if not isinstance(payload, list):
        raise CandidateError("recovery capture must be a list")
    seen: set[int] = set()
    out: list[dict[str, Any]] = []
    for row in payload:
        if not isinstance(row, dict):
            raise CandidateError("recovery carrier must be an object")
        issue = _positive_int(row.get("issue_number"), "recovery.issue_number")
        comment_id = _positive_int(row.get("comment_id"), "recovery.comment_id")
        if comment_id in seen:
            raise CandidateError("duplicate recovery comment id")
        seen.add(comment_id)
        author = str(row.get("author_login", ""))
        body64 = row.get("body_base64")
        if not isinstance(body64, str):
            raise CandidateError("recovery body_base64 is required")
        try:
            body = base64.b64decode(body64, validate=True)
            body.decode("utf-8", errors="strict")
        except (ValueError, UnicodeDecodeError, binascii.Error) as exc:
            raise CandidateError("recovery body is not exact UTF-8 base64") from exc
        supplied_sha = row.get("body_sha256")
        if supplied_sha is not None and _sha256(supplied_sha, "recovery.body_sha256") != sha256_bytes(body):
            raise CandidateError("recovery body SHA-256 mismatch")
        out.append(
            {
                "issue_number": issue,
                "comment_id": comment_id,
                "author_login": author,
                "body_bytes": body,
            }
        )
    out.sort(key=lambda item: item["comment_id"])
    return out


def _apply_git_object_proof(
    sources: Sequence[Mapping[str, Any]],
    proof: Any,
) -> list[dict[str, Any]]:
    if proof is None:
        proof = []
    if not isinstance(proof, list) or any(not isinstance(row, dict) for row in proof):
        raise CandidateError("exact Git-object retrieval proof must be a list of objects")
    by_key: dict[tuple[int, int], list[Mapping[str, Any]]] = {}
    for row in proof:
        key = (
            _positive_int(row.get("run_id"), "git-object-proof.run_id"),
            _positive_int(row.get("run_attempt"), "git-object-proof.run_attempt"),
        )
        by_key.setdefault(key, []).append(row)
    effective: list[dict[str, Any]] = []
    for source in sources:
        row = dict(source)
        if row.get("conclusion") == EXPECTED_SUCCESS and isinstance(row.get("publication_intent_bytes"), (bytes, bytearray)):
            key = (int(row["run_id"]), int(row["run_attempt"]))
            matches = by_key.get(key, [])
            if len(matches) != 1:
                # A retained byte carrier without one exact retrieval proof is
                # deliberately passed to Slice A as unavailable evidence.
                row["publication_intent_bytes"] = None
                row["snapshot_bytes"] = None
            else:
                item = matches[0]
                verified = all(bool(item.get(field)) for field in (
                    "fetch_succeeded", "commit_present", "path_present", "bytes_match"
                ))
                if not verified:
                    row["publication_intent_bytes"] = None
                    row["snapshot_bytes"] = None
        effective.append(row)
    return effective


def _serialisable_source_input(source: Mapping[str, Any], bundle_root: Path) -> dict[str, Any]:
    row = {key: value for key, value in source.items() if not key.endswith("_bytes")}
    run_id = int(source["run_id"])
    attempt = int(source["run_attempt"])
    if isinstance(source.get("publication_intent_bytes"), (bytes, bytearray)):
        rel_intent = PurePosixPath("raw-inputs/sources") / str(run_id) / str(attempt) / "deterministic-publication-intent.json"
        rel_snapshot = PurePosixPath("raw-inputs/sources") / str(run_id) / str(attempt) / "payload/snapshot.json"
        intent = bytes(source["publication_intent_bytes"])
        snapshot = bytes(source["snapshot_bytes"])
        intent_path = bundle_root / rel_intent
        snapshot_path = bundle_root / rel_snapshot
        intent_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        intent_path.write_bytes(intent)
        snapshot_path.write_bytes(snapshot)
        row.update(
            {
                "publication_intent_path": rel_intent.as_posix(),
                "publication_intent_sha256": sha256_bytes(intent),
                "snapshot_path_in_bundle": rel_snapshot.as_posix(),
                "snapshot_sha256": sha256_bytes(snapshot),
            }
        )
    else:
        row.update({"publication_intent_path": None, "snapshot_path_in_bundle": None})
    return row


def _serialise_recoveries(recoveries: Sequence[Mapping[str, Any]], bundle_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for recovery in recoveries:
        comment_id = int(recovery["comment_id"])
        rel = PurePosixPath("raw-inputs/recovery-comments") / f"{comment_id}.txt"
        body = bytes(recovery["body_bytes"])
        path = bundle_root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        rows.append(
            {
                "issue_number": int(recovery["issue_number"]),
                "comment_id": comment_id,
                "author_login": str(recovery["author_login"]),
                "body_path": rel.as_posix(),
                "body_sha256": sha256_bytes(body),
            }
        )
    rows.sort(key=lambda item: item["comment_id"])
    return rows


def _find_source_bytes(source_inputs: Sequence[Mapping[str, Any]], added: Mapping[str, Any]) -> bytes:
    for source in source_inputs:
        if int(source.get("run_id", 0) or 0) != int(added["source_run_id"]):
            continue
        if int(source.get("run_attempt", 0) or 0) != int(added["source_run_attempt"]):
            continue
        raw = source.get("snapshot_bytes")
        if not isinstance(raw, (bytes, bytearray)):
            continue
        snapshot = bytes(raw)
        if sha256_bytes(snapshot) != added["sha256"]:
            raise CandidateError("manifest/source snapshot SHA-256 mismatch")
        if accumulation.git_blob_sha(snapshot) != added["git_blob_sha"]:
            raise CandidateError("manifest/source snapshot Git blob mismatch")
        return snapshot
    raise CandidateError(f"cannot materialise manifest addition {added['path']}")


def _bundle_hashes(bundle_root: Path) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    for path in sorted(Path(bundle_root).rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(bundle_root).as_posix()
        if rel == "bundle-sha256.json":
            continue
        raw = path.read_bytes()
        files.append({"path": rel, "sha256": sha256_bytes(raw), "size": len(raw)})
    return {"contract": BUNDLE_HASH_CONTRACT, "files": files}


def prepare_bundle(
    repository_root: Path,
    base_sha: str,
    capture: Mapping[str, Any],
    artifact_root: Path,
    recovery_capture: Any,
    bundle_root: Path,
    workflow_run_id: int,
    workflow_run_attempt: int,
    git_object_proof: Any = None,
) -> dict[str, Any]:
    bundle_root = Path(bundle_root)
    if bundle_root.exists():
        shutil.rmtree(bundle_root)
    bundle_root.mkdir(parents=True)
    closure = build_source_population_closure(capture)
    if closure["expected_main_sha"] != _sha1(base_sha, "base_sha"):
        raise CandidateError("capture expected_main_sha differs from requested base")
    sources = source_inputs_from_capture(capture, artifact_root)
    effective_sources = _apply_git_object_proof(sources, git_object_proof)
    recoveries = decode_recovery_capture(recovery_capture)
    manifest = accumulation.build_accumulation_manifest(
        Path(repository_root),
        base_sha,
        effective_sources,
        recoveries,
        ALLOWED_RECOVERY_ISSUES,
    )
    _write_json(bundle_root / "accumulation-manifest.json", manifest)
    _write_json(bundle_root / "source-population-closure.json", closure)
    serial_sources = [_serialisable_source_input(source, bundle_root) for source in sources]
    _write_json(bundle_root / "raw-inputs/source-inputs.json", serial_sources)
    serial_recoveries = _serialise_recoveries(recoveries, bundle_root)
    _write_json(bundle_root / "raw-inputs/recovery-comments.json", serial_recoveries)

    if not manifest["blocking_findings"]:
        for added in manifest["added_paths"]:
            rel = PurePosixPath(str(added["path"]))
            if rel.is_absolute() or ".." in rel.parts or rel.parts[:3] != SOURCE_PREFIX.parts:
                raise CandidateError("manifest addition is outside trusted source scope")
            raw = _find_source_bytes(sources, added)
            path = bundle_root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)

    if git_object_proof is None:
        git_object_proof = []
    status = "blocked" if manifest["blocking_findings"] else ("no-candidate" if not manifest["added_paths"] else "candidate")
    evidence = {
        "contract": EVIDENCE_CONTRACT,
        "repository": EXPECTED_REPOSITORY,
        "expected_main_sha": base_sha,
        "base_tree_sha": manifest["base_tree_sha"],
        "candidate_id": manifest["candidate_id"],
        "workflow_run_id": int(workflow_run_id),
        "workflow_run_attempt": int(workflow_run_attempt),
        "prepared_artifact_name": f"trusted-main-source-evidence-candidate-{workflow_run_id}-{workflow_run_attempt}",
        "source_population_closure_sha256": closure["sha256"],
        "recovery_comment_ids": [row["comment_id"] for row in serial_recoveries],
        "recovery_carriers": [
            {
                "issue_number": row["issue_number"],
                "comment_id": row["comment_id"],
                "author_login": row["author_login"],
                "body_sha256": row["body_sha256"],
            }
            for row in serial_recoveries
        ],
        "exact_git_object_retrieval": git_object_proof,
        "status": status,
        "added_paths": [row["path"] for row in manifest["added_paths"]],
    }
    _write_json(bundle_root / "candidate-evidence.json", evidence)
    _write_json(bundle_root / "bundle-sha256.json", _bundle_hashes(bundle_root))
    return evidence


def verify_bundle(bundle_root: Path) -> None:
    expected = _read_json(Path(bundle_root) / "bundle-sha256.json")
    actual = _bundle_hashes(Path(bundle_root))
    if canonical_json_bytes(expected) != canonical_json_bytes(actual):
        raise CandidateError("prepared bundle SHA-256 table mismatch")


def source_inputs_from_bundle(bundle_root: Path) -> list[dict[str, Any]]:
    rows = _read_json(Path(bundle_root) / "raw-inputs/source-inputs.json")
    if not isinstance(rows, list):
        raise CandidateError("bundled source inputs must be a list")
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            raise CandidateError("bundled source input must be an object")
        source = {key: value for key, value in row.items() if key not in {
            "publication_intent_path", "publication_intent_sha256", "snapshot_path_in_bundle", "snapshot_sha256"
        }}
        intent_rel = row.get("publication_intent_path")
        snapshot_rel = row.get("snapshot_path_in_bundle")
        if intent_rel is not None or snapshot_rel is not None:
            if not isinstance(intent_rel, str) or not isinstance(snapshot_rel, str):
                raise CandidateError("bundled source byte references are incomplete")
            intent = (Path(bundle_root) / intent_rel).read_bytes()
            snapshot = (Path(bundle_root) / snapshot_rel).read_bytes()
            if sha256_bytes(intent) != _sha256(row.get("publication_intent_sha256"), "publication intent SHA"):
                raise CandidateError("bundled publication intent hash mismatch")
            if sha256_bytes(snapshot) != _sha256(row.get("snapshot_sha256"), "snapshot SHA"):
                raise CandidateError("bundled snapshot hash mismatch")
            source["publication_intent_bytes"] = intent
            source["snapshot_bytes"] = snapshot
        elif source.get("conclusion") == EXPECTED_SUCCESS:
            source["publication_intent_bytes"] = None
            source["snapshot_bytes"] = None
        out.append(source)
    return out


def recovery_inputs_from_bundle(bundle_root: Path) -> list[dict[str, Any]]:
    rows = _read_json(Path(bundle_root) / "raw-inputs/recovery-comments.json")
    if not isinstance(rows, list):
        raise CandidateError("bundled recovery inputs must be a list")
    out: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            raise CandidateError("bundled recovery input must be an object")
        rel = row.get("body_path")
        if not isinstance(rel, str):
            raise CandidateError("bundled recovery body path is missing")
        body = (Path(bundle_root) / rel).read_bytes()
        if sha256_bytes(body) != _sha256(row.get("body_sha256"), "recovery body SHA"):
            raise CandidateError("bundled recovery body hash mismatch")
        out.append(
            {
                "issue_number": _positive_int(row.get("issue_number"), "recovery.issue_number"),
                "comment_id": _positive_int(row.get("comment_id"), "recovery.comment_id"),
                "author_login": str(row.get("author_login", "")),
                "body_bytes": body,
            }
        )
    out.sort(key=lambda item: item["comment_id"])
    return out


def replay_bundle(repository_root: Path, base_sha: str, bundle_root: Path) -> dict[str, Any]:
    verify_bundle(bundle_root)
    expected_manifest = _read_json(Path(bundle_root) / "accumulation-manifest.json")
    sources = source_inputs_from_bundle(bundle_root)
    evidence = _read_json(Path(bundle_root) / "candidate-evidence.json")
    proof = evidence.get("exact_git_object_retrieval", []) if isinstance(evidence, dict) else []
    effective_sources = _apply_git_object_proof(sources, proof)
    recoveries = recovery_inputs_from_bundle(bundle_root)
    actual = accumulation.build_accumulation_manifest(
        Path(repository_root),
        _sha1(base_sha, "base_sha"),
        effective_sources,
        recoveries,
        ALLOWED_RECOVERY_ISSUES,
    )
    if canonical_json_bytes(expected_manifest) != canonical_json_bytes(actual):
        raise CandidateError("deterministic Slice A replay differs from prepared manifest")
    for added in actual["added_paths"]:
        raw = (Path(bundle_root) / str(added["path"])).read_bytes()
        if sha256_bytes(raw) != added["sha256"] or accumulation.git_blob_sha(raw) != added["git_blob_sha"]:
            raise CandidateError("prepared materialised addition differs from manifest")
    return actual


def verify_closure(prepared_path: Path, current_capture: Mapping[str, Any]) -> dict[str, Any]:
    prepared_raw = Path(prepared_path).read_bytes()
    current = build_source_population_closure(current_capture)
    current_raw = canonical_json_bytes(current) + b"\n"
    if current_raw != prepared_raw:
        raise CandidateError("source population closure drifted after preparation")
    return current


def compare_recovery_capture(bundle_root: Path, current_capture: Any) -> None:
    prepared = recovery_inputs_from_bundle(bundle_root)
    current = decode_recovery_capture(current_capture)
    prepared_identity = [
        {
            "issue_number": row["issue_number"],
            "comment_id": row["comment_id"],
            "author_login": row["author_login"],
            "body_sha256": sha256_bytes(bytes(row["body_bytes"])),
            "body_base64": base64.b64encode(bytes(row["body_bytes"])).decode("ascii"),
        }
        for row in prepared
    ]
    current_identity = [
        {
            "issue_number": row["issue_number"],
            "comment_id": row["comment_id"],
            "author_login": row["author_login"],
            "body_sha256": sha256_bytes(bytes(row["body_bytes"])),
            "body_base64": base64.b64encode(bytes(row["body_bytes"])).decode("ascii"),
        }
        for row in current
    ]
    if canonical_json_bytes(prepared_identity) != canonical_json_bytes(current_identity):
        raise CandidateError("recovery carrier identity/body drifted from prepared bundle")


def _git(repository_root: Path, *args: str) -> bytes:
    completed = subprocess.run(
        ["git", "-C", str(repository_root), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        env={**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_OPTIONAL_LOCKS": "0", "LC_ALL": "C"},
    )
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise CandidateError(detail or f"git {' '.join(args)} failed")
    return completed.stdout


def verify_worktree(repository_root: Path, base_sha: str, manifest: Mapping[str, Any]) -> None:
    expected = {str(row["path"]): row for row in manifest.get("added_paths", []) if isinstance(row, dict)}
    raw = _git(Path(repository_root), "diff", "--cached", "--name-status", "-z", _sha1(base_sha, "base_sha"))
    parts = [part.decode("utf-8", errors="strict") for part in raw.split(b"\0") if part]
    if len(parts) % 2:
        raise CandidateError("cannot parse staged candidate diff")
    seen: set[str] = set()
    for index in range(0, len(parts), 2):
        status, path = parts[index], parts[index + 1]
        if status != "A":
            raise CandidateError(f"candidate diff is not additions-only: {status} {path}")
        rel = PurePosixPath(path)
        if rel.parts[:3] != SOURCE_PREFIX.parts or ".." in rel.parts or path.startswith("_site/"):
            raise CandidateError(f"candidate path is outside trusted source scope: {path}")
        if path not in expected:
            raise CandidateError(f"candidate diff contains path not in manifest: {path}")
        staged = _git(Path(repository_root), "show", f":{path}")
        if sha256_bytes(staged) != expected[path]["sha256"]:
            raise CandidateError(f"candidate bytes differ from manifest: {path}")
        seen.add(path)
    if seen != set(expected):
        raise CandidateError("candidate diff does not equal manifest added_paths")


def render_pr_body(
    manifest: Mapping[str, Any],
    evidence: Mapping[str, Any],
    candidate_commit_sha: str,
) -> str:
    candidate_commit_sha = _sha1(candidate_commit_sha, "candidate_commit_sha")
    window = manifest.get("window") if isinstance(manifest.get("window"), dict) else {}
    additions = [row for row in manifest.get("added_paths", []) if isinstance(row, dict)]
    recoveries = [row for row in manifest.get("applied_recovery_decisions", []) if isinstance(row, dict)]
    blockers = [row for row in manifest.get("blocking_findings", []) if isinstance(row, dict)]
    hours = [row for row in manifest.get("hours", []) if isinstance(row, dict)]
    body = f"""## Summary

Phase 17 Slice B source-only staging candidate. This pull request is **not public evidence authority**; protected `main` remains the sole public evidence authority.

Part of #523

## Exact candidate identity

- base SHA: `{manifest['base_sha']}`
- base tree: `{manifest['base_tree_sha']}`
- candidate commit SHA: `{candidate_commit_sha}`
- candidate ID: `{manifest['candidate_id']}`
- workflow run/attempt: `{evidence['workflow_run_id']}` / `{evidence['workflow_run_attempt']}`
- prepared artifact: `{evidence['prepared_artifact_name']}`
- expected main SHA: `{evidence['expected_main_sha']}`
- source-population closure SHA-256: `{evidence['source_population_closure_sha256']}`
- H_main: `{manifest['anchor_observation_hour_utc']}`
- target window: `{window.get('start_utc')}` .. `{window.get('end_utc')}`

## Ordered hour dispositions

"""
    if hours:
        body += "\n".join(
            f"- `{row.get('canonical_observation_hour_utc')}` — `{row.get('disposition')}`"
            for row in hours
        ) + "\n"
    else:
        body += "- None.\n"
    body += "\n## Exact source additions\n\n"
    if additions:
        body += "\n".join(
            f"- `{row['path']}` — SHA-256 `{row['sha256']}` — Git blob `{row['git_blob_sha']}`"
            for row in additions
        ) + "\n"
    else:
        body += "- None.\n"
    body += "\n## Recovery decisions\n\n"
    if recoveries:
        for row in recoveries:
            carrier = row.get("carrier", {}) if isinstance(row, dict) else {}
            body += (
                f"- comment `{carrier.get('comment_id')}` / class `{row.get('blocker_class')}` / "
                f"blocker `{row.get('blocker_fingerprint')}` / body SHA-256 `{carrier.get('body_sha256')}`\n"
            )
    else:
        body += "- None supplied/applied.\n"
    body += "\n## Remaining blockers\n\n"
    if blockers:
        body += "\n".join(
            f"- `{row.get('blocker_class')}` / `{row.get('blocker_fingerprint')}`" for row in blockers
        ) + "\n"
    else:
        body += "- None.\n"
    body += """

## Deterministic replay

- Prepared bundle SHA-256 table verified before replay.
- Exact source and recovery bytes rehydrated from the prepared bundle.
- Slice A/helper replay reproduced the exact canonical manifest, `candidate_id`, `added_paths`, and materialised bytes before publication.

## Authority and scope boundaries

- Additions-only source evidence under `data/crypto/hourly/...`.
- No model or report generation.
- No Phase 14 / #477 authority.
- No automatic merge and no merge capability in Slice B.
- No recurring schedule.
- Candidate branch/PR is disposable staging only.
- Any refreshed head or changed `candidate_id` requires a new substantive review.

## Verification contract

Publication success for this workflow run requires exact PR base/head/body pairing, live protected `main == expected_main_sha`, byte-identical recovery carriers (or the exact empty recovery-input set), deterministic Slice A replay, and byte-identical source-population closure immediately around the remote write boundaries.
"""
    return body.rstrip() + "\n"


def verify_pr_snapshot(
    snapshot: Mapping[str, Any],
    expected_main_sha: str,
    candidate_commit_sha: str,
    candidate_id: str,
    workflow_run_id: int,
    workflow_run_attempt: int,
) -> None:
    base = snapshot.get("base") if isinstance(snapshot.get("base"), dict) else {}
    head = snapshot.get("head") if isinstance(snapshot.get("head"), dict) else {}
    if base.get("ref") != "main" or base.get("sha") != _sha1(expected_main_sha, "expected_main_sha"):
        raise CandidateError("final PR base identity mismatch")
    if head.get("ref") != EXPECTED_BRANCH or head.get("sha") != _sha1(candidate_commit_sha, "candidate_commit_sha"):
        raise CandidateError("final PR head identity mismatch")
    body = snapshot.get("body")
    if not isinstance(body, str):
        raise CandidateError("final PR body is missing")
    required = (
        str(candidate_id),
        str(candidate_commit_sha),
        str(workflow_run_id),
        str(workflow_run_attempt),
        str(expected_main_sha),
    )
    if any(value not in body for value in required):
        raise CandidateError("final PR body does not carry exact run/candidate/base identity")


def _print_json(payload: Any) -> None:
    sys.stdout.buffer.write(canonical_json_bytes(payload) + b"\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 17 Slice B source-candidate helper")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("window")
    p.add_argument("--repository-root", default=".")
    p.add_argument("--base-sha", required=True)

    p = sub.add_parser("closure")
    p.add_argument("--capture", required=True)
    p.add_argument("--output")

    p = sub.add_parser("prepare")
    p.add_argument("--repository-root", default=".")
    p.add_argument("--base-sha", required=True)
    p.add_argument("--capture", required=True)
    p.add_argument("--artifact-root", required=True)
    p.add_argument("--recovery-capture", required=True)
    p.add_argument("--bundle-root", required=True)
    p.add_argument("--workflow-run-id", required=True, type=int)
    p.add_argument("--workflow-run-attempt", required=True, type=int)
    p.add_argument("--git-object-proof")

    p = sub.add_parser("replay")
    p.add_argument("--repository-root", default=".")
    p.add_argument("--base-sha", required=True)
    p.add_argument("--bundle-root", required=True)

    p = sub.add_parser("verify-closure")
    p.add_argument("--prepared", required=True)
    p.add_argument("--capture", required=True)

    p = sub.add_parser("verify-recoveries")
    p.add_argument("--bundle-root", required=True)
    p.add_argument("--current-capture", required=True)

    p = sub.add_parser("verify-worktree")
    p.add_argument("--repository-root", default=".")
    p.add_argument("--base-sha", required=True)
    p.add_argument("--manifest", required=True)

    p = sub.add_parser("render-pr")
    p.add_argument("--manifest", required=True)
    p.add_argument("--evidence", required=True)
    p.add_argument("--candidate-commit-sha", required=True)
    p.add_argument("--output")

    p = sub.add_parser("verify-pr")
    p.add_argument("--snapshot", required=True)
    p.add_argument("--expected-main-sha", required=True)
    p.add_argument("--candidate-commit-sha", required=True)
    p.add_argument("--candidate-id", required=True)
    p.add_argument("--workflow-run-id", required=True, type=int)
    p.add_argument("--workflow-run-attempt", required=True, type=int)

    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.command == "window":
            _print_json(derive_window(Path(args.repository_root), args.base_sha))
        elif args.command == "closure":
            closure = build_source_population_closure(_read_json(Path(args.capture)))
            if args.output:
                _write_json(Path(args.output), closure)
            else:
                _print_json(closure)
        elif args.command == "prepare":
            evidence = prepare_bundle(
                Path(args.repository_root),
                args.base_sha,
                _read_json(Path(args.capture)),
                Path(args.artifact_root),
                _read_json(Path(args.recovery_capture)),
                Path(args.bundle_root),
                args.workflow_run_id,
                args.workflow_run_attempt,
                _read_json(Path(args.git_object_proof)) if args.git_object_proof else [],
            )
            _print_json(evidence)
        elif args.command == "replay":
            manifest = replay_bundle(Path(args.repository_root), args.base_sha, Path(args.bundle_root))
            _print_json({"candidate_id": manifest["candidate_id"], "added_paths": manifest["added_paths"]})
        elif args.command == "verify-closure":
            closure = verify_closure(Path(args.prepared), _read_json(Path(args.capture)))
            _print_json({"sha256": closure["sha256"]})
        elif args.command == "verify-recoveries":
            compare_recovery_capture(Path(args.bundle_root), _read_json(Path(args.current_capture)))
            _print_json({"recovery_fresh": True})
        elif args.command == "verify-worktree":
            verify_worktree(Path(args.repository_root), args.base_sha, _read_json(Path(args.manifest)))
            _print_json({"candidate_scope": "verified"})
        elif args.command == "render-pr":
            body = render_pr_body(
                _read_json(Path(args.manifest)),
                _read_json(Path(args.evidence)),
                args.candidate_commit_sha,
            )
            if args.output:
                Path(args.output).write_text(body, encoding="utf-8")
            else:
                sys.stdout.write(body)
        elif args.command == "verify-pr":
            verify_pr_snapshot(
                _read_json(Path(args.snapshot)),
                args.expected_main_sha,
                args.candidate_commit_sha,
                args.candidate_id,
                args.workflow_run_id,
                args.workflow_run_attempt,
            )
            _print_json({"pr_identity": "verified"})
        else:  # pragma: no cover
            raise CandidateError("unknown command")
        return 0
    except (CandidateError, accumulation.AccumulationError, OSError, TypeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


# Review-remediation overrides are intentionally defined after the original
# helpers so the Slice B behaviour changes remain narrow and auditable.
_ORIGINAL_BUILD_SOURCE_POPULATION_CLOSURE = build_source_population_closure


def build_source_population_closure(capture: Mapping[str, Any]) -> dict[str, Any]:
    """Bind the closed population to the resolved scheduled ingestion workflow."""
    expected_workflow_id = _positive_int(capture.get("workflow_id"), "capture.workflow_id")
    closure = _ORIGINAL_BUILD_SOURCE_POPULATION_CLOSURE(capture)
    for run in closure["runs"]:
        for attempt in run["attempts"]:
            if attempt["workflow_id"] != expected_workflow_id:
                raise CandidateError("attempt workflow id does not match capture workflow")
            if attempt["event"] != EXPECTED_EVENT:
                raise CandidateError("attempt event does not match scheduled ingestion workflow")
    closure.pop("sha256", None)
    closure["workflow_id"] = expected_workflow_id
    closure["sha256"] = sha256_bytes(canonical_json_bytes(closure))
    return closure


def publication_intent_git_reference(intent_bytes: bytes) -> dict[str, Any]:
    """Classify exact intent bytes without failing before Slice A can fingerprint them."""
    if not isinstance(intent_bytes, (bytes, bytearray)):
        raise CandidateError("publication intent reference requires exact bytes")
    raw = bytes(intent_bytes)
    result: dict[str, Any] = {
        "publication_intent_sha256": sha256_bytes(raw),
        "intent_parse_succeeded": False,
        "intent_reference_valid": False,
        "snapshot_commit_sha": None,
        "snapshot_path": None,
    }
    try:
        payload = json.loads(raw.decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return result
    if not isinstance(payload, dict):
        return result
    result["intent_parse_succeeded"] = True
    commit_sha = str(payload.get("snapshot_commit_sha") or "")
    snapshot_path = str(payload.get("snapshot_path") or "").replace("\\", "/")
    result["snapshot_commit_sha"] = commit_sha or None
    result["snapshot_path"] = snapshot_path or None
    path = PurePosixPath(snapshot_path)
    result["intent_reference_valid"] = bool(
        SHA1_RE.fullmatch(commit_sha)
        and snapshot_path
        and not snapshot_path.startswith("/")
        and ".." not in path.parts
        and path.parts[:3] == SOURCE_PREFIX.parts
        and snapshot_path.endswith("_source_snapshot.json")
    )
    return result


def _apply_git_object_proof(
    sources: Sequence[Mapping[str, Any]],
    proof: Any,
) -> list[dict[str, Any]]:
    """Apply exact-object proof while preserving malformed retained bytes for Slice A."""
    if proof is None:
        proof = []
    if not isinstance(proof, list) or any(not isinstance(item, dict) for item in proof):
        raise CandidateError("exact Git-object retrieval proof must be a list of objects")
    by_key: dict[tuple[int, int], list[Mapping[str, Any]]] = {}
    for item in proof:
        key = (
            _positive_int(item.get("run_id"), "git-object-proof.run_id"),
            _positive_int(item.get("run_attempt"), "git-object-proof.run_attempt"),
        )
        by_key.setdefault(key, []).append(item)

    effective: list[dict[str, Any]] = []
    for source in sources:
        row = dict(source)
        intent_value = row.get("publication_intent_bytes")
        if row.get("conclusion") != EXPECTED_SUCCESS or not isinstance(intent_value, (bytes, bytearray)):
            effective.append(row)
            continue
        snapshot_value = row.get("snapshot_bytes")
        if not isinstance(snapshot_value, (bytes, bytearray)):
            row["publication_intent_bytes"] = None
            row["snapshot_bytes"] = None
            effective.append(row)
            continue

        key = (int(row["run_id"]), int(row["run_attempt"]))
        matches = by_key.get(key, [])
        if len(matches) != 1:
            row["publication_intent_bytes"] = None
            row["snapshot_bytes"] = None
            effective.append(row)
            continue

        item = matches[0]
        intent = bytes(intent_value)
        snapshot = bytes(snapshot_value)
        reference = publication_intent_git_reference(intent)
        for field in (
            "publication_intent_sha256",
            "intent_parse_succeeded",
            "intent_reference_valid",
            "snapshot_commit_sha",
            "snapshot_path",
        ):
            if item.get(field) != reference[field]:
                raise CandidateError(f"Git-object proof {field} differs from exact retained intent")
        if _sha256(item.get("snapshot_sha256"), "git-object-proof.snapshot_sha256") != sha256_bytes(snapshot):
            raise CandidateError("Git-object proof snapshot SHA-256 differs from exact retained bytes")

        if reference["intent_reference_valid"]:
            verified = all(
                item.get(field) is True
                for field in ("fetch_succeeded", "commit_present", "path_present", "bytes_match")
            )
            if not verified:
                # A syntactically valid exact reference that cannot be proved is
                # intentionally downgraded to Slice A unavailable-input evidence.
                row["publication_intent_bytes"] = None
                row["snapshot_bytes"] = None
        # Malformed/incomplete intent bytes are deliberately preserved so Slice A
        # emits a canonical source-input-unverifiable blocker whose fingerprint
        # binds the exact intent and snapshot SHA-256 identities.
        effective.append(row)
    return effective


if __name__ == "__main__":
    raise SystemExit(main())
