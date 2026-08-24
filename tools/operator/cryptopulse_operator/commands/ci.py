"""Authoritative GitHub Actions run evidence."""

from __future__ import annotations

from ..evidence import Evidence, Status
from ..github_read import GitHubReader, GitHubReadError, REPOSITORY
from ..process import ProcessRunner
from ..review_support import ci_snapshot, runtime_gate, ReviewSupportError


def run(run_id: int, runner: ProcessRunner, github: GitHubReader) -> Evidence:
    target = {"kind": "workflow-run", "id": run_id}
    gate = runtime_gate(runner, github)
    if gate.status is not None:
        return Evidence(
            command="ci",
            repository=REPOSITORY,
            invocation_target=target,
            runtime=gate.runtime,
            remote={},
            local={},
            status=gate.status,
            completeness={"complete": False, "runtime": gate.complete, "ci": False},
            assertions=gate.assertions,
            findings=gate.findings,
        )
    try:
        result = ci_snapshot(run_id, github)
    except (GitHubReadError, ReviewSupportError):
        return Evidence(
            command="ci",
            repository=REPOSITORY,
            invocation_target=target,
            runtime=gate.runtime,
            remote={},
            local={},
            status=Status.INCOMPLETE,
            completeness={"complete": False, "runtime": True, "ci": False},
            assertions=gate.assertions,
            findings=({"code": "ci-evidence-incomplete"},),
        )
    assertions = list(gate.assertions)
    completed = result.data["status"] == "completed" and result.data["conclusion"] is not None
    assertions.append({"name": "run-completed", "holds": completed})
    if not result.complete or not completed:
        status = Status.INCOMPLETE
    else:
        success = result.data["conclusion"] == "success"
        assertions.append({"name": "run-success", "holds": success})
        status = Status.PASS if success else Status.FAIL
    return Evidence(
        command="ci",
        repository=REPOSITORY,
        invocation_target=target,
        runtime=gate.runtime,
        remote=result.data,
        local={},
        status=status,
        completeness={"complete": result.complete and completed, "runtime": True, "ci": result.complete},
        assertions=tuple(assertions),
        findings=result.findings,
    )
