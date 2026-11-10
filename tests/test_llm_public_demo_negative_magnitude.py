from __future__ import annotations

import unittest
from pathlib import Path

from llm_analysis.diagnostics import Diagnostic, ValidationReport
from llm_analysis.public_demo_negative_magnitude import (
    filter_negative_magnitude_diagnostics,
)


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "llm_analysis" / "public_demo_benchmark_projection.py"


def evidence(value: float) -> dict:
    return {
        "evidence_id": "market.asset.bitcoin.change_24h_pct",
        "evidence_type": "number",
        "field": "change_24h_pct",
        "unit": "percent",
        "source": {"name": "coingecko"},
        "subject": {
            "id": "bitcoin",
            "type": "asset",
            "name": "Bitcoin",
            "symbol": "BTC",
        },
        "value": value,
    }


def claim(
    text: str,
    *,
    claim_type: str = "absolute_observation",
    quoted_value: float = -0.54516,
    quoted_unit: str = "percent",
) -> dict:
    return {
        "claim_type": claim_type,
        "text": text,
        "evidence_ids": ["market.asset.bitcoin.change_24h_pct"],
        "confidence": "high",
        "quoted_values": [
            {
                "evidence_id": "market.asset.bitcoin.change_24h_pct",
                "value": quoted_value,
                "unit": quoted_unit,
            }
        ],
    }


def diagnostic(token: str) -> Diagnostic:
    return Diagnostic(
        "value",
        "untraceable_number",
        "$.analysis.key_observations[0].text",
        f"numeric token '{token}' is not traceable to referenced evidence",
    )


class PublicDemoNegativeMagnitudeTests(unittest.TestCase):
    def filter(self, item: dict, *, evidence_value: float = -0.54516, token: str = "0.54516"):
        bundle = {"evidence": [evidence(evidence_value)]}
        analysis = {"key_observations": [item]}
        return filter_negative_magnitude_diagnostics(
            ValidationReport((diagnostic(token),)), bundle, analysis
        )

    def test_exact_absolute_magnitude_passes_for_absolute_observation(self) -> None:
        report = self.filter(
            claim("Bitcoin (BTC) has decreased by 0.54516% over the last 24 hours.")
        )
        self.assertTrue(report.is_valid)

    def test_exact_absolute_magnitude_passes_for_directional_observation(self) -> None:
        report = self.filter(
            claim(
                "Bitcoin (BTC) has decreased by 0.54516% over the last 24 hours.",
                claim_type="directional_observation",
            )
        )
        self.assertTrue(report.is_valid)

    def test_rounded_magnitude_requires_approximation_wording(self) -> None:
        accepted = self.filter(
            claim("Bitcoin decreased by approximately 0.55% over 24 hours."),
            token="0.55",
        )
        rejected = self.filter(
            claim("Bitcoin decreased by 0.55% over 24 hours."),
            token="0.55",
        )
        self.assertTrue(accepted.is_valid)
        self.assertFalse(rejected.is_valid)

    def test_missing_negative_direction_remains_rejected(self) -> None:
        report = self.filter(claim("Bitcoin changed by 0.54516% over 24 hours."))
        self.assertFalse(report.is_valid)

    def test_incorrect_magnitude_remains_rejected(self) -> None:
        report = self.filter(
            claim("Bitcoin decreased by 0.54515% over 24 hours."),
            token="0.54515",
        )
        self.assertFalse(report.is_valid)

    def test_mismatched_quoted_value_or_unit_remains_rejected(self) -> None:
        wrong_value = self.filter(
            claim(
                "Bitcoin decreased by 0.54516% over 24 hours.",
                quoted_value=-0.5,
            )
        )
        wrong_unit = self.filter(
            claim(
                "Bitcoin decreased by 0.54516% over 24 hours.",
                quoted_unit="usd",
            )
        )
        self.assertFalse(wrong_value.is_valid)
        self.assertFalse(wrong_unit.is_valid)

    def test_positive_evidence_cannot_use_negative_magnitude_exception(self) -> None:
        item = claim(
            "Bitcoin decreased by 0.54516% over 24 hours.",
            quoted_value=0.54516,
        )
        report = self.filter(item, evidence_value=0.54516)
        self.assertFalse(report.is_valid)

    def test_non_numeric_diagnostic_is_unchanged(self) -> None:
        bundle = {"evidence": [evidence(-0.54516)]}
        analysis = {
            "key_observations": [
                claim("Bitcoin decreased by 0.54516% over 24 hours.")
            ]
        }
        entity = Diagnostic(
            "value",
            "untraceable_entity",
            "$.analysis.key_observations[0].text",
            "named token 'Unknown' is absent from the evidence bundle",
        )
        report = filter_negative_magnitude_diagnostics(
            ValidationReport((entity,)), bundle, analysis
        )
        self.assertEqual(report.diagnostics, (entity,))

    def test_protected_runner_uses_the_isolated_adapter(self) -> None:
        text = RUNNER.read_text(encoding="utf-8")
        self.assertIn("process_public_demo_analysis_with_negative_magnitude", text)
        self.assertIn("OpenAICompatibleSchemaClient", text)
        self.assertIn("evaluation_execution.process_analysis", text)


if __name__ == "__main__":
    unittest.main()
