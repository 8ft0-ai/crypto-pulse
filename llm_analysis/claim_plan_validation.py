"""Fail-closed validation for governed semantic claim plans.

The semantic plan is intentionally narrower than the historical model-authored
analysis contract. This module validates model-selected intent, ordering and
evidence compatibility. It never repairs a plan and never renders report prose.
"""

from __future__ import annotations

import re
from typing import Any, Iterator, Mapping, Sequence

from .contracts import CLAIM_PLAN_INTENTS
from .diagnostics import Diagnostic, ValidationReport, stable_report
from .schema_validation import validate_schema

_DIRECTIONAL_FIELDS = ("change", "delta", "return", "movement", "variation")
_DIRECTIONAL_STATUS = {
    "up",
    "down",
    "rising",
    "falling",
    "positive",
    "negative",
    "unchanged",
    "higher",
    "lower",
}
_LIMITATION_STATUS = {
    "degraded",
    "error",
    "failed",
    "incomplete",
    "invalid",
    "missing",
    "skipped",
    "stale",
    "unavailable",
    "warning",
    "conflicting",
    "valid-degraded",
}
_QUALITY_FIELDS = {
    "status",
    "quality_status",
    "reason",
    "warning",
    "warnings",
    "missing_symbols",
    "covered_symbols",
    "coverage",
    "conflict",
    "conflicts",
}
_SOURCE_STATUS_FIELDS = {"status", "reason", "warning", "warnings"}
_SNAPSHOT_STATUS_FIELDS = {
    "status",
    "quality_status",
    "warning",
    "warnings",
    "missing_symbols",
    "covered_symbols",
    "coverage",
}
_PROHIBITED_PLAN_KEYS = {
    "action",
    "advice",
    "alias",
    "currency",
    "date",
    "forecast",
    "heading",
    "headline",
    "label",
    "markdown",
    "position",
    "recommendation",
    "sentence",
    "signal",
    "target",
    "text",
    "timestamp",
    "unit",
    "value",
}
_UNTRUSTED_INSTRUCTION_PATTERNS = (
    re.compile(r"\b(?:ignore|override|disregard|replace|bypass)\b.{0,100}\b(?:instruction|schema|prompt|policy|contract)\b", re.I),
    re.compile(r"\b(?:recommend|buy|sell|hold|trade|invest)\b", re.I),
    re.compile(r"\b(?:remove|omit|weaken)\b.{0,60}\b(?:disclaimer|boundary|policy)\b", re.I),
)


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _subject(item: Mapping[str, Any]) -> Mapping[str, Any]:
    return _mapping(item.get("subject"))


def _source(item: Mapping[str, Any]) -> Mapping[str, Any]:
    return _mapping(item.get("source"))


def _evidence_map(bundle: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        str(item["evidence_id"]): item
        for item in _list(bundle.get("evidence"))
        if isinstance(item, Mapping) and isinstance(item.get("evidence_id"), str)
    }


def _nested_keys(value: Any) -> set[str]:
    if isinstance(value, Mapping):
        return set(value) | {key for child in value.values() for key in _nested_keys(child)}
    if isinstance(value, list):
        return {key for child in value for key in _nested_keys(child)}
    return set()


def iter_plan_claims(plan: Mapping[str, Any]) -> Iterator[tuple[str, str | None, Mapping[str, Any]]]:
    """Yield stable JSON paths, section kinds and object-shaped plan claims."""

    for section_index, section in enumerate(_list(plan.get("sections"))):
        if not isinstance(section, Mapping):
            continue
        section_kind = section.get("section_kind")
        section_name = section_kind if isinstance(section_kind, str) else None
        for claim_index, claim in enumerate(_list(section.get("claims"))):
            if isinstance(claim, Mapping):
                yield (
                    f"$.claim_plan.sections[{section_index}].claims[{claim_index}]",
                    section_name,
                    claim,
                )


def _relation_holds(left: float, relation: str, right: float) -> bool:
    tolerance = max(abs(left), abs(right), 1.0) * 0.001
    return {
        "greater_than": left > right,
        "less_than": left < right,
        "approximately_equal": abs(left - right) <= tolerance,
        "not_equal": left != right,
        "opposite_direction": (left < 0 < right) or (right < 0 < left),
    }.get(relation, False)


def is_source_disagreement_pair(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    """Return whether two records are the same measure from different sources."""

    if left.get("evidence_type") != "number" or right.get("evidence_type") != "number":
        return False
    same_measure = (
        _subject(left).get("id") == _subject(right).get("id")
        and left.get("field") == right.get("field")
        and left.get("unit") == right.get("unit")
    )
    left_source = _source(left).get("name")
    right_source = _source(right).get("name")
    different_source = (
        isinstance(left_source, str)
        and isinstance(right_source, str)
        and bool(left_source)
        and bool(right_source)
        and left_source != right_source
    )
    return same_measure and different_source


def claim_source_disagreement_eligible(
    claim: Mapping[str, Any], evidence_by_id: Mapping[str, Mapping[str, Any]]
) -> bool:
    """Return whether a comparison claim represents bounded source disagreement."""

    if claim.get("intent") != "comparison" or claim.get("comparison_relation") != "not_equal":
        return False
    identifiers = [item for item in _list(claim.get("evidence_ids")) if isinstance(item, str)]
    if len(identifiers) != 2 or any(item not in evidence_by_id for item in identifiers):
        return False
    left, right = (evidence_by_id[item] for item in identifiers)
    return is_source_disagreement_pair(left, right)


def _referential_diagnostics(
    bundle: Mapping[str, Any], plan: Mapping[str, Any]
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    rows = [item for item in _list(bundle.get("evidence")) if isinstance(item, Mapping)]
    identifiers = [item.get("evidence_id") for item in rows]
    if len(identifiers) != len(set(identifiers)):
        diagnostics.append(
            Diagnostic(
                "referential",
                "duplicate_bundle_evidence_id",
                "$.bundle.evidence",
                "evidence bundle identifiers must be unique",
            )
        )
    if plan.get("evidence_bundle_id") != bundle.get("bundle_id"):
        diagnostics.append(
            Diagnostic(
                "referential",
                "bundle_id_mismatch",
                "$.claim_plan.evidence_bundle_id",
                "claim plan does not reference the selected evidence bundle",
            )
        )
    evidence_by_id = _evidence_map(bundle)
    for path, _, claim in iter_plan_claims(plan):
        seen: set[str] = set()
        for index, identifier in enumerate(_list(claim.get("evidence_ids"))):
            if not isinstance(identifier, str):
                continue
            if identifier in seen:
                diagnostics.append(
                    Diagnostic(
                        "referential",
                        "duplicate_claim_evidence_id",
                        f"{path}.evidence_ids[{index}]",
                        "claim evidence identifiers must be unique",
                    )
                )
            seen.add(identifier)
            if identifier not in evidence_by_id:
                diagnostics.append(
                    Diagnostic(
                        "referential",
                        "unknown_evidence_id",
                        f"{path}.evidence_ids[{index}]",
                        f"unknown evidence ID: {identifier}",
                    )
                )
    return diagnostics


def _ordering_diagnostics(plan: Mapping[str, Any]) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    order = [item for item in _list(plan.get("analysis_order")) if isinstance(item, str)]
    if len(order) != len(set(order)):
        diagnostics.append(
            Diagnostic(
                "semantic",
                "duplicate_analysis_order",
                "$.claim_plan.analysis_order",
                "analysis order cannot contain duplicate section kinds",
            )
        )

    section_kinds = [
        section.get("section_kind")
        for section in _list(plan.get("sections"))
        if isinstance(section, Mapping) and isinstance(section.get("section_kind"), str)
    ]
    if len(section_kinds) != len(set(section_kinds)):
        diagnostics.append(
            Diagnostic(
                "semantic",
                "duplicate_section_kind",
                "$.claim_plan.sections",
                "section kinds must be unique",
            )
        )
    if order != section_kinds:
        diagnostics.append(
            Diagnostic(
                "semantic",
                "analysis_order_mismatch",
                "$.claim_plan.analysis_order",
                "analysis order must exactly match the declared section sequence",
            )
        )

    seen_claim_ids: set[str] = set()
    for path, _, claim in iter_plan_claims(plan):
        claim_id = claim.get("claim_id")
        if isinstance(claim_id, str):
            if claim_id in seen_claim_ids:
                diagnostics.append(
                    Diagnostic(
                        "semantic",
                        "duplicate_claim_id",
                        f"{path}.claim_id",
                        "claim identifiers must be unique across the plan",
                    )
                )
            seen_claim_ids.add(claim_id)
    return diagnostics


def _is_directional_record(item: Mapping[str, Any]) -> bool:
    if item.get("evidence_type") == "number":
        field = str(item.get("field", "")).casefold()
        return any(token in field for token in _DIRECTIONAL_FIELDS)
    return str(item.get("value", "")).casefold() in _DIRECTIONAL_STATUS


def _has_data_quality_support(evidence: Sequence[Mapping[str, Any]]) -> bool:
    for item in evidence:
        field = str(item.get("field", "")).casefold()
        value = item.get("value")
        folded = str(value).casefold()
        if field not in _QUALITY_FIELDS:
            continue
        if field in {"status", "quality_status", "conflict", "conflicts"} and folded in _LIMITATION_STATUS:
            return True
        if field in {"warning", "warnings", "missing_symbols"} and bool(value):
            return True
        if field == "coverage" and isinstance(value, (int, float)) and not isinstance(value, bool) and value < 1:
            return True
    return False


def _intent_diagnostics(
    bundle: Mapping[str, Any], plan: Mapping[str, Any]
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    evidence_by_id = _evidence_map(bundle)
    for path, _, claim in iter_plan_claims(plan):
        intent = claim.get("intent")
        relation = claim.get("comparison_relation")
        identifiers = [item for item in _list(claim.get("evidence_ids")) if isinstance(item, str)]
        evidence = [evidence_by_id[item] for item in identifiers if item in evidence_by_id]

        if intent not in CLAIM_PLAN_INTENTS:
            diagnostics.append(
                Diagnostic(
                    "semantic",
                    "unsupported_intent",
                    f"{path}.intent",
                    f"unsupported claim-plan intent: {intent!r}",
                )
            )
            continue

        if intent == "comparison":
            if relation == "none":
                diagnostics.append(
                    Diagnostic(
                        "semantic",
                        "comparison_relation_required",
                        f"{path}.comparison_relation",
                        "comparison intent requires a non-none relation",
                    )
                )
            if len(identifiers) != 2:
                diagnostics.append(
                    Diagnostic(
                        "semantic",
                        "comparison_operand_count",
                        f"{path}.evidence_ids",
                        "comparison intent requires exactly two evidence identifiers",
                    )
                )
            if len(evidence) == 2:
                left, right = evidence
                if left.get("evidence_type") != "number" or right.get("evidence_type") != "number":
                    diagnostics.append(
                        Diagnostic(
                            "semantic",
                            "comparison_operand_type",
                            path,
                            "comparison operands must both be numeric evidence",
                        )
                    )
                else:
                    if left.get("field") != right.get("field"):
                        diagnostics.append(
                            Diagnostic(
                                "semantic",
                                "comparison_field_mismatch",
                                path,
                                "comparison operands must represent the same field",
                            )
                        )
                    if left.get("unit") != right.get("unit"):
                        diagnostics.append(
                            Diagnostic(
                                "semantic",
                                "comparison_unit_mismatch",
                                path,
                                "comparison operands must use the same unit",
                            )
                        )
                    if (
                        relation != "none"
                        and left.get("field") == right.get("field")
                        and left.get("unit") == right.get("unit")
                        and not _relation_holds(float(left["value"]), str(relation), float(right["value"]))
                    ):
                        diagnostics.append(
                            Diagnostic(
                                "semantic",
                                "comparison_relation_mismatch",
                                f"{path}.comparison_relation",
                                "declared relation is not supported by the evidence values",
                            )
                        )
        elif relation != "none":
            diagnostics.append(
                Diagnostic(
                    "semantic",
                    "comparison_relation_forbidden",
                    f"{path}.comparison_relation",
                    "non-comparison intents must use comparison_relation 'none'",
                )
            )

        if not evidence:
            continue
        if intent == "absolute_observation" and any(
            item.get("evidence_type") not in {"number", "boolean", "set", "timestamp", "status"}
            for item in evidence
        ):
            diagnostics.append(
                Diagnostic(
                    "semantic",
                    "absolute_observation_incompatible",
                    path,
                    "absolute observations require renderable non-free-form evidence",
                )
            )
        elif intent == "directional_observation" and not all(
            _is_directional_record(item) for item in evidence
        ):
            diagnostics.append(
                Diagnostic(
                    "semantic",
                    "directional_support_missing",
                    path,
                    "directional observations require change-like numeric or directional-status evidence",
                )
            )
        elif intent == "source_status":
            supported = (
                all(_subject(item).get("type") == "source" for item in evidence)
                and all(str(item.get("field", "")).casefold() in _SOURCE_STATUS_FIELDS for item in evidence)
                and any(str(item.get("field", "")).casefold() == "status" for item in evidence)
            )
            if not supported:
                diagnostics.append(
                    Diagnostic(
                        "semantic",
                        "source_status_support_missing",
                        path,
                        "source status requires source-subject status evidence",
                    )
                )
        elif intent == "snapshot_status":
            supported = (
                all(_subject(item).get("type") == "snapshot" for item in evidence)
                and all(str(item.get("field", "")).casefold() in _SNAPSHOT_STATUS_FIELDS for item in evidence)
                and any(str(item.get("field", "")).casefold() in {"status", "quality_status"} for item in evidence)
            )
            if not supported:
                diagnostics.append(
                    Diagnostic(
                        "semantic",
                        "snapshot_status_support_missing",
                        path,
                        "snapshot status requires snapshot-subject quality or status evidence",
                    )
                )
        elif intent == "data_quality_limitation" and not _has_data_quality_support(evidence):
            diagnostics.append(
                Diagnostic(
                    "semantic",
                    "data_quality_support_missing",
                    path,
                    "data-quality limitations require explicit missing, failed, stale, degraded, skipped, warning, incomplete or conflicting evidence",
                )
            )
    return diagnostics


def _policy_diagnostics(
    bundle: Mapping[str, Any], plan: Mapping[str, Any]
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    prohibited = _PROHIBITED_PLAN_KEYS & _nested_keys(plan)
    for key in sorted(prohibited):
        diagnostics.append(
            Diagnostic(
                "policy",
                "prohibited_plan_field",
                "$.claim_plan",
                f"model-owned plan field is prohibited: {key}",
            )
        )

    evidence_by_id = _evidence_map(bundle)
    for path, _, claim in iter_plan_claims(plan):
        for identifier in _list(claim.get("evidence_ids")):
            if not isinstance(identifier, str) or identifier not in evidence_by_id:
                continue
            item = evidence_by_id[identifier]
            value = item.get("value")
            if item.get("evidence_type") != "string" or not isinstance(value, str):
                continue
            if any(pattern.search(value) for pattern in _UNTRUSTED_INSTRUCTION_PATTERNS):
                diagnostics.append(
                    Diagnostic(
                        "policy",
                        "unsafe_untrusted_evidence_reference",
                        f"{path}.evidence_ids",
                        f"claim selects instruction-like untrusted evidence: {identifier}",
                    )
                )
    return diagnostics


def validate_claim_plan(
    bundle: dict[str, Any],
    plan: dict[str, Any],
    *,
    evidence_schema: dict[str, Any],
    claim_plan_schema: dict[str, Any],
) -> ValidationReport:
    """Validate without mutating, repairing or rendering the supplied plan."""

    diagnostics: list[Diagnostic] = []
    diagnostics.extend(validate_schema(bundle, evidence_schema, path="$.bundle"))
    diagnostics.extend(validate_schema(plan, claim_plan_schema, path="$.claim_plan"))
    if isinstance(bundle, dict) and isinstance(plan, dict):
        diagnostics.extend(_referential_diagnostics(bundle, plan))
        diagnostics.extend(_ordering_diagnostics(plan))
        diagnostics.extend(_intent_diagnostics(bundle, plan))
        diagnostics.extend(_policy_diagnostics(bundle, plan))
    return stable_report(diagnostics)
