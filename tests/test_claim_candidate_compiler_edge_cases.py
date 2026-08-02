from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path
from typing import Any

from llm_analysis.claim_candidate_compiler import (
    ClaimCandidateCompilationError,
    compile_claim_candidates,
)

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "schemas"
FIXTURES = ROOT / "tests" / "fixtures" / "llm_analysis"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


class ClaimCandidateCompilerEdgeCaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.evidence_schema = load_json(SCHEMAS / "crypto-market-evidence-bundle-v1.json")
        cls.candidate_schema = load_json(SCHEMAS / "crypto-market-claim-candidate-v1.json")
        cls.bundle = load_json(FIXTURES / "evidence_bundle_valid.json")

    def compile(self, bundle: dict[str, Any]) -> tuple[dict[str, Any], ...]:
        return compile_claim_candidates(
            bundle,
            evidence_schema=self.evidence_schema,
            candidate_schema=self.candidate_schema,
        )

    def test_fractional_rank_and_wrong_unit_direction_are_not_misclassified(self) -> None:
        bundle = copy.deepcopy(self.bundle)
        bundle["evidence"].extend(
            [
                {
                    "evidence_id": "market.asset.bitcoin.market_cap_rank",
                    "evidence_type": "number",
                    "subject": {
                        "type": "asset",
                        "id": "bitcoin",
                        "symbol": "BTC",
                        "name": "Bitcoin",
                    },
                    "field": "market_cap_rank",
                    "value": 1.5,
                    "unit": "rank",
                    "source": {
                        "name": "coingecko",
                        "source_path": "/test/market_cap_rank",
                    },
                },
                {
                    "evidence_id": "market.asset.cardano.change_24h_pct",
                    "evidence_type": "number",
                    "subject": {
                        "type": "asset",
                        "id": "cardano",
                        "symbol": "ADA",
                        "name": "Cardano",
                    },
                    "field": "change_24h_pct",
                    "value": 2.0,
                    "unit": "usd",
                    "source": {
                        "name": "coingecko",
                        "source_path": "/test/change_24h_pct",
                    },
                },
            ]
        )
        candidates = self.compile(bundle)
        rank_id = "market.asset.bitcoin.market_cap_rank"
        wrong_unit_id = "market.asset.cardano.change_24h_pct"
        self.assertFalse(any(rank_id in candidate["evidence_ids"] for candidate in candidates))
        self.assertTrue(
            any(
                candidate["intent"] == "absolute_observation"
                and candidate["evidence_ids"] == [wrong_unit_id]
                for candidate in candidates
            )
        )
        self.assertFalse(
            any(
                candidate["intent"] == "directional_observation"
                and wrong_unit_id in candidate["evidence_ids"]
                for candidate in candidates
            )
        )

    def test_non_string_warning_does_not_become_a_limitation(self) -> None:
        bundle = copy.deepcopy(self.bundle)
        warning_id = "quality.snapshot.warning"
        bundle["evidence"].append(
            {
                "evidence_id": warning_id,
                "evidence_type": "boolean",
                "subject": {"type": "snapshot", "id": "1742-aest"},
                "field": "warning",
                "value": True,
                "source": {
                    "name": "snapshot-validator",
                    "source_path": "/quality/warning",
                },
            }
        )
        candidates = self.compile(bundle)
        self.assertFalse(
            any(
                candidate["intent"] == "data_quality_limitation"
                and warning_id in candidate["evidence_ids"]
                for candidate in candidates
            )
        )

    def test_unrenderable_source_and_snapshot_status_fail_closed(self) -> None:
        source_bundle = copy.deepcopy(self.bundle)
        next(
            record
            for record in source_bundle["evidence"]
            if record["evidence_id"] == "source.coingecko.status"
        )["value"] = "not ready"
        with self.assertRaises(ClaimCandidateCompilationError) as caught:
            self.compile(source_bundle)
        self.assertEqual(caught.exception.code, "unsupported_source_status")

        snapshot_bundle = copy.deepcopy(self.bundle)
        next(
            record
            for record in snapshot_bundle["evidence"]
            if record["evidence_id"] == "quality.snapshot.status"
        )["value"] = "not ready"
        with self.assertRaises(ClaimCandidateCompilationError) as caught:
            self.compile(snapshot_bundle)
        self.assertEqual(caught.exception.code, "unsupported_snapshot_status")

    def test_broad_subject_projection_is_stable_and_collision_resistant(self) -> None:
        bundle = copy.deepcopy(self.bundle)
        for index, raw_id in enumerate(("17 A", "17-A"), start=1):
            bundle["evidence"].append(
                {
                    "evidence_id": f"quality.snapshot.extra_{index}.status",
                    "evidence_type": "status",
                    "subject": {"type": "snapshot", "id": raw_id},
                    "field": "status",
                    "value": "valid-ok",
                    "source": {
                        "name": "snapshot-validator",
                        "source_path": f"/quality/extra_{index}/status",
                    },
                }
            )
        candidates = self.compile(bundle)
        projected = [
            candidate["subject"]["id"]
            for candidate in candidates
            if candidate["intent"] == "snapshot_status"
            and candidate["evidence_ids"][0].startswith("quality.snapshot.extra_")
        ]
        self.assertEqual(len(projected), 2)
        self.assertEqual(len(set(projected)), 2)
        self.assertTrue(all(value.startswith("snapshot_17_a_") for value in projected))
        self.assertEqual(projected, [
            candidate["subject"]["id"]
            for candidate in self.compile(copy.deepcopy(bundle))
            if candidate["intent"] == "snapshot_status"
            and candidate["evidence_ids"][0].startswith("quality.snapshot.extra_")
        ])


if __name__ == "__main__":
    unittest.main()
