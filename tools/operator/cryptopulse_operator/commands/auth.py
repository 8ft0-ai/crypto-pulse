"""Privileged read-capability evidence for operator-toolkit/v1 Slice C."""

from __future__ import annotations

from ..evidence import Evidence, Status
from ..github_read import GitHubReader, REPOSITORY
from ..privileged_readback import auth_snapshot, load_config, PrivilegedReadbackError
from ..process import ProcessRunner
from ..review_support import runtime_gate


def run(runner: ProcessRunner, github: GitHubReader) -> Evidence:
    target = {"kind": "github-read-capability"}
    gate = runtime_gate(runner, github)
    if gate.status is not None:
        return Evidence(
            command="auth", repository=REPOSITORY, invocation_target=target,
            runtime=gate.runtime, remote={}, local={}, status=gate.status,
            completeness={"complete": False, "runtime": gate.complete, "privileged_read": False},
            assertions=gate.assertions, findings=gate.findings,
        )
    try:
        result = auth_snapshot(github, load_config())
    except PrivilegedReadbackError:
        return Evidence(
            command="auth", repository=REPOSITORY, invocation_target=target,
            runtime=gate.runtime, remote={}, local={}, status=Status.ERROR,
            completeness={"complete": False, "runtime": True, "privileged_read": False},
            assertions=gate.assertions, findings=({"code": "trusted-slice-c-configuration-invalid"},),
        )
    return Evidence(
        command="auth", repository=REPOSITORY, invocation_target=target,
        runtime=gate.runtime, remote=result.data, local={}, status=result.status,
        completeness={"complete": result.complete, "runtime": True, "privileged_read": result.complete},
        assertions=gate.assertions + result.assertions, findings=result.findings,
    )
