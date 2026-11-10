"""Reviewer-visible outputs for semantic claim-plan model selection."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Mapping

QUALITY_LEADERBOARD = "quality-leaderboard.md"
DEPLOYMENT_LEADERBOARD = "deployment-leaderboard.md"
REVIEWER_SCORECARD = "reviewer-scorecard.csv"


def _percent(value: Any) -> str:
    return "n/a" if not isinstance(value, (int, float)) else f"{100 * float(value):.1f}%"


def _money(value: Any) -> str:
    return "n/a" if not isinstance(value, (int, float)) else f"${float(value):.6f}"


def write_leaderboards(output: Path, quality_rows: list[dict[str, Any]], deployment_rows: list[dict[str, Any]]) -> None:
    quality = [
        "# Semantic plan quality leaderboard", "",
        "| Rank | Model | Role | Hard passes | Qualified | Quality | Stability | Cost |",
        "|---:|---|---|---:|---|---:|---:|---:|",
    ]
    for index, row in enumerate(quality_rows, 1):
        quality.append(
            f"| {index} | `{row['model']}` | `{row['role']}` | {row['hard_passes']}/{row['expected_runs']} | "
            f"{'yes' if row['qualified'] else 'no'} | {row['quality_score']:.2f} | {_percent(row['stability'])} | {_money(row['total_cost_usd'])} |"
        )
    (output / QUALITY_LEADERBOARD).write_text("\n".join(quality) + "\n", encoding="utf-8")

    deployment = [
        "# Semantic plan deployment leaderboard", "",
        "GPT-5.6 is benchmark-only and is excluded from this table.", "",
        "| Rank | Model | Qualified | Benchmark quality retained | Cost per hard pass |",
        "|---:|---|---|---:|---:|",
    ]
    for index, row in enumerate(deployment_rows, 1):
        deployment.append(
            f"| {index} | `{row['model']}` | {'yes' if row['qualified'] else 'no'} | "
            f"{_percent(row['quality_retained_vs_benchmark'])} | {_money(row['cost_per_hard_pass_usd'])} |"
        )
    (output / DEPLOYMENT_LEADERBOARD).write_text("\n".join(deployment) + "\n", encoding="utf-8")


def write_scorecard(output: Path, records: list[dict[str, Any]]) -> None:
    fields = [
        "model_key", "requested_model", "candidate_role", "case_key", "repeat",
        "status", "hard_pass", "expectation_hard_pass", "semantic_coverage",
        "materiality", "restraint", "claim_count", "redundant_claim_count",
        "actual_model", "actual_provider", "latency_ms", "input_tokens",
        "output_tokens", "estimated_cost_usd", "failure_code", "expectation_diagnostics",
    ]
    with (output / REVIEWER_SCORECARD).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in records:
            writer.writerow({key: json.dumps(row.get(key), sort_keys=True) if isinstance(row.get(key), (list, dict)) else row.get(key) for key in fields})


def actions_summary(summary: Mapping[str, Any]) -> str:
    lines = [
        "# Semantic claim-plan model selection", "",
        f"- Trusted main: `{summary.get('trusted_main_sha')}`",
        f"- Completed substantive generations: `{summary.get('completed_substantive_generations')} / {summary.get('maximum_substantive_generations')}`",
        f"- Observed cost: `{_money(summary.get('observed_total_cost_usd'))}`",
        f"- Cost ceiling: `{_money(summary.get('maximum_total_cost_usd'))}`",
        "- Automatic generation: `disabled`",
        "- Publication: `disabled`", "", "## Models", "",
    ]
    for row in summary.get("models", []):
        lines.append(
            f"- `{row['model']}`: hard passes `{row['hard_passes']} / {row['expected_runs']}`, "
            f"qualified `{'yes' if row['qualified'] else 'no'}`, quality `{row['quality_score']:.2f}`, "
            f"benchmark retention `{_percent(row.get('quality_retained_vs_benchmark'))}`"
        )
    return "\n".join(lines) + "\n"
