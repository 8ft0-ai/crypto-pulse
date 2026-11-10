"""Trusted-main target adapter for protected IssueOps dispatches."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Mapping

from issueops_dispatch import core, runner

TARGET_BRANCH = "main"
TARGET_REF = "refs/heads/main"
AUTHORISATION_INPUT = "issueops_authorisation_id"


class GitHubAPI(runner.GitHubAPI):
    """Dispatcher API with one trusted-main target dispatch write."""

    def dispatch_main_once(
        self,
        workflow_id: int,
        fixed_inputs: Mapping[str, Any],
        authorisation_id: str,
    ) -> Mapping[str, Any]:
        if AUTHORISATION_INPUT in fixed_inputs:
            raise core.ContractError(
                f"fixed_inputs may not override reserved {AUTHORISATION_INPUT}"
            )
        inputs = dict(fixed_inputs)
        inputs[AUTHORISATION_INPUT] = authorisation_id
        _, payload = self._request(
            "POST",
            f"/actions/workflows/{workflow_id}/dispatches",
            body={"ref": TARGET_BRANCH, "inputs": inputs},
            expected=(200,),
        )
        return runner._mapping(payload, "workflow dispatch response")


def validate_target_run_main(
    run: Mapping[str, Any],
    resolution: core.Resolution,
    *,
    expected_run_id: int | None = None,
) -> None:
    record = resolution.record
    run_id = run.get("id")
    if not isinstance(run_id, int):
        raise core.ContractError("target run id is missing")
    if expected_run_id is not None and run_id != expected_run_id:
        raise core.ContractError("target run id does not match direct dispatch identity")
    repository = run.get("repository")
    if not isinstance(repository, Mapping):
        raise core.ContractError("target run repository identity is missing")
    if (
        repository.get("full_name") != core.REPOSITORY
        or repository.get("id") != core.REPOSITORY_ID
    ):
        raise core.ContractError("target run repository identity mismatch")
    if run.get("workflow_id") != record["target_workflow_id"]:
        raise core.ContractError("target run workflow id mismatch")
    if run.get("path") != record["target_workflow_path"]:
        raise core.ContractError("target run workflow path mismatch")
    if run.get("event") != "workflow_dispatch":
        raise core.ContractError("target run event mismatch")
    if run.get("run_attempt") != 1:
        raise core.ContractError("target rerun is never authorised")
    if run.get("head_sha") != resolution.source_sha:
        raise core.ContractError("target run SHA mismatch")
    if run.get("head_branch") != TARGET_BRANCH:
        raise core.ContractError("target run ref is not trusted main")


def _reconcile_ambiguous_tag_creation(
    api: GitHubAPI,
    resolution: core.Resolution,
    cause: runner.AmbiguousGitHubResponse,
) -> None:
    try:
        reconciled = api.get_tag(resolution.execution_tag)
    except core.ContractError as exc:
        raise core.ContractError(
            "ambiguous execution-tag creation; exact-ref reconciliation unavailable; "
            "no continuation ownership"
        ) from exc
    if reconciled is None:
        raise core.ContractError(
            "ambiguous execution-tag creation; canonical ref absent after bounded "
            "reconciliation; no continuation ownership"
        ) from cause
    try:
        runner.validate_tag_ref(reconciled, resolution)
    except core.ContractError as exc:
        raise core.ContractError(
            "ambiguous execution-tag creation; canonical ref exists but is conflicting; "
            "authority consumed/conflicted and no continuation ownership"
        ) from exc
    raise core.ContractError(
        "ambiguous execution-tag creation; exact canonical ref exists; authority consumed "
        "and no continuation ownership"
    ) from cause


def consume_and_dispatch_main(
    *,
    api: GitHubAPI,
    event: Mapping[str, Any],
    resolution: core.Resolution,
) -> Mapping[str, Any]:
    runner.validate_target_workflow(api, resolution)
    ruleset_id = resolution.record["execution_tag_ruleset_id"]
    runner.validate_runtime_ruleset(api.get_ruleset(ruleset_id), resolution)

    if api.get_tag(resolution.execution_tag) is not None:
        raise core.ContractError(
            "execution tag already exists; authorisation is consumed or conflicted"
        )

    live_comment = api.get_comment(int(event["comment"]["id"]))
    core.ensure_comment_unchanged(event, live_comment, resolution)

    try:
        created = api.create_tag_once(
            resolution.execution_ref, resolution.source_sha
        )
    except runner.AmbiguousGitHubResponse as exc:
        _reconcile_ambiguous_tag_creation(api, resolution, exc)
        raise AssertionError("ambiguous reconciliation must terminate")

    try:
        runner.validate_tag_ref(created, resolution)
    except core.ContractError as exc:
        ambiguity = runner.AmbiguousGitHubResponse(
            "create-reference returned an unverifiable HTTP 201 response body"
        )
        ambiguity.__cause__ = exc
        _reconcile_ambiguous_tag_creation(api, resolution, ambiguity)
        raise AssertionError("ambiguous reconciliation must terminate")

    read_back = api.get_tag(resolution.execution_tag)
    if read_back is None:
        raise core.ContractError("execution tag disappeared after creation")
    runner.validate_tag_ref(read_back, resolution)

    runner.validate_runtime_ruleset(api.get_ruleset(ruleset_id), resolution)
    final_tag = api.get_tag(resolution.execution_tag)
    if final_tag is None:
        raise core.ContractError("execution tag disappeared before dispatch")
    runner.validate_tag_ref(final_tag, resolution)

    runner.validate_target_workflow(api, resolution)

    response = api.dispatch_main_once(
        resolution.record["target_workflow_id"],
        resolution.record["fixed_inputs"],
        resolution.record["authorisation_id"],
    )
    run_id = response.get("workflow_run_id")
    run_url = response.get("run_url")
    html_url = response.get("html_url")
    if (
        not isinstance(run_id, int)
        or not isinstance(run_url, str)
        or not isinstance(html_url, str)
    ):
        raise core.ContractError("workflow dispatch did not return direct run identity")
    run = api.get_run_attempt(run_id, 1)
    validate_target_run_main(run, resolution, expected_run_id=run_id)
    return {
        "workflow_run_id": run_id,
        "run_url": run_url,
        "html_url": html_url,
        "target_run": dict(run),
    }


def canonical_subject_main(
    *, resolution: core.Resolution, target_run: Mapping[str, Any]
) -> dict[str, Any]:
    data = {
        "schema": core.ATTESTATION_SCHEMA,
        "repository": core.REPOSITORY,
        "repository_id": core.REPOSITORY_ID,
        "authorisation_id": resolution.record["authorisation_id"],
        "authorisation_sha": resolution.source_sha,
        "execution_ref": resolution.execution_ref,
        "target_workflow_id": resolution.record["target_workflow_id"],
        "target_workflow_path": resolution.record["target_workflow_path"],
        "target_run_id": target_run["id"],
        "target_ref": TARGET_REF,
        "target_sha": resolution.source_sha,
    }
    if tuple(data) != core.SUBJECT_KEYS:
        raise AssertionError("canonical subject field order drift")
    return data


def canonical_predicate_main(
    *,
    resolution: core.Resolution,
    event: Mapping[str, Any],
    dispatcher_run_id: int,
    dispatcher_run_attempt: int,
    target_run: Mapping[str, Any],
) -> dict[str, Any]:
    data = {
        "schema": core.ATTESTATION_SCHEMA,
        "repository": core.REPOSITORY,
        "repository_id": core.REPOSITORY_ID,
        "repository_owner_id": core.REPOSITORY_OWNER_ID,
        "authorisation_id": resolution.record["authorisation_id"],
        "authorisation_sha": resolution.source_sha,
        "authorisation_record_sha256": resolution.record_sha256,
        "triggering_issue": resolution.record["governing_issue"],
        "triggering_comment_id": event["comment"]["id"],
        "triggering_comment_body_sha256": resolution.comment_body_sha256,
        "actor_login": core.ACTOR_LOGIN,
        "actor_user_id": core.ACTOR_USER_ID,
        "required_author_association": core.AUTHOR_ASSOCIATION,
        "execution_ref": resolution.execution_ref,
        "dispatcher_workflow_path": core.DISPATCHER_WORKFLOW_PATH,
        "dispatcher_workflow_sha": resolution.source_sha,
        "dispatcher_run_id": dispatcher_run_id,
        "dispatcher_run_attempt": dispatcher_run_attempt,
        "target_workflow_id": resolution.record["target_workflow_id"],
        "target_workflow_path": resolution.record["target_workflow_path"],
        "target_run_id": target_run["id"],
        "target_ref": TARGET_REF,
        "target_sha": resolution.source_sha,
        "target_event": "workflow_dispatch",
        "fixed_inputs_sha256": resolution.fixed_inputs_sha256,
    }
    if tuple(data) != core.PREDICATE_KEYS:
        raise AssertionError("canonical predicate field order drift")
    return data


def write_attestation_inputs_main(
    *,
    event: Mapping[str, Any],
    resolution: core.Resolution,
    dispatcher_run_id: int,
    dispatcher_run_attempt: int,
    target_run: Mapping[str, Any],
    output_dir: Path,
) -> tuple[Path, Path]:
    if dispatcher_run_attempt != 1:
        raise core.ContractError("dispatcher rerun may not sign")
    validate_target_run_main(target_run, resolution)
    subject = canonical_subject_main(resolution=resolution, target_run=target_run)
    predicate = canonical_predicate_main(
        resolution=resolution,
        event=event,
        dispatcher_run_id=dispatcher_run_id,
        dispatcher_run_attempt=dispatcher_run_attempt,
        target_run=target_run,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    subject_path = output_dir / "issueops-dispatch-target-run.json"
    predicate_path = output_dir / "issueops-dispatch-predicate.json"
    subject_path.write_bytes(core.canonical_json_bytes(subject))
    predicate_path.write_bytes(core.canonical_json_bytes(predicate))
    return subject_path, predicate_path


def command_consume(args: argparse.Namespace) -> int:
    resolution = runner.resolve_from_files(args)
    if resolution is None:
        raise core.ContractError("side-effect job has no active authorisation")
    event = runner.load_event(Path(args.event))
    api = GitHubAPI(args.repository, args.token)
    result = consume_and_dispatch_main(
        api=api, event=event, resolution=resolution
    )
    runner._github_output("target_run_id", str(result["workflow_run_id"]))
    runner._github_output("target_run_url", str(result["html_url"]))
    return 0


def command_prepare_attestation(args: argparse.Namespace) -> int:
    resolution = runner.resolve_from_files(args)
    if resolution is None:
        raise core.ContractError("signing job has no active authorisation")
    event = runner.load_event(Path(args.event))
    api = GitHubAPI(args.repository, args.token)
    run = api.get_run_attempt(args.target_run_id, 1)
    validate_target_run_main(
        run, resolution, expected_run_id=args.target_run_id
    )
    subject, predicate = write_attestation_inputs_main(
        event=event,
        resolution=resolution,
        dispatcher_run_id=args.dispatcher_run_id,
        dispatcher_run_attempt=args.run_attempt,
        target_run=run,
        output_dir=Path(args.output_dir),
    )
    runner._github_output("subject_path", str(subject))
    runner._github_output("predicate_path", str(predicate))
    runner._github_output(
        "subject_sha256", core.sha256_bytes(subject.read_bytes())
    )
    runner._github_output(
        "predicate_type", resolution.record["attestation_predicate_type"]
    )
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    def common(target: argparse.ArgumentParser) -> None:
        target.add_argument("--event", required=True)
        target.add_argument("--config", required=True)
        target.add_argument("--dispatcher-workflow", required=True)
        target.add_argument("--source-sha", required=True)
        target.add_argument("--run-attempt", required=True, type=int)

    consume = sub.add_parser("consume")
    common(consume)
    consume.add_argument("--repository", required=True)
    consume.add_argument("--token", required=True)
    consume.set_defaults(func=command_consume)

    sign = sub.add_parser("prepare-attestation")
    common(sign)
    sign.add_argument("--repository", required=True)
    sign.add_argument("--token", required=True)
    sign.add_argument("--target-run-id", required=True, type=int)
    sign.add_argument("--dispatcher-run-id", required=True, type=int)
    sign.add_argument("--output-dir", required=True)
    sign.set_defaults(func=command_prepare_attestation)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return args.func(args)
    except core.ContractError as exc:
        print(f"IssueOps trusted-main dispatch rejected: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
