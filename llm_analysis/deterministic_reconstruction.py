"""Defence-in-depth validation for deterministic claim-plan reconstruction."""
from __future__ import annotations

from collections import Counter
from typing import Any, Mapping, Sequence

from .claim_candidate_contract import index_candidates_by_id
from .deterministic_ranking import (
    DeterministicRankingError,
    RankingConfig,
    reconstruct_claim_plan as _reconstruct_claim_plan,
)


def _fail(code: str, path: str, message: str) -> None:
    raise DeterministicRankingError(code, path, message)


def reconstruct_claim_plan(
    selection: Mapping[str, Any],
    candidates: Sequence[Mapping[str, Any]],
    *,
    config: RankingConfig,
) -> dict[str, Any]:
    """Reconstruct only selections that satisfy every repository-owned bound."""

    identifiers = selection.get("selected_candidate_ids")
    if not isinstance(identifiers, list):
        _fail(
            "invalid_list",
            "$.selection.selected_candidate_ids",
            "must be a list",
        )
    if not identifiers:
        _fail(
            "empty_selection",
            "$.selection.selected_candidate_ids",
            "must not be empty",
        )
    if len(identifiers) != len(set(identifiers)):
        _fail(
            "duplicate_selection",
            "$.selection.selected_candidate_ids",
            "must be unique",
        )
    if len(identifiers) > config.max_total:
        _fail(
            "excessive_selection",
            "$.selection.selected_candidate_ids",
            f"must contain at most {config.max_total} candidate IDs",
        )

    bundle_id = selection.get("evidence_bundle_id")
    if not isinstance(bundle_id, str) or not bundle_id.strip():
        _fail(
            "invalid_string",
            "$.selection.evidence_bundle_id",
            "must be a non-empty string",
        )

    try:
        indexed = index_candidates_by_id(candidates)
    except ValueError as exc:
        _fail("invalid_candidate_identity", "$.candidates", str(exc))

    missing = [identifier for identifier in identifiers if identifier not in indexed]
    if missing:
        _fail(
            "unknown_selected_candidate_id",
            "$.selection.selected_candidate_ids",
            "unknown candidate IDs: " + ", ".join(str(item) for item in missing),
        )

    section_counts: Counter[str] = Counter()
    intent_counts: Counter[str] = Counter()
    redundancy_groups: set[str] = set()
    for index, identifier in enumerate(identifiers):
        candidate = indexed[str(identifier)]
        path = f"$.selection.selected_candidate_ids[{index}]"
        if candidate.get("evidence_bundle_id") != bundle_id:
            _fail(
                "selected_candidate_bundle_mismatch",
                path,
                "selected candidate does not reference the selection evidence bundle",
            )

        section = candidate.get("section")
        if not isinstance(section, str) or section not in config.section_limits:
            _fail("unsupported_section", path, f"unsupported section: {section!r}")
        intent = candidate.get("intent")
        if not isinstance(intent, str) or intent not in config.intent_limits:
            _fail("unsupported_intent", path, f"unsupported intent: {intent!r}")

        section_counts[section] += 1
        intent_counts[intent] += 1
        if section_counts[section] > min(
            config.section_limits[section],
            config.max_per_section,
        ):
            _fail(
                "selection_section_limit",
                path,
                f"selection exceeds the configured {section} section limit",
            )
        if intent_counts[intent] > config.intent_limits[intent]:
            _fail(
                "selection_intent_limit",
                path,
                f"selection exceeds the configured {intent} intent limit",
            )

        features = candidate.get("features")
        if not isinstance(features, Mapping):
            _fail("invalid_mapping", path, "candidate features must be an object")
        redundancy_group = features.get("redundancy_group")
        if not isinstance(redundancy_group, str) or not redundancy_group.strip():
            _fail(
                "invalid_string",
                path,
                "candidate redundancy group must be a non-empty string",
            )
        if redundancy_group in redundancy_groups:
            _fail(
                "selection_redundancy_violation",
                path,
                f"redundancy group selected more than once: {redundancy_group}",
            )
        redundancy_groups.add(redundancy_group)

    return _reconstruct_claim_plan(selection, candidates, config=config)
