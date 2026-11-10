from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from llm_analysis.evaluation import prepare_evaluation
from llm_analysis.evaluation_execution import execute_evaluation
from llm_analysis.openrouter_client import IneligibleRoutingError
from tests.test_llm_analysis_evaluation import (
    Accepted,
    FakeBuilder,
    FakeClient,
    catalogue,
    fixture_repo,
)


class SelectiveClient:
    """Reproduce the live ZDR rejection for Nemotron while allowing Qwen to run."""

    def __init__(self, config):
        self.config = config

    def generate(self, **kwargs):
        if self.config.model.startswith("nvidia/"):
            raise IneligibleRoutingError(
                "No endpoints found matching your data policy (Zero data retention)."
            )
        return FakeClient(self.config).generate(**kwargs)


class NeverCalledClient:
    def __init__(self, _config):
        raise AssertionError("provider client must not be constructed for ineligible models")


def ineligible_catalogue() -> dict:
    payload = catalogue()
    for row in payload["data"]:
        row["pricing"]["completion"] = "0.01"
    return payload


class EvaluationExecutionTests(unittest.TestCase):
    def test_provider_policy_failure_is_recorded_and_evaluation_continues(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            prepared = Path(tmp) / "prepared"
            output = Path(tmp) / "output"
            sha = fixture_repo(root)
            prepare_evaluation(
                repository_root=root,
                config_path="config/llm-evaluation.yml",
                output_dir=prepared,
                bundle_builder=FakeBuilder(sha),
            )

            with patch(
                "llm_analysis.evaluation_execution.process_analysis",
                return_value=Accepted(),
            ):
                summary = execute_evaluation(
                    repository_root=root,
                    config_path="config/llm-evaluation.yml",
                    prepared_dir=prepared,
                    output_dir=output,
                    api_key="secret",
                    trusted_main_sha="abc",
                    catalogue_loader=catalogue,
                    client_factory=SelectiveClient,
                )

            self.assertEqual(summary["decision"]["decision"], "change")
            self.assertEqual(
                summary["decision"]["selected_model"],
                "qwen/qwen3-next-80b-a3b-instruct:free",
            )
            current, alternative = summary["model_results"]
            self.assertEqual(current["hard_passes"], 0)
            self.assertEqual(len(current["hard_failures"]), 6)
            self.assertTrue(
                all(item["failure_code"] == "ineligible_routing" for item in current["hard_failures"])
            )
            self.assertEqual(alternative["hard_passes"], 6)

            records = sorted(output.glob("runs/**/run-record.json"))
            self.assertEqual(len(records), 12)
            failed = json.loads(
                (output / "runs/current/normal/repeat-1/run-record.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(failed["status"], "failed")
            self.assertEqual(failed["failure_code"], "ineligible_routing")
            self.assertIsNone(failed["evidence_reference_count"])
            self.assertEqual(failed["output_dir"], "runs/current/normal/repeat-1")

    def test_catalogue_ineligibility_produces_complete_no_go_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            prepared = Path(tmp) / "prepared"
            output = Path(tmp) / "output"
            sha = fixture_repo(root)
            prepare_evaluation(
                repository_root=root,
                config_path="config/llm-evaluation.yml",
                output_dir=prepared,
                bundle_builder=FakeBuilder(sha),
            )

            summary = execute_evaluation(
                repository_root=root,
                config_path="config/llm-evaluation.yml",
                prepared_dir=prepared,
                output_dir=output,
                api_key="secret",
                trusted_main_sha="abc",
                catalogue_loader=ineligible_catalogue,
                client_factory=NeverCalledClient,
            )

            self.assertEqual(summary["decision"]["decision"], "no-go")
            records = sorted(output.glob("runs/**/run-record.json"))
            self.assertEqual(len(records), 12)
            self.assertTrue(
                all(json.loads(path.read_text())["status"] == "ineligible" for path in records)
            )


if __name__ == "__main__":
    unittest.main()
