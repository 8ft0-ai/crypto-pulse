#!/usr/bin/env python3
"""Candidate-only, fail-closed temporal admissibility of scheduled source evidence.

A GitHub job completion is not a Phase-12 observation hour.  The 24-hour
allowance is an *eligibility limit*, not a claimed clock-accuracy guarantee.
Only exact Phase-12-valid snapshot bytes ever supply an observation hour.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

import trusted_main_source_evidence_accumulation as legacy

CONTRACT = "trusted-main-scheduled-source-temporal-admissibility/v1"
MAX_POST_COMPLETION_SKEW = timedelta(hours=24)
SOURCE_WORKFLOW = ".github/workflows/ingest-crypto-sources.yml"
INGEST_JOB_NAME = "Fetch source snapshot and open PR"

# Immutable *Git blob* approvals, not October run IDs or source commit IDs.
# These three exact blobs were verified at the historical 12-15 October heads.
# If the producer, validator or scheduled workflow changes, missing-byte
# historical exclusions stop until that changed contract is reviewed.
SUPPORTED_BLOBS = {
    SOURCE_WORKFLOW: "fa3962d2c24c0650070eea798a159493b50ecaaa",
    "scripts/ingest_crypto_sources.py": "3ef984a7db5e5c5edae1137b14b3cec0e56165f4",
    "scripts/validate_crypto_observation_hour.py": "21e18835c1047243ebda4b5ec7760fd9df793356",
}
# Later scheduled ingestion adds the bounded scheduler request and accepted-hour
# receipt stages, but retains the identical generation/validation commands.
# These are audited workflow blobs, not an allowlist of source run IDs.
ADDITIONAL_SCHEDULED_WORKFLOW_BLOBS = frozenset({
    "b23c2854e01073ed9022305e4b881ac4e1dc2613",
})


def _utc(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z", value
    ):
        raise ValueError(f"{field} is not an exact UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError(f"{field} is not a real UTC timestamp") from exc
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def prove_bound(repository_root: Path, source: Mapping[str, Any]) -> dict[str, Any]:
    """Prove a candidate admissibility ceiling, without asserting source hour."""
    if source.get("event") != "schedule" or source.get("conclusion") != "success":
        raise ValueError("only successful scheduled source input has a temporal bound")
    head = source.get("workflow_head_sha")
    if not isinstance(head, str) or legacy.SHA1_RE.fullmatch(head) is None:
        raise ValueError("scheduled input has no exact source commit")
    if source.get("workflow_path") != SOURCE_WORKFLOW:
        raise ValueError("scheduled workflow path differs from approved provenance")
    blobs: dict[str, str] = {}
    for path, approved in SUPPORTED_BLOBS.items():
        try:
            actual = legacy._git_text(Path(repository_root), "rev-parse", f"{head}:{path}")
        except legacy.AccumulationError as exc:
            raise ValueError(f"cannot establish source-head blob for {path}") from exc
        allowed = {approved}
        if path == SOURCE_WORKFLOW:
            allowed.update(ADDITIONAL_SCHEDULED_WORKFLOW_BLOBS)
        if actual not in allowed:
            raise ValueError(f"unsupported historical temporal provenance: {path}")
        blobs[path] = actual

    record = source.get("temporal_job_proof")
    if not isinstance(record, dict) or type(record.get("total_count")) is not int:
        raise ValueError("missing exact attempt-specific job census")
    jobs = record.get("jobs")
    if record["total_count"] != 1 or not isinstance(jobs, list) or len(jobs) != 1:
        raise ValueError("scheduled source does not have exactly one completed job")
    job = jobs[0]
    if not isinstance(job, dict) or any(
        type(job.get(name)) is not int or job[name] <= 0
        for name in ("id", "run_id", "run_attempt")
    ):
        raise ValueError("scheduled job identity is incomplete")
    if (
        job["run_id"] != source.get("run_id")
        or job["run_attempt"] != source.get("run_attempt")
        or job.get("head_sha") != head
        or job.get("name") != INGEST_JOB_NAME
        or job.get("status") != "completed"
        or job.get("conclusion") != "success"
    ):
        raise ValueError("scheduled job does not bind exact successful attempt")
    started = _utc(job.get("started_at"), "job.started_at")
    completed = _utc(job.get("completed_at"), "job.completed_at")
    if completed < started:
        raise ValueError("job completed before it started")
    steps = job.get("steps")
    if not isinstance(steps, list):
        raise ValueError("scheduled job steps are missing")
    selected: dict[str, dict[str, Any]] = {}
    for step in steps:
        if not isinstance(step, dict):
            raise ValueError("malformed scheduled job step")
        name = step.get("name")
        if name in {"Fetch source data", "Validate observation hour"}:
            if name in selected:
                raise ValueError("duplicate temporal-provenance job step")
            if step.get("status") != "completed" or step.get("conclusion") != "success":
                raise ValueError("required source step did not succeed")
            s_start = _utc(step.get("started_at"), f"{name}.started_at")
            s_end = _utc(step.get("completed_at"), f"{name}.completed_at")
            if not (started <= s_start <= s_end <= completed):
                raise ValueError("source step timing exceeds completed ingestion job")
            selected[name] = {"started": s_start, "completed": s_end}
    if set(selected) != {"Fetch source data", "Validate observation hour"}:
        raise ValueError("required source generation/validation steps are absent")
    if selected["Fetch source data"]["completed"] > selected["Validate observation hour"]["started"]:
        raise ValueError("observation-hour validation precedes source generation")
    upper = completed + MAX_POST_COMPLETION_SKEW
    return {
        "contract": CONTRACT,
        "source_run_id": job["run_id"],
        "source_run_attempt": job["run_attempt"],
        "source_workflow_id": source.get("workflow_id"),
        "source_workflow_head_sha": head,
        "source_provenance_blobs": blobs,
        "job_id": job["id"],
        "job_completed_at_utc": _iso(completed),
        "job_proof_sha256": legacy.sha256_bytes(legacy.canonical_json_bytes(record)),
        "max_post_completion_skew_hours": 24,
        "latest_admissible_observation_hour_utc": _iso(
            upper.replace(minute=0, second=0, microsecond=0)
        ),
    }


def verify_exact_snapshot_timestamp(source: Mapping[str, Any], bound: Mapping[str, Any]) -> None:
    """New candidate gate, applied only after full exact-byte Phase-12 validation."""
    raw = source.get("snapshot_bytes")
    if not isinstance(raw, (bytes, bytearray)):
        raise ValueError("candidate snapshot bytes are missing")
    try:
        snapshot = json.loads(bytes(raw).decode("utf-8"))
        generated = _utc(snapshot["run"]["generated_at_utc"], "snapshot.run.generated_at_utc")
    except (KeyError, TypeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("validated snapshot has no exact generation timestamp") from exc
    finished = _utc(bound["job_completed_at_utc"], "job.completed_at")
    if generated > finished + MAX_POST_COMPLETION_SKEW:
        raise ValueError("scheduled source generated timestamp exceeds admissibility ceiling")
