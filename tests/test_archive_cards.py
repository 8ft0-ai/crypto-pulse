from pathlib import Path
from types import SimpleNamespace

from site_generator import archive_cards, homepage_summary


class BaseStub:
    @staticmethod
    def split_front_matter(text: str):
        return ({"live_data_status": "partial"}, text)

    @staticmethod
    def strip_chatgpt_citations(text: str):
        return text

    @staticmethod
    def month_name(month: str):
        return "July" if month == "07" else month


def report(tmp_path: Path, body: str, *, filename: str = "report.md", headline: str = "Evidence summary"):
    source = tmp_path / filename
    source.write_text(body, encoding="utf-8")
    return SimpleNamespace(
        source_path=source,
        year="2026",
        month="07",
        day="10",
        time_label="09:00" if filename == "report.md" else "",
        tz="AEST" if filename == "report.md" else "",
        timestamp="2026-07-10 09:00 AEST",
        title="Hourly report",
        headline=headline,
        url="archive/2026/07/10/report.html",
        source_items=["CoinGecko"],
    )


def test_archive_card_shows_time_metrics_and_data_status(tmp_path):
    item = report(tmp_path, """
| Asset | Price | 1h | 24h | Note |
| --- | --- | --- | --- | --- |
| BTC | 1 | +0.4% | -1.2% | mixed |
| ETH | 1 | -0.2% | +2.1% | firm |
""")
    html = archive_cards.recent_report_cards([item], BaseStub)
    assert "2026-07-10 · 09:00 AEST" in html
    assert "BTC 24h" in html and "-1.2%" in html
    assert "ETH 24h" in html and "+2.1%" in html
    assert "Data" in html and "partial" in html
    assert html.index("BTC 24h") < html.index("ETH 24h") < html.index("Data")


def test_time_falls_back_to_short_report_filename(tmp_path):
    item = report(tmp_path, "No metric table is present.", filename="1742_AEST.md")
    html = archive_cards.recent_report_cards([item], BaseStub)
    assert "2026-07-10 · 17:42 AEST" in html


def test_missing_metrics_are_omitted_without_placeholder_text(tmp_path):
    item = report(tmp_path, "No metric table is present.")
    html = archive_cards.recent_report_cards([item], BaseStub)
    assert "BTC 24h" not in html
    assert "ETH 24h" not in html
    assert "not specified" not in html.lower()
    assert "partial" in html


def test_disclaimer_headline_is_not_rendered_on_archive_card(tmp_path):
    item = report(
        tmp_path,
        "No metric table is present.",
        headline="This report is deterministic demonstration content. It is not financial advice.",
    )
    html = archive_cards.recent_report_cards([item], BaseStub)
    assert "not financial advice" not in html.lower()


def test_safe_headline_skips_disclaimer_and_uses_first_evidence_line():
    body = """
This report is deterministic demonstration content generated from one validated source snapshot. It is not financial advice.

Source-provided market fields are listed without interpretation.
"""
    value = homepage_summary.safe_headline(body, body.splitlines()[1])
    assert value == "Source-provided market fields are listed without interpretation."


def test_non_colour_status_signals_are_rendered():
    html = archive_cards.metric_html([
        ("BTC 24h", "+1.0%", "up"),
        ("ETH 24h", "-2.0%", "down"),
        ("Data", "partial", "status"),
    ])
    assert "archive-metric-up" in html
    assert "archive-metric-down" in html
    assert "archive-metric-status" in html


def test_configure_replaces_both_archive_renderers():
    base = SimpleNamespace(recent_report_cards=None, grouped_archive=None)
    archive_cards.configure(base)
    assert callable(base.recent_report_cards)
    assert callable(base.grouped_archive)
