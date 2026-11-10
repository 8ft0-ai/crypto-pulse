from __future__ import annotations

import unittest
from pathlib import Path

from llm_analysis.diagnostics import Diagnostic, ValidationReport
from llm_analysis.public_demo_validation import filter_public_demo_diagnostics

ROOT = Path(__file__).resolve().parents[1]
PROMPT = ROOT / "prompts" / "crypto-market-analysis-v1.md"
RUNNER = ROOT / "llm_analysis" / "public_demo_benchmark_projection.py"


def evidence(
    evidence_id: str,
    value,
    *,
    unit: str | None = None,
    subject_name: str | None = None,
    source_name: str = "coingecko",
    observed_at: str | None = None,
):
    item = {
        "evidence_id": evidence_id,
        "evidence_type": "number",
        "field": evidence_id.rsplit(".", 1)[-1],
        "source": {"name": source_name},
        "subject": {"id": evidence_id.split(".")[0], "type": "asset"},
        "value": value,
    }
    if unit is not None:
        item["unit"] = unit
    if subject_name is not None:
        item["subject"]["name"] = subject_name
    if observed_at is not None:
        item["observed_at"] = observed_at
    return item


def quoted(evidence_id: str, value, unit: str):
    return {"evidence_id": evidence_id, "value": value, "unit": unit}


class PublicDemoGroundedTextTests(unittest.TestCase):
    def setUp(self) -> None:
        self.bundle = {
            "evidence": [
                evidence(
                    "bitcoin.price",
                    62739,
                    unit="usd",
                    subject_name="Bitcoin",
                    observed_at="2026-07-08T07:41:15.609Z",
                ),
                evidence(
                    "bitcoin.change_1h_pct",
                    0.3958877430642739,
                    unit="percent",
                    subject_name="Bitcoin",
                    observed_at="2026-07-08T07:41:15.609Z",
                ),
                evidence(
                    "bitcoin.change_24h_pct",
                    -0.54516,
                    unit="percent",
                    subject_name="Bitcoin",
                    observed_at="2026-07-08T07:41:15.609Z",
                ),
                evidence(
                    "stablecoin.tether.circulating_usd",
                    182984655114.5454,
                    unit="usd",
                    subject_name="Tether",
                    source_name="defillama",
                ),
                evidence(
                    "exchange.coinbase.price",
                    62738.02,
                    unit="usd",
                    subject_name="Bitcoin",
                    source_name="coinbase_exchange",
                    observed_at="2026-07-08T07:42:07Z",
                ),
            ]
        }
        self.analysis = {
            "headline": {
                "claim_type": "absolute_observation",
                "text": "As of 2026-07-08, Bitcoin was $62,739.",
                "evidence_ids": ["bitcoin.price"],
                "quoted_values": [quoted("bitcoin.price", 62739, "usd")],
            },
            "key_observations": [
                {
                    "claim_type": "directional_observation",
                    "text": "In the last hour, Bitcoin increased by approximately 0.40%.",
                    "evidence_ids": ["bitcoin.change_1h_pct"],
                    "quoted_values": [quoted("bitcoin.change_1h_pct", 0.3958877430642739, "percent")],
                },
                {
                    "claim_type": "directional_observation",
                    "text": "Over 24 hours, Bitcoin decreased by approximately 0.55%.",
                    "evidence_ids": ["bitcoin.change_24h_pct"],
                    "quoted_values": [quoted("bitcoin.change_24h_pct", -0.54516, "percent")],
                },
            ],
            "market_summary": [
                {
                    "claim_type": "absolute_observation",
                    "text": "Tether circulation was approximately $182,984,655,114.55.",
                    "evidence_ids": ["stablecoin.tether.circulating_usd"],
                    "quoted_values": [quoted("stablecoin.tether.circulating_usd", 182984655114.5454, "usd")],
                }
            ],
            "data_quality_notes": [
                {
                    "claim_type": "data_quality_limitation",
                    "text": "Several sources were unavailable.",
                    "evidence_ids": ["bitcoin.price"],
                }
            ],
            "source_evidence_note": {
                "claim_type": "source_disagreement",
                "text": "Coinbase Exchange reported a different Bitcoin price.",
                "evidence_ids": ["exchange.coinbase.price", "bitcoin.price"],
            },
        }

    def test_actual_smoke_false_positive_pattern_leaves_only_semantic_error(self) -> None:
        report = ValidationReport(
            (
                Diagnostic("value", "untraceable_entity", "$.analysis.data_quality_notes[0].text", "named token 'Several' is absent from the evidence bundle"),
                Diagnostic("value", "untraceable_entity", "$.analysis.headline.text", "named token 'As' is absent from the evidence bundle"),
                Diagnostic("value", "untraceable_number", "$.analysis.headline.text", "numeric token '08,' is not traceable to referenced evidence"),
                Diagnostic("value", "untraceable_entity", "$.analysis.key_observations[0].text", "named token 'In' is absent from the evidence bundle"),
                Diagnostic("value", "untraceable_number", "$.analysis.key_observations[0].text", "numeric token '0.40' is not traceable to referenced evidence"),
                Diagnostic("value", "untraceable_entity", "$.analysis.key_observations[1].text", "named token 'Over' is absent from the evidence bundle"),
                Diagnostic("value", "untraceable_number", "$.analysis.key_observations[1].text", "numeric token '0.55' is not traceable to referenced evidence"),
                Diagnostic("value", "untraceable_number", "$.analysis.market_summary[0].text", "numeric token '182,984,655,114.55' is not traceable to referenced evidence"),
                Diagnostic("value", "entity_mismatch", "$.analysis.source_evidence_note.text", "named entity 'coinbase exchange' is not supported by this claim's evidence references"),
                Diagnostic("semantic", "invalid_source_disagreement", "$.analysis.source_evidence_note", "source disagreement must compare the same measurement from different sources"),
            )
        )

        filtered = filter_public_demo_diagnostics(report, self.bundle, self.analysis)

        self.assertEqual(
            [(item.stage, item.code) for item in filtered.diagnostics],
            [("semantic", "invalid_source_disagreement")],
        )

    def test_rounding_requires_exact_quoted_evidence_and_approximation_wording(self) -> None:
        diagnostic = Diagnostic("value", "untraceable_number", "$.analysis.key_observations[0].text", "numeric token '0.40' is not traceable to referenced evidence")

        no_quote = dict(self.analysis)
        no_quote["key_observations"] = [dict(self.analysis["key_observations"][0], quoted_values=[])]
        self.assertEqual(len(filter_public_demo_diagnostics(ValidationReport((diagnostic,)), self.bundle, no_quote).diagnostics), 1)

        no_approx = dict(self.analysis)
        no_approx["key_observations"] = [dict(self.analysis["key_observations"][0], text="Bitcoin increased by 0.40%.")]
        self.assertEqual(len(filter_public_demo_diagnostics(ValidationReport((diagnostic,)), self.bundle, no_approx).diagnostics), 1)

    def test_negative_magnitude_requires_explicit_direction(self) -> None:
        diagnostic = Diagnostic("value", "untraceable_number", "$.analysis.key_observations[1].text", "numeric token '0.55' is not traceable to referenced evidence")
        changed = dict(self.analysis)
        changed["key_observations"] = [
            self.analysis["key_observations"][0],
            dict(self.analysis["key_observations"][1], text="Bitcoin changed by approximately 0.55%."),
        ]
        self.assertEqual(len(filter_public_demo_diagnostics(ValidationReport((diagnostic,)), self.bundle, changed).diagnostics), 1)

    def test_unrelated_date_and_unknown_mid_sentence_entity_still_fail(self) -> None:
        date_diagnostic = Diagnostic("value", "untraceable_number", "$.analysis.headline.text", "numeric token '09,' is not traceable to referenced evidence")
        entity_diagnostic = Diagnostic("value", "untraceable_entity", "$.analysis.headline.text", "named token 'Tesla' is absent from the evidence bundle")
        changed = dict(self.analysis)
        changed["headline"] = dict(self.analysis["headline"], text="As of 2026-07-09, Bitcoin outpaced Tesla.")
        filtered = filter_public_demo_diagnostics(ValidationReport((date_diagnostic, entity_diagnostic)), self.bundle, changed)
        self.assertEqual({item.code for item in filtered.diagnostics}, {"untraceable_number", "untraceable_entity"})

    def test_prompt_and_runner_record_the_bounded_contract(self) -> None:
        prompt = PROMPT.read_text(encoding="utf-8")
        runner = RUNNER.read_text(encoding="utf-8")
        self.assertIn("same subject ID, field, and unit but different source names", prompt)
        self.assertIn("ordinary decimal rounding", prompt)
        self.assertIn("process_public_demo_analysis", runner)
        self.assertIn("evaluation_execution.process_analysis", runner)


if __name__ == "__main__":
    unittest.main()
