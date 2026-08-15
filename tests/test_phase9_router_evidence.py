from __future__ import annotations

import unittest
from typing import Any

from llm_analysis.gpt_oss_quality_comparison import _interpret_router_evidence

MODEL = "openai/gpt-oss-120b"
PROVIDER = "deepinfra"


def retained_scalar_response() -> dict[str, Any]:
    """Credential-free fixture matching the retained run 31859246138 route shape."""
    return {
        "http_status": 200,
        "model": MODEL,
        "usage": {
            "prompt_tokens": 19000,
            "completion_tokens": 800,
            "cost": 0.001,
            "completion_tokens_details": {"reasoning_tokens": 400},
        },
        "openrouter_metadata": {
            "attempt": 1,
            "endpoints": {
                "available": [
                    {"provider": "DeepInfra", "selected": True},
                ]
            },
        },
    }


def interpret(payload: dict[str, Any]) -> dict[str, Any]:
    return _interpret_router_evidence(
        payload["openrouter_metadata"],
        expected_provider_slug=PROVIDER,
        actual_model=payload["model"],
        expected_model=MODEL,
    )


class Phase9RouterEvidenceTests(unittest.TestCase):
    def test_retained_scalar_attempt_one_is_direct_route_evidence(self) -> None:
        payload = retained_scalar_response()
        self.assertEqual(payload["http_status"], 200)
        self.assertNotIn("attempts", payload["openrouter_metadata"])

        evidence = interpret(payload)

        self.assertIsNone(evidence["failure_code"])
        self.assertEqual(evidence["attempt_count"], 1)
        self.assertFalse(evidence["provider_fallback_used"])

    def test_scalar_attempt_greater_than_one_fails_closed(self) -> None:
        payload = retained_scalar_response()
        payload["openrouter_metadata"]["attempt"] = 2

        evidence = interpret(payload)

        self.assertEqual(evidence["failure_code"], "provider_fallback_or_metadata_failure")
        self.assertEqual(evidence["attempt_count"], 2)
        self.assertTrue(evidence["provider_fallback_used"])

    def test_multiple_explicit_attempts_fail_closed(self) -> None:
        payload = retained_scalar_response()
        payload["openrouter_metadata"]["attempts"] = [
            {"provider": "DeepInfra", "status": 503},
            {"provider": "DeepInfra", "status": 200},
        ]

        evidence = interpret(payload)

        self.assertEqual(evidence["failure_code"], "provider_fallback_or_metadata_failure")
        self.assertEqual(evidence["attempt_count"], 2)
        self.assertTrue(evidence["provider_fallback_used"])

    def test_provider_mismatch_fails_closed(self) -> None:
        payload = retained_scalar_response()
        payload["openrouter_metadata"]["endpoints"]["available"][0]["provider"] = "OtherProvider"

        evidence = interpret(payload)

        self.assertEqual(evidence["failure_code"], "provider_identity_mismatch")

    def test_model_mismatch_fails_closed(self) -> None:
        payload = retained_scalar_response()
        payload["model"] = "openai/other-model"

        evidence = interpret(payload)

        self.assertEqual(evidence["failure_code"], "model_identity_mismatch")

    def test_conflicting_scalar_and_array_evidence_fails_closed(self) -> None:
        payload = retained_scalar_response()
        payload["openrouter_metadata"].update(
            {
                "attempt": 2,
                "attempts": [{"provider": "DeepInfra", "status": 200}],
            }
        )

        evidence = interpret(payload)

        self.assertEqual(evidence["failure_code"], "provider_fallback_or_metadata_failure")
        self.assertTrue(evidence["provider_fallback_used"])

    def test_ambiguous_selected_provider_fails_closed(self) -> None:
        payload = retained_scalar_response()
        payload["openrouter_metadata"]["endpoints"]["available"].append(
            {"provider": "DeepInfra", "selected": True}
        )

        evidence = interpret(payload)

        self.assertEqual(evidence["failure_code"], "provider_fallback_or_metadata_failure")

    def test_malformed_competing_selected_provider_fails_closed(self) -> None:
        payload = retained_scalar_response()
        payload["openrouter_metadata"]["endpoints"]["available"].append(
            {"provider": None, "selected": True}
        )

        evidence = interpret(payload)

        self.assertEqual(evidence["failure_code"], "provider_fallback_or_metadata_failure")
        self.assertTrue(evidence["provider_fallback_used"])

    def test_single_malformed_selected_provider_fails_closed(self) -> None:
        payload = retained_scalar_response()
        payload["openrouter_metadata"]["endpoints"]["available"] = [
            {"provider": None, "selected": True}
        ]

        evidence = interpret(payload)

        self.assertEqual(evidence["failure_code"], "provider_fallback_or_metadata_failure")
        self.assertTrue(evidence["provider_fallback_used"])

    def test_unsuccessful_explicit_attempt_fails_closed(self) -> None:
        payload = retained_scalar_response()
        payload["openrouter_metadata"]["attempts"] = [
            {"provider": "DeepInfra", "status": 503}
        ]

        evidence = interpret(payload)

        self.assertEqual(evidence["failure_code"], "provider_attempt_invalid")
        self.assertEqual(evidence["attempt_count"], 1)
        self.assertFalse(evidence["provider_fallback_used"])

    def test_malformed_attempts_do_not_fall_back_to_scalar(self) -> None:
        payload = retained_scalar_response()
        payload["openrouter_metadata"]["attempts"] = {"provider": "DeepInfra", "status": 200}

        evidence = interpret(payload)

        self.assertEqual(evidence["failure_code"], "provider_fallback_or_metadata_failure")
        self.assertTrue(evidence["provider_fallback_used"])

    def test_boolean_scalar_attempt_is_not_treated_as_one(self) -> None:
        payload = retained_scalar_response()
        payload["openrouter_metadata"]["attempt"] = True

        evidence = interpret(payload)

        self.assertEqual(evidence["failure_code"], "provider_fallback_or_metadata_failure")
        self.assertTrue(evidence["provider_fallback_used"])


if __name__ == "__main__":
    unittest.main()
