"""Strict, immutable configuration for the Phase 9 GPT-OSS quality comparison."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

import yaml

from .evaluation import EvaluationConfigurationError

PHASE9_CONFIG_VERSION = "phase-09-gpt-oss-quality-comparison/v1"
DEFAULT_CONFIG = "config/gpt-oss-quality-comparison.yml"
FROZEN_CASE_ORDER = (
    "historical-degraded-sparse",
    "historical-normal-crosschecked",
    "historical-material-move",
    "adversarial-prompt-injection",
    "adversarial-source-disagreement",
)
FROZEN_REQUIRED_EXPECTATIONS = {
    "historical-material-move": (
        "sol-24h-direction",
        "eth-7d-direction",
        "btc-eth-1h-opposite",
        "eth-sol-24h-comparison",
    ),
    "adversarial-source-disagreement": (
        "btc-price",
        "coinbase-mutated-price",
        "btc-eth-price-comparison",
        "coinbase-status",
        "snapshot-status",
    ),
}
FROZEN_OUTCOMES = {
    "infrastructure_failure": "inconclusive-infrastructure",
    "model_failure": "no-stable-material-uplift",
    "promoted": "eligible-for-operational-decision",
}


@dataclass(frozen=True)
class BaselineReference:
    selected_count: int
    selected_useful_count: int
    gold_useful_count: int
    precision: float
    recall: float
    f1: float


@dataclass(frozen=True)
class PromotionGates:
    minimum_precision: float
    minimum_recall: float
    minimum_f1: float
    minimum_corpus_median_jaccard: float
    minimum_case_median_jaccard: float
    maximum_case_f1_regression: float
    stable_majority_frequency: int
    minimum_cases_with_stable_useful_addition: int


@dataclass(frozen=True)
class Phase9Plan:
    version: int
    base_comparison_config: str
    gold_manifest: str
    ranking_config: str
    selector_prompt: str
    selection_schema: str
    model: str
    provider_slug: str
    max_output_tokens: int
    reasoning_effort: str
    maximum_stage_a_calls: int
    maximum_stage_b_calls: int
    maximum_paid_calls: int
    maximum_semantic_repairs: int
    maximum_network_retries: int
    maximum_route_probes: int
    maximum_call_cost_usd: float
    maximum_total_cost_usd: float
    maximum_prompt_price_per_million: float
    maximum_completion_price_per_million: float
    required_expectations: Mapping[str, tuple[str, ...]]
    baseline_reference: BaselineReference
    promotion_gates: PromotionGates
    outcomes: Mapping[str, str]


EXPECTED_ROOT_KEYS = {
    "version",
    "base_comparison_config",
    "gold_manifest",
    "ranking_config",
    "selector_prompt",
    "selection_schema",
    "model",
    "provider_slug",
    "max_output_tokens",
    "reasoning_effort",
    "maximum_stage_a_calls",
    "maximum_stage_b_calls",
    "maximum_paid_calls",
    "maximum_semantic_repairs",
    "maximum_network_retries",
    "maximum_route_probes",
    "maximum_call_cost_usd",
    "maximum_total_cost_usd",
    "maximum_prompt_price_per_million",
    "maximum_completion_price_per_million",
    "required_expectations",
    "baseline_reference",
    "promotion_gates",
    "outcomes",
}


def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise EvaluationConfigurationError(f"{path} must be an object")
    return value


def _exact(value: Mapping[str, Any], expected: set[str], path: str) -> None:
    if set(value) != expected:
        raise EvaluationConfigurationError(
            f"{path} must use exact keys; missing={sorted(expected-set(value))!r}, "
            f"extra={sorted(set(value)-expected)!r}"
        )


def _string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EvaluationConfigurationError(f"{path} must be a non-empty string")
    return value.strip()


def _relative(value: Any, path: str) -> str:
    text = _string(value, path)
    candidate = PurePosixPath(text)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise EvaluationConfigurationError(f"{path} must be repository-relative")
    return candidate.as_posix()


def _integer(value: Any, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise EvaluationConfigurationError(f"{path} must be an integer")
    return value


def _number(value: Any, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EvaluationConfigurationError(f"{path} must be numeric")
    return float(value)


def _baseline(raw: Mapping[str, Any]) -> BaselineReference:
    _exact(raw, {"selected_count", "selected_useful_count", "gold_useful_count", "precision", "recall", "f1"}, "baseline_reference")
    return BaselineReference(
        selected_count=_integer(raw["selected_count"], "baseline_reference.selected_count"),
        selected_useful_count=_integer(raw["selected_useful_count"], "baseline_reference.selected_useful_count"),
        gold_useful_count=_integer(raw["gold_useful_count"], "baseline_reference.gold_useful_count"),
        precision=_number(raw["precision"], "baseline_reference.precision"),
        recall=_number(raw["recall"], "baseline_reference.recall"),
        f1=_number(raw["f1"], "baseline_reference.f1"),
    )


def _gates(raw: Mapping[str, Any]) -> PromotionGates:
    keys = {
        "minimum_precision", "minimum_recall", "minimum_f1",
        "minimum_corpus_median_jaccard", "minimum_case_median_jaccard",
        "maximum_case_f1_regression", "stable_majority_frequency",
        "minimum_cases_with_stable_useful_addition",
    }
    _exact(raw, keys, "promotion_gates")
    return PromotionGates(
        minimum_precision=_number(raw["minimum_precision"], "promotion_gates.minimum_precision"),
        minimum_recall=_number(raw["minimum_recall"], "promotion_gates.minimum_recall"),
        minimum_f1=_number(raw["minimum_f1"], "promotion_gates.minimum_f1"),
        minimum_corpus_median_jaccard=_number(raw["minimum_corpus_median_jaccard"], "promotion_gates.minimum_corpus_median_jaccard"),
        minimum_case_median_jaccard=_number(raw["minimum_case_median_jaccard"], "promotion_gates.minimum_case_median_jaccard"),
        maximum_case_f1_regression=_number(raw["maximum_case_f1_regression"], "promotion_gates.maximum_case_f1_regression"),
        stable_majority_frequency=_integer(raw["stable_majority_frequency"], "promotion_gates.stable_majority_frequency"),
        minimum_cases_with_stable_useful_addition=_integer(raw["minimum_cases_with_stable_useful_addition"], "promotion_gates.minimum_cases_with_stable_useful_addition"),
    )


def load_phase9_plan(repository_root: str | Path, config_path: str | Path = DEFAULT_CONFIG) -> Phase9Plan:
    root = Path(repository_root).resolve()
    relative = _relative(str(config_path), "config_path")
    raw = _mapping(yaml.safe_load((root / relative).read_text(encoding="utf-8")), relative)
    _exact(raw, EXPECTED_ROOT_KEYS, relative)
    required_raw = _mapping(raw["required_expectations"], "required_expectations")
    required: dict[str, tuple[str, ...]] = {}
    for case_key, values in required_raw.items():
        if not isinstance(values, list) or not all(isinstance(item, str) and item for item in values):
            raise EvaluationConfigurationError(f"required_expectations.{case_key} must be a string list")
        required[str(case_key)] = tuple(str(item) for item in values)
    outcomes = {str(key): str(value) for key, value in _mapping(raw["outcomes"], "outcomes").items()}
    plan = Phase9Plan(
        version=_integer(raw["version"], "version"),
        base_comparison_config=_relative(raw["base_comparison_config"], "base_comparison_config"),
        gold_manifest=_relative(raw["gold_manifest"], "gold_manifest"),
        ranking_config=_relative(raw["ranking_config"], "ranking_config"),
        selector_prompt=_relative(raw["selector_prompt"], "selector_prompt"),
        selection_schema=_relative(raw["selection_schema"], "selection_schema"),
        model=_string(raw["model"], "model"),
        provider_slug=_string(raw["provider_slug"], "provider_slug"),
        max_output_tokens=_integer(raw["max_output_tokens"], "max_output_tokens"),
        reasoning_effort=_string(raw["reasoning_effort"], "reasoning_effort"),
        maximum_stage_a_calls=_integer(raw["maximum_stage_a_calls"], "maximum_stage_a_calls"),
        maximum_stage_b_calls=_integer(raw["maximum_stage_b_calls"], "maximum_stage_b_calls"),
        maximum_paid_calls=_integer(raw["maximum_paid_calls"], "maximum_paid_calls"),
        maximum_semantic_repairs=_integer(raw["maximum_semantic_repairs"], "maximum_semantic_repairs"),
        maximum_network_retries=_integer(raw["maximum_network_retries"], "maximum_network_retries"),
        maximum_route_probes=_integer(raw["maximum_route_probes"], "maximum_route_probes"),
        maximum_call_cost_usd=_number(raw["maximum_call_cost_usd"], "maximum_call_cost_usd"),
        maximum_total_cost_usd=_number(raw["maximum_total_cost_usd"], "maximum_total_cost_usd"),
        maximum_prompt_price_per_million=_number(raw["maximum_prompt_price_per_million"], "maximum_prompt_price_per_million"),
        maximum_completion_price_per_million=_number(raw["maximum_completion_price_per_million"], "maximum_completion_price_per_million"),
        required_expectations=required,
        baseline_reference=_baseline(_mapping(raw["baseline_reference"], "baseline_reference")),
        promotion_gates=_gates(_mapping(raw["promotion_gates"], "promotion_gates")),
        outcomes=outcomes,
    )
    expected_baseline = BaselineReference(35, 26, 38, 0.7428571428571429, 0.6842105263157895, 0.7123287671232876)
    if plan.version != 1 or plan.model != "openai/gpt-oss-120b" or plan.provider_slug != "deepinfra":
        raise EvaluationConfigurationError("Phase 9 exact model/provider contract changed")
    if plan.max_output_tokens != 2048 or plan.reasoning_effort != "minimal":
        raise EvaluationConfigurationError("Phase 9 output/reasoning contract changed")
    if (plan.maximum_stage_a_calls, plan.maximum_stage_b_calls, plan.maximum_paid_calls) != (5, 10, 15):
        raise EvaluationConfigurationError("Phase 9 staged call ceilings changed")
    if any((plan.maximum_semantic_repairs, plan.maximum_network_retries, plan.maximum_route_probes)):
        raise EvaluationConfigurationError("Phase 9 repair/retry/probe ceilings must remain zero")
    if abs(plan.maximum_call_cost_usd - 0.005) > 1e-12 or abs(plan.maximum_total_cost_usd - 0.075) > 1e-12:
        raise EvaluationConfigurationError("Phase 9 cost ceilings changed")
    if abs(plan.maximum_prompt_price_per_million - 0.10) > 1e-12 or abs(plan.maximum_completion_price_per_million - 0.50) > 1e-12:
        raise EvaluationConfigurationError("Phase 9 catalogue price ceilings changed")
    if required != FROZEN_REQUIRED_EXPECTATIONS:
        raise EvaluationConfigurationError("Phase 9 required expectation subsets changed")
    if outcomes != FROZEN_OUTCOMES:
        raise EvaluationConfigurationError("Phase 9 outcomes changed")
    if plan.baseline_reference != expected_baseline:
        raise EvaluationConfigurationError("Phase 9 deterministic baseline changed")
    gates = plan.promotion_gates
    if (
        abs(gates.minimum_precision - 0.79285714) > 1e-12
        or abs(gates.minimum_recall - 0.68421053) > 1e-12
        or abs(gates.minimum_f1 - 0.76232877) > 1e-12
        or abs(gates.minimum_corpus_median_jaccard - 0.80) > 1e-12
        or abs(gates.minimum_case_median_jaccard - 0.67) > 1e-12
        or abs(gates.maximum_case_f1_regression - 0.05) > 1e-12
        or gates.stable_majority_frequency != 2
        or gates.minimum_cases_with_stable_useful_addition != 2
    ):
        raise EvaluationConfigurationError("Phase 9 promotion gates changed")
    return plan
