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
from datetime import datetime
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



def _complete_run_listing(
    github_json: Callable[[str], Any], endpoint: str, field: str,
) -> list[dict[str, Any]]:
    """Require stable, unique records across complete bounded Actions pages.

    For multi-page results, re-read each page and require byte-for-byte
    equivalent decoded records. This rejects observed pagination drift, not
    claims that GitHub provides an atomic snapshot of a changing collection.
    """
    def read_pages() -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        seen: set[int] = set()
        total: int | None = None
        for page in range(1, 21):
            suffix = "?per_page=100" + (f"&page={page}" if page > 1 else "")
            response = github_json(endpoint + suffix)
            _require(isinstance(response, dict), f"{field} listing is invalid")
            count = response.get("total_count")
            items = response.get(field)
            _require(type(count) is int and 0 <= count <= 2000
                     and isinstance(items, list) and len(items) <= 100
                     and all(isinstance(item, dict) for item in items),
                     f"{field} listing is invalid or exceeds the bounded limit")
            if total is None:
                total = count
            _require(count == total, f"{field} listing changed during pagination")
            _require(len(items) == min(100, total - len(result)),
                     f"{field} listing is incomplete or inconsistent")
            for item in items:
                record_id = item.get("id")
                _require(type(record_id) is int and record_id > 0
                         and record_id not in seen,
                         f"{field} listing has invalid or repeated record IDs")
                seen.add(record_id)
            result.extend(items)
            if len(result) == total:
                return result
        raise PromotionProofError(f"{field} listing exceeds bounded pagination")

    first = read_pages()
    if len(first) > 100:
        _require(read_pages() == first,
                 f"{field} listing changed across bounded consistency re-read")
    return first


def _github_time(value: Any, label: str) -> datetime:
    _require(isinstance(value, str)
             and re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value)
             is not None, f"{label} is missing or invalid")
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as exc:
        raise PromotionProofError(f"{label} is invalid") from exc


def _ci_pr_link(
    ci: Mapping[str, Any], pr: Mapping[str, Any], pr_number: int,
    head: str, branch: str, github_json: Callable[[str], Any], root: str,
) -> None:
    """Bind exact-head CI to a unique PR even after GitHub clears run links.

    GitHub clears workflow_run.pull_requests on some merged/deleted PR
    branches. When that authoritative field is empty, consult the commit's
    independently reported, unique associated PR. Both paths fail closed
    on absent or ambiguous PR identity.
    """
    # The workflow base repository does not identify the source that supplied
    # the code. Require the actual CI head repository to be the same trusted,
    # in-repository promotion PR head (not merely a matching fork commit).
    repo = pr["head"]["repo"]
    base_repo = pr["base"]["repo"]
    ci_head = ci.get("head_repository")
    ci_base = ci.get("repository")
    _require(isinstance(ci_head, dict) and isinstance(ci_base, dict)
             and type(repo.get("id")) is int and type(base_repo.get("id")) is int
             and repo["id"] == base_repo["id"]
             and repo.get("full_name") == REPOSITORY
             and ci_head.get("id") == repo["id"]
             and ci_head.get("full_name") == REPOSITORY
             and ci_base.get("id") == base_repo["id"]
             and ci_base.get("full_name") == REPOSITORY,
             "CI head repository does not match trusted promotion PR")

    created = _github_time(pr.get("created_at"), "promotion PR creation time")
    merged = _github_time(pr.get("merged_at"), "promotion PR merge time")
    ci_created = _github_time(ci.get("created_at"), "CI creation time")
    ci_started = _github_time(ci.get("run_started_at"), "CI start time")
    _require(created <= ci_created <= ci_started <= merged,
             "CI run occurred outside the promotion PR lifecycle")

    linked = ci.get("pull_requests")
    _require(isinstance(linked, list), "CI run PR association metadata is missing")
    if not linked:
        linked = github_json(f"{root}/commits/{head}/pulls?per_page=100")
        _require(isinstance(linked, list) and len(linked) < 100,
                 "CI commit PR association is missing, truncated or ambiguous")
    _require(len(linked) == 1 and isinstance(linked[0], dict),
             "CI run does not have a unique promotion PR association")
    association = linked[0]
    assoc_head = association.get("head")
    assoc_base = association.get("base")
    pr_head, pr_base = pr["head"], pr["base"]
    _require(
        association.get("number") == pr_number
        and isinstance(assoc_head, dict) and isinstance(assoc_base, dict)
        and assoc_head.get("sha") == head and assoc_head.get("ref") == branch
        and assoc_base.get("ref") == "main"
        and isinstance(assoc_head.get("repo"), dict)
        and isinstance(assoc_base.get("repo"), dict)
        and assoc_head["repo"].get("id") == pr_head["repo"].get("id")
        and assoc_base["repo"].get("id") == pr_base["repo"].get("id"),
        "CI evidence is associated with a different PR, branch or repository",
    )

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
    artifacts = _complete_run_listing(
        github_json, f"{root}/actions/runs/{run_id}/artifacts", "artifacts")
    matches = [x for x in artifacts if x.get("name") == artifact_name]
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
    _ci_pr_link(ci, pr, pr_number, head, branch, github_json, root)
    # Use the run-owned jobs endpoint (actions:read already granted), rather
    # than expanding workflow permissions merely to read the Checks API.
    jobs = _complete_run_listing(
        github_json, f"{root}/actions/runs/{ci_id}/jobs", "jobs")
    matching = [j for j in jobs if isinstance(j, dict)
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
    pinned = github_bytes(
        f"{root}/contents/{path}?ref={expected_main_sha}",
        "application/vnd.github.raw+json")
    _require(pinned == snapshot_bytes and _sha256(pinned) == digest,
             "pinned protected-main JSON does not match original retained bytes")
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
