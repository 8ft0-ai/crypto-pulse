"""Local prerequisite and read-capability diagnostics."""

from __future__ import annotations

import shutil
import sys
from typing import Any

from ..evidence import Evidence, Status
from ..github_read import GitHubReader, REPOSITORY
from ..process import ProcessRunner
from ..runtime import inspect_runtime, RuntimeIdentityError


def run(runner: ProcessRunner, github: GitHubReader) -> Evidence:
    findings: list[dict[str, Any]] = []
    assertions: list[dict[str, Any]] = []
    tools = {name: shutil.which(name) is not None for name in ("git", "gh")}
    python_ok = sys.version_info >= (3, 12)
    auth_ok = tools["gh"] and github.auth_ok()
    assertions.extend([
        {"name": "python>=3.12", "holds": python_ok},
        {"name": "git-present", "holds": tools["git"]},
        {"name": "gh-present", "holds": tools["gh"]},
        {"name": "gh-authenticated-read", "holds": bool(auth_ok)},
    ])
    try:
        runtime = inspect_runtime(runner, github)
        runtime_identity = runtime.identity
    except RuntimeIdentityError:
        runtime = None
        runtime_identity = {"repository": REPOSITORY, "clean": False, "provenance": None}
        findings.append({"code": "runtime-identity-error"})

    prereq_ok = python_ok and all(tools.values()) and bool(auth_ok)
    if runtime is None:
        status = Status.ERROR
        completeness = {"complete": False, "runtime": False, "github": bool(auth_ok)}
    elif not runtime.complete:
        status = Status.INCOMPLETE
        completeness = {"complete": False, "runtime": False, "github": bool(auth_ok)}
        findings.append({"code": runtime.reason or "runtime-incomplete"})
    elif not runtime.trusted:
        status = Status.ERROR
        completeness = {"complete": True, "runtime": True, "github": bool(auth_ok)}
        findings.append({"code": runtime.reason or "runtime-untrusted"})
    elif not prereq_ok:
        status = Status.ERROR
        completeness = {"complete": True, "runtime": True, "github": bool(auth_ok)}
        findings.append({"code": "prerequisite-or-authentication-failure"})
    else:
        status = Status.PASS
        completeness = {"complete": True, "runtime": True, "github": True}

    return Evidence(command="doctor", repository=REPOSITORY, invocation_target={"kind": "local-runtime"}, runtime=runtime_identity, remote={}, local={"python": f"{sys.version_info.major}.{sys.version_info.minor}", "tools": tools, "authenticated": bool(auth_ok)}, status=status, completeness=completeness, assertions=tuple(assertions), findings=tuple(findings))
