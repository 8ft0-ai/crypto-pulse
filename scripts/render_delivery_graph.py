from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

from validate_delivery_graph import load_delivery_graph, validate_delivery_graph


DEFAULT_INPUT = Path("docs/delivery/delivery.yaml")
DEFAULT_OUTPUT = Path("docs/delivery/graph.md")


def render_delivery_graph(path: Path) -> str:
    validate_delivery_graph(path)
    graph = load_delivery_graph(path)
    nodes = graph["nodes"]
    edges = graph["edges"]

    lines = [
        "# CryptoPulse delivery graph",
        "",
        "This file is generated from `docs/delivery/delivery.yaml` by `scripts/render_delivery_graph.py`.",
        "",
        "The graph is a curated navigation layer over GitHub issues, pull requests, workflow runs, commits, and delivery records. It is not the canonical audit trail.",
        "",
        "```mermaid",
        "flowchart LR",
    ]

    for node in nodes:
        mermaid_id = _mermaid_id(node["id"])
        label = _node_label(node)
        lines.append(f"  {mermaid_id}[\"{_escape_mermaid_label(label)}\"]")

    lines.append("")

    for edge in edges:
        source = _mermaid_id(edge["from"])
        target = _mermaid_id(edge["to"])
        label = edge.get("label") or edge["type"].replace("_", " ")
        lines.append(f"  {source} -->|{_escape_mermaid_label(str(label))}| {target}")

    lines.extend(["```", ""])
    return "\n".join(lines)


def write_delivery_graph(input_path: Path = DEFAULT_INPUT, output_path: Path = DEFAULT_OUTPUT) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_delivery_graph(input_path), encoding="utf-8")


def _node_label(node: dict[str, Any]) -> str:
    node_type = str(node["type"]).replace("_", " ").title()
    title = str(node["title"])

    if node["type"] == "phase":
        return f"Phase\\n{title}"
    if node["type"] == "pull_request":
        return f"PR #{node['number']}\\n{title}"
    if node["type"] == "issue":
        return f"Issue #{node['number']}\\n{title}"
    if node["type"] == "workflow_run":
        return f"Workflow Run\\n{title}"
    if node["type"] == "artifact":
        return f"Artifact\\n{title}"
    if node["type"] == "boundary":
        return f"Boundary\\n{title}"
    if node["type"] == "problem":
        return f"Problem\\n{title}"
    if node["type"] == "lesson":
        return f"Lesson\\n{title}"

    return f"{node_type}\\n{title}"


def _mermaid_id(node_id: str) -> str:
    sanitized = re.sub(r"[^0-9A-Za-z_]", "_", node_id)
    if not sanitized or sanitized[0].isdigit():
        sanitized = f"node_{sanitized}"
    return sanitized


def _escape_mermaid_label(label: str) -> str:
    return label.replace('"', "'")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render CryptoPulse delivery graph Mermaid Markdown.")
    parser.add_argument(
        "--input",
        default=str(DEFAULT_INPUT),
        help="Path to delivery graph YAML. Defaults to docs/delivery/delivery.yaml.",
    )
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help="Path to write generated Markdown. Defaults to docs/delivery/graph.md.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    write_delivery_graph(Path(args.input), Path(args.output))
    print(f"Rendered delivery graph: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
