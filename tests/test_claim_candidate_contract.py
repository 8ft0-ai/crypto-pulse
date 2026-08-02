from __future__ import annotations

import copy
import json
import random
import unittest
from pathlib import Path
from typing import Any

from llm_analysis.claim_candidate_contract import (
    CANDIDATE_COMPARISON_RELATION_ORDER,
    CANDIDATE_INTENT_ORDER,
    CANDIDATE_SECTION_ORDER,
    candidate_id_matches,
    candidate_identity_payload,
    candidate_sort_key,
    derive_candidate_id,
    index_candidates_by_id,
    normalise_candidate_semantics,
    order_candidates,
)
from llm_analysis.contracts import (
    CLAIM_CANDIDATE_IDENTITY_VERSION,
    CLAIM_CANDIDATE_SCHEMA_VERSION,
    CLAIM_PLAN_COMPARISON_RELATIONS,
    CLAIM_PLAN_CONFIDENCE_LEVELS,
    CLAIM_PLAN_INTENTS,
    CLAIM_PLAN_SECTION_KINDS,
)
from llm_analysis.schema_validation import validate_schema

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "crypto-market-claim-candidate-v1.json"
CONTRACT = ROOT / "docs" / "reference" / "claim-candidate-contract.md"
FIXTURES = ROOT / "tests" / "fixtures" / "llm_analysis"

PROHIBITED_CANDIDATE_KEYS = {
    "text",
    "value",
    "unit",
    "currency",
    "date",
    "timestamp",
    "label",
    "alias",
    "headline",
    "heading",
    "sentence",
    "markdown",
    "rationale",
    "recommendation",
    "forecast",
    "target",
    "signal",
    "position",
    "action",
    "advice",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def nested_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {key for child in value.values() for key in nested_keys(child)}
    if isinstance(value, list):
        return {key for child in value for key in nested_keys(child)}
    return set()


def apply_invalid_mutation(candidates: list[dict[str, Any]], case: dict[str, Any]) -> dict[str, Any]:
    mutated = copy.deepcopy(candidates[case["base_index"]])
    target: Any = mutated
    for part in case["path"][:-1]:
        target = target[part]
    key = case["path"][-1]
    if case["operation"] == "delete":
        del target[key]
    else:
        target[key] = case["value"]
    return mutated


class ClaimCandidateContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = load_json(SCHEMA)
        cls.candidates = load_json(FIXTURES / "claim_candidates_valid.json")
        cls.invalid_cases = load_json(FIXTURES / "claim_candidate_invalid_cases.json")

    def test_versions_and_vocabularies_match_existing_claim_plan_contract(self) -> None:
        self.assertEqual(CLAIM_CANDIDATE_SCHEMA_VERSION, "crypto-market-claim-candidate/v1")
        self.assertEqual(CLAIM_CANDIDATE_IDENTITY_VERSION, "crypto-market-claim-candidate-identity/v1")
        self.assertEqual(
            self.schema["properties"]["candidate_version"]["const"],
            CLAIM_CANDIDATE_SCHEMA_VERSION,
        )
        self.assertEqual(tuple(self.schema["properties"]["intent"]["enum"]), CLAIM_PLAN_INTENTS)
        self.assertEqual(
            tuple(self.schema["properties"]["comparison_relation"]["enum"]),
            CLAIM_PLAN_COMPARISON_RELATIONS,
        )
        self.assertEqual(tuple(self.schema["properties"]["section"]["enum"]), CLAIM_PLAN_SECTION_KINDS)
        self.assertEqual(tuple(self.schema["properties"]["confidence"]["enum"]), CLAIM_PLAN_CONFIDENCE_LEVELS)
        self.assertEqual(CANDIDATE_SECTION_ORDER, CLAIM_PLAN_SECTION_KINDS)
        self.assertEqual(CANDIDATE_INTENT_ORDER, CLAIM_PLAN_INTENTS)
        self.assertEqual(CANDIDATE_COMPARISON_RELATION_ORDER, CLAIM_PLAN_COMPARISON_RELATIONS)

    def test_valid_fixtures_cover_every_intent_and_have_exact_content_ids(self) -> None:
        self.assertEqual({candidate["intent"] for candidate in self.candidates}, set(CLAIM_PLAN_INTENTS))
        for candidate in self.candidates:
            with self.subTest(intent=candidate["intent"]):
                self.assertEqual(validate_schema(candidate, self.schema), [])
                self.assertTrue(candidate_id_matches(candidate))
                self.assertEqual(candidate["candidate_id"], derive_candidate_id(candidate))

    def test_invalid_fixture_matrix_fails_closed(self) -> None:
        for name, case in self.invalid_cases.items():
            invalid_candidate = apply_invalid_mutation(self.candidates, case)
            diagnostics = validate_schema(invalid_candidate, self.schema)
            with self.subTest(case=name):
                self.assertTrue(diagnostics)
                self.assertIn(case["expected_code"], {item.code for item in diagnostics})

    def test_ranking_features_and_map_order_do_not_change_semantic_identity(self) -> None:
        candidate = copy.deepcopy(self.candidates[0])
        expected = derive_candidate_id(candidate)
        candidate["features"] = {
            "materiality_bucket": "high",
            "cross_source": True,
            "conflict_status": "corroborated",
            "recency_bucket": "recent",
            "quality_significance": "minor",
            "section_eligibility": ["key_observations", "market_summary"],
            "redundancy_group": "different_ranking_group",
            "corroboration_count": 3,
        }
        reordered = dict(reversed(list(candidate.items())))
        reordered["subject"] = dict(reversed(list(candidate["subject"].items())))
        self.assertEqual(derive_candidate_id(candidate), expected)
        self.assertEqual(derive_candidate_id(reordered), expected)
        self.assertNotIn("features", candidate_identity_payload(candidate))
        self.assertNotIn("candidate_id", candidate_identity_payload(candidate))

    def test_comparison_operand_reversal_preserves_identity_when_relation_is_inverted(self) -> None:
        canonical = copy.deepcopy(self.candidates[2])
        reversed_candidate = copy.deepcopy(canonical)
        reversed_candidate["evidence_ids"] = list(reversed(canonical["evidence_ids"]))
        reversed_candidate["comparison_relation"] = "not_equal"
        self.assertEqual(derive_candidate_id(reversed_candidate), derive_candidate_id(canonical))

        asymmetric = copy.deepcopy(canonical)
        asymmetric["comparison_relation"] = "greater_than"
        reversed_asymmetric = copy.deepcopy(asymmetric)
        reversed_asymmetric["evidence_ids"] = list(reversed(asymmetric["evidence_ids"]))
        reversed_asymmetric["comparison_relation"] = "less_than"
        self.assertEqual(
            normalise_candidate_semantics(reversed_asymmetric),
            normalise_candidate_semantics(asymmetric),
        )
        self.assertEqual(derive_candidate_id(reversed_asymmetric), derive_candidate_id(asymmetric))

    def test_each_semantic_change_changes_identity(self) -> None:
        base = copy.deepcopy(self.candidates[0])
        expected = derive_candidate_id(base)
        mutations = {
            "bundle": ("evidence_bundle_id", "sha256:" + "b" * 64),
            "intent": ("intent", "directional_observation"),
            "operands": ("evidence_ids", ["market.asset.bitcoin.market_cap_usd"]),
            "relation": ("comparison_relation", "not_equal"),
            "section": ("section", "key_observations"),
            "metric": ("metric", "market_cap_usd"),
            "confidence": ("confidence", "medium"),
        }
        for name, (field, value) in mutations.items():
            changed = copy.deepcopy(base)
            changed[field] = value
            with self.subTest(field=name):
                self.assertNotEqual(derive_candidate_id(changed), expected)
        changed_subject = copy.deepcopy(base)
        changed_subject["subject"]["id"] = "ethereum"
        self.assertNotEqual(derive_candidate_id(changed_subject), expected)

    def test_candidate_order_is_stable_across_input_traversal(self) -> None:
        expected = [candidate["candidate_id"] for candidate in order_candidates(self.candidates)]
        for seed in range(10):
            shuffled = copy.deepcopy(self.candidates)
            random.Random(seed).shuffle(shuffled)
            actual = [candidate["candidate_id"] for candidate in order_candidates(shuffled)]
            self.assertEqual(actual, expected)
        self.assertEqual(
            [candidate_sort_key(candidate) for candidate in order_candidates(self.candidates)],
            sorted(candidate_sort_key(candidate) for candidate in self.candidates),
        )

    def test_exact_id_index_rejects_stale_and_duplicate_ids(self) -> None:
        index = index_candidates_by_id(self.candidates)
        self.assertEqual(set(index), {candidate["candidate_id"] for candidate in self.candidates})
        stale = copy.deepcopy(self.candidates[0])
        stale["metric"] = "market_cap_usd"
        with self.assertRaisesRegex(ValueError, "does not match"):
            index_candidates_by_id([stale])
        with self.assertRaisesRegex(ValueError, "duplicate candidate ID"):
            index_candidates_by_id([self.candidates[0], copy.deepcopy(self.candidates[0])])

    def test_contract_exposes_no_model_authored_facts_or_prose(self) -> None:
        self.assertFalse(PROHIBITED_CANDIDATE_KEYS & nested_keys(self.schema))
        for candidate in self.candidates:
            self.assertFalse(PROHIBITED_CANDIDATE_KEYS & nested_keys(candidate))
        self.assertEqual(
            set(self.schema["properties"]),
            {
                "candidate_version",
                "candidate_id",
                "evidence_bundle_id",
                "intent",
                "evidence_ids",
                "comparison_relation",
                "section",
                "subject",
                "metric",
                "confidence",
                "features",
            },
        )

    def test_reference_documents_identity_ordering_compatibility_and_scope(self) -> None:
        text = CONTRACT.read_text(encoding="utf-8")
        for marker in (
            "claim-candidate:sha256:",
            "canonical JSON",
            "ranking features are excluded",
            "comparison operands",
            "Presentation ordering",
            "`crypto-market-claim-plan/v1` remains unchanged",
            "A future model may select existing candidate IDs only",
            "Slice 2 remains blocked",
            "does not compile candidates",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, text)


if __name__ == "__main__":
    unittest.main()
