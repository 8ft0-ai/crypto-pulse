from __future__ import annotations

from pathlib import Path

from ..environment import PrerequisiteError
from ..process import ProcessRunner
from ._common import prepare


def run(
    *,
    port: int = 8000,
    cwd: Path | None = None,
    runner: ProcessRunner | None = None,
) -> int:
    root, python, runner = prepare(cwd=cwd, runner=runner)
    if not 1024 <= port <= 65535:
        raise PrerequisiteError("serve port must be in range 1024-65535")

    site = root / "_site"
    if site.is_symlink():
        raise PrerequisiteError("serve requires a safe existing _site directory")
    if not site.exists():
        raise PrerequisiteError(
            "serve requires an existing _site/index.html; run cp-dev build first"
        )
    if not site.is_dir() or site.resolve() != root / "_site":
        raise PrerequisiteError("serve requires a safe existing _site directory")
    if not (site / "index.html").is_file():
        raise PrerequisiteError(
            "serve requires an existing _site/index.html; run cp-dev build first"
        )

    argv = [
        str(python),
        "-m",
        "http.server",
        str(port),
        "--bind",
        "127.0.0.1",
        "--directory",
        str(site),
    ]
    try:
        result = runner.run(argv, cwd=root)
    except KeyboardInterrupt:
        print("OK serve: stopped")
        return 0
    if result.returncode != 0:
        print(f"FAILED serve (exit {result.returncode})")
        return 2
    return 0
