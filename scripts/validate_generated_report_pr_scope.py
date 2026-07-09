#!/usr/bin/env python3
"""Validate changed-file scope for generated crypto report PRs."""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Iterable


@dataclass(frozen=True)
class ScopeValidationResult:
    allowed_paths: tuple[str, ...]
    rejected_paths: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not self.rejected_paths


class ScopeValidationError(ValueError):
    """Raised when changed files are outside the generated-report scope."""


def normalise_path(path: str) -> str:
    return path.strip().replace("\\", "/")


def is_generated_report_markdown(path: str) -> bool:
    candidate = PurePosixPath(path)
    parts = candidate.parts
    if len(parts) < 5:
        return False
    if parts[:3] != ("reports", "crypto", "hourly"):
        return False
    return candidate.suffix == ".md"


def is_allowed_generated_report_path(path: str) -> bool:
    if not path or path.startswith("/") or ".." in PurePosixPath(path).parts:
        return False
    if path.startswith("_site/"):
        return False
    return is_generated_report_markdown(path)


def validate_changed_paths(paths: Iterable[str]) -> ScopeValidationResult:
    allowed: list[str] = []
    rejected: list[str] = []

    for raw_path in paths:
        path = normalise_path(raw_path)
        if not path:
            continue
        if is_allowed_generated_report_path(path):
            allowed.append(path)
        else:
            rejected.append(path)

    return ScopeValidationResult(tuple(allowed), tuple(rejected))


def validate_or_raise(paths: Iterable[str]) -> ScopeValidationResult:
    result = validate_changed_paths(paths)
    if not result.passed:
        rejected = "\n".join(f"- {path}" for path in result.rejected_paths)
        raise ScopeValidationError(f"Generated report PR contains unexpected changed files:\n{rejected}")
    return result


def read_paths_from_args(args: argparse.Namespace) -> list[str]:
    paths: list[str] = []
    if args.from_file:
        with open(args.from_file, encoding="utf-8") as handle:
            paths.extend(line.strip() for line in handle)
    paths.extend(args.paths)
    if not paths and not sys.stdin.isatty():
        paths.extend(line.strip() for line in sys.stdin)
    return paths


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="*", help="Changed paths to validate.")
    parser.add_argument("--from-file", help="Read changed paths from a newline-delimited file.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    paths = read_paths_from_args(args)

    try:
        result = validate_or_raise(paths)
    except ScopeValidationError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print("Generated report PR changed-file scope: passed")
    for path in result.allowed_paths:
        print(f"- {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
