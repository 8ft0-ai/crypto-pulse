from __future__ import annotations

from pathlib import Path

from ..checks import missing_site_artifacts, tracked_site_paths
from ..environment import (
    check_dependency_imports,
    require_expected_repository,
    resolve_repository,
    validate_venv,
)
from ..process import ProcessRunner


def _run_gate(
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


def run(
    *,
    cwd: Path | None = None,
    runner: ProcessRunner | None = None,
) -> int:
    runner = runner or ProcessRunner()
    cwd = (cwd or Path.cwd()).resolve()
    context = resolve_repository(cwd, runner)
    require_expected_repository(context)
    python = validate_venv(context.root, runner)
    check_dependency_imports(context.root, python, runner)

    failures = 0

    if not _run_gate(
        "unit tests",
        [str(python), "-m", "unittest", "discover", "-s", "tests"],
        root=context.root,
        runner=runner,
    ):
        failures += 1

    if not _run_gate(
        "documentation validation",
        [str(python), "scripts/validate_documentation.py"],
        root=context.root,
        runner=runner,
    ):
        failures += 1

    tracked = tracked_site_paths(context.root, runner)
    if tracked:
        print("FAILED generated output: tracked _site/ content exists")
        failures += 1
    else:
        print("OK generated output: no tracked _site/ content")

    if not _run_gate(
        "site build",
        [str(python), "-m", "site_generator"],
        root=context.root,
        runner=runner,
    ):
        failures += 1

    missing = missing_site_artifacts(context.root)
    if missing:
        print("FAILED expected site artefacts:")
        for path in missing:
            print(f"  - {path}")
        failures += 1
    else:
        print("OK expected site artefacts")

    return 2 if failures else 0
