"""Compact provider-only projection of the canonical Slice 5 selector request."""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from .contracts import content_sha256

COMPACT_SELECTOR_REQUEST_VERSION = "phase-06-compact-candidate-selector-request/v1"
MAX_COMPACT_REQUEST_BYTES = 65_536

_FIELDS = (
    "candidate_id",
    "section",
    "intent",
    "subject_type",
    "subject_id",
    "metric",
    "confidence",
    "comparison_relation",
    "materiality_bucket",
    "conflict_status",
    "quality_significance",
    "cross_source",
    "corroboration_count",
    "recency_bucket",
    "redundancy_group",
)

_VALUE_CODES: dict[str, dict[str, str]] = {
    "section": {
        "market_summary": "ms",
        "key_observations": "ko",
        "data_quality": "dq",
        "source_status": "ss",
    },
    "intent": {
        "absolute_observation": "ao",
        "directional_observation": "do",
        "comparison": "cp",
        "source_status": "ss",
        "data_quality_limitation": "dl",
        "snapshot_status": "sn",
    },
    "subject_type": {
        "asset": "a",
        "market": "m",
        "exchange_pair": "e",
        "defi_metric": "d",
        "source": "s",
        "snapshot": "n",
    },
    "confidence": {"high": "h", "medium": "m", "low": "l"},
    "comparison_relation": {
        "none": "n",
        "greater_than": "gt",
        "less_than": "lt",
        "approximately_equal": "ae",
        "opposite_direction": "od",
    },
    "materiality_bucket": {
        "not_applicable": "na",
        "low": "l",
        "medium": "m",
        "high": "h",
    },
    "conflict_status": {"none": "n", "present": "p"},
    "quality_significance": {
        "not_applicable": "na",
        "minor": "mi",
        "material": "ma",
    },
    "recency_bucket": {
        "unknown": "u",
        "current": "c",
        "recent": "r",
        "stale": "s",
    },
}


class CompactSelectorProjectionError(ValueError):
    pass


def _code(field: str, value: Any, path: str) -> str:
    if not isinstance(value, str):
        raise CompactSelectorProjectionError(f"{path} must be a string")
    mapping = _VALUE_CODES[field]
    if value not in mapping:
        raise CompactSelectorProjectionError(
            f"{path} uses unsupported {field} value {value!r}"
        )
    return mapping[value]


def _candidate_row(candidate: Mapping[str, Any], index: int) -> list[Any]:
    path = f"$.candidates[{index}]"
    subject = candidate.get("subject")
    features = candidate.get("features")
    if not isinstance(subject, Mapping):
        raise CompactSelectorProjectionError(f"{path}.subject must be an object")
    if not isinstance(features, Mapping):
        raise CompactSelectorProjectionError(f"{path}.features must be an object")
    identifier = candidate.get("candidate_id")
    subject_id = subject.get("id")
    metric = candidate.get("metric")
    redundancy_group = features.get("redundancy_group")
    if not isinstance(identifier, str) or not identifier.startswith("claim-candidate:sha256:"):
        raise CompactSelectorProjectionError(f"{path}.candidate_id is invalid")
    for name, value in (
        ("subject.id", subject_id),
        ("metric", metric),
        ("features.redundancy_group", redundancy_group),
    ):
        if not isinstance(value, str) or not value:
            raise CompactSelectorProjectionError(f"{path}.{name} must be a string")
    cross_source = features.get("cross_source")
    corroboration = features.get("corroboration_count")
    if not isinstance(cross_source, bool):
        raise CompactSelectorProjectionError(
            f"{path}.features.cross_source must be a boolean"
        )
    if (
        isinstance(corroboration, bool)
        or not isinstance(corroboration, int)
        or corroboration < 0
    ):
        raise CompactSelectorProjectionError(
            f"{path}.features.corroboration_count must be a non-negative integer"
        )
    return [
        identifier,
        _code("section", candidate.get("section"), f"{path}.section"),
        _code("intent", candidate.get("intent"), f"{path}.intent"),
        _code("subject_type", subject.get("type"), f"{path}.subject.type"),
        subject_id,
        metric,
        _code("confidence", candidate.get("confidence"), f"{path}.confidence"),
        _code(
            "comparison_relation",
            candidate.get("comparison_relation"),
            f"{path}.comparison_relation",
        ),
        _code(
            "materiality_bucket",
            features.get("materiality_bucket"),
            f"{path}.features.materiality_bucket",
        ),
        _code(
            "conflict_status",
            features.get("conflict_status"),
            f"{path}.features.conflict_status",
        ),
        _code(
            "quality_significance",
            features.get("quality_significance"),
            f"{path}.features.quality_significance",
        ),
        1 if cross_source else 0,
        corroboration,
        _code(
            "recency_bucket",
            features.get("recency_bucket"),
            f"{path}.features.recency_bucket",
        ),
        redundancy_group,
    ]


def build_compact_candidate_selector_request(
    canonical_request: Mapping[str, Any],
) -> dict[str, Any]:
    candidates = canonical_request.get("candidates")
    if not isinstance(candidates, Sequence) or isinstance(candidates, (str, bytes)):
        raise CompactSelectorProjectionError("$.candidates must be an array")
    canonical_ids = [
        candidate.get("candidate_id") if isinstance(candidate, Mapping) else None
        for candidate in candidates
    ]
    if any(not isinstance(identifier, str) for identifier in canonical_ids):
        raise CompactSelectorProjectionError("every candidate must have a string ID")
    rows = [
        _candidate_row(candidate, index)
        for index, candidate in enumerate(candidates)
        if isinstance(candidate, Mapping)
    ]
    if len(rows) != len(candidates):
        raise CompactSelectorProjectionError("every candidate must be an object")
    projected_ids = [row[0] for row in rows]
    if projected_ids != canonical_ids:
        raise CompactSelectorProjectionError(
            "compact projection changed canonical candidate order or identity"
        )
    compact = {
        "version": COMPACT_SELECTOR_REQUEST_VERSION,
        "canonical_request_id": canonical_request.get("request_id"),
        "evidence_bundle_id": canonical_request.get("evidence_bundle_id"),
        "candidate_set_id": canonical_request.get("candidate_set_id"),
        "ranking_version": canonical_request.get("ranking_version"),
        "ranking_config_sha256": canonical_request.get("ranking_config_sha256"),
        "max_selection_count": canonical_request.get("max_selection_count"),
        "section_limits": canonical_request.get("section_limits"),
        "intent_limits": canonical_request.get("intent_limits"),
        "response_schema_version": canonical_request.get("response_schema_version"),
        "fields": list(_FIELDS),
        "value_codes": {
            field: dict(sorted(values.items()))
            for field, values in sorted(_VALUE_CODES.items())
        },
        "candidates": rows,
    }
    return {
        **compact,
        "compact_request_id": "sha256:" + content_sha256(compact),
    }
