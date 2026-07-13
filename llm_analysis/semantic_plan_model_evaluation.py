"""Bounded semantic claim-plan model selection against a benchmark-only reference."""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from dataclasses import asdict, replace
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from .contracts import canonical_json_bytes
from .evaluation import (
    ACTIONS_SUMMARY,
    PREPARED_MANIFEST,
    EvaluationConfigurationError,
    EvaluationIntegrityError,
    EvaluationModel,
    _catalogue,
    _read_json,
    _write_json,
)
from .evaluation_viability import (
    ATTEMPT_RECORDS_FILE,
    AttemptPacer,
    ClassifiedTransport,
    PacedClientFactory,
    load_viability_policy,
)
from .generation_config import model_matches
from .openrouter_client import OpenRouterClient, Transport, UrllibTransport
from .paid_benchmark import PaidBenchmarkPlan, check_paid_model_availability
from .semantic_plan_benchmark import (
    SemanticPlanProfile,
    _prepared_cases,
    _run_one,
    _semantic_runtime_config,
    _validate_profile_chain,
    load_semantic_plan_profile,
    prepare_semantic_plan_benchmark,
)
from .semantic_plan_model_selection_config import (
    Candidate,
    CaseExpectation,
    SelectionPlan,
    load_expectations,
    load_selection_plan,
)
from .semantic_plan_model_selection_reporting import actions_summary, write_leaderboards, write_scorecard
from .semantic_plan_model_selection_scoring import (
    ExpectationResult,
    _jaccard,
    distribution,
    evaluate_expectation,
    stability,
)
from .semantic_plan_protected_runner import projected_paid_route_probe

MODEL_SELECTION_VERSION = "semantic-plan-model-selection/v1"
SELECTION_SUMMARY = "model-selection-summary.json"
ROUTE_RESULTS = "route-preflight.json"
AVAILABILITY_RESULTS = "model-availability.json"
EXCLUDED_RESULTS = "excluded-models.json"


class _BodyTransformTransport:
    """Apply one declared request compatibility transform without changing semantics."""

    def __init__(self, inner: Transport, *, send_temperature: bool) -> None:
        self.inner = inner
        self.send_temperature = send_temperature

    def post(self, url: str, *, headers: Mapping[str, str], body: bytes, timeout_seconds: float) -> Any:
        transformed = body
        if not self.send_temperature:
            payload = json.loads(body.decode("utf-8"))
            if not isinstance(payload, dict):
                raise EvaluationIntegrityError("OpenRouter request body must be an object")
            payload.pop("temperature", None)
            transformed = canonical_json_bytes(payload)
        return self.inner.post(url, headers=headers, body=transformed, timeout_seconds=timeout_seconds)


def _candidate_plan(base: PaidBenchmarkPlan, candidate: Candidate) -> PaidBenchmarkPlan:
    model = EvaluationModel(
        candidate.key,
        candidate.model,
        "current_candidate",
        candidate.availability_checked_at,
        candidate.known_expiration_date,
    )
    return replace(
        base,
        model=model,
        runs_per_case=candidate.repeats_per_case,
        maximum_prompt_price_per_million=candidate.maximum_prompt_price_per_million,
        maximum_completion_price_per_million=candidate.maximum_completion_price_per_million,
        maximum_generation_cost_usd=candidate.maximum_generation_cost_usd,
        maximum_experiment_cost_usd=candidate.maximum_model_cost_usd,
    )


def _candidate_profile(base: SemanticPlanProfile, candidate: Candidate) -> SemanticPlanProfile:
    return replace(
        base,
        exact_model=candidate.model,
        maximum_generation_cost_usd=candidate.maximum_generation_cost_usd,
        maximum_experiment_cost_usd=candidate.maximum_model_cost_usd,
    )


def prepare_model_selection(*, repository_root: str | Path, config_path: str | Path, output_dir: str | Path) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    selection = load_selection_plan(root, config_path)
    expectations = load_expectations(root, selection.expectations_path)
    base_plan, prepared = prepare_semantic_plan_benchmark(
        repository_root=root,
        profile_path=selection.base_profile,
        output_dir=output_dir,
    )
    if len(prepared) != 5 or {item.key for item in prepared} != set(expectations):
        raise EvaluationIntegrityError("Stage 1 expectations must exactly match the frozen five-case corpus")
    manifest_path = Path(output_dir) / PREPARED_MANIFEST
    manifest = _read_json(manifest_path)
    manifest["semantic_model_selection"] = {
        "version": MODEL_SELECTION_VERSION,
        "config_path": PurePosixPath(str(config_path)).as_posix(),
        "expectations_path": selection.expectations_path,
        "maximum_substantive_generations": selection.maximum_substantive_generations,
        "maximum_total_cost_usd": selection.maximum_total_cost_usd,
        "candidates": [asdict(item) for item in selection.candidates],
        "excluded_models": [asdict(item) for item in selection.excluded_models],
    }
    _write_json(manifest_path, manifest)
    return {
        "cases": len(prepared),
        "maximum_substantive_generations": selection.maximum_substantive_generations,
        "candidates": [item.model for item in selection.candidates],
        "base_model": base_plan.model.model,
    }


def _excluded_records(selection: SelectionPlan, catalogue: Mapping[str, Any]) -> list[dict[str, Any]]:
    rows = catalogue.get("data") if isinstance(catalogue, Mapping) else None
    indexed = {str(row.get("id")): row for row in rows or [] if isinstance(row, Mapping) and isinstance(row.get("id"), str)}
    result: list[dict[str, Any]] = []
    for item in selection.excluded_models:
        row = indexed.get(item.model)
        parameters = sorted(str(value) for value in (row or {}).get("supported_parameters", []) if isinstance(value, str))
        result.append({
            "model": item.model,
            "reason": item.reason,
            "generation_allowed": False,
            "catalogue_present": row is not None,
            "supported_parameters": parameters,
            "structured_output_eligible": {"response_format", "structured_outputs"}.issubset(parameters),
        })
    return result


def _runtime(root: Path, output: Path, public_profile: Any, base_profile: SemanticPlanProfile, base_plan: PaidBenchmarkPlan, candidate: Candidate) -> tuple[SemanticPlanProfile, PaidBenchmarkPlan, Any]:
    profile = _candidate_profile(base_profile, candidate)
    plan = _candidate_plan(base_plan, candidate)
    runtime = _semantic_runtime_config(root, profile, public_profile, plan, output)
    runtime = replace(
        runtime,
        max_cost_usd=candidate.maximum_generation_cost_usd,
        provider_policy=replace(
            runtime.provider_policy,
            max_prompt_price_per_million=candidate.maximum_prompt_price_per_million,
            max_completion_price_per_million=candidate.maximum_completion_price_per_million,
        ),
    )
    _write_json(output / "runtime-configs" / f"{candidate.key}-selection.json", {
        "model": runtime.model,
        "prompt_path": runtime.prompt_path,
        "claim_plan_schema_path": runtime.analysis_schema_path,
        "prompt_version": runtime.prompt_version,
        "claim_plan_schema_version": runtime.analysis_schema_version,
        "evidence_schema_version": runtime.evidence_schema_version,
        "temperature_sent": candidate.send_temperature,
        "temperature": runtime.temperature if candidate.send_temperature else None,
        "max_output_tokens": runtime.max_output_tokens,
        "max_cost_usd": runtime.max_cost_usd,
        "provider_policy": runtime.provider_policy.as_request(),
        "cross_model_fallback": runtime.cross_model_fallback,
    })
    return profile, plan, runtime


def _failed_expectation() -> ExpectationResult:
    return ExpectationResult(False, 0.0, 0.0, 0.0, ("canonical_plan_missing",), (), 0, 0)


def _model_summary(candidate: Candidate, rows: list[dict[str, Any]], expected: int, route: Mapping[str, Any] | None) -> dict[str, Any]:
    average = lambda key: statistics.mean(float(row[key]) for row in rows) if rows else 0.0
    semantic = average("semantic_coverage")
    materiality = average("materiality")
    restraint = average("restraint")
    repeat_stability = stability(rows)
    quality = semantic * 40 + materiality * 25 + restraint * 20 + repeat_stability * 15
    route_cost = route.get("estimated_cost_usd") if isinstance(route, Mapping) else None
    run_costs = [row.get("estimated_cost_usd") for row in rows]
    complete_cost = len(rows) == expected and isinstance(route_cost, (int, float)) and all(isinstance(value, (int, float)) for value in run_costs)
    corpus_cost = sum(float(value) for value in run_costs if isinstance(value, (int, float)))
    total_cost = corpus_cost + float(route_cost or 0.0)
    passes = sum(row.get("hard_pass") is True for row in rows)
    route_ok = isinstance(route, Mapping) and route.get("status") == "passed"
    qualified = route_ok and len(rows) == expected and passes == expected and complete_cost and total_cost <= candidate.maximum_model_cost_usd + 1e-12
    return {
        "model_key": candidate.key,
        "model": candidate.model,
        "role": candidate.role,
        "deployment_eligible": candidate.deployment_eligible,
        "expected_runs": expected,
        "completed_runs": len(rows),
        "hard_passes": passes,
        "qualified": qualified,
        "semantic_coverage": semantic,
        "materiality": materiality,
        "restraint": restraint,
        "stability": repeat_stability,
        "quality_score": quality,
        "latency_ms": distribution(row.get("latency_ms") for row in rows),
        "input_tokens": distribution(row.get("input_tokens") for row in rows),
        "output_tokens": distribution(row.get("output_tokens") for row in rows),
        "route_cost_usd": route_cost,
        "corpus_cost_usd": corpus_cost,
        "total_cost_usd": total_cost,
        "cost_metadata_complete": complete_cost,
        "provider_fallback_runs": sum(row.get("provider_fallback_used") is True for row in rows),
        "cross_model_fallback_runs": sum(row.get("cross_model_fallback_used") is True for row in rows),
        "actual_providers": sorted({str(row.get("actual_provider")) for row in rows if row.get("actual_provider")}),
        "cost_per_hard_pass_usd": total_cost / passes if passes else None,
    }


def execute_model_selection(
    *,
    repository_root: str | Path,
    config_path: str | Path,
    prepared_dir: str | Path,
    output_dir: str | Path,
    api_key: str | None = None,
    trusted_main_sha: str | None = None,
    catalogue_loader: Any = None,
    sleeper: Any = None,
    monotonic: Any = None,
    now: Any = None,
    jitter: Any = None,
) -> dict[str, Any]:
    if not api_key:
        raise EvaluationIntegrityError("OPENROUTER_API_KEY is required for model selection")
    root = Path(repository_root).resolve()
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    selection = load_selection_plan(root, config_path)
    expectations = load_expectations(root, selection.expectations_path)
    base_profile = load_semantic_plan_profile(root, selection.base_profile)
    public_profile, base_plan, classifications = _validate_profile_chain(root, base_profile)
    prepared = _prepared_cases(base_plan, Path(prepared_dir))
    manifest = _read_json(Path(prepared_dir) / PREPARED_MANIFEST)
    selected_manifest = manifest.get("semantic_model_selection")
    if not isinstance(selected_manifest, Mapping) or selected_manifest.get("version") != MODEL_SELECTION_VERSION:
        raise EvaluationIntegrityError("prepared corpus is not a semantic model-selection manifest")

    catalogue = (catalogue_loader or _catalogue)()
    excluded = _excluded_records(selection, catalogue)
    _write_json(output / EXCLUDED_RESULTS, {"models": excluded})
    policy = load_viability_policy(root / selection.viability_config)
    pacer_args = {key: value for key, value in {"sleeper": sleeper, "monotonic": monotonic, "now": now, "jitter": jitter}.items() if value is not None}
    pacer = AttemptPacer(policy, **pacer_args)
    classification_by_case = {str(row["case_key"]): str(row["classification"]) for row in classifications}
    availability_rows: list[dict[str, Any]] = []
    route_rows: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []
    route_by_model: dict[str, dict[str, Any]] = {}
    observed_cost = 0.0

    for candidate in selection.candidates:
        profile, plan, runtime = _runtime(root, output, public_profile, base_profile, base_plan, candidate)
        availability = check_paid_model_availability(plan, catalogue_loader=lambda: catalogue)
        availability_rows.append({
            "candidate": asdict(candidate),
            "availability": asdict(availability.availability),
            "prompt_price_per_million": availability.prompt_price_per_million,
            "completion_price_per_million": availability.completion_price_per_million,
            "context_length": availability.context_length,
            "maximum_completion_tokens": availability.maximum_completion_tokens,
        })
        if not availability.availability.eligible:
            row = {"model_key": candidate.key, "requested_model": candidate.model, "status": "not_attempted", "failure_code": availability.availability.reason or "catalogue_ineligible"}
            route_rows.append(row)
            route_by_model[candidate.key] = row
            continue
        if observed_cost + candidate.maximum_generation_cost_usd > selection.maximum_total_cost_usd + 1e-12:
            raise EvaluationIntegrityError("whole evaluation cost ceiling would be exceeded by route preflight")
        route_transport = _BodyTransformTransport(UrllibTransport(), send_temperature=candidate.send_temperature)
        try:
            route = pacer.call(
                f"route-preflight/{candidate.key}",
                lambda: projected_paid_route_probe(runtime, api_key, transport=route_transport),
            )
            row = {"model_key": candidate.key, "status": "passed", **dict(route)}
            cost = route.get("estimated_cost_usd")
            if isinstance(cost, (int, float)) and not isinstance(cost, bool):
                observed_cost += float(cost)
        except Exception as exc:
            row = {
                "model_key": candidate.key,
                "requested_model": candidate.model,
                "status": "failed",
                "failure_code": str(getattr(exc, "code", None) or "route_preflight_failure"),
                "message": " ".join(str(exc).split())[:500].replace(api_key, "[REDACTED]"),
            }
        route_rows.append(row)
        route_by_model[candidate.key] = row
        if row["status"] != "passed":
            continue

        generation_transport = _BodyTransformTransport(ClassifiedTransport(), send_temperature=candidate.send_temperature)
        factory = PacedClientFactory(pacer, builder=lambda config, transport=generation_transport: OpenRouterClient(config, transport=transport))
        for case in prepared:
            for repeat_index in range(1, candidate.repeats_per_case + 1):
                if observed_cost + candidate.maximum_generation_cost_usd > selection.maximum_total_cost_usd + 1e-12:
                    raise EvaluationIntegrityError("whole evaluation cost ceiling would be exceeded by the next generation")
                factory.set_logical_id(f"corpus/{candidate.key}/{case.key}/repeat-{repeat_index}")
                record = _run_one(
                    root=root,
                    profile=profile,
                    plan=plan,
                    config=runtime,
                    prepared=case,
                    prepared_dir=Path(prepared_dir),
                    repeat=repeat_index,
                    classification=classification_by_case[case.key],
                    output=output,
                    api_key=api_key,
                    client_factory=factory,
                )
                if record.estimated_cost_usd is not None:
                    observed_cost += float(record.estimated_cost_usd)
                run_dir = output / record.output_dir
                canonical = run_dir / "canonical-claim-plan.json"
                expectation = evaluate_expectation(_read_json(canonical), expectations[case.key]) if canonical.exists() else _failed_expectation()
                _write_json(run_dir / "case-expectation.json", asdict(expectation))
                hard_pass = (
                    record.status == "accepted"
                    and expectation.hard_pass
                    and record.actual_model is not None
                    and model_matches(candidate.model, record.actual_model)
                    and bool(record.actual_provider)
                    and record.provider_fallback_used is not None
                    and record.cross_model_fallback_used is False
                    and record.estimated_cost_usd is not None
                )
                records.append({
                    **asdict(record),
                    "candidate_role": candidate.role,
                    "deployment_eligible": candidate.deployment_eligible,
                    "expectation_hard_pass": expectation.hard_pass,
                    "hard_pass": hard_pass,
                    "semantic_coverage": expectation.semantic_coverage,
                    "materiality": expectation.materiality,
                    "restraint": expectation.restraint,
                    "expectation_diagnostics": list(expectation.diagnostics),
                    "claim_signatures": list(expectation.claim_signatures),
                    "claim_count": expectation.claim_count,
                    "redundant_claim_count": expectation.redundant_claim_count,
                })

    _write_json(output / AVAILABILITY_RESULTS, {"models": availability_rows})
    _write_json(output / ROUTE_RESULTS, {"routes": route_rows})
    _write_json(output / ATTEMPT_RECORDS_FILE, {"attempts": [asdict(item) for item in pacer.records]})
    if observed_cost > selection.maximum_total_cost_usd + 1e-12:
        raise EvaluationIntegrityError("observed evaluation cost exceeded the whole evaluation ceiling")

    models = [
        _model_summary(
            candidate,
            [row for row in records if row["model_key"] == candidate.key],
            len(prepared) * candidate.repeats_per_case,
            route_by_model.get(candidate.key),
        )
        for candidate in selection.candidates
    ]
    benchmark = next((row["quality_score"] for row in models if row["role"] == "quality_benchmark"), None)
    for row in models:
        row["quality_retained_vs_benchmark"] = row["quality_score"] / benchmark if isinstance(benchmark, (int, float)) and benchmark > 0 else None
    quality_rows = sorted(models, key=lambda row: (-float(row["quality_score"]), row["model_key"]))
    deployment_rows = sorted(
        [row for row in models if row["deployment_eligible"]],
        key=lambda row: (not bool(row["qualified"]), -float(row["quality_retained_vs_benchmark"] or 0), float(row["cost_per_hard_pass_usd"] or float("inf"))),
    )
    summary = {
        "version": MODEL_SELECTION_VERSION,
        "trusted_main_sha": trusted_main_sha,
        "base_profile": selection.base_profile,
        "cases": len(prepared),
        "maximum_substantive_generations": selection.maximum_substantive_generations,
        "completed_substantive_generations": len(records),
        "maximum_total_cost_usd": selection.maximum_total_cost_usd,
        "observed_total_cost_usd": observed_cost,
        "automatic_generation": False,
        "publication": False,
        "models": models,
        "quality_leaderboard": [row["model_key"] for row in quality_rows],
        "deployment_leaderboard": [row["model_key"] for row in deployment_rows],
        "records": records,
        "excluded_models": excluded,
    }
    _write_json(output / SELECTION_SUMMARY, summary)
    write_leaderboards(output, quality_rows, deployment_rows)
    write_scorecard(output, records)
    (output / ACTIONS_SUMMARY).write_text(actions_summary(summary), encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--repository-root", default=".")
    prepare.add_argument("--config", default="config/semantic-plan-model-selection.yml")
    prepare.add_argument("--output-dir", required=True)
    run = commands.add_parser("run")
    run.add_argument("--repository-root", default=".")
    run.add_argument("--config", default="config/semantic-plan-model-selection.yml")
    run.add_argument("--prepared-dir", required=True)
    run.add_argument("--output-dir", required=True)
    run.add_argument("--trusted-main-sha")
    args = parser.parse_args()
    try:
        result = (
            prepare_model_selection(repository_root=args.repository_root, config_path=args.config, output_dir=args.output_dir)
            if args.command == "prepare"
            else execute_model_selection(
                repository_root=args.repository_root,
                config_path=args.config,
                prepared_dir=args.prepared_dir,
                output_dir=args.output_dir,
                api_key=os.environ.get("OPENROUTER_API_KEY"),
                trusted_main_sha=args.trusted_main_sha,
            )
        )
        print(json.dumps(result, sort_keys=True))
        return 0
    except (EvaluationConfigurationError, EvaluationIntegrityError, OSError, ValueError, TypeError) as exc:
        print(f"semantic model selection failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
