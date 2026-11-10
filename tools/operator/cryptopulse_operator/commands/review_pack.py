"""Aggregate current candidate and exact-head CI evidence."""

from __future__ import annotations

from ..evidence import Evidence, Status
from ..github_read import GitHubReader, GitHubReadError, REPOSITORY
from ..process import ProcessRunner
from ..review_support import review_pack_snapshot, runtime_gate, ReviewSupportError


def run(pr_number: int, runner: ProcessRunner, github: GitHubReader) -> Evidence:
    target = {"kind": "pull-request-review-pack", "number": pr_number}
    gate = runtime_gate(runner, github)
    if gate.status is not None:
        return Evidence(
            command="review-pack",
            repository=REPOSITORY,
            invocation_target=target,
            runtime=gate.runtime,
            remote={},
            local={},
            status=gate.status,
            completeness={"complete": False, "runtime": gate.complete, "review_pack": False},
            assertions=gate.assertions,
            findings=gate.findings,
        )
    try:
        result, status, pack_assertions = review_pack_snapshot(pr_number, github)
    except (GitHubReadError, ReviewSupportError):
        return Evidence(
            command="review-pack",
            repository=REPOSITORY,
            invocation_target=target,
            runtime=gate.runtime,
            remote={},
            local={},
            status=Status.INCOMPLETE,
            completeness={"complete": False, "runtime": True, "review_pack": False},
            assertions=gate.assertions,
            findings=({"code": "review-pack-evidence-incomplete"},),
        )
    assertions = tuple([*gate.assertions, *pack_assertions])
    return Evidence(
        command="review-pack",
        repository=REPOSITORY,
        invocation_target=target,
        runtime=gate.runtime,
        remote=result.data,
        local={},
        status=status,
        completeness={"complete": result.complete and status in {Status.PASS, Status.FAIL}, "runtime": True, "review_pack": result.complete},
        assertions=assertions,
        findings=result.findings,
    )
