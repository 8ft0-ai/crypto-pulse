"""Fixed-form subprocess execution for the operator toolkit."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
from typing import Mapping, Sequence


@dataclass(frozen=True)
class ProcessResult:
    returncode: int
    stdout: str
    stderr: str


class ProcessError(RuntimeError):
    pass


class ProcessRunner:
    """Run only caller-selected fixed executables without a shell."""

    def __init__(self, *, env: Mapping[str, str] | None = None) -> None:
        base = dict(os.environ if env is None else env)
        base.pop("PYTHONPATH", None)
        base.pop("PYTHONHOME", None)
        base["PYTHONNOUSERSITE"] = "1"
        self._env = base

    def run(self, argv: Sequence[str], *, cwd: Path | None = None) -> ProcessResult:
        if not argv or not isinstance(argv[0], str) or not argv[0]:
            raise ProcessError("subprocess executable is missing")
        if any(not isinstance(arg, str) for arg in argv):
            raise ProcessError("subprocess arguments must be strings")
        proc = subprocess.run(
            list(argv),
            cwd=str(cwd) if cwd else None,
            env=self._env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            shell=False,
            check=False,
        )
        return ProcessResult(proc.returncode, proc.stdout, proc.stderr)

    def git(self, args: Sequence[str], *, cwd: Path | None = None) -> ProcessResult:
        return self.run(["git", *args], cwd=cwd)

    def gh(self, args: Sequence[str], *, cwd: Path | None = None) -> ProcessResult:
        return self.run(["gh", *args], cwd=cwd)
