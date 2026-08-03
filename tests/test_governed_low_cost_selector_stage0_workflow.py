from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/governed-low-cost-selector-stage-0.yml"
CONFIG = ROOT / "config/low-cost-candidate-selector-stage-0.yml"
RUNNER = ROOT / "llm_analysis/candidate_selector_stage0_runner.py"
IMPLEMENTATION = ROOT / "llm_analysis/candidate_selector_stage0.py"
REFERENCE = ROOT / "docs/reference/low-cost-candidate-selector-stage-0.md"
EVALUATION = ROOT / "evaluation/phase-07/low-cost-selector-stage-0/README.md"


class GovernedLowCostSelectorStage0WorkflowTests(unittest.TestCase):
    def test_paid_stage0_workflow_remains_archived(self) -> None:
        self.assertFalse(WORKFLOW.exists())

    def test_historical_stage0_implementation_remains_auditable(self) -> None:
        for path in (CONFIG, RUNNER, IMPLEMENTATION, REFERENCE, EVALUATION):
            self.assertTrue(path.is_file(), path)

    def test_archival_records_preserve_run_and_stop_boundaries(self) -> None:
        reference = REFERENCE.read_text(encoding="utf-8")
        evaluation = EVALUATION.read_text(encoding="utf-8")
        combined = reference + "\n" + evaluation
        for required in (
            "30780938812",
            "c5e22c35ab23d0ff43b0801e2d1675216d5cbc2b",
            "8843606111",
            "8843610508",
            "No second Stage 0 run is authorised",
            "stage1_authorized: false",
            "deterministic Phase 6 selector remains the sole active selector",
        ):
            self.assertIn(required, combined)

    def test_no_temporary_phase7_dispatch_or_reconciliation_workflow_remains(self) -> None:
        workflows = ROOT / ".github/workflows"
        prohibited = (
            "governed-low-cost-selector-stage-0.yml",
            "phase7-stage0-run-reconciliation.yml",
        )
        for name in prohibited:
            self.assertFalse((workflows / name).exists(), name)


if __name__ == "__main__":
    unittest.main()
