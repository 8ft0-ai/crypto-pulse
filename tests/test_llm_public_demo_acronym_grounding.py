from __future__ import annotations

import unittest
from pathlib import Path

from llm_analysis.diagnostics import Diagnostic, ValidationReport
from llm_analysis.public_demo_validation import (
    SENTENCE_OPENERS,
    filter_public_demo_diagnostics,
)


ROOT = Path(__file__).resolve().parents[1]
PROMPT = ROOT / "prompts" / "crypto-market-analysis-v1.md"


class PublicDemoAcronymGroundingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.bundle = {
            "evidence": [
                {
                    "evidence_id": "source.binance.status",
                    "evidence_type": "status",
                    "field": "status",
                    "source": {"name": "source-snapshot"},
                    "subject": {"id": "binance", "name": "Binance", "type": "source"},
                    "value": "skipped",
                },
                {
                    "evidence_id": "defi.market.total_tvl_usd",
                    "evidence_type": "number",
                    "field": "total_tvl_usd",
                    "source": {"name": "defillama"},
                    "subject": {
                        "id": "total-tvl",
                        "name": "Total DeFi TVL",
                        "type": "defi_metric",
                    },
                    "unit": "usd",
                    "value": 135161325877,
                },
            ]
        }
        self.analysis = {
            "data_quality_notes": [
                {
                    "claim_type": "data_quality_limitation",
                    "text": "Multiple sources reported skipped status.",
                    "evidence_ids": ["source.binance.status"],
                }
            ],
            "key_observations": [
                {
                    "claim_type": "absolute_observation",
                    "text": "The total DeFi TVL (Total Value Locked) is 135161325877 USD.",
                    "evidence_ids": ["defi.market.total_tvl_usd"],
                    "quoted_values": [
                        {
                            "evidence_id": "defi.market.total_tvl_usd",
                            "value": 135161325877,
                            "unit": "usd",
                        }
                    ],
                }
            ],
        }

    def test_retained_smoke_pattern_removes_only_sentence_opening_multiple(self) -> None:
        report = ValidationReport(
            (
                Diagnostic(
                    "value",
                    "untraceable_entity",
                    "$.analysis.data_quality_notes[0].text",
                    "named token 'Multiple' is absent from the evidence bundle",
                ),
                Diagnostic(
                    "value",
                    "untraceable_entity",
                    "$.analysis.key_observations[0].text",
                    "named token 'Value' is absent from the evidence bundle",
                ),
                Diagnostic(
                    "value",
                    "untraceable_entity",
                    "$.analysis.key_observations[0].text",
                    "named token 'Locked' is absent from the evidence bundle",
                ),
            )
        )

        filtered = filter_public_demo_diagnostics(report, self.bundle, self.analysis)

        self.assertEqual(
            [item.message for item in filtered.diagnostics],
            [
                "named token 'Locked' is absent from the evidence bundle",
                "named token 'Value' is absent from the evidence bundle",
            ],
        )

    def test_multiple_is_safe_only_at_a_sentence_boundary(self) -> None:
        changed = dict(self.analysis)
        changed["data_quality_notes"] = [
            dict(
                self.analysis["data_quality_notes"][0],
                text="The sources labelled Multiple entries as skipped.",
            )
        ]
        diagnostic = Diagnostic(
            "value",
            "untraceable_entity",
            "$.analysis.data_quality_notes[0].text",
            "named token 'Multiple' is absent from the evidence bundle",
        )

        filtered = filter_public_demo_diagnostics(
            ValidationReport((diagnostic,)), self.bundle, changed
        )

        self.assertEqual(filtered.diagnostics, (diagnostic,))

    def test_finance_terms_are_not_added_to_sentence_opener_allowlist(self) -> None:
        self.assertIn("multiple", SENTENCE_OPENERS)
        self.assertNotIn("value", SENTENCE_OPENERS)
        self.assertNotIn("locked", SENTENCE_OPENERS)

    def test_prompt_prohibits_unsupported_acronym_expansion(self) -> None:
        prompt = PROMPT.read_text(encoding="utf-8")
        self.assertIn("Do not expand, define, or reinterpret an acronym", prompt)
        self.assertIn("keep `Total DeFi TVL` as `Total DeFi TVL`", prompt)
        self.assertIn("do not write `Total Value Locked`", prompt)


if __name__ == "__main__":
    unittest.main()
