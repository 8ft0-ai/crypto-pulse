"""Reviewed CryptoPulse contract index for operator-toolkit/v1 Slice D."""

from __future__ import annotations

from ..evidence import Evidence, Status
from ..github_read import GitHubReader, REPOSITORY
from ..process import ProcessRunner
from ..project_proof import ProjectProofError, contracts_snapshot, load_config
from ..review_support import runtime_gate


def run(runner: ProcessRunner, github: GitHubReader) -> Evidence:
    target = {"kind": "project-contract-index"}
    gate = runtime_gate(runner, github)
    if gate.status is not None:
        return Evidence(
            command="contracts", repository=REPOSITORY, invocation_target=target,
            runtime=gate.runtime, remote={}, local={}, status=gate.status,
            completeness={"complete": False, "runtime": gate.complete, "contracts": False},
            assertions=gate.assertions, findings=gate.findings,
        )
    try:
        result = contracts_snapshot(load_config())
    except ProjectProofError:
        return Evidence(
            command="contracts", repository=REPOSITORY, invocation_target=target,
            runtime=gate.runtime, remote={}, local={}, status=Status.ERROR,
            completeness={"complete": False, "runtime": True, "contracts": False},
            assertions=gate.assertions, findings=({"code": "trusted-slice-d-configuration-invalid"},),
        )
    return Evidence(
        command="contracts", repository=REPOSITORY, invocation_target=target,
        runtime=gate.runtime, remote=result.data, local={}, status=result.status,
        completeness={"complete": result.complete, "runtime": True, "contracts": result.complete},
        assertions=gate.assertions + result.assertions, findings=result.findings,
    )
