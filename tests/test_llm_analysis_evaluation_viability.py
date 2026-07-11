from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from llm_analysis.evaluation import prepare_evaluation
from llm_analysis.evaluation_viability import (
    AttemptIneligibleRoutingError,
    AttemptPacer,
    ClassifiedTransport,
    ProviderCapacityError,
    RateLimitedError,
    ViabilityPolicy,
    execute_viability_evaluation,
    load_viability_policy,
)
from llm_analysis.openrouter_client import HttpResponse
from tests.test_llm_analysis_evaluation import Accepted, FakeBuilder, FakeClient, catalogue, fixture_repo

ROOT = Path(__file__).resolve().parents[1]


class FakeClock:
    def __init__(self) -> None:
        self.seconds = 0.0
        self.sleeps: list[float] = []
        self.origin = datetime(2026, 7, 11, tzinfo=timezone.utc)

    def monotonic(self) -> float:
        return self.seconds

    def now(self) -> datetime:
        return self.origin + timedelta(seconds=self.seconds)

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.seconds += seconds


class FakeTransport:
    def __init__(self, response: HttpResponse) -> None:
        self.response = response

    def post(self, *_args, **_kwargs) -> HttpResponse:
        return self.response


class NeverClient:
    def __init__(self, _config) -> None:
        raise AssertionError("provider client must not be constructed")


class ViabilityTests(unittest.TestCase):
    def policy(self) -> ViabilityPolicy:
        return ViabilityPolicy(
            key_status_endpoint="https://openrouter.ai/api/v1/key",
            minimum_interval_seconds=10,
            maximum_jitter_seconds=0,
            maximum_attempts=3,
            fallback_backoff_seconds=(15, 30, 60),
            maximum_delay_seconds=300,
            smoke_case_key="normal",
            maximum_full_corpus_candidates=2,
        )

    def test_source_controlled_policy_is_strict_and_bounded(self) -> None:
        policy = load_viability_policy(ROOT / "config/llm-evaluation-viability.yml")
        self.assertEqual(policy.minimum_interval_seconds, 10)
        self.assertEqual(policy.maximum_jitter_seconds, 3)
        self.assertEqual(policy.maximum_attempts, 3)
        self.assertEqual(policy.fallback_backoff_seconds, (15.0, 30.0, 60.0))
        self.assertEqual(policy.maximum_full_corpus_candidates, 2)

    def test_retry_after_and_rate_limit_reset_are_honoured(self) -> None:
        clock = FakeClock()
        pacer = AttemptPacer(
            self.policy(),
            sleeper=clock.sleep,
            monotonic=clock.monotonic,
            now=clock.now,
            jitter=lambda _low, _high: 0,
        )
        outcomes = [
            RateLimitedError(
                "limited",
                status=429,
                headers={
                    "Retry-After": "20",
                    "X-RateLimit-Reset": str(int((clock.origin + timedelta(seconds=25)).timestamp())),
                },
                provider_code=429,
            ),
            "ok",
        ]

        def operation():
            value = outcomes.pop(0)
            if isinstance(value, BaseException):
                raise value
            return value

        self.assertEqual(pacer.call("route/model", operation), "ok")
        self.assertEqual(clock.sleeps, [25.0])
        self.assertEqual([record.classification for record in pacer.records], ["rate_limited", "success"])
        self.assertEqual(pacer.records[1].delay_source, "rate_limit_reset")

    def test_capacity_uses_exponential_backoff_and_zdr_does_not_retry(self) -> None:
        clock = FakeClock()
        pacer = AttemptPacer(self.policy(), sleeper=clock.sleep, monotonic=clock.monotonic, now=clock.now, jitter=lambda _low, _high: 0)
        outcomes = [ProviderCapacityError("busy", status=503), "ok"]

        def capacity():
            value = outcomes.pop(0)
            if isinstance(value, BaseException):
                raise value
            return value

        self.assertEqual(pacer.call("smoke/model", capacity), "ok")
        self.assertEqual(clock.sleeps, [15.0])
        with self.assertRaises(AttemptIneligibleRoutingError):
            pacer.call("route/zdr", lambda: (_ for _ in ()).throw(AttemptIneligibleRoutingError("no ZDR route", status=404)))
        zdr_records = [item for item in pacer.records if item.logical_id == "route/zdr"]
        self.assertEqual(len(zdr_records), 1)
        self.assertEqual(zdr_records[0].classification, "ineligible_routing")

    def test_classified_transport_preserves_retry_metadata_and_redacts_secret(self) -> None:
        response = HttpResponse(
            429,
            json.dumps({"error": {"message": "secret-test-key exceeded limit", "metadata": {"provider_code": 429, "error_type": "rate_limit_exceeded"}}}).encode(),
            {"Retry-After": "30"},
        )
        transport = ClassifiedTransport(FakeTransport(response))
        with self.assertRaises(RateLimitedError) as captured:
            transport.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": "Bearer secret-test-key"},
                body=b"{}",
                timeout_seconds=30,
            )
        self.assertNotIn("secret-test-key", str(captured.exception))
        self.assertEqual(captured.exception.status, 429)
        self.assertEqual(captured.exception.headers["retry-after"], "30")
        self.assertEqual(captured.exception.provider_code, "429")

    def _fixture(self, root: Path, prepared: Path) -> None:
        sha = fixture_repo(root)
        shutil.copy(ROOT / "config/llm-evaluation-viability.yml", root / "config/llm-evaluation-viability.yml")
        prepare_evaluation(
            repository_root=root,
            config_path="config/llm-evaluation.yml",
            output_dir=prepared,
            bundle_builder=FakeBuilder(sha),
        )

    def test_route_and_smoke_gates_prevent_failed_candidate_from_reaching_corpus(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            prepared = Path(tmp) / "prepared"
            output = Path(tmp) / "output"
            self._fixture(root, prepared)
            clock = FakeClock()

            def probe(config, _api_key):
                if config.model.startswith("nvidia/"):
                    raise AttemptIneligibleRoutingError("no ZDR route", status=404)
                return {"requested_model": config.model, "actual_model": config.model.removesuffix(":free"), "actual_provider": "test-provider"}

            key_status = lambda _key: {
                "limit": None,
                "limit_reset": None,
                "limit_remaining": None,
                "usage": 0,
                "usage_daily": 0,
                "usage_weekly": 0,
                "usage_monthly": 0,
                "is_free_tier": True,
            }
            with patch("llm_analysis.evaluation_execution.process_analysis", return_value=Accepted()):
                summary = execute_viability_evaluation(
                    repository_root=root,
                    config_path="config/llm-evaluation.yml",
                    viability_config_path="config/llm-evaluation-viability.yml",
                    prepared_dir=prepared,
                    output_dir=output,
                    api_key="secret",
                    trusted_main_sha="abc",
                    catalogue_loader=catalogue,
                    key_status_loader=key_status,
                    probe=probe,
                    client_builder=FakeClient,
                    sleeper=clock.sleep,
                    monotonic=clock.monotonic,
                    now=clock.now,
                    jitter=lambda _low, _high: 0,
                )

            self.assertEqual(summary["decision"]["decision"], "change")
            self.assertEqual(summary["decision"]["selected_model"], "qwen/qwen3-next-80b-a3b-instruct:free")
            self.assertEqual(summary["viability"]["maximum_logical_calls"], 16)
            self.assertEqual(summary["viability"]["completed_logical_calls"], 9)
            self.assertEqual(summary["viability"]["http_attempts"], 9)
            self.assertEqual(summary["viability"]["smoke_passes"], 1)
            self.assertEqual(summary["viability"]["full_corpus_finalists"], ["alternative"])
            self.assertEqual(len(list(output.glob("runs/**/run-record.json"))), 6)
            self.assertEqual(len(list((output / "stages/smoke").glob("runs/**/run-record.json"))), 1)
            self.assertFalse(any("current" in path.as_posix() for path in output.glob("runs/**/run-record.json")))
            attempts = json.loads((output / "attempt-records.json").read_text())["attempts"]
            self.assertNotIn("secret", json.dumps(attempts))
            self.assertTrue(all(delay >= 10 for delay in clock.sleeps))

    def test_insufficient_key_quota_stops_before_model_calls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            prepared = Path(tmp) / "prepared"
            output = Path(tmp) / "output"
            self._fixture(root, prepared)
            probe_calls: list[str] = []

            summary = execute_viability_evaluation(
                repository_root=root,
                config_path="config/llm-evaluation.yml",
                viability_config_path="config/llm-evaluation-viability.yml",
                prepared_dir=prepared,
                output_dir=output,
                api_key="secret",
                catalogue_loader=catalogue,
                key_status_loader=lambda _key: {
                    "limit": 1,
                    "limit_reset": "daily",
                    "limit_remaining": 0,
                    "usage": 1,
                    "usage_daily": 1,
                    "usage_weekly": 1,
                    "usage_monthly": 1,
                    "is_free_tier": True,
                },
                probe=lambda config, _key: probe_calls.append(config.model),
                client_builder=NeverClient,
                jitter=lambda _low, _high: 0,
            )

            self.assertEqual(summary["decision"]["decision"], "no-go")
            self.assertEqual(summary["viability"]["key_status"]["request_budget_assessment"], "insufficient")
            self.assertEqual(summary["viability"]["completed_logical_calls"], 0)
            self.assertEqual(probe_calls, [])
            self.assertTrue(all(item["failure_code"] == "insufficient_quota" for item in summary["viability"]["stages"]))


if __name__ == "__main__":
    unittest.main()
