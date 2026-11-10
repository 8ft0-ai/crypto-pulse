from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path

from llm_analysis.diagnostics import Diagnostic, ValidationReport
from llm_analysis.openai_schema_projection import (
    project_openai_strict_schema,
    source_disagreement_supported,
)
from llm_analysis.public_demo_validation import filter_public_demo_diagnostics


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "crypto-market-analysis-v1.json"
PROMPT_PATH = ROOT / "prompts" / "crypto-market-analysis-v1.md"


def numeric(
    evidence_id: str,
    *,
    subject_id: str,
    field: str,
    unit: str,
    source: str,
    symbol: str | None = None,
    name: str | None = None,
) -> dict:
    subject = {"id": subject_id, "type": "asset"}
    if symbol is not None:
        subject["symbol"] = symbol
    if name is not None:
        subject["name"] = name
    return {
        "evidence_id": evidence_id,
        "evidence_type": "number",
        "field": field,
        "source": {"name": source},
        "subject": subject,
        "unit": unit,
        "value": 1,
    }


def claim(text: str) -> dict:
    return {
        "claim_type": "data_quality_limitation",
        "text": text,
        "evidence_ids": ["source.coinbase_exchange.covered_symbols"],
        "confidence": "high",
    }


class EvidenceAwareProviderSchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.canonical = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    def claim_types(self, bundle: dict) -> list[str]:
        projected = project_openai_strict_schema(
            self.canonical,
            evidence_bundle=bundle,
        )
        return projected["$defs"]["claim"]["properties"]["claim_type"]["enum"]

    def test_source_disagreement_is_removed_without_an_eligible_pair(self) -> None:
        bundle = {
            "evidence": [
                numeric(
                    "market.bitcoin.price",
                    subject_id="bitcoin",
                    field="price_usd",
                    unit="usd",
                    source="coingecko",
                ),
                numeric(
                    "exchange.btc-usd.price",
                    subject_id="btc-usd",
                    field="price",
                    unit="usd",
                    source="coinbase_exchange",
                ),
            ]
        }

        self.assertFalse(source_disagreement_supported(bundle))
        self.assertNotIn("source_disagreement", self.claim_types(bundle))
        self.assertIn("comparison", self.claim_types(bundle))

    def test_source_disagreement_is_retained_for_same_measure_different_sources(self) -> None:
        bundle = {
            "evidence": [
                numeric(
                    "market.bitcoin.price.coingecko",
                    subject_id="bitcoin",
                    field="price_usd",
                    unit="usd",
                    source="coingecko",
                ),
                numeric(
                    "market.bitcoin.price.coinbase",
                    subject_id="bitcoin",
                    field="price_usd",
                    unit="usd",
                    source="coinbase_exchange",
                ),
            ]
        }

        self.assertTrue(source_disagreement_supported(bundle))
        self.assertIn("source_disagreement", self.claim_types(bundle))

    def test_evidence_aware_projection_does_not_mutate_canonical_schema(self) -> None:
        original = deepcopy(self.canonical)
        project_openai_strict_schema(
            self.canonical,
            evidence_bundle={"evidence": []},
        )
        self.assertEqual(self.canonical, original)
        self.assertEqual(json.loads(SCHEMA_PATH.read_text(encoding="utf-8")), original)


class SetMemberAliasTests(unittest.TestCase):
    def bundle(self, *, ambiguous_btc: bool = False) -> dict:
        evidence = [
            {
                "evidence_id": "source.coinbase_exchange.covered_symbols",
                "evidence_type": "set",
                "field": "covered_symbols",
                "source": {"name": "source-snapshot"},
                "subject": {
                    "id": "coinbase_exchange",
                    "name": "Coinbase Exchange",
                    "type": "source",
                },
                "value": ["BTC", "ETH", "SOL"],
            },
            numeric(
                "market.bitcoin.price",
                subject_id="bitcoin",
                field="price_usd",
                unit="usd",
                source="coingecko",
                symbol="BTC",
                name="Bitcoin",
            ),
            numeric(
                "market.ethereum.price",
                subject_id="ethereum",
                field="price_usd",
                unit="usd",
                source="coingecko",
                symbol="ETH",
                name="Ethereum",
            ),
            numeric(
                "market.solana.price",
                subject_id="solana",
                field="price_usd",
                unit="usd",
                source="coingecko",
                symbol="SOL",
                name="Solana",
            ),
        ]
        if ambiguous_btc:
            evidence.append(
                numeric(
                    "market.wrapped-bitcoin.price",
                    subject_id="wrapped-bitcoin",
                    field="price_usd",
                    unit="usd",
                    source="coingecko",
                    symbol="BTC",
                    name="Wrapped Bitcoin",
                )
            )
        return {"evidence": evidence}

    def analysis(self, text: str) -> dict:
        return {"risks_and_limitations": [claim(text)]}

    def diagnostic(self, token: str) -> Diagnostic:
        return Diagnostic(
            "value",
            "entity_mismatch",
            "$.analysis.risks_and_limitations[0].text",
            f"named entity '{token}' is not supported by this claim's evidence references",
        )

    def test_exact_set_members_and_unique_bundle_names_are_supported(self) -> None:
        tokens = ("bitcoin", "btc", "ethereum", "eth", "solana", "sol")
        report = ValidationReport(tuple(self.diagnostic(token) for token in tokens))
        analysis = self.analysis(
            "The cited coverage set includes Bitcoin (BTC), Ethereum (ETH), and Solana (SOL)."
        )
        original = deepcopy(analysis)

        filtered = filter_public_demo_diagnostics(report, self.bundle(), analysis)

        self.assertTrue(filtered.is_valid)
        self.assertEqual(analysis, original)

    def test_unrelated_alias_remains_rejected(self) -> None:
        report = ValidationReport((self.diagnostic("dogecoin"),))
        filtered = filter_public_demo_diagnostics(
            report,
            self.bundle(),
            self.analysis("The cited coverage set includes Dogecoin."),
        )
        self.assertEqual([item.code for item in filtered.diagnostics], ["entity_mismatch"])

    def test_ambiguous_symbol_name_mapping_rejects_name_but_keeps_exact_symbol(self) -> None:
        report = ValidationReport(
            (
                self.diagnostic("bitcoin"),
                self.diagnostic("btc"),
            )
        )
        filtered = filter_public_demo_diagnostics(
            report,
            self.bundle(ambiguous_btc=True),
            self.analysis("The cited coverage set includes Bitcoin (BTC)."),
        )
        self.assertEqual(
            [(item.code, item.message) for item in filtered.diagnostics],
            [
                (
                    "entity_mismatch",
                    "named entity 'bitcoin' is not supported by this claim's evidence references",
                )
            ],
        )

    def test_prompt_records_provider_claim_type_and_set_alias_boundaries(self) -> None:
        prompt = PROMPT_PATH.read_text(encoding="utf-8")
        self.assertIn("claim_type` allowed by the provider schema", prompt)
        self.assertIn("Provider-allowed claim types are authoritative", prompt)
        self.assertIn("cited set-valued record may repeat its exact set members", prompt)
        self.assertIn("maps to exactly one subject name", prompt)


if __name__ == "__main__":
    unittest.main()
