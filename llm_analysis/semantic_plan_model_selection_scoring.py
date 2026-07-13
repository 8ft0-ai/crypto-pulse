"""Case expectations and soft quality scoring for semantic claim plans."""
from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from .semantic_plan_model_selection_config import CaseExpectation


@dataclass(frozen=True)
class ExpectationResult:
    hard_pass: bool
    semantic_coverage: float
    materiality: float
    restraint: float
    diagnostics: tuple[str, ...]
    claim_signatures: tuple[str, ...]
    claim_count: int
    redundant_claim_count: int


def _claims(plan: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return [
        claim
        for section in plan.get("sections", [])
        if isinstance(section, Mapping)
        for claim in section.get("claims", [])
        if isinstance(claim, Mapping)
    ]


def _signature(claim: Mapping[str, Any]) -> str:
    evidence = claim.get("evidence_ids")
    identifiers = sorted(str(item) for item in evidence) if isinstance(evidence, list) else []
    return "|".join(
        (
            str(claim.get("intent") or ""),
            ",".join(identifiers),
            str(claim.get("comparison_relation") or ""),
        )
    )


def _redundant_claim_count(claims: list[Mapping[str, Any]]) -> int:
    signatures = [_signature(claim) for claim in claims]
    duplicates = len(signatures) - len(set(signatures))
    comparison_operands = [
        {str(item) for item in claim.get("evidence_ids", [])}
        for claim in claims
        if claim.get("intent") == "comparison"
        and isinstance(claim.get("evidence_ids"), list)
        and len(claim.get("evidence_ids", [])) == 2
    ]
    repeated_absolutes = 0
    for claim in claims:
        identifiers = claim.get("evidence_ids")
        if (
            claim.get("intent") == "absolute_observation"
            and isinstance(identifiers, list)
            and len(identifiers) == 1
        ):
            repeated_absolutes += any(
                str(identifiers[0]) in operands for operands in comparison_operands
            )
    return duplicates + repeated_absolutes


def evaluate_expectation(
    plan: Mapping[str, Any], expectation: CaseExpectation
) -> ExpectationResult:
    claims = _claims(plan)
    selected = {
        str(identifier)
        for claim in claims
        for identifier in (
            claim.get("evidence_ids")
            if isinstance(claim.get("evidence_ids"), list)
            else []
        )
    }
    diagnostics: list[str] = []
    required_hits = sum(
        identifier in selected for identifier in expectation.required_evidence_ids
    )
    if required_hits != len(expectation.required_evidence_ids):
        diagnostics.append(
            "missing_required_evidence:"
            + ",".join(
                sorted(set(expectation.required_evidence_ids) - selected)
            )
        )
    forbidden_hits = sorted(selected.intersection(expectation.forbidden_evidence_ids))
    if forbidden_hits:
        diagnostics.append("selected_forbidden_evidence:" + ",".join(forbidden_hits))

    quality_hits = sorted(
        {
            str(identifier)
            for claim in claims
            if claim.get("intent") == "data_quality_limitation"
            and isinstance(claim.get("evidence_ids"), list)
            for identifier in claim["evidence_ids"]
            if identifier in expectation.forbidden_data_quality_evidence_ids
        }
    )
    if quality_hits:
        diagnostics.append("unsupported_quality_selection:" + ",".join(quality_hits))

    disagreement_ok = True
    if expectation.required_source_disagreement_ids:
        target = set(expectation.required_source_disagreement_ids)
        disagreement_ok = any(
            claim.get("intent") == "comparison"
            and claim.get("comparison_relation")
            in {"not_equal", "less_than", "greater_than"}
            and isinstance(claim.get("evidence_ids"), list)
            and {str(item) for item in claim["evidence_ids"]} == target
            for claim in claims
        )
        if not disagreement_ok:
            diagnostics.append("missing_required_source_disagreement")

    hard_pass = (
        required_hits == len(expectation.required_evidence_ids)
        and not forbidden_hits
        and not quality_hits
        and disagreement_ok
    )
    denominator = len(expectation.required_evidence_ids) + int(
        bool(expectation.required_source_disagreement_ids)
    )
    numerator = required_hits + int(
        disagreement_ok and bool(expectation.required_source_disagreement_ids)
    )
    semantic_coverage = 1.0 if denominator == 0 else numerator / denominator
    discouraged_hits = selected.intersection(expectation.discouraged_evidence_ids)
    materiality = max(
        0.0,
        1.0
        - len(discouraged_hits)
        / max(1, len(expectation.discouraged_evidence_ids)),
    )
    redundant = _redundant_claim_count(claims)
    count_restraint = min(
        1.0, expectation.maximum_claims / max(expectation.maximum_claims, len(claims))
    )
    restraint = count_restraint * max(0.5, 1.0 - 0.1 * redundant)
    return ExpectationResult(
        hard_pass,
        semantic_coverage,
        materiality,
        restraint,
        tuple(diagnostics),
        tuple(sorted(_signature(claim) for claim in claims)),
        len(claims),
        redundant,
    )


def evaluate_validated_expectation(
    plan: Mapping[str, Any] | None,
    expectation: CaseExpectation,
    *,
    validator_accepted: bool,
) -> ExpectationResult | None:
    """Return soft quality metrics only for a canonically accepted plan."""
    if not validator_accepted or not isinstance(plan, Mapping):
        return None
    return evaluate_expectation(plan, expectation)


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 1.0
    union = left | right
    return len(left & right) / len(union) if union else 1.0


def stability(rows: Iterable[Mapping[str, Any]]) -> float:
    scored_rows = [row for row in rows if row.get("scored") is True]
    if not scored_rows:
        return 0.0
    grouped: dict[str, list[set[str]]] = {}
    for row in scored_rows:
        grouped.setdefault(str(row["case_key"]), []).append(
            set(row.get("claim_signatures", []))
        )
    scores = [
        _jaccard(repeats[left], repeats[right])
        for repeats in grouped.values()
        for left in range(len(repeats))
        for right in range(left + 1, len(repeats))
    ]
    return statistics.mean(scores) if scores else 1.0


def distribution(
    values: Iterable[float | int | None],
) -> dict[str, float | None]:
    clean = [
        float(value)
        for value in values
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    ]
    if not clean:
        return {"minimum": None, "median": None, "maximum": None, "mean": None}
    return {
        "minimum": min(clean),
        "median": statistics.median(clean),
        "maximum": max(clean),
        "mean": statistics.mean(clean),
    }
