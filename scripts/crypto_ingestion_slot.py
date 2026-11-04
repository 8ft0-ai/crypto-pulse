#!/usr/bin/env python3
"""Fail-closed UTC-hour acceptance for the existing crypto ingestion workflow.

The workflow's single, non-cancelling concurrency group serialises these checks
and the final receipt upload. An Actions artifact is the durable acceptance
marker; the rolling snapshot PR is never the acceptance authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from validate_crypto_observation_hour import validate_observation_hour
from validate_crypto_snapshot import ValidationError, load_config, parse_iso_timestamp

CONTRACT = "crypto-hour-ingestion/v1"
HOUR_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:00:00Z$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
MAX_LIST = 100


def canonical_hour(value: str) -> datetime:
    if HOUR_RE.fullmatch(value) is None:
        raise ValidationError("intended hour must use canonical YYYY-MM-DDTHH:00:00Z")
    result = datetime.strptime(value, "%Y-%m-%dT%H:00:00Z").replace(tzinfo=timezone.utc)
    if result.strftime("%Y-%m-%dT%H:00:00Z") != value:
        raise ValidationError("intended hour is not canonical")
    return result


def receipt_name(hour: datetime) -> str:
    return "crypto-hour-accepted-" + hour.strftime("%Y%m%dT%H")


def check_request(event: str, intended: str, correlation: str, now: datetime) -> datetime | None:
    if event == "schedule":
        if intended or correlation:
            raise ValidationError("scheduled ingestion cannot override its observation hour")
        return None
    if event != "workflow_dispatch":
        raise ValidationError("unsupported ingestion event")
    hour = canonical_hour(intended)
    if correlation != "cp-" + hour.strftime("%Y%m%d%H"):
        raise ValidationError("dispatch correlation does not match intended UTC hour")
    if not hour + timedelta(minutes=7) <= now < hour + timedelta(minutes=30):
        raise ValidationError("external ingestion outside the frozen :07–:30 UTC window")
    return hour


def inspect_snapshot(
    snapshot: Path, config: Path, event: str, intended: str,
    correlation: str, now: datetime,
) -> tuple[datetime, dict[str, str]]:
    requested_hour = check_request(event, intended, correlation, now)
    evidence = validate_observation_hour(snapshot, load_config(config))
    if evidence["quality_status"] != "valid-ok":
        raise ValidationError("only valid-ok source evidence may be accepted")
    actual_hour = canonical_hour(evidence["observation_hour_utc"])
    generated = parse_iso_timestamp(evidence["generated_at_utc"], "run.generated_at_utc")
    if generated > now + timedelta(seconds=60):
        raise ValidationError("snapshot timestamp is in the future")
    if requested_hour is not None and requested_hour != actual_hour:
        raise ValidationError("snapshot observation hour differs from requested UTC hour")
    return actual_hour, evidence


def verify_vacant(listing: dict, name: str) -> None:
    if not re.fullmatch(r"crypto-hour-accepted-\d{8}T\d{2}", name):
        raise ValidationError("invalid acceptance artifact name")
    total = listing.get("total_count")
    artifacts = listing.get("artifacts")
    if type(total) is not int or total < 0 or total > MAX_LIST:
        raise ValidationError("artifact count unavailable or incomplete")
    if not isinstance(artifacts, list) or len(artifacts) != total:
        raise ValidationError("artifact list incomplete")
    for artifact in artifacts:
        if not isinstance(artifact, dict) or artifact.get("name") != name:
            raise ValidationError("artifact response is not restricted to the requested hour")
    if total:
        raise ValidationError("duplicate accepted UTC hour; refuse this ingestion")


def build_receipt(
    *, snapshot: Path, config: Path, event: str, intended: str,
    correlation: str, now: datetime, run_id: str,
    run_attempt: str, snapshot_commit: str, source_intent: str,
    rolling_pr_outcome: str,
) -> dict[str, object]:
    hour, evidence = inspect_snapshot(snapshot, config, event, intended, correlation, now)
    if not run_id.isdecimal() or int(run_id) < 1:
        raise ValidationError("run ID must be positive")
    if not run_attempt.isdecimal() or int(run_attempt) < 1:
        raise ValidationError("run attempt must be positive")
    if SHA_RE.fullmatch(snapshot_commit) is None:
        raise ValidationError("invalid source snapshot commit identity")
    if source_intent != f"deterministic-publication-intent-{run_id}-{run_attempt}":
        raise ValidationError("immutable intent artifact identity mismatch")
    if rolling_pr_outcome not in {"success", "failure", "skipped"}:
        raise ValidationError("invalid rolling PR outcome")
    return {
        "contract_version": CONTRACT,
        "status": "accepted-on-artifact-upload",
        "intended_hour_utc": hour.strftime("%Y-%m-%dT%H:00:00Z"),
        "source_event": event,
        "dispatch_correlation_id": correlation if event == "workflow_dispatch" else None,
        "run_id": int(run_id),
        "run_attempt": int(run_attempt),
        "generated_at_utc": evidence["generated_at_utc"],
        "quality_status": evidence["quality_status"],
        "receipt_prepared_at_utc": now.isoformat().replace("+00:00", "Z"),
        "accepted_hour_artifact": receipt_name(hour),
        "snapshot_sha256": hashlib.sha256(snapshot.read_bytes()).hexdigest(),
        "snapshot_commit_sha": snapshot_commit,
        "source_intent_artifact": source_intent,
        "rolling_pr_outcome": rolling_pr_outcome,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("request", "prepare", "vacant", "accept"))
    parser.add_argument("--event", default="")
    parser.add_argument("--intended-hour", default="")
    parser.add_argument("--correlation", default="")
    parser.add_argument("--snapshot", type=Path)
    parser.add_argument("--config", type=Path, default=Path("config/crypto_sources.yml"))
    parser.add_argument("--listing", type=Path)
    parser.add_argument("--name", default="")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--run-id", default="")
    parser.add_argument("--run-attempt", default="")
    parser.add_argument("--snapshot-commit", default="")
    parser.add_argument("--source-intent", default="")
    parser.add_argument("--rolling-pr-outcome", default="")
    args = parser.parse_args()
    now = datetime.now(timezone.utc)
    try:
        if args.command == "request":
            check_request(args.event, args.intended_hour, args.correlation, now)
        elif args.command == "vacant":
            if args.listing is None:
                raise ValidationError("artifact listing required")
            verify_vacant(json.loads(args.listing.read_text(encoding="utf-8")), args.name)
        else:
            if args.snapshot is None:
                raise ValidationError("snapshot path required")
            if args.command == "prepare":
                hour, _ = inspect_snapshot(
                    args.snapshot, args.config, args.event, args.intended_hour, args.correlation, now
                )
                print(receipt_name(hour))
            else:
                if args.output is None:
                    raise ValidationError("receipt output path required")
                receipt = build_receipt(
                    snapshot=args.snapshot, config=args.config,
                    event=args.event, intended=args.intended_hour,
                    correlation=args.correlation, now=now,
                    run_id=args.run_id, run_attempt=args.run_attempt,
                    snapshot_commit=args.snapshot_commit, source_intent=args.source_intent,
                    rolling_pr_outcome=args.rolling_pr_outcome,
                )
                args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (ValidationError, ValueError, KeyError, OSError, json.JSONDecodeError) as exc:
        parser.exit(1, f"Hourly ingestion refused: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
