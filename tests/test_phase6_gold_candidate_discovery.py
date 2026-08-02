from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from llm_analysis.claim_candidate_compiler import compile_claim_candidates
from llm_analysis.contracts import canonical_json_bytes, content_sha256
from llm_analysis.evaluation import prepare_evaluation

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "schemas"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def rehash_bundle(bundle: dict[str, Any]) -> None:
    payload = {key: value for key, value in bundle.items() if key != "bundle_id"}
    bundle["bundle_id"] = f"sha256:{content_sha256(payload)}"


def signature(candidate: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_id": candidate["candidate_id"],
        "evidence_bundle_id": candidate["evidence_bundle_id"],
        "intent": candidate["intent"],
        "section": candidate["section"],
        "subject": candidate["subject"],
        "metric": candidate["metric"],
        "comparison_relation": candidate["comparison_relation"],
        "evidence_ids": candidate["evidence_ids"],
        "features": candidate["features"],
    }


class Phase6GoldCandidateDiscovery(unittest.TestCase):
    def test_emit_inventory_for_review(self) -> None:
        evidence_schema = load_json(SCHEMAS / "crypto-market-evidence-bundle-v1.json")
        candidate_schema = load_json(SCHEMAS / "crypto-market-claim-candidate-v1.json")
        inventory: dict[str, Any] = {
            "version": "phase-06-gold-candidate-discovery/v2",
            "trusted_main": "4df11666d6c35c13263f08b6dd3c74ef6068098f",
            "cases": [],
            "normalisation_probe": None,
        }
        prepared_bundles: dict[str, dict[str, Any]] = {}
        with tempfile.TemporaryDirectory() as temp:
            _, prepared = prepare_evaluation(
                repository_root=ROOT,
                config_path="config/llm-evaluation.yml",
                output_dir=temp,
            )
            for case in prepared:
                bundle = load_json(Path(temp) / case.bundle_file)
                prepared_bundles[case.key] = bundle
                candidates = list(
                    compile_claim_candidates(
                        bundle,
                        evidence_schema=evidence_schema,
                        candidate_schema=candidate_schema,
                    )
                )
                inventory["cases"].append(
                    {
                        "key": case.key,
                        "scenario_tags": list(case.scenario_tags),
                        "mutation": case.mutation,
                        "bundle_id": case.bundle_id,
                        "candidate_count": len(candidates),
                        "ordered_candidate_sha256": content_sha256(candidates),
                    }
                )

            source = prepared_bundles["adversarial-source-disagreement"]
            normalised = copy.deepcopy(source)
            market = next(
                item
                for item in normalised["evidence"]
                if item["evidence_id"] == "market.asset.bitcoin.price_usd"
            )
            exchange = next(
                item
                for item in normalised["evidence"]
                if item["evidence_id"] == "exchange.coinbase_exchange.btc-usd.price"
            )
            previous_bundle_id = normalised["bundle_id"]
            exchange["evidence_id"] = "exchange.coinbase_exchange.bitcoin.price_usd"
            exchange["subject"] = copy.deepcopy(market["subject"])
            exchange["field"] = "price_usd"
            rehash_bundle(normalised)
            candidates = list(
                compile_claim_candidates(
                    normalised,
                    evidence_schema=evidence_schema,
                    candidate_schema=candidate_schema,
                )
            )
            expected_ids = [
                "exchange.coinbase_exchange.bitcoin.price_usd",
                "market.asset.bitcoin.price_usd",
            ]
            matches = [
                candidate
                for candidate in candidates
                if candidate["intent"] == "comparison"
                and candidate["evidence_ids"] == expected_ids
            ]
            inventory["normalisation_probe"] = {
                "classification": "evaluation-only",
                "source_case": "adversarial-source-disagreement",
                "previous_bundle_id": previous_bundle_id,
                "normalised_bundle_id": normalised["bundle_id"],
                "candidate_count": len(candidates),
                "ordered_candidate_sha256": content_sha256(candidates),
                "comparison_matches": [signature(candidate) for candidate in matches],
            }

        print("PHASE6_GOLD_DISCOVERY_BEGIN")
        print(canonical_json_bytes(inventory).decode("utf-8"))
        print("PHASE6_GOLD_DISCOVERY_END")
        self.fail("intentional discovery run; replace with reviewed gold-corpus tests")
