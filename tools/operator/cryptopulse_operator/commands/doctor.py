"""Local prerequisite and read-capability diagnostics."""

from __future__ import annotations

import sys
from typing import Any

from ..evidence import Evidence, Status
from ..github_read import GitHubReader, REPOSITORY
from ..process import ProcessRunner
from ..runtime import inspect_runtime, RuntimeIdentityError


def python_supported(version: tuple[int, int] | None) -> bool:
    return version is not None and version >= (3, 12)


def run(runner: ProcessRunner, github: GitHubReader) -> Evidence:
    findings: list[dict[str, Any]] = []
    assertions: list[dict[str, Any]] = []
    tools = {name: runner.has_executable(name) for name in ("git", "gh")}
    version = (sys.version_info.major, sys.version_info.minor)
    python_ok = python_supported(version)
    auth_ok = tools["gh"] and github.auth_ok()
    assertions.extend([
        {"name": "python>=3.12", "holds": python_ok},
        {"name": "git-present", "holds": tools["git"]},
        {"name": "gh-present", "holds": tools["gh"]},
        {"name": "gh-authenticated-read", "holds": bool(auth_ok)},
    ])

    prereq_ok = python_ok and all(tools.values()) and bool(auth_ok)
    runtime = None
    runtime_identity = {"repository": REPOSITORY, "clean": False, "provenance": None}
    if prereq_ok:
        try:
            runtime = inspect_runtime(runner, github)
            runtime_identity = runtime.identity
        except RuntimeIdentityError:
            findings.append({"code": "runtime-identity-error"})

    if not prereq_ok:
        status = Status.ERROR
        completeness = {"complete": False, "runtime": False, "github": bool(auth_ok)}
        findings.append({"code": "prerequisite-or-authentication-failure"})
    elif runtime is None:
        status = Status.ERROR
        completeness = {"complete": False, "runtime": False, "github": True}
    elif not runtime.complete:
        status = Status.INCOMPLETE
        completeness = {"complete": False, "runtime": False, "github": True}
        findings.append({"code": runtime.reason or "runtime-incomplete"})
    elif not runtime.trusted:
        status = Status.ERROR
        completeness = {"complete": True, "runtime": True, "github": True}
        findings.append({"code": runtime.reason or "runtime-untrusted"})
    else:
        status = Status.PASS
        completeness = {"complete": True, "runtime": True, "github": True}

    return Evidence(command="doctor", repository=REPOSITORY, invocation_target={"kind": "local-runtime"}, runtime=runtime_identity, remote={}, local={"python": f"{version[0]}.{version[1]}", "tools": tools, "authenticated": bool(auth_ok)}, status=status, completeness=completeness, assertions=tuple(assertions), findings=tuple(findings))
