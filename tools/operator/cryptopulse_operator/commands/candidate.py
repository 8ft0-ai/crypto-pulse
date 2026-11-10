"""Authoritative pull-request candidate evidence."""

from __future__ import annotations

from ..evidence import Evidence, Status
from ..github_read import GitHubReader, GitHubReadError, REPOSITORY
from ..process import ProcessRunner
from ..review_support import candidate_snapshot, runtime_gate, ReviewSupportError


def run(pr_number: int, runner: ProcessRunner, github: GitHubReader) -> Evidence:
    target = {"kind": "pull-request", "number": pr_number}
    gate = runtime_gate(runner, github)
    if gate.status is not None:
        return Evidence(
            command="candidate",
            repository=REPOSITORY,
            invocation_target=target,
            runtime=gate.runtime,
            remote={},
            local={},
            status=gate.status,
            completeness={"complete": False, "runtime": gate.complete, "candidate": False},
            assertions=gate.assertions,
            findings=gate.findings,
        )
    try:
        result = candidate_snapshot(pr_number, github)
    except (GitHubReadError, ReviewSupportError):
        return Evidence(
            command="candidate",
            repository=REPOSITORY,
            invocation_target=target,
            runtime=gate.runtime,
            remote={},
            local={},
            status=Status.INCOMPLETE,
            completeness={"complete": False, "runtime": True, "candidate": False},
            assertions=gate.assertions,
            findings=({"code": "candidate-evidence-incomplete"},),
        )
    return Evidence(
        command="candidate",
        repository=REPOSITORY,
        invocation_target=target,
        runtime=gate.runtime,
        remote=result.data,
        local={},
        status=Status.PASS if result.complete else Status.INCOMPLETE,
        completeness={"complete": result.complete, "runtime": True, "candidate": result.complete},
        assertions=gate.assertions,
        findings=result.findings,
    )
