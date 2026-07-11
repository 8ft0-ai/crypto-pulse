"""Deterministic Markdown rendering for accepted structured analysis."""

from __future__ import annotations

from typing import Any

from .diagnostics import ValidationReport


class InvalidAnalysisError(ValueError):
    def __init__(self, report: ValidationReport):
        super().__init__("analysis validation failed; no Markdown was rendered")
        self.report = report


def _plain(text: str) -> str:
    """Collapse model-controlled whitespace so it cannot create Markdown structure."""

    return " ".join(text.split())


def _escape_text(text: str) -> str:
    escaped = _plain(text).replace("\\", "\\\\")
    for character in "`*_[]<>#|":
        escaped = escaped.replace(character, "\\" + character)
    return escaped


def _code(text: str) -> str:
    return f"`{_plain(text).replace('`', 'ˋ')}`"


def _claim_lines(claim: dict[str, Any]) -> list[str]:
    ids = ", ".join(_code(item) for item in claim["evidence_ids"])
    return [
        f"- {_escape_text(claim['text'])}",
        f"  - Claim type: {_code(claim['claim_type'])}",
        f"  - Confidence: {_code(claim['confidence'])}",
        f"  - Evidence: {ids}",
    ]


def render_markdown(bundle: dict[str, Any], analysis: dict[str, Any], report: ValidationReport) -> bytes:
    if not report.is_valid:
        raise InvalidAnalysisError(report)
    lines = [
        "<!-- Deterministically rendered by llm_analysis.render; do not edit generated text. -->",
        "",
        f"# {_escape_text(analysis['headline']['text'])}",
        "",
        f"- Headline claim type: {_code(analysis['headline']['claim_type'])}",
        f"- Headline confidence: {_code(analysis['headline']['confidence'])}",
        f"- Headline evidence: {', '.join(_code(item) for item in analysis['headline']['evidence_ids'])}",
        "",
        "> **Product boundaries**",
    ]
    lines.extend(f"> - {_escape_text(item)}" for item in bundle["product_boundaries"])
    sections = (
        ("Market summary", analysis["market_summary"]),
        ("Key observations", analysis["key_observations"]),
        ("Risks and limitations", analysis["risks_and_limitations"]),
        ("Data quality", analysis["data_quality_notes"]),
    )
    for title, claims in sections:
        lines.extend(["", f"## {title}", ""])
        if claims:
            for claim in claims:
                lines.extend(_claim_lines(claim))
        else:
            lines.append("- No accepted claims.")
    lines.extend(["", "## Source evidence note", ""])
    lines.extend(_claim_lines(analysis["source_evidence_note"]))
    lines.extend([
        "",
        "---",
        "",
        f"Evidence bundle: {_code(analysis['evidence_bundle_id'])}  ",
        f"Analysis schema: {_code(analysis['schema_version'])}  ",
        f"Prompt version: {_code(analysis['prompt_version'])}",
        "",
    ])
    return "\n".join(lines).encode("utf-8")
