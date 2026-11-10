"""Live Pages verification proof for operator-toolkit/v1 Slice D."""

from __future__ import annotations

from ..evidence import Evidence, Status
from ..github_read import GitHubReader, REPOSITORY
from ..process import ProcessRunner
from ..project_proof import ProjectProofError, live_snapshot, load_config
from ..review_support import runtime_gate


def run(runner: ProcessRunner, github: GitHubReader) -> Evidence:
    target = {"kind": "live-pages-verification"}
    gate = runtime_gate(runner, github)
    if gate.status is not None:
        return Evidence(
            command="live", repository=REPOSITORY, invocation_target=target,
            runtime=gate.runtime, remote={}, local={}, status=gate.status,
            completeness={"complete": False, "runtime": gate.complete, "live": False},
            assertions=gate.assertions, findings=gate.findings,
        )
    try:
        result = live_snapshot(github, load_config())
    except ProjectProofError:
        return Evidence(
            command="live", repository=REPOSITORY, invocation_target=target,
            runtime=gate.runtime, remote={}, local={}, status=Status.ERROR,
            completeness={"complete": False, "runtime": True, "live": False},
            assertions=gate.assertions, findings=({"code": "trusted-slice-d-configuration-invalid"},),
        )
    return Evidence(
        command="live", repository=REPOSITORY, invocation_target=target,
        runtime=gate.runtime, remote=result.data, local={}, status=result.status,
        completeness={"complete": result.complete, "runtime": True, "live": result.complete},
        assertions=gate.assertions + result.assertions, findings=result.findings,
    )
