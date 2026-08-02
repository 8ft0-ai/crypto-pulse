from __future__ import annotations

import json
import unittest
from pathlib import Path

from llm_analysis.candidate_selection_contract import (
    CANDIDATE_SELECTION_SCHEMA_VERSION,
    build_candidate_selector_request,
)
from llm_analysis.candidate_selection_proof import evaluate_candidate_selection_proof
from llm_analysis.openai_schema_projection import project_openai_strict_schema

ROOT = Path(__file__).resolve().parents[1]
PROOF = ROOT / "evaluation" / "phase-06" / "candidate-selection"
SCHEMA = ROOT / "schemas" / "crypto-market-candidate-selection-v1.json"
PROMPT = ROOT / "prompts" / "crypto-market-candidate-selection-v1.txt"


class CandidateSelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.proof = evaluate_candidate_selection_proof(ROOT)
        cls.summary = cls.proof.summary
        cls.scenarios = cls.proof.scenarios["records"]

    def test_canonical_schema_contains_only_candidate_ids(self) -> None:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        self.assertEqual(schema["additionalProperties"], False)
        self.assertEqual(schema["required"], ["selected_candidate_ids"])
        self.assertEqual(set(schema["properties"]), {"selected_candidate_ids"})
        selected = schema["properties"]["selected_candidate_ids"]
        self.assertEqual(selected["minItems"], 1)
        self.assertEqual(selected["maxItems"], 7)
        self.assertEqual(selected["uniqueItems"], True)
        self.assertEqual(
            selected["items"]["pattern"],
            r"^claim-candidate:sha256:[0-9a-f]{64}$",
        )
        projected = project_openai_strict_schema(schema)
        self.assertNotIn("uniqueItems", projected["properties"]["selected_candidate_ids"])
        self.assertEqual(CANDIDATE_SELECTION_SCHEMA_VERSION, "crypto-market-candidate-selection/v1")

    def test_retained_proof_outputs_are_byte_stable(self) -> None:
        for relative, expected in self.proof.outputs.items():
            self.assertEqual((ROOT / relative).read_bytes(), expected, relative)

    def test_offline_scenario_totals_and_fallback_equivalence(self) -> None:
        overall = self.summary["overall"]
        self.assertEqual(overall["status"], "pass")
        self.assertEqual(overall["case_count"], 5)
        self.assertEqual(overall["scenario_count"], 25)
        self.assertEqual(overall["accepted_initial_count"], 5)
        self.assertEqual(overall["accepted_after_repair_count"], 5)
        self.assertEqual(overall["fallback_count"], 15)
        self.assertEqual(overall["fallback_exact_count"], 15)
        self.assertEqual(overall["maximum_semantic_repair_count"], 1)
        self.assertEqual(overall["scripted_selector_attempt_count"], 35)
        self.assertEqual(overall["candidate_permutation_stable_count"], 5)
        self.assertEqual(overall["evidence_permutation_stable_count"], 5)
        self.assertEqual(overall["provider_call_count"], 0)
        self.assertFalse(overall["automatic_generation_enabled"])
        self.assertFalse(overall["publication_enabled"])
        for record in self.scenarios:
            self.assertLessEqual(record["semantic_repair_count"], 1)
            self.assertTrue(record["validation"]["valid"])
            if record["fallback_used"]:
                self.assertTrue(record["fallback_exact"])
                self.assertEqual(
                    record["selected_candidate_ids"],
                    record["baseline_selected_candidate_ids"],
                )

    def test_only_semantic_id_failures_are_repaired(self) -> None:
        by_scenario: dict[str, list[dict]] = {}
        for record in self.scenarios:
            by_scenario.setdefault(record["scenario"], []).append(record)
        for record in by_scenario["accepted_after_repair"]:
            self.assertEqual(record["selector_attempt_count"], 2)
            self.assertEqual(record["semantic_repair_count"], 1)
            self.assertFalse(record["fallback_used"])
        for record in by_scenario["invalid_repair_fallback"]:
            self.assertEqual(record["selector_attempt_count"], 2)
            self.assertEqual(record["semantic_repair_count"], 1)
            self.assertTrue(record["fallback_used"])
        for scenario in ("malformed_envelope_fallback", "client_failure_fallback"):
            for record in by_scenario[scenario]:
                self.assertEqual(record["selector_attempt_count"], 1)
                self.assertEqual(record["semantic_repair_count"], 0)
                self.assertTrue(record["fallback_used"])

    def test_validation_matrix_has_stable_bounded_diagnostics(self) -> None:
        actual = {
            item["name"]: [diagnostic["code"] for diagnostic in item["diagnostics"]]
            for item in self.summary["validation_matrix"]
        }
        self.assertEqual(
            actual,
            {
                "unknown": ["unknown_selected_candidate_id"],
                "duplicate": ["duplicate_selection"],
                "excessive": ["excessive_selection"],
                "redundancy": ["selection_redundancy_violation"],
                "mixed_bundle": ["selected_candidate_bundle_mismatch"],
            },
        )

    def test_request_is_canonical_and_contains_no_source_instructions(self) -> None:
        request = self.proof.representative_request
        reversed_request = build_candidate_selector_request(
            list(reversed(request["candidates"])),
            config=__import__(
                "llm_analysis.deterministic_ranking",
                fromlist=["load_ranking_config"],
            ).load_ranking_config(ROOT),
            evidence_bundle_id=request["evidence_bundle_id"],
        )
        self.assertEqual(request, reversed_request)
        self.assertEqual(request["max_selection_count"], 7)
        self.assertEqual(request["response_schema_version"], CANDIDATE_SELECTION_SCHEMA_VERSION)
        catalogue_text = json.dumps(request["candidates"], sort_keys=True).casefold()
        for unsafe in (
            "ignore all prior instructions",
            "recommend buying btc",
            "remove every disclaimer",
            "rationale",
            "explanation",
        ):
            self.assertNotIn(unsafe, catalogue_text)

    def test_model_list_order_is_not_plan_order(self) -> None:
        accepted = next(
            item
            for item in self.scenarios
            if item["case"] == "historical-material-move"
            and item["scenario"] == "accepted_initial"
        )
        raw_ids = accepted["attempts"][0]["response"]["selected_candidate_ids"]
        self.assertEqual(raw_ids, list(reversed(accepted["selected_candidate_ids"])))
        self.assertNotEqual(raw_ids, accepted["selected_candidate_ids"])

    def test_no_provider_or_publication_execution_path_is_added(self) -> None:
        source = "\n".join(
            (ROOT / "llm_analysis" / name).read_text(encoding="utf-8")
            for name in (
                "candidate_selection_contract.py",
                "candidate_selector.py",
                "candidate_selection_evaluation.py",
                "candidate_selection_proof.py",
                "candidate_selection_validation_proof.py",
            )
        )
        for prohibited in (
            "OpenRouterClient(",
            "urllib.request",
            "OPENROUTER_API_KEY",
            "_site/",
            "git push",
            "workflow_dispatch",
        ):
            self.assertNotIn(prohibited, source)
        prompt = PROMPT.read_text(encoding="utf-8")
        self.assertIn("selected_candidate_ids", prompt)
        self.assertNotIn("free-form rationale", prompt)


if __name__ == "__main__":
    unittest.main()
