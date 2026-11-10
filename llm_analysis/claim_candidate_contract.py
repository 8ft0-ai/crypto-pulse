"""Deterministic identity and ordering for repository-owned claim candidates.

This module defines the executable parts of the Phase 6 Slice 1 contract. It
normalises candidate semantics, derives content-addressed identifiers and orders
already-constructed candidates. It does not enumerate evidence, rank candidates,
select claims, reconstruct plans or render prose.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from .contracts import (
    CLAIM_CANDIDATE_IDENTITY_VERSION,
    CLAIM_CANDIDATE_SCHEMA_VERSION,
    CLAIM_PLAN_COMPARISON_RELATIONS,
    CLAIM_PLAN_INTENTS,
    CLAIM_PLAN_SECTION_KINDS,
    content_sha256,
)

CLAIM_CANDIDATE_ID_PREFIX = "claim-candidate:sha256:"

CANDIDATE_SECTION_ORDER = CLAIM_PLAN_SECTION_KINDS
CANDIDATE_INTENT_ORDER = CLAIM_PLAN_INTENTS
CANDIDATE_COMPARISON_RELATION_ORDER = CLAIM_PLAN_COMPARISON_RELATIONS

_SEMANTIC_FIELDS = (
    "candidate_version",
    "evidence_bundle_id",
    "intent",
    "evidence_ids",
    "comparison_relation",
    "section",
    "subject",
    "metric",
    "confidence",
)
_INVERTED_RELATION = {
    "greater_than": "less_than",
    "less_than": "greater_than",
}


def _rank(value: Any, ordered: tuple[str, ...]) -> int:
    try:
        return ordered.index(str(value))
    except ValueError:
        return len(ordered)


def normalise_candidate_semantics(candidate: Mapping[str, Any]) -> dict[str, Any]:
    """Return the canonical semantic fields used for identity and ordering.

    Evidence identifiers are always sorted. When a comparison pair is reversed,
    asymmetric relations are inverted so equivalent operands retain equivalent
    meaning. Ranking features and ``candidate_id`` are intentionally excluded.
    """

    evidence_ids = [str(value) for value in candidate.get("evidence_ids", [])]
    relation = str(candidate.get("comparison_relation", ""))
    if candidate.get("intent") == "comparison" and len(evidence_ids) == 2:
        canonical_ids = sorted(evidence_ids)
        if evidence_ids != canonical_ids:
            relation = _INVERTED_RELATION.get(relation, relation)
        evidence_ids = canonical_ids
    else:
        evidence_ids = sorted(evidence_ids)

    subject = candidate.get("subject")
    canonical_subject = {
        "type": str(subject.get("type", "")) if isinstance(subject, Mapping) else "",
        "id": str(subject.get("id", "")) if isinstance(subject, Mapping) else "",
    }

    normalised = {
        "candidate_version": candidate.get("candidate_version"),
        "evidence_bundle_id": candidate.get("evidence_bundle_id"),
        "intent": candidate.get("intent"),
        "evidence_ids": evidence_ids,
        "comparison_relation": relation,
        "section": candidate.get("section"),
        "subject": canonical_subject,
        "metric": candidate.get("metric"),
        "confidence": candidate.get("confidence"),
    }
    return {field: normalised[field] for field in _SEMANTIC_FIELDS}


def candidate_identity_payload(candidate: Mapping[str, Any]) -> dict[str, Any]:
    """Return the domain-separated canonical payload hashed for candidate ID."""

    return {
        "identity_version": CLAIM_CANDIDATE_IDENTITY_VERSION,
        **normalise_candidate_semantics(candidate),
    }


def derive_candidate_id(candidate: Mapping[str, Any]) -> str:
    """Derive a stable content-addressed ID from repository-owned semantics."""

    return CLAIM_CANDIDATE_ID_PREFIX + content_sha256(candidate_identity_payload(candidate))


def candidate_id_matches(candidate: Mapping[str, Any]) -> bool:
    """Return whether the stored candidate ID matches its canonical semantics."""

    return candidate.get("candidate_id") == derive_candidate_id(candidate)


def candidate_sort_key(candidate: Mapping[str, Any]) -> tuple[Any, ...]:
    """Return the canonical presentation-order key for an existing candidate."""

    semantic = normalise_candidate_semantics(candidate)
    subject = semantic["subject"]
    return (
        _rank(semantic["section"], CANDIDATE_SECTION_ORDER),
        _rank(semantic["intent"], CANDIDATE_INTENT_ORDER),
        subject["type"],
        subject["id"],
        semantic["metric"],
        tuple(semantic["evidence_ids"]),
        _rank(semantic["comparison_relation"], CANDIDATE_COMPARISON_RELATION_ORDER),
        derive_candidate_id(candidate),
    )


def order_candidates(candidates: Iterable[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
    """Return candidates in stable presentation order without changing semantics."""

    return sorted(candidates, key=candidate_sort_key)


def index_candidates_by_id(
    candidates: Iterable[Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]]:
    """Build a fail-closed exact-ID lookup for an already-validated candidate set.

    Stored IDs must match canonical semantics and every ID must be unique. The
    function deliberately rejects even byte-identical duplicates so later
    selection cannot depend on implicit deduplication or traversal order.
    """

    result: dict[str, Mapping[str, Any]] = {}
    for candidate in candidates:
        candidate_id = candidate.get("candidate_id")
        if not isinstance(candidate_id, str) or not candidate_id_matches(candidate):
            raise ValueError("candidate ID does not match canonical candidate semantics")
        if candidate_id in result:
            raise ValueError(f"duplicate candidate ID: {candidate_id}")
        result[candidate_id] = candidate
    return result
