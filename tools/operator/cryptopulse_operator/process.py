"""Fixed-form subprocess execution for the operator toolkit."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import subprocess
from typing import Mapping, Sequence


_EXECUTABLE_CANDIDATES: dict[str, tuple[str, ...]] = {
    "git": ("/usr/bin/git", "/opt/homebrew/bin/git", "/usr/local/bin/git"),
    "gh": ("/usr/bin/gh", "/opt/homebrew/bin/gh", "/usr/local/bin/gh"),
}
_SAFE_PATH = "/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin:/usr/local/bin"


@dataclass(frozen=True)
class ProcessResult:
    returncode: int
    stdout: str
    stderr: str


class ProcessError(RuntimeError):
    pass


def resolve_executable(name: str) -> str | None:
    try:
        candidates = _EXECUTABLE_CANDIDATES[name]
    except KeyError as exc:
        raise ProcessError(f"unsupported executable: {name}") from exc
    for candidate in candidates:
        path = Path(candidate)
        if path.is_file() and os.access(path, os.X_OK):
            return candidate
    return None


class ProcessRunner:
    """Run only fixed, absolute system executables without a shell."""

    def __init__(self, *, env: Mapping[str, str] | None = None) -> None:
        self._executables = {name: resolve_executable(name) for name in _EXECUTABLE_CANDIDATES}
        base = dict(os.environ if env is None else env)
        for key in tuple(base):
            if key.startswith("GIT_") or key.startswith("DYLD_") or key in {
                "LD_PRELOAD",
                "LD_LIBRARY_PATH",
                "PYTHONPATH",
                "PYTHONHOME",
                "GH_CONFIG_DIR",
                "GH_HOST",
                "BASH_ENV",
                "ENV",
                "CDPATH",
            }:
                base.pop(key, None)
        base["PYTHONNOUSERSITE"] = "1"
        base["PYTHONDONTWRITEBYTECODE"] = "1"
        base["PATH"] = _SAFE_PATH
        self._env = base

    def has_executable(self, name: str) -> bool:
        return self._executables.get(name) is not None

    def executable(self, name: str) -> str | None:
        return self._executables.get(name)

    def run(self, argv: Sequence[str], *, cwd: Path | None = None) -> ProcessResult:
        if not argv or not isinstance(argv[0], str) or not argv[0]:
            raise ProcessError("subprocess executable is missing")
        if any(not isinstance(arg, str) for arg in argv):
            raise ProcessError("subprocess arguments must be strings")
        allowed = {value for value in self._executables.values() if value}
        if not Path(argv[0]).is_absolute() or argv[0] not in allowed:
            raise ProcessError("subprocess executable is not an approved absolute path")
        try:
            proc = subprocess.run(
                list(argv),
                cwd=str(cwd) if cwd else None,
                env=self._env,
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                shell=False,
                check=False,
                timeout=30,
            )
        except subprocess.TimeoutExpired:
            return ProcessResult(124, "", "subprocess timed out")
        return ProcessResult(proc.returncode, proc.stdout, proc.stderr)

    def _run_named(self, name: str, args: Sequence[str], *, cwd: Path | None = None) -> ProcessResult:
        executable = self._executables.get(name)
        if executable is None:
            return ProcessResult(127, "", f"{name} unavailable")
        return self.run([executable, *args], cwd=cwd)

    def git(self, args: Sequence[str], *, cwd: Path | None = None) -> ProcessResult:
        return self._run_named("git", args, cwd=cwd)

    def gh(self, args: Sequence[str], *, cwd: Path | None = None) -> ProcessResult:
        return self._run_named("gh", args, cwd=cwd)
