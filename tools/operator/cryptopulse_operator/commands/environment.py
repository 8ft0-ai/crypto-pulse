"""Protected-environment readback for operator-toolkit/v1 Slice C."""

from __future__ import annotations

from ..evidence import Evidence
from ..github_read import GitHubReader, REPOSITORY
from ..privileged_readback import environment_snapshot
from ..process import ProcessRunner
from ..review_support import runtime_gate


def run(name: str, runner: ProcessRunner, github: GitHubReader) -> Evidence:
    target = {"kind": "environment", "name": name}
    gate = runtime_gate(runner, github)
    if gate.status is not None:
        return Evidence(
            command="environment", repository=REPOSITORY, invocation_target=target,
            runtime=gate.runtime, remote={}, local={}, status=gate.status,
            completeness={"complete": False, "runtime": gate.complete, "environment": False},
            assertions=gate.assertions, findings=gate.findings,
        )
    result = environment_snapshot(name, github)
    return Evidence(
        command="environment", repository=REPOSITORY, invocation_target=target,
        runtime=gate.runtime, remote=result.data, local={}, status=result.status,
        completeness={"complete": result.complete, "runtime": True, "environment": result.complete},
        assertions=gate.assertions + result.assertions, findings=result.findings,
    )
