"""Fail-closed trusted-main provenance guard for the Phase 9 protected target."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
import time
import urllib.error
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from issueops_dispatch import core
from issueops_dispatch import protected_dispatch as dispatch
from issueops_dispatch import target_guard as common
from issueops_dispatch.runner import load_registry

ATTESTATION_ENUMERATIONS = 12
ATTESTATION_INTERVAL_SECONDS = 5


def verify_asset_checksum(path: Path) -> None:
    if not path.is_file():
        raise common.GuardError("pinned gh release asset is missing")
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != common.PINNED_GH_SHA256:
        raise common.GuardError("pinned gh release asset SHA-256 mismatch")


def verify_dispatcher_workflow_hash(
    record: Mapping[str, Any], repository_root: Path
) -> None:
    path = repository_root / core.DISPATCHER_WORKFLOW_PATH
    if not path.is_file():
        raise common.GuardError("frozen dispatcher workflow is missing")
    actual = core.sha256_bytes(path.read_bytes())
    if actual != record["dispatcher_workflow_sha256"]:
        raise common.GuardError(
            "dispatcher workflow SHA-256 does not match source-controlled authority"
        )


def _is_initial_attestation_subject_404(
    error: common.GuardError,
    client: common.GitHubReadAPI,
    subject_sha256: str,
) -> bool:
    cause = error.__cause__
    if not isinstance(cause, urllib.error.HTTPError) or cause.code != 404:
        return False
    try:
        parsed = urllib.parse.urlparse(cause.geturl())
        query = urllib.parse.parse_qs(
            parsed.query, keep_blank_values=True, strict_parsing=True
        )
    except (AttributeError, ValueError):
        return False
    expected_path = (
        f"/repos/{client.repository}/attestations/sha256:{subject_sha256}"
    )
    return (
        parsed.scheme == "https"
        and parsed.netloc == "api.github.com"
        and parsed.path == expected_path
        and not parsed.params
        and not parsed.fragment
        and query
        == {
            "predicate_type": [core.PREDICATE_TYPE],
            "per_page": ["100"],
        }
    )


def wait_for_attestations(
    client: common.GitHubReadAPI,
    subject_sha256: str,
    *,
    enumerations: int = ATTESTATION_ENUMERATIONS,
    interval_seconds: int = ATTESTATION_INTERVAL_SECONDS,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> list[Mapping[str, Any]]:
    if enumerations < 1:
        raise common.GuardError("attestation enumeration bound must be positive")
    for attempt in range(enumerations):
        try:
            attestations = client.list_attestations(subject_sha256)
        except common.GuardError as exc:
            if not _is_initial_attestation_subject_404(
                exc, client, subject_sha256
            ):
                raise
            attestations = []
        if attestations:
            return attestations
        if attempt + 1 < enumerations:
            sleep_fn(interval_seconds)
    raise common.GuardError(
        "no dispatcher attestation became available within the bounded wait"
    )


def verify_statement_and_predicate_main(
    statement: Mapping[str, Any],
    *,
    resolution: core.Resolution,
    target_run_id: int,
    dispatcher_run_id: int,
) -> None:
    if statement.get("predicateType") != core.PREDICATE_TYPE:
        raise common.GuardError("verified statement predicate type mismatch")
    subjects = common._list(statement.get("subject"), "verified statement subject")
    if len(subjects) != 1:
        raise common.GuardError(
            "verified statement must contain exactly one subject"
        )
    subject = common._mapping(subjects[0], "verified subject")
    digest = common._mapping(subject.get("digest"), "verified subject digest")
    expected_subject = dispatch.canonical_subject_main(
        resolution=resolution, target_run={"id": target_run_id}
    )
    expected_digest = core.sha256_bytes(
        core.canonical_json_bytes(expected_subject)
    )
    if digest.get("sha256") != expected_digest:
        raise common.GuardError("verified attestation subject digest mismatch")

    predicate = common._mapping(
        statement.get("predicate"), "verified statement predicate"
    )
    required = {
        "schema": core.ATTESTATION_SCHEMA,
        "repository": core.REPOSITORY,
        "repository_id": core.REPOSITORY_ID,
        "repository_owner_id": core.REPOSITORY_OWNER_ID,
        "authorisation_id": resolution.record["authorisation_id"],
        "authorisation_sha": resolution.source_sha,
        "authorisation_record_sha256": resolution.record_sha256,
        "triggering_issue": resolution.record["governing_issue"],
        "triggering_comment_body_sha256": resolution.comment_body_sha256,
        "actor_login": resolution.record["actor_login"],
        "actor_user_id": resolution.record["actor_user_id"],
        "required_author_association": resolution.record[
            "required_author_association"
        ],
        "execution_ref": resolution.execution_ref,
        "dispatcher_workflow_path": core.DISPATCHER_WORKFLOW_PATH,
        "dispatcher_workflow_sha": resolution.source_sha,
        "dispatcher_run_id": dispatcher_run_id,
        "dispatcher_run_attempt": 1,
        "target_workflow_id": resolution.record["target_workflow_id"],
        "target_workflow_path": resolution.record["target_workflow_path"],
        "target_run_id": target_run_id,
        "target_ref": dispatch.TARGET_REF,
        "target_sha": resolution.source_sha,
        "target_event": "workflow_dispatch",
        "fixed_inputs_sha256": resolution.fixed_inputs_sha256,
    }
    for key, value in required.items():
        if predicate.get(key) != value:
            raise common.GuardError(
                f"signed dispatcher predicate {key} mismatch"
            )
    comment_id = predicate.get("triggering_comment_id")
    if not isinstance(comment_id, int) or comment_id <= 0:
        raise common.GuardError(
            "signed dispatcher predicate has invalid triggering_comment_id"
        )


def verify_gh_result_main(
    payload: Any,
    *,
    resolution: core.Resolution,
    target_run_id: int,
    run_lookup: Callable[[int], Mapping[str, Any]],
) -> int:
    entries = common._list(payload, "gh attestation verification output")
    if len(entries) != 1:
        raise common.GuardError(
            "one candidate bundle must produce exactly one verification result"
        )
    result = common._mapping(entries[0], "verification result entry")
    verification = common._mapping(
        result.get("verificationResult"), "verificationResult"
    )
    signature = common._mapping(
        verification.get("signature"), "verification signature"
    )
    certificate = common._mapping(
        signature.get("certificate"), "verification certificate"
    )
    timestamps = common._list(
        verification.get("verifiedTimestamps"), "verified timestamps"
    )
    if not timestamps:
        raise common.GuardError(
            "verified attestation contains no independently verified timestamp"
        )
    dispatcher_run_id = common.verify_certificate(
        certificate, source_sha=resolution.source_sha
    )
    run = run_lookup(dispatcher_run_id)
    common.verify_dispatcher_run(
        run,
        dispatcher_run_id=dispatcher_run_id,
        source_sha=resolution.source_sha,
    )
    statement = common._mapping(
        verification.get("statement"), "verified statement"
    )
    verify_statement_and_predicate_main(
        statement,
        resolution=resolution,
        target_run_id=target_run_id,
        dispatcher_run_id=dispatcher_run_id,
    )
    return dispatcher_run_id


def execute_guard(
    *,
    repository_root: Path,
    authorisation_id: str,
    github_ref: str,
    github_sha: str,
    workflow_sha: str,
    run_id: int,
    run_attempt: int,
    repository: str,
    token: str,
    gh_binary: Path,
    now: datetime,
    api: common.GitHubReadAPI | None = None,
    sleep_fn: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    if repository != core.REPOSITORY:
        raise common.GuardError(
            "protected target is running in the wrong repository"
        )
    if run_attempt != 1:
        raise common.GuardError("protected target reruns are not authorised")
    if github_ref != dispatch.TARGET_REF:
        raise common.GuardError(
            "protected target must execute from trusted main"
        )
    if not core.SHA40_RE.fullmatch(github_sha):
        raise common.GuardError(
            "protected target source SHA is not a full lowercase commit SHA"
        )
    if workflow_sha != github_sha:
        raise common.GuardError(
            "github.workflow_sha must equal github.sha on trusted main"
        )
    if (
        not isinstance(authorisation_id, str)
        or not core.AUTHORISATION_ID_RE.fullmatch(authorisation_id)
    ):
        raise common.GuardError("invalid protected authorisation_id input")

    registry = load_registry(
        repository_root / ".github/issueops-workflow-dispatch.yml"
    )
    record = common.select_authorisation(
        registry, authorisation_id=authorisation_id, now=now
    )
    common.verify_workflow_hash(
        record, repository_root / common.TARGET_WORKFLOW_PATH
    )
    verify_dispatcher_workflow_hash(record, repository_root)

    execution_ref = (
        f"refs/tags/issueops/dispatch/{authorisation_id}--sha-{github_sha}"
    )
    resolution = common.build_resolution(
        record=record,
        source_sha=github_sha,
        execution_ref=execution_ref,
    )

    client = api or common.GitHubReadAPI(repository, token)
    common.verify_tag_ref(
        client.get_tag(resolution.execution_tag),
        execution_ref=resolution.execution_ref,
        source_sha=github_sha,
    )
    common.verify_ruleset(
        client.get_ruleset(record["execution_tag_ruleset_id"]), record
    )

    subject = dispatch.canonical_subject_main(
        resolution=resolution, target_run={"id": run_id}
    )
    subject_bytes = core.canonical_json_bytes(subject)
    subject_digest = core.sha256_bytes(subject_bytes)
    attestations = wait_for_attestations(
        client, subject_digest, sleep_fn=sleep_fn
    )

    common.verify_pinned_gh(gh_binary)
    verified: list[tuple[int, int]] = []
    signer_verified_but_conflicting = 0
    with tempfile.TemporaryDirectory(
        prefix="issueops-target-guard-main-"
    ) as tmp:
        temp_root = Path(tmp)
        subject_path = temp_root / "dispatch-subject.json"
        subject_path.write_bytes(subject_bytes)
        for index, item in enumerate(attestations):
            bundle_url = item.get("bundle_url")
            if not isinstance(bundle_url, str):
                raise common.GuardError(
                    "attestation collection contains an item without bundle_url"
                )
            bundle_path = temp_root / f"bundle-{index}.json"
            bundle_path.write_bytes(client.fetch_bundle(bundle_url))
            payload = common.run_gh_verify(
                gh_binary=gh_binary,
                subject_path=subject_path,
                bundle_path=bundle_path,
                source_sha=github_sha,
                token=token,
            )
            if payload is None:
                continue
            try:
                dispatcher_run_id = verify_gh_result_main(
                    payload,
                    resolution=resolution,
                    target_run_id=run_id,
                    run_lookup=client.get_run_attempt,
                )
            except common.GuardError:
                signer_verified_but_conflicting += 1
                continue
            verified.append((index, dispatcher_run_id))

    if signer_verified_but_conflicting:
        raise common.GuardError(
            "a cryptographically verified canonical-signer receipt conflicts "
            "with the frozen target authority"
        )
    if len(verified) != 1:
        raise common.GuardError(
            "protected target requires exactly one qualifying canonical "
            "dispatcher receipt"
        )

    return {
        "authorisation_id": authorisation_id,
        "authorisation_sha": github_sha,
        "execution_ref": resolution.execution_ref,
        "target_ref": dispatch.TARGET_REF,
        "target_run_id": run_id,
        "subject_sha256": subject_digest,
        "dispatcher_run_id": verified[0][1],
        "ruleset_id": record["execution_tag_ruleset_id"],
        "ruleset_name": record["execution_tag_ruleset_name"],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    asset = sub.add_parser("verify-asset")
    asset.add_argument("--asset", type=Path, required=True)

    guard = sub.add_parser("guard")
    guard.add_argument("--repository-root", type=Path, default=Path("."))
    guard.add_argument("--authorisation-id", required=True)
    guard.add_argument("--gh-bin", type=Path, required=True)
    guard.add_argument("--output", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(sys.argv[1:] if argv is None else argv)
    try:
        if args.command == "verify-asset":
            verify_asset_checksum(args.asset)
            return 0
        result = execute_guard(
            repository_root=args.repository_root,
            authorisation_id=args.authorisation_id,
            github_ref=os.environ["GITHUB_REF"],
            github_sha=os.environ["GITHUB_SHA"],
            workflow_sha=os.environ["GITHUB_WORKFLOW_SHA"],
            run_id=int(os.environ["GITHUB_RUN_ID"]),
            run_attempt=int(os.environ["GITHUB_RUN_ATTEMPT"]),
            repository=os.environ["GITHUB_REPOSITORY"],
            token=os.environ["GITHUB_TOKEN"],
            gh_binary=args.gh_bin,
            now=datetime.now(timezone.utc),
        )
    except (KeyError, ValueError, common.GuardError) as exc:
        print(
            f"IssueOps trusted-main target provenance rejected: {exc}",
            file=sys.stderr,
        )
        return 1
    payload = json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
