from __future__ import annotations

from pathlib import Path
import sys

from ..checks import tracked_site_paths
from ..environment import (
    EXPECTED_REPOSITORY,
    PrerequisiteError,
    check_dependency_imports,
    python_supported,
    resolve_repository,
    validate_venv,
)
from ..process import ProcessRunner


def run(
    *,
    cwd: Path | None = None,
    runner: ProcessRunner | None = None,
    host_version: tuple[int, ...] | None = None,
) -> int:
    runner = runner or ProcessRunner()
    cwd = (cwd or Path.cwd()).resolve()
    context = resolve_repository(cwd, runner)
    failures = 0

    print("OK Git: repository discovery succeeded")
    print(f"OK repository root: {context.root}")

    if context.origin_repository == EXPECTED_REPOSITORY:
        print(f"OK origin: {EXPECTED_REPOSITORY}")
    else:
        print(f"FAILED origin: expected {EXPECTED_REPOSITORY}")
        failures += 1

    version = host_version or tuple(sys.version_info)
    if python_supported(version):
        print(f"OK host Python: {version[0]}.{version[1]}")
    else:
        print("FAILED host Python: Python >= 3.12 is required")
        failures += 1

    try:
        python = validate_venv(context.root, runner)
        print(f"OK virtual environment: {python}")
        modules = check_dependency_imports(context.root, python, runner)
        print(f"OK dependencies: {', '.join(modules)}")
    except PrerequisiteError as exc:
        print(f"FAILED virtual environment: {exc}")
        failures += 1

    tracked = tracked_site_paths(context.root, runner)
    if tracked:
        print("FAILED generated output: tracked _site/ content exists")
        failures += 1
    elif (context.root / "_site").exists():
        print("OK generated output: disposable _site/ is present and untracked")
    else:
        print("OK generated output: _site/ is absent")

    print("OK working tree: edits are allowed for developer diagnostics")
    return 2 if failures else 0
