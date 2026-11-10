from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from site_generator import homepage_summary


DISCLAIMER = "This AI-generated demo report is for demonstration purposes only and is not financial advice."


class FakeBase:
    @staticmethod
    def split_front_matter(raw: str):
        return {"live_data_status": "ok"}, raw

    @staticmethod
    def strip_chatgpt_citations(value: str) -> str:
        return value


class FakeSearch:
    @staticmethod
    def markdown_section(markdown_text: str, title: str) -> str:
        marker = f"## {title}\n"
        if marker not in markdown_text:
            return ""
        remainder = markdown_text.split(marker, 1)[1]
        return remainder.split("\n## ", 1)[0].strip()

    @staticmethod
    def first_text_line(block: str) -> str:
        return next((line.strip() for line in block.splitlines() if line.strip()), "")

    @staticmethod
    def extract_trend_confidence(body: str) -> str:
        return "Not specified"

    @staticmethod
    def extract_leaders(body: str) -> str:
        return "Open latest report for asset detail"

    @staticmethod
    def extract_main_risk(body: str) -> str:
        return "Open latest report for risk detail"

    @staticmethod
    def extract_data_quality(body: str, metadata: dict[str, object]) -> str:
        return f"Live data status: {metadata['live_data_status']}"


@dataclass
class FakeReport:
    source_path: Path
    headline: str
    timestamp: str = "2026-07-10 08:00 AEST"
    url: str = "reports/2026-07-10-0800.html"


def test_boilerplate_and_placeholders_are_not_meaningful() -> None:
    assert not homepage_summary.is_meaningful(DISCLAIMER)
    assert not homepage_summary.is_meaningful("Not specified")
    assert not homepage_summary.is_meaningful("Open latest report for risk detail")
    assert homepage_summary.is_meaningful("BTC and ETH source snapshots passed all configured checks")


def test_panel_excludes_disclaimer_fallback_and_suppresses_missing_fields(tmp_path: Path) -> None:
    source = tmp_path / "report.md"
    source.write_text(
        "## Executive summary\nBTC and ETH source snapshots passed all configured checks.\n",
        encoding="utf-8",
    )
    report = FakeReport(source_path=source, headline=DISCLAIMER)

    html = homepage_summary.latest_market_read_panel(report, FakeSearch, FakeBase)

    assert DISCLAIMER not in html
    assert "BTC and ETH source snapshots passed all configured checks" in html
    assert "Trend confidence" not in html
    assert "Leading assets" not in html
    assert "Main risk" not in html
    assert "Data quality and provenance" in html
    assert "This report format does not publish every legacy interpretation field" in html


def test_panel_keeps_meaningful_legacy_fields(tmp_path: Path) -> None:
    source = tmp_path / "legacy.md"
    source.write_text(
        "## Rolling trend analysis\n"
        "### Emerging trend\nBroad market momentum improved.\n"
        "### Analyst read\nThe move remained concentrated in large-cap assets.\n",
        encoding="utf-8",
    )
    report = FakeReport(source_path=source, headline="Legacy report headline")

    class LegacySearch(FakeSearch):
        @staticmethod
        def extract_trend_confidence(body: str) -> str:
            return "Medium"

        @staticmethod
        def extract_leaders(body: str) -> str:
            return "BTC, ETH"

        @staticmethod
        def extract_main_risk(body: str) -> str:
            return "A reversal in spot demand"

    html = homepage_summary.latest_market_read_panel(report, LegacySearch, FakeBase)

    assert "Broad market momentum improved" in html
    assert "The move remained concentrated in large-cap assets" in html
    assert "Trend confidence" in html
    assert "BTC, ETH" in html
    assert "A reversal in spot demand" in html
