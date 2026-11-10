"""Read-only local Git observations."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from .process import ProcessRunner


REPOSITORY = "8ft0-ai/crypto-pulse"


class GitObservationError(RuntimeError):
    pass


def _required(result, label: str) -> str:
    if result.returncode != 0:
        raise GitObservationError(f"{label} failed")
    return result.stdout.strip()


def normalise_remote(url: str) -> str | None:
    value = url.strip()
    patterns = (
        r"https://github\.com/(?P<repo>[^/]+/[^/]+?)(?:\.git)?$",
        r"git@github\.com:(?P<repo>[^/]+/[^/]+?)(?:\.git)?$",
        r"ssh://git@github\.com/(?P<repo>[^/]+/[^/]+?)(?:\.git)?$",
    )
    for pattern in patterns:
        match = re.fullmatch(pattern, value)
        if match:
            return match.group("repo")
    return None


def observe_repository(root: Path, runner: ProcessRunner) -> dict[str, Any]:
    root = root.resolve()
    top = Path(_required(runner.git(["-C", str(root), "rev-parse", "--show-toplevel"]), "git root")).resolve()
    if top != root:
        raise GitObservationError("requested repository path is not the Git toplevel")
    head = _required(runner.git(["-C", str(root), "rev-parse", "HEAD"]), "git HEAD")
    tree = _required(runner.git(["-C", str(root), "rev-parse", "HEAD^{tree}"]), "git tree")
    remote_url = _required(runner.git(["-C", str(root), "remote", "get-url", "origin"]), "origin remote")
    remote_repo = normalise_remote(remote_url)
    status = _required(
        runner.git(["-C", str(root), "status", "--porcelain=v1", "--untracked-files=all"]),
        "git status",
    )
    branch_result = runner.git(["-C", str(root), "symbolic-ref", "--quiet", "--short", "HEAD"])
    branch = branch_result.stdout.strip() if branch_result.returncode == 0 else None
    return {
        "root": str(root),
        "head_sha": head,
        "tree_sha": tree,
        "branch": branch,
        "dirty": bool(status),
        "origin_repository": remote_repo,
        "origin_matches": remote_repo == REPOSITORY,
    }
