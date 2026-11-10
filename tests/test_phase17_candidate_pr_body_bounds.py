from __future__ import annotations

import inspect
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import trusted_main_source_evidence_candidate as candidate


class Phase17CandidatePrBodyBoundsTests(unittest.TestCase):
    def _manifest(self, recoveries):
        return {
            "base_sha": "1" * 40,
            "base_tree_sha": "2" * 40,
            "candidate_id": "3" * 64,
            "anchor_observation_hour_utc": "2026-08-20T00:00:00Z",
            "window": {
                "start_utc": "2026-08-20T01:00:00Z",
                "end_utc": "2026-08-21T01:00:00Z",
            },
            "added_paths": [],
            "applied_recovery_decisions": recoveries,
            "blocking_findings": [],
            "hours": [],
        }

    def _evidence(self):
        return {
            "workflow_run_id": 33171111714,
            "workflow_run_attempt": 1,
            "prepared_artifact_name": "trusted-main-source-evidence-candidate-33171111714-1",
            "expected_main_sha": "1" * 40,
            "source_population_closure_sha256": "4" * 64,
        }

    def _recoveries(self):
        rows = []
        for index in range(351):
            blocker_class = (
                "duplicate-observation-hour"
                if index >= 348
                else "source-input-unverifiable"
            )
            rows.append(
                {
                    "blocker_class": blocker_class,
                    "blocker_fingerprint": f"{index:064x}",
                    "carrier": {
                        "comment_id": 5446661525 + index,
                        "body_sha256": f"{index + 1:064x}",
                    },
                }
            )
        return rows

    def test_351_recoveries_are_summarised_deterministically_below_safe_limit(self):
        manifest = self._manifest(self._recoveries())
        evidence = self._evidence()
        commit_sha = "5" * 40

        first = candidate.render_pr_body(manifest, evidence, commit_sha)
        second = candidate.render_pr_body(manifest, evidence, commit_sha)

        self.assertEqual(first, second)
        self.assertLess(candidate.PR_BODY_SAFE_MAX_CHARS, 65_536)
        self.assertLessEqual(len(first), candidate.PR_BODY_SAFE_MAX_CHARS)
        self.assertIn("Applied recovery count: `351`", first)
        self.assertIn("`source-input-unverifiable=348`", first)
        self.assertIn("`duplicate-observation-hour=3`", first)
        self.assertIn(evidence["prepared_artifact_name"], first)
        self.assertIn(manifest["candidate_id"], first)
        self.assertNotIn("comment `5446661525` / class", first)

    def test_body_over_safe_limit_fails_closed(self):
        manifest = self._manifest([])
        manifest["anchor_observation_hour_utc"] = "x" * 61_000

        with self.assertRaises(candidate.CandidateError):
            candidate.render_pr_body(manifest, self._evidence(), "5" * 40)

    def test_public_main_preserves_existing_zero_argument_cli_contract(self):
        self.assertEqual(list(inspect.signature(candidate.main).parameters), [])


if __name__ == "__main__":
    unittest.main()
