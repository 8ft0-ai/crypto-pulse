#!/usr/bin/env python3
"""One-off retrospective source recovery; prospective accumulation is untouched.

Reuses Phase 17/18's accepted-hour and Phase 12 validators. The original
candidate commit and its retained evidence bundle are immutable inputs.
Only the exact, explicitly enumerated original candidate population is eligible.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

import trusted_main_source_evidence_accumulation as core
import trusted_main_source_evidence_accumulation_v12 as prospective
import trusted_main_source_evidence_candidate_v12 as candidate

SOURCE_SET_CONTRACT = "cryptopulse-retrospective-source-set/v1"
CLOSURE_CONTRACT = "cryptopulse-historical-gap-source-closure/v1"
MANIFEST_CONTRACT = "cryptopulse-trusted-main-historical-recovery/v1"
MAX_RECORDS = 25


class RecoveryError(ValueError):
    """Historical evidence does not satisfy the exact recovery contract."""


def _sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or core.SHA1_RE.fullmatch(value) is None:
        raise RecoveryError(f"{label} must be an exact lowercase 40-hex SHA")
    return value


def _digest(value: Any, label: str) -> str:
    if not isinstance(value, str) or core.SHA256_RE.fullmatch(value) is None:
        raise RecoveryError(f"{label} must be an exact lowercase SHA-256")
    return value


def _json(path: Path) -> Any:
    return json.loads(path.read_bytes().decode("utf-8"))


def _hash(value: Any) -> str:
    return core.sha256_bytes(core.canonical_json_bytes(value))


def _git(root: Path, *args: str) -> bytes:
    return core._git(root, *args)


def live_main_sha(root: Path) -> str:
    """Read the remote's actual main ref, never the stale local HEAD."""
    remote = _git(root, "remote", "get-url", "origin").decode().strip()
    allowed = {
        "https://github.com/8ft0-ai/crypto-pulse.git",
        "git@github.com:8ft0-ai/crypto-pulse.git",
    }
    if remote not in allowed:
        raise RecoveryError("origin is not the canonical CryptoPulse repository")
    reply = _git(root, "ls-remote", "--exit-code", "origin", "refs/heads/main")
    lines = reply.decode("ascii").splitlines()
    if len(lines) != 1:
        raise RecoveryError("current protected main cannot be uniquely resolved")
    fields = lines[0].split("\t")
    if len(fields) != 2 or fields[1] != "refs/heads/main":
        raise RecoveryError("unexpected remote main-ref response")
    return _sha(fields[0], "current protected main")


def validate_source_set(source_set: Any, original_manifest: Mapping[str, Any],
                        original_commit_sha: str) -> list[dict[str, Any]]:
    if not isinstance(source_set, dict) or set(source_set) != {
        "contract", "original_candidate_commit_sha", "original_candidate_id", "records"
    }:
        raise RecoveryError("historical source set has unsupported fields")
    if source_set["contract"] != SOURCE_SET_CONTRACT:
        raise RecoveryError("historical source-set contract mismatch")
    if _sha(source_set["original_candidate_commit_sha"], "source commit") != original_commit_sha:
        raise RecoveryError("historical source commit is not the bound original")
    if _digest(source_set["original_candidate_id"], "original candidate ID") != original_manifest["candidate_id"]:
        raise RecoveryError("original candidate manifest identity mismatch")
    rows = source_set["records"]
    original = original_manifest.get("added_paths")
    if not isinstance(rows, list) or not isinstance(original, list) or not (1 <= len(rows) <= MAX_RECORDS):
        raise RecoveryError("historical source set must contain 1 to 25 records")
    if len(rows) != len(original) or any(not isinstance(x, dict) for x in rows):
        raise RecoveryError("historical source set must equal the complete original selection")
    if core.canonical_json_bytes(rows) != core.canonical_json_bytes(original):
        raise RecoveryError("historical source set differs from original candidate manifest")
    hours, paths, runs = set(), set(), set()
    for row in rows:
        hour = core._canonical_hour(row.get("canonical_observation_hour_utc"))
        path = row.get("path")
        if not core._safe_snapshot_path(path):
            raise RecoveryError("historical path is outside the canonical source scope")
        _digest(row.get("sha256"), "source digest")
        _sha(row.get("git_blob_sha"), "source Git blob")
        run_id, attempt = row.get("source_run_id"), row.get("source_run_attempt")
        if type(run_id) is not int or type(attempt) is not int or run_id <= 0 or attempt <= 0:
            raise RecoveryError("source run/attempt identity is invalid")
        if hour in hours or path in paths or (run_id, attempt) in runs:
            raise RecoveryError("duplicate UTC hour, source path or run/attempt")
        hours.add(hour)
        paths.add(path)
        runs.add((run_id, attempt))
    return rows


def verify_original_evidence(root: Path, bundle: Path, original_commit_sha: str
                            ) -> tuple[dict[str, Any], dict[str, Any]]:
    candidate.verify_bundle(bundle)
    original_manifest = _json(bundle / "accumulation-manifest.json")
    original_closure = _json(bundle / "source-population-closure.json")
    evidence = _json(bundle / "candidate-evidence.json")
    if not all(isinstance(x, dict) for x in (original_manifest, original_closure, evidence)):
        raise RecoveryError("original evidence is not a JSON object")
    candidate_id = _digest(original_manifest.get("candidate_id"), "original candidate ID")
    if core._candidate_id(original_manifest) != candidate_id:
        raise RecoveryError("incorrect original manifest digest")
    original_closure_sha = _digest(original_closure.get("sha256"), "original closure SHA")
    if _hash({k: v for k, v in original_closure.items() if k != "sha256"}) != original_closure_sha:
        raise RecoveryError("incorrect original source-population closure digest")
    if (original_closure.get("expected_main_sha") != original_manifest.get("base_sha")
            or evidence.get("expected_main_sha") != original_manifest.get("base_sha")
            or evidence.get("candidate_id") != candidate_id
            or evidence.get("source_population_closure_sha256") != original_closure_sha):
        raise RecoveryError("original candidate, manifest and closure bindings disagree")
    if original_manifest.get("blocking_findings") or len(original_manifest.get("added_paths", [])) != 25:
        raise RecoveryError("original candidate has blocked or incomplete selection")
    original_base = _sha(original_manifest.get("base_sha"), "original base")
    original_parent = _git(root, "rev-list", "--parents", "-n", "1", original_commit_sha).decode().split()
    if original_parent != [original_commit_sha, original_base]:
        raise RecoveryError("historical candidate does not descend from its recorded base")
    diff = _git(root, "diff-tree", "--no-commit-id", "--name-status", "-r",
                original_commit_sha).decode().splitlines()
    expected_paths = {row["path"] for row in original_manifest["added_paths"]}
    if len(diff) != len(expected_paths) or {row[2:] for row in diff if row.startswith("A\t")} != expected_paths:
        raise RecoveryError("original candidate tree differs from source-only manifest")
    return original_manifest, original_closure


def build_recovery(root: Path, exact_main_sha: str, observed_main_sha: str,
                   original_commit_sha: str, source_set: Any, bundle: Path
                   ) -> tuple[dict[str, Any], dict[str, Any], dict[str, bytes]]:
    exact_main_sha = _sha(exact_main_sha, "trusted-main SHA")
    original_commit_sha = _sha(original_commit_sha, "original source commit")
    if _sha(observed_main_sha, "observed-main SHA") != exact_main_sha:
        raise RecoveryError("stale or mismatched trusted-main binding")
    main, tree = core._require_exact_commit(root, exact_main_sha)
    original_manifest, original_closure = verify_original_evidence(root, bundle, original_commit_sha)
    rows = validate_source_set(source_set, original_manifest, original_commit_sha)
    anchor = core._resolve_anchor(root, main)
    if anchor is None:
        raise RecoveryError("trusted-main observation anchor is unavailable")
    config = core._load_base_config(root, main)
    raw_sources = candidate.source_inputs_from_bundle(bundle)
    by_run: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for source in raw_sources:
        key = (source.get("run_id"), source.get("run_attempt"))
        by_run.setdefault(key, []).append(source)

    verified: list[dict[str, Any]] = []
    additions: list[dict[str, Any]] = []
    already: list[dict[str, Any]] = []
    original_bytes: dict[str, bytes] = {}
    for row in rows:
        path = row["path"]
        key = (row["source_run_id"], row["source_run_attempt"])
        matches = by_run.get(key, [])
        if len(matches) != 1:
            raise RecoveryError(f"missing or ambiguous original source provenance: {path}")
        source = matches[0]
        if source.get("event") != "workflow_dispatch" or source.get("conclusion") != "success":
            raise RecoveryError(f"unsupported historical source record: {path}")
        blob = core._git_bytes_at(root, original_commit_sha, path)
        if blob is None:
            raise RecoveryError(f"missing historical Git source blob: {path}")
        if (core.sha256_bytes(blob) != row["sha256"]
                or core.git_blob_sha(blob) != row["git_blob_sha"]):
            raise RecoveryError(f"original Git blob identity differs from manifest: {path}")
        proof = prospective._verify_candidate_source(root, main, config, source)
        if (proof["snapshot_bytes"] != blob
                or proof["snapshot_sha256"] != row["sha256"]
                or proof["snapshot_git_blob_sha"] != row["git_blob_sha"]
                or proof["snapshot_path"] != path
                or proof["canonical_observation_hour_utc"] != row["canonical_observation_hour_utc"]
                or proof["quality_status"] != "valid-ok"):
            raise RecoveryError(f"snapshot provenance, UTC hour or quality differs: {path}")
        if proof["canonical_observation_hour_utc"] > anchor:
            raise RecoveryError(f"source is prospective, not historical: {path}")
        record = {**row,
                  "publication_intent_sha256": proof["publication_intent_sha256"],
                  "accepted_hour_receipt_sha256": proof["accepted_hour_receipt_sha256"],
                  "input_identity": proof["input_identity"]}
        trusted = core._git_bytes_at(root, main, path)
        if trusted is None:
            record["disposition"] = "selected-retrospective"
            additions.append(row)
            original_bytes[path] = blob
        elif trusted == blob:
            record["disposition"] = "already-trusted-identical"
            already.append(row)
        else:
            raise RecoveryError(f"same-path differing bytes in trusted main: {path}")
        verified.append(record)

    closure = {
        "contract": CLOSURE_CONTRACT,
        "repository": core.EXPECTED_REPOSITORY,
        "selection_mode": "explicit-retrospective-not-forward-accumulation",
        "trusted_main_sha": main,
        "trusted_main_tree_sha": tree,
        "original_candidate_commit_sha": original_commit_sha,
        "original_candidate_id": original_manifest["candidate_id"],
        "original_source_population_closure_sha256": original_closure["sha256"],
        "requested_source_set_sha256": _hash(source_set),
        "verified_records": verified,
    }
    closure["sha256"] = _hash(closure)
    manifest = {
        "contract": MANIFEST_CONTRACT,
        "repository": core.EXPECTED_REPOSITORY,
        "base_sha": main,
        "base_tree_sha": tree,
        "anchor_observation_hour_utc": anchor,
        "source_population_closure_sha256": closure["sha256"],
        "original_candidate_commit_sha": original_commit_sha,
        "original_candidate_id": original_manifest["candidate_id"],
        "selection": {
            "policy": "explicit-retrospective-only",
            "max_additions": MAX_RECORDS,
            "requested_hours_utc": [row["canonical_observation_hour_utc"] for row in rows],
            "selected_hours_utc": [row["canonical_observation_hour_utc"] for row in additions],
        },
        "verified_source_inputs": [
            {k: v for k, v in item.items() if k != "disposition"} for item in verified
        ],
        "already_trusted_paths": already,
        "added_paths": additions,
        "blocking_findings": [],
    }
    manifest["candidate_id"] = core._candidate_id(manifest)
    return manifest, closure, original_bytes


def write_prepared(output: Path, manifest: Mapping[str, Any], closure: Mapping[str, Any],
                   files: Mapping[str, bytes], materialise: Path | None) -> None:
    if output.exists() and any(output.iterdir()):
        raise RecoveryError("recovery output directory must be empty")
    if materialise is not None:
        if not materialise.is_dir():
            raise RecoveryError("source-only materialisation root must exist")
        for rel in files:
            if (materialise / rel).exists():
                raise RecoveryError(f"refusing to overwrite materialised source: {rel}")
    output.mkdir(parents=True, exist_ok=True)
    for name, data in (("recovery-manifest.json", manifest),
                       ("source-population-closure.json", closure)):
        (output / name).write_bytes(core.canonical_json_bytes(data) + b"\n")
    if materialise is not None:
        for rel, blob in files.items():
            target = materialise / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(blob)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, default=Path("."))
    parser.add_argument("--trusted-main-sha", required=True)
    parser.add_argument("--original-candidate-sha", required=True)
    parser.add_argument("--source-set", required=True, type=Path)
    parser.add_argument("--original-bundle", required=True, type=Path)
    parser.add_argument("--output-directory", required=True, type=Path)
    parser.add_argument("--materialise-to", type=Path)
    args = parser.parse_args()
    try:
        observed = live_main_sha(args.repository_root)
        manifest, closure, files = build_recovery(
            args.repository_root, args.trusted_main_sha, observed,
            args.original_candidate_sha, _json(args.source_set), args.original_bundle)
        if live_main_sha(args.repository_root) != args.trusted_main_sha:
            raise RecoveryError("trusted main advanced during recovery")
        write_prepared(args.output_directory, manifest, closure, files, args.materialise_to)
        print(json.dumps({"candidate_id": manifest["candidate_id"],
                          "base_sha": manifest["base_sha"],
                          "closure_sha256": closure["sha256"],
                          "selected": len(files),
                          "already_trusted": len(manifest["already_trusted_paths"])},
                         sort_keys=True))
        return 0
    except (RecoveryError, core.AccumulationError, candidate.CandidateError,
            OSError, TypeError, ValueError, subprocess.CalledProcessError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
