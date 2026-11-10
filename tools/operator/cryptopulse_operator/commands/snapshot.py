"""Bounded repository and authoritative-main snapshot."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..evidence import Evidence, Status
from ..git_local import observe_repository, GitObservationError
from ..github_read import GitHubReader, GitHubReadError, REPOSITORY
from ..process import ProcessRunner
from ..runtime import inspect_runtime, RuntimeIdentityError


def run(repo: Path, runner: ProcessRunner, github: GitHubReader) -> Evidence:
    findings: list[dict[str, Any]] = []
    assertions: list[dict[str, Any]] = []
    tools = {name: runner.has_executable(name) for name in ("git", "gh")}
    auth_ok = tools["gh"] and github.auth_ok()
    if not all(tools.values()) or not auth_ok:
        assertions.extend([
            {"name": "git-present", "holds": tools["git"]},
            {"name": "gh-present", "holds": tools["gh"]},
            {"name": "gh-authenticated-read", "holds": bool(auth_ok)},
        ])
        return Evidence(
            command="snapshot",
            repository=REPOSITORY,
            invocation_target={"kind": "repository", "path": str(repo.resolve())},
            runtime={"repository": REPOSITORY, "clean": False, "provenance": None},
            remote={},
            local={"tools": tools, "authenticated": bool(auth_ok)},
            status=Status.ERROR,
            completeness={"complete": False, "runtime": False, "remote": False, "local": False},
            assertions=tuple(assertions),
            findings=({"code": "prerequisite-or-authentication-failure"},),
        )
    try:
        runtime = inspect_runtime(runner, github)
        runtime_identity = runtime.identity
    except RuntimeIdentityError:
        runtime = None
        runtime_identity = {"repository": REPOSITORY, "clean": False, "provenance": None}
        findings.append({"code": "runtime-identity-error"})
    try:
        local = observe_repository(repo, runner)
    except GitObservationError:
        local = {}
        findings.append({"code": "local-repository-incomplete"})
    try:
        remote = github.main_branch()
    except GitHubReadError:
        remote = {}
        findings.append({"code": "authoritative-main-incomplete"})
    if local:
        assertions.append({"name": "canonical-origin", "holds": bool(local.get("origin_matches"))})
    if remote:
        assertions.append({"name": "main-protected", "holds": bool(remote.get("protected"))})
    complete = bool(runtime and runtime.complete and local and remote)
    false_assertion = any(not bool(item["holds"]) for item in assertions)
    if runtime is None:
        status = Status.ERROR
    elif not runtime.complete:
        status = Status.INCOMPLETE
        findings.append({"code": runtime.reason or "runtime-incomplete"})
    elif not runtime.trusted:
        status = Status.ERROR
        findings.append({"code": runtime.reason or "runtime-untrusted"})
    elif not complete:
        status = Status.INCOMPLETE
    elif false_assertion:
        status = Status.FAIL
    else:
        status = Status.PASS
    return Evidence(command="snapshot", repository=REPOSITORY, invocation_target={"kind": "repository", "path": str(repo.resolve())}, runtime=runtime_identity, remote=remote, local=local, status=status, completeness={"complete": complete, "runtime": bool(runtime and runtime.complete), "remote": bool(remote), "local": bool(local)}, assertions=tuple(assertions), findings=tuple(findings))
