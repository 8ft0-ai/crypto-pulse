from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from llm_analysis.generation_config import load_generation_config
from llm_analysis.openai_schema_projection import (
    OpenAICompatibleSchemaClient,
    project_openai_strict_schema,
    remove_null_object_properties,
)
from llm_analysis.openrouter_client import GenerationMetadata, GenerationResult


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "crypto-market-analysis-v1.json"
CONFIG_PATH = ROOT / "config" / "llm-generation-gpt-4o-mini-benchmark.yml"
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "governed-gpt4o-mini-public-demo.yml"
UNSUPPORTED = {
    "allOf",
    "not",
    "dependentRequired",
    "dependentSchemas",
    "if",
    "then",
    "else",
    "uniqueItems",
    "const",
}


def walk(value):
    yield value
    if isinstance(value, dict):
        for item in value.values():
            yield from walk(item)
    elif isinstance(value, list):
        for item in value:
            yield from walk(item)


class FakeDelegate:
    captured_schema = None

    def __init__(self, _config, *, transport=None) -> None:
        self.transport = transport

    def generate(self, *, evidence_bundle, prompt_template, analysis_schema, api_key=None, environment=None):
        type(self).captured_schema = analysis_schema
        metadata = GenerationMetadata(
            requested_model="openai/gpt-4o-mini",
            actual_model="openai/gpt-4o-mini",
            actual_provider="OpenAI",
            generation_id="gen-test",
            input_tokens=10,
            output_tokens=20,
            total_tokens=30,
            estimated_cost_usd=0.0001,
            latency_ms=100,
            provider_fallback_used=False,
            cross_model_fallback_used=False,
            provider_preferences=(),
            router_attempt=1,
            finish_reason="stop",
        )
        return GenerationResult(
            analysis={
                "required": "kept",
                "optional": None,
                "nested": {"kept": 1, "removed": None},
                "items": [{"kept": True, "removed": None}, None],
            },
            raw_completion='{"required":"kept","optional":null}',
            metadata=metadata,
            provenance={"completion_sha256": "unchanged"},
            request_summary={"structured_output": True},
        )


class OpenAISchemaProjectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.canonical = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        cls.projected = project_openai_strict_schema(cls.canonical)

    def test_projection_does_not_mutate_canonical_schema(self) -> None:
        original = deepcopy(self.canonical)
        project_openai_strict_schema(self.canonical)
        self.assertEqual(self.canonical, original)
        self.assertEqual(json.loads(SCHEMA_PATH.read_text(encoding="utf-8")), original)

    def test_projection_removes_unsupported_keywords_and_document_metadata(self) -> None:
        serialized_keys = {
            key
            for node in walk(self.projected)
            if isinstance(node, dict)
            for key in node
        }
        self.assertFalse(UNSUPPORTED.intersection(serialized_keys))
        self.assertNotIn("$schema", self.projected)
        self.assertNotIn("$id", self.projected)
        self.assertEqual(self.projected["properties"]["schema_version"]["enum"], ["crypto-market-analysis/v1"])

    def test_every_projected_object_requires_every_property(self) -> None:
        objects = [
            node
            for node in walk(self.projected)
            if isinstance(node, dict) and node.get("type") == "object"
        ]
        self.assertGreater(len(objects), 1)
        for node in objects:
            properties = node.get("properties", {})
            self.assertEqual(node.get("additionalProperties"), False)
            self.assertEqual(node.get("required"), list(properties))

    def test_canonical_optional_fields_are_nullable_only_in_projection(self) -> None:
        claim = self.projected["$defs"]["claim"]
        quoted_value = self.projected["$defs"]["quoted_value"]

        for name in ("quoted_values", "comparison"):
            branches = claim["properties"][name]["anyOf"]
            self.assertEqual(branches[-1], {"type": "null"})
        unit_branches = quoted_value["properties"]["unit"]["anyOf"]
        self.assertEqual(unit_branches[-1], {"type": "null"})

        canonical_claim = self.canonical["$defs"]["claim"]
        self.assertNotIn("quoted_values", canonical_claim["required"])
        self.assertNotIn("comparison", canonical_claim["required"])
        self.assertNotIn("unit", self.canonical["$defs"]["quoted_value"]["required"])

    def test_null_normalisation_removes_only_object_properties(self) -> None:
        value = {
            "keep": 1,
            "drop": None,
            "nested": {"drop": None, "keep": "x"},
            "items": [{"drop": None, "keep": True}, None],
        }
        self.assertEqual(
            remove_null_object_properties(value),
            {"keep": 1, "nested": {"keep": "x"}, "items": [{"keep": True}, None]},
        )

    def test_client_projects_schema_and_preserves_raw_provider_evidence(self) -> None:
        config = load_generation_config(CONFIG_PATH)
        with patch("llm_analysis.openai_schema_projection.OpenRouterClient", FakeDelegate):
            client = OpenAICompatibleSchemaClient(config)
            result = client.generate(
                evidence_bundle={},
                prompt_template="unused",
                analysis_schema=self.canonical,
                api_key="secret",
            )

        self.assertIsNotNone(FakeDelegate.captured_schema)
        self.assertNotIn("allOf", json.dumps(FakeDelegate.captured_schema, sort_keys=True))
        self.assertEqual(
            result.analysis,
            {
                "required": "kept",
                "nested": {"kept": 1},
                "items": [{"kept": True}, None],
            },
        )
        self.assertEqual(result.raw_completion, '{"required":"kept","optional":null}')
        self.assertEqual(result.provenance, {"completion_sha256": "unchanged"})
        self.assertEqual(result.metadata.actual_provider, "OpenAI")

    def test_workflow_uses_projection_runner_and_preserves_protection(self) -> None:
        text = WORKFLOW_PATH.read_text(encoding="utf-8")
        self.assertIn("llm_analysis.public_demo_benchmark_projection prepare", text)
        self.assertIn("llm_analysis.public_demo_benchmark_projection run", text)
        self.assertIn("workflow_dispatch:", text)
        self.assertIn("contents: read", text)
        self.assertIn("governed-llm-dry-run", text)
        self.assertNotIn("contents: write", text)
        self.assertNotIn("schedule:", text)


if __name__ == "__main__":
    unittest.main()
