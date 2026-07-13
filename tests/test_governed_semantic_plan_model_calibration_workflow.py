from __future__ import annotations

import unittest
from pathlib import Path


class SupersededSemanticPlanModelCalibrationTests(unittest.TestCase):
    def test_obsolete_workflow_entry_point_is_removed(self) -> None:
        workflow = Path(
            ".github/workflows/governed-semantic-plan-model-calibration.yml"
        )
        self.assertFalse(workflow.exists())

    def test_historical_runner_config_and_record_remain_auditable(self) -> None:
        runner = Path("llm_analysis/semantic_plan_model_calibration.py")
        config = Path("config/semantic-plan-model-calibration.yml")
        record = Path("docs/governed-semantic-plan-model-calibration.md")

        self.assertTrue(runner.is_file())
        self.assertTrue(config.is_file())
        self.assertTrue(record.is_file())
        text = record.read_text(encoding="utf-8")
        self.assertIn("Status: superseded historical calibration", text)
        self.assertIn("Do not rerun this three-model calibration", text)
        self.assertIn("Semantic plan calibration — GPT-5.6 + Nex only", text)


if __name__ == "__main__":
    unittest.main()
