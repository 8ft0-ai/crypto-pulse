"""Offline, layered validation for governed structured analysis."""

from __future__ import annotations

import re
from typing import Any, Iterable, Iterator

from .contracts import CLAIM_TYPES
from .diagnostics import Diagnostic, ValidationReport, stable_report
from .schema_validation import validate_schema

CLAIM_COLLECTIONS = ("market_summary", "key_observations", "risks_and_limitations", "data_quality_notes")
PROHIBITED_FIELDS = {"recommendation", "position", "target", "entry", "exit", "trade", "signal", "watchlist", "allocation"}
QUALITY_FIELDS = {"status", "reason", "warning", "warnings", "quality_status", "missing_symbols", "covered_symbols"}
DIRECTIONAL_STATUS = {"up", "down", "rising", "falling", "positive", "negative", "unchanged", "higher", "lower"}

NUMBER_RE = re.compile(r"(?<![A-Za-z0-9])[-+]?\d[\d,]*(?:\.\d+)?(?![A-Za-z0-9])")
TIMESTAMP_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})\b")
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")
CAPITALISED_RE = re.compile(r"\b(?:[A-Z][a-z]+(?:[A-Z][a-z]+)*|[A-Z]{2,})\b")
ENTITY_WORD_ALLOWLIST = {"a", "an", "the", "ai", "us", "usd", "http", "https", "utc", "aest", "aedt", "github", "json", "markdown"}

POLICY_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("causal_language", re.compile(r"\b(?:because|caused by|due to|drove|driven by|resulted from|as a result of)\b", re.I)),
    ("forecast_language", re.compile(r"\b(?:will|forecast|predict(?:s|ed|ion)?|expected to|likely to|set to|poised to|may (?:rise|fall|gain|decline)|outlook)\b", re.I)),
    ("advice_language", re.compile(r"\b(?:should\s+(?:buy|sell|hold|trade|invest)|recommend(?:s|ed|ation)?|consider\s+(?:buying|selling|trading|investing)|investors? should)\b", re.I)),
    ("target_language", re.compile(r"\b(?:price target|target price|support level|resistance level|entry point|exit point|target of)\b", re.I)),
    ("signal_language", re.compile(r"\b(?:trading signal|buy signal|sell signal|bullish signal|bearish signal|watchlist)\b", re.I)),
    ("position_guidance", re.compile(r"\b(?:open|close|add to|reduce|increase|decrease|hold)\s+(?:a |the |your )?(?:position|allocation|exposure|portfolio)\b", re.I)),
    ("prompt_override_language", re.compile(r"\b(?:ignore|override|disregard|replace|bypass)\b.{0,80}\b(?:schema|instruction|prompt|policy|contract)\b|\breturn\s+(?:markdown|non-json|plain text)\b", re.I)),
    ("disclaimer_weakening", re.compile(r"\b(?:this is financial advice|this is investment research|omit (?:the )?disclaimer|remove (?:the )?disclaimer|not merely a demonstration)\b", re.I)),
)


def iter_claims(analysis: dict[str, Any]) -> Iterator[tuple[str, dict[str, Any]]]:
    headline = analysis.get("headline")
    if isinstance(headline, dict):
        yield "$.analysis.headline", headline
    for name in CLAIM_COLLECTIONS:
        items = analysis.get(name, [])
        if isinstance(items, list):
            for index, item in enumerate(items):
                if isinstance(item, dict):
                    yield f"$.analysis.{name}[{index}]", item
    note = analysis.get("source_evidence_note")
    if isinstance(note, dict):
        yield "$.analysis.source_evidence_note", note


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _claim_evidence_ids(claim: dict[str, Any]) -> list[str]:
    return [item for item in _list(claim.get("evidence_ids")) if isinstance(item, str)]


def _subject(item: dict[str, Any]) -> dict[str, Any]:
    value = item.get("subject")
    return value if isinstance(value, dict) else {}


def _source(item: dict[str, Any]) -> dict[str, Any]:
    value = item.get("source")
    return value if isinstance(value, dict) else {}


def _nested_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {key for child in value.values() for key in _nested_keys(child)}
    if isinstance(value, list):
        return {key for child in value for key in _nested_keys(child)}
    return set()


def _evidence_map(bundle: dict[str, Any]) -> dict[str, dict[str, Any]]:
    evidence = _list(bundle.get("evidence"))
    return {item.get("evidence_id"): item for item in evidence if isinstance(item, dict) and isinstance(item.get("evidence_id"), str)}


def _normalise_number(value: str | int | float) -> str:
    text = str(value).replace(",", "")
    if text.startswith("+"):
        text = text[1:]
    try:
        number = float(text)
    except ValueError:
        return text
    if number == int(number):
        return str(int(number))
    return format(number, ".15g")


def _number_tokens(value: Any) -> set[str]:
    if isinstance(value, bool):
        return set()
    if isinstance(value, (int, float)):
        return {_normalise_number(value)}
    if isinstance(value, str):
        return {_normalise_number(match.group(0)) for match in NUMBER_RE.finditer(value)}
    return set()


def _referential_diagnostics(bundle: dict[str, Any], analysis: dict[str, Any]) -> list[Diagnostic]:
    errors: list[Diagnostic] = []
    evidence_by_id = _evidence_map(bundle)
    ids = [item.get("evidence_id") for item in _list(bundle.get("evidence")) if isinstance(item, dict)]
    if len(ids) != len(set(ids)):
        errors.append(Diagnostic("referential", "duplicate_evidence_id", "$.bundle.evidence", "evidence IDs must be unique"))
    if analysis.get("evidence_bundle_id") != bundle.get("bundle_id"):
        errors.append(Diagnostic("referential", "bundle_id_mismatch", "$.analysis.evidence_bundle_id", "analysis does not reference the selected evidence bundle"))
    for path, claim in iter_claims(analysis):
        for index, evidence_id in enumerate(_claim_evidence_ids(claim)):
            if evidence_id not in evidence_by_id:
                errors.append(Diagnostic("referential", "unknown_evidence_id", f"{path}.evidence_ids[{index}]", f"unknown evidence ID: {evidence_id}"))
        comparison = claim.get("comparison")
        if isinstance(comparison, dict):
            for key in ("left_evidence_id", "right_evidence_id"):
                evidence_id = comparison.get(key)
                if evidence_id not in evidence_by_id:
                    errors.append(Diagnostic("referential", "unknown_evidence_id", f"{path}.comparison.{key}", f"unknown evidence ID: {evidence_id}"))
        for index, quoted in enumerate(_list(claim.get("quoted_values"))):
            if isinstance(quoted, dict) and quoted.get("evidence_id") not in evidence_by_id:
                errors.append(Diagnostic("referential", "unknown_evidence_id", f"{path}.quoted_values[{index}].evidence_id", f"unknown evidence ID: {quoted.get('evidence_id')}"))
    return errors


def _relation_holds(left: float, relation: str, right: float) -> bool:
    tolerance = max(abs(left), abs(right), 1.0) * 0.001
    return {
        "greater_than": left > right,
        "less_than": left < right,
        "approximately_equal": abs(left - right) <= tolerance,
        "not_equal": left != right,
        "opposite_direction": (left < 0 < right) or (right < 0 < left),
    }.get(relation, False)


def _value_diagnostics(bundle: dict[str, Any], analysis: dict[str, Any]) -> list[Diagnostic]:
    errors: list[Diagnostic] = []
    evidence_by_id = _evidence_map(bundle)
    label_to_ids: dict[str, set[str]] = {}
    for evidence_id, item in evidence_by_id.items():
        subject = _subject(item)
        labels = {subject.get("name"), subject.get("symbol"), _source(item).get("name")}
        for label in labels:
            if isinstance(label, str) and len(label) >= 2:
                label_to_ids.setdefault(label.casefold(), set()).add(evidence_id)

    for path, claim in iter_claims(analysis):
        referenced_ids = [item for item in _claim_evidence_ids(claim) if item in evidence_by_id]
        referenced = [evidence_by_id[item] for item in referenced_ids]
        text = str(claim.get("text", ""))

        for index, quoted in enumerate(_list(claim.get("quoted_values"))):
            if not isinstance(quoted, dict):
                continue
            evidence = evidence_by_id.get(quoted.get("evidence_id"))
            if not evidence or evidence.get("evidence_type") != "number":
                continue
            if quoted.get("value") != evidence.get("value"):
                errors.append(Diagnostic("value", "quoted_value_mismatch", f"{path}.quoted_values[{index}].value", "quoted numeric value does not match evidence"))
            expected_unit = evidence.get("unit")
            if quoted.get("unit") != expected_unit:
                errors.append(Diagnostic("value", "unit_mismatch", f"{path}.quoted_values[{index}].unit", "quoted unit does not match evidence"))

        comparison = claim.get("comparison")
        if isinstance(comparison, dict):
            left_id = comparison.get("left_evidence_id")
            right_id = comparison.get("right_evidence_id")
            declared_ids = _claim_evidence_ids(claim)
            if left_id not in declared_ids or right_id not in declared_ids:
                errors.append(Diagnostic("value", "comparison_reference_mismatch", f"{path}.comparison", "comparison evidence must also appear in evidence_ids"))
            left = evidence_by_id.get(left_id)
            right = evidence_by_id.get(right_id)
            if left and right and left.get("evidence_type") == right.get("evidence_type") == "number":
                if left.get("unit") != right.get("unit"):
                    errors.append(Diagnostic("value", "comparison_unit_mismatch", f"{path}.comparison", "comparison units are incompatible"))
                elif not _relation_holds(float(left["value"]), str(comparison.get("relation")), float(right["value"])):
                    errors.append(Diagnostic("value", "comparison_mismatch", f"{path}.comparison.relation", "declared comparison is not supported by the evidence values"))

        allowed_numbers: set[str] = set()
        allowed_timestamps: set[str] = set()
        for item in referenced:
            allowed_numbers.update(_number_tokens(item.get("value")))
            allowed_numbers.update(_number_tokens(item.get("field")))
            if isinstance(item.get("field"), str):
                allowed_numbers.update(_normalise_number(token) for token in re.findall(r"\d+(?:\.\d+)?", item["field"]))
            allowed_numbers.update(_number_tokens(item.get("observed_at")))
            if isinstance(item.get("observed_at"), str):
                allowed_timestamps.add(item["observed_at"])
            if item.get("evidence_type") == "timestamp" and isinstance(item.get("value"), str):
                allowed_timestamps.add(item["value"])
        timestamp_spans = [match.span() for match in TIMESTAMP_RE.finditer(text)]
        for match in NUMBER_RE.finditer(text):
            if any(start <= match.start() and match.end() <= end for start, end in timestamp_spans):
                continue
            token = _normalise_number(match.group(0))
            if token not in allowed_numbers:
                errors.append(Diagnostic("value", "untraceable_number", path + ".text", f"numeric token {match.group(0)!r} is not traceable to referenced evidence"))
        for timestamp in TIMESTAMP_RE.findall(text):
            if timestamp not in allowed_timestamps:
                errors.append(Diagnostic("value", "timestamp_mismatch", path + ".text", f"timestamp {timestamp!r} is not traceable to referenced evidence"))

        folded = text.casefold()
        for label, supporting_ids in label_to_ids.items():
            if re.search(rf"(?<![\w]){re.escape(label)}(?![\w])", folded) and not (supporting_ids & set(referenced_ids)):
                errors.append(Diagnostic("value", "entity_mismatch", path + ".text", f"named entity {label!r} is not supported by this claim's evidence references"))

        known_entity_words = {
            word.casefold()
            for label in label_to_ids
            for word in re.findall(r"[A-Za-z0-9]+", label)
        }
        for match in CAPITALISED_RE.finditer(text):
            token = match.group(0)
            if token.casefold() not in known_entity_words | ENTITY_WORD_ALLOWLIST:
                errors.append(Diagnostic("value", "untraceable_entity", path + ".text", f"named token {token!r} is absent from the evidence bundle"))

        units = {item.get("unit") for item in referenced if item.get("unit")}
        if ("%" in text or re.search(r"\bpercent(?:age)?\b", text, re.I)) and "percent" not in units:
            errors.append(Diagnostic("value", "unit_mismatch", path + ".text", "percentage wording is not supported by percent evidence"))
        if ("US$" in text or re.search(r"\bUSD\b", text, re.I)) and "usd" not in units:
            errors.append(Diagnostic("value", "unit_mismatch", path + ".text", "USD wording is not supported by USD evidence"))
    return errors


def _semantic_diagnostics(bundle: dict[str, Any], analysis: dict[str, Any]) -> list[Diagnostic]:
    errors: list[Diagnostic] = []
    evidence_by_id = _evidence_map(bundle)
    for path, claim in iter_claims(analysis):
        claim_type = claim.get("claim_type")
        evidence = [evidence_by_id[item] for item in _claim_evidence_ids(claim) if item in evidence_by_id]
        if claim_type not in CLAIM_TYPES:
            errors.append(Diagnostic("semantic", "unsupported_claim_type", path + ".claim_type", f"unsupported claim type: {claim_type!r}"))
            continue
        if claim_type == "directional_observation":
            supported = any(item.get("evidence_type") == "number" for item in evidence) or any(str(item.get("value", "")).casefold() in DIRECTIONAL_STATUS for item in evidence)
            if not supported:
                errors.append(Diagnostic("semantic", "invalid_directional_support", path, "directional observations require numeric or directional-status evidence"))
        if claim_type in {"comparison", "source_disagreement"}:
            comparison = claim.get("comparison")
            if not isinstance(comparison, dict):
                errors.append(Diagnostic("semantic", "missing_comparison", path, "comparison claim requires a structured comparison"))
            else:
                left = evidence_by_id.get(comparison.get("left_evidence_id"))
                right = evidence_by_id.get(comparison.get("right_evidence_id"))
                if left and right and (left.get("evidence_type") != "number" or right.get("evidence_type") != "number"):
                    errors.append(Diagnostic("semantic", "incompatible_comparison", path, "comparison claims require numeric evidence"))
                if claim_type == "source_disagreement" and left and right:
                    left_subject = _subject(left)
                    right_subject = _subject(right)
                    same_measure = left_subject.get("id") == right_subject.get("id") and left.get("field") == right.get("field") and left.get("unit") == right.get("unit")
                    different_source = _source(left).get("name") != _source(right).get("name")
                    if not same_measure or not different_source:
                        errors.append(Diagnostic("semantic", "invalid_source_disagreement", path, "source disagreement must compare the same measurement from different sources"))
        if claim_type == "data_quality_limitation":
            if not evidence or any(_subject(item).get("type") not in {"source", "snapshot"} and item.get("field") not in QUALITY_FIELDS for item in evidence):
                errors.append(Diagnostic("semantic", "invalid_data_quality_support", path, "data-quality claims require source, snapshot, status, reason, warning, or coverage evidence"))
        if claim_type == "qualitative_interpretation":
            if len(evidence) < 2:
                errors.append(Diagnostic("semantic", "qualitative_support", path, "qualitative interpretation requires at least two evidence records"))
            if _list(claim.get("quoted_values")) or claim.get("comparison"):
                errors.append(Diagnostic("semantic", "qualitative_structure", path, "qualitative interpretation cannot introduce quoted values or a comparison object"))
        if claim_type not in {"comparison", "source_disagreement"} and claim.get("comparison") is not None:
            errors.append(Diagnostic("semantic", "unexpected_comparison", path, "this claim type cannot carry a comparison object"))
    return errors


def _is_data_quality_cause(claim: dict[str, Any], evidence_by_id: dict[str, dict[str, Any]]) -> bool:
    if claim.get("claim_type") != "data_quality_limitation":
        return False
    evidence = [evidence_by_id[item] for item in _claim_evidence_ids(claim) if item in evidence_by_id]
    return bool(evidence) and all(_subject(item).get("type") in {"source", "snapshot"} or item.get("field") in QUALITY_FIELDS for item in evidence)


def _policy_diagnostics(bundle: dict[str, Any], analysis: dict[str, Any]) -> list[Diagnostic]:
    errors: list[Diagnostic] = []
    evidence_by_id = _evidence_map(bundle)
    for path, claim in iter_claims(analysis):
        prohibited = PROHIBITED_FIELDS & _nested_keys(claim)
        for key in sorted(prohibited):
            errors.append(Diagnostic("policy", "prohibited_field", path, f"prohibited field present: {key}"))
        text = str(claim.get("text", ""))
        sentences = SENTENCE_RE.split(text)
        for sentence in sentences:
            for code, pattern in POLICY_PATTERNS:
                if code == "causal_language" and _is_data_quality_cause(claim, evidence_by_id):
                    continue
                if pattern.search(sentence):
                    errors.append(Diagnostic("policy", code, path + ".text", f"unsupported policy language detected: {code}"))
    return errors


def validate_analysis(bundle: dict[str, Any], analysis: dict[str, Any], *, evidence_schema: dict[str, Any], analysis_schema: dict[str, Any]) -> ValidationReport:
    diagnostics: list[Diagnostic] = []
    diagnostics.extend(validate_schema(bundle, evidence_schema, path="$.bundle"))
    diagnostics.extend(validate_schema(analysis, analysis_schema, path="$.analysis"))
    if isinstance(bundle, dict) and isinstance(analysis, dict):
        diagnostics.extend(_referential_diagnostics(bundle, analysis))
        diagnostics.extend(_value_diagnostics(bundle, analysis))
        diagnostics.extend(_semantic_diagnostics(bundle, analysis))
        diagnostics.extend(_policy_diagnostics(bundle, analysis))
    return stable_report(diagnostics)
