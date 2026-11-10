from __future__ import annotations

from pathlib import Path

from ..process import ProcessRunner
from ._common import BUILD_ARGV, prepare, run_gate


def run(
    *,
    cwd: Path | None = None,
    runner: ProcessRunner | None = None,
) -> int:
    root, python, runner = prepare(cwd=cwd, runner=runner)
    return 0 if run_gate(
        "site build",
        [str(python), *BUILD_ARGV],
        root=root,
        runner=runner,
    ) else 2
