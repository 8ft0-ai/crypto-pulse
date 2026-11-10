#!/usr/bin/env python3
"""Validate deterministic CryptoPulse Markdown reports.

The report validator is intentionally deterministic and local-only. It reads a
raw Markdown report, checks its front matter and required sections, verifies the
referenced source snapshot exists, and rejects advice-like language. It does not
build `_site/`, call an LLM, fetch live data, or publish anything.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

REPORT_SCHEMA_VERSION = "deterministic-crypto-report/v1"
VALID_QUALITY_STATUSES = {"valid-ok", "valid-degraded"}

REQUIRED_FRONT_MATTER = {
    "schema_version",
    "report_type",
    "source_snapshot",
    "generated_at_utc",
    "generated_at_local",
    "timezone",
    "cadence",
    "quality_status",
    "no_investment_advice",
    "llm_generated",
}

REQUIRED_SECTIONS = [
    "## Product boundary and non-investment-advice notice",
    "## Snapshot quality",
    "## Market summary",
    "## DeFi and stablecoin summary",
    "## Exchange cross-check summary",
    "## Evidence and source status",
    "## Scope limitations",
]

ASSET_PATTERN = r"(?:BTC|ETH|SOL|bitcoin|ethereum|solana)"
EXPLICIT_ASSET_ACTION_PATTERNS = [
    re.compile(rf"\b(?:buy|sell|hold|accumulate|short|long)\s+{ASSET_PATTERN}\b", re.IGNORECASE),
    re.compile(rf"\b{ASSET_PATTERN}\s+(?:buy|sell|hold|accumulate|short|long)\b", re.IGNORECASE),
    re.compile(rf"\b(?:go|stay|remain)\s+(?:long|short)\s+(?:on\s+)?{ASSET_PATTERN}\b", re.IGNORECASE),
]
BROAD_ADVICE_PATTERNS = [
    re.compile(r"\btarget price\b|\bprice target\b", re.IGNORECASE),
    re.compile(r"\btrading signal\b", re.IGNORECASE),
    re.compile(r"\bposition guidance\b", re.IGNORECASE),
    re.compile(r"\bentry point\b|\bexit point\b", re.IGNORECASE),
    re.compile(r"\bstop[- ]loss\b|\btake[- ]profit\b", re.IGNORECASE),
]
BOUNDARY_LINE_MARKERS = (
    "not ",
    "does not",
    "do not",
    "no ",
    "without",
    "non-investment-advice",
    "scope limitation",
)


class ReportValidationError(ValueError):
    """Raised when a deterministic Markdown report fails validation."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate deterministic CryptoPulse Markdown reports.")
    parser.add_argument("path", help="Markdown report file or directory containing .md reports.")
    parser.add_argument(
        "--root",
        default=".",
        help="Repository root used to resolve relative source_snapshot paths. Defaults to the current directory.",
    )
    return parser.parse_args()


def strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def parse_front_matter(text: str) -> tuple[dict[str, str], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ReportValidationError("report must start with YAML front matter")

    end_index = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_index = index
            break
    if end_index is None:
        raise ReportValidationError("front matter is missing a closing --- delimiter")

    fields: dict[str, str] = {}
    for raw_line in lines[1:end_index]:
        line = raw_line.rstrip()
        if not line or line.startswith("  - "):
            continue
        if ":" not in line:
            raise ReportValidationError(f"front matter line is not a key/value pair: {line}")
        key, value = line.split(":", 1)
        key = key.strip()
        if key:
            fields[key] = strip_quotes(value)

    body = "\n".join(lines[end_index + 1 :])
    return fields, body


def normalised_bool(value: str) -> str:
    return value.strip().lower()


def validate_front_matter(fields: dict[str, str], report_path: Path, root: Path) -> None:
    missing = sorted(REQUIRED_FRONT_MATTER - set(fields))
    if missing:
        raise ReportValidationError("missing required front matter fields: " + ", ".join(missing))

    if fields["schema_version"] != REPORT_SCHEMA_VERSION:
        raise ReportValidationError(f"schema_version must be {REPORT_SCHEMA_VERSION}")
    if fields["report_type"] != "crypto_market_snapshot":
        raise ReportValidationError("report_type must be crypto_market_snapshot")
    if fields["quality_status"] not in VALID_QUALITY_STATUSES:
        raise ReportValidationError("quality_status must be valid-ok or valid-degraded")
    if normalised_bool(fields["no_investment_advice"]) != "true":
        raise ReportValidationError("no_investment_advice must be true")
    if normalised_bool(fields["llm_generated"]) != "false":
        raise ReportValidationError("llm_generated must be false")

    for key in ("source_snapshot", "generated_at_utc", "generated_at_local", "timezone", "cadence"):
        if not fields[key].strip() or fields[key].strip().lower() == "null":
            raise ReportValidationError(f"{key} must be populated")

    source_snapshot = Path(fields["source_snapshot"])
    candidates = [source_snapshot] if source_snapshot.is_absolute() else [root / source_snapshot, report_path.parent / source_snapshot]
    if not any(candidate.exists() and candidate.is_file() for candidate in candidates):
        raise ReportValidationError(f"source_snapshot does not point to an existing file: {fields['source_snapshot']}")


def validate_required_sections(body: str) -> None:
    body_lines = set(body.splitlines())
    missing = [section for section in REQUIRED_SECTIONS if section not in body_lines]
    if missing:
        raise ReportValidationError("missing required report sections: " + ", ".join(missing))


def validate_product_boundary_language(body: str) -> None:
    lower = body.lower()
    required_phrases = [
        "not financial advice",
        "investment research",
        "recommendation",
        "trading signal",
        "buy, sell, or hold",
    ]
    missing = [phrase for phrase in required_phrases if phrase not in lower]
    if missing:
        raise ReportValidationError("missing product-boundary/non-investment-advice language: " + ", ".join(missing))


def validate_evidence_references(body: str) -> None:
    lower = body.lower()
    if "## evidence and source status" not in lower:
        raise ReportValidationError("missing evidence/source status section")
    if "source snapshot:" not in lower:
        raise ReportValidationError("missing source snapshot evidence reference")
    if "| source | status |" not in lower:
        raise ReportValidationError("missing source status evidence table")


def is_boundary_line(line: str) -> bool:
    lower = line.lower()
    return any(marker in lower for marker in BOUNDARY_LINE_MARKERS)


def validate_advice_language(body: str) -> None:
    for line_number, line in enumerate(body.splitlines(), start=1):
        for pattern in EXPLICIT_ASSET_ACTION_PATTERNS:
            if pattern.search(line):
                raise ReportValidationError(f"prohibited advice-like asset action on line {line_number}: {line.strip()}")
        for pattern in BROAD_ADVICE_PATTERNS:
            if pattern.search(line) and not is_boundary_line(line):
                raise ReportValidationError(f"prohibited advice-like phrase on line {line_number}: {line.strip()}")


def validate_report(path: Path, root: Path | None = None) -> None:
    root = (root or Path.cwd()).resolve()
    report_path = path.resolve()
    try:
        text = report_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ReportValidationError(f"report not found: {path}") from exc

    fields, body = parse_front_matter(text)
    validate_front_matter(fields, report_path, root)
    validate_required_sections(body)
    validate_product_boundary_language(body)
    validate_evidence_references(body)
    validate_advice_language(body)


def iter_report_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    if path.is_dir():
        return sorted(path.rglob("*.md"))
    raise SystemExit(f"Path not found: {path}")


def main() -> int:
    args = parse_args()
    files = iter_report_files(Path(args.path))
    if not files:
        print(f"No Markdown report files found under {args.path}", file=sys.stderr)
        return 1

    failures: list[str] = []
    root = Path(args.root)
    for path in files:
        try:
            validate_report(path, root)
        except ReportValidationError as exc:
            failures.append(f"{path}: {exc}")

    if failures:
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1

    print(f"Validated {len(files)} deterministic crypto report file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
