from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_pages_site
import generate_crypto_daily_report as daily
from validate_crypto_daily_report import validate_daily

DAY = date(2026, 11, 22)
CUT = datetime(2026, 11, 23, 1, 0, tzinfo=timezone.utc)
HOURS = ("1107_AEDT", "1207_AEDT")


def git(root: Path, *args: str, at: str = "2026-11-22T03:00:00Z") -> str:
    env = {**os.environ, "GIT_AUTHOR_DATE": at, "GIT_COMMITTER_DATE": at}
    result = subprocess.run(["git", "-C", str(root), *args], check=True,
                            env=env, capture_output=True, text=True)
    return result.stdout.strip()


class DailyReportProofs(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="cryptopulse-daily-test-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "config").mkdir()
        (self.root / "config/crypto_sources.yml").write_bytes(
            (ROOT / "config/crypto_sources.yml").read_bytes()
        )
        for hour in HOURS:
            source = ROOT / "data/crypto/hourly/2026/11/22" / f"{hour}_source_snapshot.json"
            target = self.root / "data/crypto/hourly/2026/11/22" / source.name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
        git(self.root, "init", "-q", "-b", "main")
        git(self.root, "config", "user.name", "Synthetic Proof")
        git(self.root, "config", "user.email", "synthetic@example.invalid")
        self.sha = self.commit()
        self.config = self.root / "config/crypto_sources.yml"

    def commit(self, at: str = "2026-11-22T03:00:00Z") -> str:
        git(self.root, "add", ".")
        git(self.root, "commit", "-q", "-m", "Synthetic protected main", at=at)
        sha = git(self.root, "rev-parse", "HEAD")
        git(self.root, "update-ref", "refs/remotes/origin/main", sha)
        return sha

    def generate(self, sha: str | None = None):
        return daily.generate(self.root, sha or self.sha, DAY,
                              self.root / "reports/crypto/daily", self.config, CUT)

    def test_exact_two_hours_and_twenty_two_explicit_missing(self) -> None:
        path, records = self.generate()
        self.assertEqual(len(records), 24)
        self.assertEqual([r["status"] for r in records[:2]], ["valid-ok", "valid-ok"])
        self.assertEqual(sum(r["status"] == "missing" for r in records), 22)
        text = path.read_text()
        self.assertIn("Accepted UTC hours: **2/24**", text)
        self.assertIn("Missing hours: **22**", text)
        self.assertIn("SOL", text)
        self.assertIn(self.sha, text)
        self.assertIn("Snapshot SHA-256", text)

    def test_repeat_is_byte_identical_and_conflicting_existing_report_refused(self) -> None:
        path, _ = self.generate()
        before = path.read_bytes()
        self.generate()
        self.assertEqual(path.read_bytes(), before)
        path.write_bytes(before + b"\nTAMPER")
        with self.assertRaisesRegex(daily.DailyReportError, "different bytes"):
            self.generate()

    def test_reject_before_fixed_cutoff(self) -> None:
        with self.assertRaisesRegex(daily.DailyReportError, "cut-off has not elapsed"):
            daily.generate(self.root, self.sha, DAY, self.root / "reports",
                           self.config, datetime(2026, 11, 23, 0, 59, tzinfo=timezone.utc))

    def test_reject_snapshot_only_merged_after_cutoff(self) -> None:
        source = self.root / "data/crypto/hourly/2026/11/22/1107_AEDT_source_snapshot.json"
        source.write_bytes(source.read_bytes() + b" ")
        late_sha = self.commit("2026-11-23T02:00:00Z")
        with self.assertRaisesRegex(daily.DailyReportError, "not on protected main"):
            self.generate(late_sha)
        # Older pinned protected-main evidence remains reproducible.
        self.assertEqual(len([r for r in self.generate()[1] if r["status"] == "valid-ok"]), 2)

    def test_reject_duplicate_utc_hour_even_with_distinct_paths(self) -> None:
        source = self.root / "data/crypto/hourly/2026/11/22/1107_AEDT_source_snapshot.json"
        duplicate = source.with_name("1108_AEDT_source_snapshot.json")
        duplicate.write_bytes(source.read_bytes())
        duplicated_sha = self.commit("2026-11-22T04:00:00Z")
        with self.assertRaisesRegex(daily.DailyReportError, "Multiple trusted-main snapshots"):
            self.generate(duplicated_sha)

    def test_worktree_modification_cannot_change_pinned_snapshot_or_config(self) -> None:
        first, _ = self.generate()
        original = first.read_bytes()
        source = self.root / "data/crypto/hourly/2026/11/22/1107_AEDT_source_snapshot.json"
        source.write_text("untrusted worktree edit")
        self.config.write_text("corrupt: true\n")
        self.generate()
        self.assertEqual(first.read_bytes(), original)

    def test_tampered_candidate_rejected_by_independent_replay(self) -> None:
        path, _ = self.generate()
        validate_daily(path, self.root)
        path.write_bytes(path.read_bytes().replace(b"Accepted UTC hours: **2/24**",
                                                   b"Accepted UTC hours: **24/24**"))
        with self.assertRaisesRegex(daily.DailyReportError, "differ"):
            validate_daily(path, self.root)

    def test_degraded_rejected_and_missing_distinct(self) -> None:
        records = [{"hour": f"2026-11-22T{i:02d}:00:00Z", "status": "missing"}
                   for i in range(24)]
        records[0] = {"hour": "2026-11-22T00:00:00Z", "status": "valid-degraded",
                      "actual": "2026-11-22T00:07:00Z", "path": "data/crypto/hourly/x",
                      "sha256": "a"*64, "sources": [], "prices": {}}
        records[1] = {"hour": "2026-11-22T01:00:00Z", "status": "rejected",
                      "actual": "2026-11-22T01:07:00Z", "path": "data/crypto/hourly/y",
                      "sha256": "b"*64, "reason": "invalid sample", "prices": {}}
        result = daily.render(DAY, self.sha, records)
        self.assertIn("Accepted UTC hours: **1/24**", result)
        self.assertIn("Degraded accepted hours: **1**", result)
        self.assertIn("Rejected snapshots: **1**", result)
        self.assertIn("Missing hours: **22**", result)
        self.assertIn("unavailable", result)

    def test_future_provider_price_not_used(self) -> None:
        source = ROOT / "data/crypto/hourly/2026/11/22/1107_AEDT_source_snapshot.json"
        payload = json.loads(source.read_text())
        capture = daily.utc(payload["run"]["generated_at_utc"])
        for asset in payload["market"]["assets"]:
            if asset["symbol"] == "BTC":
                asset["last_updated"] = "2026-11-22T23:59:59Z"
        self.assertNotIn("BTC", daily.asset_prices(payload, capture))

    def test_site_archive_latest_search_feed_and_hourly_path(self) -> None:
        path, _ = self.generate()
        hourly_source = ROOT / "reports/crypto/hourly/2026/11/22/1107_AEDT.md"
        hourly_target = self.root / hourly_source.relative_to(ROOT)
        hourly_target.parent.mkdir(parents=True, exist_ok=True)
        hourly_target.write_bytes(hourly_source.read_bytes())
        with (mock.patch.object(build_pages_site, "ROOT", self.root),
              mock.patch.object(build_pages_site, "REPORTS_DIR", self.root / "reports/crypto/hourly"),
              mock.patch.object(build_pages_site, "OUT", self.root / "_site"),
              mock.patch.object(build_pages_site, "verify_editorial_source")):
            # The archived hourly editorial link is verified separately against
            # the real repository; this isolated Git fixture tests routing only.
            reports = build_pages_site.collect_reports()
            self.assertEqual(len(reports), 2)
            self.assertEqual(reports[0].source_path, path)
            self.assertEqual(reports[0].url, "archive/daily/2026/11/22/2026-11-22_UTC.html")
            self.assertEqual(reports[1].url, "archive/2026/11/22/1107_AEDT.html")
            (self.root / "_site").mkdir()
            build_pages_site.write_report_pages(reports)
            build_pages_site.write_site_indexes(reports)
        index = (self.root / "_site/latest.html").read_text()
        feed = (self.root / "_site/feed.xml").read_text()
        search = json.loads((self.root / "_site/search-index.json").read_text())
        manifest = json.loads((self.root / "_site/manifest.json").read_text())
        self.assertIn("CryptoPulse daily evidence summary", index)
        self.assertIn("archive/daily/2026/11/22/2026-11-22_UTC.html", feed)
        self.assertEqual(search[0]["url"], reports[0].url)
        self.assertEqual(manifest["latest"]["url"], reports[0].url)
        self.assertTrue((self.root / "_site/archive/2026/11/22/1107_AEDT.html").exists())
        self.assertTrue((self.root / "_site/archive/daily/2026/11/22/2026-11-22_UTC.html").exists())


if __name__ == "__main__":
    unittest.main()
