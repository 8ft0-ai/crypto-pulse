from __future__ import annotations

import os
from pathlib import Path
import shutil

from ..environment import PrerequisiteError
from ..process import ProcessRunner
from ._common import prepare_repository

_CACHE_ROOTS = ("site_generator", "scripts", "tests", "tools/dev")


def _within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _validate_candidate(
    path: Path,
    *,
    repository_root: Path,
    allow_root: Path,
    label: str,
) -> Path:
    if path.is_symlink():
        raise PrerequisiteError(f"refusing to clean symlinked {label}: {path}")
    resolved = path.resolve()
    if not _within(resolved, repository_root) or not _within(resolved, allow_root):
        raise PrerequisiteError(f"refusing to clean escaped {label}: {path}")
    return resolved


def _discover(root: Path) -> tuple[Path | None, tuple[Path, ...], tuple[Path, ...]]:
    repository_root = root.resolve()
    site = root / "_site"
    site_candidate: Path | None = None
    if site.is_symlink():
        raise PrerequisiteError("refusing to clean symlinked _site")
    if site.exists():
        if not site.is_dir() or site.resolve() != repository_root / "_site":
            raise PrerequisiteError("refusing to clean unsafe _site")
        site_candidate = site.resolve()

    cache_dirs: list[Path] = []
    pyc_files: list[Path] = []
    for relative in _CACHE_ROOTS:
        allow = root / relative
        if not allow.exists():
            continue
        if allow.is_symlink() or not allow.is_dir():
            raise PrerequisiteError(
                f"refusing to clean unsafe allowlist root: {relative}"
            )
        allow_root = allow.resolve()
        if not _within(allow_root, repository_root):
            raise PrerequisiteError(
                f"refusing to clean escaped allowlist root: {relative}"
            )
        for current, dirnames, filenames in os.walk(allow_root, followlinks=False):
            current_path = Path(current)
            kept_dirs: list[str] = []
            for name in dirnames:
                candidate = current_path / name
                if name == "__pycache__":
                    cache_dirs.append(
                        _validate_candidate(
                            candidate,
                            repository_root=repository_root,
                            allow_root=allow_root,
                            label="__pycache__",
                        )
                    )
                else:
                    kept_dirs.append(name)
            dirnames[:] = kept_dirs
            for name in filenames:
                if not name.endswith(".pyc"):
                    continue
                candidate = current_path / name
                pyc_files.append(
                    _validate_candidate(
                        candidate,
                        repository_root=repository_root,
                        allow_root=allow_root,
                        label=".pyc",
                    )
                )
    return site_candidate, tuple(cache_dirs), tuple(pyc_files)


def run(
    *,
    cwd: Path | None = None,
    runner: ProcessRunner | None = None,
) -> int:
    root, _runner = prepare_repository(cwd=cwd, runner=runner)
    site, cache_dirs, pyc_files = _discover(root)
    if site is not None:
        shutil.rmtree(site)
    for path in cache_dirs:
        shutil.rmtree(path)
    for path in pyc_files:
        path.unlink()
    print(
        "OK clean: removed "
        f"{int(site is not None)} site tree, "
        f"{len(cache_dirs)} cache directories and {len(pyc_files)} .pyc files"
    )
    return 0
