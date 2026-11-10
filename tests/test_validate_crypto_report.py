from __future__ import annotations

import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_crypto_report import ReportValidationError, validate_report

FIXTURES = ROOT / "tests" / "fixtures"


VALID_REPORT_TEMPLATE = """---
schema_version: "deterministic-crypto-report/v1"
report_type: "crypto_market_snapshot"
source_snapshot: "tests/fixtures/valid_ok_snapshot.json"
generated_at_utc: "2026-07-08T04:34:52Z"
generated_at_local: "2026-07-08T14:34:52+10:00"
timezone: "Australia/Sydney"
cadence: "hourly"
quality_status: "valid-ok"
required_sources:
  - "coingecko"
  - "defillama"
optional_exchange_sources:
  - "coinbase_exchange"
selected_exchange_crosscheck: "coinbase_exchange"
no_investment_advice: true
llm_generated: false
---
# Crypto market evidence snapshot — 8 July 2026, 14:34 AEST

## Product boundary and non-investment-advice notice

This report is deterministic demonstration content generated from one validated source snapshot. It is not financial advice, investment research, a recommendation, a trading signal, or a call to buy, sell, or hold any asset.

## Snapshot quality

Status: `valid-ok`

## Market summary

| Asset | Price USD |
| --- | ---: |
| BTC | 60,000.00 |

This section records the validated snapshot values only. It does not infer entry points, exit points, targets, or trade direction.

## DeFi and stablecoin summary

Total DeFi TVL: USD 100,000,000,000.

## Exchange cross-check summary

Selected exchange cross-check: `coinbase_exchange`

## Evidence and source status

Source snapshot: `tests/fixtures/valid_ok_snapshot.json`

| Source | Status | Fetched at | Notes |
| --- | --- | --- | --- |
| coingecko | ok | 2026-07-08T04:34:52Z |  |
| defillama | ok | 2026-07-08T04:34:52Z |  |

## Scope limitations

- This report is generated from one validated source snapshot.
- This report made no LLM calls and used no hidden enrichment.
- This report is not financial advice, investment research, a recommendation, a trading signal, or a call to buy, sell, or hold any asset.
"""


class DeterministicCryptoReportValidationTests(unittest.TestCase):
    def write_report(self, body: str, root: Path) -> Path:
        report_path = root / "reports" / "crypto" / "hourly" / "sample.md"
        report_path.parent.mkdir(parents=True)
        report_path.write_text(textwrap.dedent(body).lstrip(), encoding="utf-8")
        return report_path

    def assert_report_rejected(self, body: str, expected_message: str) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixtures = root / "tests" / "fixtures"
            fixtures.mkdir(parents=True)
            (fixtures / "valid_ok_snapshot.json").write_text("{}", encoding="utf-8")
            report_path = self.write_report(body, root)
            with self.assertRaisesRegex(ReportValidationError, expected_message):
                validate_report(report_path, root)

    def test_valid_report_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixtures = root / "tests" / "fixtures"
            fixtures.mkdir(parents=True)
            (fixtures / "valid_ok_snapshot.json").write_text("{}", encoding="utf-8")
            report_path = self.write_report(VALID_REPORT_TEMPLATE, root)
            validate_report(report_path, root)

    def test_missing_required_section_is_rejected(self) -> None:
        body = VALID_REPORT_TEMPLATE.replace("## DeFi and stablecoin summary", "## Stablecoins")
        self.assert_report_rejected(body, "missing required report sections")

    def test_missing_disclaimer_language_is_rejected(self) -> None:
        body = VALID_REPORT_TEMPLATE.replace("not financial advice", "general information")
        self.assert_report_rejected(body, "missing product-boundary")

    def test_missing_source_reference_is_rejected(self) -> None:
        body = VALID_REPORT_TEMPLATE.replace("tests/fixtures/valid_ok_snapshot.json", "tests/fixtures/missing_snapshot.json", 1)
        self.assert_report_rejected(body, "source_snapshot does not point")

    def test_prohibited_advice_language_is_rejected(self) -> None:
        body = VALID_REPORT_TEMPLATE + "\nRecommendation: buy BTC now.\n"
        self.assert_report_rejected(body, "prohibited advice-like asset action")

    def test_negated_boundary_language_is_allowed(self) -> None:
        body = VALID_REPORT_TEMPLATE + "\nThis report does not provide a target price or trading signal.\n"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixtures = root / "tests" / "fixtures"
            fixtures.mkdir(parents=True)
            (fixtures / "valid_ok_snapshot.json").write_text("{}", encoding="utf-8")
            report_path = self.write_report(body, root)
            validate_report(report_path, root)


if __name__ == "__main__":
    unittest.main()
