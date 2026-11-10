#!/usr/bin/env python3
"""Build deterministic generated report PR evidence."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, Literal

EvidenceStatus = Literal["passed", "not run", "not required", "failed"]
ALLOWED_STATUSES: set[str] = {"passed", "not run", "not required", "failed"}

REQUIRED_SCOPE_LIMITATIONS: tuple[str, ...] = (
    "This PR adds a deterministic Markdown report only.",
    "This PR does not call an LLM.",
    "This PR does not provide investment advice or trading recommendations.",
    "This PR does not publish or deploy the report.",
    "This PR does not auto-merge.",
    "This PR does not introduce secrets or paid API keys.",
    "This PR does not commit generated `_site/` output.",
)


@dataclass(frozen=True)
class EvidenceField:
    name: str
    status: EvidenceStatus
    value: str
    detail: str = ""

    def to_markdown(self) -> str:
        detail = f" — {self.detail}" if self.detail else ""
        return f"{self.name}: `{self.status}` — {self.value}{detail}"


@dataclass(frozen=True)
class ReportPrEvidence:
    summary: str
    source_snapshot: EvidenceField
    generated_report: EvidenceField
    snapshot_quality: EvidenceField
    required_sources: EvidenceField
    optional_exchange_sources: EvidenceField
    selected_exchange_crosscheck: EvidenceField
    report_validation: EvidenceField
    advice_language_check: EvidenceField
    unit_tests: EvidenceField
    static_site_build: EvidenceField
    rendered_archive_path: EvidenceField
    changed_files: EvidenceField
    site_committed: EvidenceField
    workflow_run: EvidenceField
    scope_limitations: tuple[str, ...] = REQUIRED_SCOPE_LIMITATIONS

    def fields(self) -> tuple[EvidenceField, ...]:
        return (
            self.source_snapshot,
            self.generated_report,
            self.snapshot_quality,
            self.required_sources,
            self.optional_exchange_sources,
            self.selected_exchange_crosscheck,
            self.report_validation,
            self.advice_language_check,
            self.unit_tests,
            self.static_site_build,
            self.rendered_archive_path,
            self.changed_files,
            self.site_committed,
            self.workflow_run,
            EvidenceField(
                name="Scope limitations",
                status="passed",
                value="included",
                detail="generated PR body includes required product and automation boundaries",
            ),
        )

    def to_manifest(self) -> dict[str, object]:
        return {
            "summary": self.summary,
            "fields": [asdict(field) for field in self.fields()],
            "scope_limitations": list(self.scope_limitations),
        }

    def to_markdown(self) -> str:
        lines: list[str] = [
            "## Summary",
            "",
            self.summary,
            "",
            "## Report evidence",
            "",
        ]
        for field in self.fields():
            lines.append(field.to_markdown())
            lines.append("")
        lines.extend([
            "## Scope limitations",
            "",
            *[f"- {limitation}" for limitation in self.scope_limitations],
            "",
        ])
        return "\n".join(lines)


def validate_status(value: str) -> EvidenceStatus:
    if value not in ALLOWED_STATUSES:
        allowed = ", ".join(sorted(ALLOWED_STATUSES))
        raise ValueError(f"Unsupported evidence status {value!r}; expected one of: {allowed}")
    return value  # type: ignore[return-value]


def evidence_field(name: str, status: str, value: str, detail: str = "") -> EvidenceField:
    return EvidenceField(name=name, status=validate_status(status), value=value, detail=detail)


def comma_list(values: Iterable[str]) -> str:
    clean = [value.strip() for value in values if value.strip()]
    return ", ".join(clean) if clean else "none"


def build_report_pr_evidence(args: argparse.Namespace) -> ReportPrEvidence:
    changed_files = comma_list(args.changed_file)
    required_sources = comma_list(args.required_source)
    optional_exchange_sources = comma_list(args.optional_exchange_source)

    return ReportPrEvidence(
        summary="Adds one deterministic raw Markdown crypto report generated from one validated source snapshot.",
        source_snapshot=evidence_field("Source snapshot", args.source_snapshot_status, args.source_snapshot),
        generated_report=evidence_field("Generated report", args.generated_report_status, args.generated_report),
        snapshot_quality=evidence_field("Snapshot quality", args.snapshot_quality_status, args.snapshot_quality),
        required_sources=evidence_field("Required sources", args.required_sources_status, required_sources),
        optional_exchange_sources=evidence_field(
            "Optional exchange sources",
            args.optional_exchange_sources_status,
            optional_exchange_sources,
        ),
        selected_exchange_crosscheck=evidence_field(
            "Selected exchange cross-check",
            args.selected_exchange_status,
            args.selected_exchange_crosscheck,
        ),
        report_validation=evidence_field("Report validation", args.report_validation_status, args.report_validation),
        advice_language_check=evidence_field(
            "Advice-language check",
            args.advice_language_status,
            args.advice_language_check,
        ),
        unit_tests=evidence_field("Unit tests", args.unit_tests_status, args.unit_tests),
        static_site_build=evidence_field("Static site build", args.static_site_build_status, args.static_site_build),
        rendered_archive_path=evidence_field(
            "Rendered archive path",
            args.rendered_archive_status,
            args.rendered_archive_path,
        ),
        changed_files=evidence_field("Changed files", args.changed_files_status, changed_files),
        site_committed=evidence_field("_site committed", args.site_committed_status, args.site_committed),
        workflow_run=evidence_field("Workflow run", args.workflow_run_status, args.workflow_run),
    )


def write_text(path: str | None, body: str) -> None:
    if path:
        Path(path).write_text(body, encoding="utf-8")
    else:
        print(body, end="")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-snapshot", required=True)
    parser.add_argument("--source-snapshot-status", default="passed")
    parser.add_argument("--generated-report", required=True)
    parser.add_argument("--generated-report-status", default="passed")
    parser.add_argument("--snapshot-quality", required=True)
    parser.add_argument("--snapshot-quality-status", default="passed")
    parser.add_argument("--required-source", action="append", default=[])
    parser.add_argument("--required-sources-status", default="passed")
    parser.add_argument("--optional-exchange-source", action="append", default=[])
    parser.add_argument("--optional-exchange-sources-status", default="not required")
    parser.add_argument("--selected-exchange-crosscheck", required=True)
    parser.add_argument("--selected-exchange-status", default="passed")
    parser.add_argument("--report-validation", default="python scripts/validate_crypto_report.py")
    parser.add_argument("--report-validation-status", default="passed")
    parser.add_argument("--advice-language-check", default="deterministic report validator")
    parser.add_argument("--advice-language-status", default="passed")
    parser.add_argument("--unit-tests", default="python -m unittest discover -s tests")
    parser.add_argument("--unit-tests-status", default="passed")
    parser.add_argument("--static-site-build", default="python -m site_generator")
    parser.add_argument("--static-site-build-status", default="passed")
    parser.add_argument("--rendered-archive-path", required=True)
    parser.add_argument("--rendered-archive-status", default="passed")
    parser.add_argument("--changed-file", action="append", default=[])
    parser.add_argument("--changed-files-status", default="passed")
    parser.add_argument("--site-committed", default="no")
    parser.add_argument("--site-committed-status", default="passed")
    parser.add_argument("--workflow-run", required=True)
    parser.add_argument("--workflow-run-status", default="passed")
    parser.add_argument("--markdown-output")
    parser.add_argument("--json-output")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    evidence = build_report_pr_evidence(args)

    markdown = evidence.to_markdown()
    manifest = json.dumps(evidence.to_manifest(), indent=2, sort_keys=True) + "\n"

    if args.markdown_output:
        write_text(args.markdown_output, markdown)
    else:
        print(markdown, end="")
    if args.json_output:
        write_text(args.json_output, manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
