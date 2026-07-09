from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from render_delivery_graph import render_delivery_graph, write_delivery_graph


class DeliveryGraphRendererTests(unittest.TestCase):
    def test_repository_graph_renders_phase_chain(self) -> None:
        markdown = render_delivery_graph(ROOT / "docs" / "delivery" / "delivery.yaml")
        required_markers = [
            "# CryptoPulse delivery graph",
            "```mermaid",
            "Phase 1 — Source evidence spine",
            "Phase 2 — Deterministic report review loop",
            "Phase 3 — Self-proving generated report PRs",
            "Generated PR validation can be approval-gated",
            "phase_2 -->|revealed problem| problem_approval_gated_validation",
            "problem_approval_gated_validation -->|motivated| phase_3",
            "phase_3 -->|proved by| pr_132",
            "phase_3 -->|closed out by| pr_134",
        ]
        for marker in required_markers:
            with self.subTest(marker=marker):
                self.assertIn(marker, markdown)

    def test_repository_graph_file_matches_renderer_output(self) -> None:
        expected = render_delivery_graph(ROOT / "docs" / "delivery" / "delivery.yaml")
        actual = (ROOT / "docs" / "delivery" / "graph.md").read_text(encoding="utf-8")
        self.assertEqual(actual, expected)

    def test_write_delivery_graph_writes_output_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "graph.md"
            write_delivery_graph(ROOT / "docs" / "delivery" / "delivery.yaml", output_path)
            output = output_path.read_text(encoding="utf-8")
        self.assertIn("flowchart LR", output)
        self.assertIn("Phase 3 — Self-proving generated report PRs", output)

    def test_cli_writes_graph(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output_path = Path(tmp) / "graph.md"
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "render_delivery_graph.py"),
                    "--output",
                    str(output_path),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            output = output_path.read_text(encoding="utf-8")
        self.assertIn("Rendered delivery graph", result.stdout)
        self.assertIn("phase_1 -->|enabled| phase_2", output)


if __name__ == "__main__":
    unittest.main()
