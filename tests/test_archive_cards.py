from pathlib import Path
from types import SimpleNamespace

from site_generator import archive_cards


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


def report(tmp_path: Path, body: str):
    source = tmp_path / "report.md"
    source.write_text(body, encoding="utf-8")
    return SimpleNamespace(
        source_path=source,
        year="2026",
        month="07",
        day="10",
        time_label="09:00",
        tz="AEST",
        timestamp="2026-07-10 09:00 AEST",
        title="Hourly report",
        headline="Evidence summary",
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


def test_missing_metrics_are_omitted_without_placeholder_text(tmp_path):
    item = report(tmp_path, "No metric table is present.")
    html = archive_cards.recent_report_cards([item], BaseStub)
    assert "BTC 24h" not in html
    assert "ETH 24h" not in html
    assert "not specified" not in html.lower()
    assert "partial" in html


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
