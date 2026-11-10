"""Bounded paid-model benchmark for governed Phase 5 analysis."""
from __future__ import annotations

import argparse
import json
import os
import urllib.request
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Mapping

import yaml

from .contracts import canonical_json_bytes
from .evaluation import (
    ACTIONS_SUMMARY,
    AVAILABILITY_FILE,
    DECISION_MARKDOWN,
    PREPARED_MANIFEST,
    REVIEWER_WORKSHEET,
    SUMMARY_JSON,
    CatalogueLoader,
    EvaluationConfigurationError,
    EvaluationIntegrityError,
    EvaluationModel,
    ModelAvailability,
    PreparedCase,
    RunRecord,
    _aggregate,
    _catalogue,
    _decision_text,
    _read_json,
    _write_json,
    load_evaluation_plan,
    prepare_evaluation,
)
from .evaluation_execution import _run_one
from .evidence_bundle import EvidenceBundleError
from .evaluation_viability import (
    ATTEMPT_RECORDS_FILE,
    KEY_STATUS_FILE,
    STAGE_RESULTS_FILE,
    AttemptPacer,
    ClassifiedTransport,
    PacedClientFactory,
    ViabilityPolicy,
    load_key_status,
    load_viability_policy,
    _runtime_config,
    _stage,
    _utc,
)
from .generation_config import ConfigurationError, GenerationConfig, model_matches
from .openrouter_client import (
    CostLimitError,
    GenerationError,
    IneligibleRoutingError,
    ProviderGenerationError,
    Transport,
    _check_selected_provider,
    _parse_json_bytes,
    _selected_provider,
)

PAID_BENCHMARK_VERSION = "phase-05-paid-benchmark/v1"
PAID_PRICING_FILE = "paid-pricing.json"
REQUIRED_MODEL_PARAMETERS = frozenset({"response_format", "structured_outputs"})


@dataclass(frozen=True)
class PaidBenchmarkPlan:
    version: int
    base_generation_config: str
    corpus_source_config: str
    runs_per_case: int
    model: EvaluationModel
    cases: tuple[Any, ...]
    maximum_prompt_price_per_million: float
    maximum_completion_price_per_million: float
    maximum_generation_cost_usd: float
    maximum_experiment_cost_usd: float

    @property
    def models(self) -> tuple[EvaluationModel, ...]:
        return (self.model,)

    @property
    def maximum_logical_calls(self) -> int:
        return 2 + len(self.cases) * self.runs_per_case


@dataclass(frozen=True)
class PaidAvailability:
    availability: ModelAvailability
    prompt_price_per_million: float | None
    completion_price_per_million: float | None
    context_length: int | None
    maximum_completion_tokens: int | None


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


def _number(value: Any, path: str, *, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EvaluationConfigurationError(f"{path} must be a number")
    result = float(value)
    if not minimum <= result <= maximum:
        raise EvaluationConfigurationError(f"{path} must be between {minimum} and {maximum}")
    return result


def _optional_date(value: Any, path: str) -> str | None:
    if value is None:
        return None
    text = _string(value, path)
    try:
        date.fromisoformat(text)
    except ValueError as exc:
        raise EvaluationConfigurationError(f"{path} must be YYYY-MM-DD") from exc
    return text


def load_paid_benchmark_plan(repository_root: str | Path, config_path: str | Path) -> PaidBenchmarkPlan:
    root = Path(repository_root).resolve()
    config_rel = _relative(str(config_path), "config_path")
    raw = yaml.safe_load((root / config_rel).read_text(encoding="utf-8"))
    config = _mapping(raw, config_rel)
    expected = {"version", "base_generation_config", "corpus_source_config", "model", "pricing"}
    if set(config) != expected or config.get("version") != 1:
        raise EvaluationConfigurationError("paid benchmark config must use version 1 and exact supported keys")

    source_rel = _relative(config.get("corpus_source_config"), "corpus_source_config")
    source_plan = load_evaluation_plan(root, source_rel)
    model_raw = _mapping(config.get("model"), "model")
    if set(model_raw) != {"key", "model", "availability_checked_at", "known_expiration_date"}:
        raise EvaluationConfigurationError("model must use the exact supported keys")
    key = _string(model_raw.get("key"), "model.key")
    slug = _string(model_raw.get("model"), "model.model")
    if slug.startswith("openrouter/") or "/" not in slug:
        raise EvaluationConfigurationError("model.model must be one explicit provider/model slug")
    if any(slug.endswith(suffix) for suffix in (":free", ":nitro", ":floor", ":exacto")):
        raise EvaluationConfigurationError("paid benchmark model must use the unmodified base slug")
    checked = _optional_date(model_raw.get("availability_checked_at"), "model.availability_checked_at")
    if checked is None:
        raise EvaluationConfigurationError("model.availability_checked_at is required")
    model = EvaluationModel(
        key=key,
        model=slug,
        role="current_candidate",
        availability_checked_at=checked,
        known_expiration_date=_optional_date(model_raw.get("known_expiration_date"), "model.known_expiration_date"),
    )

    pricing = _mapping(config.get("pricing"), "pricing")
    pricing_keys = {
        "mode",
        "maximum_prompt_price_per_million",
        "maximum_completion_price_per_million",
        "maximum_generation_cost_usd",
        "maximum_experiment_cost_usd",
    }
    if set(pricing) != pricing_keys or pricing.get("mode") != "paid":
        raise EvaluationConfigurationError("pricing must use paid mode and exact supported keys")
    prompt_cap = _number(pricing.get("maximum_prompt_price_per_million"), "pricing.maximum_prompt_price_per_million", minimum=0.000001, maximum=100)
    completion_cap = _number(pricing.get("maximum_completion_price_per_million"), "pricing.maximum_completion_price_per_million", minimum=0.000001, maximum=100)
    generation_cap = _number(pricing.get("maximum_generation_cost_usd"), "pricing.maximum_generation_cost_usd", minimum=0.000001, maximum=1)
    experiment_cap = _number(pricing.get("maximum_experiment_cost_usd"), "pricing.maximum_experiment_cost_usd", minimum=0.000001, maximum=5)
    maximum_calls = 2 + len(source_plan.cases) * source_plan.runs_per_case
    if experiment_cap < generation_cap * maximum_calls:
        raise EvaluationConfigurationError("maximum_experiment_cost_usd must cover every bounded logical call at the per-generation ceiling")

    return PaidBenchmarkPlan(
        version=1,
        base_generation_config=_relative(config.get("base_generation_config"), "base_generation_config"),
        corpus_source_config=source_rel,
        runs_per_case=source_plan.runs_per_case,
        model=model,
        cases=source_plan.cases,
        maximum_prompt_price_per_million=prompt_cap,
        maximum_completion_price_per_million=completion_cap,
        maximum_generation_cost_usd=generation_cap,
        maximum_experiment_cost_usd=experiment_cap,
    )


def prepare_paid_benchmark(
    *,
    repository_root: str | Path,
    config_path: str | Path,
    output_dir: str | Path,
    bundle_builder: Callable[..., Any] | None = None,
) -> tuple[PaidBenchmarkPlan, tuple[PreparedCase, ...]]:
    plan = load_paid_benchmark_plan(repository_root, config_path)
    kwargs: dict[str, Any] = {
        "repository_root": repository_root,
        "config_path": plan.corpus_source_config,
        "output_dir": output_dir,
    }
    if bundle_builder is not None:
        kwargs["bundle_builder"] = bundle_builder
    _, prepared = prepare_evaluation(**kwargs)
    manifest = _read_json(Path(output_dir) / PREPARED_MANIFEST)
    manifest.update({
        "evaluation_version": PAID_BENCHMARK_VERSION,
        "config_path": PurePosixPath(str(config_path)).as_posix(),
        "models": [asdict(plan.model)],
        "pricing": {
            "mode": "paid",
            "maximum_prompt_price_per_million": plan.maximum_prompt_price_per_million,
            "maximum_completion_price_per_million": plan.maximum_completion_price_per_million,
            "maximum_generation_cost_usd": plan.maximum_generation_cost_usd,
            "maximum_experiment_cost_usd": plan.maximum_experiment_cost_usd,
        },
    })
    _write_json(Path(output_dir) / PREPARED_MANIFEST, manifest)
    return plan, prepared


def _price_per_million(value: Any, path: str) -> Decimal:
    try:
        result = Decimal(str(value)) * Decimal(1_000_000)
    except (InvalidOperation, ValueError) as exc:
        raise EvaluationIntegrityError(f"{path} is not a valid catalogue price") from exc
    if result < 0:
        raise EvaluationIntegrityError(f"{path} must be non-negative")
    return result


def check_paid_model_availability(
    plan: PaidBenchmarkPlan,
    *,
    catalogue_loader: CatalogueLoader = _catalogue,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
) -> PaidAvailability:
    payload = catalogue_loader()
    rows = payload.get("data")
    if not isinstance(rows, list):
        raise EvaluationIntegrityError("OpenRouter model catalogue is missing data[]")
    row = next((item for item in rows if isinstance(item, Mapping) and item.get("id") == plan.model.model), None)
    checked = now().astimezone(timezone.utc)
    available = isinstance(row, Mapping)
    eligible = available
    reason: str | None = None
    prompt_raw = completion_raw = expiration = None
    supported: tuple[str, ...] = ()
    prompt_per_million = completion_per_million = None
    context_length = maximum_completion_tokens = None

    if isinstance(row, Mapping):
        params = row.get("supported_parameters")
        supported = tuple(sorted(str(item) for item in params)) if isinstance(params, list) else ()
        pricing = row.get("pricing") if isinstance(row.get("pricing"), Mapping) else {}
        prompt_raw = str(pricing.get("prompt")) if pricing.get("prompt") is not None else None
        completion_raw = str(pricing.get("completion")) if pricing.get("completion") is not None else None
        expiration = str(row.get("expiration_date")) if row.get("expiration_date") else None
        context_length = row.get("context_length") if isinstance(row.get("context_length"), int) else None
        top_provider = row.get("top_provider") if isinstance(row.get("top_provider"), Mapping) else {}
        maximum_completion_tokens = top_provider.get("max_completion_tokens") if isinstance(top_provider.get("max_completion_tokens"), int) else None
        missing = sorted(REQUIRED_MODEL_PARAMETERS - set(supported))
        if missing:
            eligible = False
            reason = "missing required parameters: " + ", ".join(missing)
        elif prompt_raw is None or completion_raw is None:
            eligible = False
            reason = "catalogue pricing is incomplete"
        else:
            prompt_decimal = _price_per_million(prompt_raw, "pricing.prompt")
            completion_decimal = _price_per_million(completion_raw, "pricing.completion")
            prompt_per_million = float(prompt_decimal)
            completion_per_million = float(completion_decimal)
            if prompt_decimal > Decimal(str(plan.maximum_prompt_price_per_million)):
                eligible = False
                reason = f"prompt price {prompt_decimal}/M exceeds approved cap {plan.maximum_prompt_price_per_million}/M"
            elif completion_decimal > Decimal(str(plan.maximum_completion_price_per_million)):
                eligible = False
                reason = f"completion price {completion_decimal}/M exceeds approved cap {plan.maximum_completion_price_per_million}/M"
        if eligible and context_length is not None and context_length < 16_384:
            eligible = False
            reason = "model context length is below the governed benchmark minimum"
        if eligible and maximum_completion_tokens is not None and maximum_completion_tokens < 4_000:
            eligible = False
            reason = "provider maximum completion is below the configured output limit"
        if expiration:
            try:
                expired = date.fromisoformat(expiration) < checked.date()
            except ValueError:
                eligible = False
                reason = "catalogue expiration_date is invalid"
            else:
                if expired:
                    eligible = False
                    reason = f"model expired on {expiration}"
    else:
        reason = "model slug not present in current OpenRouter catalogue"

    availability = ModelAvailability(
        plan.model.key,
        plan.model.model,
        available,
        eligible,
        reason,
        prompt_raw,
        completion_raw,
        supported,
        expiration,
        checked.isoformat().replace("+00:00", "Z"),
    )
    return PaidAvailability(availability, prompt_per_million, completion_per_million, context_length, maximum_completion_tokens)


def paid_route_probe(config: GenerationConfig, api_key: str, *, transport: Transport | None = None) -> Mapping[str, Any]:
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["ok"],
        "properties": {"ok": {"const": True}},
    }
    body = canonical_json_bytes({
        "model": config.model,
        "messages": [{"role": "user", "content": "Return exactly one JSON object with ok set to true."}],
        "temperature": 0,
        "max_tokens": 16,
        "stream": False,
        "response_format": {"type": "json_schema", "json_schema": {"name": "crypto_pulse_paid_route_probe", "strict": True, "schema": schema}},
        "provider": config.provider_policy.as_request(),
    })
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": config.app_referer,
        "X-OpenRouter-Title": config.app_title,
        "X-OpenRouter-Metadata": "enabled",
    }
    response = ClassifiedTransport(transport).post(config.endpoint, headers=headers, body=body, timeout_seconds=config.timeout_seconds)
    payload = _parse_json_bytes(response.body)
    if not isinstance(payload, Mapping):
        raise ProviderGenerationError("OpenRouter route probe response must be an object")
    actual_model = payload.get("model") if isinstance(payload.get("model"), str) else None
    if actual_model is None or not model_matches(config.model, actual_model):
        raise IneligibleRoutingError("OpenRouter route probe did not preserve the requested model")
    choices = payload.get("choices")
    if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], Mapping):
        raise ProviderGenerationError("OpenRouter route probe must return one choice")
    message = choices[0].get("message")
    content = message.get("content") if isinstance(message, Mapping) else None
    if not isinstance(content, str):
        raise ProviderGenerationError("OpenRouter route probe is missing message.content")
    try:
        decoded = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ProviderGenerationError("OpenRouter route probe did not return JSON") from exc
    if decoded != {"ok": True}:
        raise ProviderGenerationError("OpenRouter route probe did not satisfy its strict schema")
    metadata = payload.get("openrouter_metadata") if isinstance(payload.get("openrouter_metadata"), Mapping) else {}
    provider = _selected_provider(metadata)
    _check_selected_provider(config, provider)
    if provider is None:
        raise ProviderGenerationError("OpenRouter route probe did not identify the actual provider")
    usage = payload.get("usage") if isinstance(payload.get("usage"), Mapping) else {}
    cost_raw = usage.get("cost")
    if isinstance(cost_raw, bool) or not isinstance(cost_raw, (int, float)):
        raise CostLimitError("OpenRouter paid route probe did not report usage.cost")
    cost = float(cost_raw)
    if cost > config.max_cost_usd:
        raise CostLimitError(f"OpenRouter route probe cost {cost:.6f} USD exceeds configured limit")
    return {
        "requested_model": config.model,
        "actual_model": actual_model,
        "actual_provider": provider,
        "generation_id": payload.get("id") if isinstance(payload.get("id"), str) else None,
        "estimated_cost_usd": cost,
    }


def _paid_quota_summary(status: Mapping[str, Any], plan: PaidBenchmarkPlan) -> dict[str, Any]:
    remaining = status.get("limit_remaining")
    known_remaining = isinstance(remaining, (int, float)) and not isinstance(remaining, bool)
    insufficient = known_remaining and float(remaining) < plan.maximum_experiment_cost_usd
    return {
        "is_free_tier": status.get("is_free_tier"),
        "limit": status.get("limit"),
        "limit_reset": status.get("limit_reset"),
        "limit_remaining": remaining,
        "usage": status.get("usage"),
        "usage_daily": status.get("usage_daily"),
        "usage_weekly": status.get("usage_weekly"),
        "usage_monthly": status.get("usage_monthly"),
        "maximum_logical_calls": plan.maximum_logical_calls,
        "approved_experiment_cost_usd": plan.maximum_experiment_cost_usd,
        "request_budget_assessment": "insufficient" if insufficient else ("appears_sufficient" if known_remaining else "unknown"),
        "rate_limit_headroom_known": False,
    }


def _prepared_cases(plan: PaidBenchmarkPlan, prepared_root: Path) -> tuple[PreparedCase, ...]:
    manifest = _read_json(prepared_root / PREPARED_MANIFEST)
    if manifest.get("evaluation_version") != PAID_BENCHMARK_VERSION:
        raise EvaluationIntegrityError("prepared corpus is not a paid benchmark manifest")
    rows = manifest.get("cases")
    if not isinstance(rows, list):
        raise EvaluationIntegrityError("prepared manifest is missing cases")
    prepared = tuple(
        PreparedCase(str(row["key"]), str(row["snapshot_path"]), str(row["snapshot_sha256"]), str(row["quality_status"]), str(row["bundle_id"]), str(row["bundle_file"]), tuple(row.get("scenario_tags", [])), row.get("mutation"))
        for row in rows if isinstance(row, Mapping)
    )
    if tuple(item.key for item in prepared) != tuple(item.key for item in plan.cases):
        raise EvaluationIntegrityError("prepared corpus does not match paid benchmark plan")
    for item in prepared:
        if _read_json(prepared_root / item.bundle_file).get("bundle_id") != item.bundle_id:
            raise EvaluationIntegrityError(f"prepared bundle ID mismatch for {item.key}")
    return prepared


def _apply_cost_guard(
    summary: dict[str, Any],
    *,
    plan: PaidBenchmarkPlan,
    route_cost: float | None,
    smoke_record: RunRecord | None,
    records: list[RunRecord],
) -> dict[str, Any]:
    smoke_cost = smoke_record.estimated_cost_usd if smoke_record is not None else None
    full_costs = [item.estimated_cost_usd for item in records]
    all_required_runs_completed = len(records) == len(plan.cases) * plan.runs_per_case
    cost_metadata_complete = route_cost is not None and smoke_cost is not None and all(value is not None for value in full_costs) if all_required_runs_completed else False
    total = sum(value for value in [route_cost, smoke_cost, *full_costs] if value is not None)
    exceeded = total > plan.maximum_experiment_cost_usd
    summary["paid_benchmark"] = {
        "approved_prompt_price_per_million": plan.maximum_prompt_price_per_million,
        "approved_completion_price_per_million": plan.maximum_completion_price_per_million,
        "approved_generation_cost_usd": plan.maximum_generation_cost_usd,
        "approved_experiment_cost_usd": plan.maximum_experiment_cost_usd,
        "route_cost_usd": route_cost,
        "smoke_cost_usd": smoke_cost,
        "full_corpus_cost_usd": sum(value for value in full_costs if value is not None),
        "total_cost_usd": total,
        "cost_metadata_complete_for_qualification": cost_metadata_complete,
        "experiment_cost_ceiling_exceeded": exceeded,
    }
    if summary["decision"]["selected_model"] is not None and (not cost_metadata_complete or exceeded):
        summary["model_results"][0]["disqualified"] = True
        summary["decision"] = {
            "decision": "no-go",
            "selected_model": None,
            "reason": "The model passed content gates but did not satisfy the complete paid-cost evidence and experiment ceiling.",
        }
    return summary


def execute_paid_benchmark(
    *,
    repository_root: str | Path,
    config_path: str | Path,
    viability_config_path: str | Path,
    prepared_dir: str | Path,
    output_dir: str | Path,
    api_key: str | None = None,
    trusted_main_sha: str | None = None,
    catalogue_loader: CatalogueLoader = _catalogue,
    key_status_loader: Callable[[str], Mapping[str, Any]] = load_key_status,
    probe: Callable[[GenerationConfig, str], Mapping[str, Any]] = paid_route_probe,
    client_builder: Callable[[GenerationConfig], Any] | None = None,
    sleeper: Callable[[float], None] | None = None,
    monotonic: Callable[[], float] | None = None,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    jitter: Callable[[float, float], float] | None = None,
) -> dict[str, Any]:
    import random
    import time

    root = Path(repository_root).resolve()
    prepared_root = Path(prepared_dir)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    plan = load_paid_benchmark_plan(root, config_path)
    policy: ViabilityPolicy = load_viability_policy(root / viability_config_path)
    prepared = _prepared_cases(plan, prepared_root)
    smoke = next((item for item in prepared if item.key == policy.smoke_case_key), None)
    if smoke is None:
        raise EvaluationConfigurationError(f"smoke case {policy.smoke_case_key!r} is not in the prepared corpus")
    paid_availability = check_paid_model_availability(plan, catalogue_loader=catalogue_loader, now=now)
    availability = (paid_availability.availability,)
    _write_json(output / AVAILABILITY_FILE, {"models": [asdict(item) for item in availability]})
    _write_json(output / PAID_PRICING_FILE, {
        "model": plan.model.model,
        "prompt_price_per_million": paid_availability.prompt_price_per_million,
        "completion_price_per_million": paid_availability.completion_price_per_million,
        "context_length": paid_availability.context_length,
        "maximum_completion_tokens": paid_availability.maximum_completion_tokens,
        "approved_prompt_price_per_million": plan.maximum_prompt_price_per_million,
        "approved_completion_price_per_million": plan.maximum_completion_price_per_million,
    })
    if not api_key:
        raise EvaluationIntegrityError("OPENROUTER_API_KEY is required for controlled paid benchmark")
    key_status = _paid_quota_summary(key_status_loader(api_key), plan)
    _write_json(output / KEY_STATUS_FILE, key_status)

    pacer = AttemptPacer(
        policy,
        sleeper=sleeper or time.sleep,
        monotonic=monotonic or time.monotonic,
        now=now,
        jitter=jitter or random.uniform,
    )
    factory = PacedClientFactory(pacer, client_builder)
    stages: list[dict[str, Any]] = []
    records: list[RunRecord] = []
    route_cost: float | None = None
    smoke_record: RunRecord | None = None

    if key_status["request_budget_assessment"] == "insufficient":
        stages.append(_stage(plan.model, "route_preflight", "not_run", failure_code="insufficient_quota"))
    elif not paid_availability.availability.eligible:
        stages.append(_stage(plan.model, "route_preflight", "ineligible", failure_code="model_ineligible", details={"reason": paid_availability.availability.reason}))
    else:
        runtime = _runtime_config(root, plan.base_generation_config, plan.model, output / "runtime-configs" / f"{plan.model.key}.yml")
        if abs(runtime.max_cost_usd - plan.maximum_generation_cost_usd) > 1e-12:
            raise EvaluationConfigurationError("base generation max_cost_usd does not match the paid benchmark plan")
        logical_id = f"route-preflight/{plan.model.key}"
        try:
            route = pacer.call(logical_id, lambda: probe(runtime, api_key))
        except (GenerationError, ConfigurationError, OSError, ValueError, RuntimeError, TypeError) as exc:
            stages.append(_stage(plan.model, "route_preflight", "failed", failure_code=str(getattr(exc, "code", None) or "route_preflight_failure")))
        else:
            route_cost = route.get("estimated_cost_usd") if isinstance(route.get("estimated_cost_usd"), (int, float)) else None
            stages.append(_stage(plan.model, "route_preflight", "passed", details=route))
            factory.set_logical_id(f"contract-smoke/{plan.model.key}/{smoke.key}")
            smoke_record = _run_one(
                root=root,
                model=plan.model,
                config=runtime,
                prepared=smoke,
                prepared_dir=prepared_root,
                repeat=1,
                output_dir=output / "stages" / "smoke",
                api_key=api_key,
                client_factory=factory,
            )
            smoke_passed = smoke_record.hard_pass and smoke_record.estimated_cost_usd is not None
            smoke_failure = smoke_record.failure_code if smoke_record.failure_code else (None if smoke_passed else "cost_metadata_missing")
            stages.append(_stage(plan.model, "contract_smoke", "passed" if smoke_passed else "failed", failure_code=smoke_failure, details={"validation": smoke_record.validation, "run_record": smoke_record.output_dir, "estimated_cost_usd": smoke_record.estimated_cost_usd}))
            if smoke_passed:
                stages.append(_stage(plan.model, "full_corpus_selection", "selected", details={"rule": "single approved paid benchmark model"}))
                for case in prepared:
                    for repeat in range(1, plan.runs_per_case + 1):
                        factory.set_logical_id(f"full-corpus/{plan.model.key}/{case.key}/repeat-{repeat}")
                        records.append(_run_one(
                            root=root,
                            model=plan.model,
                            config=runtime,
                            prepared=case,
                            prepared_dir=prepared_root,
                            repeat=repeat,
                            output_dir=output,
                            api_key=api_key,
                            client_factory=factory,
                        ))

    summary = _aggregate(plan, availability, records)
    summary["evaluation_version"] = PAID_BENCHMARK_VERSION
    summary["trusted_main_sha"] = trusted_main_sha
    summary["completed_at"] = _utc(now())
    summary["viability"] = {
        "policy": asdict(policy),
        "key_status": key_status,
        "maximum_logical_calls": plan.maximum_logical_calls,
        "completed_logical_calls": len({item.logical_id for item in pacer.records}),
        "http_attempts": len(pacer.records),
        "route_preflight_candidates": 1,
        "smoke_passes": sum(item["stage"] == "contract_smoke" and item["status"] == "passed" for item in stages),
        "full_corpus_finalists": [plan.model.key] if any(item["stage"] == "full_corpus_selection" and item["status"] == "selected" for item in stages) else [],
        "stages": stages,
    }
    _apply_cost_guard(summary, plan=plan, route_cost=route_cost, smoke_record=smoke_record, records=records)
    _write_json(output / ATTEMPT_RECORDS_FILE, {"attempts": [asdict(item) for item in pacer.records]})
    _write_json(output / STAGE_RESULTS_FILE, {"stages": stages})
    _write_json(output / SUMMARY_JSON, summary)

    decision = _decision_text(summary, availability)
    paid = summary["paid_benchmark"]
    decision += "\n\n## Paid benchmark boundary\n\n"
    decision += f"- Maximum logical calls: `{plan.maximum_logical_calls}`\n"
    decision += f"- Completed logical calls: `{summary['viability']['completed_logical_calls']}`\n"
    decision += f"- HTTP attempts: `{summary['viability']['http_attempts']}`\n"
    decision += f"- Approved per-generation cost: `${plan.maximum_generation_cost_usd}`\n"
    decision += f"- Approved experiment cost: `${plan.maximum_experiment_cost_usd}`\n"
    decision += f"- Recorded total cost: `${paid['total_cost_usd']}`\n"
    decision += f"- Cost metadata complete for qualification: `{paid['cost_metadata_complete_for_qualification']}`\n"
    (output / DECISION_MARKDOWN).write_text(decision, encoding="utf-8")
    worksheet = ["model_key,case_key,repeat,manual_usefulness_0_to_5,manual_readability_0_to_5,reviewer_notes"] + [
        f"{plan.model.key},{case.key},{repeat},,," for case in plan.cases for repeat in range(1, plan.runs_per_case + 1)
    ]
    (output / REVIEWER_WORKSHEET).write_text("\n".join(worksheet) + "\n", encoding="utf-8")
    (output / ACTIONS_SUMMARY).write_text(decision + f"\n\n- Trusted main commit: `{trusted_main_sha or 'not-recorded'}`\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare")
    prepare.add_argument("--repository-root", default=".")
    prepare.add_argument("--config", default="config/llm-evaluation-gpt-4o-mini.yml")
    prepare.add_argument("--output-dir", required=True)
    run = sub.add_parser("run")
    run.add_argument("--repository-root", default=".")
    run.add_argument("--config", default="config/llm-evaluation-gpt-4o-mini.yml")
    run.add_argument("--viability-config", default="config/llm-evaluation-viability.yml")
    run.add_argument("--prepared-dir", required=True)
    run.add_argument("--output-dir", required=True)
    run.add_argument("--trusted-main-sha")
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            plan, cases = prepare_paid_benchmark(repository_root=args.repository_root, config_path=args.config, output_dir=args.output_dir)
            print(json.dumps({"model": plan.model.model, "cases": len(cases), "runs_per_case": plan.runs_per_case, "maximum_logical_calls": plan.maximum_logical_calls}, sort_keys=True))
        else:
            summary = execute_paid_benchmark(
                repository_root=args.repository_root,
                config_path=args.config,
                viability_config_path=args.viability_config,
                prepared_dir=args.prepared_dir,
                output_dir=args.output_dir,
                api_key=os.environ.get("OPENROUTER_API_KEY"),
                trusted_main_sha=args.trusted_main_sha,
            )
            print(json.dumps(summary["decision"], sort_keys=True))
        return 0
    except (EvaluationConfigurationError, EvaluationIntegrityError, EvidenceBundleError, ConfigurationError, OSError, ValueError, TypeError) as exc:
        secret = os.environ.get("OPENROUTER_API_KEY", "")
        message = " ".join(str(exc).split())[:500]
        if secret:
            message = message.replace(secret, "[REDACTED]")
        print(json.dumps({"error": message}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
