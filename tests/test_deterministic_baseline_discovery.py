from __future__ import annotations

import unittest
from pathlib import Path

from llm_analysis.deterministic_baseline_record import (
    evaluate_deterministic_baseline_record,
)

ROOT = Path(__file__).resolve().parents[1]


class DeterministicBaselineDiscoveryTests(unittest.TestCase):
    def test_emit_reviewed_baseline_outputs(self) -> None:
        result = evaluate_deterministic_baseline_record(ROOT)

        print("PHASE6_BASELINE_SUMMARY_BEGIN")
        print(result.summary_bytes.decode("utf-8"), end="")
        print("PHASE6_BASELINE_SUMMARY_END")
        print("PHASE6_BASELINE_REPORT_BEGIN")
        print(result.report_markdown.decode("utf-8"), end="")
        print("PHASE6_BASELINE_REPORT_END")
        self.fail("intentional discovery run; replace with retained-output tests")
