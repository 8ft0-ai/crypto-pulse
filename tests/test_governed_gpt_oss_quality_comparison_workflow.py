from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

import yaml

from llm_analysis import gpt_oss_quality_comparison as core
from llm_analysis import gpt_oss_quality_comparison_runner as runner

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/governed-gpt-oss-quality-comparison.yml"


class GovernedGPTOSSQualityComparisonWorkflowTests(unittest.TestCase):
    def test_workflow_is_manual_and_protected_tag_only(self) -> None:
        raw = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
        trigger = raw.get("on") if "on" in raw else raw.get(True)
        self.assertEqual(set(trigger), {"workflow_dispatch"})
        self.assertEqual(raw["permissions"], {"contents": "read"})
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("refs/tags/issueops/dispatch/", text)
        self.assertIn("github.workflow_sha", text)
        self.assertNotIn("issue_comment", text)
        self.assertNotIn("schedule:", text)
        self.assertNotIn("ref: main", text)

    def test_secret_free_guard_has_only_required_read_permissions(self) -> None:
        raw = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
        guard = raw["jobs"]["guard"]
        self.assertEqual(
            guard["permissions"],
            {"contents": "read", "actions": "read", "attestations": "read"},
        )
        self.assertIn("github.run_attempt == 1", str(guard["if"]))
        text = WORKFLOW.read_text(encoding="utf-8")
        guard_text = text.split("  prepare:", 1)[0]
        self.assertNotIn("OPENROUTER_API_KEY", guard_text)
        self.assertNotIn("environment: governed-llm-dry-run", guard_text)
        self.assertIn("issueops_dispatch.target_guard", guard_text)

    def test_pinned_attestation_verifier_contract_is_frozen(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("gh_2.97.0_linux_amd64.tar.gz", text)
        self.assertIn(
            "a2c9b8497e1f85b1ad0dfcb78b5a622e098801b8e461e459e88e1ee12f018112",
            text,
        )
        self.assertIn("sha256sum --check --strict", text)
        self.assertIn("gh version 2.97.0", text)

    def test_preparation_uses_exact_authorised_sha(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        prepare = text.split("  prepare:", 1)[1].split("  compare:", 1)[0]
        self.assertNotIn("OPENROUTER_API_KEY", prepare)
        self.assertIn("ref: ${{ github.sha }}", prepare)
        self.assertNotIn("ref: main", prepare)
        self.assertIn("test \"$sha\" = \"$GITHUB_SHA\"", prepare)

    def test_protected_execution_independently_rejects_reruns(self) -> None:
        raw = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
        compare = raw["jobs"]["compare"]
        condition = str(compare["if"])
        self.assertIn("github.run_attempt == 1", condition)
        self.assertIn("needs.guard.result == 'success'", condition)
        self.assertEqual(compare["environment"], "governed-llm-dry-run")
        text = WORKFLOW.read_text(encoding="utf-8")
        compare_text = text.split("  compare:", 1)[1]
        self.assertIn("OPENROUTER_API_KEY", compare_text)
        self.assertIn("test \"$TRUSTED_SHA\" = \"$GITHUB_SHA\"", compare_text)

    def test_workflow_has_no_repository_write_or_automatic_trigger(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        for prohibited in (
            "contents: write",
            "pull-requests: write",
            "git push",
            "gh pr",
            "repository_dispatch",
            "attestations: write",
            "actions: write",
        ):
            self.assertNotIn(prohibited, text)
        self.assertIn("gpt-oss-quality-comparison-prepared", text)
        self.assertIn(
            "gpt-oss-quality-comparison-${{ github.run_id }}", text
        )


class GovernedGPTOSSQualityComparisonRemediationTests(unittest.TestCase):
    def test_http_evidence_excludes_returned_reasoning_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "http-response.json"
            payload = {
                "raw_body_sha256": "a" * 64,
                "raw_body_utf8": json.dumps(
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": "{\"selected_candidate_ids\":[]}",
                                    "reasoning": "private chain of thought",
                                    "reasoning_details": [
                                        {"text": "private detail"}
                                    ],
                                }
                            }
                        ],
                        "usage": {
                            "completion_tokens_details": {
                                "reasoning_tokens": 42
                            }
                        },
                    }
                ),
            }
            with runner._patched_core_execution():
                core._write_json(path, payload)
            retained = json.loads(path.read_text(encoding="utf-8"))
            body = json.loads(retained["raw_body_utf8"])
            self.assertNotIn("reasoning", body["choices"][0]["message"])
            self.assertNotIn(
                "reasoning_details", body["choices"][0]["message"]
            )
            self.assertEqual(
                body["usage"]["completion_tokens_details"]["reasoning_tokens"],
                42,
            )
            self.assertTrue(retained["raw_body_reasoning_text_excluded"])
            self.assertTrue(retained["raw_body_reasoning_fields_removed"])
            self.assertEqual(retained["raw_body_sha256"], "a" * 64)

    def test_non_json_http_body_is_not_retained_as_text(self) -> None:
        retained, removed = runner._sanitise_raw_body(
            "unexpected provider reasoning text"
        )
        self.assertTrue(removed)
        self.assertNotIn("unexpected provider reasoning text", retained)
        self.assertIn("SHA-256", retained)

    def test_router_attempt_model_identity_is_terminal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            schedule = {
                "stage": "A",
                "case_key": "historical-degraded-sparse",
                "repeat_index": 1,
                "planned_order": 1,
            }
            call_dir = runner._call_dir(output, schedule)
            call_dir.mkdir(parents=True)
            core._write_json(
                call_dir / "interpreted-response.json",
                {
                    "requested_model": "openai/gpt-oss-120b",
                    "actual_model": "openai/gpt-oss-120b",
                    "cross_model_fallback_used": False,
                    "openrouter_metadata": {
                        "attempts": [
                            {
                                "provider": "DeepInfra",
                                "model": "openai/gpt-oss-20b",
                                "status": 200,
                            }
                        ]
                    },
                },
            )

            def completed(**_: object) -> dict[str, object]:
                return {
                    **schedule,
                    "classification": "completed",
                    "selected_candidate_ids": [],
                }

            original = core._execute_call
            core._execute_call = completed
            try:
                with runner._patched_core_execution():
                    result = core._execute_call(
                        output=output,
                        schedule=schedule,
                        prepared_case={
                            "useful_candidate_ids": [],
                            "key": "historical-degraded-sparse",
                        },
                        prepared_root=output,
                        plan=SimpleNamespace(model="openai/gpt-oss-120b"),
                    )
            finally:
                core._execute_call = original

            self.assertEqual(
                result["classification"], "infrastructure-failure"
            )
            self.assertEqual(
                result["failure_code"],
                "provider_attempt_model_identity_mismatch",
            )
            self.assertTrue(result["cross_model_fallback_used"])
            self.assertFalse(result["router_attempt_model_identity_preserved"])
            self.assertEqual(
                result["router_attempt_model"], "openai/gpt-oss-20b"
            )
            retained = json.loads(
                (call_dir / "result.json").read_text(encoding="utf-8")
            )
            self.assertEqual(retained, result)

    def test_unexpected_outer_failure_retains_exact_infrastructure_outcome(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            schedule = core._planned_schedule()
            first = schedule[0]
            call_dir = runner._call_dir(output, first)
            call_dir.mkdir(parents=True)
            core._write_json(
                call_dir / "result.json",
                {
                    **first,
                    "classification": "completed",
                    "selected_candidate_ids": ["candidate-1"],
                    "observed_cost_usd": 0.001,
                },
            )
            plan = SimpleNamespace(
                outcomes={
                    "infrastructure_failure": "inconclusive-infrastructure"
                },
                maximum_paid_calls=15,
                maximum_call_cost_usd=0.005,
                maximum_total_cost_usd=0.075,
            )
            summary = runner._write_unexpected_execution_summary(
                output=output,
                plan=plan,
                trusted_main_sha="a" * 40,
                schedule=schedule,
                message="simulated post-call scoring failure",
            )
            self.assertEqual(
                summary["outcome"], "inconclusive-infrastructure"
            )
            self.assertEqual(summary["status"], "partial-non-adjudicable")
            self.assertEqual(summary["completed_paid_calls"], 1)
            self.assertEqual(
                summary["failure_code"],
                "unexpected_protected_execution_failure",
            )
            records = json.loads(
                (output / core.RECORDS_FILE).read_text(encoding="utf-8")
            )
            self.assertEqual(len(records["records"]), 1)
            self.assertTrue((output / core.REVIEWER_CSV).is_file())
            self.assertTrue((output / core.DECISION_INPUT).is_file())


if __name__ == "__main__":
    unittest.main()
