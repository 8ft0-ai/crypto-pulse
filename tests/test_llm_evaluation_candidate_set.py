from __future__ import annotations

import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
EVALUATION_CONFIG = ROOT / "config" / "llm-evaluation.yml"
CANDIDATE_RECORD = ROOT / "evaluation" / "phase-05" / "free-proof-candidates.md"
HISTORICAL_DECISION = ROOT / "evaluation" / "phase-05" / "decision.yml"


class FinalFreeModelCandidateTests(unittest.TestCase):
    def test_exact_bounded_candidate_set_is_source_controlled(self) -> None:
        config = yaml.safe_load(EVALUATION_CONFIG.read_text(encoding="utf-8"))
        models = config["models"]

        self.assertEqual(len(models), 3)
        self.assertEqual(
            {item["model"] for item in models},
            {
                "nvidia/nemotron-nano-9b-v2:free",
                "openai/gpt-oss-20b:free",
                "cognitivecomputations/dolphin-mistral-24b-venice-edition:free",
            },
        )
        self.assertEqual(sum(item["role"] == "current_candidate" for item in models), 1)
        self.assertTrue(all(item["model"].endswith(":free") for item in models))
        self.assertTrue(all(not item["model"].startswith("openrouter/") for item in models))
        self.assertTrue(all(item["availability_checked_at"] == "2026-07-11" for item in models))

        by_key = {item["key"]: item for item in models}
        self.assertIsNone(by_key["nemotron-nano-9b-v2"]["known_expiration_date"])
        self.assertIsNone(by_key["gpt-oss-20b"]["known_expiration_date"])
        self.assertEqual(
            by_key["venice-dolphin-mistral-24b"]["known_expiration_date"],
            "2026-07-19",
        )

    def test_candidate_record_explains_qwen_exclusion_and_preserves_boundaries(self) -> None:
        text = CANDIDATE_RECORD.read_text(encoding="utf-8")

        for slug in (
            "nvidia/nemotron-nano-9b-v2:free",
            "openai/gpt-oss-20b:free",
            "cognitivecomputations/dolphin-mistral-24b-venice-edition:free",
        ):
            self.assertIn(slug, text)

        self.assertIn("qwen/qwen3-next-80b-a3b-instruct:free", text)
        self.assertIn("no longer reports zero prompt and completion prices", text)
        self.assertIn("ZDR:                         required", text)
        self.assertIn("cross-model fallback:        disabled", text)
        self.assertIn("paid calls:                  prohibited", text)
        self.assertIn("2026-07-11T07:14:28Z", text)

    def test_historical_no_go_remains_unchanged(self) -> None:
        decision = yaml.safe_load(HISTORICAL_DECISION.read_text(encoding="utf-8"))

        self.assertEqual(decision["status"], "no-go")
        self.assertEqual(decision["source_run"]["run_id"], 29142348720)
        self.assertIsNone(decision["results"]["selected_model"])
        self.assertTrue(decision["boundaries"]["zero_data_retention_required"])
        self.assertFalse(decision["boundaries"]["cross_model_fallback_enabled"])
        self.assertFalse(decision["boundaries"]["paid_model_approved"])


if __name__ == "__main__":
    unittest.main()
