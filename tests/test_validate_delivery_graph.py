from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_delivery_graph import DeliveryGraphValidationError, validate_delivery_graph


VALID_GRAPH = {
    "schema_version": "delivery-graph/v1",
    "nodes": [
        {
            "id": "phase-1",
            "type": "phase",
            "title": "Phase 1",
            "status": "complete",
            "summary": "A completed phase.",
        },
        {
            "id": "artifact-report",
            "type": "artifact",
            "title": "Report",
            "path": "reports/example.md",
            "artifact_kind": "report",
            "committed": True,
        },
        {
            "id": "artifact-rendered",
            "type": "artifact",
            "title": "Rendered page",
            "path": "_site/archive/example.html",
            "artifact_kind": "rendered_proof",
            "committed": False,
        },
    ],
    "edges": [
        {"from": "phase-1", "to": "artifact-report", "type": "produced"},
        {"from": "phase-1", "to": "artifact-rendered", "type": "produced"},
    ],
}


class DeliveryGraphValidationTests(unittest.TestCase):
    def test_repository_delivery_graph_is_valid(self) -> None:
        result = validate_delivery_graph(ROOT / "planning" / "delivery" / "delivery.yaml")
        self.assertGreaterEqual(result.node_count, 3)
        self.assertGreaterEqual(result.edge_count, 3)

    def test_valid_delivery_graph_passes_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            graph_path = self.write_graph(repo_root, VALID_GRAPH)
            result = validate_delivery_graph(graph_path, repo_root=repo_root)
        self.assertEqual(result.node_count, 3)
        self.assertEqual(result.edge_count, 2)

    def test_duplicate_node_id_fails(self) -> None:
        graph = deepcopy(VALID_GRAPH)
        graph["nodes"].append(deepcopy(graph["nodes"][0]))
        self.assert_validation_fails(graph, "duplicate node id")

    def test_missing_edge_endpoint_fails(self) -> None:
        graph = deepcopy(VALID_GRAPH)
        graph["edges"].append({"from": "phase-1", "to": "missing", "type": "produced"})
        self.assert_validation_fails(graph, "missing target node")

    def test_invalid_node_type_fails(self) -> None:
        graph = deepcopy(VALID_GRAPH)
        graph["nodes"][0]["type"] = "milestone"
        self.assert_validation_fails(graph, "invalid node type")

    def test_invalid_edge_type_fails(self) -> None:
        graph = deepcopy(VALID_GRAPH)
        graph["edges"][0]["type"] = "points_sideways"
        self.assert_validation_fails(graph, "invalid edge type")

    def test_missing_required_field_fails(self) -> None:
        graph = deepcopy(VALID_GRAPH)
        del graph["nodes"][0]["summary"]
        self.assert_validation_fails(graph, "missing required fields")

    def test_committed_site_artifact_fails(self) -> None:
        graph = deepcopy(VALID_GRAPH)
        graph["nodes"][2]["committed"] = True
        self.assert_validation_fails(graph, "committed _site output")

    def test_cli_validates_repository_graph(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "validate_delivery_graph.py")],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Delivery graph validation: passed", result.stdout)

    def assert_validation_fails(self, graph: dict, message: str) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            graph_path = self.write_graph(repo_root, graph)
            with self.assertRaisesRegex(DeliveryGraphValidationError, message):
                validate_delivery_graph(graph_path, repo_root=repo_root)

    def write_graph(self, repo_root: Path, graph: dict) -> Path:
        import yaml

        (repo_root / "reports").mkdir(parents=True, exist_ok=True)
        (repo_root / "reports" / "example.md").write_text("# Example\n", encoding="utf-8")
        graph_path = repo_root / "delivery.yaml"
        graph_path.write_text(yaml.safe_dump(graph, sort_keys=False), encoding="utf-8")
        return graph_path


if __name__ == "__main__":
    unittest.main()
