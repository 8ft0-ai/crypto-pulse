"""Pure contract logic for the reusable IssueOps workflow dispatcher."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

SCHEMA_VERSION = 2
REPOSITORY = "8ft0-ai/crypto-pulse"
REPOSITORY_ID = 1233729904
REPOSITORY_OWNER_ID = 130460431
ACTOR_LOGIN = "8ft0-ai"
ACTOR_USER_ID = 130460431
AUTHOR_ASSOCIATION = "OWNER"
DISPATCHER_WORKFLOW_PATH = ".github/workflows/issueops-workflow-dispatch.yml"
CONSUMPTION_MECHANISM = "execution_tag_v1"
PROVENANCE_MECHANISM = "dispatch_attestation_v1"
PREDICATE_TYPE = "https://github.com/8ft0-ai/crypto-pulse/issueops/dispatch-attestation/v1"
TARGET_REF_POLICY = "consumed_execution_tag_v1"
AUTHORISATION_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,48}$")
SHA40_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
RECORD_KEYS = frozenset(
    {
        "authorisation_id",
        "governing_issue",
        "command",
        "actor_login",
        "actor_user_id",
        "required_author_association",
        "target_workflow_id",
        "target_workflow_path",
        "target_ref_policy",
        "target_workflow_sha256",
        "fixed_inputs",
        "maximum_dispatch_attempts",
        "enabled",
        "not_before",
        "expires_at",
        "consumption_mechanism",
        "provenance_mechanism",
        "attestation_predicate_type",
        "dispatcher_workflow_path",
        "dispatcher_workflow_sha256",
        "execution_tag_ruleset_id",
        "execution_tag_ruleset_name",
        "purpose",
    }
)
SUBJECT_KEYS = (
    "repository",
    "repository_id",
    "repository_owner_id",
    "authorisation_id",
    "authorisation_sha",
    "authorisation_record_sha256",
    "triggering_issue",
    "triggering_comment_id",
    "triggering_comment_body_sha256",
    "actor_login",
    "actor_user_id",
    "required_author_association",
    "execution_ref",
    "dispatcher_workflow_path",
    "dispatcher_workflow_sha",
    "dispatcher_run_id",
    "dispatcher_run_attempt",
    "target_workflow_id",
    "target_workflow_path",
    "target_run_id",
    "target_ref",
    "target_sha",
)
PREDICATE_KEYS = SUBJECT_KEYS + ("target_event", "fixed_inputs_sha256")


class ContractError(ValueError):
    """Raised when dispatcher authority cannot be proven exactly."""


@dataclass(frozen=True)
class Resolution:
    record: dict[str, Any]
    source_sha: str
    record_sha256: str
    comment_body_sha256: str
    fixed_inputs_sha256: str
    execution_tag: str
    execution_ref: str


def canonical_json_bytes(value: Any) -> bytes:
    """Return the contract's stable UTF-8 JSON serialisation."""
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        + "\n"
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def _rfc3339(value: str | None, *, name: str) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ContractError(f"{name} must be RFC3339 text or null")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ContractError(f"{name} is not valid RFC3339") from exc
    if parsed.tzinfo is None:
        raise ContractError(f"{name} must include a timezone")
    return parsed.astimezone(timezone.utc)


def _validate_fixed_inputs(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContractError("fixed_inputs must be an object")
    for key, item in value.items():
        if not isinstance(key, str) or not key:
            raise ContractError("fixed_inputs keys must be non-empty strings")
        if item is not None and not isinstance(item, (str, int, float, bool)):
            raise ContractError("fixed_inputs values must be JSON scalars")
    return dict(value)


def validate_record(record: Mapping[str, Any], *, now: datetime) -> dict[str, Any]:
    if set(record) != RECORD_KEYS:
        missing = sorted(RECORD_KEYS - set(record))
        extra = sorted(set(record) - RECORD_KEYS)
        raise ContractError(f"authorisation schema mismatch missing={missing} extra={extra}")
    item = dict(record)
    auth_id = item["authorisation_id"]
    if not isinstance(auth_id, str) or not AUTHORISATION_ID_RE.fullmatch(auth_id):
        raise ContractError("invalid authorisation_id")
    if not isinstance(item["governing_issue"], int) or item["governing_issue"] <= 0:
        raise ContractError("governing_issue must be a positive integer")
    if not isinstance(item["command"], str) or not item["command"]:
        raise ContractError("command must be non-empty exact text")
    if item["actor_login"] != ACTOR_LOGIN or item["actor_user_id"] != ACTOR_USER_ID:
        raise ContractError("actor identity is not the frozen repository owner")
    if item["required_author_association"] != AUTHOR_ASSOCIATION:
        raise ContractError("required_author_association must be OWNER")
    if not isinstance(item["target_workflow_id"], int) or item["target_workflow_id"] <= 0:
        raise ContractError("target_workflow_id must be positive")
    if not isinstance(item["target_workflow_path"], str) or not item["target_workflow_path"].startswith(".github/workflows/"):
        raise ContractError("target_workflow_path must be an exact workflow path")
    if item["target_ref_policy"] != TARGET_REF_POLICY:
        raise ContractError("unsupported target_ref_policy")
    if not isinstance(item["target_workflow_sha256"], str) or not SHA256_RE.fullmatch(item["target_workflow_sha256"]):
        raise ContractError("target_workflow_sha256 must be lowercase SHA-256")
    item["fixed_inputs"] = _validate_fixed_inputs(item["fixed_inputs"])
    if item["maximum_dispatch_attempts"] != 1:
        raise ContractError("maximum_dispatch_attempts must equal 1")
    if not isinstance(item["enabled"], bool):
        raise ContractError("enabled must be boolean")
    _rfc3339(item["not_before"], name="not_before")
    _rfc3339(item["expires_at"], name="expires_at")
    if item["consumption_mechanism"] != CONSUMPTION_MECHANISM:
        raise ContractError("unsupported consumption_mechanism")
    if item["provenance_mechanism"] != PROVENANCE_MECHANISM:
        raise ContractError("unsupported provenance_mechanism")
    if item["attestation_predicate_type"] != PREDICATE_TYPE:
        raise ContractError("unexpected attestation_predicate_type")
    if item["dispatcher_workflow_path"] != DISPATCHER_WORKFLOW_PATH:
        raise ContractError("unexpected dispatcher_workflow_path")
    if not isinstance(item["dispatcher_workflow_sha256"], str) or not SHA256_RE.fullmatch(item["dispatcher_workflow_sha256"]):
        raise ContractError("dispatcher_workflow_sha256 must be lowercase SHA-256")
    if not isinstance(item["execution_tag_ruleset_id"], int) or item["execution_tag_ruleset_id"] <= 0:
        raise ContractError("execution_tag_ruleset_id must be positive")
    if not isinstance(item["execution_tag_ruleset_name"], str) or not item["execution_tag_ruleset_name"]:
        raise ContractError("execution_tag_ruleset_name must be non-empty")
    if not isinstance(item["purpose"], str) or not item["purpose"]:
        raise ContractError("purpose must be non-empty")
    return item


def validate_registry(registry: Mapping[str, Any], *, now: datetime) -> list[dict[str, Any]]:
    if set(registry) != {"schema_version", "authorisations"}:
        raise ContractError("registry must contain exactly schema_version and authorisations")
    if registry["schema_version"] != SCHEMA_VERSION:
        raise ContractError("unsupported registry schema_version")
    records = registry["authorisations"]
    if not isinstance(records, list):
        raise ContractError("authorisations must be a list")
    validated = [validate_record(record, now=now) for record in records]
    ids = [record["authorisation_id"] for record in validated]
    if len(ids) != len(set(ids)):
        raise ContractError("authorisation_id values must be unique")
    return validated


def resolve_event(
    *,
    event: Mapping[str, Any],
    registry: Mapping[str, Any],
    source_sha: str,
    dispatcher_workflow_bytes: bytes,
    run_attempt: int,
    now: datetime,
) -> Resolution | None:
    if run_attempt != 1:
        raise ContractError("dispatcher reruns may not perform side effects")
    if event.get("action") != "created":
        return None
    issue = event.get("issue")
    comment = event.get("comment")
    if not isinstance(issue, Mapping) or not isinstance(comment, Mapping):
        raise ContractError("malformed issue_comment event")
    if issue.get("pull_request") is not None:
        return None
    if not SHA40_RE.fullmatch(source_sha):
        raise ContractError("created-event github.sha must be a full lowercase commit SHA")
    records = validate_registry(registry, now=now)
    now_utc = now.astimezone(timezone.utc)

    def active(record: Mapping[str, Any]) -> bool:
        if not record["enabled"]:
            return False
        not_before = _rfc3339(record["not_before"], name="not_before")
        expires_at = _rfc3339(record["expires_at"], name="expires_at")
        return (not_before is None or now_utc >= not_before) and (
            expires_at is None or now_utc < expires_at
        )

    matches = [
        record
        for record in records
        if active(record)
        and record["governing_issue"] == issue.get("number")
        and record["command"] == comment.get("body")
        and record["actor_login"] == (comment.get("user") or {}).get("login")
        and record["actor_user_id"] == (comment.get("user") or {}).get("id")
        and record["required_author_association"] == comment.get("author_association")
    ]
    if not matches:
        return None
    if len(matches) != 1:
        raise ContractError("created comment resolves to more than one authorisation")
    record = matches[0]
    workflow_hash = sha256_bytes(dispatcher_workflow_bytes)
    if workflow_hash != record["dispatcher_workflow_sha256"]:
        raise ContractError("dispatcher workflow hash does not match source-controlled authority")
    execution_tag = f"issueops/dispatch/{record['authorisation_id']}--sha-{source_sha}"
    execution_ref = f"refs/tags/{execution_tag}"
    return Resolution(
        record=record,
        source_sha=source_sha,
        record_sha256=sha256_bytes(canonical_json_bytes(record)),
        comment_body_sha256=sha256_text(str(comment["body"])),
        fixed_inputs_sha256=sha256_bytes(canonical_json_bytes(record["fixed_inputs"])),
        execution_tag=execution_tag,
        execution_ref=execution_ref,
    )


def ensure_comment_unchanged(event: Mapping[str, Any], live_comment: Mapping[str, Any], resolution: Resolution) -> None:
    comment = event["comment"]
    issue = event["issue"]
    if live_comment.get("id") != comment.get("id"):
        raise ContractError("triggering comment identity changed")
    if live_comment.get("body") != resolution.record["command"]:
        raise ContractError("triggering comment body changed")
    if live_comment.get("html_url") and f"/issues/{issue['number']}#" not in live_comment["html_url"]:
        raise ContractError("triggering comment moved outside the governing issue")
    user = live_comment.get("user") or {}
    if user.get("id") != ACTOR_USER_ID or user.get("login") != ACTOR_LOGIN:
        raise ContractError("triggering actor changed")
    if live_comment.get("author_association") != AUTHOR_ASSOCIATION:
        raise ContractError("triggering author association changed")
    if live_comment.get("created_at") != live_comment.get("updated_at"):
        raise ContractError("edited command cannot consume authority")


def canonical_subject(
    *,
    resolution: Resolution,
    event: Mapping[str, Any],
    dispatcher_run_id: int,
    dispatcher_run_attempt: int,
    target_run: Mapping[str, Any],
) -> dict[str, Any]:
    data = {
        "repository": REPOSITORY,
        "repository_id": REPOSITORY_ID,
        "repository_owner_id": REPOSITORY_OWNER_ID,
        "authorisation_id": resolution.record["authorisation_id"],
        "authorisation_sha": resolution.source_sha,
        "authorisation_record_sha256": resolution.record_sha256,
        "triggering_issue": resolution.record["governing_issue"],
        "triggering_comment_id": event["comment"]["id"],
        "triggering_comment_body_sha256": resolution.comment_body_sha256,
        "actor_login": ACTOR_LOGIN,
        "actor_user_id": ACTOR_USER_ID,
        "required_author_association": AUTHOR_ASSOCIATION,
        "execution_ref": resolution.execution_ref,
        "dispatcher_workflow_path": DISPATCHER_WORKFLOW_PATH,
        "dispatcher_workflow_sha": resolution.source_sha,
        "dispatcher_run_id": dispatcher_run_id,
        "dispatcher_run_attempt": dispatcher_run_attempt,
        "target_workflow_id": resolution.record["target_workflow_id"],
        "target_workflow_path": resolution.record["target_workflow_path"],
        "target_run_id": target_run["id"],
        "target_ref": resolution.execution_ref,
        "target_sha": resolution.source_sha,
    }
    if tuple(data) != SUBJECT_KEYS:
        raise AssertionError("canonical subject field order drift")
    return data


def canonical_predicate(subject: Mapping[str, Any], *, fixed_inputs_sha256: str) -> dict[str, Any]:
    data = dict(subject)
    data["target_event"] = "workflow_dispatch"
    data["fixed_inputs_sha256"] = fixed_inputs_sha256
    if tuple(data) != PREDICATE_KEYS:
        raise AssertionError("canonical predicate field order drift")
    return data
