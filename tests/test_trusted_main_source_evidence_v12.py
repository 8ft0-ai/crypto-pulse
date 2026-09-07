from __future__ import annotations

import hashlib
import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import trusted_main_source_evidence_accumulation as legacy  # noqa: E402
import trusted_main_source_evidence_accumulation_v12 as accumulation  # noqa: E402
import trusted_main_source_evidence_candidate_v12 as candidate  # noqa: E402


ANCHOR = "2026-08-22T05:00:00Z"
BASE_SHA = "1" * 40
BASE_TREE = "2" * 40


def hour(offset: int) -> str:
    base = datetime.fromisoformat(ANCHOR.replace("Z", "+00:00"))
    return (base + timedelta(hours=offset)).strftime("%Y-%m-%dT%H:00:00Z")


class AccumulationV12Tests(unittest.TestCase):
    def source(
        self,
        run_id: int,
        attempt: int = 1,
        *,
        conclusion: str = "success",
        event: str = "schedule",
        raw: bytes | None = b"snapshot\n",
    ) -> dict[str, object]:
        return {
            "repository": accumulation.EXPECTED_REPOSITORY,
            "workflow_path": accumulation.EXPECTED_WORKFLOW_PATH,
            "workflow_id": 111,
            "event": event,
            "conclusion": conclusion,
            "run_id": run_id,
            "run_attempt": attempt,
            "workflow_head_sha": "a" * 40,
            "artifact_name": f"deterministic-publication-intent-{run_id}-{attempt}",
            "publication_intent_bytes": b"{}" if raw is not None else None,
            "snapshot_bytes": raw,
        }

    def verified(
        self,
        source: dict[str, object],
        observation_hour: str,
        *,
        raw: bytes = b"snapshot\n",
        path: str | None = None,
    ) -> dict[str, object]:
        run_id = int(source["run_id"])
        attempt = int(source["run_attempt"])
        path = path or f"data/crypto/hourly/2026/09/07/{run_id:06d}_AEST_source_snapshot.json"
        return {
            "input_identity": legacy._identity(source),
            "workflow_id": int(source["workflow_id"]),
            "run_id": run_id,
            "run_attempt": attempt,
            "workflow_head_sha": source["workflow_head_sha"],
            "artifact_name": source["artifact_name"],
            "publication_intent_sha256": hashlib.sha256(
                source["publication_intent_bytes"]
            ).hexdigest(),
            "snapshot_sha256": hashlib.sha256(raw).hexdigest(),
            "snapshot_git_blob_sha": legacy.git_blob_sha(raw),
            "snapshot_commit_sha": "b" * 40,
            "snapshot_path": path,
            "canonical_observation_hour_utc": observation_hour,
            "quality_status": "valid-ok",
            "snapshot_bytes": raw,
        }

    def build(
        self,
        sources: list[dict[str, object]],
        verified: list[dict[str, object]],
        *,
        recoveries: list[dict[str, object]] | None = None,
        trusted_by_path: dict[str, bytes | None] | None = None,
    ) -> dict[str, object]:
        verified_by_key = {
            (int(row["run_id"]), int(row["run_attempt"])): row for row in verified
        }

        def verify(
            repository_root: Path,
            base_sha: str,
            config: dict[str, object],
            source: dict[str, object],
        ) -> dict[str, object]:
            key = (int(source["run_id"]), int(source["run_attempt"]))
            if key not in verified_by_key:
                raise ValueError("publication_intent_bytes must be exact bytes")
            return dict(verified_by_key[key])

        def git_bytes(repository_root: Path, sha: str, path: str) -> bytes | None:
            if trusted_by_path is None:
                return None
            return trusted_by_path.get(path)

        with (
            mock.patch.object(legacy, "_require_exact_commit", return_value=(BASE_SHA, BASE_TREE)),
            mock.patch.object(legacy, "_load_base_config", return_value={}),
            mock.patch.object(legacy, "_resolve_anchor", return_value=ANCHOR),
            mock.patch.object(legacy, "_verify_source", side_effect=verify),
            mock.patch.object(legacy, "_git_bytes_at", side_effect=git_bytes),
        ):
            return accumulation.build_accumulation_manifest(
                Path("."),
                BASE_SHA,
                sources,
                recoveries or [],
                [523],
            )

    def recovery_for(self, blocker: dict[str, object], comment_id: int = 9001) -> dict[str, object]:
        body = {
            "contract": legacy.RECOVERY_CONTRACT,
            "repository": legacy.EXPECTED_REPOSITORY,
            "disposition": legacy.RECOVERY_DISPOSITION,
            "prohibitions": list(legacy.RECOVERY_PROHIBITIONS),
            "blocker_class": blocker["blocker_class"],
            "blocker_fingerprint": blocker["blocker_fingerprint"],
            "canonical_observation_hour_utc": blocker["canonical_observation_hour_utc"],
            "input_identities": blocker["input_identities"],
            "reason": "owner terminal exclusion for deterministic v1.2 test",
        }
        return {
            "issue_number": 523,
            "comment_id": comment_id,
            "author_login": legacy.OWNER_LOGIN,
            "body_bytes": legacy.canonical_json_bytes(body),
        }

    def test_stranded_gap_reaches_later_genuine_observations_without_inventing_hours(self) -> None:
        a = self.source(101)
        b = self.source(102)
        manifest = self.build(
            [a, b],
            [self.verified(a, hour(72)), self.verified(b, hour(96))],
        )
        self.assertEqual(manifest["contract"], accumulation.CONTRACT)
        self.assertEqual(
            manifest["selection"]["selected_hours_utc"], [hour(72), hour(96)]
        )
        self.assertEqual(
            [row["canonical_observation_hour_utc"] for row in manifest["hours"]],
            [hour(72), hour(96)],
        )
        self.assertNotIn(hour(1), [row["canonical_observation_hour_utc"] for row in manifest["hours"]])
        self.assertEqual(len(manifest["added_paths"]), 2)

    def test_selects_exactly_earliest_25_observations(self) -> None:
        sources = [self.source(200 + offset) for offset in range(30)]
        verified = [
            self.verified(source, hour(offset + 1))
            for offset, source in enumerate(sources)
        ]
        manifest = self.build(sources, verified)
        self.assertEqual(len(manifest["added_paths"]), 25)
        self.assertEqual(
            manifest["selection"]["selected_hours_utc"],
            [hour(offset) for offset in range(1, 26)],
        )
        dispositions = {
            row["canonical_observation_hour_utc"]: row["disposition"]
            for row in manifest["hours"]
        }
        self.assertEqual(dispositions[hour(25)], "selected")
        self.assertEqual(dispositions[hour(26)], "eligible-deferred")

    def test_market_content_does_not_change_chronological_selection(self) -> None:
        a = self.source(301)
        b = self.source(302)
        first = self.build(
            [a, b],
            [
                self.verified(a, hour(5), raw=b'{"BTC":1}\n'),
                self.verified(b, hour(8), raw=b'{"BTC":999}\n'),
            ],
        )
        second = self.build(
            [a, b],
            [
                self.verified(a, hour(5), raw=b'{"BTC":999999}\n'),
                self.verified(b, hour(8), raw=b'{"BTC":0}\n'),
            ],
        )
        self.assertEqual(
            first["selection"]["selected_hours_utc"],
            second["selection"]["selected_hours_utc"],
        )

    def test_duplicate_hour_has_no_winner(self) -> None:
        a = self.source(401)
        b = self.source(402)
        manifest = self.build(
            [a, b],
            [
                self.verified(a, hour(10), raw=b"a"),
                self.verified(b, hour(10), raw=b"b"),
            ],
        )
        self.assertEqual(manifest["added_paths"], [])
        self.assertEqual(
            [row["blocker_class"] for row in manifest["blocking_findings"]],
            ["duplicate-observation-hour"],
        )
        self.assertEqual(manifest["hours"][0]["disposition"], "duplicate")

    def test_duplicate_recovery_excludes_whole_set_and_leaves_gap(self) -> None:
        a = self.source(411)
        b = self.source(412)
        later = self.source(413)
        initial = self.build(
            [a, b, later],
            [
                self.verified(a, hour(10), raw=b"a"),
                self.verified(b, hour(10), raw=b"b"),
                self.verified(later, hour(11), raw=b"later"),
            ],
        )
        blocker = initial["blocking_findings"][0]
        recovered = self.build(
            [a, b, later],
            [
                self.verified(a, hour(10), raw=b"a"),
                self.verified(b, hour(10), raw=b"b"),
                self.verified(later, hour(11), raw=b"later"),
            ],
            recoveries=[self.recovery_for(blocker)],
        )
        self.assertFalse(recovered["blocking_findings"])
        self.assertEqual(
            recovered["hours"][0]["disposition"], "terminal-excluded"
        )
        self.assertEqual(
            recovered["selection"]["selected_hours_utc"], [hour(11)]
        )

    def test_null_hour_unavailable_input_blocks_until_exact_recovery(self) -> None:
        expired = self.source(501, raw=None)
        later = self.source(502)
        initial = self.build(
            [expired, later],
            [self.verified(later, hour(100), raw=b"later")],
        )
        self.assertEqual(initial["added_paths"], [])
        blocker = initial["blocking_findings"][0]
        self.assertEqual(blocker["blocker_class"], "source-input-unverifiable")
        self.assertIsNone(blocker["canonical_observation_hour_utc"])

        recovered = self.build(
            [expired, later],
            [self.verified(later, hour(100), raw=b"later")],
            recoveries=[self.recovery_for(blocker)],
        )
        self.assertFalse(recovered["blocking_findings"])
        self.assertEqual(
            recovered["selection"]["selected_hours_utc"], [hour(100)]
        )
        self.assertNotIn(
            None,
            [row["canonical_observation_hour_utc"] for row in recovered["hours"]],
        )

    def test_later_failed_attempt_does_not_erase_earlier_success(self) -> None:
        success = self.source(601, attempt=1)
        failed = self.source(601, attempt=2, conclusion="failure")
        manifest = self.build(
            [success, failed],
            [self.verified(success, hour(20))],
        )
        self.assertEqual(
            manifest["selection"]["selected_hours_utc"], [hour(20)]
        )
        self.assertEqual(
            [row["kind"] for row in manifest["operational_diagnostics"]],
            ["non-success-input"],
        )

    def test_trusted_path_conflict_remains_hard_blocker(self) -> None:
        source = self.source(701)
        verified = self.verified(source, hour(30), raw=b"new")
        manifest = self.build(
            [source],
            [verified],
            trusted_by_path={verified["snapshot_path"]: b"old"},
        )
        self.assertEqual(manifest["added_paths"], [])
        self.assertEqual(
            manifest["blocking_findings"][0]["blocker_class"],
            "trusted-path-conflict",
        )

    def test_already_trusted_exact_bytes_are_not_readded(self) -> None:
        source = self.source(702)
        verified = self.verified(source, hour(31), raw=b"same")
        manifest = self.build(
            [source],
            [verified],
            trusted_by_path={verified["snapshot_path"]: b"same"},
        )
        self.assertFalse(manifest["blocking_findings"])
        self.assertEqual(manifest["added_paths"], [])
        self.assertEqual(manifest["hours"][0]["disposition"], "already-trusted")

    def test_one_candidate_path_cannot_claim_multiple_hours(self) -> None:
        a = self.source(801)
        b = self.source(802)
        shared = "data/crypto/hourly/2026/09/07/shared_source_snapshot.json"
        manifest = self.build(
            [a, b],
            [
                self.verified(a, hour(40), raw=b"a", path=shared),
                self.verified(b, hour(41), raw=b"b", path=shared),
            ],
        )
        self.assertEqual(manifest["added_paths"], [])
        self.assertEqual(
            manifest["blocking_findings"][0]["blocker_class"],
            "candidate-path-identity-conflict",
        )


class CandidatePopulationV12Tests(unittest.TestCase):
    def attempt(
        self,
        run_id: int,
        attempt: int,
        created_at: str,
        *,
        conclusion: str = "success",
    ) -> dict[str, object]:
        return {
            "id": run_id,
            "run_attempt": attempt,
            "workflow_id": 111,
            "event": "schedule",
            "status": "completed",
            "conclusion": conclusion,
            "head_sha": "a" * 40,
            "head_branch": "main",
            "created_at": created_at,
            "run_started_at": created_at,
            "updated_at": created_at,
        }

    def source_run(
        self,
        run_id: int,
        created_at: str,
        *,
        attempts: int = 1,
        discovery: list[str] | None = None,
    ) -> dict[str, object]:
        rows = [
            self.attempt(
                run_id,
                number,
                created_at,
                conclusion="success" if number == 1 else "failure",
            )
            for number in range(1, attempts + 1)
        ]
        return {
            "run_id": run_id,
            "latest_run_attempt": attempts,
            "discovery_sources": discovery or ["census"],
            "attempts": rows,
            "artifacts": [],
        }

    def capture(self, runs: list[dict[str, object]], *, extensions: list[int] | None = None) -> dict[str, object]:
        return {
            "repository": candidate.EXPECTED_REPOSITORY,
            "workflow_path": candidate.EXPECTED_WORKFLOW_PATH,
            "workflow_id": 111,
            "expected_main_sha": BASE_SHA,
            "census": {
                "start_utc": "2026-07-22T05:00:00Z",
                "end_utc": "2026-09-07T05:16:21Z",
            },
            "retained_artifact_extension_run_ids": extensions or [],
            "runs": runs,
        }

    def test_census_bounds_are_anchor_minus_31_days_to_exact_candidate_created_at(self) -> None:
        bounds = candidate.census_bounds(
            ANCHOR, "2026-09-07T05:16:21Z"
        )
        self.assertEqual(bounds["start_utc"], "2026-07-22T05:00:00Z")
        self.assertEqual(bounds["end_utc"], "2026-09-07T05:16:21Z")

    def test_retained_extension_cannot_admit_post_c_end_run(self) -> None:
        after = self.source_run(
            900,
            "2026-09-07T05:17:00Z",
            discovery=["retained-artifact-extension"],
        )
        closure = candidate.build_source_population_closure(
            self.capture([after], extensions=[900])
        )
        self.assertEqual(closure["discovered_run_ids"], [])
        self.assertEqual(closure["retained_artifact_extension_run_ids"], [])

    def test_pre_c_start_retained_extension_is_conservatively_admitted(self) -> None:
        old = self.source_run(
            901,
            "2026-07-20T00:00:00Z",
            discovery=["retained-artifact-extension"],
        )
        closure = candidate.build_source_population_closure(
            self.capture([old], extensions=[901])
        )
        self.assertEqual(closure["discovered_run_ids"], [901])
        self.assertEqual(
            closure["runs"][0]["source_run_created_at_utc"],
            "2026-07-20T00:00:00Z",
        )

    def test_new_rerun_attempt_changes_second_pass_closure(self) -> None:
        prepared_capture = self.capture(
            [self.source_run(902, "2026-09-01T00:00:00Z", attempts=1)]
        )
        current_capture = self.capture(
            [self.source_run(902, "2026-09-01T00:00:00Z", attempts=2)]
        )
        prepared = candidate.build_source_population_closure(prepared_capture)
        current = candidate.build_source_population_closure(current_capture)
        self.assertNotEqual(prepared["sha256"], current["sha256"])

    def test_workflow_retention_is_exactly_35_days_and_no_staging_carrier(self) -> None:
        ingestion = (
            ROOT / ".github/workflows/ingest-crypto-sources.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("retention-days: 35", ingestion)
        self.assertNotIn("automation/source-evidence-staging", ingestion)
        self.assertNotIn("source-evidence-staging-carrier", ingestion)


if __name__ == "__main__":
    unittest.main()
