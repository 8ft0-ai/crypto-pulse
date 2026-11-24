#!/usr/bin/env python3
"""Build the immutable metadata for a daily review PR."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from daily_publication import build_attestation


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("date", "trusted-main-sha", "main-base-sha", "records", "report",
                 "candidate-head-sha", "candidate-branch", "app-slug", "output"):
        parser.add_argument("--" + name, required=True)
    for name in ("pr-number", "workflow-id", "run-id", "run-attempt", "app-actor-id"):
        parser.add_argument("--" + name, type=int, required=True)
    args = parser.parse_args()
    records = json.loads(Path(args.records).read_text(encoding="utf-8"))
    config = subprocess.run(["git", "show", f"{args.trusted_main_sha}:config/crypto_sources.yml"],
                            check=True, capture_output=True).stdout
    hours = [{"hour": item["hour"], "status": item["status"],
              "path": item.get("path"), "sha256": item.get("sha256")}
             for item in records]
    report = Path(args.report)
    attestation = build_attestation(
        reporting_date_utc=args.date, trusted_main_sha=args.trusted_main_sha,
        expected_main_base_sha=args.main_base_sha,
        source_config_sha256=hashlib.sha256(config).hexdigest(), hours=hours,
        report_path=report.as_posix(), report_bytes=report.read_bytes(),
        candidate_head_sha=args.candidate_head_sha,
        candidate_branch=args.candidate_branch, pull_request_number=args.pr_number,
        generation_workflow_id=args.workflow_id, generation_run_id=args.run_id,
        generation_run_attempt=args.run_attempt,
        publication_app_actor_id=args.app_actor_id,
        publication_app_slug=args.app_slug)
    Path(args.output).write_text(json.dumps(attestation, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
