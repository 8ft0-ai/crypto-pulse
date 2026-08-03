from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/governed-openrouter-transport-calibration.yml"
REFERENCE = ROOT / "docs/reference/openrouter-transport-calibration.md"
EVALUATION = ROOT / "evaluation/phase-08/openrouter-transport-calibration/README.md"


class ArchivedOpenRouterTransportCalibrationWorkflowTests(unittest.TestCase):
    def test_paid_workflow_remains_archived(self) -> None:
        self.assertFalse(WORKFLOW.exists())

    def test_auditable_implementation_remains_retained(self) -> None:
        for path in (
            ROOT / "config/openrouter-transport-calibration-v1.yml",
            ROOT / "llm_analysis/openrouter_transport_calibration.py",
            ROOT / "llm_analysis/openrouter_transport_calibration_runner.py",
            ROOT / "tests/test_openrouter_transport_calibration.py",
            REFERENCE,
            EVALUATION,
        ):
            self.assertTrue(path.is_file(), path)

    def test_historical_records_retain_exact_run_and_artifacts(self) -> None:
        combined = REFERENCE.read_text(encoding="utf-8") + EVALUATION.read_text(
            encoding="utf-8"
        )
        for required in (
            "30784874599",
            "8844907236",
            "sha256:14c8560c565c49547e5e32fa88f5d7c9ca32c98d337b3009b7c30c7401ca0f7d",
            "8844924119",
            "sha256:ac3af0e5e825d21cdf62f7266d6db3342514ae35437a4e1015de6d128a1ab295",
            "openai/gpt-oss-120b",
            "deepinfra",
            "USD 0.007966518",
            "no rerun",
        ):
            self.assertIn(required, combined)


if __name__ == "__main__":
    unittest.main()