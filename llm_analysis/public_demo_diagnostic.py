"""Full-corpus diagnostic runner for the governed GPT-4o mini public-data demo.

The normal paid benchmark is fail-fast: a rejected smoke response prevents the corpus
from running. This adapter continues only after a real provider completion that failed
content validation, preserves the original smoke artefacts, executes the bounded corpus,
and forces a non-qualifying diagnostic-only decision.
"""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable, Mapping

from . import paid_benchmark
from . import public_demo_benchmark as base
from . import public_demo_benchmark_compat as compat
from . import public_demo_benchmark_projection as projection
from .evaluation import (
    ACTIONS_SUMMARY,
    DECISION_MARKDOWN,
    SUMMARY_JSON,
    EvaluationConfigurationError,
    EvaluationIntegrityError,
    RunRecord,
    _read_json,
    _write_json,
)
from .evaluation_viability import STAGE_RESULTS_FILE
from .generation_config import ConfigurationError

DIAGNOSTIC_VERSION = "phase-05-public-data-diagnostic/v1"
DIAGNOSTIC_SUMMARY_FILE = "diagnostic-corpus-summary.json"


def _is_smoke_output_dir(value: Any) -> bool:
    parts = Path(value).parts
    return len(parts) >= 2 and parts[-2:] == ("stages", "smoke")


def _can_continue_after_smoke(record: RunRecord) -> bool:
    """Allow continuation only for a complete provider result rejected by validation."""

    return (
        record.status == "rejected"
        and not record.hard_pass
        and record.failure_code == "analysis_rejected"
        and record.actual_model is not None
        and record.actual_provider is not None
        and record.estimated_cost_usd is not None
        and record.generation_id is not None
        and record.completion_sha256 is not None
    )


def _continuation_proxy(record: RunRecord) -> RunRecord:
    """Return an in-memory gate proxy; the original rejected record remains on disk."""

    if not _can_continue_after_smoke(record):
        return record
    return replace(record, status="accepted", hard_pass=True, failure_code=None)


def _collect_diagnostic_summary(output: Path) -> dict[str, Any]:
    records: list[Mapping[str, Any]] = []
    for path in sorted((output / "runs").glob("**/run-record.json")):
        value = _read_json(path)
        if isinstance(value, Mapping):
            records.append(value)

    status_counts = Counter(str(item.get("status", "unknown")) for item in records)
    diagnostic_counts: Counter[str] = Counter()
    stage_counts: Counter[str] = Counter()
    provider_counts: Counter[str] = Counter()
    provider_fallback_runs = 0
    cross_model_fallback_runs = 0
    latencies: list[float] = []
    input_tokens: list[float] = []
    output_tokens: list[float] = []
    costs: list[float] = []
    completion_hashes: dict[str, list[str]] = {}

    for record in records:
        provider = record.get("actual_provider")
        if isinstance(provider, str) and provider:
            provider_counts[provider] += 1
        provider_fallback_runs += int(record.get("provider_fallback_used") is True)
        cross_model_fallback_runs += int(record.get("cross_model_fallback_used") is True)
        if isinstance(record.get("latency_ms"), (int, float)):
            latencies.append(float(record["latency_ms"]))
        if isinstance(record.get("input_tokens"), (int, float)):
            input_tokens.append(float(record["input_tokens"]))
        if isinstance(record.get("output_tokens"), (int, float)):
            output_tokens.append(float(record["output_tokens"]))
        if isinstance(record.get("estimated_cost_usd"), (int, float)):
            costs.append(float(record["estimated_cost_usd"]))
        case_key = record.get("case_key")
        completion_hash = record.get("completion_sha256")
        if isinstance(case_key, str) and isinstance(completion_hash, str):
            completion_hashes.setdefault(case_key, []).append(completion_hash)
        validation = record.get("validation")
        diagnostics = validation.get("diagnostics") if isinstance(validation, Mapping) else None
        if not isinstance(diagnostics, list):
            continue
        for diagnostic in diagnostics:
            if not isinstance(diagnostic, Mapping):
                continue
            stage = str(diagnostic.get("stage", "unknown"))
            code = str(diagnostic.get("code", "unknown"))
            stage_counts[stage] += 1
            diagnostic_counts[f"{stage}/{code}"] += 1

    return {
        "version": DIAGNOSTIC_VERSION,
        "corpus_run_count": len(records),
        "hard_pass_count": sum(item.get("hard_pass") is True for item in records),
        "status_counts": dict(sorted(status_counts.items())),
        "diagnostic_stage_counts": dict(sorted(stage_counts.items())),
        "diagnostic_code_counts": dict(sorted(diagnostic_counts.items())),
        "actual_provider_counts": dict(sorted(provider_counts.items())),
        "provider_fallback_runs": provider_fallback_runs,
        "cross_model_fallback_runs": cross_model_fallback_runs,
        "latency_ms_mean_all_completed": (sum(latencies) / len(latencies)) if latencies else None,
        "input_tokens_mean_all_completed": (sum(input_tokens) / len(input_tokens)) if input_tokens else None,
        "output_tokens_mean_all_completed": (sum(output_tokens) / len(output_tokens)) if output_tokens else None,
        "corpus_cost_usd": sum(costs),
        "completion_reproducibility": {
            case: {"observed": len(values), "distinct_hashes": len(set(values))}
            for case, values in sorted(completion_hashes.items())
        },
        "qualification_allowed": False,
        "publication_allowed": False,
    }


def _restore_smoke_stage(summary: dict[str, Any], smoke: RunRecord) -> None:
    viability = summary.get("viability")
    if not isinstance(viability, dict):
        raise EvaluationIntegrityError("diagnostic summary is missing viability")
    stages = viability.get("stages")
    if not isinstance(stages, list):
        raise EvaluationIntegrityError("diagnostic summary is missing viability stages")

    for stage in stages:
        if not isinstance(stage, dict):
            continue
        if stage.get("stage") == "contract_smoke":
            stage["status"] = "passed" if smoke.hard_pass else "failed"
            stage["failure_code"] = smoke.failure_code
            stage["details"] = {
                "validation": smoke.validation,
                "run_record": smoke.output_dir,
                "estimated_cost_usd": smoke.estimated_cost_usd,
            }
        elif stage.get("stage") == "full_corpus_selection":
            stage["stage"] = "diagnostic_full_corpus_selection"
            stage["status"] = "selected"
            stage["details"] = {
                "rule": "continue after complete smoke content-validation result",
                "qualification_allowed": False,
            }

    viability["smoke_passes"] = int(smoke.hard_pass)
    viability["full_corpus_finalists"] = []


def _diagnostic_decision_text(
    summary: Mapping[str, Any],
    smoke: RunRecord,
    diagnostic: Mapping[str, Any],
) -> str:
    paid = summary.get("paid_benchmark") if isinstance(summary.get("paid_benchmark"), Mapping) else {}
    viability = summary.get("viability") if isinstance(summary.get("viability"), Mapping) else {}
    return (
        "# Phase 5 public-data diagnostic corpus\n\n"
        "Decision: **diagnostic-only**\n\n"
        "Selected model: `none`\n\n"
        "This run collected the complete bounded corpus for diagnosis. It cannot qualify "
        "or publish a model, regardless of pass count.\n\n"
        "## Smoke gate\n\n"
        f"- Status: `{smoke.status}`\n"
        f"- Failure code: `{smoke.failure_code or 'none'}`\n"
        f"- Provider completion retained: `{smoke.completion_sha256 is not None}`\n"
        f"- Continued after content-validation rejection: `{_can_continue_after_smoke(smoke)}`\n\n"
        "## Corpus evidence\n\n"
        f"- Corpus runs completed: `{diagnostic.get('corpus_run_count', 0)}`\n"
        f"- Hard passes: `{diagnostic.get('hard_pass_count', 0)}`\n"
        f"- Diagnostic codes: `{json.dumps(diagnostic.get('diagnostic_code_counts', {}), sort_keys=True)}`\n"
        f"- Actual providers: `{json.dumps(diagnostic.get('actual_provider_counts', {}), sort_keys=True)}`\n"
        f"- Provider/cross-model fallback runs: `{diagnostic.get('provider_fallback_runs', 0)}` / "
        f"`{diagnostic.get('cross_model_fallback_runs', 0)}`\n"
        f"- Mean latency ms: `{diagnostic.get('latency_ms_mean_all_completed')}`\n"
        f"- Mean input/output tokens: `{diagnostic.get('input_tokens_mean_all_completed')}` / "
        f"`{diagnostic.get('output_tokens_mean_all_completed')}`\n\n"
        "## Bounded execution\n\n"
        f"- Completed logical calls: `{viability.get('completed_logical_calls')}`\n"
        f"- HTTP attempts: `{viability.get('http_attempts')}`\n"
        f"- Recorded total cost USD: `{paid.get('total_cost_usd')}`\n"
        f"- Cost metadata complete: `{paid.get('cost_metadata_complete_for_qualification')}`\n"
        f"- Cost ceiling exceeded: `{paid.get('experiment_cost_ceiling_exceeded')}`\n"
    )


def _force_diagnostic_only(
    summary: dict[str, Any],
    *,
    smoke: RunRecord,
    output: Path,
    trusted_main_sha: str | None,
) -> dict[str, Any]:
    _restore_smoke_stage(summary, smoke)
    diagnostic = _collect_diagnostic_summary(output)
    continued = _can_continue_after_smoke(smoke) and diagnostic["corpus_run_count"] > 0
    diagnostic.update(
        {
            "continued_after_smoke_validation_failure": continued,
            "smoke_status": smoke.status,
            "smoke_failure_code": smoke.failure_code,
        }
    )
    summary["diagnostic_mode"] = diagnostic
    for result in summary.get("model_results", []):
        if isinstance(result, dict):
            result["disqualified"] = True
    summary["decision"] = {
        "decision": "diagnostic-only",
        "selected_model": None,
        "reason": "The complete bounded corpus was collected for diagnosis; qualification is disabled.",
    }

    _write_json(output / DIAGNOSTIC_SUMMARY_FILE, diagnostic)
    _write_json(output / SUMMARY_JSON, summary)
    viability = summary.get("viability", {})
    _write_json(output / STAGE_RESULTS_FILE, {"stages": viability.get("stages", [])})
    decision = _diagnostic_decision_text(summary, smoke, diagnostic)
    (output / DECISION_MARKDOWN).write_text(decision, encoding="utf-8")
    (output / ACTIONS_SUMMARY).write_text(
        decision + f"\n- Trusted main commit: `{trusted_main_sha or 'not-recorded'}`\n",
        encoding="utf-8",
    )
    return summary


def _execute_paid_diagnostic(
    execute: Callable[..., dict[str, Any]],
    **kwargs: Any,
) -> dict[str, Any]:
    original_run_one = paid_benchmark._run_one
    captured: dict[str, RunRecord] = {}

    def run_one(**run_kwargs: Any) -> RunRecord:
        record = original_run_one(**run_kwargs)
        if _is_smoke_output_dir(run_kwargs.get("output_dir")):
            captured["smoke"] = record
            return _continuation_proxy(record)
        return record

    paid_benchmark._run_one = run_one
    try:
        summary = execute(**kwargs)
    finally:
        paid_benchmark._run_one = original_run_one

    smoke = captured.get("smoke")
    if smoke is None:
        return summary
    return _force_diagnostic_only(
        summary,
        smoke=smoke,
        output=Path(kwargs["output_dir"]),
        trusted_main_sha=kwargs.get("trusted_main_sha"),
    )


def execute_public_demo_diagnostic(**kwargs: Any) -> dict[str, Any]:
    """Run the projected public demo while forcing any completed corpus to diagnostic-only."""

    original_execute = base.execute_paid_benchmark

    def execute(**paid_kwargs: Any) -> dict[str, Any]:
        return _execute_paid_diagnostic(original_execute, **paid_kwargs)

    base.execute_paid_benchmark = execute
    try:
        return projection.execute_public_demo_projection(**kwargs)
    finally:
        base.execute_paid_benchmark = original_execute


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare")
    prepare.add_argument("--repository-root", default=".")
    prepare.add_argument("--profile", default="config/llm-public-data-demo.yml")
    prepare.add_argument("--output-dir", required=True)
    run = sub.add_parser("run")
    run.add_argument("--repository-root", default=".")
    run.add_argument("--profile", default="config/llm-public-data-demo.yml")
    run.add_argument("--viability-config", default="config/llm-evaluation-viability.yml")
    run.add_argument("--prepared-dir", required=True)
    run.add_argument("--output-dir", required=True)
    run.add_argument("--trusted-main-sha")
    args = parser.parse_args()

    try:
        if args.command == "prepare":
            plan, cases = base.prepare_public_demo(
                repository_root=args.repository_root,
                profile_path=args.profile,
                output_dir=args.output_dir,
            )
            print(
                json.dumps(
                    {
                        "model": plan.model.model,
                        "cases": len(cases),
                        "maximum_logical_calls": plan.maximum_logical_calls,
                        "mode": "diagnostic-only",
                    },
                    sort_keys=True,
                )
            )
        else:
            summary = execute_public_demo_diagnostic(
                repository_root=args.repository_root,
                profile_path=args.profile,
                viability_config_path=args.viability_config,
                prepared_dir=args.prepared_dir,
                output_dir=args.output_dir,
                api_key=os.environ.get("OPENROUTER_API_KEY"),
                trusted_main_sha=args.trusted_main_sha,
            )
            print(json.dumps(summary["decision"], sort_keys=True))
        return 0
    except (
        EvaluationConfigurationError,
        EvaluationIntegrityError,
        ConfigurationError,
        OSError,
        ValueError,
        TypeError,
    ) as exc:
        secret = os.environ.get("OPENROUTER_API_KEY", "")
        message = compat.safe_provider_diagnostic(exc, secret)
        print(f"public demo diagnostic benchmark failed: {message}", file=os.sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
