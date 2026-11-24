from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
import yaml
from datetime import date, datetime, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import build_pages_site
import generate_crypto_daily_report as daily
import daily_publication as daily_pub
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

    def test_daily_and_hourly_at_exact_same_cutoff_preserve_both(self) -> None:
        from types import SimpleNamespace
        from site_generator.report_chronology import canonicalise_reports

        daily_report = SimpleNamespace(
            source_rel="reports/crypto/daily/2026/11/22/2026-11-22_UTC.md",
            metadata={
                "schema_version": "deterministic-crypto-daily-report/v1",
                "report_type": "crypto_daily_consolidation",
                "reporting_date_utc": "2026-11-22",
                "evidence_cutoff_utc": "2026-11-23T01:00:00Z",
                "report_reference_time_utc": "2026-11-23T01:00:00Z",
                "cadence": "daily",
                "trusted_main_sha": "a" * 40,
            },
        )
        hourly_report = SimpleNamespace(
            source_rel="reports/crypto/hourly/2026/11/23/0100_UTC.md",
            metadata={
                "schema_version": "deterministic-crypto-report/v1",
                "generated_at_utc": "2026-11-23T01:00:00Z",
                "generated_at_local": "2026-11-23T01:00:00+00:00",
                "timezone": "UTC",
                "timezone_abbreviation": "UTC",
            },
        )
        ordered = canonicalise_reports([hourly_report, daily_report])
        self.assertEqual(ordered, [daily_report, hourly_report])
        self.assertEqual(daily_report.report_time_utc, hourly_report.report_time_utc)

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

    def test_daily_publication_attestation_and_independent_preflight(self) -> None:
        _, slots = self.generate()
        # The attestation preserves all slot dispositions and exact source bytes.
        hours = [{"hour": row["hour"], "status": row["status"],
                  "path": row.get("path"), "sha256": row.get("sha256")}
                 for row in slots]
        path = daily.output_path(DAY, self.root / "reports/crypto/daily")
        branch = "automation/daily-publication-9001-1-2026-11-22"
        att = daily_pub.build_attestation(
            reporting_date_utc=DAY.isoformat(), trusted_main_sha=self.sha,
            expected_main_base_sha=self.sha,
            source_config_sha256=__import__("hashlib").sha256(self.config.read_bytes()).hexdigest(),
            hours=hours,
            report_path="reports/crypto/daily/2026/11/22/2026-11-22_UTC.md",
            report_bytes=path.read_bytes(), candidate_head_sha="b"*40,
            candidate_branch=branch, pull_request_number=4,
            generation_workflow_id=55, generation_run_id=9001,
            generation_run_attempt=1, publication_app_actor_id=77,
            publication_app_slug="cryptopulse-publication")
        facts = {
            "source_ancestor_at_cutoff": True, "source_replay_valid": True,
            "source_population_valid": True, "report_replay_valid": True,
            "changed_files": [att["report_path"]], "duplicate_date_count": 0,
            "duplicate_candidate_count": 0, "pr_number": 4, "same_repository": True, "pr_open": True,
            "pr_author_id": 77, "pr_author_login": "cryptopulse-publication[bot]",
            "pr_head_sha": "b"*40, "pr_head_ref": branch, "pr_base": "main",
            "current_main_sha": self.sha, "validation_head_sha": "b"*40,
            "validation_status": "success",
            "validation_check": "Build site and check generated output",
            "validation_app_slug": "github-actions",
            "attestation_count": 1, "attestation_expired": False,
            "artifact_name": "cryptopulse-daily-attestation-9001-1",
            "generation_run_id": 9001, "generation_workflow_id": 55,
            "generation_workflow_path": daily_pub.GENERATION_WORKFLOW_PATH,
            "trusted_generation_run": True,
            "generation_head_sha": self.sha, "report_path": att["report_path"],
            "report_sha256": att["report_sha256"],
        }
        self.assertTrue(daily_pub.evaluate_daily_gate(att, facts)["eligible"])
        self.assertTrue(daily_pub.evaluate_daily_gate(att, facts)["eligible"])
        daily_pub.independently_validate_candidate(self.root, att, path.read_bytes(),
                                                   [att["report_path"]])

        for key, value in (("source_ancestor_at_cutoff", False),
                           ("source_replay_valid", False),
                           ("source_population_valid", False),
                           ("report_replay_valid", False),
                           ("pr_head_sha", "c"*40), ("pr_base", "other"),
                           ("duplicate_date_count", 1),
                           ("pr_author_id", 78), ("attestation_count", 2),
                           ("trusted_generation_run", False)):
            changed = dict(facts, **{key: value})
            self.assertFalse(daily_pub.evaluate_daily_gate(att, changed)["eligible"], key)

        tampered = dict(att, source_population_sha256="0"*64)
        self.assertFalse(daily_pub.evaluate_daily_gate(tampered, facts)["eligible"])
        self.assertFalse(daily_pub.evaluate_daily_gate(att, dict(facts, changed_files=[att["report_path"], "README.md"]))["eligible"])

    def test_daily_population_distinguishes_missing_and_rejected_and_duplicate_hours(self) -> None:
        _, slots = self.generate()
        hours = [{"hour": row["hour"], "status": row["status"],
                  "path": row.get("path"), "sha256": row.get("sha256")}
                 for row in slots]
        daily_pub.validate_hours(DAY.isoformat(), hours)
        self.assertEqual(sum(row["status"] == "missing" for row in hours), 22)
        hours[2] = dict(hours[2], status="rejected", path=hours[0]["path"], sha256=hours[0]["sha256"])
        with self.assertRaisesRegex(daily_pub.DailyPublicationError, "duplicate"):
            daily_pub.validate_hours(DAY.isoformat(), hours)

    def test_daily_workflow_wiring_is_manual_read_only_at_preflight_and_pages_aware(self) -> None:
        generate = yaml.safe_load((ROOT / ".github/workflows/generate-daily-crypto-report.yml").read_text())
        gate = yaml.safe_load((ROOT / ".github/workflows/deterministic-site-publication-gate.yml").read_text())
        pages = yaml.safe_load((ROOT / ".github/workflows/pages.yml").read_text())
        # PyYAML's YAML 1.1 parser treats `on` as boolean true.
        trigger = generate.get("on", generate.get(True, {}))
        self.assertEqual(set(trigger), {"workflow_dispatch"})
        self.assertNotIn("schedule", trigger)
        generate_text = (ROOT / ".github/workflows/generate-daily-crypto-report.yml").read_text()
        self.assertIn("automation/daily-publication-", generate_text)
        self.assertIn("actions/create-github-app-token@v3", generate_text)
        self.assertIn("cryptopulse-daily-attestation-${{ github.run_id }}-${{ github.run_attempt }}", generate_text)
        self.assertIn(".head.sha == $head", generate_text)
        gate_trigger = gate.get("on", gate.get(True, {}))
        self.assertIn("workflow_run", gate_trigger)
        self.assertNotIn("schedule", gate_trigger)
        self.assertEqual(gate["permissions"]["contents"], "read")
        self.assertEqual(gate["permissions"]["pull-requests"], "read")
        pages_trigger = pages.get("on", pages.get(True, {}))
        paths = pages_trigger["push"]["paths"]
        self.assertIn("reports/crypto/daily/**/*.md", paths)
        self.assertIn("reports/crypto/hourly/**/*.md", paths)
        self.assertIn("preflight", gate["jobs"])
        self.assertIn("merge", gate["jobs"])
        self.assertIn("daily-preflight", gate["jobs"])
        self.assertNotIn("create-github-app-token", str(gate["jobs"]["daily-preflight"]))


if __name__ == "__main__":
    unittest.main()
