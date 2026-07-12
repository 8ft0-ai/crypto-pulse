#!/usr/bin/env python3
"""Validate repository-internal Markdown navigation and generated-output boundaries."""

from __future__ import annotations

import argparse
import posixpath
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence
from urllib.parse import unquote, urlsplit

INLINE_LINK_RE = re.compile(
    r"(?<!!)\[[^\]]*\]\(\s*(<[^>]+>|[^\s)]+)(?:\s+(?:\"[^\"]*\"|'[^']*'|\([^)]*\)))?\s*\)"
)
IMAGE_LINK_RE = re.compile(
    r"!\[[^\]]*\]\(\s*(<[^>]+>|[^\s)]+)(?:\s+(?:\"[^\"]*\"|'[^']*'|\([^)]*\)))?\s*\)"
)
REFERENCE_LINK_RE = re.compile(r"^\s*\[[^\]]+\]:\s*(<[^>]+>|\S+)", re.MULTILINE)
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
METADATA_RE = re.compile(r"^\s*>\s*\*\*(Mode|Audience|Outcome):\*\*\s*(.*?)\s*$")
CANONICAL_FILENAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*\.md$")
MODE_CATALOGUES = {
    "Tutorials": "tutorials/",
    "How-to guides": "how-to/",
    "Reference": "reference/",
    "Explanation": "explanation/",
}
DECLARED_MODE_BY_DIRECTORY = {
    "tutorials": "Tutorial",
    "how-to": "How-to",
    "reference": "Reference",
    "explanation": "Explanation",
}
EXTERNAL_SCHEMES = {"http", "https", "mailto", "tel", "ftp", "data"}

# Add a path here when a compatibility file is deliberately removed. The validator
# will then report references to that path distinctly from ordinary missing targets.
REMOVED_DOCUMENT_PATHS: frozenset[str] = frozenset()


@dataclass(frozen=True, order=True)
class Diagnostic:
    source: str
    line: int
    code: str
    message: str

    def render(self) -> str:
        return f"{self.source}:{self.line}: {self.code}: {self.message}"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Validate internal Markdown links, canonical documentation structure, "
            "navigation and _site exclusion."
        )
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root. Defaults to the parent of scripts/.",
    )
    return parser.parse_args(argv)


def tracked_files(root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"],
        check=True,
        capture_output=True,
    )
    return sorted(item for item in result.stdout.decode("utf-8").split("\0") if item)


def strip_fenced_code(text: str) -> str:
    output: list[str] = []
    fence: str | None = None
    for line in text.splitlines(keepends=True):
        match = re.match(r"^\s*(`{3,}|~{3,})", line)
        if match:
            marker = match.group(1)[0]
            if fence is None:
                fence = marker
            elif fence == marker:
                fence = None
            output.append("\n" if line.endswith("\n") else "")
            continue
        output.append(("\n" if line.endswith("\n") else "") if fence else line)
    return "".join(output)


def markdown_links(text: str) -> list[tuple[int, str]]:
    stripped = strip_fenced_code(text)
    links: list[tuple[int, str]] = []
    for pattern in (INLINE_LINK_RE, IMAGE_LINK_RE, REFERENCE_LINK_RE):
        for match in pattern.finditer(stripped):
            target = match.group(1).strip()
            if target.startswith("<") and target.endswith(">"):
                target = target[1:-1].strip()
            line = stripped.count("\n", 0, match.start()) + 1
            links.append((line, target))
    return sorted(links)


def heading_anchors(text: str) -> set[str]:
    anchors: set[str] = set()
    counts: dict[str, int] = {}
    for line in strip_fenced_code(text).splitlines():
        match = HEADING_RE.match(line)
        if not match:
            continue
        heading = match.group(2)
        heading = re.sub(r"`([^`]*)`", r"\1", heading)
        heading = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", heading)
        heading = re.sub(r"<[^>]+>", "", heading)
        heading = heading.lower().strip()
        heading = re.sub(r"[^\w\- ]", "", heading, flags=re.UNICODE)
        base = re.sub(r"\s+", "-", heading)
        count = counts.get(base, 0)
        counts[base] = count + 1
        anchor = base if count == 0 else f"{base}-{count}"
        anchors.add(anchor)
    return anchors


def repository_relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def canonical_mode_for_path(relative_path: str) -> str | None:
    parts = Path(relative_path).parts
    if len(parts) < 3 or parts[0] != "docs" or parts[1] not in DECLARED_MODE_BY_DIRECTORY:
        return None
    if not relative_path.lower().endswith(".md"):
        return None
    return DECLARED_MODE_BY_DIRECTORY[parts[1]]


def canonical_pages(paths: Iterable[str]) -> dict[str, str]:
    return {
        path: mode
        for path in paths
        if (mode := canonical_mode_for_path(path)) is not None
    }


def validate_link(
    *,
    root: Path,
    source_path: Path,
    line: int,
    raw_target: str,
    removed_paths: frozenset[str],
) -> list[Diagnostic]:
    source = repository_relative(source_path, root)
    target = raw_target.strip()
    if not target:
        return [Diagnostic(source, line, "malformed-link", "empty link destination")]
    if "\\" in target:
        return [Diagnostic(source, line, "malformed-link", f"backslashes are not valid in relative links: {target}")]
    if target.startswith("//") or re.match(r"^[A-Za-z]:", target):
        return [Diagnostic(source, line, "malformed-link", f"unsupported absolute destination: {target}")]

    parsed = urlsplit(target)
    if parsed.scheme.lower() in EXTERNAL_SCHEMES or parsed.netloc:
        return []
    if parsed.scheme:
        return [Diagnostic(source, line, "malformed-link", f"unsupported link scheme: {parsed.scheme}")]
    if target.startswith("#"):
        fragment = unquote(parsed.fragment)
        if fragment and fragment not in heading_anchors(source_path.read_text(encoding="utf-8")):
            return [Diagnostic(source, line, "missing-anchor", f"heading '#{fragment}' does not exist")]
        return []
    if parsed.path.startswith("/"):
        return [Diagnostic(source, line, "malformed-link", f"use a repository-relative path, not: {target}")]

    decoded_path = unquote(parsed.path)
    destination = (source_path.parent / decoded_path).resolve()
    try:
        relative_destination = repository_relative(destination, root)
    except ValueError:
        return [Diagnostic(source, line, "repository-escape", f"link escapes the repository: {target}")]

    if relative_destination in removed_paths:
        return [Diagnostic(source, line, "removed-document-path", f"link targets removed path: {relative_destination}")]
    if not destination.exists():
        return [Diagnostic(source, line, "missing-target", f"target does not exist: {relative_destination}")]

    fragment = unquote(parsed.fragment)
    if fragment and destination.is_file() and destination.suffix.lower() == ".md":
        anchors = heading_anchors(destination.read_text(encoding="utf-8"))
        if fragment not in anchors:
            return [
                Diagnostic(
                    source,
                    line,
                    "missing-anchor",
                    f"heading '#{fragment}' does not exist in {relative_destination}",
                )
            ]
    return []


def mode_catalogue_links(index_text: str) -> list[tuple[str, int, str]]:
    current_mode: str | None = None
    results: list[tuple[str, int, str]] = []
    for line_number, line in enumerate(strip_fenced_code(index_text).splitlines(), start=1):
        heading = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if heading:
            level = len(heading.group(1))
            title = heading.group(2).strip()
            current_mode = title if level == 3 and title in MODE_CATALOGUES else None
            continue
        if current_mode and re.match(r"^\s*-\s+", line):
            link = INLINE_LINK_RE.search(line)
            if link:
                target = link.group(1).strip("<>")
                results.append((current_mode, line_number, target))
    return results


def validate_index(root: Path, paths: Sequence[str]) -> list[Diagnostic]:
    index_path = root / "docs" / "index.md"
    if not index_path.is_file():
        return [Diagnostic("docs/index.md", 1, "missing-index", "docs/index.md does not exist")]

    diagnostics: list[Diagnostic] = []
    tracked = set(paths)
    canonical = canonical_pages(paths)
    seen: dict[str, tuple[str, int]] = {}
    counts: dict[str, int] = {}

    for mode, line, target in mode_catalogue_links(index_path.read_text(encoding="utf-8")):
        parsed = urlsplit(target)
        expected_prefix = MODE_CATALOGUES[mode]
        if parsed.scheme or parsed.netloc or parsed.path.startswith("/"):
            diagnostics.append(
                Diagnostic("docs/index.md", line, "invalid-navigation", f"{mode} entry must be a relative docs path: {target}")
            )
            continue

        normalised = posixpath.normpath(unquote(parsed.path))
        repository_target = posixpath.normpath(posixpath.join("docs", normalised))
        target_mode = canonical_mode_for_path(repository_target)

        if not normalised.startswith(expected_prefix):
            diagnostics.append(
                Diagnostic(
                    "docs/index.md",
                    line,
                    "wrong-navigation-mode",
                    f"{mode} entry must target {expected_prefix}: {target}",
                )
            )
        if target_mode is None:
            diagnostics.append(
                Diagnostic(
                    "docs/index.md",
                    line,
                    "noncanonical-navigation",
                    f"{mode} entry must target a canonical Diátaxis page: {target}",
                )
            )
        if repository_target not in tracked:
            diagnostics.append(
                Diagnostic(
                    "docs/index.md",
                    line,
                    "untracked-navigation",
                    f"catalogue target is not a tracked file: {repository_target}",
                )
            )

        previous = seen.get(repository_target)
        if previous:
            previous_mode, previous_line = previous
            diagnostics.append(
                Diagnostic(
                    "docs/index.md",
                    line,
                    "duplicate-navigation",
                    f"{target} already appears in {previous_mode} at line {previous_line}",
                )
            )
        else:
            seen[repository_target] = (mode, line)
        counts[repository_target] = counts.get(repository_target, 0) + 1

    for path, declared_mode in sorted(canonical.items()):
        if counts.get(path, 0) == 0:
            diagnostics.append(
                Diagnostic(
                    path,
                    1,
                    "unindexed-canonical-page",
                    f"{declared_mode} page is absent from the matching docs/index.md mode catalogue",
                )
            )
    return diagnostics


def validate_canonical_page(root: Path, relative_path: str, expected_mode: str) -> list[Diagnostic]:
    path = root / relative_path
    diagnostics: list[Diagnostic] = []

    if not CANONICAL_FILENAME_RE.fullmatch(path.name):
        diagnostics.append(
            Diagnostic(
                relative_path,
                1,
                "invalid-document-filename",
                "canonical documentation filenames must be lower-case and hyphenated",
            )
        )

    text = path.read_text(encoding="utf-8")
    stripped = strip_fenced_code(text)
    h1_lines = [
        line_number
        for line_number, line in enumerate(stripped.splitlines(), start=1)
        if (match := HEADING_RE.match(line)) and len(match.group(1)) == 1
    ]
    if not h1_lines:
        diagnostics.append(Diagnostic(relative_path, 1, "missing-h1", "canonical page must contain exactly one H1"))
    elif len(h1_lines) > 1:
        diagnostics.append(
            Diagnostic(
                relative_path,
                h1_lines[1],
                "multiple-h1",
                f"canonical page contains {len(h1_lines)} H1 headings; exactly one is required",
            )
        )

    metadata: dict[str, list[tuple[int, str]]] = {"Mode": [], "Audience": [], "Outcome": []}
    for line_number, line in enumerate(text.splitlines()[:15], start=1):
        match = METADATA_RE.match(line)
        if match:
            metadata[match.group(1)].append((line_number, match.group(2).strip()))

    for field in ("Mode", "Audience", "Outcome"):
        values = metadata[field]
        if not values:
            diagnostics.append(
                Diagnostic(
                    relative_path,
                    1,
                    "missing-page-metadata",
                    f"canonical page must declare {field} in the visible metadata block near the top",
                )
            )
        elif len(values) > 1:
            diagnostics.append(
                Diagnostic(
                    relative_path,
                    values[1][0],
                    "duplicate-page-metadata",
                    f"canonical page declares {field} more than once near the top",
                )
            )

    if metadata["Mode"]:
        line, actual_mode = metadata["Mode"][0]
        if actual_mode != expected_mode:
            diagnostics.append(
                Diagnostic(
                    relative_path,
                    line,
                    "declared-mode-mismatch",
                    f"declared mode {actual_mode!r} does not match directory mode {expected_mode!r}",
                )
            )

    return diagnostics


def validate_tracked_site(paths: Iterable[str]) -> list[Diagnostic]:
    committed = sorted(path for path in paths if path == "_site" or path.startswith("_site/"))
    return [
        Diagnostic(path, 1, "committed-generated-site", "_site is disposable output and must not be tracked")
        for path in committed
    ]


def validate_repository(
    root: Path,
    *,
    tracked: Sequence[str] | None = None,
    removed_paths: frozenset[str] = REMOVED_DOCUMENT_PATHS,
) -> list[Diagnostic]:
    root = root.resolve()
    paths = list(tracked if tracked is not None else tracked_files(root))
    diagnostics = validate_tracked_site(paths)
    canonical = canonical_pages(paths)

    for relative_path in sorted(path for path in paths if path.lower().endswith(".md")):
        source_path = (root / relative_path).resolve()
        if not source_path.is_file():
            diagnostics.append(Diagnostic(relative_path, 1, "missing-tracked-file", "tracked Markdown file is absent"))
            continue
        text = source_path.read_text(encoding="utf-8")
        for line, target in markdown_links(text):
            diagnostics.extend(
                validate_link(
                    root=root,
                    source_path=source_path,
                    line=line,
                    raw_target=target,
                    removed_paths=removed_paths,
                )
            )

    for relative_path, expected_mode in sorted(canonical.items()):
        path = root / relative_path
        if path.is_file():
            diagnostics.extend(validate_canonical_page(root, relative_path, expected_mode))

    diagnostics.extend(validate_index(root, paths))
    return sorted(set(diagnostics))


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    root = args.root.resolve()
    try:
        paths = tracked_files(root)
        diagnostics = validate_repository(root, tracked=paths)
    except (OSError, subprocess.CalledProcessError, UnicodeError) as exc:
        print(f"documentation-validation-error: {exc}", file=sys.stderr)
        return 1

    if diagnostics:
        for diagnostic in diagnostics:
            print(diagnostic.render(), file=sys.stderr)
        print(f"Documentation validation failed with {len(diagnostics)} error(s).", file=sys.stderr)
        return 1

    markdown_count = sum(path.lower().endswith(".md") for path in paths)
    print(f"Documentation validation passed: {markdown_count} tracked Markdown file(s) checked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
