"""Public-demo validation refinements for grounded human-readable prose.

The canonical validator remains authoritative. This module removes only diagnostics
that can be independently re-proven from the claim's cited evidence: supported ISO
dates, bounded decimal rounding with exact quoted values, source-label aliases, and
common sentence-opening function words. No output is repaired or inferred.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Any, Mapping

from .contracts import canonical_json_bytes
from .diagnostics import Diagnostic, ValidationReport, stable_report
from .pipeline import PipelineResult
from .render import render_markdown
from .validate import iter_claims, validate_analysis

ISO_DATE_RE = re.compile(r"(?<!\d)\d{4}-\d{2}-\d{2}(?!\d)")
APPROXIMATION_RE = re.compile(r"\b(?:approximately|approx\.?|about|around|roughly)\b", re.I)
NEGATIVE_DIRECTION_RE = re.compile(r"\b(?:decreased|declined|fell|fallen|down|dropped|lower)\b", re.I)
SENTENCE_OPENERS = frozenset(
    {
        "as",
        "in",
        "over",
        "several",
        "during",
        "across",
        "while",
        "although",
        "however",
        "overall",
        "meanwhile",
        "additionally",
        "by",
        "at",
        "on",
        "from",
        "after",
        "before",
        "based",
    }
)
_QUOTED_TOKEN_RE = re.compile(r"'([^']+)'")


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _subject(item: Mapping[str, Any]) -> Mapping[str, Any]:
    value = item.get("subject")
    return value if isinstance(value, Mapping) else {}


def _source(item: Mapping[str, Any]) -> Mapping[str, Any]:
    value = item.get("source")
    return value if isinstance(value, Mapping) else {}


def _evidence_map(bundle: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        str(item["evidence_id"]): item
        for item in _list(bundle.get("evidence"))
        if isinstance(item, Mapping) and isinstance(item.get("evidence_id"), str)
    }


def _diagnostic_token(diagnostic: Diagnostic) -> str | None:
    match = _QUOTED_TOKEN_RE.search(diagnostic.message)
    return match.group(1) if match else None


def _normalised_number(value: str) -> Decimal | None:
    try:
        return Decimal(value.replace(",", "").strip())
    except InvalidOperation:
        return None


def _decimal_places(value: str) -> int:
    text = value.replace(",", "").strip()
    return len(text.partition(".")[2]) if "." in text else 0


def _referenced_evidence(
    claim: Mapping[str, Any], evidence_by_id: Mapping[str, Mapping[str, Any]]
) -> dict[str, Mapping[str, Any]]:
    return {
        evidence_id: evidence_by_id[evidence_id]
        for evidence_id in _list(claim.get("evidence_ids"))
        if isinstance(evidence_id, str) and evidence_id in evidence_by_id
    }


def _safe_sentence_opener(token: str, text: str) -> bool:
    if token.casefold() not in SENTENCE_OPENERS:
        return False
    return bool(re.search(rf"(?:^|[.!?]\s+){re.escape(token)}\b", text))


def _label_aliases(item: Mapping[str, Any]) -> set[str]:
    labels = {
        _subject(item).get("name"),
        _subject(item).get("symbol"),
        _source(item).get("name"),
    }
    aliases: set[str] = set()
    for label in labels:
        if not isinstance(label, str) or len(label.strip()) < 2:
            continue
        folded = label.strip().casefold()
        aliases.add(folded)
        aliases.add(re.sub(r"[_-]+", " ", folded))
    return aliases


def _safe_entity_alias(
    token: str,
    claim: Mapping[str, Any],
    evidence_by_id: Mapping[str, Mapping[str, Any]],
) -> bool:
    supported = set().union(
        *(
            _label_aliases(item)
            for item in _referenced_evidence(claim, evidence_by_id).values()
        )
    )
    return re.sub(r"[_-]+", " ", token.casefold()) in supported


def _safe_iso_date(
    token: str,
    text: str,
    claim: Mapping[str, Any],
    evidence_by_id: Mapping[str, Mapping[str, Any]],
) -> bool:
    token_number = _normalised_number(token)
    if token_number is None:
        return False
    allowed_dates: set[str] = set()
    for item in _referenced_evidence(claim, evidence_by_id).values():
        candidates = [item.get("observed_at")]
        if item.get("evidence_type") == "timestamp":
            candidates.append(item.get("value"))
        for candidate in candidates:
            if isinstance(candidate, str):
                match = ISO_DATE_RE.search(candidate)
                if match:
                    allowed_dates.add(match.group(0))
    for date_text in ISO_DATE_RE.findall(text):
        if date_text not in allowed_dates:
            continue
        if any(_normalised_number(part) == token_number for part in date_text.split("-")):
            return True
    return False


def _safe_rounded_number(
    token: str,
    text: str,
    claim: Mapping[str, Any],
    evidence_by_id: Mapping[str, Mapping[str, Any]],
) -> bool:
    if not APPROXIMATION_RE.search(text):
        return False
    displayed = _normalised_number(token)
    if displayed is None:
        return False
    places = _decimal_places(token)
    quantum = Decimal(1).scaleb(-places)
    referenced = _referenced_evidence(claim, evidence_by_id)
    for quoted in _list(claim.get("quoted_values")):
        if not isinstance(quoted, Mapping):
            continue
        evidence_id = quoted.get("evidence_id")
        evidence = referenced.get(evidence_id) if isinstance(evidence_id, str) else None
        if not evidence or evidence.get("evidence_type") != "number":
            continue
        if quoted.get("value") != evidence.get("value") or quoted.get("unit") != evidence.get("unit"):
            continue
        try:
            exact = Decimal(str(evidence["value"]))
        except (InvalidOperation, KeyError):
            continue
        candidates = {exact.quantize(quantum, rounding=ROUND_HALF_UP)}
        if exact < 0 and claim.get("claim_type") == "directional_observation" and NEGATIVE_DIRECTION_RE.search(text):
            candidates.add(abs(exact).quantize(quantum, rounding=ROUND_HALF_UP))
        if displayed in candidates:
            return True
    return False


def filter_public_demo_diagnostics(
    report: ValidationReport,
    bundle: Mapping[str, Any],
    analysis: Mapping[str, Any],
) -> ValidationReport:
    """Remove only diagnostics re-proven safe from cited evidence."""

    claims = {path: claim for path, claim in iter_claims(dict(analysis))}
    evidence_by_id = _evidence_map(bundle)
    retained: list[Diagnostic] = []
    for diagnostic in report.diagnostics:
        claim_path = diagnostic.path.removesuffix(".text")
        claim = claims.get(claim_path)
        token = _diagnostic_token(diagnostic)
        text = str(claim.get("text", "")) if isinstance(claim, Mapping) else ""
        safe = False
        if claim is not None and token is not None:
            if diagnostic.code == "untraceable_entity":
                safe = _safe_sentence_opener(token, text)
            elif diagnostic.code == "entity_mismatch":
                safe = _safe_entity_alias(token, claim, evidence_by_id)
            elif diagnostic.code == "untraceable_number":
                safe = _safe_iso_date(token, text, claim, evidence_by_id) or _safe_rounded_number(
                    token, text, claim, evidence_by_id
                )
        if not safe:
            retained.append(diagnostic)
    return stable_report(retained)


def process_public_demo_analysis(
    bundle: dict[str, Any],
    analysis: dict[str, Any],
    *,
    evidence_schema: dict[str, Any],
    analysis_schema: dict[str, Any],
) -> PipelineResult:
    """Run canonical validation plus evidence-proven public-demo refinements."""

    canonical = validate_analysis(
        bundle,
        analysis,
        evidence_schema=evidence_schema,
        analysis_schema=analysis_schema,
    )
    report = filter_public_demo_diagnostics(canonical, bundle, analysis)
    if not report.is_valid:
        return PipelineResult(report=report, normalised_analysis=None, markdown=None)
    normalised = canonical_json_bytes(analysis) + b"\n"
    markdown = render_markdown(bundle, analysis, report)
    return PipelineResult(report=report, normalised_analysis=normalised, markdown=markdown)
