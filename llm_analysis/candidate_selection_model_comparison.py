"""Prepare and run the governed Phase 6 bounded-selector comparison."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import statistics
import sys
from dataclasses import asdict, replace
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Mapping, Sequence

from .candidate_selection_contract import build_candidate_selector_request
from .candidate_selection_model_comparison_config import (
    COMPARISON_CONFIG_VERSION,
    CandidateSelectionComparisonPlan,
    ComparisonModel,
    load_candidate_selection_comparison_plan,
)
from .candidate_selection_model_scoring import (
    apply_predeclared_decision,
    score_selection,
    summarize_model,
)
from .candidate_selector import run_bounded_candidate_selector
from .claim_candidate_compiler import compile_claim_candidates
from .claim_candidate_gold_corpus import (
    _forbidden_matches,
    evaluate_claim_candidate_gold_corpus,
    load_claim_candidate_gold_manifest,
)
from .contracts import canonical_json_bytes, content_sha256
from .deterministic_baseline_evaluation import evaluate_deterministic_baseline
from .deterministic_ranking import load_ranking_config, run_deterministic_baseline
from .evaluation import (
    EvaluationConfigurationError,
    EvaluationIntegrityError,
    EvaluationModel,
    _catalogue,
    _read_json,
    _write_json,
    prepare_evaluation,
)
from .evaluation_viability import (
    ATTEMPT_RECORDS_FILE,
    AttemptPacer,
    ClassifiedTransport,
    load_viability_policy,
)
from .generation_config import GenerationConfig
from .openrouter_candidate_selector import OpenRouterCandidateSelectorClient
from .openrouter_client import Transport, UrllibTransport
from .paid_benchmark import PaidBenchmarkPlan, check_paid_model_availability
from .semantic_plan_benchmark import (
    SemanticPlanProfile,
    _semantic_runtime_config,
    _validate_profile_chain,
    load_semantic_plan_profile,
)
from .semantic_plan_protected_runner import projected_paid_route_probe

COMPARISON_VERSION = "phase-06-candidate-selection-model-comparison/v1"
PREPARED_VERSION = "phase-06-candidate-selection-model-comparison-prepared/v1"
PREPARED_MANIFEST = "candidate-selection-comparison-prepared.json"
SUMMARY_FILE = "candidate-selection-comparison-summary.json"
RUNS_FILE = "candidate-selection-comparison-runs.json"
AVAILABILITY_FILE = "model-availability.json"
ROUTES_FILE = "route-preflight.json"
DECISION_INPUT_FILE = "decision-input.md"
ACTIONS_SUMMARY = "actions-summary.md"
REVIEWER_CSV = "reviewer-scorecard.csv"
DEFAULT_CONFIG = "config/candidate-selection-model-comparison.yml"


class _BodyTransformTransport:
    def __init__(self, inner: Transport, *, send_temperature: bool) -> None:
        self.inner = inner
        self.send_temperature = send_temperature

    def post(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        body: bytes,
        timeout_seconds: float,
    ) -> Any:
        transformed = body
        if not self.send_temperature:
            payload = json.loads(body.decode("utf-8"))
            if not isinstance(payload, dict):
                raise EvaluationIntegrityError("OpenRouter request body must be an object")
            payload.pop("temperature", None)
            transformed = canonical_json_bytes(payload)
        return self.inner.post(
            url,
            headers=headers,
            body=transformed,
            timeout_seconds=timeout_seconds,
        )


class _BudgetLedger:
    def __init__(self, plan: CandidateSelectionComparisonPlan) -> None:
        self.plan = plan
        self.total_cost = 0.0
        self.model_costs = {item.key: 0.0 for item in plan.models}
        self.substantive_calls = 0
        self.route_probes = 0

    def before_route(self, model: ComparisonModel) -> None:
        if self.route_probes >= self.plan.maximum_route_probes:
            raise EvaluationIntegrityError("route-probe ceiling would be exceeded")
        self._check_cost(model, model.maximum_generation_cost_usd)
        self.route_probes += 1

    def before_generation(self, model: ComparisonModel, maximum_cost: float) -> None:
        if self.substantive_calls >= self.plan.maximum_substantive_generations:
            raise EvaluationIntegrityError("substantive generation ceiling would be exceeded")
        self._check_cost(model, maximum_cost)
        self.substantive_calls += 1

    def _check_cost(self, model: ComparisonModel, maximum_cost: float) -> None:
        if self.total_cost + maximum_cost > self.plan.maximum_total_cost_usd + 1e-12:
            raise EvaluationIntegrityError("whole-run cost ceiling would be exceeded")
        if (
            self.model_costs[model.key] + maximum_cost
            > model.maximum_model_cost_usd + 1e-12
        ):
            raise EvaluationIntegrityError(f"{model.key} cost ceiling would be exceeded")

    def add(self, model: ComparisonModel, actual_cost: float) -> None:
        if actual_cost < 0:
            raise EvaluationIntegrityError("provider cost must not be negative")
        self.total_cost += actual_cost
        self.model_costs[model.key] += actual_cost
        if self.total_cost > self.plan.maximum_total_cost_usd + 1e-12:
            raise EvaluationIntegrityError("observed whole-run cost exceeded the ceiling")
        if self.model_costs[model.key] > model.maximum_model_cost_usd + 1e-12:
            raise EvaluationIntegrityError(f"observed {model.key} cost exceeded its ceiling")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise EvaluationIntegrityError(f"{path} must contain a JSON object")
    return value


def _relative(root: Path, path: Path) -> str:
    return PurePosixPath(path.relative_to(root).as_posix()).as_posix()


def _f1(precision: float, recall: float) -> float:
    return 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)


def _verify_baseline(
    plan: CandidateSelectionComparisonPlan,
    baseline: Mapping[str, Any],
) -> None:
    overall = baseline.get("overall")
    if not isinstance(overall, Mapping):
        raise EvaluationIntegrityError("deterministic baseline summary is missing overall")
    expected = plan.baseline_reference
    actual = {
        "selected_count": int(overall.get("selected_count", -1)),
        "selected_useful_count": int(overall.get("selected_useful_count", -1)),
        "gold_useful_count": int(overall.get("gold_useful_count", -1)),
        "precision": float(overall.get("selected_useful_precision", -1.0)),
        "recall": float(overall.get("selected_useful_recall", -1.0)),
    }
    actual["f1"] = _f1(actual["precision"], actual["recall"])
    declared = asdict(expected)
    for key in ("selected_count", "selected_useful_count", "gold_useful_count"):
        if actual[key] != declared[key]:
            raise EvaluationIntegrityError(f"baseline {key} differs from the reviewed contract")
    for key in ("precision", "recall", "f1"):
        if abs(actual[key] - declared[key]) > 1e-12:
            raise EvaluationIntegrityError(f"baseline {key} differs from the reviewed contract")


def prepare_candidate_selection_comparison(
    *,
    repository_root: str | Path,
    config_path: str | Path = DEFAULT_CONFIG,
    output_dir: str | Path,
) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    plan = load_candidate_selection_comparison_plan(root, config_path)
    gold_manifest = load_claim_candidate_gold_manifest(root, plan.gold_manifest)
    gold = evaluate_claim_candidate_gold_corpus(root, plan.gold_manifest).summary
    baseline = evaluate_deterministic_baseline(
        root,
        ranking_config_path=plan.ranking_config,
        gold_manifest_path=plan.gold_manifest,
    ).summary
    _verify_baseline(plan, baseline)

    source_dir = output / "source-corpus"
    _, prepared = prepare_evaluation(
        repository_root=root,
        config_path=gold_manifest["source_evaluation_config"],
        output_dir=source_dir,
    )
    if len(prepared) != 5:
        raise EvaluationIntegrityError("Slice 6 must use exactly five frozen cases")
    prepared_by_key = {item.key: item for item in prepared}
    gold_by_key = {item["key"]: item for item in gold["cases"]}
    baseline_by_key = {item["key"]: item for item in baseline["cases"]}
    case_manifest_by_key = {item["key"]: item for item in gold_manifest["cases"]}

    evidence_schema = _read_object(root / "schemas/crypto-market-evidence-bundle-v1.json")
    candidate_schema = _read_object(root / "schemas/crypto-market-claim-candidate-v1.json")
    claim_plan_schema = _read_object(root / "schemas/crypto-market-claim-plan-v1.json")
    selection_schema = _read_object(root / plan.selection_schema)
    ranking = load_ranking_config(root, plan.ranking_config)

    cases: list[dict[str, Any]] = []
    for case_key in [item["key"] for item in gold_manifest["cases"]]:
        prepared_case = prepared_by_key[case_key]
        case_dir = output / "cases" / case_key
        case_dir.mkdir(parents=True, exist_ok=True)
        bundle = _read_object(source_dir / prepared_case.bundle_file)
        candidates = list(
            compile_claim_candidates(
                bundle,
                evidence_schema=evidence_schema,
                candidate_schema=candidate_schema,
            )
        )
        baseline_result = run_deterministic_baseline(
            bundle,
            candidates,
            config=ranking,
            evidence_schema=evidence_schema,
            candidate_schema=candidate_schema,
            claim_plan_schema=claim_plan_schema,
        )
        reviewed = gold_by_key[case_key]
        expected_sha = reviewed["ordered_candidate_sha256"]
        if content_sha256(candidates) != expected_sha:
            raise EvaluationIntegrityError(f"{case_key} candidate set differs from gold review")
        useful_ids = sorted(
            str(item["candidate_id"]) for item in reviewed["resolved_candidates"]
        )
        case_manifest = case_manifest_by_key[case_key]
        prohibited_ids = sorted(
            {
                identifier
                for rule in case_manifest["forbidden"]
                for identifier in _forbidden_matches(rule, candidates, bundle)
            }
        )
        if prohibited_ids:
            raise EvaluationIntegrityError(
                f"{case_key} compiler emitted a prohibited candidate before model evaluation"
            )
        request = build_candidate_selector_request(
            candidates,
            config=ranking,
            evidence_bundle_id=bundle["bundle_id"],
        )
        paths = {
            "bundle": case_dir / "evidence-bundle.json",
            "candidates": case_dir / "claim-candidates.json",
            "baseline_selection": case_dir / "baseline-selection.json",
            "baseline_plan": case_dir / "baseline-plan.json",
            "baseline_render": case_dir / "baseline-render.md",
            "selector_request": case_dir / "selector-request.json",
            "reviewed_ids": case_dir / "reviewed-candidate-ids.json",
        }
        _write_json(paths["bundle"], bundle)
        _write_json(paths["candidates"], {"candidates": candidates})
        _write_json(paths["baseline_selection"], baseline_result.selection)
        _write_json(paths["baseline_plan"], baseline_result.claim_plan)
        paths["baseline_render"].write_bytes(baseline_result.render.markdown)
        _write_json(paths["selector_request"], request)
        _write_json(
            paths["reviewed_ids"],
            {
                "useful_candidate_ids": useful_ids,
                "prohibited_candidate_ids": prohibited_ids,
            },
        )
        baseline_case = baseline_by_key[case_key]
        if baseline_result.selection["selected_candidate_ids"] != baseline_case["selection"]["selected_candidate_ids"]:
            raise EvaluationIntegrityError(f"{case_key} prepared baseline selection drifted")
        cases.append(
            {
                "key": case_key,
                "classification": case_manifest["classification"],
                "bundle_id": bundle["bundle_id"],
                "candidate_count": len(candidates),
                "ordered_candidate_sha256": content_sha256(candidates),
                "candidate_set_id": request["candidate_set_id"],
                "request_id": request["request_id"],
                "useful_candidate_ids": useful_ids,
                "prohibited_candidate_ids": prohibited_ids,
                "baseline_selected_candidate_ids": list(
                    baseline_result.selection["selected_candidate_ids"]
                ),
                "paths": {key: _relative(output, value) for key, value in paths.items()},
                "hashes": {
                    "bundle": content_sha256(bundle),
                    "candidates": content_sha256(candidates),
                    "baseline_selection": content_sha256(baseline_result.selection),
                    "baseline_plan": content_sha256(baseline_result.claim_plan),
                    "baseline_render": _sha256_bytes(baseline_result.render.markdown),
                    "selector_request": content_sha256(request),
                },
            }
        )

    manifest = {
        "version": PREPARED_VERSION,
        "comparison_version": COMPARISON_VERSION,
        "configuration_version": COMPARISON_CONFIG_VERSION,
        "config_path": PurePosixPath(str(config_path)).as_posix(),
        "config_sha256": content_sha256(asdict(plan)),
        "gold_manifest": plan.gold_manifest,
        "gold_summary_version": gold["version"],
        "ranking_config": plan.ranking_config,
        "selection_schema": plan.selection_schema,
        "selector_prompt": plan.selector_prompt,
        "baseline": baseline["overall"],
        "models": [asdict(item) for item in plan.models],
        "limits": {
            "maximum_logical_runs": plan.maximum_logical_runs,
            "maximum_substantive_generations": plan.maximum_substantive_generations,
            "maximum_route_probes": plan.maximum_route_probes,
            "maximum_semantic_repairs_per_run": plan.maximum_semantic_repairs_per_run,
            "maximum_total_cost_usd": plan.maximum_total_cost_usd,
        },
        "cases": cases,
    }
    _write_json(output / PREPARED_MANIFEST, manifest)
    return {
        "version": PREPARED_VERSION,
        "case_count": len(cases),
        "candidate_counts": {item["key"]: item["candidate_count"] for item in cases},
        "baseline": baseline["overall"],
        "models": [item.model for item in plan.models],
        "provider_calls": 0,
    }


def _model_plan(
    base: PaidBenchmarkPlan,
    model: ComparisonModel,
) -> PaidBenchmarkPlan:
    return replace(
        base,
        model=EvaluationModel(
            model.key,
            model.model,
            "current_candidate",
            model.availability_checked_at,
            model.known_expiration_date,
        ),
        runs_per_case=model.repeats_per_case,
        maximum_prompt_price_per_million=model.maximum_prompt_price_per_million,
        maximum_completion_price_per_million=model.maximum_completion_price_per_million,
        maximum_generation_cost_usd=model.maximum_generation_cost_usd,
        maximum_experiment_cost_usd=model.maximum_model_cost_usd,
    )


def _model_runtime(
    root: Path,
    output: Path,
    comparison: CandidateSelectionComparisonPlan,
    public_profile: Any,
    base_profile: SemanticPlanProfile,
    base_plan: PaidBenchmarkPlan,
    model: ComparisonModel,
) -> tuple[PaidBenchmarkPlan, GenerationConfig]:
    profile = replace(
        base_profile,
        exact_model=model.model,
        maximum_generation_cost_usd=model.maximum_generation_cost_usd,
        maximum_experiment_cost_usd=model.maximum_model_cost_usd,
    )
    paid_plan = _model_plan(base_plan, model)
    runtime = _semantic_runtime_config(
        root,
        profile,
        public_profile,
        paid_plan,
        output,
    )
    runtime = replace(
        runtime,
        prompt_path=comparison.selector_prompt,
        analysis_schema_path=comparison.selection_schema,
        prompt_version="crypto-market-candidate-selection/v1",
        analysis_schema_version="crypto-market-candidate-selection/v1",
        temperature=0.0,
        max_output_tokens=512,
        max_cost_usd=model.maximum_generation_cost_usd,
        retry_limit=0,
        cross_model_fallback=False,
        provider_policy=replace(
            runtime.provider_policy,
            data_collection="deny",
            zdr=False,
            allow_fallbacks=False,
            order=(),
            only=(model.allowed_actual_provider,),
            ignore=(),
            sort=None,
            max_prompt_price_per_million=model.maximum_prompt_price_per_million,
            max_completion_price_per_million=model.maximum_completion_price_per_million,
            max_request_price=model.maximum_generation_cost_usd,
        ),
    )
    _write_json(
        output / "runtime-configs" / f"{model.key}.json",
        {
            "model": runtime.model,
            "allowed_actual_provider": model.allowed_actual_provider,
            "prompt_path": runtime.prompt_path,
            "selection_schema_path": runtime.analysis_schema_path,
            "max_output_tokens": runtime.max_output_tokens,
            "max_request_bytes": runtime.max_request_bytes,
            "max_cost_usd": runtime.max_cost_usd,
            "temperature_sent": model.send_temperature,
            "provider_policy": runtime.provider_policy.as_request(),
            "cross_model_fallback": runtime.cross_model_fallback,
            "automatic_generation": False,
            "publication": False,
        },
    )
    return paid_plan, runtime


def _redundant_selection_count(
    selected_ids: Sequence[str],
    candidates: Sequence[Mapping[str, Any]],
) -> int:
    indexed = {str(item["candidate_id"]): item for item in candidates}
    groups: list[str] = []
    for identifier in selected_ids:
        features = indexed.get(identifier, {}).get("features")
        group = features.get("redundancy_group") if isinstance(features, Mapping) else None
        if isinstance(group, str):
            groups.append(group)
    return len(groups) - len(set(groups))


def _safe_provider_calls(calls: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {key: value for key, value in call.items() if key != "raw_completion"}
        for call in calls
    ]


def _decision_markdown(summary: Mapping[str, Any]) -> str:
    decision = summary["predeclared_decision"]
    lines = [
        "# Phase 6 bounded-selector comparison decision input",
        "",
        "> This is deterministic decision input, not an automatic production approval.",
        "",
        f"- Trusted main SHA: `{summary.get('trusted_main_sha')}`",
        f"- Protected outcome: `{decision['outcome']}`",
        f"- Completed substantive calls: `{summary['completed_substantive_generations']} / {summary['maximum_substantive_generations']}`",
        f"- Observed total cost: `USD {summary['observed_total_cost_usd']:.6f}`",
        "",
        "## Model comparison",
        "",
        "| Role | Model | Accepted | Fallback | Precision | Recall | F1 | Stability | Cost | Governance |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for model in summary["models"]:
        lines.append(
            f"| `{model['role']}` | `{model['model']}` | {model['accepted_runs']} / {model['expected_runs']} | "
            f"{model['fallback_runs']} | {model['precision']:.2%} | {model['recall']:.2%} | "
            f"{model['f1']:.2%} | {model['mean_pairwise_jaccard']:.3f} | "
            f"USD {model['total_cost_usd']:.6f} | `{str(model['governance_pass']).lower()}` |"
        )
    lines.extend(
        [
            "",
            "## Predeclared gate results",
            "",
            f"Quality gate: `{json.dumps(decision.get('quality_gate', {}), sort_keys=True)}`",
            "",
            f"Deployment gate: `{json.dumps(decision.get('deployment_gate', {}), sort_keys=True)}`",
            "",
            "A separate reviewed issue and pull request must confirm or reject this outcome. This workflow cannot enable generation, change ranking, publish a report or promote a model.",
            "",
        ]
    )
    return "\n".join(lines)


def _write_reviewer_csv(path: Path, records: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "model_key",
        "model",
        "case_key",
        "repeat_index",
        "outcome",
        "fallback_used",
        "fallback_reason",
        "semantic_repair_count",
        "selected_count",
        "useful_selected_count",
        "useful_expected_count",
        "precision",
        "recall",
        "f1",
        "prohibited_selected_count",
        "provider_call_count",
        "logical_latency_ms",
        "logical_cost_usd",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in records:
            writer.writerow(
                {
                    "model_key": row["model_key"],
                    "model": row["model"],
                    "case_key": row["case_key"],
                    "repeat_index": row["repeat_index"],
                    "outcome": row["outcome"],
                    "fallback_used": row["fallback_used"],
                    "fallback_reason": row["fallback_reason"],
                    "semantic_repair_count": row["semantic_repair_count"],
                    "selected_count": row["selected_count"],
                    "useful_selected_count": row["useful_selected_count"],
                    "useful_expected_count": row["useful_expected_count"],
                    "precision": row["precision"],
                    "recall": row["recall"],
                    "f1": row["f1"],
                    "prohibited_selected_count": len(
                        row["prohibited_selected_candidate_ids"]
                    ),
                    "provider_call_count": len(row["provider_calls"]),
                    "logical_latency_ms": row["logical_latency_ms"],
                    "logical_cost_usd": row["logical_cost_usd"],
                }
            )


def execute_candidate_selection_comparison(
    *,
    repository_root: str | Path,
    config_path: str | Path = DEFAULT_CONFIG,
    prepared_dir: str | Path,
    output_dir: str | Path,
    api_key: str | None,
    trusted_main_sha: str | None = None,
    catalogue_loader: Callable[[], Mapping[str, Any]] | None = None,
    route_probe: Callable[..., Mapping[str, Any]] = projected_paid_route_probe,
    transport_factory: Callable[[], Transport] | None = None,
    sleeper: Any = None,
    monotonic: Any = None,
    now: Any = None,
    jitter: Any = None,
) -> dict[str, Any]:
    if not api_key:
        raise EvaluationIntegrityError("OPENROUTER_API_KEY is required")
    root = Path(repository_root).resolve()
    prepared_root = Path(prepared_dir).resolve()
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    comparison = load_candidate_selection_comparison_plan(root, config_path)
    manifest = _read_object(prepared_root / PREPARED_MANIFEST)
    if manifest.get("version") != PREPARED_VERSION:
        raise EvaluationIntegrityError("prepared corpus has the wrong Slice 6 version")
    if manifest.get("config_sha256") != content_sha256(asdict(comparison)):
        raise EvaluationIntegrityError("prepared corpus and checked-in comparison config differ")
    if len(manifest.get("cases", [])) != 5:
        raise EvaluationIntegrityError("prepared comparison must contain five cases")

    evidence_schema = _read_object(root / "schemas/crypto-market-evidence-bundle-v1.json")
    candidate_schema = _read_object(root / "schemas/crypto-market-claim-candidate-v1.json")
    claim_plan_schema = _read_object(root / "schemas/crypto-market-claim-plan-v1.json")
    selection_schema = _read_object(root / comparison.selection_schema)
    ranking = load_ranking_config(root, comparison.ranking_config)
    prompt_template = (root / comparison.selector_prompt).read_text(encoding="utf-8")

    base_profile = load_semantic_plan_profile(root, comparison.base_profile)
    public_profile, base_plan, classifications = _validate_profile_chain(root, base_profile)
    expected_classifications = {
        str(item["key"]): str(item["classification"])
        for item in manifest["cases"]
    }
    for key, classification in expected_classifications.items():
        expected_public = "evaluation-only" if classification == "evaluation-only" else "public-market-data"
        if classifications.get(key) != expected_public:
            raise EvaluationIntegrityError(f"input classification mismatch for {key}")

    catalogue = (catalogue_loader or _catalogue)()
    policy = load_viability_policy(root / comparison.viability_config)
    policy = replace(policy, maximum_attempts=1)
    pacer_kwargs = {
        key: value
        for key, value in {
            "sleeper": sleeper,
            "monotonic": monotonic,
            "now": now,
            "jitter": jitter,
        }.items()
        if value is not None
    }
    pacer = AttemptPacer(policy, **pacer_kwargs)
    ledger = _BudgetLedger(comparison)
    availability_rows: list[dict[str, Any]] = []
    route_rows: list[dict[str, Any]] = []
    route_by_key: dict[str, dict[str, Any]] = {}
    availability_by_key: dict[str, dict[str, Any]] = {}
    records: list[dict[str, Any]] = []
    transport_builder = transport_factory or (lambda: ClassifiedTransport())

    for model in comparison.models:
        paid_plan, runtime = _model_runtime(
            root,
            output,
            comparison,
            public_profile,
            base_profile,
            base_plan,
            model,
        )
        availability = check_paid_model_availability(
            paid_plan,
            catalogue_loader=lambda: catalogue,
        )
        availability_row = {
            "model_key": model.key,
            "model": model.model,
            "allowed_actual_provider": model.allowed_actual_provider,
            "availability": asdict(availability.availability),
            "prompt_price_per_million": availability.prompt_price_per_million,
            "completion_price_per_million": availability.completion_price_per_million,
            "context_length": availability.context_length,
            "maximum_completion_tokens": availability.maximum_completion_tokens,
        }
        availability_rows.append(availability_row)
        availability_by_key[model.key] = availability_row
        if not availability.availability.eligible:
            route_row = {
                "model_key": model.key,
                "requested_model": model.model,
                "status": "not_attempted",
                "failure_code": availability.availability.reason or "catalogue_ineligible",
            }
            route_rows.append(route_row)
            route_by_key[model.key] = route_row
            continue

        ledger.before_route(model)
        route_transport = _BodyTransformTransport(
            UrllibTransport(),
            send_temperature=model.send_temperature,
        )
        try:
            route_result = pacer.call(
                f"route-preflight/{model.key}",
                lambda: route_probe(
                    runtime,
                    api_key,
                    transport=route_transport,
                ),
            )
            route_cost = route_result.get("estimated_cost_usd")
            if isinstance(route_cost, bool) or not isinstance(route_cost, (int, float)):
                raise EvaluationIntegrityError("route probe did not report cost")
            ledger.add(model, float(route_cost))
            if route_result.get("actual_provider") != model.allowed_actual_provider:
                raise EvaluationIntegrityError(
                    f"{model.key} route selected an unapproved provider"
                )
            route_row = {"model_key": model.key, "status": "passed", **dict(route_result)}
        except Exception as exc:
            route_row = {
                "model_key": model.key,
                "requested_model": model.model,
                "status": "failed",
                "failure_code": str(getattr(exc, "code", None) or "route_preflight_failure"),
                "message": " ".join(str(exc).split())[:500].replace(api_key, "[REDACTED]"),
            }
        route_rows.append(route_row)
        route_by_key[model.key] = route_row
        if route_row["status"] != "passed":
            continue

        for case in manifest["cases"]:
            case_key = str(case["key"])
            paths = case["paths"]
            bundle = _read_object(prepared_root / paths["bundle"])
            candidate_payload = _read_object(prepared_root / paths["candidates"])
            candidates = candidate_payload.get("candidates")
            if not isinstance(candidates, list):
                raise EvaluationIntegrityError(f"prepared candidates missing for {case_key}")
            if content_sha256(candidates) != case["hashes"]["candidates"]:
                raise EvaluationIntegrityError(f"prepared candidates changed for {case_key}")
            useful_ids = list(case["useful_candidate_ids"])
            prohibited_ids = set(case["prohibited_candidate_ids"])
            direct_baseline = run_deterministic_baseline(
                bundle,
                candidates,
                config=ranking,
                evidence_schema=evidence_schema,
                candidate_schema=candidate_schema,
                claim_plan_schema=claim_plan_schema,
            )
            if direct_baseline.selection["selected_candidate_ids"] != case["baseline_selected_candidate_ids"]:
                raise EvaluationIntegrityError(f"runtime baseline drifted for {case_key}")

            for repeat_index in range(1, model.repeats_per_case + 1):
                logical_id = f"corpus/{model.key}/{case_key}/repeat-{repeat_index}"
                client = OpenRouterCandidateSelectorClient(
                    runtime,
                    prompt_template=prompt_template,
                    api_key=api_key,
                    logical_id=logical_id,
                    transport=transport_builder(),
                    pacer=pacer,
                    send_temperature=model.send_temperature,
                    monotonic=monotonic or __import__("time").monotonic,
                    before_provider_call=lambda maximum, current=model: ledger.before_generation(
                        current, maximum
                    ),
                    after_provider_call=lambda actual, current=model: ledger.add(current, actual),
                )
                result = run_bounded_candidate_selector(
                    bundle,
                    candidates,
                    client=client,
                    config=ranking,
                    evidence_schema=evidence_schema,
                    candidate_schema=candidate_schema,
                    claim_plan_schema=claim_plan_schema,
                    selection_schema=selection_schema,
                )
                provider_calls = [item.protected_dict() for item in client.call_records]
                model_selected_ids = (
                    []
                    if result.record["fallback_used"]
                    else list(result.record["selected_candidate_ids"])
                )
                score = score_selection(model_selected_ids, useful_ids)
                prohibited_selected = sorted(set(model_selected_ids) & prohibited_ids)
                run_dir = output / "runs" / model.key / case_key / f"repeat-{repeat_index}"
                run_dir.mkdir(parents=True, exist_ok=True)
                _write_json(run_dir / "selector-record.json", result.record)
                _write_json(run_dir / "provider-calls-protected.json", {"calls": provider_calls})
                _write_json(run_dir / "claim-plan.json", result.claim_plan)
                (run_dir / "rendered-report.md").write_bytes(result.render.markdown)
                logical_latency = sum(int(item["latency_ms"]) for item in provider_calls)
                logical_cost = sum(float(item["estimated_cost_usd"]) for item in provider_calls)
                record = {
                    "model_key": model.key,
                    "model": model.model,
                    "role": model.role,
                    "case_key": case_key,
                    "classification": case["classification"],
                    "repeat_index": repeat_index,
                    "outcome": result.record["outcome"],
                    "fallback_used": result.record["fallback_used"],
                    "fallback_reason": result.record["fallback_reason"],
                    "semantic_repair_count": result.record["semantic_repair_count"],
                    "selector_attempt_count": result.record["selector_attempt_count"],
                    "model_selected_candidate_ids": model_selected_ids,
                    "final_selected_candidate_ids": list(result.record["selected_candidate_ids"]),
                    "baseline_selected_candidate_ids": list(
                        result.record["baseline_selected_candidate_ids"]
                    ),
                    "useful_candidate_ids": useful_ids,
                    "prohibited_selected_candidate_ids": prohibited_selected,
                    "redundant_selection_count": _redundant_selection_count(
                        model_selected_ids, candidates
                    ),
                    "logical_latency_ms": logical_latency,
                    "logical_cost_usd": logical_cost,
                    "provider_calls": _safe_provider_calls(provider_calls),
                    "claim_plan_sha256": result.record["claim_plan_sha256"],
                    "rendered_markdown_sha256": result.record[
                        "rendered_markdown_sha256"
                    ],
                    "validation": result.record["validation"],
                    **score,
                }
                _write_json(run_dir / "score.json", record)
                records.append(record)

    _write_json(output / AVAILABILITY_FILE, {"models": availability_rows})
    _write_json(output / ROUTES_FILE, {"routes": route_rows})
    _write_json(
        output / ATTEMPT_RECORDS_FILE,
        {"attempts": [asdict(item) for item in pacer.records]},
    )
    _write_json(output / RUNS_FILE, {"version": COMPARISON_VERSION, "records": records})

    model_summaries = [
        summarize_model(
            model,
            [row for row in records if row["model_key"] == model.key],
            expected_runs=model.repeats_per_case * 5,
            route=route_by_key.get(model.key),
            availability=availability_by_key.get(model.key),
        )
        for model in comparison.models
    ]
    decision = apply_predeclared_decision(comparison, model_summaries)
    summary = {
        "version": COMPARISON_VERSION,
        "trusted_main_sha": trusted_main_sha,
        "config_path": PurePosixPath(str(config_path)).as_posix(),
        "config_sha256": content_sha256(asdict(comparison)),
        "prepared_manifest_sha256": content_sha256(manifest),
        "case_count": 5,
        "maximum_logical_runs": comparison.maximum_logical_runs,
        "completed_logical_runs": len(records),
        "maximum_substantive_generations": comparison.maximum_substantive_generations,
        "completed_substantive_generations": ledger.substantive_calls,
        "maximum_route_probes": comparison.maximum_route_probes,
        "completed_route_probes": ledger.route_probes,
        "maximum_total_cost_usd": comparison.maximum_total_cost_usd,
        "observed_total_cost_usd": ledger.total_cost,
        "model_costs_usd": dict(ledger.model_costs),
        "baseline": manifest["baseline"],
        "models": model_summaries,
        "predeclared_decision": decision,
        "automatic_generation": False,
        "publication": False,
        "repository_write": False,
        "provider_call_count_in_pr_ci": 0,
    }
    _write_json(output / SUMMARY_FILE, summary)
    decision_text = _decision_markdown(summary)
    (output / DECISION_INPUT_FILE).write_text(decision_text, encoding="utf-8")
    (output / ACTIONS_SUMMARY).write_text(decision_text, encoding="utf-8")
    _write_reviewer_csv(output / REVIEWER_CSV, records)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--repository-root", default=".")
    prepare.add_argument("--config", default=DEFAULT_CONFIG)
    prepare.add_argument("--output-dir", required=True)
    run = commands.add_parser("run")
    run.add_argument("--repository-root", default=".")
    run.add_argument("--config", default=DEFAULT_CONFIG)
    run.add_argument("--prepared-dir", required=True)
    run.add_argument("--output-dir", required=True)
    run.add_argument("--trusted-main-sha")
    args = parser.parse_args()
    try:
        result = (
            prepare_candidate_selection_comparison(
                repository_root=args.repository_root,
                config_path=args.config,
                output_dir=args.output_dir,
            )
            if args.command == "prepare"
            else execute_candidate_selection_comparison(
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
    except (
        EvaluationConfigurationError,
        EvaluationIntegrityError,
        OSError,
        ValueError,
        TypeError,
    ) as exc:
        print(f"candidate selection model comparison failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
