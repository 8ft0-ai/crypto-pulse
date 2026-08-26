from __future__ import annotations

from pathlib import Path

from ..checks import missing_site_artifacts, tracked_site_paths
from ..process import ProcessRunner
from ._common import BUILD_ARGV, TEST_ARGV, prepare, run_gate


def run(
    *,
    cwd: Path | None = None,
    runner: ProcessRunner | None = None,
) -> int:
    root, python, runner = prepare(cwd=cwd, runner=runner)
    failures = 0

    if not run_gate("unit tests", [str(python), *TEST_ARGV], root=root, runner=runner):
        failures += 1

    if not run_gate(
        "documentation validation",
        [str(python), "scripts/validate_documentation.py"],
        root=root,
        runner=runner,
    ):
        failures += 1

    tracked = tracked_site_paths(root, runner)
    if tracked:
        print("FAILED generated output: tracked _site/ content exists")
        failures += 1
    else:
        print("OK generated output: no tracked _site/ content")

    if not run_gate("site build", [str(python), *BUILD_ARGV], root=root, runner=runner):
        failures += 1

    missing = missing_site_artifacts(root)
    if missing:
        print("FAILED expected site artefacts:")
        for path in missing:
            print(f"  - {path}")
        failures += 1
    else:
        print("OK expected site artefacts")

    return 2 if failures else 0
