from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import yaml


SCHEMA_VERSION = "delivery-graph/v1"

ALLOWED_NODE_TYPES = {
    "baseline",
    "phase",
    "problem",
    "decision",
    "issue",
    "pull_request",
    "workflow_run",
    "artifact",
    "boundary",
    "lesson",
}

ALLOWED_EDGE_TYPES = {
    "enabled",
    "motivated",
    "revealed_problem",
    "resolved_by",
    "implemented_by",
    "proved_by",
    "generated_by",
    "produced",
    "validated_by",
    "preserved",
    "carried_forward_to",
    "recorded_by",
    "closed_out_by",
    "depends_on",
}

ALLOWED_PHASE_STATUSES = {"shaping", "planned", "active", "complete", "blocked"}
ALLOWED_ARTIFACT_KINDS = {
    "source_snapshot",
    "report",
    "script",
    "rendered_preview",
    "rendered_proof",
    "documentation",
}

REQUIRED_FIELDS_BY_TYPE = {
    "baseline": {"id", "type", "title", "status", "summary"},
    "phase": {"id", "type", "title", "status", "summary"},
    "problem": {"id", "type", "title", "summary"},
    "decision": {"id", "type", "title", "summary"},
    "issue": {"id", "type", "title", "number", "url", "status"},
    "pull_request": {"id", "type", "title", "number", "url", "status"},
    "workflow_run": {"id", "type", "title", "url", "conclusion"},
    "artifact": {"id", "type", "title", "path", "artifact_kind", "committed"},
    "boundary": {"id", "type", "title", "summary"},
    "lesson": {"id", "type", "title", "summary"},
}


class DeliveryGraphValidationError(ValueError):
    """Raised when delivery graph metadata is invalid."""


@dataclass(frozen=True)
class DeliveryGraphValidationResult:
    path: Path
    node_count: int
    edge_count: int


def load_delivery_graph(path: Path) -> dict[str, Any]:
    try:
        graph = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise DeliveryGraphValidationError(f"invalid YAML: {exc}") from exc

    if not isinstance(graph, dict):
        raise DeliveryGraphValidationError("delivery graph must be a YAML mapping")

    return graph


def validate_delivery_graph(path: Path, *, repo_root: Path | None = None) -> DeliveryGraphValidationResult:
    repo_root = repo_root or path.resolve().parents[2]
    graph = load_delivery_graph(path)

    if graph.get("schema_version") != SCHEMA_VERSION:
        raise DeliveryGraphValidationError(
            f"schema_version must be {SCHEMA_VERSION!r}; got {graph.get('schema_version')!r}"
        )

    nodes = graph.get("nodes")
    edges = graph.get("edges")

    if not isinstance(nodes, list) or not nodes:
        raise DeliveryGraphValidationError("nodes must be a non-empty list")
    if not isinstance(edges, list):
        raise DeliveryGraphValidationError("edges must be a list")

    node_ids = _validate_nodes(nodes, repo_root=repo_root)
    _validate_edges(edges, node_ids=node_ids)

    return DeliveryGraphValidationResult(path=path, node_count=len(nodes), edge_count=len(edges))


def _validate_nodes(nodes: Iterable[Any], *, repo_root: Path) -> set[str]:
    seen: set[str] = set()

    for index, node in enumerate(nodes):
        if not isinstance(node, dict):
            raise DeliveryGraphValidationError(f"node #{index + 1} must be a mapping")

        node_id = _required_string(node, "id", f"node #{index + 1}")
        if node_id in seen:
            raise DeliveryGraphValidationError(f"duplicate node id: {node_id}")
        seen.add(node_id)

        node_type = _required_string(node, "type", node_id)
        if node_type not in ALLOWED_NODE_TYPES:
            raise DeliveryGraphValidationError(f"invalid node type for {node_id}: {node_type}")

        missing = sorted(REQUIRED_FIELDS_BY_TYPE[node_type] - set(node))
        if missing:
            raise DeliveryGraphValidationError(f"node {node_id} missing required fields: {', '.join(missing)}")

        _validate_type_specific_node(node, repo_root=repo_root)

    return seen


def _validate_type_specific_node(node: dict[str, Any], *, repo_root: Path) -> None:
    node_id = str(node["id"])
    node_type = str(node["type"])

    if node_type in {"baseline", "phase"} and node.get("status") not in ALLOWED_PHASE_STATUSES:
        raise DeliveryGraphValidationError(f"{node_type} {node_id} has invalid status: {node.get('status')}")

    if node_type in {"issue", "pull_request"}:
        if not isinstance(node.get("number"), int):
            raise DeliveryGraphValidationError(f"{node_type} {node_id} number must be an integer")
        _required_string(node, "url", node_id)

    if node_type == "workflow_run":
        _required_string(node, "url", node_id)
        _required_string(node, "conclusion", node_id)

    if node_type == "artifact":
        _validate_artifact_node(node, repo_root=repo_root)


def _validate_artifact_node(node: dict[str, Any], *, repo_root: Path) -> None:
    node_id = str(node["id"])
    path_text = _required_string(node, "path", node_id)

    if node.get("artifact_kind") not in ALLOWED_ARTIFACT_KINDS:
        raise DeliveryGraphValidationError(
            f"artifact {node_id} has invalid artifact_kind: {node.get('artifact_kind')}"
        )

    committed = node.get("committed")
    if not isinstance(committed, bool):
        raise DeliveryGraphValidationError(f"artifact {node_id} committed must be a boolean")

    if path_text.startswith("/") or ".." in Path(path_text).parts:
        raise DeliveryGraphValidationError(f"artifact {node_id} has unsafe path: {path_text}")

    if path_text.startswith("_site/"):
        if committed:
            raise DeliveryGraphValidationError(f"artifact {node_id} represents committed _site output")
        if node.get("artifact_kind") not in {"rendered_preview", "rendered_proof"}:
            raise DeliveryGraphValidationError(
                f"artifact {node_id} under _site must be rendered_preview or rendered_proof"
            )
        return

    local_path = repo_root / path_text
    if not local_path.exists():
        raise DeliveryGraphValidationError(f"artifact {node_id} path does not exist: {path_text}")


def _validate_edges(edges: Iterable[Any], *, node_ids: set[str]) -> None:
    for index, edge in enumerate(edges):
        if not isinstance(edge, dict):
            raise DeliveryGraphValidationError(f"edge #{index + 1} must be a mapping")

        source = _required_string(edge, "from", f"edge #{index + 1}")
        target = _required_string(edge, "to", f"edge #{index + 1}")
        edge_type = _required_string(edge, "type", f"edge #{index + 1}")

        if source not in node_ids:
            raise DeliveryGraphValidationError(f"edge references missing source node: {source}")
        if target not in node_ids:
            raise DeliveryGraphValidationError(f"edge references missing target node: {target}")
        if edge_type not in ALLOWED_EDGE_TYPES:
            raise DeliveryGraphValidationError(f"invalid edge type: {edge_type}")


def _required_string(mapping: dict[str, Any], key: str, context: str) -> str:
    value = mapping.get(key)
    if not isinstance(value, str) or not value.strip():
        raise DeliveryGraphValidationError(f"{context} must define non-empty string field {key!r}")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate CryptoPulse delivery graph metadata.")
    parser.add_argument(
        "path",
        nargs="?",
        default="planning/delivery/delivery.yaml",
        help="Path to delivery graph YAML. Defaults to planning/delivery/delivery.yaml.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    path = Path(args.path)
    try:
        result = validate_delivery_graph(path)
    except DeliveryGraphValidationError as exc:
        print(f"Delivery graph validation: failed: {exc}")
        return 1

    print(
        "Delivery graph validation: passed "
        f"({result.node_count} nodes, {result.edge_count} edges)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
