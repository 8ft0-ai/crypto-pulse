from __future__ import annotations

import base64
import unittest
from pathlib import Path

from llm_analysis.claim_candidate_gold_corpus import evaluate_claim_candidate_gold_corpus

ROOT = Path(__file__).resolve().parents[1]


class Phase6GoldCandidateOutputGeneration(unittest.TestCase):
    def test_generate_reviewed_outputs(self) -> None:
        result = evaluate_claim_candidate_gold_corpus(ROOT)
        print("PHASE6_GOLD_SUMMARY_BEGIN")
        print(base64.b64encode(result.summary_bytes).decode("ascii"))
        print("PHASE6_GOLD_SUMMARY_END")
        print("PHASE6_GOLD_REPORT_BEGIN")
        print(base64.b64encode(result.report_markdown).decode("ascii"))
        print("PHASE6_GOLD_REPORT_END")
        self.fail("intentional output generation; replace with checked-in output validation")
