#!/usr/bin/env python3
"""Daily-only publication candidate and preflight policy.

This module is deliberately separate from the hourly publication gate.
"""
from __future__ import annotations

import hashlib
import re
from datetime import date, datetime, time, timedelta, timezone
from pathlib import PurePosixPath
from typing import Any, Mapping, Sequence

CONTRACT = "cryptopulse-daily-publication/v1"
GENERATION_WORKFLOW_PATH = ".github/workflows/generate-daily-crypto-report.yml"
BRANCH = re.compile(r"^automation/daily-publication-([1-9][0-9]*)-([1-9][0-9]*)-(\d{4}-\d{2}-\d{2})$")
SHA1 = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
STATUSES = {"valid-ok", "valid-degraded", "rejected", "missing"}
REPORT_PREFIX = "reports/crypto/daily/"


class DailyPublicationError(ValueError):
    pass


def _sha(value: Any, pattern: re.Pattern[str], name: str) -> str:
    text = str(value or "")
    if not pattern.fullmatch(text):
        raise DailyPublicationError(f"invalid {name}")
    return text


def canonical_report_path(day: str) -> str:
    parsed = date.fromisoformat(day)
    if parsed.isoformat() != day:
        raise DailyPublicationError("reporting date is not canonical")
    return f"{REPORT_PREFIX}{parsed:%Y/%m/%d}/{day}_UTC.md"


def source_population_digest(hours: Sequence[Mapping[str, Any]]) -> str:
    import json
    encoded = json.dumps(list(hours), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def validate_daily_scope(paths: Sequence[str], report_path: str) -> None:
    if report_path != canonical_report_path(report_path.rsplit("/", 1)[-1].removesuffix("_UTC.md")):
        raise DailyPublicationError("daily report path is not canonical")
    if list(paths) != [report_path]:
        raise DailyPublicationError("candidate must change exactly one daily Markdown path")
    pure = PurePosixPath(report_path)
    if ".." in pure.parts or not report_path.endswith("_UTC.md"):
        raise DailyPublicationError("unsafe daily report path")


def validate_hours(day: str, hours: Sequence[Mapping[str, Any]]) -> None:
    if not isinstance(hours, (list, tuple)) or len(hours) != 24:
        raise DailyPublicationError("attestation must contain all 24 UTC hours")
    start = datetime.combine(date.fromisoformat(day), time.min, tzinfo=timezone.utc)
    seen: set[str] = set()
    for offset, slot in enumerate(hours):
        expected = (start + timedelta(hours=offset)).strftime("%Y-%m-%dT%H:00:00Z")
        if not isinstance(slot, Mapping) or slot.get("hour") != expected:
            raise DailyPublicationError("hour population is incomplete or out of order")
        status = slot.get("status")
        if status not in STATUSES:
            raise DailyPublicationError("unsupported hour disposition")
        path, digest = slot.get("path"), slot.get("sha256")
        if status == "missing":
            if path is not None or digest is not None:
                raise DailyPublicationError("missing hour must not claim source bytes")
        else:
            if not isinstance(path, str) or not path.startswith("data/crypto/hourly/"):
                raise DailyPublicationError("source path is outside hourly population")
            _sha(digest, SHA256, "source digest")
            if path in seen:
                raise DailyPublicationError("duplicate source snapshot path")
            seen.add(path)


def validate_attestation(value: Mapping[str, Any]) -> None:
    if value.get("schema") != CONTRACT or value.get("variant") != "daily-review-pr/v1":
        raise DailyPublicationError("unsupported daily attestation type")
    if value.get("generation_workflow_path") != GENERATION_WORKFLOW_PATH:
        raise DailyPublicationError("daily generation workflow identity mismatch")
    day = value.get("reporting_date_utc")
    if not isinstance(day, str) or canonical_report_path(day) != value.get("report_path"):
        raise DailyPublicationError("daily report identity mismatch")
    expected_cutoff = datetime.combine(date.fromisoformat(day) + timedelta(days=1), time(1), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if value.get("cutoff_utc") != expected_cutoff:
        raise DailyPublicationError("daily cutoff mismatch")
    for field in ("trusted_main_sha", "expected_main_base_sha", "candidate_head_sha"):
        _sha(value.get(field), SHA1, field)
    _sha(value.get("report_sha256"), SHA256, "report digest")
    _sha(value.get("source_config_sha256"), SHA256, "source config digest")
    hours = value.get("hours")
    validate_hours(day, hours)
    if value.get("source_population_sha256") != source_population_digest(hours):
        raise DailyPublicationError("source population digest mismatch")
    for field in ("generation_workflow_id", "generation_run_id", "generation_run_attempt", "pull_request_number", "publication_app_actor_id"):
        if not isinstance(value.get(field), int) or value[field] <= 0:
            raise DailyPublicationError(f"invalid {field}")
    if not isinstance(value.get("publication_app_slug"), str) or not value["publication_app_slug"]:
        raise DailyPublicationError("missing publication App slug")
    if value.get("candidate_branch", "").startswith("automation/daily-publication-") is False:
        raise DailyPublicationError("daily candidate branch prefix mismatch")
    match = BRANCH.fullmatch(value["candidate_branch"])
    if not match or int(match.group(1)) != value["generation_run_id"] or int(match.group(2)) != value["generation_run_attempt"] or match.group(3) != day:
        raise DailyPublicationError("daily branch identity mismatch")


def build_attestation(*, reporting_date_utc: str, trusted_main_sha: str,
                      expected_main_base_sha: str, source_config_sha256: str,
                      hours: Sequence[Mapping[str, Any]],
                      report_path: str, report_bytes: bytes, candidate_head_sha: str,
                      candidate_branch: str, pull_request_number: int,
                      generation_workflow_id: int, generation_run_id: int,
                      generation_run_attempt: int, publication_app_actor_id: int,
                      publication_app_slug: str) -> dict[str, Any]:
    value = {"schema": CONTRACT, "variant": "daily-review-pr/v1",
             "generation_workflow_path": GENERATION_WORKFLOW_PATH,
             "reporting_date_utc": reporting_date_utc,
             "cutoff_utc": (datetime.combine(date.fromisoformat(reporting_date_utc) + timedelta(days=1), time(1), timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")),
             "trusted_main_sha": trusted_main_sha, "expected_main_base_sha": expected_main_base_sha,
             "source_config_sha256": source_config_sha256,
             "hours": list(hours), "source_population_sha256": source_population_digest(hours),
             "report_path": report_path, "report_sha256": hashlib.sha256(report_bytes).hexdigest(),
             "candidate_head_sha": candidate_head_sha, "candidate_branch": candidate_branch,
             "pull_request_number": pull_request_number, "generation_workflow_id": generation_workflow_id,
             "generation_run_id": generation_run_id, "generation_run_attempt": generation_run_attempt,
             "publication_app_actor_id": publication_app_actor_id, "publication_app_slug": publication_app_slug}
    validate_attestation(value)
    return value


def evaluate_daily_gate(attestation: Mapping[str, Any], facts: Mapping[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    try:
        validate_attestation(attestation)
    except (DailyPublicationError, ValueError, TypeError) as exc:
        return {"eligible": False, "reasons": [str(exc)]}
    checks = {
        "trusted source ancestry at cutoff": facts.get("source_ancestor_at_cutoff") is True,
        "source files and pinned config replay": facts.get("source_replay_valid") is True,
        "source population bytes": facts.get("source_population_valid") is True,
        "deterministic report replay": facts.get("report_replay_valid") is True,
        "candidate path scope": facts.get("changed_files") == [attestation["report_path"]],
        "no prior daily date": facts.get("duplicate_date_count") == 0,
        "no existing candidate PR": facts.get("duplicate_candidate_count") == 0,
        "exact PR number": facts.get("pr_number") == attestation["pull_request_number"],
        "same-repository PR": facts.get("same_repository") is True,
        "open App-authored PR": facts.get("pr_open") is True and facts.get("pr_author_id") == attestation["publication_app_actor_id"] and facts.get("pr_author_login") == f"{attestation['publication_app_slug']}[bot]",
        "exact PR head": facts.get("pr_head_sha") == attestation["candidate_head_sha"] and facts.get("pr_head_ref") == attestation["candidate_branch"],
        "exact PR base": facts.get("pr_base") == "main" and facts.get("current_main_sha") == attestation["expected_main_base_sha"],
        "successful validation identity": facts.get("validation_head_sha") == attestation["candidate_head_sha"] and facts.get("validation_status") == "success" and facts.get("validation_check") == "Build site and check generated output",
        "validation check application identity": facts.get("validation_app_slug") == "github-actions",
        "unique immutable attestation artifact": facts.get("attestation_count") == 1 and facts.get("attestation_expired") is False and facts.get("artifact_name") == f"cryptopulse-daily-attestation-{attestation['generation_run_id']}-{attestation['generation_run_attempt']}",
        "generation run identity": facts.get("generation_run_id") == attestation["generation_run_id"] and facts.get("generation_workflow_id") == attestation["generation_workflow_id"] and facts.get("generation_workflow_path") == GENERATION_WORKFLOW_PATH and facts.get("generation_head_sha") == attestation["expected_main_base_sha"],
        "trusted generation event": facts.get("trusted_generation_run") is True
            and facts.get("generation_event") in ("workflow_dispatch", "schedule"),
        "exact report bytes": facts.get("report_path") == attestation["report_path"] and facts.get("report_sha256") == attestation["report_sha256"],
    }
    reasons.extend(label for label, ok in checks.items() if not ok)
    return {"eligible": not reasons, "reasons": reasons}


def independently_validate_candidate(root: Any, attestation: Mapping[str, Any],
                                     report_bytes: bytes, changed_paths: Sequence[str]) -> None:
    """Re-read pinned Git blobs and replay the report without trusting its PR body."""
    import tempfile
    from pathlib import Path
    from generate_crypto_daily_report import evidence, render, source_commit, git
    from validate_crypto_snapshot import load_config
    validate_attestation(attestation)
    validate_daily_scope(changed_paths, str(attestation["report_path"]))
    root = Path(root)
    day = date.fromisoformat(str(attestation["reporting_date_utc"]))
    cutoff = datetime.combine(day + timedelta(days=1), time(1), timezone.utc)
    source_commit(root, str(attestation["trusted_main_sha"]), cutoff)
    raw_config = git(root, "show", f"{attestation['trusted_main_sha']}:config/crypto_sources.yml")
    if hashlib.sha256(raw_config).hexdigest() != attestation["source_config_sha256"]:
        raise DailyPublicationError("pinned source config digest mismatch")
    with tempfile.TemporaryDirectory(prefix="cryptopulse-daily-gate-") as tmp:
        config_path = Path(tmp) / "crypto_sources.yml"
        config_path.write_bytes(raw_config)
        config = load_config(config_path)
    records = evidence(root, str(attestation["trusted_main_sha"]), day, config)
    population = [{"hour": item["hour"], "status": item["status"],
                   "path": item.get("path"), "sha256": item.get("sha256")}
                  for item in records]
    if source_population_digest(population) != attestation["source_population_sha256"]:
        raise DailyPublicationError("pinned source population differs from attestation")
    if hashlib.sha256(report_bytes).hexdigest() != attestation["report_sha256"]:
        raise DailyPublicationError("daily report bytes differ from attestation")
    if render(day, str(attestation["trusted_main_sha"]), records).encode("utf-8") != report_bytes:
        raise DailyPublicationError("daily report replay differs from candidate bytes")
