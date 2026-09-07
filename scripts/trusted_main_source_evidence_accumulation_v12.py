#!/usr/bin/env python3
"""Phase 17/18 trusted-main source-evidence accumulation contract v1.2.

v1.1 remains immutable historical evidence.  This module reuses its exact
source/recovery verification primitives and changes only liveness selection:
the earliest at most 25 genuine verified observations after H_main may be
selected, without inventing records for missing wall-clock hours.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import trusted_main_source_evidence_accumulation as _v11

# Re-export the proven v1.1 verification/recovery primitives for candidate code.
for _name, _value in vars(_v11).items():
    if _name not in {"__name__", "__loader__", "__package__", "__spec__", "CONTRACT", "WINDOW_HOURS", "build_accumulation_manifest", "main"}:
        globals()[_name] = _value

CONTRACT = "trusted-main-source-evidence-accumulation/v1.2"
MAX_ADDITIONS = 25
GAP_SEMANTICS = "unobserved-hours-remain-absent"


def _source_order(record: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        str(record["canonical_observation_hour_utc"]),
        int(record["run_id"]),
        int(record["run_attempt"]),
        str(record["snapshot_sha256"]),
        str(record["snapshot_path"]),
    )


def build_accumulation_manifest(
    repository_root: Path,
    exact_base_sha: str,
    source_inputs: Sequence[Mapping[str, Any]],
    recovery_comment_inputs: Sequence[Mapping[str, Any]] = (),
    allowed_recovery_issue_numbers: Iterable[int] = (),
) -> dict[str, Any]:
    """Build one deterministic v1.2 accumulation manifest.

    The complete captured successful-input population remains globally
    fail-closed.  Only after exact blockers are resolved are genuine verified
    observations strictly after H_main considered, oldest first, with a hard
    maximum of 25 additions.
    """
    repository_root = Path(repository_root)
    base_sha, base_tree_sha = _v11._require_exact_commit(repository_root, exact_base_sha)
    config = _v11._load_base_config(repository_root, base_sha)
    anchor = _v11._resolve_anchor(repository_root, base_sha)

    if anchor is None:
        finding = _v11._blocker(
            "anchor-unavailable",
            [],
            None,
            reason="no Phase 13 validated current candidate",
        )
        manifest: dict[str, Any] = {
            "contract": CONTRACT,
            "repository": _v11.EXPECTED_REPOSITORY,
            "base_sha": base_sha,
            "base_tree_sha": base_tree_sha,
            "anchor_observation_hour_utc": None,
            "selection": None,
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
        manifest["candidate_id"] = _v11._candidate_id(manifest)
        return manifest

    diagnostics: list[dict[str, Any]] = []
    supersession: list[dict[str, Any]] = []
    input_blockers: list[dict[str, Any]] = []

    # Preserve v1.1 run/attempt semantics exactly: only scheduled successful
    # attempts participate; among multiple successful attempts the highest
    # successful attempt supersedes earlier successful attempts.  A later
    # failed attempt is diagnostic-only and therefore cannot erase success.
    scheduled_success: dict[int, list[Mapping[str, Any]]] = {}
    for source in sorted(source_inputs, key=_v11._input_sort_key):
        identity = _v11._identity(source)
        if source.get("event") != _v11.EXPECTED_EVENT:
            diagnostics.append(_v11._diagnostic("non-schedule-input", identity))
            continue
        if source.get("conclusion") != _v11.EXPECTED_CONCLUSION:
            diagnostics.append(_v11._diagnostic("non-success-input", identity))
            continue
        try:
            run_id = _v11._int(source.get("run_id"), "run_id")
            _v11._int(source.get("run_attempt"), "run_attempt")
        except ValueError as exc:
            input_blockers.append(
                _v11._blocker(
                    "source-input-identity-invalid",
                    [identity],
                    None,
                    reason=str(exc),
                )
            )
            continue
        scheduled_success.setdefault(run_id, []).append(source)

    winners: list[Mapping[str, Any]] = []
    for run_id in sorted(scheduled_success):
        rows = scheduled_success[run_id]
        by_attempt: dict[int, list[Mapping[str, Any]]] = {}
        for row in rows:
            attempt = _v11._int(row.get("run_attempt"), "run_attempt")
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
                            "input_identity": _v11._identity(row),
                        }
                    )
        highest_rows = by_attempt[highest]
        if len(highest_rows) > 1:
            raw_identities = [_v11._identity(row) for row in highest_rows]
            exact_payloads = {
                _v11.canonical_json_bytes(
                    {
                        **_v11._identity(row),
                        "publication_intent_sha256": _v11.sha256_bytes(
                            _v11._bytes(row.get("publication_intent_bytes"), "publication_intent_bytes")
                        )
                        if isinstance(row.get("publication_intent_bytes"), (bytes, bytearray))
                        else None,
                        "snapshot_sha256": _v11.sha256_bytes(
                            _v11._bytes(row.get("snapshot_bytes"), "snapshot_bytes")
                        )
                        if isinstance(row.get("snapshot_bytes"), (bytes, bytearray))
                        else None,
                    }
                )
                for row in highest_rows
            }
            if len(exact_payloads) == 1:
                diagnostics.append(
                    _v11._diagnostic(
                        "duplicate-carrier-collapsed",
                        raw_identities[0],
                        count=len(highest_rows),
                    )
                )
                winners.append(highest_rows[0])
            else:
                input_blockers.append(
                    _v11._blocker(
                        "duplicate-run-attempt",
                        raw_identities,
                        None,
                        run_id=run_id,
                        run_attempt=highest,
                    )
                )
            continue
        winners.append(highest_rows[0])

    verified_all: list[dict[str, Any]] = []
    verified_after_anchor: list[dict[str, Any]] = []
    for source in sorted(winners, key=_v11._input_sort_key):
        identity = _v11._identity(source)
        try:
            candidate = _v11._verify_source(repository_root, base_sha, config, source)
        except (_v11.AccumulationError, TypeError, ValueError) as exc:
            input_blockers.append(
                _v11._blocker(
                    "source-input-unverifiable",
                    [identity],
                    None,
                    reason=str(exc),
                )
            )
            continue
        verified_all.append(candidate)
        if candidate["canonical_observation_hour_utc"] <= anchor:
            diagnostics.append(
                _v11._diagnostic(
                    "verified-input-at-or-before-anchor",
                    candidate["input_identity"],
                    canonical_observation_hour_utc=candidate["canonical_observation_hour_utc"],
                )
            )
            continue
        verified_after_anchor.append(candidate)

    # A repository path cannot truthfully represent two canonical hours in one
    # candidate population.  Fail closed instead of allowing path-map overwrite.
    conflicting_path_keys: set[tuple[int, int, str]] = set()
    by_path: dict[str, list[dict[str, Any]]] = {}
    for candidate in verified_after_anchor:
        by_path.setdefault(candidate["snapshot_path"], []).append(candidate)
    for path, rows in sorted(by_path.items()):
        hours = {row["canonical_observation_hour_utc"] for row in rows}
        payloads = {row["snapshot_sha256"] for row in rows}
        if len(hours) > 1 or len(payloads) > 1:
            input_blockers.append(
                _v11._blocker(
                    "candidate-path-identity-conflict",
                    [row["input_identity"] for row in rows],
                    None,
                    candidate_path=path,
                    candidate_hours=sorted(hours),
                    candidate_sha256s=sorted(payloads),
                )
            )
            for row in rows:
                conflicting_path_keys.add(
                    (int(row["run_id"]), int(row["run_attempt"]), str(row["snapshot_sha256"]))
                )

    candidates_for_hours = [
        row
        for row in verified_after_anchor
        if (int(row["run_id"]), int(row["run_attempt"]), str(row["snapshot_sha256"]))
        not in conflicting_path_keys
    ]

    by_hour: dict[str, list[dict[str, Any]]] = {}
    for candidate in candidates_for_hours:
        by_hour.setdefault(candidate["canonical_observation_hour_utc"], []).append(candidate)

    hours: list[dict[str, Any]] = []
    hour_blockers: list[dict[str, Any]] = []
    eligible_by_hour: dict[str, dict[str, Any]] = {}

    for hour in sorted(by_hour):
        candidates = sorted(by_hour[hour], key=_source_order)
        public_candidates = [_v11._source_public(item) for item in candidates]
        record: dict[str, Any] = {
            "canonical_observation_hour_utc": hour,
            "disposition": "no-promotable-observation",
            "source_candidates": public_candidates,
        }
        if len(candidates) > 1:
            blocker = _v11._blocker(
                "duplicate-observation-hour",
                [item["input_identity"] for item in candidates],
                hour,
                candidate_paths=[item["snapshot_path"] for item in candidates],
                candidate_sha256s=[item["snapshot_sha256"] for item in candidates],
            )
            hour_blockers.append(blocker)
            record["disposition"] = "duplicate"
            record["blocker_fingerprint"] = blocker["blocker_fingerprint"]
        else:
            candidate = candidates[0]
            trusted = _v11._git_bytes_at(repository_root, base_sha, candidate["snapshot_path"])
            if trusted is None:
                record["disposition"] = "eligible"
                record["eligible_source"] = _v11._source_public(candidate)
                eligible_by_hour[hour] = candidate
            elif trusted == candidate["snapshot_bytes"]:
                record["disposition"] = "already-trusted"
                record["trusted_path"] = candidate["snapshot_path"]
                record["trusted_sha256"] = _v11.sha256_bytes(trusted)
            else:
                blocker = _v11._blocker(
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
                        "sha256": _v11.sha256_bytes(trusted),
                        "git_blob_sha": _v11.git_blob_sha(trusted),
                    },
                )
                hour_blockers.append(blocker)
                record["disposition"] = "path-conflict"
                record["blocker_fingerprint"] = blocker["blocker_fingerprint"]
        hours.append(record)

    original_blockers = sorted(
        [*input_blockers, *hour_blockers],
        key=lambda item: (
            str(item.get("canonical_observation_hour_utc") or ""),
            item["blocker_class"],
            item["blocker_fingerprint"],
        ),
    )
    recovered, applied, recovery_blockers = _v11._apply_recoveries(
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

    unrecovered = [
        item
        for item in original_blockers
        if item["blocker_fingerprint"] not in recovered
    ]
    blocking_findings = sorted(
        [*unrecovered, *recovery_blockers],
        key=lambda item: (
            str(item.get("canonical_observation_hour_utc") or ""),
            item["blocker_class"],
            item["blocker_fingerprint"],
        ),
    )

    added_paths: list[dict[str, Any]] = []
    selected_hours: list[str] = []
    h_select_end: str | None = None
    if not blocking_findings:
        eligible_records = [
            record for record in hours if record["disposition"] == "eligible"
        ]
        eligible_records.sort(
            key=lambda record: _source_order(
                eligible_by_hour[record["canonical_observation_hour_utc"]]
            )
        )
        selected = eligible_records[:MAX_ADDITIONS]
        selected_hours = [
            str(record["canonical_observation_hour_utc"]) for record in selected
        ]
        h_select_end = selected_hours[-1] if selected_hours else None
        selected_set = set(selected_hours)
        for record in eligible_records:
            hour = str(record["canonical_observation_hour_utc"])
            record["disposition"] = (
                "selected" if hour in selected_set else "eligible-deferred"
            )
        for hour in selected_hours:
            candidate = eligible_by_hour[hour]
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

    # Explicit anti-skip proof: every eligible hour at/before H_select_end must
    # be selected.  This check is content-independent and chronological.
    if h_select_end is not None:
        omitted_earlier = [
            record["canonical_observation_hour_utc"]
            for record in hours
            if record["canonical_observation_hour_utc"] <= h_select_end
            and record["disposition"] == "eligible-deferred"
        ]
        if omitted_earlier:
            raise _v11.AccumulationError(
                "anti-skip invariant violated: earlier eligible observation omitted"
            )

    manifest = {
        "contract": CONTRACT,
        "repository": _v11.EXPECTED_REPOSITORY,
        "base_sha": base_sha,
        "base_tree_sha": base_tree_sha,
        "anchor_observation_hour_utc": anchor,
        "selection": {
            "policy": "earliest-genuine-observations",
            "max_additions": MAX_ADDITIONS,
            "gap_semantics": GAP_SEMANTICS,
            "selected_hours_utc": selected_hours,
            "h_select_end_utc": h_select_end,
        },
        # Kept for PR/render compatibility; it no longer denotes a fixed
        # wall-clock eligibility window.
        "window": {
            "start_utc": _v11._hour_add(anchor, 1),
            "end_utc": h_select_end,
            "hours": len(selected_hours),
            "max_additions": MAX_ADDITIONS,
            "gap_semantics": GAP_SEMANTICS,
        },
        "hours": hours,
        "verified_source_inputs": sorted(
            [_v11._source_public(item) for item in verified_all],
            key=_source_order,
        ),
        "supersession_records": sorted(
            supersession,
            key=lambda item: (
                item["run_id"],
                item["superseded_run_attempt"],
                _v11.canonical_json_bytes(item["input_identity"]),
            ),
        ),
        "operational_diagnostics": sorted(
            diagnostics, key=_v11.canonical_json_bytes
        ),
        "input_level_blockers": sorted(
            input_blockers, key=lambda item: item["blocker_fingerprint"]
        ),
        "hour_level_blockers": sorted(
            hour_blockers, key=lambda item: item["blocker_fingerprint"]
        ),
        "applied_recovery_decisions": sorted(
            applied, key=lambda item: item["blocker_fingerprint"]
        ),
        "blocking_findings": blocking_findings,
        "added_paths": added_paths,
    }
    manifest["candidate_id"] = _v11._candidate_id(manifest)
    return manifest
