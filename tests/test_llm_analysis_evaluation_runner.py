from __future__ import annotations

import contextlib
import io
import os
import sys
import unittest
from unittest.mock import patch

from llm_analysis.evaluation_runner import main


class EvaluationRunnerTests(unittest.TestCase):
    def test_cli_forwards_environment_secret_without_printing_it(self) -> None:
        secret = "test-openrouter-secret"
        argv = [
            "evaluation_runner",
            "--repository-root",
            ".",
            "--config",
            "config/llm-evaluation.yml",
            "--prepared-dir",
            "/tmp/prepared",
            "--output-dir",
            "/tmp/output",
            "--trusted-main-sha",
            "abc123",
        ]
        output = io.StringIO()
        with (
            patch.object(sys, "argv", argv),
            patch.dict(os.environ, {"OPENROUTER_API_KEY": secret}, clear=False),
            patch(
                "llm_analysis.evaluation_runner.execute_evaluation",
                return_value={"decision": {"decision": "retain", "selected_model": "model"}},
            ) as execute,
            contextlib.redirect_stdout(output),
        ):
            self.assertEqual(main(), 0)

        self.assertEqual(execute.call_args.kwargs["api_key"], secret)
        self.assertEqual(execute.call_args.kwargs["trusted_main_sha"], "abc123")
        self.assertNotIn(secret, output.getvalue())
        self.assertIn('"decision": "retain"', output.getvalue())

    def test_cli_redacts_secret_from_failures(self) -> None:
        secret = "test-openrouter-secret"
        argv = [
            "evaluation_runner",
            "--prepared-dir",
            "/tmp/prepared",
            "--output-dir",
            "/tmp/output",
        ]
        output = io.StringIO()
        with (
            patch.object(sys, "argv", argv),
            patch.dict(os.environ, {"OPENROUTER_API_KEY": secret}, clear=False),
            patch(
                "llm_analysis.evaluation_runner.execute_evaluation",
                side_effect=ValueError(f"provider rejected {secret}"),
            ),
            contextlib.redirect_stdout(output),
        ):
            self.assertEqual(main(), 2)

        self.assertNotIn(secret, output.getvalue())
        self.assertIn("[REDACTED]", output.getvalue())


if __name__ == "__main__":
    unittest.main()
