from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest import mock

from llm_analysis.openrouter_client import HttpResponse
from llm_analysis.semantic_plan_model_final_calibration import (
    EXECUTION_MESSAGE,
    FinalRequestTransform,
    load_final_calibration_config,
    normalise_cross_source_prices,
)
from llm_analysis.semantic_plan_model_selection_scoring import (
    evaluate_validated_expectation,
    stability,
)


class _CaptureTransport:
    def __init__(self) -> None:
        self.body: bytes | None = None

    def post(self, url, *, headers, body, timeout_seconds):
        self.body = body
        return HttpResponse(status=200, body=b"{}", headers={})


class FinalSemanticPlanModelCalibrationTests(unittest.TestCase):
    def test_checked_config_is_two_call_and_quarter_dollar_bounded(self) -> None:
        base, candidates, overrides, smoke_case, total_cap = load_final_calibration_config(
            Path("."), "config/semantic-plan-model-final-calibration.yml"
        )

        self.assertEqual(
            tuple(item.key for item in candidates),
            ("gpt-5-6-sol", "nex-n2-mini"),
        )
        self.assertEqual(smoke_case, "historical-normal-crosschecked")
        self.assertEqual(total_cap, 0.25)
        self.assertFalse(overrides["gpt-5-6-sol"]["ensure_user_message"])
        self.assertTrue(overrides["nex-n2-mini"]["ensure_user_message"])
        self.assertLessEqual(
            sum(row["maximum_model_cost_usd"] for row in overrides.values()),
            total_cap,
        )
        self.assertEqual(len(base.candidates), 3)

    def test_request_transform_adds_one_user_message_for_nex(self) -> None:
        inner = _CaptureTransport()
        transport = FinalRequestTransform(
            inner, send_temperature=True, ensure_user_message=True
        )

        transport.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={},
            body=json.dumps(
                {
                    "model": "nex-agi/nex-n2-mini",
                    "messages": [{"role": "system", "content": "governed prompt"}],
                    "temperature": 0.2,
                }
            ).encode(),
            timeout_seconds=60,
        )

        self.assertIsNotNone(inner.body)
        payload = json.loads(inner.body.decode())
        users = [item for item in payload["messages"] if item["role"] == "user"]
        self.assertEqual(users, [{"role": "user", "content": EXECUTION_MESSAGE}])

    def test_request_transform_does_not_duplicate_existing_user_message(self) -> None:
        inner = _CaptureTransport()
        transport = FinalRequestTransform(
            inner, send_temperature=False, ensure_user_message=True
        )
        transport.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={},
            body=json.dumps(
                {
                    "messages": [
                        {"role": "system", "content": "governed prompt"},
                        {"role": "user", "content": "existing"},
                    ],
                    "temperature": 0.2,
                }
            ).encode(),
            timeout_seconds=60,
        )

        self.assertIsNotNone(inner.body)
        payload = json.loads(inner.body.decode())
        self.assertNotIn("temperature", payload)
        self.assertEqual(
            [item for item in payload["messages"] if item["role"] == "user"],
            [{"role": "user", "content": "existing"}],
        )

    def test_cross_source_price_normalisation_recomputes_bundle_id(self) -> None:
        bundle = {
            "bundle_id": "sha256:old",
            "evidence": [
                {
                    "evidence_id": "exchange.coinbase_exchange.btc-usd.price",
                    "field": "price",
                    "unit": "usd",
                    "value": 10,
                    "source": {
                        "name": "coinbase_exchange",
                        "source_path": "/price",
                    },
                },
                {
                    "evidence_id": "exchange.coinbase_exchange.btc-usd.bid",
                    "field": "bid",
                    "unit": "usd",
                    "value": 9,
                    "source": {
                        "name": "coinbase_exchange",
                        "source_path": "/bid",
                    },
                },
            ],
        }

        normalised, record = normalise_cross_source_prices(bundle)

        self.assertEqual(normalised["evidence"][0]["field"], "price_usd")
        self.assertEqual(normalised["evidence"][1]["field"], "bid")
        self.assertNotEqual(normalised["bundle_id"], bundle["bundle_id"])
        self.assertEqual(
            record["changes"][0]["evidence_id"],
            bundle["evidence"][0]["evidence_id"],
        )

    def test_validator_rejected_plan_is_unscored(self) -> None:
        self.assertIsNone(
            evaluate_validated_expectation(
                {"sections": []},
                mock.Mock(),
                validator_accepted=False,
            )
        )

    def test_empty_failures_receive_no_stability_score(self) -> None:
        rows = [
            {"case_key": "case", "claim_signatures": [], "scored": False},
            {"case_key": "case", "claim_signatures": [], "scored": False},
        ]
        self.assertEqual(stability(rows), 0.0)


if __name__ == "__main__":
    unittest.main()
