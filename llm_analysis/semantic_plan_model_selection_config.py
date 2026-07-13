"""Configuration for bounded semantic claim-plan model selection."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

import yaml

from .evaluation import EvaluationConfigurationError


@dataclass(frozen=True)
class Candidate:
    key: str
    model: str
    role: str
    deployment_eligible: bool
    repeats_per_case: int
    availability_checked_at: str
    known_expiration_date: str | None
    maximum_prompt_price_per_million: float
    maximum_completion_price_per_million: float
    maximum_generation_cost_usd: float
    maximum_model_cost_usd: float
    send_temperature: bool


@dataclass(frozen=True)
class ExcludedModel:
    model: str
    reason: str
    generation_allowed: bool


@dataclass(frozen=True)
class SelectionPlan:
    version: int
    base_profile: str
    viability_config: str
    expectations_path: str
    maximum_substantive_generations: int
    maximum_total_cost_usd: float
    candidates: tuple[Candidate, ...]
    excluded_models: tuple[ExcludedModel, ...]


@dataclass(frozen=True)
class CaseExpectation:
    case_key: str
    required_evidence_ids: tuple[str, ...]
    forbidden_evidence_ids: tuple[str, ...]
    forbidden_data_quality_evidence_ids: tuple[str, ...]
    required_source_disagreement_ids: tuple[str, ...]
    discouraged_evidence_ids: tuple[str, ...]
    maximum_claims: int


def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise EvaluationConfigurationError(f"{path} must be an object")
    return value


def _string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EvaluationConfigurationError(f"{path} must be a non-empty string")
    return value.strip()


def _relative(value: Any, path: str) -> str:
    text = _string(value, path)
    candidate = PurePosixPath(text)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise EvaluationConfigurationError(f"{path} must be repository-relative without '..'")
    return candidate.as_posix()


def _integer(value: Any, path: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise EvaluationConfigurationError(f"{path} must be an integer between {minimum} and {maximum}")
    return value


def _number(value: Any, path: str, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EvaluationConfigurationError(f"{path} must be numeric")
    result = float(value)
    if not minimum <= result <= maximum:
        raise EvaluationConfigurationError(f"{path} must be between {minimum} and {maximum}")
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


def _strings(value: Any, path: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise EvaluationConfigurationError(f"{path} must be a list of non-empty strings")
    result = tuple(item.strip() for item in value)
    if len(result) != len(set(result)):
        raise EvaluationConfigurationError(f"{path} must not contain duplicates")
    return result


def load_selection_plan(repository_root: str | Path, config_path: str | Path) -> SelectionPlan:
    root = Path(repository_root).resolve()
    relative = _relative(str(config_path), "config_path")
    config = _mapping(yaml.safe_load((root / relative).read_text(encoding="utf-8")), relative)
    expected = {
        "version", "base_profile", "viability_config", "expectations_path",
        "maximum_substantive_generations", "maximum_total_cost_usd",
        "candidates", "excluded_models",
    }
    if set(config) != expected or config.get("version") != 1:
        raise EvaluationConfigurationError("model-selection config must use version 1 and exact supported keys")

    rows = config.get("candidates")
    if not isinstance(rows, list) or len(rows) != 3:
        raise EvaluationConfigurationError("candidates must contain exactly three models")
    candidates: list[Candidate] = []
    seen_keys: set[str] = set()
    seen_models: set[str] = set()
    seen_roles: set[str] = set()
    allowed_roles = {"quality_benchmark", "primary_candidate", "consistency_candidate"}
    candidate_keys = {
        "key", "model", "role", "deployment_eligible", "repeats_per_case",
        "availability_checked_at", "known_expiration_date",
        "maximum_prompt_price_per_million", "maximum_completion_price_per_million",
        "maximum_generation_cost_usd", "maximum_model_cost_usd", "send_temperature",
    }
    for index, raw in enumerate(rows):
        row = _mapping(raw, f"candidates[{index}]")
        if set(row) != candidate_keys:
            raise EvaluationConfigurationError(f"candidates[{index}] must use exact supported keys")
        key = _string(row.get("key"), f"candidates[{index}].key")
        model = _string(row.get("model"), f"candidates[{index}].model")
        role = _string(row.get("role"), f"candidates[{index}].role")
        if key in seen_keys or model in seen_models or role in seen_roles:
            raise EvaluationConfigurationError("candidate keys, model slugs and roles must be unique")
        if role not in allowed_roles:
            raise EvaluationConfigurationError("unsupported candidate role")
        deployment = row.get("deployment_eligible")
        send_temperature = row.get("send_temperature")
        if not isinstance(deployment, bool) or not isinstance(send_temperature, bool):
            raise EvaluationConfigurationError("candidate booleans are invalid")
        if deployment == (role == "quality_benchmark"):
            raise EvaluationConfigurationError("only affordable candidates may be deployment eligible")
        candidate = Candidate(
            key=key,
            model=model,
            role=role,
            deployment_eligible=deployment,
            repeats_per_case=_integer(row.get("repeats_per_case"), "repeats_per_case", 1, 5),
            availability_checked_at=_date(row.get("availability_checked_at"), "availability_checked_at") or "",
            known_expiration_date=_date(row.get("known_expiration_date"), "known_expiration_date", optional=True),
            maximum_prompt_price_per_million=_number(row.get("maximum_prompt_price_per_million"), "maximum_prompt_price_per_million", 0, 100),
            maximum_completion_price_per_million=_number(row.get("maximum_completion_price_per_million"), "maximum_completion_price_per_million", 0, 100),
            maximum_generation_cost_usd=_number(row.get("maximum_generation_cost_usd"), "maximum_generation_cost_usd", 0.000001, 1),
            maximum_model_cost_usd=_number(row.get("maximum_model_cost_usd"), "maximum_model_cost_usd", 0.000001, 5),
            send_temperature=send_temperature,
        )
        minimum_model_ceiling = candidate.maximum_generation_cost_usd * (1 + candidate.repeats_per_case * 5)
        if candidate.maximum_model_cost_usd + 1e-12 < minimum_model_ceiling:
            raise EvaluationConfigurationError(f"{key} model ceiling does not cover every bounded call")
        candidates.append(candidate)
        seen_keys.add(key)
        seen_models.add(model)
        seen_roles.add(role)
    if sum(item.role == "quality_benchmark" for item in candidates) != 1:
        raise EvaluationConfigurationError("exactly one quality benchmark is required")

    excluded_rows = config.get("excluded_models")
    if not isinstance(excluded_rows, list) or not excluded_rows:
        raise EvaluationConfigurationError("excluded_models must contain at least one model")
    excluded: list[ExcludedModel] = []
    for index, raw in enumerate(excluded_rows):
        row = _mapping(raw, f"excluded_models[{index}]")
        if set(row) != {"model", "reason", "generation_allowed"} or row.get("generation_allowed") is not False:
            raise EvaluationConfigurationError("excluded models must use the exact non-generation contract")
        excluded.append(ExcludedModel(_string(row.get("model"), "model"), _string(row.get("reason"), "reason"), False))

    maximum_generations = _integer(config.get("maximum_substantive_generations"), "maximum_substantive_generations", 1, 50)
    planned_generations = sum(item.repeats_per_case * 5 for item in candidates)
    if planned_generations != maximum_generations:
        raise EvaluationConfigurationError(f"configured repeats imply {planned_generations} generations, expected {maximum_generations}")
    maximum_total_cost = _number(config.get("maximum_total_cost_usd"), "maximum_total_cost_usd", 0.01, 2.50)
    if sum(item.maximum_model_cost_usd for item in candidates) > maximum_total_cost + 1e-12:
        raise EvaluationConfigurationError("model ceilings exceed the whole evaluation cost ceiling")

    return SelectionPlan(
        1,
        _relative(config.get("base_profile"), "base_profile"),
        _relative(config.get("viability_config"), "viability_config"),
        _relative(config.get("expectations_path"), "expectations_path"),
        maximum_generations,
        maximum_total_cost,
        tuple(candidates),
        tuple(excluded),
    )


def load_expectations(repository_root: str | Path, path: str | Path) -> dict[str, CaseExpectation]:
    root = Path(repository_root).resolve()
    relative = _relative(str(path), "expectations_path")
    config = _mapping(yaml.safe_load((root / relative).read_text(encoding="utf-8")), relative)
    cases = config.get("cases")
    if set(config) != {"version", "cases"} or config.get("version") != 1 or not isinstance(cases, Mapping):
        raise EvaluationConfigurationError("expectations must use version 1 and a cases object")
    allowed = {
        "required_evidence_ids", "forbidden_evidence_ids",
        "forbidden_data_quality_evidence_ids", "required_source_disagreement_ids",
        "discouraged_evidence_ids", "maximum_claims",
    }
    result: dict[str, CaseExpectation] = {}
    for case_key, raw in cases.items():
        key = _string(case_key, "case key")
        row = _mapping(raw, f"cases.{key}")
        if set(row) != allowed:
            raise EvaluationConfigurationError(f"cases.{key} must use exact supported keys")
        disagreement = _strings(row.get("required_source_disagreement_ids"), "required_source_disagreement_ids")
        if disagreement and len(disagreement) != 2:
            raise EvaluationConfigurationError("required_source_disagreement_ids must contain exactly two IDs")
        result[key] = CaseExpectation(
            key,
            _strings(row.get("required_evidence_ids"), "required_evidence_ids"),
            _strings(row.get("forbidden_evidence_ids"), "forbidden_evidence_ids"),
            _strings(row.get("forbidden_data_quality_evidence_ids"), "forbidden_data_quality_evidence_ids"),
            disagreement,
            _strings(row.get("discouraged_evidence_ids"), "discouraged_evidence_ids"),
            _integer(row.get("maximum_claims"), "maximum_claims", 1, 40),
        )
    return result
