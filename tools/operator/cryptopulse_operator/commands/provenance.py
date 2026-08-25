"""Trusted runtime-to-live evidence chain for operator-toolkit/v1 Slice D."""

from __future__ import annotations

from ..evidence import Evidence, Status
from ..github_read import GitHubReader, REPOSITORY
from ..process import ProcessRunner
from ..project_proof import ProjectProofError, load_config, provenance_snapshot
from ..review_support import runtime_gate


def run(runner: ProcessRunner, github: GitHubReader) -> Evidence:
    target = {"kind": "pages-live-provenance"}
    gate = runtime_gate(runner, github)
    if gate.status is not None:
        return Evidence(
            command="provenance", repository=REPOSITORY, invocation_target=target,
            runtime=gate.runtime, remote={}, local={}, status=gate.status,
            completeness={"complete": False, "runtime": gate.complete, "provenance": False},
            assertions=gate.assertions, findings=gate.findings,
        )
    try:
        result = provenance_snapshot(github, load_config())
    except ProjectProofError:
        return Evidence(
            command="provenance", repository=REPOSITORY, invocation_target=target,
            runtime=gate.runtime, remote={}, local={}, status=Status.ERROR,
            completeness={"complete": False, "runtime": True, "provenance": False},
            assertions=gate.assertions, findings=({"code": "trusted-slice-d-configuration-invalid"},),
        )
    return Evidence(
        command="provenance", repository=REPOSITORY, invocation_target=target,
        runtime=gate.runtime, remote=result.data, local={}, status=result.status,
        completeness={"complete": result.complete, "runtime": True, "provenance": result.complete},
        assertions=gate.assertions + result.assertions, findings=result.findings,
    )
