from __future__ import annotations

import json
import re
import unittest
from pathlib import Path
from typing import Any

from llm_analysis.contracts import (
    ANALYSIS_SCHEMA_VERSION,
    CLAIM_TYPES,
    EVIDENCE_ID_PATTERN,
    EVIDENCE_SCHEMA_VERSION,
    PROMPT_VERSION,
    PROVENANCE_SCHEMA_VERSION,
    canonical_json_bytes,
    content_sha256,
    evidence_id,
)

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "schemas"
FIXTURES = ROOT / "tests" / "fixtures" / "llm_analysis"
PROMPT = ROOT / "prompts" / "crypto-market-analysis-v1.md"
CONTRACT = ROOT / "docs" / "governed-llm-analysis-contract.md"

PROHIBITED_FIELDS = {"recommendation", "position", "target", "entry", "exit", "trade", "signal"}
CAUSAL_RE = re.compile(r"\b(?:because|caused by|due to|drove|driven by)\b", re.IGNORECASE)
ADVICE_RE = re.compile(
    r"\b(?:should\s+(?:buy|sell|hold|trade|invest)|buy|sell|trading signal|price target|portfolio|position)\b",
    re.IGNORECASE,
)
PROMPT_OVERRIDE_RE = re.compile(r"\b(?:ignore|override|replace)\b.*\b(?:schema|instruction|prompt|policy)\b", re.IGNORECASE)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def claims(analysis: dict[str, Any]) -> list[dict[str, Any]]:
    result = [analysis["headline"]]
    for name in ("market_summary", "key_observations", "risks_and_limitations", "data_quality_notes"):
        result.extend(analysis[name])
    result.append(analysis["source_evidence_note"])
    return result


def nested_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return set(value) | {key for child in value.values() for key in nested_keys(child)}
    if isinstance(value, list):
        return {key for child in value for key in nested_keys(child)}
    return set()


def claim_violations(claim: dict[str, Any], evidence_by_id: dict[str, dict[str, Any]]) -> set[str]:
    violations: set[str] = set()
    claim_type = claim.get("claim_type")
    if claim_type not in CLAIM_TYPES:
        violations.add("unsupported_claim_type")

    evidence_ids = claim.get("evidence_ids", [])
    if any(item not in evidence_by_id for item in evidence_ids):
        violations.add("unknown_evidence_id")

    if PROHIBITED_FIELDS & nested_keys(claim):
        violations.add("prohibited_field")

    text = str(claim.get("text", ""))
    if CAUSAL_RE.search(text):
        violations.add("causal_language")
    if ADVICE_RE.search(text):
        violations.add("advice_language")
    if PROMPT_OVERRIDE_RE.search(text):
        violations.add("prompt_override_language")

    if claim_type == "qualitative_interpretation" and len(evidence_ids) < 2:
        violations.add("qualitative_support")

    if claim_type in {"comparison", "source_disagreement"}:
        comparison = claim.get("comparison")
        if not isinstance(comparison, dict):
            violations.add("missing_comparison")
        else:
            left = evidence_by_id.get(comparison.get("left_evidence_id"))
            right = evidence_by_id.get(comparison.get("right_evidence_id"))
            if not left or not right:
                violations.add("unknown_evidence_id")
            elif left.get("evidence_type") != "number" or right.get("evidence_type") != "number":
                violations.add("incompatible_comparison")
            elif left.get("unit") != right.get("unit"):
                violations.add("incompatible_comparison")
            else:
                relation = comparison.get("relation")
                left_value = left["value"]
                right_value = right["value"]
                relation_ok = {
                    "greater_than": left_value > right_value,
                    "less_than": left_value < right_value,
                    "approximately_equal": abs(left_value - right_value)
                    <= max(abs(left_value), abs(right_value), 1) * 0.001,
                    "not_equal": left_value != right_value,
                    "opposite_direction": (left_value < 0 < right_value)
                    or (right_value < 0 < left_value),
                }.get(relation, False)
                if not relation_ok:
                    violations.add("comparison_mismatch")

    for quoted in claim.get("quoted_values", []):
        evidence = evidence_by_id.get(quoted.get("evidence_id"))
        if not evidence or evidence.get("evidence_type") != "number":
            violations.add("quoted_value_mismatch")
            continue
        if quoted.get("value") != evidence.get("value") or quoted.get("unit") != evidence.get("unit"):
            violations.add("quoted_value_mismatch")

    return violations


class GovernedLlmContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.evidence_schema = load_json(SCHEMAS / "crypto-market-evidence-bundle-v1.json")
        cls.analysis_schema = load_json(SCHEMAS / "crypto-market-analysis-v1.json")
        cls.provenance_schema = load_json(SCHEMAS / "crypto-market-generation-provenance-v1.json")
        cls.bundle = load_json(FIXTURES / "evidence_bundle_valid.json")
        cls.analysis = load_json(FIXTURES / "analysis_valid.json")
        cls.invalid_cases = load_json(FIXTURES / "analysis_invalid_cases.json")
        cls.provenance = load_json(FIXTURES / "generation_provenance_valid.json")
        cls.evidence_by_id = {item["evidence_id"]: item for item in cls.bundle["evidence"]}

    def test_version_constants_match_schemas_and_fixtures(self) -> None:
        self.assertEqual(self.bundle["schema_version"], EVIDENCE_SCHEMA_VERSION)
        self.assertEqual(self.analysis["schema_version"], ANALYSIS_SCHEMA_VERSION)
        self.assertEqual(self.analysis["prompt_version"], PROMPT_VERSION)
        self.assertEqual(self.provenance["schema_version"], PROVENANCE_SCHEMA_VERSION)
        self.assertEqual(
            self.evidence_schema["properties"]["schema_version"]["const"],
            EVIDENCE_SCHEMA_VERSION,
        )
        self.assertEqual(
            self.analysis_schema["properties"]["schema_version"]["const"],
            ANALYSIS_SCHEMA_VERSION,
        )
        self.assertEqual(
            self.provenance_schema["properties"]["schema_version"]["const"],
            PROVENANCE_SCHEMA_VERSION,
        )

    def test_schema_documents_are_strict_and_reviewer_visible(self) -> None:
        for schema in (self.evidence_schema, self.analysis_schema, self.provenance_schema):
            self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
            self.assertFalse(schema["additionalProperties"])
            self.assertTrue(
                schema["$id"].startswith("https://8ft0-ai.github.io/crypto-pulse/schemas/")
            )

    def test_claim_taxonomy_matches_analysis_schema(self) -> None:
        schema_claim_types = tuple(
            self.analysis_schema["$defs"]["claim"]["properties"]["claim_type"]["enum"]
        )
        self.assertEqual(schema_claim_types, CLAIM_TYPES)

    def test_analysis_schema_exposes_no_advice_or_trading_fields(self) -> None:
        self.assertFalse(PROHIBITED_FIELDS & nested_keys(self.analysis_schema))
        self.assertFalse(PROHIBITED_FIELDS & nested_keys(self.analysis))

    def test_evidence_ids_are_deterministic_unique_and_well_formed(self) -> None:
        ids = [item["evidence_id"] for item in self.bundle["evidence"]]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(re.fullmatch(EVIDENCE_ID_PATTERN, item) for item in ids))
        self.assertEqual(
            evidence_id("market", "asset", "bitcoin", "change_24h_pct"),
            "market.asset.bitcoin.change_24h_pct",
        )
        with self.assertRaises(ValueError):
            evidence_id("market", "Bad Segment")

    def test_canonical_json_and_hash_are_stable(self) -> None:
        left = {"b": 2, "a": [3, 1]}
        right = {"a": [3, 1], "b": 2}
        self.assertEqual(canonical_json_bytes(left), canonical_json_bytes(right))
        self.assertEqual(content_sha256(left), content_sha256(right))
        self.assertRegex(content_sha256(left), r"^[0-9a-f]{64}$")

    def test_valid_analysis_references_only_bundle_evidence(self) -> None:
        self.assertEqual(self.analysis["evidence_bundle_id"], self.bundle["bundle_id"])
        for claim in claims(self.analysis):
            with self.subTest(text=claim["text"]):
                self.assertEqual(claim_violations(claim, self.evidence_by_id), set())

    def test_comparison_claim_is_machine_checkable(self) -> None:
        headline = self.analysis["headline"]
        comparison = headline["comparison"]
        left = self.evidence_by_id[comparison["left_evidence_id"]]
        right = self.evidence_by_id[comparison["right_evidence_id"]]
        self.assertEqual(left["unit"], right["unit"])
        self.assertGreater(left["value"], right["value"])

    def test_invalid_fixture_matrix_exercises_required_rejections(self) -> None:
        expected_categories = {
            "unknown_evidence_id",
            "unsupported_claim_type",
            "quoted_value_mismatch",
            "causal_language",
            "prohibited_field",
            "advice_language",
            "prompt_override_language",
        }
        observed: set[str] = set()
        for name, case in self.invalid_cases.items():
            expected = case["expected_violation"]
            violations = claim_violations(case["claim"], self.evidence_by_id)
            observed.add(expected)
            with self.subTest(case=name):
                self.assertIn(expected, violations)
        self.assertEqual(observed, expected_categories)

    def test_prompt_marks_source_payload_as_untrusted_and_denies_external_authority(self) -> None:
        text = PROMPT.read_text(encoding="utf-8")
        required = (
            "<BEGIN_UNTRUSTED_EVIDENCE_BUNDLE>",
            "<END_UNTRUSTED_EVIDENCE_BUNDLE>",
            "Return JSON only",
            "Do not fetch, recall, infer, or select external facts or sources",
            "Do not explain why a price or market moved",
            "Do not provide forecasts",
            "repository will independently validate",
        )
        for marker in required:
            with self.subTest(marker=marker):
                self.assertIn(marker, text)
        self.assertNotIn("OPENROUTER_API_KEY", text)
        self.assertNotIn("GITHUB_TOKEN", text)

    def test_provenance_fixture_records_identity_versions_hashes_usage_and_routing(self) -> None:
        required = {
            "requested_model",
            "actual_model",
            "actual_provider",
            "prompt_version",
            "analysis_schema_version",
            "evidence_schema_version",
            "source_snapshot",
            "evidence_bundle",
            "generation_parameters",
            "usage",
            "generation_id",
            "prompt_sha256",
            "completion_sha256",
            "routing",
            "estimated_cost_usd",
        }
        self.assertTrue(required <= set(self.provenance))
        self.assertFalse(self.provenance["routing"]["cross_model_fallback_used"])
        self.assertEqual(
            self.provenance["source_snapshot"]["path"],
            self.bundle["source_snapshot"]["path"],
        )
        self.assertEqual(
            self.provenance["evidence_bundle"]["bundle_id"],
            self.bundle["bundle_id"],
        )

    def test_contract_document_records_layered_validation_and_feedback_loop_boundary(self) -> None:
        text = CONTRACT.read_text(encoding="utf-8")
        for marker in (
            "Schema validity",
            "Referential validity",
            "Value consistency",
            "Permitted claim semantics",
            "Policy validity",
            "previous LLM analysis or generated narrative",
            "No OpenRouter API call is introduced",
            "No generated `_site/` output is committed",
        ):
            with self.subTest(marker=marker):
                self.assertIn(marker, text)


if __name__ == "__main__":
    unittest.main()
