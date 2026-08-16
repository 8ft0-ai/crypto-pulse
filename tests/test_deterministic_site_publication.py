from __future__ import annotations

import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "deterministic_site_publication.py"
)
SPEC = importlib.util.spec_from_file_location(
    "deterministic_site_publication", MODULE_PATH
)
assert SPEC and SPEC.loader
publication = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = publication
SPEC.loader.exec_module(publication)

FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "deterministic_site_publication_v3.json"
)


class DeterministicSitePublicationTests(unittest.TestCase):
    def setUp(self) -> None:
        payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
        self.attestation = payload["attestation"]
        self.facts = payload["facts"]

    def decision(self, *, attestation=None, facts=None):
        return publication.evaluate_gate(
            self.attestation if attestation is None else attestation,
            self.facts if facts is None else facts,
        )

    def mutate_fact(self, *path, value):
        facts = copy.deepcopy(self.facts)
        cursor = facts
        for key in path[:-1]:
            cursor = cursor[key]
        cursor[path[-1]] = value
        return facts

    def assert_refused(self, decision, fragment: str) -> None:
        self.assertFalse(decision.eligible)
        self.assertTrue(
            any(fragment in reason for reason in decision.reasons),
            decision.reasons,
        )

    def source_intent(self) -> dict[str, object]:
        return {
            "publication_contract": publication.CONTRACT,
            "source_workflow_id": 273000001,
            "source_workflow_path": publication.EXPECTED_SOURCE_WORKFLOW_PATH,
            "source_workflow_run_id": 54321,
            "source_workflow_run_attempt": 1,
            "source_workflow_head_sha": "a" * 40,
            "main_base_sha": "a" * 40,
            "snapshot_commit_sha": "d" * 40,
            "snapshot_path": self.attestation["snapshot_path"],
            "snapshot_sha256": self.attestation["snapshot_sha256"],
            "generated_at_utc": "2026-08-17T00:17:00Z",
            "observation_hour_utc": "2026-08-17T00:00:00Z",
            "observation_hour_compact": "20260817T0000Z",
            "snapshot_quality": "valid-ok",
            "blocking_issues": [],
            "non_blocking_warnings": [],
            "warnings": [],
            "errors": [],
            "automatic_eligible": True,
            "refusal_reasons": [],
        }

    def test_positive_recurring_gate(self):
        decision = self.decision()
        self.assertTrue(decision.eligible, decision.reasons)
        self.assertEqual((), decision.reasons)

    def test_disabled_and_unknown_activation_refuse(self):
        self.assert_refused(
            self.decision(
                facts=self.mutate_fact("activation", value="disabled")
            ),
            "activation is disabled",
        )
        self.assertEqual(
            "disabled", publication.normalise_activation("unexpected")
        )
        self.assert_refused(
            self.decision(
                facts=self.mutate_fact("activation", value="unexpected")
            ),
            "activation is disabled",
        )

    def test_pilot_is_bound_to_source_ingestion_run(self):
        facts = self.mutate_fact("activation", value="pilot")
        facts["pilot_run_id"] = "12345"
        self.assert_refused(
            self.decision(facts=facts), "pilot activation"
        )
        facts["pilot_run_id"] = "54321"
        self.assertTrue(self.decision(facts=facts).eligible)

    def test_degraded_blocking_warning_and_error_evidence_refuse(self):
        variants = [
            (("snapshot", "quality_status"), "valid-degraded", "not valid-ok"),
            (("snapshot", "blocking_issues"), ["missing"], "blocking issues"),
            (("snapshot", "non_blocking_warnings"), ["warning"], "quality warnings"),
            (("snapshot", "warnings"), ["warning"], "records warnings"),
            (("snapshot", "errors"), ["error"], "records errors"),
        ]
        for path, value, fragment in variants:
            with self.subTest(path=path):
                self.assert_refused(
                    self.decision(
                        facts=self.mutate_fact(*path, value=value)
                    ),
                    fragment,
                )

    def test_noncanonical_observation_hour_refuses(self):
        self.assert_refused(
            self.decision(
                facts=self.mutate_fact(
                    "snapshot",
                    "observation_hour_utc",
                    value="2026-08-17T00:01:00Z",
                )
            ),
            "start of a UTC hour",
        )

    def test_generation_workflow_identity_is_bound(self):
        variants = [
            (("generation_run", "id"), 12346, "generation run id"),
            (("generation_run", "run_attempt"), 2, "run attempt"),
            (("generation_run", "workflow_id"), 1, "workflow id"),
            (("generation_run", "path"), ".github/workflows/other.yml", "workflow path"),
            (("generation_run", "head_branch"), "feature", "default branch"),
            (("generation_run", "event"), "schedule", "event is not trusted"),
            (("generation_run", "head_sha"), "e" * 40, "head/base"),
            (("generation_run", "conclusion"), "failure", "did not succeed"),
        ]
        for path, value, fragment in variants:
            with self.subTest(path=path):
                self.assert_refused(
                    self.decision(
                        facts=self.mutate_fact(*path, value=value)
                    ),
                    fragment,
                )

    def test_candidate_head_mutation_refuses(self):
        self.assert_refused(
            self.decision(
                facts=self.mutate_fact("pr", "head_sha", value="e" * 40)
            ),
            "head changed",
        )

    def test_wrong_pr_branch_number_app_and_shape_refuse(self):
        variants = [
            (("pr", "number"), 601, "number mismatch"),
            (("pr", "head_ref"), "automation/deterministic-publication-999-1-20260817T0000Z", "branch mismatch"),
            (("pr", "author_id"), 111, "actor id mismatch"),
            (("pr", "author_login"), "someone-else[bot]", "actor login mismatch"),
            (("pr", "base"), "other", "base is not main"),
            (("pr", "same_repository"), False, "not same-repository"),
            (("pr", "draft"), True, "is draft"),
            (("pr", "open"), False, "is not open"),
        ]
        for path, value, fragment in variants:
            with self.subTest(path=path):
                self.assert_refused(
                    self.decision(
                        facts=self.mutate_fact(*path, value=value)
                    ),
                    fragment,
                )

    def test_snapshot_and_report_hash_mismatch_refuse(self):
        self.assert_refused(
            self.decision(
                facts=self.mutate_fact(
                    "snapshot", "sha256", value="0" * 64
                )
            ),
            "snapshot hash mismatch",
        )
        self.assert_refused(
            self.decision(
                facts=self.mutate_fact(
                    "report", "sha256", value="0" * 64
                )
            ),
            "report hash mismatch",
        )

    def test_attestation_must_be_unique_and_not_expired(self):
        for count in (0, 2):
            self.assert_refused(
                self.decision(
                    facts=self.mutate_fact(
                        "attestation_count", value=count
                    )
                ),
                "exactly one",
            )
        self.assert_refused(
            self.decision(
                facts=self.mutate_fact(
                    "attestation_expired", value=True
                )
            ),
            "expired",
        )

    def test_exact_two_file_scope_rejects_extra_and_site_paths(self):
        facts = copy.deepcopy(self.facts)
        facts["changed_files"].append("README.md")
        self.assert_refused(
            self.decision(facts=facts), "exactly its snapshot JSON"
        )
        facts = copy.deepcopy(self.facts)
        facts["changed_files"][1] = "_site/latest.html"
        self.assert_refused(
            self.decision(facts=facts), "exactly its snapshot JSON"
        )

    def test_duplicate_observation_hour_refuses(self):
        self.assert_refused(
            self.decision(
                facts=self.mutate_fact(
                    "duplicate_publication_count", value=1
                )
            ),
            "already published",
        )

    def test_validation_must_be_exact_head_success_from_github_actions(self):
        variants = [
            (("validation", "workflow_name"), "Other", "workflow identity"),
            (("validation", "conclusion"), "failure", "did not succeed"),
            (("validation", "head_sha"), "e" * 40, "validated head"),
            (("validation", "check_name"), "Other", "check name"),
            (("validation", "check_conclusion"), "failure", "check did not succeed"),
            (("validation", "check_app_slug"), "untrusted", "check source"),
            (("validation", "pending_required_checks"), 1, "remains pending"),
            (("validation", "failed_required_checks"), 1, "check failed"),
        ]
        for path, value, fragment in variants:
            with self.subTest(path=path):
                self.assert_refused(
                    self.decision(
                        facts=self.mutate_fact(*path, value=value)
                    ),
                    fragment,
                )

    def test_stale_main_after_validation_refuses(self):
        self.assert_refused(
            self.decision(
                facts=self.mutate_fact("current_main_sha", value="e" * 40)
            ),
            "current main advanced",
        )

    def test_unresolved_thread_and_blocking_review_refuse(self):
        self.assert_refused(
            self.decision(
                facts=self.mutate_fact("unresolved_threads", value=1)
            ),
            "unresolved review threads",
        )
        self.assert_refused(
            self.decision(
                facts=self.mutate_fact("blocking_reviews", value=1)
            ),
            "blocking reviews",
        )

    def test_gate_paginates_reviews_beyond_first_100(self):
        workflow = (
            Path(__file__).resolve().parents[1]
            / ".github"
            / "workflows"
            / "deterministic-site-publication-gate.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("gh api --paginate --slurp \\", workflow)
        self.assertIn(
            '"/repos/$GITHUB_REPOSITORY/pulls/$PR_NUMBER/reviews?per_page=100"',
            workflow,
        )
        self.assertIn("| jq 'add // []' > \"$WORK/reviews.json\"", workflow)
        self.assertNotIn(
            'gh api "/repos/$GITHUB_REPOSITORY/pulls/$PR_NUMBER/reviews?per_page=100" >',
            workflow,
        )

    def test_gate_fails_closed_when_review_threads_exceed_first_100(self):
        workflow = (
            Path(__file__).resolve().parents[1]
            / ".github"
            / "workflows"
            / "deterministic-site-publication-gate.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("reviewThreads(first:100){totalCount pageInfo{hasNextPage}", workflow)
        self.assertIn("(.pageInfo.hasNextPage == false)", workflow)
        self.assertIn("(.totalCount == (.nodes | length))", workflow)
        self.assertIn(
            "Review thread metadata is incomplete; refusing publication eligibility.",
            workflow,
        )

    def test_branch_identity_round_trip(self):
        branch = publication.publication_branch(
            12345, 1, "2026-08-17T00:00:00Z"
        )
        self.assertEqual(self.attestation["candidate_branch"], branch)
        identity = publication.parse_publication_branch(branch)
        self.assertEqual(12345, identity["generation_workflow_run_id"])
        self.assertEqual(1, identity["generation_workflow_run_attempt"])
        self.assertEqual(
            "2026-08-17T00:00:00Z", identity["observation_hour_utc"]
        )
        with self.assertRaises(publication.PublicationPolicyError):
            publication.parse_publication_branch(
                "automation/deterministic-publication-latest"
            )

    def test_candidate_scope_rejects_path_traversal(self):
        with self.assertRaises(publication.PublicationPolicyError):
            publication.validate_candidate_scope(
                [
                    "data/crypto/hourly/../../secret.json",
                    self.attestation["report_path"],
                ],
                "data/crypto/hourly/../../secret.json",
                self.attestation["report_path"],
            )

    def test_source_intent_requires_valid_ok_no_warning_error_and_canonical_hour(self):
        snapshot = {
            "run": {
                "generated_at_utc": "2026-08-17T00:17:00Z",
                "observation_hour_utc": "2026-08-17T00:00:00Z",
            },
            "warnings": [],
            "errors": [],
        }
        quality = {
            "status": "valid-ok",
            "blocking_issues": [],
            "non_blocking_warnings": [],
        }
        intent = publication.build_publication_intent(
            snapshot=snapshot,
            snapshot_path=self.attestation["snapshot_path"],
            snapshot_sha256=self.attestation["snapshot_sha256"],
            snapshot_commit_sha=self.attestation["snapshot_commit_sha"],
            main_base_sha=self.attestation["main_base_sha"],
            source_workflow_id=273000001,
            source_workflow_run_id=54321,
            source_workflow_run_attempt=1,
            source_workflow_head_sha=self.attestation["main_base_sha"],
            quality=quality,
        )
        self.assertTrue(intent["automatic_eligible"])
        snapshot["warnings"] = ["warning"]
        intent = publication.build_publication_intent(
            snapshot=snapshot,
            snapshot_path=self.attestation["snapshot_path"],
            snapshot_sha256=self.attestation["snapshot_sha256"],
            snapshot_commit_sha=self.attestation["snapshot_commit_sha"],
            main_base_sha=self.attestation["main_base_sha"],
            source_workflow_id=273000001,
            source_workflow_run_id=54321,
            source_workflow_run_attempt=1,
            source_workflow_head_sha=self.attestation["main_base_sha"],
            quality=quality,
        )
        self.assertFalse(intent["automatic_eligible"])

    def test_verify_intent_detects_tamper_and_wrong_triggering_source(self):
        payload = b"snapshot-bytes\n"
        intent = self.source_intent()
        intent["snapshot_sha256"] = publication.sha256_bytes(payload)
        publication.verify_publication_intent(
            intent,
            payload,
            expected_main_base_sha="a" * 40,
            expected_source_workflow_id=273000001,
            expected_source_run_id=54321,
            expected_source_run_attempt=1,
        )
        with self.assertRaises(publication.PublicationPolicyError):
            publication.verify_publication_intent(
                intent,
                b"tampered\n",
                expected_main_base_sha="a" * 40,
                expected_source_workflow_id=273000001,
                expected_source_run_id=54321,
                expected_source_run_attempt=1,
            )
        with self.assertRaises(publication.PublicationPolicyError):
            publication.verify_publication_intent(
                intent,
                payload,
                expected_main_base_sha="a" * 40,
                expected_source_workflow_id=273000001,
                expected_source_run_id=99999,
                expected_source_run_attempt=1,
            )

    def test_attestation_build_binds_separate_source_and_generation_runs(self):
        built = publication.build_attestation(
            intent=self.source_intent(),
            report_path=self.attestation["report_path"],
            report_sha256=self.attestation["report_sha256"],
            generation_workflow_id=274000001,
            generation_workflow_run_id=12345,
            generation_workflow_run_attempt=1,
            generation_workflow_head_sha="a" * 40,
            candidate_branch=self.attestation["candidate_branch"],
            candidate_head_sha="b" * 40,
            pull_request_number=600,
            publication_app_actor_id=987654,
            publication_app_slug="cryptopulse-deterministic-publication",
        )
        publication.validate_attestation_shape(built)
        self.assertEqual(12345, built["generation_workflow_run_id"])
        self.assertEqual(54321, built["source_workflow_run_id"])
        self.assertEqual(
            publication.EXPECTED_GENERATION_WORKFLOW_PATH,
            built["generation_workflow_path"],
        )

    def test_source_and_generation_heads_must_equal_attested_main(self):
        attestation = copy.deepcopy(self.attestation)
        attestation["source_workflow_head_sha"] = "e" * 40
        self.assert_refused(
            self.decision(attestation=attestation), "source head/base"
        )
        attestation = copy.deepcopy(self.attestation)
        attestation["generation_workflow_head_sha"] = "e" * 40
        self.assert_refused(
            self.decision(attestation=attestation), "generation head/base"
        )

    def test_canonical_json_is_byte_stable_and_key_order_independent(self):
        left = {"z": 1, "a": {"b": 2, "a": 1}}
        right = {"a": {"a": 1, "b": 2}, "z": 1}
        self.assertEqual(
            publication.canonical_json_bytes(left),
            publication.canonical_json_bytes(right),
        )
        self.assertEqual(
            publication.canonical_json_sha256(left),
            publication.canonical_json_sha256(right),
        )

    def test_count_observation_hour_is_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data = root / "data" / "crypto" / "hourly" / "2026" / "08" / "17"
            data.mkdir(parents=True)
            (data / "a.json").write_text(
                json.dumps(
                    {
                        "run": {
                            "observation_hour_utc": "2026-08-17T00:00:00Z"
                        }
                    }
                ),
                encoding="utf-8",
            )
            (data / "b.json").write_text(
                json.dumps(
                    {
                        "run": {
                            "observation_hour_utc": "2026-08-17T01:00:00Z"
                        }
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                1,
                publication.count_observation_hour(
                    root, "2026-08-17T00:00:00Z"
                ),
            )


if __name__ == "__main__":
    unittest.main()
