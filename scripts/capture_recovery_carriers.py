#!/usr/bin/env python3
"""Capture explicit recovery decisions, plus one immutable owner-approved legacy exclusion.

Scheduled runs may reuse ONLY the already authorised, exact byte-bound terminal
exclusion for ingestion run 41724015748, and only while that run is in the
frozen source census. Other recovery still requires explicit manual dispatch.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import subprocess
from pathlib import Path
from typing import Any

PINNED_SOURCE_RUN = 41724015748
PINNED_COMMENT = 6841402278
PINNED_ISSUE = 523
PINNED_OWNER = "8ft0-ai"
PINNED_REPO = "8ft0-ai/crypto-pulse"
PINNED_FINGERPRINT = "705ac2b652ca552018b12628c8a92dff98836dfc42034361de5e5c8d698c0774"
PINNED_BODY_SHA256 = "f5a8efe94e6eaa928edd90ffde4eafd4b88f1d4039dde0613bd137d15e1f2257"


class RecoveryCaptureError(ValueError):
    pass


def ids_for_capture(event: str, raw: str, census: dict[str, Any]) -> list[int]:
    if event not in ("schedule", "workflow_dispatch"):
        raise RecoveryCaptureError("unsupported recovery event")
    if event == "schedule":
        if raw:
            raise RecoveryCaptureError("scheduled recovery IDs must be empty")
        runs = census.get("runs")
        if not isinstance(runs, list):
            raise RecoveryCaptureError("missing complete source-run census")
        if not all(isinstance(r, dict) and type(r.get("run_id")) is int for r in runs):
            raise RecoveryCaptureError("malformed source-run census")
        identities = [r["run_id"] for r in runs]
        if len(identities) != len(set(identities)):
            raise RecoveryCaptureError("duplicate source-run identity")
        return [PINNED_COMMENT] if PINNED_SOURCE_RUN in identities else []
    values = [x.strip() for x in re.split(r"[,\n]+", raw) if x.strip()]
    ids: list[int] = []
    for value in values:
        if not value.isdigit() or int(value) <= 0 or int(value) in ids:
            raise RecoveryCaptureError("invalid or duplicate explicit recovery comment ID")
        ids.append(int(value))
    return ids


def capture_comment(comment: dict[str, Any], comment_id: int, event: str,
                    repo: str) -> dict[str, Any]:
    if type(comment.get("id")) is not int or comment["id"] != comment_id:
        raise RecoveryCaptureError("comment ID mismatches requested recovery identity")
    issue_url = str(comment.get("issue_url", ""))
    match = re.fullmatch(r"https://api\.github\.com/repos/" + re.escape(repo) +
                         r"/issues/(\d+)", issue_url)
    if match is None:
        raise RecoveryCaptureError("recovery issue/repository identity invalid")
    body = comment.get("body")
    if not isinstance(body, str):
        raise RecoveryCaptureError("recovery decision has no exact UTF-8 body")
    raw = body.encode("utf-8")
    digest = hashlib.sha256(raw).hexdigest()
    author = str((comment.get("user") or {}).get("login", ""))
    if event == "schedule":
        if (repo != PINNED_REPO or comment_id != PINNED_COMMENT
                or int(match.group(1)) != PINNED_ISSUE
                or author != PINNED_OWNER or digest != PINNED_BODY_SHA256):
            raise RecoveryCaptureError("pinned owner exclusion identity/body drift")
        parsed = json.loads(body)
        if (parsed.get("contract") != "trusted-main-source-evidence-recovery-decision/v1"
                or parsed.get("disposition") != "exclude-from-accumulation"
                or parsed.get("blocker_fingerprint") != PINNED_FINGERPRINT
                or [x.get("run_id") for x in parsed.get("input_identities", [])] != [PINNED_SOURCE_RUN]):
            raise RecoveryCaptureError("pinned recovery content drift")
    return {
        "issue_number": int(match.group(1)),
        "comment_id": comment_id,
        "author_login": author,
        "body_base64": base64.b64encode(raw).decode("ascii"),
        "body_sha256": digest,
    }


def capture(repo: str, event: str, comment_ids: str, census: dict[str, Any]) -> list[dict[str, Any]]:
    if not re.fullmatch(r"[A-Za-z0-9-]+/[A-Za-z0-9_.-]+", repo):
        raise RecoveryCaptureError("invalid repository")
    if event == "schedule" and repo != PINNED_REPO:
        raise RecoveryCaptureError("foreign scheduled recovery repository")
    rows = []
    for comment_id in ids_for_capture(event, comment_ids, census):
        completed = subprocess.run(
            ["gh", "api", f"/repos/{repo}/issues/comments/{comment_id}"],
            check=True, text=True, capture_output=True,
        )
        rows.append(capture_comment(json.loads(completed.stdout), comment_id, event, repo))
    return rows


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repository", required=True)
    p.add_argument("--event", required=True)
    p.add_argument("--comment-ids", required=True)
    p.add_argument("--source-capture", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    try:
        census = json.loads(a.source_capture.read_text(encoding="utf-8"))
        rows = capture(a.repository, a.event, a.comment_ids, census)
        a.output.write_text(json.dumps(rows, sort_keys=True, separators=(",", ":")), encoding="utf-8")
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError, KeyError) as exc:
        print(f"recovery capture blocked: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
