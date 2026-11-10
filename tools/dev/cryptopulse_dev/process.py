from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import subprocess
from typing import Sequence


@dataclass(frozen=True)
class ProcessResult:
    returncode: int
    stdout: str = ""
    stderr: str = ""


class ProcessRunner:
    def run(
        self,
        argv: Sequence[str],
        *,
        cwd: Path | None = None,
        capture: bool = False,
    ) -> ProcessResult:
        try:
            completed = subprocess.run(
                list(argv),
                cwd=cwd,
                text=True,
                capture_output=capture,
                check=False,
            )
        except OSError as exc:
            return ProcessResult(returncode=127, stderr=str(exc))
        return ProcessResult(
            returncode=completed.returncode,
            stdout=completed.stdout or "",
            stderr=completed.stderr or "",
        )
