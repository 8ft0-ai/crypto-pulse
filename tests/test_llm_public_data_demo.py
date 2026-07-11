from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

import yaml

from llm_analysis.evaluation import EvaluationIntegrityError, PREPARED_MANIFEST
from llm_analysis.generation_config import ConfigurationError, load_generation_config
from llm_analysis.paid_benchmark import load_paid_benchmark_plan
from llm_analysis.public_demo_benchmark import (
    PUBLIC_DEMO_VERSION,
    load_public_demo_profile,
    prepare_public_demo,
    public_runtime_config,
    validate_public_plan,
)

ROOT = Path(__file__).resolve().parents[1]
PROFILE = "config/llm-public-data-demo.yml"
GENERATION_CONFIG = ROOT / "config" / "llm-generation-gpt-4o-mini-benchmark.yml"
WORKFLOW = ROOT / ".github" / "workflows" / "governed-gpt4o-mini-public-demo.yml"


class PublicDataDemoTests(unittest.TestCase):
    def test_profile_is_explicit_and_bounded(self) -> None:
        profile = load_public_demo_profile(ROOT, PROFILE)

        self.assertEqual(profile.profile, "public-data-demo")
        self.assertFalse(profile.zdr)
        self.assertEqual(profile.data_collection, "deny")
        self.assertTrue(profile.ordinary_provider_retention_accepted)
        self.assertEqual(profile.documented_maximum_abuse_monitoring_days, 30)
        self.assertEqual(set(profile.allowed_classifications), {"public-market-data", "evaluation-only"})
        self.assertFalse(profile.cross_model_fallback)
        self.assertFalse(profile.automatic_generation)
        self.assertFalse(profile.publication)

    def test_fixed_corpus_is_public_or_evaluation_only(self) -> None:
        profile = load_public_demo_profile(ROOT, PROFILE)
        plan = load_paid_benchmark_plan(ROOT, profile.benchmark_config)
        classifications = validate_public_plan(plan, profile)

        self.assertEqual(len(classifications), 5)
        self.assertEqual(sum(item["classification"] == "public-market-data" for item in classifications), 3)
        self.assertEqual(sum(item["classification"] == "evaluation-only" for item in classifications), 2)

    def test_sensitive_or_unclassified_inputs_fail_closed(self) -> None:
        profile = load_public_demo_profile(ROOT, PROFILE)
        plan = load_paid_benchmark_plan(ROOT, profile.benchmark_config)
        first = plan.cases[0]

        internal_case = replace(first, snapshot_path="data/internal/customer_snapshot.json")
        with self.assertRaisesRegex(EvaluationIntegrityError, "outside the public snapshot boundary"):
            validate_public_plan(replace(plan, cases=(internal_case, *plan.cases[1:])), profile)

        unclassified_mutation = replace(first, mutation={"kind": "prompt_injection"})
        with self.assertRaisesRegex(EvaluationIntegrityError, "must be classified evaluation-only"):
            validate_public_plan(replace(plan, cases=(unclassified_mutation, *plan.cases[1:])), profile)

        sensitive_tag = replace(first, scenario_tags=(*first.scenario_tags, "customer"))
        with self.assertRaisesRegex(EvaluationIntegrityError, "prohibited classification tag"):
            validate_public_plan(replace(plan, cases=(sensitive_tag, *plan.cases[1:])), profile)

    def test_runtime_transform_changes_only_zdr(self) -> None:
        profile = load_public_demo_profile(ROOT, PROFILE)
        base = load_generation_config(GENERATION_CONFIG)
        transformed = public_runtime_config(base, profile)

        self.assertTrue(base.provider_policy.zdr)
        self.assertFalse(transformed.provider_policy.zdr)
        self.assertEqual(transformed.provider_policy.data_collection, "deny")
        self.assertTrue(transformed.provider_policy.require_parameters)
        self.assertEqual(transformed.model, base.model)
        self.assertEqual(transformed.max_cost_usd, base.max_cost_usd)
        self.assertEqual(transformed.structured_output, base.structured_output)
        self.assertEqual(transformed.cross_model_fallback, base.cross_model_fallback)
        self.assertEqual(
            replace(transformed.provider_policy, zdr=True),
            base.provider_policy,
        )
        self.assertEqual(replace(transformed, provider_policy=base.provider_policy), base)

    def test_default_generation_loader_still_rejects_non_zdr_config(self) -> None:
        raw = yaml.safe_load(GENERATION_CONFIG.read_text(encoding="utf-8"))
        raw["provider_policy"]["zdr"] = False
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "non-zdr.yml"
            path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
            with self.assertRaisesRegex(ConfigurationError, "zdr must remain true"):
                load_generation_config(path)

    def test_prepare_records_public_classifications(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, cases = prepare_public_demo(
                repository_root=ROOT,
                profile_path=PROFILE,
                output_dir=tmp,
            )
            manifest = yaml.safe_load((Path(tmp) / PREPARED_MANIFEST).read_text(encoding="utf-8"))

        self.assertEqual(len(cases), 5)
        self.assertEqual(manifest["public_data_demo"]["version"], PUBLIC_DEMO_VERSION)
        self.assertEqual(len(manifest["public_data_demo"]["classifications"]), 5)

    def test_workflow_is_manual_read_only_and_non_publishing(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("workflow_dispatch:", text)
        self.assertNotIn("schedule:", text)
        self.assertIn("contents: read", text)
        self.assertIn('if [[ "$GITHUB_REF" != "refs/heads/main" ]]', text)
        self.assertIn("llm_analysis.public_demo_benchmark", text)
        self.assertIn("governed-llm-dry-run", text)
        self.assertIn("OPENROUTER_API_KEY", text)
        self.assertNotIn("contents: write", text)
        self.assertNotIn("pull_request", text)
        self.assertNotIn("git push", text)


if __name__ == "__main__":
    unittest.main()
