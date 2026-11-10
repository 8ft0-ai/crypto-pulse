"""Align public-demo negative-magnitude validation with the trusted prompt.

The existing public-demo validator remains authoritative. This adapter removes only
``untraceable_number`` diagnostics that can be re-proven from exact cited negative
evidence plus explicit negative-direction wording. It does not repair model output,
rewrite claim types, or add numeric tolerance.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Mapping

from .contracts import canonical_json_bytes
from .diagnostics import Diagnostic, ValidationReport, stable_report
from .pipeline import PipelineResult
from .public_demo_validation import filter_public_demo_diagnostics
from .render import render_markdown
from .validate import iter_claims, validate_analysis

_TOKEN_RE = re.compile(r"'([^']+)'")
_APPROXIMATION_RE = re.compile(
    r"\b(?:approximately|approx\.?|about|around|roughly)\b", re.I
)
_NEGATIVE_DIRECTION_RE = re.compile(
    r"\b(?:decreased|declined|fell|fallen|down|dropped|lower)\b", re.I
)


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _decimal(value: Any) -> Decimal | None:
    try:
        return Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, ValueError):
        return None


def _decimal_places(token: str) -> int:
    text = token.replace(",", "").strip()
    return len(text.partition(".")[2]) if "." in text else 0


def _evidence_map(bundle: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        str(item["evidence_id"]): item
        for item in _list(bundle.get("evidence"))
        if isinstance(item, Mapping) and isinstance(item.get("evidence_id"), str)
    }


def _safe_negative_magnitude(
    diagnostic: Diagnostic,
    claim: Mapping[str, Any],
    evidence_by_id: Mapping[str, Mapping[str, Any]],
) -> bool:
    if diagnostic.code != "untraceable_number":
        return False
    token_match = _TOKEN_RE.search(diagnostic.message)
    if token_match is None:
        return False
    text = str(claim.get("text", ""))
    if not _NEGATIVE_DIRECTION_RE.search(text):
        return False
    displayed = _decimal(token_match.group(1))
    if displayed is None:
        return False

    referenced_ids = {
        item
        for item in _list(claim.get("evidence_ids"))
        if isinstance(item, str) and item in evidence_by_id
    }
    approximate = bool(_APPROXIMATION_RE.search(text))
    places = _decimal_places(token_match.group(1))
    quantum = Decimal(1).scaleb(-places)

    for quoted in _list(claim.get("quoted_values")):
        if not isinstance(quoted, Mapping):
            continue
        evidence_id = quoted.get("evidence_id")
        if not isinstance(evidence_id, str) or evidence_id not in referenced_ids:
            continue
        evidence = evidence_by_id[evidence_id]
        if evidence.get("evidence_type") != "number":
            continue
        if quoted.get("value") != evidence.get("value"):
            continue
        if quoted.get("unit") != evidence.get("unit"):
            continue
        exact = _decimal(evidence.get("value"))
        if exact is None or exact >= 0:
            continue
        absolute = abs(exact)
        if displayed == absolute:
            return True
        if approximate and displayed == absolute.quantize(
            quantum, rounding=ROUND_HALF_UP
        ):
            return True
    return False


def filter_negative_magnitude_diagnostics(
    report: ValidationReport,
    bundle: Mapping[str, Any],
    analysis: Mapping[str, Any],
) -> ValidationReport:
    """Remove only prompt-authorised negative-magnitude diagnostics."""

    claims = {path: claim for path, claim in iter_claims(dict(analysis))}
    evidence_by_id = _evidence_map(bundle)
    retained: list[Diagnostic] = []
    for diagnostic in report.diagnostics:
        claim = claims.get(diagnostic.path.removesuffix(".text"))
        if not isinstance(claim, Mapping) or not _safe_negative_magnitude(
            diagnostic, claim, evidence_by_id
        ):
            retained.append(diagnostic)
    return stable_report(retained)


def process_public_demo_analysis_with_negative_magnitude(
    bundle: dict[str, Any],
    analysis: dict[str, Any],
    *,
    evidence_schema: dict[str, Any],
    analysis_schema: dict[str, Any],
) -> PipelineResult:
    """Run canonical and public-demo validation plus the exact sign adapter."""

    canonical = validate_analysis(
        bundle,
        analysis,
        evidence_schema=evidence_schema,
        analysis_schema=analysis_schema,
    )
    public_demo = filter_public_demo_diagnostics(canonical, bundle, analysis)
    report = filter_negative_magnitude_diagnostics(public_demo, bundle, analysis)
    if not report.is_valid:
        return PipelineResult(report=report, normalised_analysis=None, markdown=None)
    normalised = canonical_json_bytes(analysis) + b"\n"
    markdown = render_markdown(bundle, analysis, report)
    return PipelineResult(report=report, normalised_analysis=normalised, markdown=markdown)
