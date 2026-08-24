"""Trusted-runtime identity and protected-main provenance checks."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
import tomllib

from .github_read import GitHubReader, GitHubReadError, REPOSITORY
from .process import ProcessRunner


_RUNTIME_PATHS = (
    "tools/operator/cp",
    "tools/operator/operator.toml",
    "tools/operator/cryptopulse_operator",
)


class RuntimeErrorBase(RuntimeError):
    pass


class RuntimeIdentityError(RuntimeErrorBase):
    pass


@dataclass(frozen=True)
class RuntimeCheck:
    identity: dict[str, Any]
    complete: bool
    trusted: bool
    reason: str | None = None


def runtime_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _git_value(runner: ProcessRunner, root: Path, args: list[str], label: str) -> str:
    result = runner.git(["-C", str(root), *args])
    if result.returncode != 0:
        raise RuntimeIdentityError(f"unable to establish {label}")
    return result.stdout.strip()


def _runtime_matches_head(runner: ProcessRunner, root: Path) -> tuple[bool, str | None]:
    status = runner.git(["-C", str(root), "status", "--porcelain=v1", "--untracked-files=all"])
    if status.returncode != 0:
        raise RuntimeIdentityError("unable to establish runtime cleanliness")
    if status.stdout.strip():
        return False, "dirty-runtime"

    for args in (
        ["diff-index", "--cached", "--quiet", "HEAD", "--", *_RUNTIME_PATHS],
        ["diff-files", "--quiet", "--", *_RUNTIME_PATHS],
    ):
        result = runner.git(["-C", str(root), *args])
        if result.returncode == 1:
            return False, "runtime-object-mismatch"
        if result.returncode != 0:
            raise RuntimeIdentityError("unable to compare runtime objects with HEAD")

    flags = runner.git(["-C", str(root), "ls-files", "-v", "--", *_RUNTIME_PATHS])
    if flags.returncode != 0:
        raise RuntimeIdentityError("unable to inspect runtime index flags")
    tracked = [line for line in flags.stdout.splitlines() if line]
    if not tracked or any(not line.startswith("H ") for line in tracked):
        return False, "runtime-object-mismatch"

    untracked = runner.git(["-C", str(root), "ls-files", "--others", "--", "tools/operator"])
    if untracked.returncode != 0:
        raise RuntimeIdentityError("unable to inspect untracked runtime files")
    if untracked.stdout.strip():
        return False, "runtime-object-mismatch"
    return True, None


def inspect_runtime(runner: ProcessRunner, github: GitHubReader, *, root: Path | None = None) -> RuntimeCheck:
    root = (root or runtime_root()).resolve()
    top = Path(_git_value(runner, root, ["rev-parse", "--show-toplevel"], "runtime root")).resolve()
    if top != root:
        raise RuntimeIdentityError("runtime root is not the repository toplevel")
    commit_sha = _git_value(runner, root, ["rev-parse", "HEAD"], "runtime commit")
    tree_sha = _git_value(runner, root, ["rev-parse", "HEAD^{tree}"], "runtime tree")
    launcher = _git_value(runner, root, ["rev-parse", "HEAD:tools/operator/cp"], "launcher blob")
    config = _git_value(runner, root, ["rev-parse", "HEAD:tools/operator/operator.toml"], "config blob")
    package = _git_value(runner, root, ["rev-parse", "HEAD:tools/operator/cryptopulse_operator"], "package tree")
    matches_head, mismatch_reason = _runtime_matches_head(runner, root)
    try:
        config_data = tomllib.loads((root / "tools/operator/operator.toml").read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise RuntimeIdentityError("unable to read trusted operator configuration") from exc
    expected_config = {
        "contract": "operator-toolkit/v1",
        "repository": REPOSITORY,
        "github_host": "github.com",
        "default_branch": "main",
        "minimum_python": "3.12",
    }
    if any(config_data.get(key) != value for key, value in expected_config.items()):
        raise RuntimeIdentityError("trusted operator configuration does not match v1 bootstrap expectations")
    identity: dict[str, Any] = {
        "repository": REPOSITORY,
        "commit_sha": commit_sha,
        "tree_sha": tree_sha,
        "toolkit_identity": {"launcher_blob": launcher, "package_tree": package},
        "config_identity": config,
        "clean": matches_head,
        "provenance": None,
    }
    if not matches_head:
        return RuntimeCheck(identity, complete=True, trusted=False, reason=mismatch_reason or "runtime-object-mismatch")
    try:
        main = github.main_branch()
        if not main["protected"]:
            identity["provenance"] = "main-not-protected"
            return RuntimeCheck(identity, complete=True, trusted=False, reason="main-not-protected")
        provenance = github.runtime_provenance(commit_sha, main["sha"])
    except GitHubReadError:
        return RuntimeCheck(identity, complete=False, trusted=False, reason="protected-main-provenance-unavailable")
    identity["provenance"] = provenance
    trusted = provenance in {"current-main", "ancestor-of-current-main"}
    return RuntimeCheck(identity, complete=True, trusted=trusted, reason=None if trusted else "runtime-not-on-protected-main-history")
