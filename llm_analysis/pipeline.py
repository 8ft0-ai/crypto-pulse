"""Offline validation, normalisation, and rendering entrypoint."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .contracts import canonical_json_bytes
from .diagnostics import ValidationReport
from .render import render_markdown
from .validate import validate_analysis


@dataclass(frozen=True)
class PipelineResult:
    report: ValidationReport
    normalised_analysis: bytes | None
    markdown: bytes | None


def load_json(path: str | Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object in {path}")
    return value


def process_analysis(bundle: dict[str, Any], analysis: dict[str, Any], *, evidence_schema: dict[str, Any], analysis_schema: dict[str, Any]) -> PipelineResult:
    report = validate_analysis(bundle, analysis, evidence_schema=evidence_schema, analysis_schema=analysis_schema)
    if not report.is_valid:
        return PipelineResult(report=report, normalised_analysis=None, markdown=None)
    normalised = canonical_json_bytes(analysis) + b"\n"
    markdown = render_markdown(bundle, analysis, report)
    return PipelineResult(report=report, normalised_analysis=normalised, markdown=markdown)
