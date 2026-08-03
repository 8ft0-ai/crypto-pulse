"""Strict configuration for the Phase 7 low-cost selector compatibility screen."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

import yaml

from .evaluation import EvaluationConfigurationError

STAGE0_CONFIG_VERSION = "phase-07-low-cost-candidate-selector-stage-0/v1"
DEFAULT_STAGE0_CONFIG = "config/low-cost-candidate-selector-stage-0.yml"

_EXPECTED_MODELS = {
    "deepseek-v4-flash-0731": (
        "deepseek/deepseek-v4-flash-0731",
        "DeepSeek",
    ),
    "gpt-oss-120b": ("openai/gpt-oss-120b", "DeepInfra"),
    "mercury-2": ("inception/mercury-2", "Inception"),
}


@dataclass(frozen=True)
class Stage0Model:
    key: str
    model: str
    allowed_actual_provider: str
    availability_checked_at: str
    known_expiration_date: str | None
    maximum_prompt_price_per_million: float
    maximum_completion_price_per_million: float
    maximum_route_cost_usd: float
    maximum_generation_cost_usd: float
    maximum_model_cost_usd: float
    max_output_tokens: int
    send_temperature: bool


@dataclass(frozen=True)
class Stage0Plan:
    version: int
    phase6_comparison_config: str
    viability_config: str
    case_key: str
    expected_candidate_count: int
    selector_prompt: str
    selection_schema: str
    ranking_config: str
    maximum_route_probes: int
    maximum_selector_generations: int
    maximum_paid_calls: int
    maximum_semantic_repairs: int
    maximum_network_retries: int
    maximum_total_cost_usd: float
    models: tuple[Stage0Model, ...]


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


def _bool(value: Any, path: str) -> bool:
    if not isinstance(value, bool):
        raise EvaluationConfigurationError(f"{path} must be a boolean")
    return value


def _date(value: Any, path: str, *, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    text = _string(value, path)
    try:
        date.fromisoformat(text)
    except ValueError as exc:
        raise EvaluationConfigurationError(f"{path} must be YYYY-MM-DD") from exc
    return text


def load_stage0_plan(
    repository_root: str | Path,
    config_path: str | Path = DEFAULT_STAGE0_CONFIG,
) -> Stage0Plan:
    root = Path(repository_root).resolve()
    relative = _relative(str(config_path), "config_path")
    raw = _mapping(yaml.safe_load((root / relative).read_text(encoding="utf-8")), relative)
    _exact(
        raw,
        {
            "version",
            "phase6_comparison_config",
            "viability_config",
            "case_key",
            "expected_candidate_count",
            "selector_prompt",
            "selection_schema",
            "ranking_config",
            "maximum_route_probes",
            "maximum_selector_generations",
            "maximum_paid_calls",
            "maximum_semantic_repairs",
            "maximum_network_retries",
            "maximum_total_cost_usd",
            "models",
        },
        relative,
    )
    if raw.get("version") != 1:
        raise EvaluationConfigurationError("Stage 0 configuration.version must be 1")
    if raw.get("case_key") != "historical-degraded-sparse":
        raise EvaluationConfigurationError(
            "Stage 0 must use historical-degraded-sparse"
        )

    rows = raw.get("models")
    if not isinstance(rows, list) or len(rows) != 3:
        raise EvaluationConfigurationError("Stage 0 models must contain exactly three entries")
    model_keys = {
        "key",
        "model",
        "allowed_actual_provider",
        "availability_checked_at",
        "known_expiration_date",
        "maximum_prompt_price_per_million",
        "maximum_completion_price_per_million",
        "maximum_route_cost_usd",
        "maximum_generation_cost_usd",
        "maximum_model_cost_usd",
        "max_output_tokens",
        "send_temperature",
    }
    models: list[Stage0Model] = []
    seen: set[str] = set()
    for index, value in enumerate(rows):
        row = _mapping(value, f"models[{index}]")
        _exact(row, model_keys, f"models[{index}]")
        key = _string(row.get("key"), f"models[{index}].key")
        if key not in _EXPECTED_MODELS or key in seen:
            raise EvaluationConfigurationError(
                "Stage 0 model keys must be the three approved unique keys"
            )
        expected_model, expected_provider = _EXPECTED_MODELS[key]
        model = _string(row.get("model"), f"models[{index}].model")
        provider = _string(
            row.get("allowed_actual_provider"),
            f"models[{index}].allowed_actual_provider",
        )
        if model != expected_model:
            raise EvaluationConfigurationError(f"{key} must use {expected_model}")
        if provider != expected_provider:
            raise EvaluationConfigurationError(
                f"{key} must pin actual provider {expected_provider}"
            )
        if model.startswith("openrouter/") or model.endswith(
            (":free", ":nitro", ":floor", ":exacto")
        ):
            raise EvaluationConfigurationError("model aliases and variants are prohibited")
        route_cap = _number(
            row.get("maximum_route_cost_usd"),
            f"models[{index}].maximum_route_cost_usd",
            0.000001,
            0.02,
        )
        generation_cap = _number(
            row.get("maximum_generation_cost_usd"),
            f"models[{index}].maximum_generation_cost_usd",
            0.000001,
            0.04,
        )
        model_cap = _number(
            row.get("maximum_model_cost_usd"),
            f"models[{index}].maximum_model_cost_usd",
            0.000001,
            0.04,
        )
        if abs(route_cap + generation_cap - model_cap) > 1e-12:
            raise EvaluationConfigurationError(
                f"{key} model ceiling must equal route plus selector ceilings"
            )
        models.append(
            Stage0Model(
                key=key,
                model=model,
                allowed_actual_provider=provider,
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
                    0.000001,
                    1.0,
                ),
                maximum_completion_price_per_million=_number(
                    row.get("maximum_completion_price_per_million"),
                    f"models[{index}].maximum_completion_price_per_million",
                    0.000001,
                    2.0,
                ),
                maximum_route_cost_usd=route_cap,
                maximum_generation_cost_usd=generation_cap,
                maximum_model_cost_usd=model_cap,
                max_output_tokens=_integer(
                    row.get("max_output_tokens"),
                    f"models[{index}].max_output_tokens",
                    1024,
                    1024,
                ),
                send_temperature=_bool(
                    row.get("send_temperature"),
                    f"models[{index}].send_temperature",
                ),
            )
        )
        seen.add(key)
    if seen != set(_EXPECTED_MODELS):
        raise EvaluationConfigurationError("all three approved Stage 0 models are required")

    route_limit = _integer(
        raw.get("maximum_route_probes"), "maximum_route_probes", 3, 3
    )
    generation_limit = _integer(
        raw.get("maximum_selector_generations"),
        "maximum_selector_generations",
        3,
        3,
    )
    paid_limit = _integer(raw.get("maximum_paid_calls"), "maximum_paid_calls", 6, 6)
    repairs = _integer(raw.get("maximum_semantic_repairs"), "maximum_semantic_repairs", 0, 0)
    retries = _integer(raw.get("maximum_network_retries"), "maximum_network_retries", 0, 0)
    if paid_limit != route_limit + generation_limit:
        raise EvaluationConfigurationError(
            "maximum_paid_calls must equal route probes plus selector generations"
        )
    total_cap = _number(
        raw.get("maximum_total_cost_usd"),
        "maximum_total_cost_usd",
        0.06,
        0.06,
    )
    if abs(sum(item.maximum_model_cost_usd for item in models) - total_cap) > 1e-12:
        raise EvaluationConfigurationError(
            "model ceilings must exactly equal the whole Stage 0 ceiling"
        )

    return Stage0Plan(
        version=1,
        phase6_comparison_config=_relative(
            raw.get("phase6_comparison_config"), "phase6_comparison_config"
        ),
        viability_config=_relative(raw.get("viability_config"), "viability_config"),
        case_key="historical-degraded-sparse",
        expected_candidate_count=_integer(
            raw.get("expected_candidate_count"),
            "expected_candidate_count",
            201,
            201,
        ),
        selector_prompt=_relative(raw.get("selector_prompt"), "selector_prompt"),
        selection_schema=_relative(raw.get("selection_schema"), "selection_schema"),
        ranking_config=_relative(raw.get("ranking_config"), "ranking_config"),
        maximum_route_probes=route_limit,
        maximum_selector_generations=generation_limit,
        maximum_paid_calls=paid_limit,
        maximum_semantic_repairs=repairs,
        maximum_network_retries=retries,
        maximum_total_cost_usd=total_cap,
        models=tuple(models),
    )
