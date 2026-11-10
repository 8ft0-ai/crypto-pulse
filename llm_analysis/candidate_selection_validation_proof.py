"""Evaluation-only invalid-selection fixtures for the Slice 5 proof."""
from __future__ import annotations

import copy
from typing import Any, Mapping, Sequence

from .candidate_selection_contract import validate_candidate_selection
from .claim_candidate_contract import derive_candidate_id, order_candidates


def _synthetic_redundancy_case(
    candidates: Sequence[Mapping[str, Any]], config: Any
) -> tuple[dict[str, Any], dict[str, Any]]:
    ordered = list(order_candidates(candidates))
    existing_ids = {str(item["candidate_id"]) for item in ordered}
    for first in ordered:
        for second in ordered:
            if first["candidate_id"] == second["candidate_id"]:
                continue
            if first["section"] != second["section"] or first["intent"] != second["intent"]:
                continue
            if config.section_limits[first["section"]] < 2:
                continue
            if config.intent_limits[first["intent"]] < 2:
                continue
            synthetic = copy.deepcopy(second)
            synthetic["features"]["redundancy_group"] = first["features"]["redundancy_group"]
            synthetic["subject"]["id"] = synthetic["subject"]["id"] + "-synthetic"
            synthetic["candidate_id"] = ""
            synthetic["candidate_id"] = derive_candidate_id(synthetic)
            if synthetic["candidate_id"] not in existing_ids:
                return dict(first), synthetic
    raise ValueError("no candidates can form an evaluation-only redundancy pair")


def validation_matrix(
    candidates: Sequence[Mapping[str, Any]],
    *,
    config: Any,
    bundle_id: str,
    selection_schema: Mapping[str, Any],
) -> list[dict[str, Any]]:
    ordered = list(order_candidates(candidates))
    first_id = str(ordered[0]["candidate_id"])
    unknown = "claim-candidate:sha256:" + "0" * 64

    mixed = copy.deepcopy(ordered[0])
    mixed["evidence_bundle_id"] = "sha256:" + "f" * 64
    mixed["candidate_id"] = ""
    mixed["candidate_id"] = derive_candidate_id(mixed)

    first, synthetic = _synthetic_redundancy_case(ordered, config)
    checks = [
        ("unknown", {"selected_candidate_ids": [unknown]}, ordered),
        ("duplicate", {"selected_candidate_ids": [first_id, first_id]}, ordered),
        (
            "excessive",
            {
                "selected_candidate_ids": [
                    str(item["candidate_id"])
                    for item in ordered[: config.max_total + 1]
                ]
            },
            ordered,
        ),
        (
            "redundancy",
            {"selected_candidate_ids": [first["candidate_id"], synthetic["candidate_id"]]},
            [*ordered, synthetic],
        ),
        ("mixed_bundle", {"selected_candidate_ids": [mixed["candidate_id"]]}, [*ordered, mixed]),
    ]
    result: list[dict[str, Any]] = []
    for name, payload, candidate_set in checks:
        validation = validate_candidate_selection(
            payload,
            candidate_set,
            config=config,
            evidence_bundle_id=bundle_id,
            selection_schema=selection_schema,
        )
        if validation.is_valid:
            raise ValueError(f"invalid response accepted: {name}")
        result.append(
            {
                "name": name,
                "response": payload,
                "diagnostics": [item.as_dict() for item in validation.diagnostics],
            }
        )
    return result
