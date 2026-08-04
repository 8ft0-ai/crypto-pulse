from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any, Mapping
from unittest.mock import patch

from llm_analysis import gpt_oss_quality_comparison as core
from llm_analysis import gpt_oss_quality_comparison_runner as runner
from llm_analysis.contracts import content_sha256
from llm_analysis.gpt_oss_quality_comparison import PREPARED_MANIFEST
from llm_analysis.gpt_oss_quality_comparison_config import (
    DEFAULT_CONFIG,
    FROZEN_CASE_ORDER,
    load_phase9_plan,
)
from llm_analysis.gpt_oss_quality_comparison_runner import (
    execute_gpt_oss_quality_comparison,
    prepare_gpt_oss_quality_comparison,
)
from llm_analysis.gpt_oss_quality_comparison_scoring import summarize_complete_corpus
from llm_analysis.openrouter_client import HttpResponse

ROOT = Path(__file__).resolve().parents[1]


def catalogue(*, eligible: bool = True) -> dict[str, Any]:
    parameters = (
        ["response_format", "structured_outputs"]
        if eligible
        else ["response_format"]
    )
    return {
        "data": [
            {
                "id": "openai/gpt-oss-120b",
                "supported_parameters": parameters,
                "pricing": {
                    "prompt": "0.00000005",
                    "completion": "0.00000025",
                },
                "context_length": 131072,
                "top_provider": {"max_completion_tokens": 8192},
            }
        ]
    }


class FakeTransport:
    def __init__(
        self,
        selections: list[list[str]],
        *,
        modes: Mapping[int, str] | None = None,
    ) -> None:
        self.selections = list(selections)
        self.modes = dict(modes or {})
        self.calls = 0
        self.requests: list[dict[str, Any]] = []

    def post(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        body: bytes,
        timeout_seconds: float,
    ) -> HttpResponse:
        del url, timeout_seconds
        self.calls += 1
        self.assert_equal_header(headers)
        request = json.loads(body.decode("utf-8"))
        self.requests.append(request)
        mode = self.modes.get(self.calls, "success")

        if mode == "transport-error":
            raise OSError("simulated transport failure")
        if mode == "http-error":
            return HttpResponse(
                503,
                json.dumps({"error": {"message": "provider unavailable"}}).encode(),
                {"Content-Type": "application/json"},
            )

        content = (
            "not-json"
            if mode == "invalid-content"
            else json.dumps(
                {"selected_candidate_ids": self.selections[self.calls - 1]},
                separators=(",", ":"),
            )
        )
        payload: dict[str, Any] = {
            "id": f"gen-{self.calls}",
            "model": "openai/gpt-oss-120b",
            "choices": [
                {"finish_reason": "stop", "message": {"content": content}}
            ],
            "usage": {
                "prompt_tokens": 19000,
                "completion_tokens": 800,
                "total_tokens": 19800,
                "cost": 0.001,
                "completion_tokens_details": {"reasoning_tokens": 400},
            },
            "openrouter_metadata": {
                "attempt": 1,
                "endpoints": {
                    "available": [
                        {"provider": "DeepInfra", "selected": True}
                    ]
                },
                "attempts": [
                    {
                        "provider": "DeepInfra",
                        "model": "openai/gpt-oss-120b",
                        "status": 200,
                    }
                ],
            },
        }

        if mode == "model-mismatch":
            payload["model"] = "openai/gpt-oss-20b"
        elif mode == "provider-mismatch":
            payload["openrouter_metadata"] = {
                "attempt": 1,
                "endpoints": {
                    "available": [
                        {"provider": "OtherProvider", "selected": True}
                    ]
                },
                "attempts": [
                    {
                        "provider": "OtherProvider",
                        "model": "openai/gpt-oss-120b",
                        "status": 200,
                    }
                ],
            }
        elif mode == "extra-attempt":
            payload["openrouter_metadata"]["attempts"].append(
                {
                    "provider": "DeepInfra",
                    "model": "openai/gpt-oss-120b",
                    "status": 200,
                }
            )
        elif mode == "missing-cost":
            del payload["usage"]["cost"]
        elif mode == "high-cost":
            payload["usage"]["cost"] = 0.006
        elif mode == "missing-reasoning":
            payload["usage"]["completion_tokens_details"] = {}
        elif mode == "missing-finish-reason":
            payload["choices"][0]["finish_reason"] = None

        return HttpResponse(
            200,
            json.dumps(payload).encode(),
            {
                "Content-Type": "application/json",
                "X-Request-Id": f"req-{self.calls}",
            },
        )

    @staticmethod
    def assert_equal_header(headers: Mapping[str, str]) -> None:
        if headers.get("X-OpenRouter-Metadata") != "enabled":
            raise AssertionError("router metadata must be enabled")


class Phase9ComparisonTests(unittest.TestCase):
    def _prepare(self, temporary: Path) -> tuple[Path, dict[str, Any]]:
        prepared = temporary / "prepared"
        result = prepare_gpt_oss_quality_comparison(
            repository_root=ROOT,
            config_path=DEFAULT_CONFIG,
            output_dir=prepared,
        )
        self.assertEqual(result["provider_calls"], 0)
        self.assertTrue(result["prompt_injection_safety_evidence"])
        manifest = json.loads((prepared / PREPARED_MANIFEST).read_text())
        return prepared, manifest

    @staticmethod
    def _baseline_selections(manifest: Mapping[str, Any]) -> list[list[str]]:
        cases = {row["key"]: row for row in manifest["cases"]}
        return [
            list(cases[item["case_key"]]["baseline_selected_candidate_ids"])
            for item in manifest["planned_schedule"]
        ]

    def _execute(
        self,
        *,
        root: Path,
        prepared: Path,
        selections: list[list[str]],
        modes: Mapping[int, str] | None = None,
    ) -> tuple[dict[str, Any], FakeTransport, Path]:
        transport = FakeTransport(selections, modes=modes)
        output = root / "output"
        summary = execute_gpt_oss_quality_comparison(
            repository_root=ROOT,
            config_path=DEFAULT_CONFIG,
            prepared_dir=prepared,
            output_dir=output,
            api_key="test-secret",
            trusted_main_sha="a" * 40,
            catalogue_loader=catalogue,
            transport_factory=lambda: transport,
        )
        return summary, transport, output

    def test_configuration_is_the_exact_validated_contract(self) -> None:
        plan = load_phase9_plan(ROOT)
        self.assertEqual(plan.model, "openai/gpt-oss-120b")
        self.assertEqual(plan.provider_slug, "deepinfra")
        self.assertEqual(plan.maximum_stage_a_calls, 5)
        self.assertEqual(plan.maximum_stage_b_calls, 10)
        self.assertEqual(plan.maximum_paid_calls, 15)
        self.assertEqual(plan.maximum_semantic_repairs, 0)
        self.assertEqual(plan.maximum_network_retries, 0)
        self.assertEqual(plan.maximum_route_probes, 0)
        self.assertAlmostEqual(plan.maximum_call_cost_usd, 0.005)
        self.assertAlmostEqual(plan.maximum_total_cost_usd, 0.075)
        self.assertEqual(plan.promotion_gates.stable_majority_frequency, 2)

    def test_prepare_regenerates_cases_required_subsets_and_safety(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, manifest = self._prepare(Path(tmp))
            self.assertEqual(tuple(manifest["case_order"]), FROZEN_CASE_ORDER)
            self.assertEqual(len(manifest["planned_schedule"]), 15)
            indexed = {row["key"]: row for row in manifest["cases"]}
            self.assertEqual(
                len(indexed["historical-material-move"]["required_candidate_ids"]),
                4,
            )
            self.assertEqual(
                len(
                    indexed["adversarial-source-disagreement"][
                        "required_candidate_ids"
                    ]
                ),
                5,
            )
            prompt_case = indexed["adversarial-prompt-injection"]
            self.assertIn(
                "source.binance.reason",
                prompt_case["prohibited_evidence_ids"],
            )
            self.assertEqual(
                prompt_case["prohibited_candidate_ids_sha256"],
                content_sha256(prompt_case["prohibited_candidate_ids"]),
            )
            self.assertEqual(
                prompt_case["forbidden_text_sha256"],
                content_sha256(prompt_case["forbidden_text"]),
            )
            for row in indexed.values():
                self.assertTrue(row["useful_candidate_ids"])
                self.assertTrue(
                    row["paths"]["selector_request"].startswith(
                        "base-comparison/"
                    )
                )

    def test_complete_baseline_like_run_is_adjudicated_no_uplift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepared, manifest = self._prepare(root)
            summary, transport, output = self._execute(
                root=root,
                prepared=prepared,
                selections=self._baseline_selections(manifest),
            )
            self.assertEqual(summary["completed_paid_calls"], 15)
            self.assertEqual(summary["status"], "complete-adjudicable")
            self.assertEqual(summary["outcome"], "no-stable-material-uplift")
            self.assertEqual(transport.calls, 15)
            self.assertEqual(len(transport.requests), 15)
            for request in transport.requests:
                self.assertEqual(request["model"], "openai/gpt-oss-120b")
                self.assertEqual(request["provider"]["only"], ["deepinfra"])
                self.assertFalse(request["provider"]["allow_fallbacks"])
                self.assertEqual(
                    request["reasoning"],
                    {"effort": "minimal", "exclude": True},
                )
            raw = json.loads(
                (
                    output
                    / "runs/repeat-1/historical-degraded-sparse/http-response.json"
                ).read_text()
            )
            interpreted = json.loads(
                (
                    output
                    / "runs/repeat-1/historical-degraded-sparse/interpreted-response.json"
                ).read_text()
            )
            result = json.loads(
                (
                    output
                    / "runs/repeat-1/adversarial-prompt-injection/result.json"
                ).read_text()
            )
            self.assertIn("raw_body_sha256", raw)
            self.assertNotIn("reasoning", interpreted)
            self.assertEqual(interpreted["reasoning_tokens"], 400)
            self.assertEqual(result["prohibited_selected_candidate_ids"], [])
            self.assertIn("prompt_injection_safety_evidence_sha256", result)
            self.assertTrue(
                (output / "gpt-oss-quality-comparison-reviewer.csv").is_file()
            )
            self.assertTrue(
                (
                    output
                    / "gpt-oss-quality-comparison-additions-losses.csv"
                ).is_file()
            )

    def test_stage_a_model_failure_stops_immediately(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepared, manifest = self._prepare(root)
            summary, transport, output = self._execute(
                root=root,
                prepared=prepared,
                selections=self._baseline_selections(manifest),
                modes={1: "invalid-content"},
            )
            self.assertEqual(transport.calls, 1)
            self.assertEqual(summary["completed_paid_calls"], 1)
            self.assertEqual(summary["outcome"], "no-stable-material-uplift")
            self.assertEqual(summary["status"], "partial-non-adjudicable")
            self.assertEqual(len(summary["scoring"]["unattempted"]), 14)
            reviewer_rows = (
                output / "gpt-oss-quality-comparison-reviewer.csv"
            ).read_text().splitlines()
            self.assertEqual(len(reviewer_rows), 16)
            self.assertEqual(
                sum("not_attempted" in row for row in reviewer_rows),
                14,
            )

    def test_stage_b_model_failure_stops_and_reports_empty_set_jaccard(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepared, manifest = self._prepare(root)
            summary, transport, _ = self._execute(
                root=root,
                prepared=prepared,
                selections=self._baseline_selections(manifest),
                modes={6: "invalid-content"},
            )
            self.assertEqual(transport.calls, 6)
            self.assertEqual(summary["completed_paid_calls"], 6)
            self.assertEqual(summary["outcome"], "no-stable-material-uplift")
            self.assertEqual(summary["status"], "partial-non-adjudicable")
            self.assertEqual(len(summary["scoring"]["unattempted"]), 9)
            pair = next(
                row
                for row in summary["scoring"]["diagnostic_pairwise_jaccard"]
                if row["case_key"] == "historical-degraded-sparse"
                and row["left_repeat_index"] == 1
                and row["right_repeat_index"] == 2
            )
            self.assertEqual(pair["status"], "calculated")
            self.assertEqual(pair["jaccard"], 0.0)

    def test_stage_b_infrastructure_failure_stops_without_imputation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepared, manifest = self._prepare(root)
            summary, transport, _ = self._execute(
                root=root,
                prepared=prepared,
                selections=self._baseline_selections(manifest),
                modes={6: "model-mismatch"},
            )
            self.assertEqual(transport.calls, 6)
            self.assertEqual(summary["outcome"], "inconclusive-infrastructure")
            self.assertEqual(summary["status"], "partial-non-adjudicable")
            pair = next(
                row
                for row in summary["scoring"]["diagnostic_pairwise_jaccard"]
                if row["case_key"] == "historical-degraded-sparse"
                and row["left_repeat_index"] == 1
                and row["right_repeat_index"] == 2
            )
            self.assertEqual(pair["status"], "not_applicable")
            self.assertIsNone(pair["jaccard"])

    def test_terminal_infrastructure_classes_are_retained_and_mapped(self) -> None:
        modes = (
            "transport-error",
            "http-error",
            "model-mismatch",
            "provider-mismatch",
            "extra-attempt",
            "missing-cost",
            "high-cost",
            "missing-reasoning",
            "missing-finish-reason",
        )
        for mode in modes:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                prepared, manifest = self._prepare(root)
                summary, transport, output = self._execute(
                    root=root,
                    prepared=prepared,
                    selections=self._baseline_selections(manifest),
                    modes={1: mode},
                )
                self.assertEqual(transport.calls, 1)
                self.assertEqual(
                    summary["outcome"],
                    "inconclusive-infrastructure",
                )
                self.assertEqual(summary["status"], "partial-non-adjudicable")
                result = json.loads(
                    (
                        output
                        / "runs/repeat-1/historical-degraded-sparse/result.json"
                    ).read_text()
                )
                self.assertEqual(result["classification"], "infrastructure-failure")

    def test_reconstruction_validation_and_rendering_exceptions_map_to_model_failure(self) -> None:
        targets = (
            ("reconstruct_claim_plan", "reconstruction_failure"),
            ("validate_claim_plan", "semantic_validation_failure"),
            ("render_claim_plan", "rendering_failure"),
        )
        for target, expected_code in targets:
            with self.subTest(target=target), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                prepared, manifest = self._prepare(root)
                with patch.object(core, target, side_effect=ValueError("simulated boundary failure")):
                    summary, transport, output = self._execute(
                        root=root,
                        prepared=prepared,
                        selections=self._baseline_selections(manifest),
                    )
                self.assertEqual(transport.calls, 1)
                self.assertEqual(
                    summary["outcome"],
                    "no-stable-material-uplift",
                )
                result = json.loads(
                    (
                        output
                        / "runs/repeat-1/historical-degraded-sparse/result.json"
                    ).read_text()
                )
                self.assertEqual(result["classification"], "model-failure")
                self.assertEqual(result["failure_code"], expected_code)
                self.assertEqual(result["selected_candidate_ids"], [])

    def test_prompt_injection_prohibited_selection_is_a_terminal_model_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepared, manifest = self._prepare(root)
            cases = {row["key"]: row for row in manifest["cases"]}
            prompt_case = cases["adversarial-prompt-injection"]
            prohibited_id = prompt_case["baseline_selected_candidate_ids"][0]
            original_derive = runner._derive_case_safety

            def derive_with_prohibited(**kwargs: Any) -> dict[str, Any]:
                evidence = original_derive(**kwargs)
                if kwargs["case_definition"]["key"] == "adversarial-prompt-injection":
                    evidence["prohibited_candidate_ids"] = [prohibited_id]
                    evidence["prohibited_candidate_ids_sha256"] = content_sha256(
                        [prohibited_id]
                    )
                return evidence

            with patch.object(
                runner,
                "_derive_case_safety",
                side_effect=derive_with_prohibited,
            ):
                regenerated = runner._safety_by_case(
                    repository_root=ROOT,
                    prepared_root=prepared,
                    config_path=DEFAULT_CONFIG,
                )
                prompt_case.update(regenerated["adversarial-prompt-injection"])
                core._write_json(prepared / PREPARED_MANIFEST, manifest)
                summary, transport, output = self._execute(
                    root=root,
                    prepared=prepared,
                    selections=self._baseline_selections(manifest),
                )

            self.assertEqual(transport.calls, 4)
            self.assertEqual(summary["outcome"], "no-stable-material-uplift")
            result = json.loads(
                (
                    output
                    / "runs/repeat-1/adversarial-prompt-injection/result.json"
                ).read_text()
            )
            self.assertEqual(result["classification"], "model-failure")
            self.assertEqual(
                result["failure_code"],
                "prompt_injection_or_prohibited_candidate",
            )
            self.assertEqual(
                result["prohibited_selected_candidate_ids"],
                [prohibited_id],
            )

    def test_tampered_safety_manifest_stops_before_catalogue_or_provider(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepared, manifest = self._prepare(root)
            prompt_case = next(
                row
                for row in manifest["cases"]
                if row["key"] == "adversarial-prompt-injection"
            )
            prompt_case["prohibited_evidence_ids"] = []
            core._write_json(prepared / PREPARED_MANIFEST, manifest)
            summary = execute_gpt_oss_quality_comparison(
                repository_root=ROOT,
                prepared_dir=prepared,
                output_dir=root / "output",
                api_key="test-secret",
                trusted_main_sha="b" * 40,
                catalogue_loader=lambda: self.fail(
                    "catalogue must not be called"
                ),
                transport_factory=lambda: self.fail(
                    "transport must not be created"
                ),
            )
            self.assertEqual(summary["completed_paid_calls"], 0)
            self.assertEqual(summary["outcome"], "inconclusive-infrastructure")
            self.assertIn("safety evidence changed", summary["message"])

    def test_missing_secret_is_zero_call_infrastructure_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepared, _ = self._prepare(root)
            output = root / "output"
            summary = execute_gpt_oss_quality_comparison(
                repository_root=ROOT,
                prepared_dir=prepared,
                output_dir=output,
                api_key=None,
                trusted_main_sha="d" * 40,
                catalogue_loader=lambda: self.fail(
                    "catalogue must not be called"
                ),
                transport_factory=lambda: self.fail(
                    "transport must not be created"
                ),
            )
            self.assertEqual(summary["outcome"], "inconclusive-infrastructure")
            self.assertEqual(summary["completed_paid_calls"], 0)
            self.assertTrue(
                (output / "gpt-oss-quality-comparison-reviewer.csv").is_file()
            )

    def test_prepared_integrity_drift_stops_before_catalogue_or_provider(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepared, manifest = self._prepare(root)
            case = manifest["cases"][0]
            target = prepared / case["paths"]["selector_request"]
            payload = json.loads(target.read_text())
            payload["request_id"] = "tampered"
            target.write_text(json.dumps(payload))
            summary = execute_gpt_oss_quality_comparison(
                repository_root=ROOT,
                prepared_dir=prepared,
                output_dir=root / "output",
                api_key="test-secret",
                trusted_main_sha="e" * 40,
                catalogue_loader=lambda: self.fail(
                    "catalogue must not be called"
                ),
                transport_factory=lambda: self.fail(
                    "transport must not be created"
                ),
            )
            self.assertEqual(summary["outcome"], "inconclusive-infrastructure")
            self.assertEqual(summary["completed_paid_calls"], 0)
            self.assertIn("hash changed", summary["message"])

    def test_ineligible_catalogue_stops_before_provider_client(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepared, _ = self._prepare(root)
            summary = execute_gpt_oss_quality_comparison(
                repository_root=ROOT,
                prepared_dir=prepared,
                output_dir=root / "output",
                api_key="test-secret",
                trusted_main_sha="c" * 40,
                catalogue_loader=lambda: catalogue(eligible=False),
                transport_factory=lambda: self.fail(
                    "provider client must not be created"
                ),
            )
            self.assertEqual(summary["completed_paid_calls"], 0)
            self.assertEqual(summary["outcome"], "inconclusive-infrastructure")

    def test_synthetic_complete_corpus_can_clear_every_gate(self) -> None:
        plan = load_phase9_plan(ROOT)
        prepared: dict[str, dict[str, Any]] = {}
        records: list[dict[str, Any]] = []
        for case_key in FROZEN_CASE_ORDER:
            useful = [f"{case_key}:base", f"{case_key}:addition"]
            prepared[case_key] = {
                "classification": (
                    "evaluation-only"
                    if case_key.startswith("adversarial")
                    else "historical"
                ),
                "useful_candidate_ids": useful,
                "baseline_selected_candidate_ids": [useful[0]],
                "required_candidate_ids": (
                    useful
                    if case_key
                    in {
                        "historical-material-move",
                        "adversarial-source-disagreement",
                    }
                    else []
                ),
            }
            for repeat in (1, 2, 3):
                records.append(
                    {
                        "case_key": case_key,
                        "repeat_index": repeat,
                        "classification": "completed",
                        "selected_candidate_ids": useful,
                        "prohibited_selected_candidate_ids": [],
                        "governance_pass": True,
                    }
                )
        summary = summarize_complete_corpus(plan, records, prepared)
        self.assertEqual(
            summary["outcome"],
            "eligible-for-operational-decision",
        )
        self.assertTrue(all(summary["promotion_gates"].values()))


if __name__ == "__main__":
    unittest.main()
