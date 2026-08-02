"""Strict configuration for the Phase 6 bounded-selector comparison."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

import yaml

from .evaluation import EvaluationConfigurationError

COMPARISON_CONFIG_VERSION = "phase-06-candidate-selection-model-comparison/v1"
_ALLOWED_MODEL_SLUGS = {
    "quality_benchmark": "openai/gpt-5.6-sol",
    "deployment_candidate": "nex-agi/nex-n2-mini",
}
_ALLOWED_PROVIDERS = {
    "quality_benchmark": "OpenAI",
    "deployment_candidate": "Nex AGI",
}
_ALLOWED_OUTCOMES = {
    "quality_benchmark_failed": "remove-model-selector-from-active-roadmap",
    "deployment_candidate_failed": "research-only-no-deployment-selector",
    "both_passed": "retain-bounded-selector-candidate",
    "infrastructure_failure": "inconclusive-infrastructure",
}


@dataclass(frozen=True)
class ComparisonModel:
    key: str
    model: str
    role: str
    deployment_eligible: bool
    allowed_actual_provider: str
    repeats_per_case: int
    availability_checked_at: str
    known_expiration_date: str | None
    maximum_prompt_price_per_million: float
    maximum_completion_price_per_million: float
    maximum_generation_cost_usd: float
    maximum_model_cost_usd: float
    max_output_tokens: int
    send_temperature: bool


@dataclass(frozen=True)
class BaselineReference:
    selected_count: int
    selected_useful_count: int
    gold_useful_count: int
    precision: float
    recall: float
    f1: float


@dataclass(frozen=True)
class QualityGate:
    minimum_accepted_runs: int
    minimum_precision: float
    minimum_recall: float
    minimum_f1: float
    minimum_mean_pairwise_jaccard: float


@dataclass(frozen=True)
class DeploymentGate:
    minimum_accepted_runs: int
    maximum_precision_gap_from_baseline: float
    maximum_recall_gap_from_baseline: float
    minimum_f1: float
    minimum_uplift_retention: float
    minimum_mean_pairwise_jaccard: float
    maximum_p95_latency_seconds: float
    maximum_mean_cost_per_accepted_selection_usd: float


@dataclass(frozen=True)
class CandidateSelectionComparisonPlan:
    version: int
    base_profile: str
    viability_config: str
    gold_manifest: str
    ranking_config: str
    selector_prompt: str
    selection_schema: str
    maximum_logical_runs: int
    maximum_substantive_generations: int
    maximum_route_probes: int
    maximum_semantic_repairs_per_run: int
    maximum_fallbacks_before_decisive_failure: int
    maximum_total_cost_usd: float
    models: tuple[ComparisonModel, ...]
    baseline_reference: BaselineReference
    quality_gate: QualityGate
    deployment_gate: DeploymentGate
    outcomes: Mapping[str, str]

    @property
    def quality_model(self) -> ComparisonModel:
        return next(item for item in self.models if item.role == "quality_benchmark")

    @property
    def deployment_model(self) -> ComparisonModel:
        return next(item for item in self.models if item.role == "deployment_candidate")


def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise EvaluationConfigurationError(f"{path} must be an object")
    return value


def _exact(value: Mapping[str, Any], expected: set[str], path: str) -> None:
    if set(value) != expected:
        missing = sorted(expected - set(value))
        extra = sorted(set(value) - expected)
        raise EvaluationConfigurationError(
            f"{path} must use exact keys; missing={missing!r}, extra={extra!r}"
        )


def _string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EvaluationConfigurationError(f"{path} must be a non-empty string")
    return value.strip()


def _relative(value: Any, path: str) -> str:
    text = _string(value, path)
    candidate = PurePosixPath(text)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise EvaluationConfigurationError(
            f"{path} must be repository-relative without '..'"
        )
    return candidate.as_posix()


def _integer(value: Any, path: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise EvaluationConfigurationError(
            f"{path} must be an integer between {minimum} and {maximum}"
        )
    return value


def _number(value: Any, path: str, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EvaluationConfigurationError(f"{path} must be numeric")
    result = float(value)
    if not minimum <= result <= maximum:
        raise EvaluationConfigurationError(
            f"{path} must be between {minimum} and {maximum}"
        )
    return result


def _date(value: Any, path: str, *, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    text = _string(value, path)
    try:
        date.fromisoformat(text)
    except ValueError as exc:
        raise EvaluationConfigurationError(f"{path} must be YYYY-MM-DD") from exc
    return text


def _bool(value: Any, path: str) -> bool:
    if not isinstance(value, bool):
        raise EvaluationConfigurationError(f"{path} must be a boolean")
    return value


def _f1(precision: float, recall: float) -> float:
    return 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)


def load_candidate_selection_comparison_plan(
    repository_root: str | Path,
    config_path: str | Path = "config/candidate-selection-model-comparison.yml",
) -> CandidateSelectionComparisonPlan:
    root = Path(repository_root).resolve()
    relative = _relative(str(config_path), "config_path")
    raw = _mapping(yaml.safe_load((root / relative).read_text(encoding="utf-8")), relative)
    _exact(
        raw,
        {
            "version",
            "base_profile",
            "viability_config",
            "gold_manifest",
            "ranking_config",
            "selector_prompt",
            "selection_schema",
            "maximum_logical_runs",
            "maximum_substantive_generations",
            "maximum_route_probes",
            "maximum_semantic_repairs_per_run",
            "maximum_fallbacks_before_decisive_failure",
            "maximum_total_cost_usd",
            "models",
            "baseline_reference",
            "decision_gates",
            "outcomes",
        },
        relative,
    )
    if raw.get("version") != 1:
        raise EvaluationConfigurationError("comparison configuration.version must be 1")

    rows = raw.get("models")
    if not isinstance(rows, list) or len(rows) != 2:
        raise EvaluationConfigurationError("models must contain exactly two entries")
    model_keys = {
        "key",
        "model",
        "role",
        "deployment_eligible",
        "allowed_actual_provider",
        "repeats_per_case",
        "availability_checked_at",
        "known_expiration_date",
        "maximum_prompt_price_per_million",
        "maximum_completion_price_per_million",
        "maximum_generation_cost_usd",
        "maximum_model_cost_usd",
        "max_output_tokens",
        "send_temperature",
    }
    models: list[ComparisonModel] = []
    seen_keys: set[str] = set()
    seen_roles: set[str] = set()
    for index, value in enumerate(rows):
        row = _mapping(value, f"models[{index}]")
        _exact(row, model_keys, f"models[{index}]")
        role = _string(row.get("role"), f"models[{index}].role")
        if role not in _ALLOWED_MODEL_SLUGS or role in seen_roles:
            raise EvaluationConfigurationError("model roles must be the two approved unique roles")
        key = _string(row.get("key"), f"models[{index}].key")
        if key in seen_keys:
            raise EvaluationConfigurationError("model keys must be unique")
        model = _string(row.get("model"), f"models[{index}].model")
        if model != _ALLOWED_MODEL_SLUGS[role]:
            raise EvaluationConfigurationError(f"{role} must use {_ALLOWED_MODEL_SLUGS[role]}")
        if model.endswith((":free", ":nitro", ":floor", ":exacto")):
            raise EvaluationConfigurationError("model variants and router aliases are prohibited")
        provider = _string(
            row.get("allowed_actual_provider"),
            f"models[{index}].allowed_actual_provider",
        )
        if provider != _ALLOWED_PROVIDERS[role]:
            raise EvaluationConfigurationError(
                f"{role} must pin actual provider {_ALLOWED_PROVIDERS[role]}"
            )
        deployment = _bool(
            row.get("deployment_eligible"),
            f"models[{index}].deployment_eligible",
        )
        if deployment != (role == "deployment_candidate"):
            raise EvaluationConfigurationError(
                "only the deployment_candidate may be deployment eligible"
            )
        model_row = ComparisonModel(
            key=key,
            model=model,
            role=role,
            deployment_eligible=deployment,
            allowed_actual_provider=provider,
            repeats_per_case=_integer(
                row.get("repeats_per_case"),
                f"models[{index}].repeats_per_case",
                3,
                3,
            ),
            availability_checked_at=_date(
                row.get("availability_checked_at"),
                f"models[{index}].availability_checked_at",
            )
            or "",
            known_expiration_date=_date(
                row.get("known_expiration_date"),
                f"models[{index}].known_expiration_date",
                optional=True,
            ),
            maximum_prompt_price_per_million=_number(
                row.get("maximum_prompt_price_per_million"),
                f"models[{index}].maximum_prompt_price_per_million",
                0.0,
                100.0,
            ),
            maximum_completion_price_per_million=_number(
                row.get("maximum_completion_price_per_million"),
                f"models[{index}].maximum_completion_price_per_million",
                0.0,
                100.0,
            ),
            maximum_generation_cost_usd=_number(
                row.get("maximum_generation_cost_usd"),
                f"models[{index}].maximum_generation_cost_usd",
                0.000001,
                1.0,
            ),
            maximum_model_cost_usd=_number(
                row.get("maximum_model_cost_usd"),
                f"models[{index}].maximum_model_cost_usd",
                0.000001,
                10.0,
            ),
            max_output_tokens=_integer(
                row.get("max_output_tokens"),
                f"models[{index}].max_output_tokens",
                512,
                1024,
            ),
            send_temperature=_bool(
                row.get("send_temperature"),
                f"models[{index}].send_temperature",
            ),
        )
        minimum_model_ceiling = (
            model_row.repeats_per_case
            * 5
            * 2
            * model_row.maximum_generation_cost_usd
        )
        if model_row.maximum_model_cost_usd + 1e-12 < minimum_model_ceiling:
            raise EvaluationConfigurationError(
                f"{key} model ceiling does not cover every initial and repair call"
            )
        expected_output = 1024 if role == "quality_benchmark" else 512
        if model_row.max_output_tokens != expected_output:
            raise EvaluationConfigurationError(
                f"{key} max_output_tokens must be {expected_output}"
            )
        models.append(model_row)
        seen_keys.add(key)
        seen_roles.add(role)
    if seen_roles != set(_ALLOWED_MODEL_SLUGS):
        raise EvaluationConfigurationError("both approved model roles are required")

    maximum_logical_runs = _integer(
        raw.get("maximum_logical_runs"), "maximum_logical_runs", 30, 30
    )
    maximum_generations = _integer(
        raw.get("maximum_substantive_generations"),
        "maximum_substantive_generations",
        60,
        60,
    )
    maximum_route_probes = _integer(
        raw.get("maximum_route_probes"), "maximum_route_probes", 2, 2
    )
    maximum_repairs = _integer(
        raw.get("maximum_semantic_repairs_per_run"),
        "maximum_semantic_repairs_per_run",
        1,
        1,
    )
    maximum_fallbacks = _integer(
        raw.get("maximum_fallbacks_before_decisive_failure"),
        "maximum_fallbacks_before_decisive_failure",
        2,
        2,
    )
    planned_logical = sum(item.repeats_per_case * 5 for item in models)
    if planned_logical != maximum_logical_runs:
        raise EvaluationConfigurationError(
            f"configured repeats imply {planned_logical} logical runs"
        )
    if maximum_generations != maximum_logical_runs * (1 + maximum_repairs):
        raise EvaluationConfigurationError(
            "substantive generation ceiling must cover one initial and one repair per run"
        )
    maximum_total_cost = _number(
        raw.get("maximum_total_cost_usd"), "maximum_total_cost_usd", 5.0, 5.0
    )
    if sum(item.maximum_model_cost_usd for item in models) > maximum_total_cost + 1e-12:
        raise EvaluationConfigurationError("model ceilings exceed the whole-run ceiling")

    baseline_raw = _mapping(raw.get("baseline_reference"), "baseline_reference")
    _exact(
        baseline_raw,
        {
            "selected_count",
            "selected_useful_count",
            "gold_useful_count",
            "precision",
            "recall",
            "f1",
        },
        "baseline_reference",
    )
    baseline = BaselineReference(
        selected_count=_integer(
            baseline_raw.get("selected_count"), "baseline_reference.selected_count", 35, 35
        ),
        selected_useful_count=_integer(
            baseline_raw.get("selected_useful_count"),
            "baseline_reference.selected_useful_count",
            26,
            26,
        ),
        gold_useful_count=_integer(
            baseline_raw.get("gold_useful_count"),
            "baseline_reference.gold_useful_count",
            38,
            38,
        ),
        precision=_number(
            baseline_raw.get("precision"), "baseline_reference.precision", 0.0, 1.0
        ),
        recall=_number(
            baseline_raw.get("recall"), "baseline_reference.recall", 0.0, 1.0
        ),
        f1=_number(baseline_raw.get("f1"), "baseline_reference.f1", 0.0, 1.0),
    )
    derived_precision = baseline.selected_useful_count / baseline.selected_count
    derived_recall = baseline.selected_useful_count / baseline.gold_useful_count
    derived_f1 = _f1(derived_precision, derived_recall)
    for name, actual, expected in (
        ("precision", baseline.precision, derived_precision),
        ("recall", baseline.recall, derived_recall),
        ("f1", baseline.f1, derived_f1),
    ):
        if abs(actual - expected) > 1e-12:
            raise EvaluationConfigurationError(
                f"baseline_reference.{name} does not match the declared counts"
            )

    gates_raw = _mapping(raw.get("decision_gates"), "decision_gates")
    _exact(gates_raw, {"quality_benchmark", "deployment_candidate"}, "decision_gates")
    quality_raw = _mapping(gates_raw.get("quality_benchmark"), "decision_gates.quality_benchmark")
    _exact(
        quality_raw,
        {
            "minimum_accepted_runs",
            "minimum_precision",
            "minimum_recall",
            "minimum_f1",
            "minimum_mean_pairwise_jaccard",
        },
        "decision_gates.quality_benchmark",
    )
    quality_gate = QualityGate(
        minimum_accepted_runs=_integer(
            quality_raw.get("minimum_accepted_runs"),
            "quality_benchmark.minimum_accepted_runs",
            14,
            14,
        ),
        minimum_precision=_number(
            quality_raw.get("minimum_precision"),
            "quality_benchmark.minimum_precision",
            baseline.precision,
            1.0,
        ),
        minimum_recall=_number(
            quality_raw.get("minimum_recall"),
            "quality_benchmark.minimum_recall",
            baseline.recall,
            1.0,
        ),
        minimum_f1=_number(
            quality_raw.get("minimum_f1"),
            "quality_benchmark.minimum_f1",
            baseline.f1,
            1.0,
        ),
        minimum_mean_pairwise_jaccard=_number(
            quality_raw.get("minimum_mean_pairwise_jaccard"),
            "quality_benchmark.minimum_mean_pairwise_jaccard",
            0.8,
            1.0,
        ),
    )
    deployment_raw = _mapping(
        gates_raw.get("deployment_candidate"), "decision_gates.deployment_candidate"
    )
    _exact(
        deployment_raw,
        {
            "minimum_accepted_runs",
            "maximum_precision_gap_from_baseline",
            "maximum_recall_gap_from_baseline",
            "minimum_f1",
            "minimum_uplift_retention",
            "minimum_mean_pairwise_jaccard",
            "maximum_p95_latency_seconds",
            "maximum_mean_cost_per_accepted_selection_usd",
        },
        "decision_gates.deployment_candidate",
    )
    deployment_gate = DeploymentGate(
        minimum_accepted_runs=_integer(
            deployment_raw.get("minimum_accepted_runs"),
            "deployment_candidate.minimum_accepted_runs",
            14,
            14,
        ),
        maximum_precision_gap_from_baseline=_number(
            deployment_raw.get("maximum_precision_gap_from_baseline"),
            "deployment_candidate.maximum_precision_gap_from_baseline",
            0.02,
            0.02,
        ),
        maximum_recall_gap_from_baseline=_number(
            deployment_raw.get("maximum_recall_gap_from_baseline"),
            "deployment_candidate.maximum_recall_gap_from_baseline",
            0.02,
            0.02,
        ),
        minimum_f1=_number(
            deployment_raw.get("minimum_f1"),
            "deployment_candidate.minimum_f1",
            baseline.f1,
            1.0,
        ),
        minimum_uplift_retention=_number(
            deployment_raw.get("minimum_uplift_retention"),
            "deployment_candidate.minimum_uplift_retention",
            0.8,
            1.0,
        ),
        minimum_mean_pairwise_jaccard=_number(
            deployment_raw.get("minimum_mean_pairwise_jaccard"),
            "deployment_candidate.minimum_mean_pairwise_jaccard",
            0.8,
            1.0,
        ),
        maximum_p95_latency_seconds=_number(
            deployment_raw.get("maximum_p95_latency_seconds"),
            "deployment_candidate.maximum_p95_latency_seconds",
            1.0,
            30.0,
        ),
        maximum_mean_cost_per_accepted_selection_usd=_number(
            deployment_raw.get("maximum_mean_cost_per_accepted_selection_usd"),
            "deployment_candidate.maximum_mean_cost_per_accepted_selection_usd",
            0.000001,
            0.02,
        ),
    )

    outcomes = dict(_mapping(raw.get("outcomes"), "outcomes"))
    if outcomes != _ALLOWED_OUTCOMES:
        raise EvaluationConfigurationError("outcomes must match the four predeclared values")

    return CandidateSelectionComparisonPlan(
        version=1,
        base_profile=_relative(raw.get("base_profile"), "base_profile"),
        viability_config=_relative(raw.get("viability_config"), "viability_config"),
        gold_manifest=_relative(raw.get("gold_manifest"), "gold_manifest"),
        ranking_config=_relative(raw.get("ranking_config"), "ranking_config"),
        selector_prompt=_relative(raw.get("selector_prompt"), "selector_prompt"),
        selection_schema=_relative(raw.get("selection_schema"), "selection_schema"),
        maximum_logical_runs=maximum_logical_runs,
        maximum_substantive_generations=maximum_generations,
        maximum_route_probes=maximum_route_probes,
        maximum_semantic_repairs_per_run=maximum_repairs,
        maximum_fallbacks_before_decisive_failure=maximum_fallbacks,
        maximum_total_cost_usd=maximum_total_cost,
        models=tuple(models),
        baseline_reference=baseline,
        quality_gate=quality_gate,
        deployment_gate=deployment_gate,
        outcomes=outcomes,
    )
