from __future__ import annotations

import unittest
from pathlib import Path
from types import SimpleNamespace

from site_generator import archive_reader


def report(
    when: str,
    *,
    timestamp: str,
    month: str,
    day: str,
    chronology_kind: str,
    quality_status: str | None = None,
):
    metadata = {}
    if chronology_kind == "deterministic":
        metadata["schema_version"] = "deterministic-crypto-report/v1"
    if quality_status is not None:
        metadata["quality_status"] = quality_status
    return SimpleNamespace(
        report_time_utc=when,
        timestamp=timestamp,
        year="2026",
        month=month,
        day=day,
        chronology_kind=chronology_kind,
        metadata=metadata,
    )


class Base:
    GITHUB_URL = "https://github.com/8ft0-ai/crypto-pulse"

    def __init__(self, reports):
        self._reports = reports

    def collect_reports(self):
        return list(self._reports)

    @staticmethod
    def month_name(month: str):
        return {"07": "July", "05": "May"}.get(month, month)


ARCHIVE_HTML = """<!doctype html>
<html><head><title>Archive</title></head><body>
<section class="demo-banner"><p>Demo</p></section>
<nav class="site-nav" aria-label="Primary navigation"><a href="../index.html">Home</a><a href="../latest.html">Latest Report</a></nav>
<header class="hero"><h1>Archive</h1><p>Grouped archive of AI-generated CryptoPulse demo reports.</p></header>
<section class="content archive-content"><div class="section-heading"><div><div class="eyebrow">Archive browser</div><h2>Browse generated demo reports</h2></div><a class="text-link" href="../search-index.json">Open search index JSON →</a></div>
<section class="archive-stats-grid" aria-label="Archive statistics"><article><div class="eyebrow">Cadence</div><p>Hourly archive cadence</p></article></section>
<nav class="archive-jumps"></nav>
<section class="archive-groups"><article class="archive-card" data-archive-month="2026-07" data-archive-generation="deterministic" data-archive-evidence-state="validated-source-evidence">MARKET CARD</article></section>
</section>
<footer class="footer"><div class="developer-output-links" aria-label="Developer outputs"><span>Developer outputs</span><a href="../search-index.json">Search index</a></div></footer>
</body></html>"""


class ArchiveReaderTests(unittest.TestCase):
    def test_taxonomy_keeps_generation_and_evidence_state_separate(self):
        valid = report(
            "2026-07-08T10:31:48Z",
            timestamp="2026-07-08 20:31 AEST",
            month="07",
            day="08",
            chronology_kind="deterministic",
            quality_status="valid-ok",
        )
        degraded = report(
            "2026-07-08T07:42:09Z",
            timestamp="2026-07-08 17:42 AEST",
            month="07",
            day="08",
            chronology_kind="deterministic",
            quality_status="valid-degraded",
        )
        legacy = report(
            "2026-05-16T01:00:00Z",
            timestamp="2026-05-16 11:00 AEST",
            month="05",
            day="16",
            chronology_kind="legacy",
        )

        self.assertEqual(archive_reader.report_generation(valid)["label"], "Deterministic evidence")
        self.assertEqual(archive_reader.report_evidence_state(valid)["label"], "Validated source evidence")
        self.assertEqual(archive_reader.report_evidence_state(degraded)["label"], "Degraded / partial evidence")
        self.assertEqual(archive_reader.report_generation(legacy)["label"], "AI-generated historical report")
        self.assertEqual(archive_reader.report_evidence_state(legacy)["label"], "Legacy evidence format")

    def test_unknown_deterministic_quality_is_not_invented(self):
        item = report(
            "2026-07-08T10:31:48Z",
            timestamp="2026-07-08 20:31 AEST",
            month="07",
            day="08",
            chronology_kind="deterministic",
        )
        self.assertIsNone(archive_reader.report_evidence_state(item))

    def test_archive_context_uses_existing_reverse_chronology_and_reports_discontinuity(self):
        reports = [
            report(
                "2026-07-08T10:31:48Z",
                timestamp="2026-07-08 20:31 AEST",
                month="07",
                day="08",
                chronology_kind="deterministic",
                quality_status="valid-ok",
            ),
            report(
                "2026-07-08T07:42:09Z",
                timestamp="2026-07-08 17:42 AEST",
                month="07",
                day="08",
                chronology_kind="deterministic",
                quality_status="valid-degraded",
            ),
            report(
                "2026-05-16T01:00:00Z",
                timestamp="2026-05-16 11:00 AEST",
                month="05",
                day="16",
                chronology_kind="legacy",
            ),
        ]
        context = archive_reader.build_archive_context(Base(reports))

        self.assertEqual(context["reports"], reports)
        self.assertEqual(context["total_count"], 3)
        self.assertEqual(
            context["months"],
            [
                {"key": "2026-07", "label": "July 2026"},
                {"key": "2026-05", "label": "May 2026"},
            ],
        )
        self.assertEqual(context["intervals_over_one_hour"], 2)
        self.assertEqual(context["represented_utc_dates"], 2)
        self.assertGreater(context["calendar_days"], context["represented_utc_dates"])
        self.assertGreater(context["largest_interval_seconds"], 3600)

    def test_archive_context_fails_if_input_is_not_canonical_reverse_order(self):
        reports = [
            report(
                "2026-05-16T01:00:00Z",
                timestamp="older",
                month="05",
                day="16",
                chronology_kind="legacy",
            ),
            report(
                "2026-07-08T10:31:48Z",
                timestamp="newer",
                month="07",
                day="08",
                chronology_kind="deterministic",
                quality_status="valid-ok",
            ),
        ]
        with self.assertRaises(archive_reader.ArchiveReaderIntegrationError):
            archive_reader.build_archive_context(Base(reports))

    def test_archive_transform_replaces_cadence_demotes_json_and_leads_cards_with_safety(self):
        item = report(
            "2026-07-08T10:31:48Z",
            timestamp="2026-07-08 20:31 AEST",
            month="07",
            day="08",
            chronology_kind="deterministic",
            quality_status="valid-ok",
        )
        base = Base([item])
        context = archive_reader.build_archive_context(base)
        transformed = archive_reader.transform_archive(ARCHIVE_HTML, context, base)

        self.assertNotIn("Hourly archive cadence", transformed)
        self.assertIn("Browse retained evidence", transformed)
        self.assertIn("Observed discontinuity", transformed)
        self.assertIn("Filter retained reports", transformed)
        self.assertIn("data-archive-filter-controls hidden", transformed)
        self.assertLess(transformed.index("Demo archive — not for trading"), transformed.index("MARKET CARD"))
        self.assertEqual(transformed.count("search-index.json"), 1)
        self.assertLess(transformed.index("Reader filters"), transformed.index("<summary>Developer outputs</summary>"))
        self.assertIn("cryptopulse-archive-reader.css", transformed)
        self.assertIn("cryptopulse-archive-reader.js", transformed)

    def test_archive_javascript_uses_generated_attributes_without_network_calls(self):
        script = (
            Path(__file__).resolve().parents[1]
            / "site"
            / "assets"
            / archive_reader.SCRIPT_NAME
        ).read_text(encoding="utf-8")
        self.assertIn("dataset.archiveMonth", script)
        self.assertIn("dataset.archiveGeneration", script)
        self.assertIn("dataset.archiveEvidenceState", script)
        for forbidden in ("fetch(", "XMLHttpRequest", "WebSocket", "EventSource", "sendBeacon"):
            self.assertNotIn(forbidden, script)


if __name__ == "__main__":
    unittest.main()
