from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from llm_analysis.evaluation import ACTIONS_SUMMARY, DECISION_MARKDOWN, SUMMARY_JSON
from llm_analysis.evaluation_viability import STAGE_RESULTS_FILE
from llm_analysis.generation_config import load_generation_config
from llm_analysis.openrouter_client import HttpResponse, ProviderGenerationError
from llm_analysis.public_demo_benchmark import load_public_demo_profile, public_runtime_config
from llm_analysis.public_demo_benchmark_compat import (
    _record_route_diagnostic,
    compatible_paid_route_probe,
    safe_provider_diagnostic,
)

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "llm-generation-gpt-4o-mini-benchmark.yml"
PROFILE = "config/llm-public-data-demo.yml"
WORKFLOW = ROOT / ".github" / "workflows" / "governed-gpt4o-mini-public-demo.yml"


class CapturingTransport:
    def __init__(self, *, ok: bool = True) -> None:
        self.ok = ok
        self.request: dict | None = None

    def post(self, _url: str, *, headers: dict, body: bytes, timeout_seconds: float) -> HttpResponse:
        self.request = json.loads(body.decode("utf-8"))
        payload = {
            "id": "gen-route",
            "model": "openai/gpt-4o-mini",
            "choices": [{"message": {"content": json.dumps({"ok": self.ok})}}],
            "usage": {"cost": 0.000001},
            "openrouter_metadata": {
                "attempts": [{"status": 200, "provider": "OpenAI"}]
            },
        }
        return HttpResponse(200, json.dumps(payload).encode("utf-8"), {})


class PublicDemoRouteProbeCompatibilityTests(unittest.TestCase):
    def runtime(self):
        base = load_generation_config(CONFIG)
        profile = load_public_demo_profile(ROOT, PROFILE)
        return public_runtime_config(base, profile)

    def test_probe_uses_explicit_boolean_schema_without_const(self) -> None:
        transport = CapturingTransport()
        result = compatible_paid_route_probe(self.runtime(), "secret", transport=transport)

        self.assertEqual(result["actual_model"], "openai/gpt-4o-mini")
        self.assertEqual(result["actual_provider"], "OpenAI")
        self.assertIsNotNone(transport.request)
        response_format = transport.request["response_format"]
        schema = response_format["json_schema"]["schema"]
        self.assertEqual(schema["properties"]["ok"], {"type": "boolean"})
        self.assertNotIn('"const"', json.dumps(schema, sort_keys=True))
        self.assertFalse(transport.request["provider"]["zdr"])
        self.assertEqual(transport.request["provider"]["data_collection"], "deny")
        self.assertTrue(transport.request["provider"]["require_parameters"])

    def test_probe_still_requires_true_client_side(self) -> None:
        with self.assertRaisesRegex(ProviderGenerationError, "required true result"):
            compatible_paid_route_probe(self.runtime(), "secret", transport=CapturingTransport(ok=False))

    def test_safe_diagnostic_is_bounded_single_line_and_redacts_secret(self) -> None:
        message = safe_provider_diagnostic(
            RuntimeError("provider rejected\nsecret-test-key because schema was invalid"),
            "secret-test-key",
        )
        self.assertNotIn("secret-test-key", message)
        self.assertIn("[REDACTED]", message)
        self.assertNotIn("\n", message)
        self.assertLessEqual(len(message), 500)

    def test_route_failure_diagnostic_is_retained_without_raw_payload(self) -> None:
        summary = {
            "viability": {
                "stages": [
                    {
                        "model_key": "gpt-4o-mini",
                        "model": "openai/gpt-4o-mini",
                        "stage": "route_preflight",
                        "status": "failed",
                        "failure_code": "provider_error",
                        "details": {},
                    }
                ]
            }
        }
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            (output / DECISION_MARKDOWN).write_text("# Decision\n", encoding="utf-8")
            (output / ACTIONS_SUMMARY).write_text("# Summary\n", encoding="utf-8")
            _record_route_diagnostic(summary, output, "Invalid schema at properties.ok")

            stored_summary = json.loads((output / SUMMARY_JSON).read_text(encoding="utf-8"))
            stored_stages = json.loads((output / STAGE_RESULTS_FILE).read_text(encoding="utf-8"))
            serialized = json.dumps({"summary": stored_summary, "stages": stored_stages})
            self.assertIn("Invalid schema at properties.ok", serialized)
            self.assertNotIn("Authorization", serialized)
            self.assertNotIn("request_body", serialized)
            self.assertIn("Raw response body and request secrets retained: `false`", (output / DECISION_MARKDOWN).read_text(encoding="utf-8"))

    def test_workflow_uses_compatibility_runner_without_changing_boundaries(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("llm_analysis.public_demo_benchmark_compat prepare", text)
        self.assertIn("llm_analysis.public_demo_benchmark_compat run", text)
        self.assertIn("workflow_dispatch:", text)
        self.assertIn("contents: read", text)
        self.assertIn("governed-llm-dry-run", text)
        self.assertNotIn("contents: write", text)
        self.assertNotIn("schedule:", text)


if __name__ == "__main__":
    unittest.main()
