from __future__ import annotations

import unittest
from pathlib import Path

from llm_analysis.candidate_selection_evaluation import evaluate_candidate_selection_proof

ROOT = Path(__file__).resolve().parents[1]


class CandidateSelectionDiscoveryTests(unittest.TestCase):
    def test_emit_retained_selector_proof(self) -> None:
        proof = evaluate_candidate_selection_proof(ROOT)
        for path, content in proof.outputs.items():
            print(f"SLICE5_OUTPUT_BEGIN {path}")
            print(content.decode("utf-8"), end="")
            print(f"SLICE5_OUTPUT_END {path}")
        self.fail("intentional discovery run; replace with retained-output tests")
