#!/usr/bin/env python3
"""Verify a trusted ingestion run and, for external dispatch, its accepted-hour receipt.

Both publication generation and the protected-main merge gate run this check
against GitHub Actions metadata, not a rolling snapshot PR or PR body.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

SOURCE_WORKFLOW_PATH = ".github/workflows/ingest-crypto-sources.yml"
SOURCE_CONTRACT = "crypto-hour-ingestion/v1"
PUBLICATION_CONTRACT = "deterministic-site-publication/v3"
HOUR_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:00:00Z$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class ProvenanceError(ValueError):
    """The ingestion cannot authorise deterministic publication."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ProvenanceError(message)


def canonical_hour(value: object) -> datetime:
    require(isinstance(value, str) and HOUR_RE.fullmatch(value) is not None,
            "observation hour must be canonical UTC")
    try:
        result = datetime.strptime(value, "%Y-%m-%dT%H:00:00Z").replace(tzinfo=timezone.utc)
    except ValueError as exc:
        raise ProvenanceError("invalid observation hour") from exc
    require(result.strftime("%Y-%m-%dT%H:00:00Z") == value, "noncanonical observation hour")
    return result


def utc_timestamp(value: object) -> datetime:
    require(isinstance(value, str) and value.endswith("Z"), "timestamp must be UTC")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProvenanceError("invalid UTC timestamp") from exc
    require(result.utcoffset() == timedelta(0), "timestamp must have UTC offset")
    return result


def receipt_name(hour: datetime) -> str:
    return "crypto-hour-accepted-" + hour.strftime("%Y%m%dT%H")


def verify_source(
    source_run: Mapping[str, Any],
    evidence: Mapping[str, Any],
    *,
    receipt: Mapping[str, Any] | None,
    repository: str,
) -> str:
    """Return 'schedule' or 'workflow_dispatch', otherwise fail closed.

    Evidence is the v3 immutable source intent (generation) or its hash-bound
    v3 attestation (merge gate). Both identify the original source run and bytes.
    """
    require(re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository) is not None,
            "invalid repository identity")
    hour = canonical_hour(evidence.get("observation_hour_utc"))
    require(evidence.get("publication_contract") == PUBLICATION_CONTRACT,
            "unexpected deterministic publication contract")
    if "source_workflow_path" in evidence:
        require(evidence["source_workflow_path"] == SOURCE_WORKFLOW_PATH,
                "unexpected intent source workflow")
    require(type(evidence.get("source_workflow_run_id")) is int
            and evidence["source_workflow_run_id"] > 0, "invalid source run identity")
    require(type(evidence.get("source_workflow_run_attempt")) is int
            and evidence["source_workflow_run_attempt"] > 0, "invalid source run attempt")
    require(type(evidence.get("source_workflow_id")) is int
            and evidence["source_workflow_id"] > 0, "invalid source workflow ID")
    require(isinstance(evidence.get("snapshot_sha256"), str)
            and re.fullmatch(r"[0-9a-f]{64}", evidence["snapshot_sha256"]) is not None,
            "invalid snapshot digest")
    for name in ("main_base_sha", "source_workflow_head_sha", "snapshot_commit_sha"):
        require(isinstance(evidence.get(name), str)
                and SHA_RE.fullmatch(evidence[name]) is not None,
                f"invalid {name}")

    for field, expected in (
        ("id", evidence["source_workflow_run_id"]),
        ("run_attempt", evidence["source_workflow_run_attempt"]),
        ("workflow_id", evidence["source_workflow_id"]),
        ("path", SOURCE_WORKFLOW_PATH),
        ("head_sha", evidence["source_workflow_head_sha"]),
        ("head_branch", "main"),
        ("status", "completed"),
        ("conclusion", "success"),
    ):
        require(type(source_run.get(field)) is type(expected)
                and source_run.get(field) == expected,
                f"untrusted source run {field}")
    require(evidence["source_workflow_head_sha"] == evidence["main_base_sha"],
            "source run is not tied to attested main base")
    require(isinstance(source_run.get("repository"), dict)
            and source_run["repository"].get("full_name") == repository,
            "source run repository mismatch")

    event = source_run.get("event")
    require(event in ("schedule", "workflow_dispatch"), "unsupported source event")
    if event == "schedule":
        return event

    # GitHub dispatch alone is NOT sufficient: constrain the invoking identity
    # and verify the immutable receipt from this exact successful ingestion run.
    require(source_run["run_attempt"] == 1, "external ingestion retry is not publication authority")
    require(isinstance(source_run.get("actor"), dict)
            and source_run["actor"].get("login") == repository.split("/", 1)[0],
            "unexpected external dispatch actor")
    require(isinstance(receipt, dict), "missing accepted-hour ingestion receipt")
    corr = "cp-" + hour.strftime("%Y%m%d%H")
    artifact = receipt_name(hour)
    expected = {
        "contract_version": SOURCE_CONTRACT,
        "status": "accepted-on-artifact-upload",
        "source_event": "workflow_dispatch",
        "dispatch_correlation_id": corr,
        "intended_hour_utc": evidence["observation_hour_utc"],
        "run_id": source_run["id"],
        "run_attempt": source_run["run_attempt"],
        "quality_status": "valid-ok",
        "accepted_hour_artifact": artifact,
        "snapshot_sha256": evidence["snapshot_sha256"],
        "snapshot_commit_sha": evidence["snapshot_commit_sha"],
        "source_intent_artifact": (
            f"deterministic-publication-intent-{source_run['id']}-{source_run['run_attempt']}"
        ),
    }
    for field, value in expected.items():
        require(type(receipt.get(field)) is type(value)
                and receipt[field] == value,
                f"accepted-hour receipt {field} mismatch")
    require(receipt.get("rolling_pr_outcome") in ("success", "failure", "skipped"),
            "invalid rolling PR receipt outcome")
    start = hour + timedelta(minutes=7)
    end = hour + timedelta(minutes=30)
    created = utc_timestamp(source_run.get("created_at"))
    prepared = utc_timestamp(receipt.get("receipt_prepared_at_utc"))
    require(start <= created <= prepared < end,
            "dispatch/receipt timestamps outside authorised UTC-hour window")
    return event


def load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    require(isinstance(data, dict), "expected JSON object")
    return data


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest="action", required=True)
    name = sub.add_parser("receipt-name")
    name.add_argument("--hour", required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("--source-run", required=True, type=Path)
    verify.add_argument("--evidence", required=True, type=Path)
    verify.add_argument("--receipt", type=Path)
    verify.add_argument("--repository", required=True)
    args = p.parse_args()
    try:
        if args.action == "receipt-name":
            print(receipt_name(canonical_hour(args.hour)))
        else:
            result = verify_source(
                load_json(args.source_run),
                load_json(args.evidence),
                receipt=load_json(args.receipt) if args.receipt is not None else None,
                repository=args.repository,
            )
            print("SOURCE_PROVENANCE_PASS " + result)
    except (ProvenanceError, OSError, ValueError, TypeError) as exc:
        p.exit(1, f"Source ingestion provenance refused: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
