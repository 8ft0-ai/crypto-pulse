from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
import sys
from typing import Mapping

from .process import ProcessRunner

EXPECTED_REPOSITORY = "8ft0-ai/crypto-pulse"
MIN_PYTHON = (3, 12)
_REQUIREMENT_IMPORTS: Mapping[str, str] = {
    "pyyaml": "yaml",
    "markdown": "markdown",
}


class PrerequisiteError(RuntimeError):
    pass


@dataclass(frozen=True)
class RepositoryContext:
    root: Path
    origin_repository: str | None


def python_supported(version_info: tuple[int, ...] | None = None) -> bool:
    version = tuple(version_info or tuple(sys.version_info))
    return version[:2] >= MIN_PYTHON


def normalise_remote(remote: str) -> str | None:
    value = remote.strip()
    patterns = (
        r"^https://github\.com/([^/@:]+/[^/@:]+?)(?:\.git)?/?$",
        r"^git@github\.com:([^/:]+/[^/:]+?)(?:\.git)?$",
    )
    for pattern in patterns:
        match = re.fullmatch(pattern, value)
        if match:
            return match.group(1)
    return None


def resolve_repository(cwd: Path, runner: ProcessRunner) -> RepositoryContext:
    top = runner.run(["git", "rev-parse", "--show-toplevel"], cwd=cwd, capture=True)
    if top.returncode == 127:
        raise PrerequisiteError("Git is required")
    if top.returncode != 0 or not top.stdout.strip():
        raise PrerequisiteError("not inside a Git worktree")
    root = Path(top.stdout.strip()).resolve()

    remote = runner.run(["git", "remote", "get-url", "origin"], cwd=root, capture=True)
    repository = normalise_remote(remote.stdout) if remote.returncode == 0 else None
    return RepositoryContext(root=root, origin_repository=repository)


def require_expected_repository(context: RepositoryContext) -> None:
    if context.origin_repository != EXPECTED_REPOSITORY:
        raise PrerequisiteError(
            f"origin must identify {EXPECTED_REPOSITORY} using canonical GitHub HTTPS or SSH form"
        )


def requirements_path(root: Path) -> Path:
    return root / "requirements-dev.txt"


def requirement_modules(root: Path) -> tuple[str, ...]:
    path = requirements_path(root)
    if not path.is_file():
        raise PrerequisiteError("requirements-dev.txt is missing")
    modules: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        value = raw.split("#", 1)[0].strip()
        if not value:
            continue
        package = re.split(r"[<>=!~;\[]", value, maxsplit=1)[0].strip().lower()
        if not package:
            continue
        modules.append(_REQUIREMENT_IMPORTS.get(package, package.replace("-", "_")))
    if not modules:
        raise PrerequisiteError("requirements-dev.txt declares no dependencies")
    return tuple(modules)


def venv_path(root: Path) -> Path:
    return root / ".venv"


def _venv_python_path(root: Path) -> Path:
    return venv_path(root) / "bin" / "python"


def validate_venv(root: Path, runner: ProcessRunner) -> Path:
    target = venv_path(root)
    if target.is_symlink():
        raise PrerequisiteError(".venv must not be a symlink")
    if not target.is_dir() or not (target / "pyvenv.cfg").is_file():
        raise PrerequisiteError(".venv is missing or malformed; run ./tools/dev/cp-dev bootstrap")

    expected = target.resolve()
    python = _venv_python_path(root)
    if not python.is_file():
        raise PrerequisiteError(".venv/bin/python is missing; run bootstrap --recreate")

    probe = runner.run(
        [
            str(python),
            "-I",
            "-B",
            "-c",
            "import json,sys; print(json.dumps({'version': list(sys.version_info[:3]), 'prefix': sys.prefix}))",
        ],
        cwd=root,
        capture=True,
    )
    if probe.returncode != 0:
        raise PrerequisiteError(".venv Python could not be executed")
    try:
        payload = json.loads(probe.stdout.strip())
        version = tuple(int(part) for part in payload["version"])
        prefix = Path(payload["prefix"]).resolve()
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        raise PrerequisiteError(".venv Python returned invalid environment metadata") from None

    if version[:2] < MIN_PYTHON:
        raise PrerequisiteError(".venv Python >= 3.12 is required; run bootstrap --recreate")
    if prefix != expected:
        raise PrerequisiteError(".venv Python prefix does not match the repository-local .venv")
    return python


def check_dependency_imports(root: Path, python: Path, runner: ProcessRunner) -> tuple[str, ...]:
    modules = requirement_modules(root)
    script = "import importlib; " + "; ".join(
        f"importlib.import_module({module!r})" for module in modules
    )
    result = runner.run([str(python), "-I", "-B", "-c", script], cwd=root, capture=True)
    if result.returncode != 0:
        raise PrerequisiteError(
            "required development dependencies are unavailable; run ./tools/dev/cp-dev bootstrap"
        )
    return modules


def validate_recreate_target(root: Path) -> Path:
    target = venv_path(root)
    expected = root.resolve() / ".venv"
    if target.absolute() != expected:
        raise PrerequisiteError("refusing to recreate a path other than the repository-local .venv")
    if target.is_symlink():
        raise PrerequisiteError("refusing to recreate a symlinked .venv")
    if target.exists():
        if not target.is_dir() or not (target / "pyvenv.cfg").is_file():
            raise PrerequisiteError(
                "refusing to remove an existing .venv that cannot be proven to be a virtual environment"
            )
        if target.resolve() != expected:
            raise PrerequisiteError("refusing to recreate a .venv that resolves outside the repository")
    return target
