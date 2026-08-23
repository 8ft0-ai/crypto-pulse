import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from site_generator import archive_cards, homepage_summary


class BaseStub:
    @staticmethod
    def month_name(month: str):
        return "July" if month == "07" else "May" if month == "05" else month


def report(
    tmp_path: Path,
    body: str = "",
    *,
    filename: str = "report.md",
    headline: str = "Evidence summary",
    schema_version: str | None = "deterministic-crypto-report/v1",
    quality_status: str | None = "valid-ok",
    chronology_kind: str | None = None,
    month: str = "07",
    day: str = "10",
):
    source = tmp_path / filename
    source.write_text(body, encoding="utf-8")
    metadata = {}
    if schema_version is not None:
        metadata["schema_version"] = schema_version
    if quality_status is not None:
        metadata["quality_status"] = quality_status
    if chronology_kind is None:
        chronology_kind = (
            "deterministic"
            if schema_version == "deterministic-crypto-report/v1"
            else "legacy"
        )
    return SimpleNamespace(
        source_path=source,
        year="2026",
        month=month,
        day=day,
        time_label="09:00" if filename == "report.md" else "",
        tz="AEST" if filename == "report.md" else "",
        timestamp=f"2026-{month}-{day} 09:00 AEST",
        title="Hourly report",
        headline=headline,
        url=f"archive/2026/{month}/{day}/{filename.replace('.md', '.html')}",
        metadata=metadata,
        chronology_kind=chronology_kind,
    )


class ArchiveCardTests(unittest.TestCase):
    def test_deterministic_card_uses_repository_backed_taxonomy(self):
        with tempfile.TemporaryDirectory() as tmp:
            item = report(Path(tmp))
            html = archive_cards.recent_report_cards([item], BaseStub)
        self.assertIn("Deterministic evidence", html)
        self.assertIn("Validated source evidence", html)
        self.assertIn('data-archive-generation="deterministic"', html)
        self.assertIn(
            'data-archive-evidence-state="validated-source-evidence"',
            html,
        )
        self.assertIn('data-archive-month="2026-07"', html)

    def test_degraded_deterministic_card_keeps_generation_and_quality_separate(self):
        with tempfile.TemporaryDirectory() as tmp:
            item = report(Path(tmp), quality_status="valid-degraded")
            html = archive_cards.recent_report_cards([item], BaseStub)
        self.assertIn("Deterministic evidence", html)
        self.assertIn("Degraded / partial evidence", html)

    def test_legacy_card_does_not_normalise_metrics_from_report_prose(self):
        with tempfile.TemporaryDirectory() as tmp:
            item = report(
                Path(tmp),
                """
| Asset | Price | 1h | 24h |
| --- | --- | --- | --- |
| BTC | 1 | +0.4% | -1.2% |
| ETH | 1 | -0.2% | +2.1% |
""",
                schema_version=None,
                quality_status=None,
                chronology_kind="legacy",
            )
            html = archive_cards.recent_report_cards([item], BaseStub)
        self.assertIn("AI-generated historical report", html)
        self.assertIn("Legacy evidence format", html)
        self.assertNotIn("BTC 24h", html)
        self.assertNotIn("ETH 24h", html)
        self.assertNotIn("-1.2%", html)
        self.assertNotIn("+2.1%", html)

    def test_unknown_deterministic_evidence_state_is_omitted(self):
        with tempfile.TemporaryDirectory() as tmp:
            item = report(Path(tmp), quality_status=None)
            html = archive_cards.recent_report_cards([item], BaseStub)
        self.assertIn("Deterministic evidence", html)
        self.assertNotIn("Validated source evidence", html)
        self.assertNotIn("Degraded / partial evidence", html)
        self.assertIn('data-archive-evidence-state=""', html)

    def test_time_falls_back_to_short_report_filename(self):
        with tempfile.TemporaryDirectory() as tmp:
            item = report(Path(tmp), filename="1742_AEST.md")
            html = archive_cards.recent_report_cards([item], BaseStub)
        self.assertIn("2026-07-10 · 17:42 AEST", html)

    def test_disclaimer_headline_is_not_rendered_on_archive_card(self):
        with tempfile.TemporaryDirectory() as tmp:
            item = report(
                Path(tmp),
                headline=(
                    "This report is deterministic demonstration content. "
                    "It is not financial advice."
                ),
            )
            html = archive_cards.recent_report_cards([item], BaseStub)
        self.assertNotIn("not financial advice", html.lower())

    def test_safe_headline_skips_disclaimer_and_uses_first_evidence_line(self):
        body = """
This report is deterministic demonstration content generated from one validated source snapshot. It is not financial advice.

Source-provided market fields are listed without interpretation.
"""
        value = homepage_summary.safe_headline(body, body.splitlines()[1])
        self.assertEqual(
            value,
            "Source-provided market fields are listed without interpretation.",
        )

    def test_grouped_archive_preserves_canonical_input_group_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            first = report(path, filename="first.md", month="05", day="16")
            second = report(path, filename="second.md", month="07", day="08")
            html = archive_cards.grouped_archive([first, second], BaseStub)
        self.assertLess(html.index(">May <"), html.index(">July <"))

    def test_configure_replaces_both_archive_renderers(self):
        base = SimpleNamespace(recent_report_cards=None, grouped_archive=None)
        archive_cards.configure(base)
        self.assertTrue(callable(base.recent_report_cards))
        self.assertTrue(callable(base.grouped_archive))


if __name__ == "__main__":
    unittest.main()
