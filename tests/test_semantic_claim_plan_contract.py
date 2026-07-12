from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path
from typing import Any

from llm_analysis.contracts import (
    CLAIM_PLAN_COMPARISON_RELATIONS,
    CLAIM_PLAN_CONFIDENCE_LEVELS,
    CLAIM_PLAN_INTENTS,
    CLAIM_PLAN_PROMPT_VERSION,
    CLAIM_PLAN_SCHEMA_VERSION,
    CLAIM_PLAN_SECTION_KINDS,
)
from llm_analysis.openai_schema_projection import project_openai_strict_schema
from llm_analysis.schema_validation import validate_schema

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "crypto-market-claim-plan-v1.json"
PROMPT = ROOT / "prompts" / "crypto-market-claim-plan-v1.md"
CONTRACT = ROOT / "docs" / "reference" / "semantic-claim-plan-contract.md"
FIXTURES = ROOT / "tests" / "fixtures" / "llm_analysis"

PROHIBITED_PLAN_KEYS = {
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
    "quoted_values",
    "recommendation",
    "forecast",
    "target",
    "signal",
    "position",
    "action",
}


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def nested_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {key for child in value.values() for key in nested_keys(child)}
    if isinstance(value, list):
        return {key for child in value for key in nested_keys(child)}
    return set()


def object_schemas(value: Any) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    if isinstance(value, dict):
        if value.get("type") == "object":
            result.append(value)
        for child in value.values():
            result.extend(object_schemas(child))
    elif isinstance(value, list):
        for child in value:
            result.extend(object_schemas(child))
    return result


def apply_invalid_mutation(plan: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    mutated = copy.deepcopy(plan)
    path = case["path"]
    target: Any = mutated
    for part in path[:-1]:
        target = target[part]
    key = path[-1]
    if case["operation"] == "delete":
        del target[key]
    else:
        target[key] = case["value"]
    return mutated


class SemanticClaimPlanContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = load_json(SCHEMA)
        cls.plan = load_json(FIXTURES / "claim_plan_valid.json")
        cls.invalid_cases = load_json(FIXTURES / "claim_plan_invalid_cases.json")

    def test_version_constants_match_schema_fixture_and_prompt(self) -> None:
        self.assertEqual(CLAIM_PLAN_SCHEMA_VERSION, "crypto-market-claim-plan/v1")
        self.assertEqual(CLAIM_PLAN_PROMPT_VERSION, CLAIM_PLAN_SCHEMA_VERSION)
        self.assertEqual(self.schema["properties"]["claim_plan_version"]["const"], CLAIM_PLAN_SCHEMA_VERSION)
        self.assertEqual(self.schema["properties"]["prompt_version"]["const"], CLAIM_PLAN_PROMPT_VERSION)
        self.assertEqual(self.plan["claim_plan_version"], CLAIM_PLAN_SCHEMA_VERSION)
        self.assertEqual(self.plan["prompt_version"], CLAIM_PLAN_PROMPT_VERSION)

    def test_bounded_vocabularies_match_the_canonical_schema(self) -> None:
        claim = self.schema["$defs"]["claim"]["properties"]
        section = self.schema["$defs"]["section"]["properties"]
        self.assertEqual(tuple(claim["intent"]["enum"]), CLAIM_PLAN_INTENTS)
        self.assertEqual(tuple(claim["comparison_relation"]["enum"]), CLAIM_PLAN_COMPARISON_RELATIONS)
        self.assertEqual(tuple(claim["confidence"]["enum"]), CLAIM_PLAN_CONFIDENCE_LEVELS)
        self.assertEqual(tuple(section["section_kind"]["enum"]), CLAIM_PLAN_SECTION_KINDS)
        self.assertEqual(tuple(self.schema["properties"]["analysis_order"]["items"]["enum"]), CLAIM_PLAN_SECTION_KINDS)

    def test_valid_fixture_is_schema_valid_and_covers_every_intent(self) -> None:
        self.assertEqual(validate_schema(self.plan, self.schema), [])
        intents = {
            claim["intent"]
            for section in self.plan["sections"]
            for claim in section["claims"]
        }
        self.assertEqual(intents, set(CLAIM_PLAN_INTENTS))
        comparisons = [
            claim
            for section in self.plan["sections"]
            for claim in section["claims"]
            if claim["intent"] == "comparison"
        ]
        self.assertEqual(len(comparisons), 1)
        self.assertNotEqual(comparisons[0]["comparison_relation"], "none")

    def test_invalid_fixture_matrix_fails_closed(self) -> None:
        expected_names = {
            "free_form_report_prose",
            "copied_numeric_value",
            "copied_date",
            "unsupported_intent",
            "unsupported_relation",
            "unknown_root_field",
            "duplicate_analysis_order",
            "duplicate_evidence_reference",
            "missing_required_claim_field",
        }
        self.assertEqual(set(self.invalid_cases), expected_names)
        for name, case in self.invalid_cases.items():
            invalid_plan = apply_invalid_mutation(self.plan, case)
            diagnostics = validate_schema(invalid_plan, self.schema)
            with self.subTest(case=name):
                self.assertTrue(diagnostics)
                self.assertIn(case["expected_code"], {item.code for item in diagnostics})

    def test_contract_exposes_no_free_form_governed_content_or_values(self) -> None:
        self.assertFalse(PROHIBITED_PLAN_KEYS & nested_keys(self.schema))
        self.assertFalse(PROHIBITED_PLAN_KEYS & nested_keys(self.plan))
        allowed_claim_keys = {
            "claim_id",
            "intent",
            "evidence_ids",
            "comparison_relation",
            "confidence",
        }
        for section in self.plan["sections"]:
            for claim in section["claims"]:
                self.assertEqual(set(claim), allowed_claim_keys)

    def test_every_object_is_closed_and_provider_projection_is_deterministic(self) -> None:
        canonical_before = copy.deepcopy(self.schema)
        first = project_openai_strict_schema(self.schema)
        second = project_openai_strict_schema(self.schema)
        self.assertEqual(first, second)
        self.assertEqual(self.schema, canonical_before)
        self.assertNotIn("$schema", first)
        self.assertNotIn("$id", first)
        self.assertNotIn("uniqueItems", nested_keys(first))
        for object_schema in object_schemas(first):
            self.assertFalse(object_schema["additionalProperties"])
            self.assertEqual(set(object_schema["required"]), set(object_schema.get("properties", {})))

    def test_prompt_requests_semantic_planning_and_reserves_rendering(self) -> None:
        text = PROMPT.read_text(encoding="utf-8")
        for marker in (
            "You are not writing a report",
            "Do not copy or restate evidence values",
            "Repository code, not the model, owns",
            "<BEGIN_UNTRUSTED_EVIDENCE_BUNDLE>",
            "<END_UNTRUSTED_EVIDENCE_BUNDLE>",
            "Return JSON only",
            "No model-authored prose will be interpolated",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, text)
        self.assertNotIn("OPENROUTER_API_KEY", text)
        self.assertNotIn("GITHUB_TOKEN", text)

    def test_reference_documents_provider_safe_sentinel_and_authority_boundary(self) -> None:
        text = CONTRACT.read_text(encoding="utf-8")
        for marker in (
            "crypto-market-claim-plan/v1",
            "comparison_relation",
            "provider schema has no optional object property",
            "canonical schema remains authoritative",
            "Repository code owns",
            "Fixtures authorise no provider call",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, text)


if __name__ == "__main__":
    unittest.main()
