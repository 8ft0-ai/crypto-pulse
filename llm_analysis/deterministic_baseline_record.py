"""Project the deterministic baseline evaluation into compact retained artefacts."""
from __future__ import annotations

import argparse
import copy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .contracts import canonical_json_bytes
from .deterministic_baseline_evaluation import (
    DEFAULT_REPORT,
    DEFAULT_SUMMARY,
    DeterministicBaselineEvaluationError,
    evaluate_deterministic_baseline,
)
from .deterministic_ranking import DEFAULT_RANKING_CONFIG
from .claim_candidate_gold_corpus import DEFAULT_MANIFEST as DEFAULT_GOLD_MANIFEST


@dataclass(frozen=True)
class DeterministicBaselineRecord:
    summary: dict[str, Any]
    report_markdown: bytes

    @property
    def summary_bytes(self) -> bytes:
        return canonical_json_bytes(self.summary) + b"\n"


def evaluate_deterministic_baseline_record(
    repository_root: str | Path,
    *,
    ranking_config_path: str | Path = DEFAULT_RANKING_CONFIG,
    gold_manifest_path: str | Path = DEFAULT_GOLD_MANIFEST,
) -> DeterministicBaselineRecord:
    evaluation = evaluate_deterministic_baseline(
        repository_root,
        ranking_config_path=ranking_config_path,
        gold_manifest_path=gold_manifest_path,
    )
    summary = copy.deepcopy(evaluation.summary)
    for case in summary["cases"]:
        selection = case.pop("selection")
        plan = case.pop("claim_plan")
        case["analysis_order"] = plan["analysis_order"]
        case["section_counts"] = selection["section_counts"]
        case["intent_counts"] = selection["intent_counts"]
        case["subject_count"] = selection["subject_count"]
        case["redundancy_group_count"] = selection["redundancy_group_count"]
        case["selected_candidate_ids"] = selection["selected_candidate_ids"]
        for selected in case["selected_candidates"]:
            selected.pop("sentence", None)
    return DeterministicBaselineRecord(summary, evaluation.report_markdown)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Write or verify compact retained Phase 6 baseline artefacts"
    )
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--ranking-config", default=DEFAULT_RANKING_CONFIG)
    parser.add_argument("--gold-manifest", default=DEFAULT_GOLD_MANIFEST)
    parser.add_argument("--summary", default=DEFAULT_SUMMARY)
    parser.add_argument("--report", default=DEFAULT_REPORT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = Path(args.repository_root).resolve()
    record = evaluate_deterministic_baseline_record(
        root,
        ranking_config_path=args.ranking_config,
        gold_manifest_path=args.gold_manifest,
    )
    outputs = {
        root / args.summary: record.summary_bytes,
        root / args.report: record.report_markdown,
    }
    for path, content in outputs.items():
        if args.check:
            if not path.is_file() or path.read_bytes() != content:
                raise DeterministicBaselineEvaluationError(
                    "generated_output_drift",
                    str(path),
                    "checked-in deterministic baseline output differs",
                )
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
