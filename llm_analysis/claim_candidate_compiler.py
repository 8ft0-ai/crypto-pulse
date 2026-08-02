"""Deterministically compile repository-owned claim candidates from canonical evidence.

This module implements Phase 6 Slice 2. It consumes one validated
``crypto-market-evidence-bundle/v1`` object and emits a complete, stable set of
``crypto-market-claim-candidate/v1`` records. It does not rank, select,
reconstruct a production claim plan, call a provider or render a report.
"""

from __future__ import annotations

import math
import re
from collections import defaultdict
from collections.abc import Mapping
from itertools import combinations
from typing import Any

from .claim_candidate_contract import (
    derive_candidate_id,
    index_candidates_by_id,
    order_candidates,
)
from .contracts import (
    CLAIM_CANDIDATE_SCHEMA_VERSION,
    EVIDENCE_SCHEMA_VERSION,
    content_sha256,
)
from .schema_validation import validate_schema

_MARKET_SUBJECT_TYPES = frozenset({"asset", "market", "exchange_pair", "defi_metric"})
_ABSOLUTE_TYPES = frozenset({"number", "timestamp", "boolean", "set", "status"})
_RENDERABLE_NUMERIC_UNITS = frozenset({"usd", "percent", "rank"})
_DIRECTIONAL_FIELDS = frozenset(
    {"change_1h_pct", "change_24h_pct", "change_7d_pct", "change_1d_pct"}
)
_DIRECTIONAL_STATUS = frozenset(
    {"up", "down", "rising", "falling", "positive", "negative", "unchanged", "higher", "lower"}
)
_LIMITATION_STATUS = frozenset(
    {
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
)
_SOURCE_DETAIL_FIELDS = ("reason", "warning")
_RENDERABLE_METRICS = frozenset(
    {
        "price_usd",
        "price",
        "bid",
        "ask",
        "change_1h_pct",
        "change_24h_pct",
        "change_7d_pct",
        "change_1d_pct",
        "market_cap_usd",
        "volume_24h_usd",
        "market_cap_rank",
        "total_tvl_usd",
        "circulating_usd",
        "last_updated",
        "source_time",
        "fetched_at_utc",
        "generated_at_utc",
        "status",
        "quality_status",
        "covered_symbols",
        "missing_symbols",
        "coverage",
        "warning",
        "warnings",
        "reason",
        "message",
    }
)
_RENDERABLE_SOURCE_ALIASES = frozenset(
    {
        "binance",
        "coingecko",
        "coinbase_exchange",
        "defillama",
        "snapshot-validator",
        "source-snapshot",
    }
)
_UNTRUSTED_INSTRUCTION_PATTERNS = (
    re.compile(
        r"\b(?:ignore|override|disregard|replace|bypass)\b.{0,100}"
        r"\b(?:instruction|schema|prompt|policy|contract)\b",
        re.I,
    ),
    re.compile(r"\b(?:recommend|buy|sell|hold|trade|invest)\b", re.I),
    re.compile(
        r"\b(?:remove|omit|weaken)\b.{0,60}\b(?:disclaimer|boundary|policy)\b",
        re.I,
    ),
)
_BUNDLE_ID_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class ClaimCandidateCompilationError(ValueError):
    """The evidence bundle cannot be compiled without ambiguity or repair."""

    def __init__(self, code: str, path: str, message: str):
        super().__init__(message)
        self.code = code
        self.path = path
        self.message = message


def _fail(code: str, path: str, message: str) -> None:
    raise ClaimCandidateCompilationError(code, path, message)


def _subject(record: Mapping[str, Any]) -> Mapping[str, Any]:
    value = record.get("subject")
    return value if isinstance(value, Mapping) else {}


def _source(record: Mapping[str, Any]) -> Mapping[str, Any]:
    value = record.get("source")
    return value if isinstance(value, Mapping) else {}


def _canonical_subject(record: Mapping[str, Any]) -> dict[str, str]:
    subject = _subject(record)
    return {"type": str(subject.get("type", "")), "id": str(subject.get("id", ""))}


def _has_renderable_alias(record: Mapping[str, Any]) -> bool:
    subject = _subject(record)
    if subject.get("type") == "snapshot":
        return True
    return any(isinstance(subject.get(key), str) and subject.get(key).strip() for key in ("name", "symbol"))


def _safe_detail(record: Mapping[str, Any]) -> bool:
    if record.get("evidence_type") != "string":
        return False
    value = record.get("value")
    return isinstance(value, str) and not any(pattern.search(value) for pattern in _UNTRUSTED_INSTRUCTION_PATTERNS)


def _finite_number(record: Mapping[str, Any]) -> float | None:
    value = record.get("value")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _slug(*parts: Any) -> str:
    text = "_".join(str(part).casefold() for part in parts if str(part))
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    if not text:
        return "candidate"
    if not text[0].isalpha():
        text = "candidate_" + text
    return text


def _source_names(records: list[Mapping[str, Any]]) -> tuple[str, ...]:
    return tuple(
        sorted(
            {
                str(_source(record).get("name"))
                for record in records
                if isinstance(_source(record).get("name"), str)
                and str(_source(record).get("name")).strip()
            }
        )
    )


def _materiality_for_direction(record: Mapping[str, Any]) -> str:
    number = _finite_number(record)
    if number is None or record.get("unit") != "percent":
        return "not_applicable"
    magnitude = abs(number)
    if magnitude >= 3:
        return "high"
    if magnitude >= 1:
        return "medium"
    return "low"


def _comparison_materiality(left: Mapping[str, Any], right: Mapping[str, Any]) -> str:
    left_value = _finite_number(left)
    right_value = _finite_number(right)
    if left_value is None or right_value is None:
        return "not_applicable"
    if _canonical_subject(left) != _canonical_subject(right):
        return "not_applicable"
    scale = max(abs(left_value), abs(right_value), 1.0)
    relative = abs(left_value - right_value) / scale
    if relative > 0.01:
        return "high"
    if relative > 0.001:
        return "medium"
    return "low"


def _features(
    records: list[Mapping[str, Any]],
    *,
    materiality: str,
    conflict_status: str,
    quality_significance: str,
    section_eligibility: list[str],
    redundancy_group: str,
) -> dict[str, Any]:
    source_names = _source_names(records)
    return {
        "materiality_bucket": materiality,
        "cross_source": len(source_names) > 1,
        "conflict_status": conflict_status,
        "recency_bucket": "unknown",
        "quality_significance": quality_significance,
        "section_eligibility": section_eligibility,
        "redundancy_group": redundancy_group,
        "corroboration_count": len(source_names),
    }


def _candidate(
    bundle_id: str,
    *,
    intent: str,
    records: list[Mapping[str, Any]],
    relation: str,
    section: str,
    subject: dict[str, str],
    metric: str,
    features: dict[str, Any],
) -> dict[str, Any]:
    candidate: dict[str, Any] = {
        "candidate_version": CLAIM_CANDIDATE_SCHEMA_VERSION,
        "candidate_id": "",
        "evidence_bundle_id": bundle_id,
        "intent": intent,
        "evidence_ids": sorted(str(record["evidence_id"]) for record in records),
        "comparison_relation": relation,
        "section": section,
        "subject": subject,
        "metric": metric,
        "confidence": "high",
        "features": features,
    }
    candidate["candidate_id"] = derive_candidate_id(candidate)
    return candidate


def _eligible_observation(record: Mapping[str, Any]) -> bool:
    evidence_type = record.get("evidence_type")
    return (
        _subject(record).get("type") in _MARKET_SUBJECT_TYPES
        and evidence_type in _ABSOLUTE_TYPES
        and record.get("field") in _RENDERABLE_METRICS
        and _has_renderable_alias(record)
        and (
            evidence_type != "number"
            or (
                record.get("unit") in _RENDERABLE_NUMERIC_UNITS
                and _finite_number(record) is not None
            )
        )
    )


def _eligible_direction(record: Mapping[str, Any]) -> bool:
    if not _eligible_observation(record):
        return False
    if record.get("evidence_type") == "number":
        return record.get("field") in _DIRECTIONAL_FIELDS
    if record.get("evidence_type") == "status":
        return str(record.get("value", "")).casefold() in _DIRECTIONAL_STATUS
    return False


def _approximately_equal(left: float, right: float) -> bool:
    tolerance = max(abs(left), abs(right), 1.0) * 0.001
    return abs(left - right) <= tolerance


def _comparison_relation(
    left: Mapping[str, Any], right: Mapping[str, Any]
) -> tuple[str, str]:
    left_value = _finite_number(left)
    right_value = _finite_number(right)
    if left_value is None or right_value is None:
        _fail("non_finite_comparison", "$.bundle.evidence", "comparison operands must be finite numbers")

    same_subject = _canonical_subject(left) == _canonical_subject(right)
    left_source = str(_source(left).get("name", ""))
    right_source = str(_source(right).get("name", ""))
    different_sources = bool(left_source and right_source and left_source != right_source)

    if same_subject and different_sources and _approximately_equal(left_value, right_value):
        return "approximately_equal", "corroborated"
    if (
        same_subject
        and different_sources
        and left_source in _RENDERABLE_SOURCE_ALIASES
        and right_source in _RENDERABLE_SOURCE_ALIASES
    ):
        return "not_equal", "divergent"

    if (
        left.get("field") in _DIRECTIONAL_FIELDS
        and right.get("field") in _DIRECTIONAL_FIELDS
        and ((left_value < 0 < right_value) or (right_value < 0 < left_value))
    ):
        return "opposite_direction", "none"
    if _approximately_equal(left_value, right_value):
        return "approximately_equal", "none"
    return ("greater_than", "none") if left_value > right_value else ("less_than", "none")


def _comparison_subject(left: Mapping[str, Any], right: Mapping[str, Any]) -> dict[str, str]:
    left_subject = _canonical_subject(left)
    right_subject = _canonical_subject(right)
    if left_subject == right_subject:
        return left_subject
    return {"type": "market", "id": "cross-subject-comparison"}


def _quality_significance(record: Mapping[str, Any]) -> str:
    field = str(record.get("field", "")).casefold()
    value = str(record.get("value", "")).casefold()
    if field in {"status", "quality_status"} and value in {
        "failed",
        "error",
        "invalid",
        "missing",
        "stale",
        "unavailable",
        "conflicting",
        "valid-degraded",
        "degraded",
    }:
        return "material"
    if field in {"status", "quality_status", "warning", "missing_symbols"}:
        return "minor"
    return "not_applicable"


def _qualifying_quality_record(record: Mapping[str, Any]) -> bool:
    field = str(record.get("field", "")).casefold()
    value = record.get("value")
    folded = str(value).casefold()
    if field in {"status", "quality_status"}:
        return folded in _LIMITATION_STATUS
    if field == "warning":
        return bool(value) and (
            record.get("evidence_type") != "string" or _safe_detail(record)
        )
    if field == "missing_symbols":
        return (
            record.get("evidence_type") == "set"
            and isinstance(value, list)
            and bool(value)
        )
    return False


def _compile_absolute(
    bundle_id: str, records: list[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for record in records:
        if not _eligible_observation(record):
            continue
        subject = _canonical_subject(record)
        field = str(record["field"])
        candidates.append(
            _candidate(
                bundle_id,
                intent="absolute_observation",
                records=[record],
                relation="none",
                section="market_summary",
                subject=subject,
                metric=field,
                features=_features(
                    [record],
                    materiality="not_applicable",
                    conflict_status="none",
                    quality_significance="not_applicable",
                    section_eligibility=["market_summary", "key_observations"],
                    redundancy_group=_slug(subject["id"], field),
                ),
            )
        )
    return candidates


def _compile_directional(
    bundle_id: str, records: list[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for record in records:
        if not _eligible_direction(record):
            continue
        subject = _canonical_subject(record)
        field = str(record["field"])
        candidates.append(
            _candidate(
                bundle_id,
                intent="directional_observation",
                records=[record],
                relation="none",
                section="key_observations",
                subject=subject,
                metric=field,
                features=_features(
                    [record],
                    materiality=_materiality_for_direction(record),
                    conflict_status="none",
                    quality_significance="not_applicable",
                    section_eligibility=["market_summary", "key_observations"],
                    redundancy_group=_slug(subject["id"], field, "direction"),
                ),
            )
        )
    return candidates


def _compile_comparisons(
    bundle_id: str, records: list[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    eligible = [
        record
        for record in records
        if _eligible_observation(record)
        and record.get("evidence_type") == "number"
        and _finite_number(record) is not None
    ]
    grouped: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for record in eligible:
        grouped[(str(record.get("field")), str(record.get("unit")))].append(record)

    candidates: list[dict[str, Any]] = []
    for (field, _unit), group in sorted(grouped.items()):
        ordered = sorted(group, key=lambda record: str(record["evidence_id"]))
        for left, right in combinations(ordered, 2):
            if (
                _canonical_subject(left) == _canonical_subject(right)
                and _source(left).get("name") == _source(right).get("name")
            ):
                continue
            relation, conflict = _comparison_relation(left, right)
            subject = _comparison_subject(left, right)
            same_subject = _canonical_subject(left) == _canonical_subject(right)
            eligibility = (
                ["key_observations", "risks_and_limitations"]
                if conflict == "divergent"
                else ["key_observations"]
            )
            group_name = (
                _slug(subject["id"], field)
                if same_subject
                else _slug(
                    "comparison",
                    _canonical_subject(left)["id"],
                    _canonical_subject(right)["id"],
                    field,
                )
            )
            candidates.append(
                _candidate(
                    bundle_id,
                    intent="comparison",
                    records=[left, right],
                    relation=relation,
                    section="key_observations",
                    subject=subject,
                    metric=field,
                    features=_features(
                        [left, right],
                        materiality=_comparison_materiality(left, right),
                        conflict_status=conflict,
                        quality_significance="not_applicable",
                        section_eligibility=eligibility,
                        redundancy_group=group_name,
                    ),
                )
            )
    return candidates


def _compile_source_status(
    bundle_id: str, records: list[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for record in records:
        subject = _subject(record)
        if subject.get("type") == "source" and isinstance(subject.get("id"), str):
            grouped[str(subject["id"])].append(record)

    candidates: list[dict[str, Any]] = []
    for subject_id, group in sorted(grouped.items()):
        statuses = [
            record
            for record in group
            if record.get("field") == "status"
            and record.get("evidence_type") == "status"
        ]
        if not statuses:
            continue
        if len(statuses) != 1:
            _fail(
                "ambiguous_source_status",
                f"$.bundle.evidence[{subject_id}]",
                "one source subject must have exactly one status record",
            )
        details = [
            record
            for field in _SOURCE_DETAIL_FIELDS
            for record in group
            if record.get("field") == field and _safe_detail(record)
        ]
        selected = [statuses[0], *details[:3]]
        candidates.append(
            _candidate(
                bundle_id,
                intent="source_status",
                records=selected,
                relation="none",
                section="source_status",
                subject={"type": "source", "id": subject_id},
                metric="status",
                features=_features(
                    selected,
                    materiality="not_applicable",
                    conflict_status="none",
                    quality_significance="not_applicable",
                    section_eligibility=["source_status"],
                    redundancy_group=_slug(subject_id, "source_status"),
                ),
            )
        )
    return candidates


def _compile_data_quality(
    bundle_id: str, records: list[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for record in records:
        subject = _canonical_subject(record)
        grouped[(subject["type"], subject["id"])].append(record)

    candidates: list[dict[str, Any]] = []
    for (subject_type, subject_id), group in sorted(grouped.items()):
        for qualifying in sorted(
            (record for record in group if _qualifying_quality_record(record)),
            key=lambda record: str(record["evidence_id"]),
        ):
            selected = [qualifying]
            if qualifying.get("field") in {"status", "quality_status"}:
                details = [
                    record
                    for field in _SOURCE_DETAIL_FIELDS
                    for record in group
                    if record.get("field") == field and _safe_detail(record)
                ]
                selected.extend(
                    record
                    for record in details
                    if record["evidence_id"] != qualifying["evidence_id"]
                )
                selected = selected[:4]
            field = str(qualifying["field"])
            candidates.append(
                _candidate(
                    bundle_id,
                    intent="data_quality_limitation",
                    records=selected,
                    relation="none",
                    section="data_quality",
                    subject={"type": subject_type, "id": subject_id},
                    metric=field,
                    features=_features(
                        selected,
                        materiality="not_applicable",
                        conflict_status="none",
                        quality_significance=_quality_significance(qualifying),
                        section_eligibility=["risks_and_limitations", "data_quality"],
                        redundancy_group=_slug(subject_id, field, "quality"),
                    ),
                )
            )
    return candidates


def _compile_snapshot_status(
    bundle_id: str, records: list[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for record in records:
        subject = _subject(record)
        if (
            subject.get("type") != "snapshot"
            or record.get("field") not in {"status", "quality_status"}
            or record.get("evidence_type") != "status"
        ):
            continue
        subject_id = str(subject.get("id", ""))
        field = str(record["field"])
        candidates.append(
            _candidate(
                bundle_id,
                intent="snapshot_status",
                records=[record],
                relation="none",
                section="data_quality",
                subject={"type": "snapshot", "id": subject_id},
                metric=field,
                features=_features(
                    [record],
                    materiality="not_applicable",
                    conflict_status="none",
                    quality_significance=(
                        _quality_significance(record)
                        if _qualifying_quality_record(record)
                        else "not_applicable"
                    ),
                    section_eligibility=["data_quality"],
                    redundancy_group=_slug(subject_id, field, "snapshot_status"),
                ),
            )
        )
    return candidates


def compile_claim_candidates(
    bundle: Mapping[str, Any],
    *,
    evidence_schema: dict[str, Any],
    candidate_schema: dict[str, Any],
) -> tuple[dict[str, Any], ...]:
    """Compile a canonical, exact-ID-valid and deterministically ordered candidate set."""

    if not isinstance(bundle, Mapping):
        _fail("bundle_type", "$.bundle", "evidence bundle must be an object")
    schema_diagnostics = validate_schema(dict(bundle), evidence_schema, path="$.bundle")
    if schema_diagnostics:
        first = schema_diagnostics[0]
        _fail("evidence_schema", first.path, first.message)
    if bundle.get("schema_version") != EVIDENCE_SCHEMA_VERSION:
        _fail(
            "evidence_version",
            "$.bundle.schema_version",
            f"evidence bundle must use {EVIDENCE_SCHEMA_VERSION}",
        )
    bundle_id = bundle.get("bundle_id")
    if not isinstance(bundle_id, str) or not _BUNDLE_ID_RE.fullmatch(bundle_id):
        _fail("bundle_id", "$.bundle.bundle_id", "evidence bundle ID is invalid")
    payload = {key: value for key, value in bundle.items() if key != "bundle_id"}
    expected_bundle_id = f"sha256:{content_sha256(payload)}"
    if bundle_id != expected_bundle_id:
        _fail(
            "bundle_id_mismatch",
            "$.bundle.bundle_id",
            "evidence bundle ID does not match canonical bundle content",
        )

    raw_records = bundle.get("evidence")
    if not isinstance(raw_records, list) or not raw_records:
        _fail("evidence_missing", "$.bundle.evidence", "evidence bundle contains no records")
    records = [record for record in raw_records if isinstance(record, Mapping)]
    if len(records) != len(raw_records):
        _fail("evidence_record_type", "$.bundle.evidence", "every evidence record must be an object")
    identifiers = [str(record.get("evidence_id", "")) for record in records]
    if len(identifiers) != len(set(identifiers)):
        _fail(
            "duplicate_evidence_id",
            "$.bundle.evidence",
            "evidence identifiers must be unique before compilation",
        )
    records = sorted(records, key=lambda record: str(record["evidence_id"]))

    candidates = [
        *_compile_absolute(bundle_id, records),
        *_compile_directional(bundle_id, records),
        *_compile_comparisons(bundle_id, records),
        *_compile_source_status(bundle_id, records),
        *_compile_data_quality(bundle_id, records),
        *_compile_snapshot_status(bundle_id, records),
    ]
    ordered = [dict(candidate) for candidate in order_candidates(candidates)]
    index_candidates_by_id(ordered)
    for index, candidate in enumerate(ordered):
        diagnostics = validate_schema(
            candidate,
            candidate_schema,
            path=f"$.candidates[{index}]",
        )
        if diagnostics:
            first = diagnostics[0]
            _fail("candidate_schema", first.path, first.message)
    return tuple(ordered)
