from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from site_generator import report_chronology


def _load_builder():
    path = Path(__file__).resolve().parents[1] / "scripts" / "build_pages_site.py"
    spec = importlib.util.spec_from_file_location("phase16_build_pages_site", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("unable to load site builder")
    module = importlib.util.module_from_spec(spec)
    fake_markdown = SimpleNamespace(markdown=lambda text, **_kwargs: text)
    fake_yaml = SimpleNamespace(safe_load=lambda _text: {})
    with mock.patch.dict(sys.modules, {"markdown": fake_markdown, "yaml": fake_yaml}):
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
    return module


def _report(path: str, metadata: dict) -> SimpleNamespace:
    return SimpleNamespace(
        source_rel=path,
        metadata=metadata,
        timestamp="legacy",
        sort_key="legacy",
        time_label="",
        tz="",
    )


class Phase16ReportChronologyTests(unittest.TestCase):
    def test_current_deterministic_regression_orders_2031_before_1742(self) -> None:
        earlier = _report(
            "reports/crypto/hourly/2026/07/08/1742_AEST.md",
            {
                "schema_version": "deterministic-crypto-report/v1",
                "generated_at_utc": "2026-07-08T07:42:11Z",
                "generated_at_local": "2026-07-08T17:42:11+10:00",
                "timezone": "Australia/Sydney",
                "timezone_abbreviation": "AEST",
            },
        )
        later = _report(
            "reports/crypto/hourly/2026/07/08/2031_AEST.md",
            {
                "schema_version": "deterministic-crypto-report/v1",
                "generated_at_utc": "2026-07-08T10:31:48Z",
                "generated_at_local": "2026-07-08T20:31:48+10:00",
                "timezone": "Australia/Sydney",
                "timezone_abbreviation": "AEST",
            },
        )

        ordered = report_chronology.canonicalise_reports([earlier, later])

        self.assertIs(ordered[0], later)
        self.assertEqual(later.timestamp, "2026-07-08 20:31 AEST")
        self.assertEqual(later.time_label, "20:31")
        self.assertEqual(later.report_time_utc, "2026-07-08T10:31:48Z")


    def test_deterministic_path_can_supply_display_zone_when_optional_local_metadata_absent(self) -> None:
        report = _report(
            "reports/crypto/hourly/2026/07/08/2031_AEST.md",
            {
                "schema_version": "deterministic-crypto-report/v1",
                "generated_at_utc": "2026-07-08T10:31:48Z",
            },
        )
        ordered = report_chronology.canonicalise_reports([report])
        self.assertEqual(ordered[0].timestamp, "2026-07-08 20:31 AEST")


    def test_canonical_order_flows_to_latest_archive_feed_manifest_and_search_index(self) -> None:
        builder = _load_builder()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reports_dir = root / "reports" / "crypto" / "hourly" / "2026" / "07" / "08"
            reports_dir.mkdir(parents=True)
            out = root / "_site"
            out.mkdir()
            (reports_dir / "1742_AEST.md").write_text("EARLIER", encoding="utf-8")
            (reports_dir / "2031_AEST.md").write_text("LATER", encoding="utf-8")

            def split_fixture(raw: str):
                if raw == "LATER":
                    return ({
                        "schema_version": "deterministic-crypto-report/v1",
                        "generated_at_utc": "2026-07-08T10:31:48Z",
                        "generated_at_local": "2026-07-08T20:31:48+10:00",
                        "timezone": "Australia/Sydney",
                        "timezone_abbreviation": "AEST",
                    }, "# Later deterministic report\n\nLater headline.")
                return ({
                    "schema_version": "deterministic-crypto-report/v1",
                    "generated_at_utc": "2026-07-08T07:42:11Z",
                    "generated_at_local": "2026-07-08T17:42:11+10:00",
                    "timezone": "Australia/Sydney",
                    "timezone_abbreviation": "AEST",
                }, "# Earlier deterministic report\n\nEarlier headline.")

            with mock.patch.object(builder, "ROOT", root), mock.patch.object(
                builder, "REPORTS_DIR", root / "reports" / "crypto" / "hourly"
            ), mock.patch.object(builder, "OUT", out), mock.patch.object(
                builder, "split_front_matter", side_effect=split_fixture
            ):
                reports = builder.collect_reports()
                builder.write_site_indexes(reports)

            self.assertEqual(reports[0].source_path.name, "2031_AEST.md")
            latest = (out / "latest.html").read_text(encoding="utf-8")
            archive = (out / "archive" / "index.html").read_text(encoding="utf-8")
            feed = (out / "feed.xml").read_text(encoding="utf-8")
            manifest = json.loads((out / "manifest.json").read_text(encoding="utf-8"))
            search = json.loads((out / "search-index.json").read_text(encoding="utf-8"))
            self.assertIn("Later deterministic report", latest)
            self.assertLess(archive.index("Later deterministic report"), archive.index("Earlier deterministic report"))
            self.assertLess(feed.index("Later deterministic report"), feed.index("Earlier deterministic report"))
            self.assertEqual(manifest["latest"]["title"], "Later deterministic report")
            self.assertEqual(search[0]["title"], "Later deterministic report")
            self.assertEqual(search[0]["timestamp"], "2026-07-08 20:31 AEST")

    def test_deterministic_metadata_cannot_be_repaired_from_filename(self) -> None:
        report = _report(
            "reports/crypto/hourly/2026/07/08/2031_AEST.md",
            {
                "schema_version": "deterministic-crypto-report/v1",
                "generated_at_utc": "2026-07-08T09:31:48Z",
                "generated_at_local": "2026-07-08T20:31:48+10:00",
                "timezone": "Australia/Sydney",
                "timezone_abbreviation": "AEST",
            },
        )
        with self.assertRaises(report_chronology.ReportChronologyError):
            report_chronology.canonicalise_reports([report])

    def test_deterministic_path_conflict_fails_closed(self) -> None:
        report = _report(
            "reports/crypto/hourly/2026/07/08/1742_AEST.md",
            {
                "schema_version": "deterministic-crypto-report/v1",
                "generated_at_utc": "2026-07-08T10:31:48Z",
                "generated_at_local": "2026-07-08T20:31:48+10:00",
                "timezone": "Australia/Sydney",
                "timezone_abbreviation": "AEST",
            },
        )
        with self.assertRaises(report_chronology.ReportChronologyError):
            report_chronology.canonicalise_reports([report])

    def test_legacy_prefers_valid_timestamp_and_checks_path(self) -> None:
        report = _report(
            "reports/crypto/hourly/2026/05/09/1848_AEST_crypto_market_intelligence.md",
            {"timestamp": "2026-05-09 18:48 AEST"},
        )
        ordered = report_chronology.canonicalise_reports([report])
        self.assertEqual(ordered[0].timestamp, "2026-05-09 18:48 AEST")
        self.assertEqual(ordered[0].report_time_utc, "2026-05-09T08:48:00Z")

    def test_legacy_uses_recognised_path_only_when_timestamp_absent(self) -> None:
        report = _report(
            "reports/crypto/hourly/2026/05/09/1848_AEST_crypto_market_intelligence.md",
            {},
        )
        ordered = report_chronology.canonicalise_reports([report])
        self.assertEqual(ordered[0].timestamp, "2026-05-09 18:48 AEST")

    def test_legacy_timestamp_path_conflict_fails_closed(self) -> None:
        report = _report(
            "reports/crypto/hourly/2026/05/09/1848_AEST_crypto_market_intelligence.md",
            {"timestamp": "2026-05-09 19:48 AEST"},
        )
        with self.assertRaises(report_chronology.ReportChronologyError):
            report_chronology.canonicalise_reports([report])

    def test_duplicate_canonical_instant_fails_closed(self) -> None:
        first = _report(
            "reports/crypto/hourly/2026/05/09/1848_AEST_crypto_market_intelligence.md",
            {"timestamp": "2026-05-09 18:48 AEST"},
        )
        second = _report(
            "reports/crypto/hourly/2026/05/09/0848_UTC_crypto_market_intelligence.md",
            {"timestamp": "2026-05-09 08:48 UTC"},
        )
        with self.assertRaises(report_chronology.ReportChronologyError):
            report_chronology.canonicalise_reports([first, second])

    def test_unsupported_retained_report_is_not_silently_skipped(self) -> None:
        report = _report("reports/crypto/hourly/2026/05/09/report.md", {})
        with self.assertRaises(report_chronology.ReportChronologyError):
            report_chronology.canonicalise_reports([report])


if __name__ == "__main__":
    unittest.main()
