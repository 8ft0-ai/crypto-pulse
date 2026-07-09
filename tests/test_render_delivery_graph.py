from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from render_delivery_graph import render_delivery_graph


class DeliveryGraphRendererTests(unittest.TestCase):
    def test_repository_graph_renders_phase_chain(self) -> None:
        markdown = render_delivery_graph(ROOT / "planning" / "delivery" / "delivery.yaml")
        required_markers = [
            "# CryptoPulse delivery graph",
            "Phase 1 — Source evidence spine",
            "Phase 2 — Deterministic report review loop",
            "Phase 3 — Self-proving generated report PRs",
            "phase_2 -->|revealed problem| problem_approval_gated_validation",
            "problem_approval_gated_validation -->|motivated| phase_3",
            "phase_3 -->|proved by| pr_132",
            "phase_3 -->|closed out by| pr_134",
        ]
        for marker in required_markers:
            with self.subTest(marker=marker):
                self.assertIn(marker, markdown)

    def test_repository_graph_file_matches_renderer_output(self) -> None:
        expected = render_delivery_graph(ROOT / "planning" / "delivery" / "delivery.yaml")
        actual = (ROOT / "planning" / "delivery" / "graph.md").read_text(encoding="utf-8")
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
