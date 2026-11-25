#!/usr/bin/env python3
"""Verify immutable accepted-hour evidence for protected-main source-only promotion.

This is a pure validation interface. It never writes Git refs, opens PRs or
grants publication authority; the separately guarded Actions job owns that.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from crypto_ingestion_slot import canonical_hour, receipt_name
from deterministic_site_publication import (
    PublicationPolicyError, quality_reasons, verify_publication_intent,
)
from validate_crypto_observation_hour import validate_observation_hour
from validate_crypto_snapshot import classify_snapshot_quality, load_config

SHA1 = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
INGEST_WORKFLOW = ".github/workflows/ingest-crypto-sources.yml"


class SourcePromotionError(ValueError):
    pass


def verify_bundle(
    intent: Mapping[str, Any],
    receipt: Mapping[str, Any],
    source_run: Mapping[str, Any],
    snapshot_bytes: bytes,
    snapshot_file: Path,
    config_file: Path,
) -> dict[str, str]:
    run_id = source_run.get("id")
    attempt = source_run.get("run_attempt")
    workflow_id = source_run.get("workflow_id")
    base = source_run.get("head_sha")
    event = source_run.get("event")
    if (
        type(run_id) is not int or run_id < 1
        or type(attempt) is not int or attempt != 1
        or type(workflow_id) is not int or workflow_id < 1
        or not isinstance(base, str) or not SHA1.fullmatch(base)
        or source_run.get("head_branch") != "main"
        or source_run.get("path") != INGEST_WORKFLOW
        or event not in ("schedule", "workflow_dispatch")
    ):
        raise SourcePromotionError("source-run identity or provenance is invalid")

    if (
        receipt.get("contract_version") != "crypto-hour-ingestion/v1"
        or receipt.get("status") != "accepted-on-artifact-upload"
        or receipt.get("run_id") != run_id
        or receipt.get("run_attempt") != attempt
        or receipt.get("source_event") != event
        or receipt.get("quality_status") != "valid-ok"
        or receipt.get("source_intent_artifact") != f"deterministic-publication-intent-{run_id}-{attempt}"
    ):
        raise SourcePromotionError("accepted-hour receipt identity is invalid")
    hour = receipt.get("intended_hour_utc")
    try:
        canonical = canonical_hour(hour)
    except (ValueError, TypeError) as exc:
        raise SourcePromotionError("accepted-hour receipt hour is invalid") from exc
    if receipt.get("accepted_hour_artifact") != receipt_name(canonical):
        raise SourcePromotionError("accepted-hour artefact name is invalid")
    if event == "workflow_dispatch":
        if receipt.get("dispatch_correlation_id") != "cp-" + canonical.strftime("%Y%m%d%H"):
            raise SourcePromotionError("source dispatch correlation is invalid")
    elif receipt.get("dispatch_correlation_id") is not None:
        raise SourcePromotionError("scheduled source run has dispatch correlation")

    if not isinstance(snapshot_bytes, bytes) or not snapshot_bytes:
        raise SourcePromotionError("source snapshot bytes are unavailable")
    digest = hashlib.sha256(snapshot_bytes).hexdigest()
    if receipt.get("snapshot_sha256") != digest:
        raise SourcePromotionError("accepted receipt snapshot SHA-256 mismatch")
    try:
        verify_publication_intent(
            intent, snapshot_bytes,
            expected_main_base_sha=base,
            expected_source_workflow_id=workflow_id,
            expected_source_run_id=run_id,
            expected_source_run_attempt=attempt,
        )
    except (PublicationPolicyError, ValueError, TypeError) as exc:
        raise SourcePromotionError("immutable source intent verification failed") from exc
    if (
        intent.get("automatic_eligible") is not True
        or intent.get("refusal_reasons") != []
        or intent.get("snapshot_commit_sha") != receipt.get("snapshot_commit_sha")
        or intent.get("observation_hour_utc") != hour
        or intent.get("generated_at_utc") != receipt.get("generated_at_utc")
    ):
        raise SourcePromotionError("accepted receipt contradicts immutable source intent")

    path = intent.get("snapshot_path")
    if (
        not isinstance(path, str)
        or not path.startswith("data/crypto/hourly/")
        or not path.endswith("_source_snapshot.json")
        or PurePosixPath(path).as_posix() != path
        or ".." in PurePosixPath(path).parts
        or re.search(r"[^A-Za-z0-9_./-]", path)
    ):
        raise SourcePromotionError("source path is not canonical and confined")
    if snapshot_file.read_bytes() != snapshot_bytes:
        raise SourcePromotionError("snapshot file differs from accepted bytes")
    try:
        config = load_config(config_file)
        quality = classify_snapshot_quality(json.loads(snapshot_bytes), config)
        observed = validate_observation_hour(snapshot_file, config)
    except (ValueError, TypeError, OSError, KeyError) as exc:
        raise SourcePromotionError("snapshot independent validation failed") from exc
    if quality_reasons(json.loads(snapshot_bytes), quality):
        raise SourcePromotionError("source quality is not eligible for automatic promotion")
    if (
        observed.get("observation_hour_utc") != hour
        or observed.get("generated_at_utc") != receipt.get("generated_at_utc")
        or observed.get("quality_status") != "valid-ok"
    ):
        raise SourcePromotionError("snapshot observation hour or quality does not match receipt")

    return {
        "source_path": path,
        "snapshot_sha256": digest,
        "source_hour": hour,
        "source_run_id": str(run_id),
        "source_run_attempt": str(attempt),
        "source_workflow_head_sha": base,
        "intent_snapshot_commit_sha": str(intent["snapshot_commit_sha"]),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--intent", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--source-run", required=True, type=Path)
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--config", default="config/crypto_sources.yml", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        raw = args.snapshot.read_bytes()
        result = verify_bundle(
            json.loads(args.intent.read_text(encoding="utf-8")),
            json.loads(args.receipt.read_text(encoding="utf-8")),
            json.loads(args.source_run.read_text(encoding="utf-8")),
            raw, args.snapshot, args.config,
        )
        args.output.write_text(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")
        return 0
    except (SourcePromotionError, PublicationPolicyError, OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        parser.exit(1, f"Trusted hourly source promotion refused: {exc}\n")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
