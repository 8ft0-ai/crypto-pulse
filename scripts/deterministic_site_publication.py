#!/usr/bin/env python3
"""Credential-free policy helpers for deterministic-site-publication/v3."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable, Mapping

CONTRACT = "deterministic-site-publication/v3"
EXPECTED_SOURCE_WORKFLOW_PATH = ".github/workflows/ingest-crypto-sources.yml"
EXPECTED_GENERATION_WORKFLOW_PATH = ".github/workflows/generate-deterministic-site-publication.yml"
EXPECTED_VALIDATION_WORKFLOW = "Validate CryptoPulse PR"
EXPECTED_VALIDATION_CHECK = "Build site and check generated output"
EXPECTED_VALIDATION_APP = "github-actions"
ACTIVATION_DISABLED = "disabled"
ACTIVATION_PILOT = "pilot"
ACTIVATION_RECURRING = "recurring"
ACTIVATION_STATES = {ACTIVATION_DISABLED, ACTIVATION_PILOT, ACTIVATION_RECURRING}
SHA1_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
BRANCH_RE = re.compile(
    r"^automation/deterministic-publication-([1-9][0-9]*)-([1-9][0-9]*)-([0-9]{8}T[0-9]{4}Z)$"
)


class PublicationPolicyError(ValueError):
    pass


@dataclass(frozen=True)
class GateDecision:
    eligible: bool
    reasons: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {"eligible": self.eligible, "reasons": list(self.reasons)}


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def strings(value: Any) -> list[str]:
    return [str(item) for item in as_list(value)]


def canonical_json_bytes(payload: Mapping[str, Any]) -> bytes:
    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def canonical_json_sha256(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(payload) + b"\n")


def load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PublicationPolicyError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise PublicationPolicyError(f"JSON root must be an object: {path}")
    return payload


def require_sha1(value: Any, field: str) -> str:
    text = str(value or "").lower()
    if not SHA1_RE.fullmatch(text):
        raise PublicationPolicyError(
            f"{field} must be a 40-character lowercase Git SHA"
        )
    return text


def require_sha256(value: Any, field: str) -> str:
    text = str(value or "").lower()
    if not SHA256_RE.fullmatch(text):
        raise PublicationPolicyError(
            f"{field} must be a 64-character lowercase SHA-256"
        )
    return text


def parse_utc_hour(value: Any) -> datetime:
    text = str(value or "")
    if not text.endswith("Z"):
        raise PublicationPolicyError(
            "observation_hour_utc must use canonical UTC Z notation"
        )
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00")
    except ValueError as exc:
        raise PublicationPolicyError(
            "observation_hour_utc is not a valid ISO-8601 timestamp"
        ) from exc
    if parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise PublicationPolicyError("observation_hour_utc must be UTC")
    if parsed.minute or parsed.second or parsed.microsecond:
        raise PublicationPolicyError(
            "observation_hour_utc must identify the start of a UTC hour"
        )
    if text != parsed.strftime("%Y-%m-%dT%H:00:00Z"):
        raise PublicationPolicyError("observation_hour_utc is not canonical")
    return parsed


def compact_observation_hour(value: Any) -> str:
    return parse_utc_hour(value).strftime("%Y%m%dT%H00Z")


def publication_branch(
    run_id: int | str,
    attempt: int | str,
    observation_hour_utc: str,
) -> str:
    if int(run_id) <= 0 or int(attempt) <= 0:
        raise PublicationPolicyError("run identity must be positive")
    return (
        "automation/deterministic-publication-"
        f"{int(run_id)}-{int(attempt)}-{compact_observation_hour(observation_hour_utc)}"
    )


def parse_publication_branch(branch: str) -> dict[str, Any]:
    match = BRANCH_RE.fullmatch(str(branch or ""))
    if not match:
        raise PublicationPolicyError(
            "candidate branch does not match deterministic publication identity"
        )
    run_id = int(match.group(1))
    attempt = int(match.group(2))
    try:
        hour = datetime.strptime(match.group(3), "%Y%m%dT%H%MZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError as exc:
        raise PublicationPolicyError(
            "candidate branch contains an invalid observation hour"
        ) from exc
    if hour.minute:
        raise PublicationPolicyError(
            "candidate branch observation hour is not canonical"
        )
    return {
        "generation_workflow_run_id": run_id,
        "generation_workflow_run_attempt": attempt,
        "observation_hour_utc": hour.strftime("%Y-%m-%dT%H:00:00Z"),
    }


def normalise_activation(value: Any) -> str:
    text = str(value or ACTIVATION_DISABLED).strip().lower()
    return text if text in ACTIVATION_STATES else ACTIVATION_DISABLED


def safe_repo_path(path: Any, prefix: str, suffix: str) -> bool:
    text = str(path or "").replace("\\", "/")
    pure = PurePosixPath(text)
    return bool(
        text
        and not text.startswith("/")
        and ".." not in pure.parts
        and text.startswith(prefix)
        and text.endswith(suffix)
    )


def validate_candidate_scope(
    paths: Iterable[str], snapshot_path: str, report_path: str
) -> tuple[str, str]:
    if not safe_repo_path(snapshot_path, "data/crypto/hourly/", ".json"):
        raise PublicationPolicyError(
            "snapshot_path is outside deterministic publication scope"
        )
    if not safe_repo_path(report_path, "reports/crypto/hourly/", ".md"):
        raise PublicationPolicyError(
            "report_path is outside deterministic publication scope"
        )
    changed = [
        str(path).strip().replace("\\", "/")
        for path in paths
        if str(path).strip()
    ]
    if len(changed) != 2 or set(changed) != {snapshot_path, report_path}:
        raise PublicationPolicyError(
            "publication candidate must change exactly its snapshot JSON and deterministic Markdown report"
        )
    return snapshot_path, report_path


def quality_reasons(
    snapshot: Mapping[str, Any], quality: Mapping[str, Any]
) -> list[str]:
    reasons: list[str] = []
    if str(quality.get("status", "")) != "valid-ok":
        reasons.append("snapshot quality is not valid-ok")
    if strings(quality.get("blocking_issues")):
        reasons.append("snapshot quality has blocking issues")
    if strings(quality.get("non_blocking_warnings")):
        reasons.append("snapshot quality has warnings")
    if strings(snapshot.get("warnings")):
        reasons.append("snapshot records warnings")
    if strings(snapshot.get("errors")):
        reasons.append("snapshot records errors")
    try:
        parse_utc_hour(as_dict(snapshot.get("run")).get("observation_hour_utc"))
    except PublicationPolicyError as exc:
        reasons.append(str(exc))
    return reasons


def build_publication_intent(
    *,
    snapshot: Mapping[str, Any],
    snapshot_path: str,
    snapshot_sha256: str,
    snapshot_commit_sha: str,
    main_base_sha: str,
    source_workflow_id: int,
    source_workflow_run_id: int,
    source_workflow_run_attempt: int,
    source_workflow_head_sha: str,
    quality: Mapping[str, Any],
) -> dict[str, Any]:
    run = as_dict(snapshot.get("run"))
    base = require_sha1(main_base_sha, "main_base_sha")
    source_head = require_sha1(
        source_workflow_head_sha, "source_workflow_head_sha"
    )
    if source_head != base:
        raise PublicationPolicyError(
            "trusted source workflow head must equal main_base_sha"
        )
    if not safe_repo_path(snapshot_path, "data/crypto/hourly/", ".json"):
        raise PublicationPolicyError(
            "snapshot_path is outside data/crypto/hourly"
        )
    if min(
        int(source_workflow_id),
        int(source_workflow_run_id),
        int(source_workflow_run_attempt),
    ) <= 0:
        raise PublicationPolicyError("source workflow identity must be positive")

    reasons = quality_reasons(snapshot, quality)
    hour = str(run.get("observation_hour_utc", ""))
    compact = ""
    try:
        compact = compact_observation_hour(hour)
    except PublicationPolicyError:
        pass

    return {
        "publication_contract": CONTRACT,
        "source_workflow_id": int(source_workflow_id),
        "source_workflow_path": EXPECTED_SOURCE_WORKFLOW_PATH,
        "source_workflow_run_id": int(source_workflow_run_id),
        "source_workflow_run_attempt": int(source_workflow_run_attempt),
        "source_workflow_head_sha": source_head,
        "main_base_sha": base,
        "snapshot_commit_sha": require_sha1(
            snapshot_commit_sha, "snapshot_commit_sha"
        ),
        "snapshot_path": snapshot_path,
        "snapshot_sha256": require_sha256(snapshot_sha256, "snapshot_sha256"),
        "generated_at_utc": str(run.get("generated_at_utc", "")),
        "observation_hour_utc": hour,
        "observation_hour_compact": compact,
        "snapshot_quality": str(quality.get("status", "")),
        "blocking_issues": strings(quality.get("blocking_issues")),
        "non_blocking_warnings": strings(
            quality.get("non_blocking_warnings")
        ),
        "warnings": strings(snapshot.get("warnings")),
        "errors": strings(snapshot.get("errors")),
        "automatic_eligible": not reasons,
        "refusal_reasons": reasons,
    }


def verify_publication_intent(
    intent: Mapping[str, Any],
    snapshot_bytes: bytes,
    *,
    expected_main_base_sha: str | None = None,
    expected_source_workflow_id: int | None = None,
    expected_source_run_id: int | None = None,
    expected_source_run_attempt: int | None = None,
) -> None:
    if intent.get("publication_contract") != CONTRACT:
        raise PublicationPolicyError("intent contract mismatch")
    if intent.get("source_workflow_path") != EXPECTED_SOURCE_WORKFLOW_PATH:
        raise PublicationPolicyError("intent source workflow mismatch")

    base = require_sha1(intent.get("main_base_sha"), "main_base_sha")
    source_head = require_sha1(
        intent.get("source_workflow_head_sha"), "source_workflow_head_sha"
    )
    if source_head != base:
        raise PublicationPolicyError("intent source head/base mismatch")
    if expected_main_base_sha and base != require_sha1(
        expected_main_base_sha, "expected_main_base_sha"
    ):
        raise PublicationPolicyError(
            "intent does not match the publication-generation trusted main base"
        )

    require_sha1(intent.get("snapshot_commit_sha"), "snapshot_commit_sha")
    if sha256_bytes(snapshot_bytes) != require_sha256(
        intent.get("snapshot_sha256"), "snapshot_sha256"
    ):
        raise PublicationPolicyError(
            "snapshot bytes do not match immutable source intent"
        )
    if not safe_repo_path(
        intent.get("snapshot_path"), "data/crypto/hourly/", ".json"
    ):
        raise PublicationPolicyError("intent snapshot path is invalid")
    parse_utc_hour(intent.get("observation_hour_utc"))

    ids = {
        "source_workflow_id": int(intent.get("source_workflow_id", 0)),
        "source_workflow_run_id": int(intent.get("source_workflow_run_id", 0)),
        "source_workflow_run_attempt": int(
            intent.get("source_workflow_run_attempt", 0)
        ),
    }
    if min(ids.values()) <= 0:
        raise PublicationPolicyError("intent source identity is invalid")
    expected = {
        "source_workflow_id": expected_source_workflow_id,
        "source_workflow_run_id": expected_source_run_id,
        "source_workflow_run_attempt": expected_source_run_attempt,
    }
    for field, value in expected.items():
        if value is not None and ids[field] != int(value):
            raise PublicationPolicyError(
                f"intent {field} does not match triggering source run"
            )


def build_attestation(
    *,
    intent: Mapping[str, Any],
    report_path: str,
    report_sha256: str,
    generation_workflow_id: int,
    generation_workflow_run_id: int,
    generation_workflow_run_attempt: int,
    generation_workflow_head_sha: str,
    candidate_branch: str,
    candidate_head_sha: str,
    pull_request_number: int,
    publication_app_actor_id: int,
    publication_app_slug: str,
) -> dict[str, Any]:
    if not intent.get("automatic_eligible"):
        raise PublicationPolicyError(
            "cannot attest an ineligible publication intent"
        )
    base = require_sha1(intent.get("main_base_sha"), "main_base_sha")
    generation_head = require_sha1(
        generation_workflow_head_sha, "generation_workflow_head_sha"
    )
    if generation_head != base:
        raise PublicationPolicyError(
            "publication-generation workflow head must equal main_base_sha"
        )
    if min(
        int(generation_workflow_id),
        int(generation_workflow_run_id),
        int(generation_workflow_run_attempt),
    ) <= 0:
        raise PublicationPolicyError(
            "publication-generation workflow identity must be positive"
        )

    expected_branch = publication_branch(
        generation_workflow_run_id,
        generation_workflow_run_attempt,
        str(intent.get("observation_hour_utc", "")),
    )
    if candidate_branch != expected_branch:
        raise PublicationPolicyError(
            "candidate branch does not match trusted generation run/attempt/hour identity"
        )
    if int(pull_request_number) <= 0 or int(publication_app_actor_id) <= 0:
        raise PublicationPolicyError("PR/App identity must be positive")
    slug = str(publication_app_slug or "").strip()
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", slug):
        raise PublicationPolicyError("publication App slug is invalid")

    result = {
        "publication_contract": CONTRACT,
        "generation_workflow_id": int(generation_workflow_id),
        "generation_workflow_path": EXPECTED_GENERATION_WORKFLOW_PATH,
        "generation_workflow_run_id": int(generation_workflow_run_id),
        "generation_workflow_run_attempt": int(
            generation_workflow_run_attempt
        ),
        "generation_workflow_head_sha": generation_head,
        "main_base_sha": base,
        "source_workflow_id": int(intent["source_workflow_id"]),
        "source_workflow_run_id": int(intent["source_workflow_run_id"]),
        "source_workflow_run_attempt": int(
            intent["source_workflow_run_attempt"]
        ),
        "source_workflow_head_sha": require_sha1(
            intent["source_workflow_head_sha"], "source_workflow_head_sha"
        ),
        "observation_hour_utc": intent["observation_hour_utc"],
        "snapshot_commit_sha": require_sha1(
            intent["snapshot_commit_sha"], "snapshot_commit_sha"
        ),
        "snapshot_path": intent["snapshot_path"],
        "snapshot_sha256": require_sha256(
            intent["snapshot_sha256"], "snapshot_sha256"
        ),
        "snapshot_quality": intent["snapshot_quality"],
        "blocking_issues": strings(intent.get("blocking_issues")),
        "non_blocking_warnings": strings(
            intent.get("non_blocking_warnings")
        ),
        "warnings": strings(intent.get("warnings")),
        "errors": strings(intent.get("errors")),
        "report_path": report_path,
        "report_sha256": require_sha256(report_sha256, "report_sha256"),
        "candidate_branch": candidate_branch,
        "candidate_head_sha": require_sha1(
            candidate_head_sha, "candidate_head_sha"
        ),
        "pull_request_number": int(pull_request_number),
        "publication_app_actor_id": int(publication_app_actor_id),
        "publication_app_slug": slug,
        "publication_intent_sha256": canonical_json_sha256(intent),
    }
    validate_attestation_shape(result)
    return result


def validate_attestation_shape(attestation: Mapping[str, Any]) -> None:
    if attestation.get("publication_contract") != CONTRACT:
        raise PublicationPolicyError("attestation contract mismatch")
    if (
        attestation.get("generation_workflow_path")
        != EXPECTED_GENERATION_WORKFLOW_PATH
    ):
        raise PublicationPolicyError("attestation generation workflow mismatch")

    base = require_sha1(attestation.get("main_base_sha"), "main_base_sha")
    generation_head = require_sha1(
        attestation.get("generation_workflow_head_sha"),
        "generation_workflow_head_sha",
    )
    if generation_head != base:
        raise PublicationPolicyError("attestation generation head/base mismatch")
    if require_sha1(
        attestation.get("source_workflow_head_sha"), "source_workflow_head_sha"
    ) != base:
        raise PublicationPolicyError("attestation source head/base mismatch")

    for field in ("snapshot_commit_sha", "candidate_head_sha"):
        require_sha1(attestation.get(field), field)
    for field in ("snapshot_sha256", "report_sha256"):
        require_sha256(attestation.get(field), field)

    validate_candidate_scope(
        [attestation.get("snapshot_path"), attestation.get("report_path")],
        str(attestation.get("snapshot_path", "")),
        str(attestation.get("report_path", "")),
    )
    identity = parse_publication_branch(
        str(attestation.get("candidate_branch", ""))
    )
    for field in (
        "generation_workflow_run_id",
        "generation_workflow_run_attempt",
    ):
        if int(attestation.get(field, 0)) != int(identity[field]):
            raise PublicationPolicyError(
                f"attestation {field} does not match candidate branch"
            )
    if (
        attestation.get("observation_hour_utc")
        != identity["observation_hour_utc"]
    ):
        raise PublicationPolicyError(
            "attestation observation hour does not match candidate branch"
        )

    positive_fields = (
        "generation_workflow_id",
        "generation_workflow_run_id",
        "generation_workflow_run_attempt",
        "source_workflow_id",
        "source_workflow_run_id",
        "source_workflow_run_attempt",
        "pull_request_number",
        "publication_app_actor_id",
    )
    if min(int(attestation.get(field, 0)) for field in positive_fields) <= 0:
        raise PublicationPolicyError(
            "attestation workflow/source/PR/App identity is invalid"
        )
    if not str(attestation.get("publication_app_slug", "")):
        raise PublicationPolicyError("attestation App slug is missing")


def evaluate_gate(
    attestation: Mapping[str, Any], facts: Mapping[str, Any]
) -> GateDecision:
    try:
        validate_attestation_shape(attestation)
    except PublicationPolicyError as exc:
        return GateDecision(False, (str(exc),))

    reasons: list[str] = []
    run = as_dict(facts.get("generation_run"))
    pr = as_dict(facts.get("pr"))
    validation = as_dict(facts.get("validation"))
    snapshot = as_dict(facts.get("snapshot"))
    report = as_dict(facts.get("report"))

    def deny(test: bool, text: str) -> None:
        if test:
            reasons.append(text)

    deny(
        int(facts.get("attestation_count", 0)) != 1,
        "expected exactly one immutable attestation artifact",
    )
    deny(
        bool(facts.get("attestation_expired")),
        "immutable attestation artifact is expired",
    )
    deny(
        int(run.get("id", 0))
        != int(attestation["generation_workflow_run_id"]),
        "generation run id mismatch",
    )
    deny(
        int(run.get("run_attempt", 0))
        != int(attestation["generation_workflow_run_attempt"]),
        "generation run attempt mismatch",
    )
    deny(
        int(run.get("workflow_id", 0))
        != int(attestation["generation_workflow_id"]),
        "generation workflow id mismatch",
    )
    deny(
        run.get("path") != EXPECTED_GENERATION_WORKFLOW_PATH,
        "generation workflow path mismatch",
    )
    deny(
        run.get("head_branch") != "main",
        "generation workflow did not run on the default branch",
    )
    deny(
        run.get("event") != "workflow_run",
        "generation workflow event is not trusted",
    )
    deny(
        run.get("head_sha") != attestation["main_base_sha"],
        "generation workflow head/base mismatch",
    )
    deny(
        run.get("conclusion") != "success",
        "generation workflow did not succeed",
    )

    deny(not pr.get("open"), "publication PR is not open")
    deny(bool(pr.get("draft")), "publication PR is draft")
    deny(
        not pr.get("same_repository"),
        "publication PR is not same-repository",
    )
    deny(pr.get("base") != "main", "publication PR base is not main")
    deny(
        int(pr.get("number", 0)) != int(attestation["pull_request_number"]),
        "publication PR number mismatch",
    )
    deny(
        pr.get("head_ref") != attestation["candidate_branch"],
        "publication PR branch mismatch",
    )
    deny(
        pr.get("head_sha") != attestation["candidate_head_sha"],
        "publication PR head changed after trusted generation",
    )
    deny(
        int(pr.get("author_id", 0))
        != int(attestation["publication_app_actor_id"]),
        "publication PR App actor id mismatch",
    )
    deny(
        pr.get("author_login")
        != f"{attestation['publication_app_slug']}[bot]",
        "publication PR App actor login mismatch",
    )

    deny(
        validation.get("workflow_name") != EXPECTED_VALIDATION_WORKFLOW,
        "validation workflow identity mismatch",
    )
    deny(
        validation.get("conclusion") != "success",
        "exact-head PR validation did not succeed",
    )
    deny(
        validation.get("head_sha") != attestation["candidate_head_sha"],
        "validated head does not match attested candidate",
    )
    deny(
        validation.get("check_name") != EXPECTED_VALIDATION_CHECK,
        "required validation check name mismatch",
    )
    deny(
        validation.get("check_conclusion") != "success",
        "required validation check did not succeed",
    )
    deny(
        validation.get("check_app_slug") != EXPECTED_VALIDATION_APP,
        "required validation check source mismatch",
    )
    deny(
        int(validation.get("pending_required_checks", 0)) != 0,
        "required validation check remains pending",
    )
    deny(
        int(validation.get("failed_required_checks", 0)) != 0,
        "required validation check failed",
    )

    try:
        validate_candidate_scope(
            facts.get("changed_files", []),
            str(attestation["snapshot_path"]),
            str(attestation["report_path"]),
        )
    except PublicationPolicyError as exc:
        reasons.append(str(exc))

    deny(
        snapshot.get("path") != attestation["snapshot_path"],
        "snapshot path mismatch",
    )
    deny(
        snapshot.get("sha256") != attestation["snapshot_sha256"],
        "snapshot hash mismatch",
    )
    deny(
        report.get("path") != attestation["report_path"],
        "report path mismatch",
    )
    deny(
        report.get("sha256") != attestation["report_sha256"],
        "report hash mismatch",
    )
    deny(
        snapshot.get("quality_status") != "valid-ok",
        "candidate snapshot quality is not valid-ok",
    )
    deny(
        bool(strings(snapshot.get("blocking_issues"))),
        "candidate snapshot has blocking issues",
    )
    deny(
        bool(strings(snapshot.get("non_blocking_warnings"))),
        "candidate snapshot has quality warnings",
    )
    deny(
        bool(strings(snapshot.get("warnings"))),
        "candidate snapshot records warnings",
    )
    deny(
        bool(strings(snapshot.get("errors"))),
        "candidate snapshot records errors",
    )
    try:
        parse_utc_hour(snapshot.get("observation_hour_utc"))
        deny(
            snapshot.get("observation_hour_utc")
            != attestation["observation_hour_utc"],
            "candidate snapshot observation hour mismatch",
        )
    except PublicationPolicyError as exc:
        reasons.append(str(exc))

    deny(
        facts.get("current_main_sha") != attestation["main_base_sha"],
        "current main advanced from attested base",
    )
    deny(
        int(facts.get("duplicate_publication_count", 0)) != 0,
        "observation hour is already published",
    )
    deny(
        int(facts.get("unresolved_threads", 0)) != 0,
        "publication PR has unresolved review threads",
    )
    deny(
        int(facts.get("blocking_reviews", 0)) != 0,
        "publication PR has blocking reviews",
    )

    state = normalise_activation(facts.get("activation"))
    deny(
        state == ACTIVATION_DISABLED,
        "deterministic publication activation is disabled",
    )
    deny(
        state == ACTIVATION_PILOT
        and str(attestation["source_workflow_run_id"])
        != str(facts.get("pilot_run_id", "")),
        "pilot activation is not bound to this source ingestion run",
    )

    return GateDecision(not reasons, tuple(dict.fromkeys(reasons)))


def count_observation_hour(root: Path, hour: str) -> int:
    parse_utc_hour(hour)
    count = 0
    for path in root.glob("data/crypto/hourly/**/*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if (
            isinstance(payload, dict)
            and as_dict(payload.get("run")).get("observation_hour_utc")
            == hour
        ):
            count += 1
    return count


def latest_validation(checks: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    found = [
        item
        for item in checks
        if item.get("name") == EXPECTED_VALIDATION_CHECK
        and as_dict(item.get("app")).get("slug") == EXPECTED_VALIDATION_APP
    ]
    if len(found) != 1:
        return {
            "check_name": EXPECTED_VALIDATION_CHECK,
            "check_conclusion": "missing-or-ambiguous",
            "check_app_slug": EXPECTED_VALIDATION_APP,
            "pending_required_checks": int(not found),
            "failed_required_checks": int(len(found) > 1),
        }
    check = found[0]
    return {
        "check_name": check.get("name"),
        "check_conclusion": check.get("conclusion"),
        "check_app_slug": as_dict(check.get("app")).get("slug"),
        "pending_required_checks": int(check.get("status") != "completed"),
        "failed_required_checks": int(
            check.get("status") == "completed"
            and check.get("conclusion") != "success"
        ),
    }


def normalise_gate_facts(
    *,
    attestation: Mapping[str, Any],
    pr_payload: Mapping[str, Any],
    generation_run_payload: Mapping[str, Any],
    validation_run_payload: Mapping[str, Any],
    check_runs_payload: Mapping[str, Any],
    reviews_payload: list[Any],
    threads_payload: Mapping[str, Any],
    main_payload: Mapping[str, Any],
    files_payload: list[Any],
    snapshot_bytes: bytes,
    report_bytes: bytes,
    snapshot_payload: Mapping[str, Any],
    root: Path,
    activation: str,
    pilot_run_id: str,
    attestation_count: int,
    attestation_expired: bool,
) -> dict[str, Any]:
    user = as_dict(pr_payload.get("user"))
    head = as_dict(pr_payload.get("head"))
    base = as_dict(pr_payload.get("base"))

    try:
        sys.path.insert(0, str((root / "scripts").resolve()))
        from validate_crypto_snapshot import (  # type: ignore
            classify_snapshot_quality,
            load_config,
        )

        quality = classify_snapshot_quality(
            dict(snapshot_payload),
            load_config(root / "config" / "crypto_sources.yml"),
        )
    except Exception as exc:  # trusted reconstruction fails closed
        quality = {
            "status": "invalid",
            "blocking_issues": [
                f"trusted quality reconstruction failed: {exc}"
            ],
            "non_blocking_warnings": [],
        }

    review_threads = as_list(
        as_dict(
            as_dict(
                as_dict(
                    as_dict(threads_payload.get("data")).get("repository")
                ).get("pullRequest")
            ).get("reviewThreads")
        ).get("nodes")
    )
    checks = [
        item
        for item in as_list(check_runs_payload.get("check_runs"))
        if isinstance(item, dict)
    ]

    return {
        "attestation_count": int(attestation_count),
        "attestation_expired": bool(attestation_expired),
        "generation_run": {
            key: generation_run_payload.get(key)
            for key in (
                "id",
                "run_attempt",
                "workflow_id",
                "path",
                "head_branch",
                "event",
                "head_sha",
                "conclusion",
            )
        },
        "pr": {
            "number": pr_payload.get("number"),
            "open": pr_payload.get("state") == "open",
            "draft": bool(pr_payload.get("draft")),
            "same_repository": as_dict(head.get("repo")).get("id")
            == as_dict(base.get("repo")).get("id"),
            "base": base.get("ref"),
            "head_ref": head.get("ref"),
            "head_sha": head.get("sha"),
            "author_id": user.get("id"),
            "author_login": user.get("login"),
        },
        "validation": {
            "workflow_name": validation_run_payload.get("name"),
            "conclusion": validation_run_payload.get("conclusion"),
            "head_sha": validation_run_payload.get("head_sha"),
            **latest_validation(checks),
        },
        "changed_files": [
            item.get("filename", "")
            for item in files_payload
            if isinstance(item, dict)
        ],
        "snapshot": {
            "path": attestation.get("snapshot_path"),
            "sha256": sha256_bytes(snapshot_bytes),
            "quality_status": quality.get("status"),
            "blocking_issues": strings(quality.get("blocking_issues")),
            "non_blocking_warnings": strings(
                quality.get("non_blocking_warnings")
            ),
            "warnings": strings(snapshot_payload.get("warnings")),
            "errors": strings(snapshot_payload.get("errors")),
            "observation_hour_utc": as_dict(snapshot_payload.get("run")).get(
                "observation_hour_utc"
            ),
        },
        "report": {
            "path": attestation.get("report_path"),
            "sha256": sha256_bytes(report_bytes),
        },
        "current_main_sha": main_payload.get("sha"),
        "duplicate_publication_count": count_observation_hour(
            root, str(attestation.get("observation_hour_utc", ""))
        ),
        "unresolved_threads": sum(
            1
            for item in review_threads
            if isinstance(item, dict) and not item.get("isResolved")
        ),
        "blocking_reviews": sum(
            1
            for item in reviews_payload
            if isinstance(item, dict)
            and str(item.get("state", "")).upper()
            in {"CHANGES_REQUESTED", "REQUEST_CHANGES"}
        ),
        "activation": normalise_activation(activation),
        "pilot_run_id": str(pilot_run_id or ""),
    }


def github_output(path: str | None, values: Mapping[str, Any]) -> None:
    if not path:
        return
    with Path(path).open("a", encoding="utf-8") as handle:
        for key, value in values.items():
            rendered = str(value).lower() if isinstance(value, bool) else value
            handle.write(f"{key}={rendered}\n")


def command_build_intent(args: argparse.Namespace) -> int:
    snapshot_path = Path(args.snapshot)
    snapshot = load_json(snapshot_path)
    sys.path.insert(0, str(Path("scripts").resolve()))
    from validate_crypto_snapshot import (  # type: ignore
        classify_snapshot_quality,
        load_config,
    )

    intent = build_publication_intent(
        snapshot=snapshot,
        snapshot_path=args.snapshot,
        snapshot_sha256=sha256_file(snapshot_path),
        snapshot_commit_sha=args.snapshot_commit_sha,
        main_base_sha=args.main_base_sha,
        source_workflow_id=args.source_workflow_id,
        source_workflow_run_id=args.source_run_id,
        source_workflow_run_attempt=args.source_run_attempt,
        source_workflow_head_sha=args.source_workflow_head_sha,
        quality=classify_snapshot_quality(
            snapshot, load_config(Path(args.config))
        ),
    )
    write_json(Path(args.output), intent)
    github_output(
        args.github_output,
        {
            "publication_eligible": bool(intent["automatic_eligible"]),
            "observation_hour_compact": intent["observation_hour_compact"],
            "observation_hour_utc": intent["observation_hour_utc"],
            "snapshot_path": intent["snapshot_path"],
        },
    )
    return 0


def command_verify_intent(args: argparse.Namespace) -> int:
    intent = load_json(Path(args.intent))
    snapshot_bytes = Path(args.snapshot).read_bytes()
    verify_publication_intent(
        intent,
        snapshot_bytes,
        expected_main_base_sha=args.expected_main_base_sha,
        expected_source_workflow_id=args.expected_source_workflow_id,
        expected_source_run_id=args.expected_source_run_id,
        expected_source_run_attempt=args.expected_source_run_attempt,
    )
    if not intent.get("automatic_eligible"):
        raise PublicationPolicyError(
            "publication source intent is not automatically eligible"
        )
    target = Path(str(intent["snapshot_path"]))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(snapshot_bytes)
    github_output(
        args.github_output,
        {
            "snapshot_path": target.as_posix(),
            "observation_hour_utc": intent["observation_hour_utc"],
            "observation_hour_compact": intent["observation_hour_compact"],
            "main_base_sha": intent["main_base_sha"],
            "source_workflow_run_id": intent["source_workflow_run_id"],
        },
    )
    return 0


def command_validate_scope(args: argparse.Namespace) -> int:
    paths = [
        line.strip()
        for line in Path(args.changed_files).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    validate_candidate_scope(paths, args.snapshot_path, args.report_path)
    return 0


def command_build_attestation(args: argparse.Namespace) -> int:
    intent = load_json(Path(args.intent))
    value = build_attestation(
        intent=intent,
        report_path=args.report_path,
        report_sha256=sha256_file(Path(args.report_path)),
        generation_workflow_id=args.generation_workflow_id,
        generation_workflow_run_id=args.generation_run_id,
        generation_workflow_run_attempt=args.run_attempt,
        generation_workflow_head_sha=args.generation_workflow_head_sha,
        candidate_branch=args.candidate_branch,
        candidate_head_sha=args.candidate_head_sha,
        pull_request_number=args.pull_request_number,
        publication_app_actor_id=args.publication_app_actor_id,
        publication_app_slug=args.publication_app_slug,
    )
    write_json(Path(args.output), value)
    return 0


def command_branch_identity(args: argparse.Namespace) -> int:
    value = parse_publication_branch(args.branch)
    github_output(args.github_output, value)
    print(json.dumps(value, sort_keys=True))
    return 0


def command_validate_attestation(args: argparse.Namespace) -> int:
    value = load_json(Path(args.attestation))
    validate_attestation_shape(value)
    github_output(
        args.github_output,
        {
            key: value[key]
            for key in (
                "snapshot_path",
                "report_path",
                "candidate_head_sha",
                "pull_request_number",
                "observation_hour_utc",
            )
        },
    )
    return 0


def command_assert_unpublished(args: argparse.Namespace) -> int:
    count = count_observation_hour(Path(args.root), args.observation_hour_utc)
    if count:
        raise PublicationPolicyError(
            f"observation hour is already published: {count} matching snapshot(s)"
        )
    return 0


def command_build_gate_facts(args: argparse.Namespace) -> int:
    attestation = load_json(Path(args.attestation))
    validate_attestation_shape(attestation)
    reviews = json.loads(Path(args.reviews_json).read_text(encoding="utf-8"))
    files = json.loads(Path(args.files_json).read_text(encoding="utf-8"))
    if not isinstance(reviews, list) or not isinstance(files, list):
        raise PublicationPolicyError(
            "reviews/files API payload must be arrays"
        )
    facts = normalise_gate_facts(
        attestation=attestation,
        pr_payload=load_json(Path(args.pr_json)),
        generation_run_payload=load_json(Path(args.generation_run_json)),
        validation_run_payload=load_json(Path(args.validation_run_json)),
        check_runs_payload=load_json(Path(args.check_runs_json)),
        reviews_payload=reviews,
        threads_payload=load_json(Path(args.threads_json)),
        main_payload=load_json(Path(args.main_json)),
        files_payload=files,
        snapshot_bytes=Path(args.snapshot_file).read_bytes(),
        report_bytes=Path(args.report_file).read_bytes(),
        snapshot_payload=load_json(Path(args.snapshot_file)),
        root=Path(args.main_root),
        activation=args.activation,
        pilot_run_id=args.pilot_run_id,
        attestation_count=args.attestation_count,
        attestation_expired=args.attestation_expired,
    )
    write_json(Path(args.output), facts)
    return 0


def command_gate(args: argparse.Namespace) -> int:
    decision = evaluate_gate(
        load_json(Path(args.attestation)), load_json(Path(args.facts))
    )
    if args.output:
        write_json(Path(args.output), decision.as_dict())
    github_output(args.github_output, {"eligible": decision.eligible})
    print(json.dumps(decision.as_dict(), indent=2, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("build-intent")
    for name in (
        "snapshot",
        "snapshot-commit-sha",
        "main-base-sha",
        "source-workflow-head-sha",
        "output",
    ):
        p.add_argument(f"--{name}", required=True)
    p.add_argument("--config", default="config/crypto_sources.yml")
    p.add_argument("--source-workflow-id", type=int, required=True)
    p.add_argument("--source-run-id", type=int, required=True)
    p.add_argument("--source-run-attempt", type=int, required=True)
    p.add_argument("--github-output")
    p.set_defaults(func=command_build_intent)

    p = sub.add_parser("verify-intent")
    p.add_argument("--intent", required=True)
    p.add_argument("--snapshot", required=True)
    p.add_argument("--expected-main-base-sha", required=True)
    p.add_argument("--expected-source-workflow-id", type=int, required=True)
    p.add_argument("--expected-source-run-id", type=int, required=True)
    p.add_argument("--expected-source-run-attempt", type=int, required=True)
    p.add_argument("--github-output")
    p.set_defaults(func=command_verify_intent)

    p = sub.add_parser("validate-scope")
    p.add_argument("--changed-files", required=True)
    p.add_argument("--snapshot-path", required=True)
    p.add_argument("--report-path", required=True)
    p.set_defaults(func=command_validate_scope)

    p = sub.add_parser("build-attestation")
    for name in (
        "intent",
        "report-path",
        "generation-workflow-head-sha",
        "candidate-branch",
        "candidate-head-sha",
        "publication-app-slug",
        "output",
    ):
        p.add_argument(f"--{name}", required=True)
    p.add_argument("--generation-workflow-id", type=int, required=True)
    p.add_argument("--generation-run-id", type=int, required=True)
    p.add_argument("--run-attempt", type=int, required=True)
    p.add_argument("--pull-request-number", type=int, required=True)
    p.add_argument("--publication-app-actor-id", type=int, required=True)
    p.set_defaults(func=command_build_attestation)

    p = sub.add_parser("branch-identity")
    p.add_argument("--branch", required=True)
    p.add_argument("--github-output")
    p.set_defaults(func=command_branch_identity)

    p = sub.add_parser("validate-attestation")
    p.add_argument("--attestation", required=True)
    p.add_argument("--github-output")
    p.set_defaults(func=command_validate_attestation)

    p = sub.add_parser("assert-unpublished-hour")
    p.add_argument("--root", default=".")
    p.add_argument("--observation-hour-utc", required=True)
    p.set_defaults(func=command_assert_unpublished)

    p = sub.add_parser("build-gate-facts")
    for name in (
        "attestation",
        "pr-json",
        "generation-run-json",
        "validation-run-json",
        "check-runs-json",
        "reviews-json",
        "threads-json",
        "main-json",
        "files-json",
        "snapshot-file",
        "report-file",
        "output",
    ):
        p.add_argument(f"--{name}", required=True)
    p.add_argument("--main-root", default=".")
    p.add_argument("--activation", default=ACTIVATION_DISABLED)
    p.add_argument("--pilot-run-id", default="")
    p.add_argument("--attestation-count", type=int, required=True)
    p.add_argument("--attestation-expired", action="store_true")
    p.set_defaults(func=command_build_gate_facts)

    p = sub.add_parser("gate")
    p.add_argument("--attestation", required=True)
    p.add_argument("--facts", required=True)
    p.add_argument("--output")
    p.add_argument("--github-output")
    p.set_defaults(func=command_gate)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except (PublicationPolicyError, OSError, ValueError) as exc:
        print(
            f"deterministic publication policy error: {exc}", file=sys.stderr
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
