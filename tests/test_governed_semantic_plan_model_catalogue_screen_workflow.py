from __future__ import annotations

import unittest
from pathlib import Path


class HistoricalSemanticPlanModelCatalogueScreenTests(unittest.TestCase):
    def test_superseded_five_model_workflow_is_not_dispatchable(self) -> None:
        workflow = Path(
            ".github/workflows/governed-semantic-plan-model-catalogue-screen.yml"
        )
        self.assertFalse(workflow.exists())

    def test_historical_runner_config_documentation_and_record_remain_auditable(self) -> None:
        runner = Path("llm_analysis/semantic_plan_model_catalogue_screen.py")
        config = Path("config/semantic-plan-model-catalogue-screen.yml")
        documentation = Path("docs/governed-semantic-plan-model-catalogue-screen.md")
        record = Path("evaluation/phase-05/catalogue-screen-29246391801.md")

        for path in (runner, config, documentation, record):
            self.assertTrue(path.is_file(), path)

        text = documentation.read_text(encoding="utf-8")
        self.assertIn("Status: completed historical compatibility screen", text)
        self.assertIn("Do not rerun the five-model workflow", text)
        self.assertIn("Semantic plan correction — Luna + DeepSeek + Qwen", text)


if __name__ == "__main__":
    unittest.main()
