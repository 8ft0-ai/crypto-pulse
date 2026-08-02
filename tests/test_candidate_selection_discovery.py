from __future__ import annotations

import copy
import unittest
from pathlib import Path
from typing import Any, Mapping, Sequence

import llm_analysis.candidate_selection_evaluation as evaluation
from llm_analysis.candidate_selection_contract import validate_candidate_selection
from llm_analysis.claim_candidate_contract import derive_candidate_id, order_candidates

ROOT = Path(__file__).resolve().parents[1]


def _proof_validation_matrix(
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

    pair: tuple[dict[str, Any], dict[str, Any]] | None = None
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
            synthetic["candidate_id"] = ""
            synthetic["candidate_id"] = derive_candidate_id(synthetic)
            pair = (dict(first), synthetic)
            break
        if pair is not None:
            break
    if pair is None:
        raise AssertionError("no candidates can form a synthetic redundancy pair")

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
            {
                "selected_candidate_ids": [
                    pair[0]["candidate_id"],
                    pair[1]["candidate_id"],
                ]
            },
            [*ordered, pair[1]],
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
            raise AssertionError(f"invalid response accepted: {name}")
        result.append(
            {
                "name": name,
                "response": payload,
                "diagnostics": [item.as_dict() for item in validation.diagnostics],
            }
        )
    return result


class CandidateSelectionDiscoveryTests(unittest.TestCase):
    def test_emit_retained_selector_proof(self) -> None:
        evaluation.validation_matrix = _proof_validation_matrix
        proof = evaluation.evaluate_candidate_selection_proof(ROOT)
        for path, content in proof.outputs.items():
            print(f"SLICE5_OUTPUT_BEGIN {path}")
            print(content.decode("utf-8"), end="")
            print(f"SLICE5_OUTPUT_END {path}")
        self.fail("intentional discovery run; replace with retained-output tests")
