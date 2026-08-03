from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/governed-candidate-selection-model-comparison.yml"
CONFIG = ROOT / "config/candidate-selection-model-comparison.yml"
RUNNER = ROOT / "llm_analysis/candidate_selection_model_comparison_runner.py"
SCORING = ROOT / "llm_analysis/candidate_selection_model_scoring.py"
REFERENCE = ROOT / "docs/reference/candidate-selection-model-comparison.md"
EVALUATION = ROOT / "evaluation/phase-06/candidate-selection-model-comparison/README.md"
DECISION = ROOT / "planning/roadmap/phase-06-bounded-selector-comparison-decision.md"


class GovernedCandidateSelectionModelComparisonWorkflowTests(unittest.TestCase):
    def test_paid_comparison_workflow_is_archived(self) -> None:
        self.assertFalse(
            WORKFLOW.exists(),
            "the completed Phase 6 paid comparison must not return to the Actions UI",
        )

    def test_historical_comparison_contract_remains_auditable(self) -> None:
        for path in (CONFIG, RUNNER, SCORING, REFERENCE, EVALUATION, DECISION):
            with self.subTest(path=path):
                self.assertTrue(path.is_file())

    def test_decision_prohibits_another_phase_6_run(self) -> None:
        decision = DECISION.read_text(encoding="utf-8")
        self.assertIn("No further paid Phase 6 comparison run is authorised", decision)
        self.assertIn("only supported active candidate-selection path", decision)
        self.assertIn("inconclusive-infrastructure", decision)
        self.assertIn("no Nex quality, latency, stability or deployment conclusion", decision)

    def test_no_temporary_slice_6_dispatch_or_patch_workflow_remains(self) -> None:
        workflows = ROOT / ".github/workflows"
        prohibited_fragments = (
            "candidate-selection-model-comparison",
            "phase6-slice6",
            "phase-6-slice-6",
        )
        matching = [
            path.name
            for path in workflows.glob("*.yml")
            if any(fragment in path.name for fragment in prohibited_fragments)
        ]
        self.assertEqual([], matching)


if __name__ == "__main__":
    unittest.main()
