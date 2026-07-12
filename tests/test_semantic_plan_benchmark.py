from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from llm_analysis.contracts import canonical_json_bytes
from llm_analysis.generation_config import GenerationConfig
from llm_analysis.openrouter_client import GenerationMetadata, GenerationResult
from llm_analysis.semantic_plan_benchmark import (
    SEMANTIC_BENCHMARK_VERSION,
    execute_semantic_plan_benchmark,
    load_semantic_plan_profile,
    prepare_semantic_plan_benchmark,
)

ROOT = Path(__file__).resolve().parents[1]
PROFILE = "config/llm-public-data-semantic-plan.yml"
WORKFLOW = ROOT / ".github" / "workflows" / "governed-gpt4o-mini-public-demo.yml"
HISTORICAL_DECISION = ROOT / "evaluation" / "phase-05" / "public-demo-decision.yml"


class _Clock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        self.value += 30.0
        return self.value


class _SemanticClient:
    def __init__(self, config: GenerationConfig) -> None:
        self.config = config
        self.counter = 0

    def generate(
        self,
        *,
        evidence_bundle: Mapping[str, Any],
        prompt_template: str,
        analysis_schema: Mapping[str, Any],
        api_key: str,
    ) -> GenerationResult:
        self.counter += 1
        plan = {
            "claim_plan_version": "crypto-market-claim-plan/v1",
            "prompt_version": "crypto-market-claim-plan/v1",
            "evidence_bundle_id": evidence_bundle["bundle_id"],
            "analysis_order": ["risks_and_limitations"],
            "sections": [
                {
                    "section_kind": "risks_and_limitations",
                    "claims": [
                        {
                            "claim_id": "claim-snapshot-status",
                            "intent": "snapshot_status",
                            "evidence_ids": ["quality.snapshot.status"],
                            "comparison_relation": "none",
                            "confidence": "high",
                        }
                    ],
                }
            ],
        }
        raw = canonical_json_bytes(plan).decode("utf-8")
        metadata = GenerationMetadata(
            requested_model=self.config.model,
            actual_model="openai/gpt-4o-mini",
            actual_provider="OpenAI",
            generation_id=f"generation-{self.counter}",
            input_tokens=100,
            output_tokens=50,
            total_tokens=150,
            estimated_cost_usd=0.001,
            latency_ms=250,
            provider_fallback_used=False,
            cross_model_fallback_used=False,
            provider_preferences=(),
            router_attempt=1,
            finish_reason="stop",
        )
        return GenerationResult(
            analysis=plan,
            raw_completion=raw,
            metadata=metadata,
            provenance={},
            request_summary={
                "model": self.config.model,
                "provider_policy": self.config.provider_policy.as_request(),
                "structured_output": True,
            },
        )


def _catalogue() -> Mapping[str, Any]:
    return {
        "data": [
            {
                "id": "openai/gpt-4o-mini",
                "supported_parameters": ["response_format", "structured_outputs"],
                "pricing": {"prompt": "0.00000015", "completion": "0.00000060"},
                "context_length": 128000,
                "top_provider": {"max_completion_tokens": 16384},
                "expiration_date": None,
            }
        ]
    }


def _key_status(_: str) -> Mapping[str, Any]:
    return {
        "limit_remaining": 10.0,
        "limit": 10.0,
        "limit_reset": None,
        "usage": 0.0,
        "usage_daily": 0.0,
        "usage_weekly": 0.0,
        "usage_monthly": 0.0,
        "is_free_tier": False,
    }


def _route(config: GenerationConfig, _: str) -> Mapping[str, Any]:
    return {
        "requested_model": config.model,
        "actual_model": "openai/gpt-4o-mini",
        "actual_provider": "OpenAI",
        "generation_id": "route-generation",
        "estimated_cost_usd": 0.001,
    }


class SemanticPlanBenchmarkTests(unittest.TestCase):
    def test_profile_is_an_isolated_contract_overlay(self) -> None:
        profile = load_semantic_plan_profile(ROOT, PROFILE)

        self.assertEqual(profile.profile, "public-data-semantic-plan")
        self.assertEqual(profile.exact_model, "openai/gpt-4o-mini")
        self.assertEqual(profile.prompt_version, "crypto-market-claim-plan/v1")
        self.assertEqual(profile.claim_plan_schema_version, "crypto-market-claim-plan/v1")
        self.assertEqual(profile.renderer_version, "crypto-market-claim-plan-renderer/v1")
        self.assertEqual(profile.maximum_generation_cost_usd, 0.01)
        self.assertEqual(profile.maximum_experiment_cost_usd, 0.15)
        self.assertFalse(profile.cross_model_fallback)
        self.assertFalse(profile.automatic_generation)
        self.assertFalse(profile.publication)
        self.assertEqual(profile.base_public_data_profile, "config/llm-public-data-demo.yml")

    def test_prepare_preserves_the_frozen_public_corpus(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            plan, cases = prepare_semantic_plan_benchmark(
                repository_root=ROOT,
                profile_path=PROFILE,
                output_dir=tmp,
            )
            manifest = json.loads((Path(tmp) / "prepared-corpus-manifest.json").read_text())

        self.assertEqual(plan.model.model, "openai/gpt-4o-mini")
        self.assertEqual(len(cases), 5)
        self.assertEqual(plan.runs_per_case, 2)
        self.assertEqual(manifest["semantic_plan"]["version"], SEMANTIC_BENCHMARK_VERSION)
        classifications = manifest["semantic_plan"]["classifications"]
        self.assertEqual(sum(value == "public-market-data" for value in classifications.values()), 3)
        self.assertEqual(sum(value == "evaluation-only" for value in classifications.values()), 2)

    def test_fake_full_corpus_qualifies_and_retains_complete_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as prepared_tmp, tempfile.TemporaryDirectory() as output_tmp:
            prepare_semantic_plan_benchmark(
                repository_root=ROOT,
                profile_path=PROFILE,
                output_dir=prepared_tmp,
            )
            summary = execute_semantic_plan_benchmark(
                repository_root=ROOT,
                profile_path=PROFILE,
                viability_config_path="config/llm-evaluation-viability.yml",
                prepared_dir=prepared_tmp,
                output_dir=output_tmp,
                api_key="test-secret",
                trusted_main_sha="a" * 40,
                catalogue_loader=_catalogue,
                key_status_loader=_key_status,
                probe=_route,
                client_builder=lambda config: _SemanticClient(config),
                sleeper=lambda _: None,
                monotonic=_Clock(),
                now=lambda: datetime(2026, 7, 12, 0, 0, tzinfo=timezone.utc),
                jitter=lambda _minimum, _maximum: 0.0,
            )
            output = Path(output_tmp)
            run_records = list(output.glob("runs/gpt-4o-mini/*/repeat-*/run-record.json"))

            self.assertTrue(summary["qualified"])
            self.assertEqual(summary["decision"], "semantic-plan-qualified")
            self.assertEqual(summary["completed_corpus_runs"], 10)
            self.assertEqual(summary["validated_claim_plans"], 10)
            self.assertEqual(summary["validated_rendered_outputs"], 10)
            self.assertEqual(summary["byte_identical_rerenders"], 10)
            self.assertEqual(summary["prompt_injection"], {"eligible_runs": 2, "safe_runs": 2})
            self.assertEqual(
                summary["source_disagreement"],
                {"eligible_runs": 2, "valid_or_silent_runs": 2},
            )
            self.assertTrue(summary["exact_model_identity"])
            self.assertTrue(summary["actual_provider_identity_complete"])
            self.assertEqual(summary["cross_model_fallback_runs"], 0)
            self.assertEqual(summary["policy_failures"], 0)
            self.assertTrue(summary["cost"]["metadata_complete"])
            self.assertLessEqual(summary["cost"]["total_cost_usd"], 0.15)
            self.assertFalse(summary["automatic_generation"])
            self.assertFalse(summary["publication"])
            self.assertEqual(len(run_records), 10)

            for record_path in run_records:
                run_dir = record_path.parent
                self.assertTrue((run_dir / "provider-completion.raw.json").is_file())
                self.assertTrue((run_dir / "canonical-claim-plan.json").is_file())
                self.assertTrue((run_dir / "claim-plan-validation.json").is_file())
                self.assertTrue((run_dir / "rendered-analysis.md").is_file())
                self.assertTrue((run_dir / "rendered-claims.json").is_file())
                provenance = json.loads((run_dir / "semantic-provenance.json").read_text())
                self.assertEqual(provenance["schema_version"], "crypto-market-semantic-plan-provenance/v1")
                self.assertTrue(provenance["provider_response"]["raw_completion_sha256"])
                self.assertTrue(provenance["claim_plan"]["sha256"])
                self.assertTrue(provenance["renderer"]["rendered_output_sha256"])
                self.assertTrue(provenance["renderer"]["byte_identical_rerender"])
                self.assertFalse(provenance["policy"]["automatic_generation"])
                self.assertFalse(provenance["policy"]["publication"])

    def test_workflow_is_trusted_manual_read_only_and_non_publishing(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("workflow_dispatch:", text)
        self.assertNotIn("schedule:", text)
        self.assertIn("contents: read", text)
        self.assertIn('if [[ "$GITHUB_REF" != "refs/heads/main" ]]', text)
        self.assertIn("llm_analysis.semantic_plan_benchmark prepare", text)
        self.assertIn("llm_analysis.semantic_plan_benchmark run", text)
        self.assertIn("governed-llm-dry-run", text)
        self.assertIn("OPENROUTER_API_KEY", text)
        self.assertIn("Upload non-published semantic-plan artefacts", text)
        self.assertNotIn("contents: write", text)
        self.assertNotIn("pull_request", text)
        self.assertNotIn("git push", text)

    def test_historical_natural_prose_decision_remains_present(self) -> None:
        text = HISTORICAL_DECISION.read_text(encoding="utf-8")
        self.assertIn("public-demo-no-go", text)
        self.assertIn("29151358149", text)


if __name__ == "__main__":
    unittest.main()
