"""Evaluate the deterministic Phase 6 ranking baseline over the reviewed corpus."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from .claim_candidate_compiler import compile_claim_candidates
from .claim_candidate_gold_corpus import (
    DEFAULT_MANIFEST as DEFAULT_GOLD_MANIFEST,
    evaluate_claim_candidate_gold_corpus,
    load_claim_candidate_gold_manifest,
)
from .contracts import canonical_json_bytes, content_sha256
from .deterministic_ranking import (
    DEFAULT_RANKING_CONFIG,
    DeterministicBaselineResult,
    load_ranking_config,
    run_deterministic_baseline,
)
from .evaluation import prepare_evaluation

BASELINE_EVALUATION_VERSION = "phase-06-deterministic-baseline-evaluation/v1"
DEFAULT_SUMMARY = "evaluation/phase-06/deterministic-baseline/summary.json"
DEFAULT_REPORT = "evaluation/phase-06/deterministic-baseline/review.md"


class DeterministicBaselineEvaluationError(ValueError):
    """The retained deterministic-baseline evaluation cannot be reproduced."""

    def __init__(self, code: str, path: str, message: str):
        super().__init__(f"{path}: {message}")
        self.code = code
        self.path = path
        self.message = message


@dataclass(frozen=True)
class DeterministicBaselineEvaluation:
    summary: dict[str, Any]
    report_markdown: bytes

    @property
    def summary_bytes(self) -> bytes:
        return canonical_json_bytes(self.summary) + b"\n"


def _fail(code: str, path: str, message: str) -> None:
    raise DeterministicBaselineEvaluationError(code, path, message)


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        _fail("invalid_json", str(path), "must contain a JSON object")
    return value


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _claim_id(candidate_id: str) -> str:
    return "claim-" + candidate_id.removeprefix("claim-candidate:sha256:")


def _assert_equivalent(
    first: DeterministicBaselineResult,
    second: DeterministicBaselineResult,
    path: str,
) -> None:
    if first.selection_bytes != second.selection_bytes:
        _fail("selection_permutation_drift", path, "selection bytes changed")
    if first.claim_plan_bytes != second.claim_plan_bytes:
        _fail("plan_permutation_drift", path, "claim-plan bytes changed")
    if first.render.markdown != second.render.markdown:
        _fail("render_permutation_drift", path, "rendered Markdown bytes changed")


def _render_report(summary: Mapping[str, Any]) -> bytes:
    overall = summary["overall"]
    lines = [
        "# Phase 6 deterministic ranking baseline",
        "",
        "> **Classification:** repository-owned evaluation evidence; no model or provider output.",
        "",
        f"- Ranking configuration: `{summary['ranking_config_path']}`",
        f"- Ranking configuration SHA-256: `{summary['ranking_config_sha256']}`",
        f"- Gold corpus: `{summary['gold_manifest_path']}`",
        f"- Overall status: `{overall['status']}`",
        f"- Cases rendered without an LLM: `{overall['rendered_case_count']} / {overall['case_count']}`",
        f"- Selected useful precision: `{overall['selected_useful_count']} / {overall['selected_count']} ({overall['selected_useful_precision']:.2%})`",
        f"- Selected useful recall: `{overall['selected_useful_count']} / {overall['gold_useful_count']} ({overall['selected_useful_recall']:.2%})`",
        "",
        "## Case summary",
        "",
        "| Case | Class | Candidates | Selected | Useful | Precision | Recall | Sections |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for case in summary["cases"]:
        sections = ", ".join(case["claim_plan"]["analysis_order"])
        lines.append(
            f"| `{case['key']}` | `{case['classification']}` | {case['candidate_count']} | "
            f"{case['selected_count']} | {case['selected_useful_count']} | "
            f"{case['selected_useful_precision']:.2%} | {case['selected_useful_recall']:.2%} | "
            f"{sections} |"
        )

    for case in summary["cases"]:
        lines.extend(
            [
                "",
                f"## `{case['key']}`",
                "",
                f"- Classification: `{case['classification']}`",
                f"- Bundle: `{case['bundle_id']}`",
                f"- Candidate set: `{case['candidate_count']}` candidates, SHA-256 `{case['ordered_candidate_sha256']}`",
                f"- Selected set: `{case['selected_count']}` candidates, SHA-256 `{case['selection_sha256']}`",
                f"- Claim plan SHA-256: `{case['claim_plan_sha256']}`",
                f"- Rendered Markdown SHA-256: `{case['rendered_markdown_sha256']}`",
                f"- Useful precision: `{case['selected_useful_count']} / {case['selected_count']} ({case['selected_useful_precision']:.2%})`",
                f"- Useful recall: `{case['selected_useful_count']} / {case['gold_useful_count']} ({case['selected_useful_recall']:.2%})`",
                f"- Candidate permutation stable: `{str(case['candidate_permutation_stable']).lower()}`",
                f"- Evidence permutation stable: `{str(case['evidence_permutation_stable']).lower()}`",
                "",
                "### Selected claims",
                "",
                "| Candidate | Stage | Score vector | Gold expectation | Rendered claim |",
                "| --- | --- | --- | --- | --- |",
            ]
        )
        for selected in case["selected_candidates"]:
            gold = selected["gold_name"] or "—"
            sentence = selected["sentence"].replace("|", "\\|")
            lines.append(
                f"| `{selected['candidate_id']}` | `{selected['selection_stage']}` | "
                f"`{selected['score_vector']}` | `{gold}` | {sentence} |"
            )
        lines.extend(
            [
                "",
                "### Canonical plan",
                "",
                f"- Analysis order: `{case['claim_plan']['analysis_order']}`",
                f"- Section counts: `{case['selection']['section_counts']}`",
                f"- Intent counts: `{case['selection']['intent_counts']}`",
                f"- Unique redundancy groups: `{case['selection']['redundancy_group_count']}`",
                f"- Distinct candidate subjects: `{case['selection']['subject_count']}`",
            ]
        )

    lines.extend(
        [
            "",
            "## Permanent fallback boundary",
            "",
            "This baseline is the permanent repository-owned comparator and fallback for any later optional model selector. It compiles, ranks, selects, reconstructs, validates and renders without a provider secret. It does not schedule reports, publish content or author new claim semantics.",
            "",
        ]
    )
    return "\n".join(lines).encode("utf-8")


def evaluate_deterministic_baseline(
    repository_root: str | Path,
    *,
    ranking_config_path: str | Path = DEFAULT_RANKING_CONFIG,
    gold_manifest_path: str | Path = DEFAULT_GOLD_MANIFEST,
) -> DeterministicBaselineEvaluation:
    root = Path(repository_root).resolve()
    config = load_ranking_config(root, ranking_config_path)
    gold_manifest = load_claim_candidate_gold_manifest(root, gold_manifest_path)
    gold_evaluation = evaluate_claim_candidate_gold_corpus(root, gold_manifest_path)
    gold_by_key = {item["key"]: item for item in gold_evaluation.summary["cases"]}

    evidence_schema = _read_json(root / "schemas/crypto-market-evidence-bundle-v1.json")
    candidate_schema = _read_json(root / "schemas/crypto-market-claim-candidate-v1.json")
    claim_plan_schema = _read_json(root / "schemas/crypto-market-claim-plan-v1.json")

    cases: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory() as temporary:
        _, prepared = prepare_evaluation(
            repository_root=root,
            config_path=gold_manifest["source_evaluation_config"],
            output_dir=temporary,
        )
        for prepared_case, case_manifest in zip(prepared, gold_manifest["cases"], strict=True):
            if prepared_case.key != case_manifest["key"]:
                _fail("case_order_mismatch", "$.cases", "prepared and gold case order differ")
            bundle = _read_json(Path(temporary) / prepared_case.bundle_file)
            candidates = list(
                compile_claim_candidates(
                    bundle,
                    evidence_schema=evidence_schema,
                    candidate_schema=candidate_schema,
                )
            )
            result = run_deterministic_baseline(
                bundle,
                candidates,
                config=config,
                evidence_schema=evidence_schema,
                candidate_schema=candidate_schema,
                claim_plan_schema=claim_plan_schema,
            )
            gold_case = gold_by_key[prepared_case.key]
            if result.selection["ordered_candidate_sha256"] != gold_case["ordered_candidate_sha256"]:
                _fail(
                    "gold_candidate_hash_mismatch",
                    f"$.cases.{prepared_case.key}",
                    "baseline input differs from the reviewed gold candidate set",
                )

            reversed_candidates = run_deterministic_baseline(
                bundle,
                list(reversed(candidates)),
                config=config,
                evidence_schema=evidence_schema,
                candidate_schema=candidate_schema,
                claim_plan_schema=claim_plan_schema,
            )
            _assert_equivalent(
                result,
                reversed_candidates,
                f"$.cases.{prepared_case.key}.candidate_permutation",
            )

            permuted_bundle = copy.deepcopy(bundle)
            permuted_bundle["evidence"] = list(reversed(permuted_bundle["evidence"]))
            permuted_candidates = list(
                compile_claim_candidates(
                    permuted_bundle,
                    evidence_schema=evidence_schema,
                    candidate_schema=candidate_schema,
                )
            )
            evidence_permutation = run_deterministic_baseline(
                permuted_bundle,
                permuted_candidates,
                config=config,
                evidence_schema=evidence_schema,
                candidate_schema=candidate_schema,
                claim_plan_schema=claim_plan_schema,
            )
            _assert_equivalent(
                result,
                evidence_permutation,
                f"$.cases.{prepared_case.key}.evidence_permutation",
            )

            gold_names = {
                item["candidate_id"]: item["name"]
                for item in gold_case["resolved_candidates"]
            }
            selected_ids = result.selection["selected_candidate_ids"]
            selected_useful = [identifier for identifier in selected_ids if identifier in gold_names]
            rendered_by_claim = {
                item.claim_id: item.sentence for item in result.render.claims
            }
            selected_rows = []
            for item in result.selection["selected_candidates"]:
                candidate_id = item["candidate_id"]
                selected_rows.append(
                    {
                        **item,
                        "gold_name": gold_names.get(candidate_id),
                        "sentence": rendered_by_claim[_claim_id(candidate_id)],
                    }
                )
            selected_count = len(selected_ids)
            gold_count = len(gold_names)
            useful_count = len(selected_useful)
            cases.append(
                {
                    "key": prepared_case.key,
                    "classification": case_manifest["classification"],
                    "bundle_id": bundle["bundle_id"],
                    "candidate_count": len(candidates),
                    "ordered_candidate_sha256": result.selection["ordered_candidate_sha256"],
                    "selected_count": selected_count,
                    "selected_useful_count": useful_count,
                    "gold_useful_count": gold_count,
                    "selected_useful_precision": useful_count / selected_count,
                    "selected_useful_recall": useful_count / gold_count,
                    "selection_sha256": content_sha256(result.selection),
                    "claim_plan_sha256": content_sha256(result.claim_plan),
                    "rendered_markdown_sha256": _sha256_bytes(result.render.markdown),
                    "validation": result.validation.as_dict(),
                    "candidate_permutation_stable": True,
                    "evidence_permutation_stable": True,
                    "selection": result.selection,
                    "claim_plan": result.claim_plan,
                    "selected_candidates": selected_rows,
                }
            )

    total_selected = sum(item["selected_count"] for item in cases)
    total_useful = sum(item["selected_useful_count"] for item in cases)
    total_gold = sum(item["gold_useful_count"] for item in cases)
    summary = {
        "version": BASELINE_EVALUATION_VERSION,
        "ranking_config_path": str(ranking_config_path),
        "ranking_config_sha256": content_sha256(config.as_dict()),
        "ranking_config": config.as_dict(),
        "gold_manifest_path": gold_manifest["manifest_path"],
        "gold_summary_version": gold_evaluation.summary["version"],
        "cases": cases,
        "overall": {
            "status": "pass",
            "case_count": len(cases),
            "rendered_case_count": len(cases),
            "selected_count": total_selected,
            "selected_useful_count": total_useful,
            "gold_useful_count": total_gold,
            "selected_useful_precision": total_useful / total_selected,
            "selected_useful_recall": total_useful / total_gold,
            "candidate_permutation_stable_count": len(cases),
            "evidence_permutation_stable_count": len(cases),
            "validated_plan_count": len(cases),
            "rendered_markdown_count": len(cases),
            "provider_call_count": 0,
        },
    }
    return DeterministicBaselineEvaluation(summary, _render_report(summary))


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate the deterministic Phase 6 ranking baseline")
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--ranking-config", default=DEFAULT_RANKING_CONFIG)
    parser.add_argument("--gold-manifest", default=DEFAULT_GOLD_MANIFEST)
    parser.add_argument("--summary", default=DEFAULT_SUMMARY)
    parser.add_argument("--report", default=DEFAULT_REPORT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = Path(args.repository_root).resolve()
    result = evaluate_deterministic_baseline(
        root,
        ranking_config_path=args.ranking_config,
        gold_manifest_path=args.gold_manifest,
    )
    outputs = {
        root / args.summary: result.summary_bytes,
        root / args.report: result.report_markdown,
    }
    for path, content in outputs.items():
        if args.check:
            if not path.is_file() or path.read_bytes() != content:
                _fail("generated_output_drift", str(path), "checked-in deterministic baseline output differs")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
