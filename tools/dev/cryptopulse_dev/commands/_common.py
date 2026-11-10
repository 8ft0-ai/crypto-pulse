from __future__ import annotations

from pathlib import Path

from ..environment import (
    check_dependency_imports,
    require_expected_repository,
    resolve_repository,
    validate_venv,
)
from ..process import ProcessRunner

TEST_ARGV = ("-m", "unittest", "discover", "-s", "tests")
BUILD_ARGV = ("-m", "site_generator")


def prepare_repository(
    *,
    cwd: Path | None = None,
    runner: ProcessRunner | None = None,
) -> tuple[Path, ProcessRunner]:
    runner = runner or ProcessRunner()
    cwd = (cwd or Path.cwd()).resolve()
    context = resolve_repository(cwd, runner)
    require_expected_repository(context)
    return context.root, runner


def prepare(
    *,
    cwd: Path | None = None,
    runner: ProcessRunner | None = None,
) -> tuple[Path, Path, ProcessRunner]:
    root, runner = prepare_repository(cwd=cwd, runner=runner)
    python = validate_venv(root, runner)
    check_dependency_imports(root, python, runner)
    return root, python, runner


def run_gate(
    label: str,
    argv: list[str],
    *,
    root: Path,
    runner: ProcessRunner,
) -> bool:
    result = runner.run(argv, cwd=root)
    if result.returncode == 0:
        print(f"OK {label}")
        return True
    print(f"FAILED {label} (exit {result.returncode})")
    return False
