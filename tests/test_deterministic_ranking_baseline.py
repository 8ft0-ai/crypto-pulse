from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

import yaml

from llm_analysis.claim_candidate_contract import derive_candidate_id
from llm_analysis.deterministic_baseline_record import (
    evaluate_deterministic_baseline_record,
)
from llm_analysis.deterministic_ranking import (
    DeterministicRankingError,
    load_ranking_config,
    reconstruct_claim_plan,
)

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "evaluation" / "phase-06" / "deterministic-baseline"
CONFIG = ROOT / "config" / "claim-candidate-ranking-v1.yml"
MATERIAL_OPPOSITE_ID = (
    "claim-candidate:sha256:"
    "7fba1f4e9aeb6531bda575f2f9aa6e517bafe5142fdb3f0bff3bb79ebc6c9238"
)


class DeterministicRankingBaselineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.record = evaluate_deterministic_baseline_record(ROOT)
        cls.summary = cls.record.summary
        cls.scores = cls.record.scores

    def test_retained_summary_scores_and_review_are_byte_stable(self) -> None:
        self.assertEqual(
            self.record.summary_bytes,
            (BASELINE / "summary.json").read_bytes(),
        )
        self.assertEqual(
            self.record.scores_bytes,
            (BASELINE / "scores.json").read_bytes(),
        )
        self.assertEqual(
            self.record.report_markdown,
            (BASELINE / "review.md").read_bytes(),
        )

    def test_baseline_is_bounded_valid_and_permutation_stable(self) -> None:
        overall = self.summary["overall"]
        self.assertEqual(overall["status"], "pass")
        self.assertEqual(overall["case_count"], 5)
        self.assertEqual(overall["rendered_case_count"], 5)
        self.assertEqual(overall["validated_plan_count"], 5)
        self.assertEqual(overall["candidate_permutation_stable_count"], 5)
        self.assertEqual(overall["evidence_permutation_stable_count"], 5)
        self.assertEqual(overall["provider_call_count"], 0)
        self.assertEqual(overall["selected_count"], 35)
        self.assertEqual(overall["selected_useful_count"], 26)
        self.assertAlmostEqual(overall["selected_useful_precision"], 26 / 35)
        self.assertAlmostEqual(overall["selected_useful_recall"], 26 / 38)

        for case in self.summary["cases"]:
            identifiers = case["selected_candidate_ids"]
            self.assertEqual(case["selected_count"], 7)
            self.assertEqual(len(identifiers), 7)
            self.assertEqual(len(set(identifiers)), 7)
            self.assertEqual(case["redundancy_group_count"], 7)
            self.assertTrue(case["validation"]["valid"])
            self.assertEqual(case["validation"]["diagnostics"], [])
            self.assertTrue(case["candidate_permutation_stable"])
            self.assertTrue(case["evidence_permutation_stable"])
            self.assertLessEqual(max(case["section_counts"].values()), 8)
            self.assertEqual(
                case["analysis_order"],
                ["market_summary", "key_observations", "data_quality"],
            )

    def test_score_record_is_complete_and_material_case_keeps_reviewed_signals(self) -> None:
        records = self.scores["records"]
        self.assertEqual(
            self.scores["version"],
            "phase-06-deterministic-baseline-scores/v1",
        )
        self.assertEqual(len(records), 35)
        pairs = {(item["case"], item["candidate_id"]) for item in records}
        self.assertEqual(len(pairs), 35)
        self.assertTrue(all(len(item["score_vector"]) == 11 for item in records))

        material = [
            item
            for item in records
            if item["case"] == "historical-material-move"
        ]
        opposite = [
            item for item in material if item["candidate_id"] == MATERIAL_OPPOSITE_ID
        ]
        self.assertEqual(len(opposite), 1)
        self.assertEqual(opposite[0]["gold_name"], "btc-eth-1h-opposite")
        self.assertTrue(
            any(item["gold_name"] == "eth-7d-direction" for item in material)
        )

    def test_reconstruction_copies_candidate_semantics_exactly(self) -> None:
        config = load_ranking_config(ROOT)
        candidate = {
            "candidate_version": "crypto-market-claim-candidate/v1",
            "candidate_id": "",
            "evidence_bundle_id": "sha256:" + "1" * 64,
            "intent": "comparison",
            "evidence_ids": [
                "market.asset.bitcoin.price_usd",
                "market.asset.ethereum.price_usd",
            ],
            "comparison_relation": "greater_than",
            "section": "key_observations",
            "subject": {"type": "market", "id": "cross-subject-comparison"},
            "metric": "price_usd",
            "confidence": "high",
            "features": {
                "materiality_bucket": "not_applicable",
                "cross_source": False,
                "conflict_status": "none",
                "recency_bucket": "unknown",
                "quality_significance": "not_applicable",
                "section_eligibility": ["key_observations"],
                "redundancy_group": "comparison_bitcoin_ethereum_price_usd",
                "corroboration_count": 1,
            },
        }
        candidate["candidate_id"] = derive_candidate_id(candidate)
        selection = {
            "evidence_bundle_id": candidate["evidence_bundle_id"],
            "selected_candidate_ids": [candidate["candidate_id"]],
        }

        plan = reconstruct_claim_plan(selection, [candidate], config=config)
        claim = plan["sections"][0]["claims"][0]
        self.assertEqual(claim["intent"], candidate["intent"])
        self.assertEqual(claim["evidence_ids"], candidate["evidence_ids"])
        self.assertEqual(
            claim["comparison_relation"],
            candidate["comparison_relation"],
        )
        self.assertEqual(claim["confidence"], candidate["confidence"])
        self.assertEqual(plan["analysis_order"], [candidate["section"]])
        self.assertEqual(
            set(claim),
            {
                "claim_id",
                "intent",
                "evidence_ids",
                "comparison_relation",
                "confidence",
            },
        )

    def test_unknown_duplicate_selection_and_unsafe_config_fail_closed(self) -> None:
        config = load_ranking_config(ROOT)
        unknown = "claim-candidate:sha256:" + "0" * 64
        with self.assertRaises(DeterministicRankingError) as raised:
            reconstruct_claim_plan(
                {
                    "evidence_bundle_id": "sha256:" + "1" * 64,
                    "selected_candidate_ids": [unknown],
                },
                [],
                config=config,
            )
        self.assertEqual(raised.exception.code, "unknown_selected_candidate_id")

        with self.assertRaises(DeterministicRankingError) as raised:
            reconstruct_claim_plan(
                {
                    "evidence_bundle_id": "sha256:" + "1" * 64,
                    "selected_candidate_ids": [unknown, unknown],
                },
                [],
                config=config,
            )
        self.assertEqual(raised.exception.code, "duplicate_selection")

        raw = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
        invalid = copy.deepcopy(raw)
        invalid["max_total"] = 41
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "config" / CONFIG.name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(yaml.safe_dump(invalid, sort_keys=False), encoding="utf-8")
            with self.assertRaises(DeterministicRankingError) as raised:
                load_ranking_config(temporary, f"config/{CONFIG.name}")
        self.assertEqual(raised.exception.code, "unsafe_bound")

    def test_baseline_contains_no_provider_or_publication_path(self) -> None:
        source = "\n".join(
            (ROOT / "llm_analysis" / name).read_text(encoding="utf-8")
            for name in (
                "deterministic_ranking.py",
                "deterministic_baseline_evaluation.py",
                "deterministic_baseline_record.py",
            )
        )
        for prohibited in (
            "OpenRouterClient",
            "urllib.request",
            "api_key",
            "semantic repair",
            "_site/",
        ):
            self.assertNotIn(prohibited, source)

        retained = (
            self.record.summary_bytes
            + self.record.scores_bytes
            + self.record.report_markdown
        ).decode("utf-8").casefold()
        for unsafe in (
            "ignore all prior instructions",
            "recommend buying btc",
            "remove every disclaimer",
        ):
            self.assertNotIn(unsafe, retained)


if __name__ == "__main__":
    unittest.main()
