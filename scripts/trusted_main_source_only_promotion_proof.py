#!/usr/bin/env python3
"""Verify Stage 4C source-only provenance against fresh, trusted GitHub evidence.

The original ingestion commit is intentionally not required: the immutable
intent and accepted-hour receipt bind the original bytes, while the source-only
promotion receipt, exact PR/CI/merge chain and protected-main history establish
their independently promoted lineage. No writes or workflow dispatches.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import subprocess
import zipfile
from pathlib import Path
from typing import Any, Callable, Mapping

from trusted_hourly_source import verify_bundle

REPOSITORY = "8ft0-ai/crypto-pulse"
CONTRACT = "cryptopulse-stage4c-source-only-provenance/v1"
APPROVED_WORKFLOW = ".github/workflows/pr-validation.yml"
SHA1 = re.compile(r"[0-9a-f]{40}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")


class PromotionProofError(ValueError):
    """A present Stage 4C claim cannot be proved exactly."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise PromotionProofError(message)


def _sha1(value: Any, label: str) -> str:
    _require(isinstance(value, str) and SHA1.fullmatch(value) is not None, label)
    return value


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _github_bytes(endpoint: str, accept: str | None = None) -> bytes:
    argv = ["gh", "api"]
    if accept:
        argv += ["-H", f"Accept: {accept}"]
    argv.append(endpoint)
    result = subprocess.run(argv, capture_output=True, check=False)
    if result.returncode != 0:
        raise PromotionProofError(f"trusted GitHub evidence request failed: {endpoint}")
    return result.stdout


def _github_json(endpoint: str) -> Any:
    try:
        return json.loads(_github_bytes(endpoint))
    except (ValueError, UnicodeDecodeError) as exc:
        raise PromotionProofError(f"invalid trusted GitHub JSON: {endpoint}") from exc


def _artifact_json(raw: bytes) -> tuple[dict[str, Any], str]:
    _require(len(raw) <= 2_000_000, "promotion artefact ZIP exceeds bounded size")
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            _require(archive.namelist() == ["source-promotion-proof.json"],
                     "promotion artefact must contain exactly one proof")
            entry = archive.getinfo("source-promotion-proof.json")
            _require(entry.file_size <= 100_000, "promotion proof exceeds bounded size")
            body = archive.read(entry)
        payload = json.loads(body)
    except (zipfile.BadZipFile, UnicodeDecodeError, ValueError, KeyError) as exc:
        raise PromotionProofError("invalid immutable source-only promotion artefact") from exc
    _require(isinstance(payload, dict), "promotion proof is not a JSON object")
    return payload, _sha256(body)


def verify_source_only_promotion(
    run_id: int,
    run_attempt: int,
    intent_bytes: bytes,
    snapshot_bytes: bytes,
    receipt_bytes: bytes | None,
    snapshot_file: Path,
    repo_root: Path,
    expected_main_sha: str,
    app_slug: str,
    github_json: Callable[[str], Any] = _github_json,
    github_bytes: Callable[[str, str | None], bytes] = _github_bytes,
) -> dict[str, Any] | None:
    """Return a completely validated GitHub-backed proof, or None if absent.

    Only absence of the exact run-owned promotion artefact permits the legacy
    Git-object fallback. Any inconsistent or unprovable present claim fails
    closed. The caller re-queries this interface at publication time.
    """
    _require(type(run_id) is int and run_id > 0 and
             type(run_attempt) is int and run_attempt > 0, "source run identity invalid")
    _sha1(expected_main_sha, "expected protected-main SHA is invalid")
    _require(isinstance(app_slug, str) and re.fullmatch(r"[A-Za-z0-9-]+", app_slug) is not None,
             "trusted promotion App identity is not configured")
    root = f"/repos/{REPOSITORY}"
    artifact_name = f"cryptopulse-source-only-promotion-{run_id}-{run_attempt}"
    listing = github_json(f"{root}/actions/runs/{run_id}/artifacts?per_page=100")
    _require(isinstance(listing, dict) and isinstance(listing.get("artifacts"), list),
             "promotion artefact listing is invalid")
    matches = [x for x in listing["artifacts"]
               if isinstance(x, dict) and x.get("name") == artifact_name]
    if not matches:
        return None
    _require(len(matches) == 1, "ambiguous source-only promotion artefact")
    artifact = matches[0]
    _require(artifact.get("expired") is False and
             type(artifact.get("id")) is int and artifact["id"] > 0,
             "source-only promotion artefact is expired or invalid")
    owner = artifact.get("workflow_run")
    _require(isinstance(owner, dict) and owner.get("id") == run_id,
             "promotion artefact belongs to another workflow run")
    _require(isinstance(receipt_bytes, bytes) and bool(receipt_bytes),
             "promoted source has no exact accepted-hour receipt")
    _require(isinstance(snapshot_bytes, bytes) and bool(snapshot_bytes) and
             isinstance(intent_bytes, bytes) and bool(intent_bytes),
             "promoted source has no immutable intent or snapshot bytes")

    promotion, promotion_digest = _artifact_json(
        github_bytes(f"{root}/actions/artifacts/{artifact['id']}/zip", None))
    source_run = github_json(f"{root}/actions/runs/{run_id}")
    _require(isinstance(source_run, dict) and source_run.get("id") == run_id
             and source_run.get("run_attempt") == run_attempt
             and source_run.get("status") == "completed"
             and source_run.get("conclusion") == "success"
             and source_run.get("repository", {}).get("full_name") == REPOSITORY,
             "source workflow run is not a completed successful exact run")
    if owner.get("head_sha") is not None:
        _require(owner["head_sha"] == source_run.get("head_sha"),
                 "promotion artefact workflow-head identity differs")
    try:
        intent = json.loads(intent_bytes)
        receipt = json.loads(receipt_bytes)
        bound = verify_bundle(
            intent, receipt, source_run, snapshot_bytes,
            snapshot_file, Path(repo_root) / "config/crypto_sources.yml",
        )
    except (ValueError, TypeError, OSError, KeyError) as exc:
        raise PromotionProofError("immutable intent, accepted-hour receipt or source quality invalid") from exc

    path = bound["source_path"]
    digest = bound["snapshot_sha256"]
    _require(promotion.get("status") == "merged"
             and promotion.get("source_run_id") == str(run_id)
             and promotion.get("source_path") == path
             and promotion.get("snapshot_sha256") == digest,
             "promotion claim contradicts verified source intent/receipt")
    _require(isinstance(promotion.get("pull_request_number"), str)
             and promotion["pull_request_number"].isdigit()
             and int(promotion["pull_request_number"]) > 0
             and isinstance(promotion.get("independent_ci_run_id"), str)
             and promotion["independent_ci_run_id"].isdigit()
             and int(promotion["independent_ci_run_id"]) > 0,
             "promotion PR or CI identity invalid")
    pr_number = int(promotion["pull_request_number"])
    ci_id = int(promotion["independent_ci_run_id"])
    base = _sha1(promotion.get("expected_main_base_sha"), "promotion base SHA invalid")
    head = _sha1(promotion.get("candidate_head_sha"), "promotion candidate SHA invalid")
    merge = _sha1(promotion.get("merge_commit_sha"), "promotion merge SHA invalid")
    branch = f"automation/source-only-{run_id}-{run_attempt}"
    source_head = _sha1(source_run.get("head_sha"), "source run head SHA invalid")

    ancestor = github_json(f"{root}/compare/{source_head}...{base}")
    _require(isinstance(ancestor, dict)
             and ancestor.get("status") in ("ahead", "identical")
             and ancestor.get("base_commit", {}).get("sha") == source_head
             and ancestor.get("merge_base_commit", {}).get("sha") == source_head,
             "promotion base does not descend from source workflow head")

    pr = github_json(f"{root}/pulls/{pr_number}")
    pr_head, pr_base = pr.get("head"), pr.get("base")
    _require(pr.get("number") == pr_number
             and pr.get("state") == "closed" and pr.get("merged") is True
             and isinstance(pr.get("merged_at"), str) and bool(pr["merged_at"])
             and pr.get("merge_commit_sha") == merge
             and pr.get("user", {}).get("login") == app_slug + "[bot]"
             and pr.get("merged_by", {}).get("login") == app_slug + "[bot]"
             and isinstance(pr_head, dict) and isinstance(pr_base, dict)
             and pr_head.get("sha") == head and pr_head.get("ref") == branch
             and pr_base.get("sha") == base and pr_base.get("ref") == "main"
             and pr_head.get("repo", {}).get("id") == pr_base.get("repo", {}).get("id")
             and pr_base.get("repo", {}).get("full_name") == REPOSITORY,
             "merged promotion PR identity, author or exact head/base differs")
    body = pr.get("body")
    _require(isinstance(body, str)
             and f"Immutable ingestion run: {run_id}, attempt {run_attempt}." in body
             and f"Snapshot SHA-256: `{digest}`." in body
             and f"Exact source path: `{path}`." in body
             and f"Expected protected-main base: `{base}`." in body,
             "promotion PR body fails immutable source binding")
    files = github_json(f"{root}/pulls/{pr_number}/files?per_page=100")
    _require(isinstance(files, list) and len(files) == 1
             and files[0].get("filename") == path
             and files[0].get("status") == "added"
             and files[0].get("deletions") == 0,
             "promotion PR is not exactly one added source JSON")

    ci = github_json(f"{root}/actions/runs/{ci_id}")
    _require(isinstance(ci, dict) and ci.get("id") == ci_id
             and ci.get("name") == "Validate CryptoPulse PR"
             and ci.get("path") == APPROVED_WORKFLOW
             and ci.get("event") == "pull_request"
             and ci.get("head_sha") == head and ci.get("head_branch") == branch
             and ci.get("status") == "completed" and ci.get("conclusion") == "success"
             and ci.get("repository", {}).get("full_name") == REPOSITORY
             and type(ci.get("check_suite_id")) is int,
             "required independent exact-head PR CI did not succeed")
    # Use the run-owned jobs endpoint (actions:read already granted), rather
    # than expanding workflow permissions merely to read the Checks API.
    jobs = github_json(f"{root}/actions/runs/{ci_id}/jobs?per_page=100")
    _require(isinstance(jobs, dict) and isinstance(jobs.get("jobs"), list)
             and len(jobs["jobs"]) <= 100, "exact-head CI jobs missing or truncated")
    matching = [j for j in jobs["jobs"] if isinstance(j, dict)
                and j.get("name") == "Build site and check generated output"
                and j.get("run_id") == ci_id
                and j.get("status") == "completed"
                and j.get("conclusion") == "success"
                and j.get("head_sha") == head]
    _require(len(matching) == 1, "required exact-head CI job is absent or ambiguous")

    commit = github_json(f"{root}/commits/{merge}")
    parents = commit.get("parents", []) if isinstance(commit, dict) else []
    _require(commit.get("sha") == merge and isinstance(parents, list)
             and [x.get("sha") for x in parents] == [base, head],
             "protected-main promotion merge parents differ")
    main_history = github_json(f"{root}/compare/{merge}...{expected_main_sha}")
    _require(isinstance(main_history, dict)
             and main_history.get("status") in ("ahead", "identical")
             and main_history.get("base_commit", {}).get("sha") == merge
             and main_history.get("merge_base_commit", {}).get("sha") == merge,
             "promotion merge is not an ancestor of pinned protected main")

    published = github_bytes(
        f"{root}/contents/{path}?ref={merge}", "application/vnd.github.raw+json")
    _require(published == snapshot_bytes and _sha256(published) == digest,
             "promoted protected-main JSON does not match original retained bytes")
    return {
        "contract": CONTRACT,
        "run_id": run_id, "run_attempt": run_attempt,
        "source_workflow_id": source_run["workflow_id"],
        "source_workflow_head_sha": source_head,
        "source_event": source_run["event"],
        "publication_intent_sha256": _sha256(intent_bytes),
        "accepted_hour_receipt_sha256": _sha256(receipt_bytes),
        "snapshot_sha256": digest,
        "source_path": path,
        "source_hour": bound["source_hour"],
        "original_snapshot_commit_sha": bound["intent_snapshot_commit_sha"],
        "promotion_artifact_id": artifact["id"],
        "promotion_artifact_sha256": promotion_digest,
        "promotion_pr_number": pr_number,
        "candidate_head_sha": head,
        "expected_main_base_sha": base,
        "merge_commit_sha": merge,
        "independent_ci_run_id": ci_id,
        "protected_main_sha": expected_main_sha,
        "verified": True,
    }
