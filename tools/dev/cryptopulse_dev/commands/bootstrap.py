from __future__ import annotations

from pathlib import Path
import shutil
import sys

from ..environment import (
    PrerequisiteError,
    check_dependency_imports,
    python_supported,
    require_expected_repository,
    requirement_modules,
    requirements_path,
    resolve_repository,
    validate_recreate_target,
    validate_venv,
    venv_path,
)
from ..process import ProcessRunner


class TaskFailure(RuntimeError):
    pass


def run(
    *,
    recreate: bool = False,
    cwd: Path | None = None,
    runner: ProcessRunner | None = None,
    host_python: Path | None = None,
    host_version: tuple[int, ...] | None = None,
) -> int:
    runner = runner or ProcessRunner()
    cwd = (cwd or Path.cwd()).resolve()
    context = resolve_repository(cwd, runner)
    require_expected_repository(context)

    version = host_version or tuple(sys.version_info)
    if not python_supported(version):
        raise PrerequisiteError("Python >= 3.12 is required")
    host_python = Path(host_python or sys.executable)

    requirement_modules(context.root)
    target = venv_path(context.root)

    if recreate:
        target = validate_recreate_target(context.root)
        if target.exists():
            shutil.rmtree(target)

    if not target.exists():
        created = runner.run(
            [str(host_python), "-I", "-B", "-m", "venv", str(target)],
            cwd=context.root,
        )
        if created.returncode != 0:
            raise TaskFailure("failed to create the repository-local .venv")

    python = validate_venv(context.root, runner)
    installed = runner.run(
        [
            str(python),
            "-I",
            "-B",
            "-m",
            "pip",
            "install",
            "-r",
            str(requirements_path(context.root)),
        ],
        cwd=context.root,
    )
    if installed.returncode != 0:
        raise TaskFailure("dependency installation failed")

    check_dependency_imports(context.root, python, runner)
    print(f"OK bootstrap: {target}")
    return 0
