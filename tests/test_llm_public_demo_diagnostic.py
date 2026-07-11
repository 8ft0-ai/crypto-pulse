from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path

from llm_analysis import paid_benchmark
from llm_analysis.evaluation import RunRecord
from llm_analysis.public_demo_diagnostic import (
    DIAGNOSTIC_SUMMARY_FILE,
    _can_continue_after_smoke,
    _continuation_proxy,
    _execute_paid_diagnostic,
    _force_diagnostic_only,
)

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "governed-gpt4o-mini-public-demo.yml"


def record(
    *,
    status: str = "rejected",
    hard_pass: bool = False,
    failure_code: str | None = "analysis_rejected",
    case_key: str = "historical-normal-crosschecked",
    repeat: int = 1,
    output_dir: str = "stages/smoke/runs/gpt-4o-mini/historical-normal-crosschecked/repeat-1",
    complete: bool = True,
) -> RunRecord:
    return RunRecord(
        model_key="gpt-4o-mini",
        requested_model="openai/gpt-4o-mini",
        case_key=case_key,
        repeat=repeat,
        status=status,
        hard_pass=hard_pass,
        failure_code=failure_code,
        validation={
            "valid": hard_pass,
            "diagnostics": []
            if hard_pass
            else [
                {
                    "stage": "value",
                    "code": "untraceable_number",
                    "path": "$.analysis.headline.text",
                    "message": "test diagnostic",
                }
            ],
        },
        actual_model="openai/gpt-4o-mini" if complete else None,
        actual_provider="OpenAI" if complete else None,
        provider_fallback_used=False if complete else None,
        cross_model_fallback_used=False if complete else None,
        latency_ms=1000 if complete else None,
        input_tokens=8000 if complete else None,
        output_tokens=1000 if complete else None,
        total_tokens=9000 if complete else None,
        estimated_cost_usd=0.002 if complete else None,
        generation_id="gen-test" if complete else None,
        analysis_sha256="a" * 64 if hard_pass else None,
        completion_sha256="b" * 64 if complete else None,
        readability_proxy=4.0 if hard_pass else None,
        usefulness_proxy=4.0 if hard_pass else None,
        claim_count=5 if hard_pass else None,
        evidence_reference_count=8 if hard_pass else None,
        output_dir=output_dir,
    )


def base_summary() -> dict:
    return {
        "decision": {"decision": "retain", "selected_model": "openai/gpt-4o-mini"},
        "model_results": [
            {
                "model": "openai/gpt-4o-mini",
                "disqualified": False,
                "hard_passes": 10,
                "required_runs": 10,
            }
        ],
        "paid_benchmark": {
            "total_cost_usd": 0.03,
            "cost_metadata_complete_for_qualification": True,
            "experiment_cost_ceiling_exceeded": False,
        },
        "viability": {
            "completed_logical_calls": 12,
            "http_attempts": 12,
            "smoke_passes": 1,
            "full_corpus_finalists": ["gpt-4o-mini"],
            "stages": [
                {"stage": "contract_smoke", "status": "passed", "failure_code": None},
                {"stage": "full_corpus_selection", "status": "selected"},
            ],
        },
    }


class PublicDemoDiagnosticTests(unittest.TestCase):
    def test_only_complete_content_rejection_can_continue(self) -> None:
        rejected = record()
        self.assertTrue(_can_continue_after_smoke(rejected))
        proxy = _continuation_proxy(rejected)
        self.assertTrue(proxy.hard_pass)
        self.assertEqual(proxy.status, "accepted")
        self.assertIsNone(proxy.failure_code)
        self.assertFalse(rejected.hard_pass)
        self.assertEqual(rejected.status, "rejected")

        self.assertFalse(
            _can_continue_after_smoke(
                record(status="failed", failure_code="provider_error", complete=False)
            )
        )
        self.assertFalse(_can_continue_after_smoke(record(complete=False)))

    def test_forced_summary_is_never_qualifying(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            run_dir = output / "runs" / "gpt-4o-mini" / "case" / "repeat-1"
            run_dir.mkdir(parents=True)
            (run_dir / "run-record.json").write_text(
                json.dumps(
                    asdict(
                        record(
                            case_key="case",
                            output_dir="runs/gpt-4o-mini/case/repeat-1",
                        )
                    )
                ),
                encoding="utf-8",
            )

            summary = _force_diagnostic_only(
                base_summary(),
                smoke=record(),
                output=output,
                trusted_main_sha="c" * 40,
            )

            self.assertEqual(summary["decision"]["decision"], "diagnostic-only")
            self.assertIsNone(summary["decision"]["selected_model"])
            self.assertTrue(summary["model_results"][0]["disqualified"])
            self.assertEqual(summary["viability"]["smoke_passes"], 0)
            self.assertEqual(summary["viability"]["full_corpus_finalists"], [])
            self.assertEqual(
                summary["viability"]["stages"][1]["stage"],
                "diagnostic_full_corpus_selection",
            )
            self.assertTrue((output / DIAGNOSTIC_SUMMARY_FILE).is_file())

    def test_rejected_smoke_runs_all_ten_corpus_calls_and_preserves_smoke_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            calls: list[str] = []
            original = paid_benchmark._run_one

            def fake_run_one(**kwargs):
                out = Path(kwargs["output_dir"])
                if out.parts[-2:] == ("stages", "smoke"):
                    value = record()
                    target = (
                        out
                        / "runs"
                        / "gpt-4o-mini"
                        / value.case_key
                        / "repeat-1"
                    )
                    calls.append("smoke")
                else:
                    case = kwargs["case_key"]
                    repeat = kwargs["repeat"]
                    value = record(
                        status="accepted",
                        hard_pass=True,
                        failure_code=None,
                        case_key=case,
                        repeat=repeat,
                        output_dir=f"runs/gpt-4o-mini/{case}/repeat-{repeat}",
                    )
                    target = out / value.output_dir
                    calls.append(f"{case}/{repeat}")
                target.mkdir(parents=True, exist_ok=True)
                (target / "run-record.json").write_text(
                    json.dumps(asdict(value)), encoding="utf-8"
                )
                return value

            def fake_execute(**kwargs):
                smoke = paid_benchmark._run_one(
                    output_dir=Path(kwargs["output_dir"]) / "stages" / "smoke"
                )
                if smoke.hard_pass:
                    for case in ("a", "b", "c", "d", "e"):
                        for repeat in (1, 2):
                            paid_benchmark._run_one(
                                output_dir=Path(kwargs["output_dir"]),
                                case_key=case,
                                repeat=repeat,
                            )
                return base_summary()

            paid_benchmark._run_one = fake_run_one
            try:
                summary = _execute_paid_diagnostic(
                    fake_execute,
                    output_dir=output,
                    trusted_main_sha="d" * 40,
                )
            finally:
                paid_benchmark._run_one = original

            self.assertEqual(len(calls), 11)
            self.assertEqual(summary["diagnostic_mode"]["corpus_run_count"], 10)
            self.assertEqual(summary["diagnostic_mode"]["hard_pass_count"], 10)
            self.assertTrue(
                summary["diagnostic_mode"][
                    "continued_after_smoke_validation_failure"
                ]
            )
            smoke_file = (
                output
                / "stages"
                / "smoke"
                / "runs"
                / "gpt-4o-mini"
                / "historical-normal-crosschecked"
                / "repeat-1"
                / "run-record.json"
            )
            self.assertEqual(json.loads(smoke_file.read_text())["status"], "rejected")

    def test_infrastructure_smoke_failure_does_not_run_corpus(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            calls = 0
            original = paid_benchmark._run_one

            def fake_run_one(**kwargs):
                nonlocal calls
                calls += 1
                return record(
                    status="failed",
                    failure_code="provider_error",
                    complete=False,
                )

            def fake_execute(**kwargs):
                paid_benchmark._run_one(
                    output_dir=Path(kwargs["output_dir"]) / "stages" / "smoke"
                )
                summary = base_summary()
                summary["viability"]["completed_logical_calls"] = 2
                summary["viability"]["http_attempts"] = 2
                summary["viability"]["stages"] = [
                    {"stage": "contract_smoke", "status": "failed"}
                ]
                return summary

            paid_benchmark._run_one = fake_run_one
            try:
                summary = _execute_paid_diagnostic(
                    fake_execute,
                    output_dir=output,
                    trusted_main_sha="e" * 40,
                )
            finally:
                paid_benchmark._run_one = original

            self.assertEqual(calls, 1)
            self.assertEqual(summary["diagnostic_mode"]["corpus_run_count"], 0)
            self.assertFalse(
                summary["diagnostic_mode"][
                    "continued_after_smoke_validation_failure"
                ]
            )

    def test_workflow_is_manual_read_only_protected_and_non_publishing(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("llm_analysis.public_demo_diagnostic prepare", text)
        self.assertIn("llm_analysis.public_demo_diagnostic run", text)
        self.assertIn("workflow_dispatch:", text)
        self.assertIn("contents: read", text)
        self.assertIn("governed-llm-dry-run", text)
        self.assertIn("persist-credentials: false", text)
        self.assertNotIn("contents: write", text)
        self.assertNotIn("schedule:", text)
        self.assertNotIn("git push", text)


if __name__ == "__main__":
    unittest.main()
