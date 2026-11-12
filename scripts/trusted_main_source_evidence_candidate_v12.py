#!/usr/bin/env python3
"""Phase 17 Slice B candidate integration for accumulation contract v1.2."""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from datetime import timedelta
from pathlib import Path
from typing import Any, Mapping

import trusted_main_source_evidence_accumulation_v12 as accumulation
import trusted_main_source_evidence_candidate_impl as _legacy

# Capture the proven implementation entry points before patching its globals.
_LEGACY_BUILD_CLOSURE = _legacy.build_source_population_closure

for _name, _value in vars(_legacy).items():
    if _name not in {
        "__name__",
        "__loader__",
        "__package__",
        "__spec__",
        "accumulation",
        "CLOSURE_CONTRACT",
        "derive_window",
        "census_bounds",
        "build_source_population_closure",
    }:
        globals()[_name] = _value

CLOSURE_CONTRACT = "phase17-slice-b-source-population-closure/v1.2"
CANDIDATE_WORKFLOW_PATH = ".github/workflows/build-trusted-main-source-evidence-candidate.yml"


def _candidate_run_created_at(expected_main_sha: str) -> str:
    """Resolve C_end from exact GitHub workflow-run metadata.

    GitHub's run record, not runner wall clock or event timestamps, is the
    normative source.  A token is used when exposed by the caller; the public
    repository API remains a valid read-only fallback.
    """
    repository = os.environ.get("GITHUB_REPOSITORY", "")
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    api_url = os.environ.get("GITHUB_API_URL", "https://api.github.com").rstrip("/")
    if repository != EXPECTED_REPOSITORY:
        raise CandidateError("candidate workflow repository identity mismatch")
    numeric_run_id = _positive_int(run_id, "GITHUB_RUN_ID")
    url = f"{api_url}/repos/{repository}/actions/runs/{numeric_run_id}"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "crypto-pulse-phase17-v1.2",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, urllib.error.URLError) as exc:
        raise CandidateError(f"cannot resolve exact candidate workflow run metadata: {exc}") from exc
    if not isinstance(payload, dict):
        raise CandidateError("candidate workflow run metadata is not an object")
    if _positive_int(payload.get("id"), "candidate-run.id") != numeric_run_id:
        raise CandidateError("candidate workflow run id mismatch")
    if _sha1(payload.get("head_sha"), "candidate-run.head_sha") != _sha1(
        expected_main_sha, "expected_main_sha"
    ):
        raise CandidateError("candidate workflow run head SHA differs from exact main")
    if str(payload.get("path", "")) != CANDIDATE_WORKFLOW_PATH:
        raise CandidateError("candidate workflow path mismatch")
    if str(payload.get("event", "")) not in {"schedule", "workflow_dispatch"}:
        raise CandidateError("candidate workflow event is not governed")
    created_at = payload.get("created_at")
    return _utc_text(_utc(created_at, "candidate-run.created_at"))


def census_bounds(
    anchor_observation_hour_utc: str | Mapping[str, Any],
    candidate_created_at_utc: str | None = None,
) -> dict[str, str]:
    # Preserve the historical helper call shape for v1.1 tests/tools while the
    # v1.2 derive path always supplies the real H_main and candidate C_end.
    if isinstance(anchor_observation_hour_utc, Mapping) and candidate_created_at_utc is None:
        start = _utc(anchor_observation_hour_utc.get("start_utc"), "window.start_utc")
        end = _utc(anchor_observation_hour_utc.get("end_utc"), "window.end_utc")
        if end < start:
            raise CandidateError("window end precedes start")
        return {
            "start_utc": _utc_text(start - timedelta(days=31)),
            "end_utc": _utc_text(end + timedelta(hours=1)),
        }
    if not isinstance(anchor_observation_hour_utc, str) or candidate_created_at_utc is None:
        raise CandidateError("v1.2 census requires H_main and candidate created_at")
    anchor = _utc(anchor_observation_hour_utc, "anchor_observation_hour_utc")
    end = _utc(candidate_created_at_utc, "candidate_created_at_utc")
    start = anchor - timedelta(days=31)
    if end < start:
        raise CandidateError("candidate run predates v1.2 census start")
    return {"start_utc": _utc_text(start), "end_utc": _utc_text(end)}


def derive_window(repository_root: Path, base_sha: str) -> dict[str, Any]:
    """Derive H_main and immutable v1.2 census bounds for this workflow run."""
    base_sha = _sha1(base_sha, "base_sha")
    manifest = accumulation.build_accumulation_manifest(
        Path(repository_root), base_sha, []
    )
    anchor = manifest.get("anchor_observation_hour_utc")
    if not isinstance(anchor, str) or not anchor:
        raise CandidateError("protected-main anchor is unavailable")
    created_at = _candidate_run_created_at(base_sha)
    return {
        "base_sha": base_sha,
        "base_tree_sha": manifest["base_tree_sha"],
        "anchor_observation_hour_utc": anchor,
        "selection": dict(manifest["selection"]),
        "window": dict(manifest["window"]),
        "candidate_run_created_at_utc": created_at,
        "census": census_bounds(anchor, created_at),
    }


def _run_created_at(raw_run: Mapping[str, Any]) -> str:
    """Resolve source-run creation time from exact attempt-1 GitHub metadata."""
    attempts = raw_run.get("attempts")
    if not isinstance(attempts, list):
        raise CandidateError("run attempts must be a list")
    first = [
        row
        for row in attempts
        if isinstance(row, dict)
        and _positive_int(row.get("run_attempt"), "attempt.run_attempt") == 1
    ]
    if len(first) != 1:
        raise CandidateError("source run must contain exactly one attempt-1 record")
    return _utc_text(_utc(first[0].get("created_at"), "source-run.created_at"))


def build_source_population_closure(capture: Mapping[str, Any]) -> dict[str, Any]:
    """Build the exact v1.2 admitted population and freeze post-C_end races."""
    if capture.get("repository") != EXPECTED_REPOSITORY:
        raise CandidateError("capture repository mismatch")
    census = capture.get("census")
    if not isinstance(census, dict):
        raise CandidateError("capture census is missing")
    start = _utc(census.get("start_utc"), "census.start_utc")
    end = _utc(census.get("end_utc"), "census.end_utc")
    if end < start:
        raise CandidateError("census end precedes start")

    extension_raw = capture.get("retained_artifact_extension_run_ids", [])
    if not isinstance(extension_raw, list):
        raise CandidateError("retained artifact extension run ids must be a list")
    extension_ids = {
        _positive_int(value, "retained artifact extension run id")
        for value in extension_raw
    }

    runs_raw = capture.get("runs")
    if not isinstance(runs_raw, list):
        raise CandidateError("capture runs must be a list")

    admitted_runs: list[dict[str, Any]] = []
    admitted_extension_ids: set[int] = set()
    created_by_run: dict[int, str] = {}
    for raw in runs_raw:
        if not isinstance(raw, dict):
            raise CandidateError("capture run must be an object")
        run_id = _positive_int(raw.get("run_id"), "run.run_id")
        created_text = _run_created_at(raw)
        created = _utc(created_text, "source-run.created_at")
        sources = {
            str(value)
            for value in raw.get("discovery_sources", [])
            if str(value)
        }
        is_extension = run_id in extension_ids or "retained-artifact-extension" in sources
        is_census = "census" in sources

        if created > end:
            # A post-C_end retained artifact can appear while a candidate is
            # running. It belongs to the next candidate and must not mutate
            # this candidate's closure identity.
            if is_census:
                raise CandidateError("census admitted a source run created after C_end")
            if is_extension:
                continue
            raise CandidateError("post-C_end source run has no governed discovery source")

        if created < start and not is_extension:
            raise CandidateError("pre-C_start source run is not a retained-artifact extension")
        if start <= created <= end and not (is_census or is_extension):
            raise CandidateError("in-bound source run has no governed discovery source")

        admitted_runs.append(dict(raw))
        created_by_run[run_id] = created_text
        if is_extension:
            admitted_extension_ids.add(run_id)

    filtered = dict(capture)
    filtered["runs"] = admitted_runs
    filtered["retained_artifact_extension_run_ids"] = sorted(admitted_extension_ids)
    # Keep historical scheduled evidence unchanged, but admit exact accepted
    # dispatch metadata through the same closed population.
    closure = _legacy._ORIGINAL_BUILD_SOURCE_POPULATION_CLOSURE(filtered)
    expected_workflow_id = _positive_int(capture.get("workflow_id"), "capture.workflow_id")
    raw_by_run = {int(row["run_id"]): row for row in admitted_runs}
    for run in closure["runs"]:
        raw = raw_by_run[run["run_id"]]
        raw_by_attempt = {int(row["run_attempt"]): row for row in raw["attempts"]}
        for attempt in run["attempts"]:
            if attempt["workflow_id"] != expected_workflow_id:
                raise CandidateError("attempt workflow id does not match capture workflow")
            if attempt["event"] not in {"schedule", "workflow_dispatch"}:
                raise CandidateError("attempt event is not an authorised ingestion event")
            if attempt["event"] == "workflow_dispatch":
                raw_attempt = raw_by_attempt[attempt["run_attempt"]]
                fields = (
                    "id", "run_attempt", "workflow_id", "path", "head_sha",
                    "head_branch", "status", "conclusion", "event", "actor",
                    "repository", "created_at",
                )
                attempt["dispatch_source_run"] = {
                    key: raw_attempt.get(key) for key in fields
                }
                receipts = [
                    artifact for artifact in raw["artifacts"]
                    if isinstance(artifact, dict)
                    and re.fullmatch(r"crypto-hour-accepted-\d{8}T\d{2}",
                                     str(artifact.get("name", ""))) is not None
                ]
                if len(receipts) > 1:
                    raise CandidateError("ambiguous accepted-hour artifact for dispatched run")
                carrier = receipts[0] if receipts else None
                if carrier is not None:
                    carrier_run = carrier.get("workflow_run") or {}
                    if int(carrier_run.get("id", 0) or 0) != run["run_id"]:
                        raise CandidateError("accepted-hour artifact belongs to another run")
                attempt["accepted_hour_artifact"] = (
                    {
                        "id": _positive_int(carrier["id"], "accepted-hour artifact.id"),
                        "name": carrier["name"],
                        "expired": bool(carrier.get("expired", False)),
                    }
                    if carrier is not None else None
                )
    closure.pop("sha256", None)
    closure["workflow_id"] = expected_workflow_id
    closure["contract"] = CLOSURE_CONTRACT
    closure["candidate_run_created_at_utc"] = _utc_text(end)
    closure["census"] = {
        "start_utc": _utc_text(start),
        "end_utc": _utc_text(end),
    }
    for run in closure["runs"]:
        run_id = int(run["run_id"])
        run["source_run_created_at_utc"] = created_by_run[run_id]
    closure["sha256"] = sha256_bytes(canonical_json_bytes(closure))
    return closure


# Preserve the exact accepted-hour receipt as a replayable input, rather than
# promoting a dispatch through the historical schedule-only trust boundary.
_ORIGINAL_SOURCE_INPUTS_FROM_CAPTURE = _legacy.source_inputs_from_capture
_ORIGINAL_SERIALISABLE_SOURCE_INPUT = _legacy._serialisable_source_input
_ORIGINAL_SOURCE_INPUTS_FROM_BUNDLE = _legacy.source_inputs_from_bundle


def source_inputs_from_capture(capture: Mapping[str, Any], artifact_root: Path) -> list[dict[str, Any]]:
    sources = _ORIGINAL_SOURCE_INPUTS_FROM_CAPTURE(capture, artifact_root)
    closure = build_source_population_closure(capture)
    metadata = {
        (attempt["run_id"], attempt["run_attempt"]): attempt
        for run in closure["runs"] for attempt in run["attempts"]
        if attempt["event"] == "workflow_dispatch"
    }
    for source in sources:
        if source["event"] != "workflow_dispatch":
            continue
        attempt = metadata[(source["run_id"], source["run_attempt"])]
        source["dispatch_source_run"] = attempt["dispatch_source_run"]
        source["accepted_hour_artifact"] = attempt["accepted_hour_artifact"]
        receipt_path = (
            Path(artifact_root) / str(source["run_id"]) /
            str(source["run_attempt"]) / "accepted-hour" / "receipt.json"
        )
        source["accepted_hour_receipt_bytes"] = (
            receipt_path.read_bytes() if receipt_path.is_file() else None
        )
    return sources


def _serialisable_source_input(source: Mapping[str, Any], bundle_root: Path) -> dict[str, Any]:
    row = _ORIGINAL_SERIALISABLE_SOURCE_INPUT(source, bundle_root)
    if source.get("event") != "workflow_dispatch":
        return row
    receipt = source.get("accepted_hour_receipt_bytes")
    if isinstance(receipt, (bytes, bytearray)):
        rel = (Path("raw-inputs/sources") / str(source["run_id"]) /
               str(source["run_attempt"]) / "accepted-hour" / "receipt.json")
        target = Path(bundle_root) / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(bytes(receipt))
        row["accepted_hour_receipt_path"] = rel.as_posix()
        row["accepted_hour_receipt_sha256"] = sha256_bytes(bytes(receipt))
    else:
        row["accepted_hour_receipt_path"] = None
        row["accepted_hour_receipt_sha256"] = None
    return row


def source_inputs_from_bundle(bundle_root: Path) -> list[dict[str, Any]]:
    sources = _ORIGINAL_SOURCE_INPUTS_FROM_BUNDLE(bundle_root)
    for source in sources:
        if source.get("event") != "workflow_dispatch":
            continue
        rel = source.pop("accepted_hour_receipt_path", None)
        digest = source.pop("accepted_hour_receipt_sha256", None)
        if rel is None and digest is None:
            source["accepted_hour_receipt_bytes"] = None
            continue
        expected = (
            f'raw-inputs/sources/{source["run_id"]}/{source["run_attempt"]}/'
            "accepted-hour/receipt.json"
        )
        if rel != expected:
            raise CandidateError("bundled accepted-hour receipt path is not canonical")
        raw = (Path(bundle_root) / expected).read_bytes()
        if sha256_bytes(raw) != _sha256(digest, "accepted-hour receipt SHA"):
            raise CandidateError("bundled accepted-hour receipt hash mismatch")
        source["accepted_hour_receipt_bytes"] = raw
    return sources


# Patch the mature candidate implementation in-place so its prepare/replay,
# materialisation, recovery and PR verification functions operate over v1.2.
_legacy.accumulation = accumulation
_legacy.CLOSURE_CONTRACT = CLOSURE_CONTRACT
_legacy.census_bounds = census_bounds
_legacy.derive_window = derive_window
_legacy.build_source_population_closure = build_source_population_closure
_legacy.source_inputs_from_capture = source_inputs_from_capture
_legacy._serialisable_source_input = _serialisable_source_input
_legacy.source_inputs_from_bundle = source_inputs_from_bundle

# Re-export patched functions for the public bounded wrapper.
for _name in (
    "source_inputs_from_capture",
    "prepare_bundle",
    "replay_bundle",
    "verify_closure",
    "compare_recovery_capture",
    "verify_worktree",
    "render_pr_body",
    "verify_pr_snapshot",
    "publication_intent_git_reference",
    "_write_json",
    "_bundle_hashes",
    "sha256_bytes",
    "canonical_json_bytes",
    "CandidateError",
):
    globals()[_name] = getattr(_legacy, _name)


def main() -> int:
    return _legacy.main()


if __name__ == "__main__":
    raise SystemExit(main())
