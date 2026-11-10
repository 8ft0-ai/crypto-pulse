"""Observable two-stage OpenRouter transport calibration for the real selector request."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Mapping, Sequence

import yaml

from .candidate_selection_contract import (
    SelectorEnvelopeError,
    render_candidate_selector_prompt,
    validate_candidate_selection,
)
from .candidate_selector_compact_projection import (
    build_compact_candidate_selector_request,
)
from .candidate_selector_stage0 import (
    STAGE0_PREPARED_MANIFEST,
    STAGE0_PREPARED_VERSION,
    prepare_stage0,
)
from .claim_plan_render import render_claim_plan
from .claim_plan_validation import validate_claim_plan
from .contracts import canonical_json_bytes, content_sha256
from .deterministic_ranking import load_ranking_config
from .deterministic_reconstruction import reconstruct_claim_plan
from .evaluation import EvaluationIntegrityError, _read_json, _write_json
from .generation_config import model_matches
from .openai_schema_projection import project_openai_strict_schema
from .openrouter_client import HttpResponse, Transport, UrllibTransport, _selected_provider

CALIBRATION_VERSION = "phase-08-openrouter-transport-calibration/v1"
DEFAULT_CONFIG = "config/openrouter-transport-calibration-v1.yml"
SUMMARY_FILE = "transport-calibration-summary.json"
RESULTS_FILE = "transport-calibration-results.json"
ACTIONS_SUMMARY = "actions-summary.md"


@dataclass(frozen=True)
class CalibrationModel:
    key: str
    model: str
    preferred_provider_slug: str
    maximum_prompt_price_per_million: float
    maximum_completion_price_per_million: float


@dataclass(frozen=True)
class CalibrationPlan:
    version: int
    case_key: str
    expected_candidate_count: int
    stage0_preparation_config: str
    selector_prompt: str
    selection_schema: str
    ranking_config: str
    max_output_tokens: int
    reasoning_effort: str
    maximum_discovery_calls: int
    maximum_reproduction_calls: int
    maximum_paid_calls: int
    maximum_semantic_repairs: int
    maximum_network_retries: int
    maximum_call_cost_usd: float
    maximum_total_cost_usd: float
    provider_slug_by_name: Mapping[str, str]
    models: tuple[CalibrationModel, ...]


class CalibrationConfigurationError(ValueError):
    """The checked-in Phase 8 configuration is not the reviewed contract."""


def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise CalibrationConfigurationError(f"{path} must be an object")
    return value


def _string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CalibrationConfigurationError(f"{path} must be a non-empty string")
    return value.strip()


def _integer(value: Any, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise CalibrationConfigurationError(f"{path} must be an integer")
    return value


def _number(value: Any, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise CalibrationConfigurationError(f"{path} must be a number")
    return float(value)


def load_calibration_plan(
    repository_root: str | Path,
    config_path: str | Path = DEFAULT_CONFIG,
) -> CalibrationPlan:
    root = Path(repository_root).resolve()
    raw = yaml.safe_load((root / config_path).read_text(encoding="utf-8"))
    document = _mapping(raw, "configuration")
    expected = {
        "version",
        "case_key",
        "expected_candidate_count",
        "stage0_preparation_config",
        "selector_prompt",
        "selection_schema",
        "ranking_config",
        "max_output_tokens",
        "reasoning_effort",
        "maximum_discovery_calls",
        "maximum_reproduction_calls",
        "maximum_paid_calls",
        "maximum_semantic_repairs",
        "maximum_network_retries",
        "maximum_call_cost_usd",
        "maximum_total_cost_usd",
        "provider_slug_by_name",
        "models",
    }
    if set(document) != expected:
        unknown = sorted(set(document) - expected)
        missing = sorted(expected - set(document))
        raise CalibrationConfigurationError(
            f"configuration keys differ; unknown={unknown}, missing={missing}"
        )
    if document.get("version") != 1:
        raise CalibrationConfigurationError("configuration.version must be 1")
    providers_raw = _mapping(document.get("provider_slug_by_name"), "provider_slug_by_name")
    providers = {
        _string(name, "provider_slug_by_name.name"): _string(
            slug, f"provider_slug_by_name.{name}"
        )
        for name, slug in providers_raw.items()
    }
    models_raw = document.get("models")
    if not isinstance(models_raw, list) or len(models_raw) != 2:
        raise CalibrationConfigurationError("models must contain exactly two candidates")
    model_keys = {
        "key",
        "model",
        "preferred_provider_slug",
        "maximum_prompt_price_per_million",
        "maximum_completion_price_per_million",
    }
    models: list[CalibrationModel] = []
    for index, value in enumerate(models_raw):
        row = _mapping(value, f"models[{index}]")
        if set(row) != model_keys:
            raise CalibrationConfigurationError(f"models[{index}] has unexpected keys")
        model = _string(row.get("model"), f"models[{index}].model")
        if "/" not in model or model.startswith("openrouter/"):
            raise CalibrationConfigurationError("each model must use one explicit model slug")
        models.append(
            CalibrationModel(
                key=_string(row.get("key"), f"models[{index}].key"),
                model=model,
                preferred_provider_slug=_string(
                    row.get("preferred_provider_slug"),
                    f"models[{index}].preferred_provider_slug",
                ),
                maximum_prompt_price_per_million=_number(
                    row.get("maximum_prompt_price_per_million"),
                    f"models[{index}].maximum_prompt_price_per_million",
                ),
                maximum_completion_price_per_million=_number(
                    row.get("maximum_completion_price_per_million"),
                    f"models[{index}].maximum_completion_price_per_million",
                ),
            )
        )
    plan = CalibrationPlan(
        version=1,
        case_key=_string(document.get("case_key"), "case_key"),
        expected_candidate_count=_integer(
            document.get("expected_candidate_count"), "expected_candidate_count"
        ),
        stage0_preparation_config=_string(
            document.get("stage0_preparation_config"), "stage0_preparation_config"
        ),
        selector_prompt=_string(document.get("selector_prompt"), "selector_prompt"),
        selection_schema=_string(document.get("selection_schema"), "selection_schema"),
        ranking_config=_string(document.get("ranking_config"), "ranking_config"),
        max_output_tokens=_integer(document.get("max_output_tokens"), "max_output_tokens"),
        reasoning_effort=_string(document.get("reasoning_effort"), "reasoning_effort"),
        maximum_discovery_calls=_integer(
            document.get("maximum_discovery_calls"), "maximum_discovery_calls"
        ),
        maximum_reproduction_calls=_integer(
            document.get("maximum_reproduction_calls"), "maximum_reproduction_calls"
        ),
        maximum_paid_calls=_integer(
            document.get("maximum_paid_calls"), "maximum_paid_calls"
        ),
        maximum_semantic_repairs=_integer(
            document.get("maximum_semantic_repairs"), "maximum_semantic_repairs"
        ),
        maximum_network_retries=_integer(
            document.get("maximum_network_retries"), "maximum_network_retries"
        ),
        maximum_call_cost_usd=_number(
            document.get("maximum_call_cost_usd"), "maximum_call_cost_usd"
        ),
        maximum_total_cost_usd=_number(
            document.get("maximum_total_cost_usd"), "maximum_total_cost_usd"
        ),
        provider_slug_by_name=providers,
        models=tuple(models),
    )
    if plan.case_key != "historical-degraded-sparse":
        raise CalibrationConfigurationError("Phase 8 must use historical-degraded-sparse")
    if plan.expected_candidate_count != 201:
        raise CalibrationConfigurationError("Phase 8 must retain all 201 candidates")
    if plan.max_output_tokens != 2048 or plan.reasoning_effort != "minimal":
        raise CalibrationConfigurationError("Phase 8 must use 2,048 tokens and minimal reasoning")
    if (
        plan.maximum_discovery_calls != 2
        or plan.maximum_reproduction_calls != 1
        or plan.maximum_paid_calls != 3
        or plan.maximum_semantic_repairs != 0
        or plan.maximum_network_retries != 0
    ):
        raise CalibrationConfigurationError("Phase 8 call and repair ceilings changed")
    if abs(plan.maximum_call_cost_usd - 0.025) > 1e-12:
        raise CalibrationConfigurationError("Phase 8 per-call ceiling must be USD 0.025")
    if abs(plan.maximum_total_cost_usd - 0.060) > 1e-12:
        raise CalibrationConfigurationError("Phase 8 total ceiling must be USD 0.060")
    if [item.model for item in plan.models] != [
        "inception/mercury-2",
        "openai/gpt-oss-120b",
    ]:
        raise CalibrationConfigurationError("Phase 8 model order changed")
    return plan


def _read_object(path: Path) -> dict[str, Any]:
    value = _read_json(path)
    if not isinstance(value, dict):
        raise EvaluationIntegrityError(f"{path} must contain a JSON object")
    return value


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def prepare_transport_calibration(
    *,
    repository_root: str | Path,
    config_path: str | Path = DEFAULT_CONFIG,
    output_dir: str | Path,
) -> dict[str, Any]:
    """Reuse the reviewed secret-free Phase 7 preparation for the real case."""

    root = Path(repository_root).resolve()
    output = Path(output_dir).resolve()
    plan = load_calibration_plan(root, config_path)
    result = prepare_stage0(
        repository_root=root,
        config_path=plan.stage0_preparation_config,
        output_dir=output,
    )
    manifest = _read_object(output / STAGE0_PREPARED_MANIFEST)
    if manifest.get("version") != STAGE0_PREPARED_VERSION:
        raise EvaluationIntegrityError("Phase 8 preparation has the wrong manifest version")
    if manifest.get("case_key") != plan.case_key:
        raise EvaluationIntegrityError("Phase 8 preparation selected the wrong case")
    if manifest.get("candidate_count") != plan.expected_candidate_count:
        raise EvaluationIntegrityError("Phase 8 preparation lost candidates")
    return {
        "version": CALIBRATION_VERSION,
        "case_key": plan.case_key,
        "candidate_count": manifest.get("candidate_count"),
        "compact_request_id": manifest.get("compact_request_id"),
        "compact_request_bytes": manifest.get("compact_request_bytes"),
        "provider_calls": result.get("provider_calls", 0),
    }


class _Ledger:
    def __init__(self, plan: CalibrationPlan) -> None:
        self.plan = plan
        self.calls = 0
        self.discovery_calls = 0
        self.reproduction_calls = 0
        self.total_cost = 0.0

    def before(self, stage: str) -> None:
        if self.calls >= self.plan.maximum_paid_calls:
            raise EvaluationIntegrityError("Phase 8 paid-call ceiling would be exceeded")
        if stage == "discovery":
            if self.discovery_calls >= self.plan.maximum_discovery_calls:
                raise EvaluationIntegrityError("Phase 8 discovery-call ceiling would be exceeded")
            self.discovery_calls += 1
        elif stage == "reproduction":
            if self.reproduction_calls >= self.plan.maximum_reproduction_calls:
                raise EvaluationIntegrityError("Phase 8 reproduction-call ceiling would be exceeded")
            self.reproduction_calls += 1
        else:
            raise EvaluationIntegrityError(f"unknown Phase 8 stage: {stage}")
        if (
            self.total_cost + self.plan.maximum_call_cost_usd
            > self.plan.maximum_total_cost_usd + 1e-12
        ):
            raise EvaluationIntegrityError("Phase 8 total cost reservation would be exceeded")
        self.calls += 1

    def charge(self, amount: float) -> None:
        if amount < 0:
            raise EvaluationIntegrityError("provider cost must not be negative")
        self.total_cost += amount
        if self.total_cost > self.plan.maximum_total_cost_usd + 1e-12:
            raise EvaluationIntegrityError("Phase 8 observed total cost exceeded its ceiling")


def _provider_slug(plan: CalibrationPlan, provider_name: str | None) -> str | None:
    if provider_name is None:
        return None
    direct = plan.provider_slug_by_name.get(provider_name)
    if direct:
        return direct
    normalised = "".join(character for character in provider_name.lower() if character.isalnum())
    for name, slug in plan.provider_slug_by_name.items():
        candidate = "".join(character for character in name.lower() if character.isalnum())
        if candidate == normalised:
            return slug
    return None


def _provider_policy(
    plan: CalibrationPlan,
    model: CalibrationModel,
    *,
    reproduction_provider_slug: str | None,
) -> dict[str, Any]:
    slug = reproduction_provider_slug or model.preferred_provider_slug
    policy: dict[str, Any] = {
        "require_parameters": True,
        "data_collection": "deny",
        "allow_fallbacks": reproduction_provider_slug is None,
        "order": [slug],
        "max_price": {
            "prompt": model.maximum_prompt_price_per_million,
            "completion": model.maximum_completion_price_per_million,
            "request": plan.maximum_call_cost_usd,
        },
    }
    if reproduction_provider_slug is not None:
        policy["only"] = [reproduction_provider_slug]
    return policy


def _safe_headers(headers: Mapping[str, str]) -> dict[str, str]:
    allowed = {"content-type", "x-request-id", "cf-ray", "x-openrouter-request-id"}
    return {
        str(key).lower(): str(value)
        for key, value in headers.items()
        if str(key).lower() in allowed
    }


def _initial_observation(
    *,
    stage: str,
    model: CalibrationModel,
    request_body: bytes,
    response: HttpResponse,
    api_key: str,
) -> dict[str, Any]:
    text = response.body.decode("utf-8", errors="replace")
    if api_key:
        text = text.replace(api_key, "[REDACTED]")
    return {
        "version": CALIBRATION_VERSION,
        "stage": stage,
        "requested_model": model.model,
        "http_status": response.status,
        "response_headers": _safe_headers(response.headers),
        "request_sha256": _sha256_bytes(request_body),
        "request_bytes": len(request_body),
        "raw_body_sha256": _sha256_bytes(response.body),
        "raw_body_utf8": text,
    }


def _request_body(
    *,
    plan: CalibrationPlan,
    model: CalibrationModel,
    prompt_template: str,
    compact_request: Mapping[str, Any],
    provider_schema: Mapping[str, Any],
    reproduction_provider_slug: str | None,
) -> bytes:
    prompt = render_candidate_selector_prompt(prompt_template, compact_request, None)
    value = {
        "model": model.model,
        "messages": [{"role": "system", "content": prompt}],
        "max_tokens": plan.max_output_tokens,
        "stream": False,
        "reasoning": {
            "effort": plan.reasoning_effort,
            "exclude": True,
        },
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "crypto_market_candidate_selection_v1",
                "strict": True,
                "schema": dict(provider_schema),
            },
        },
        "provider": _provider_policy(
            plan,
            model,
            reproduction_provider_slug=reproduction_provider_slug,
        ),
    }
    return canonical_json_bytes(value)


def _summary_markdown(summary: Mapping[str, Any]) -> str:
    lines = [
        "# Phase 8 observable OpenRouter transport calibration",
        "",
        "> Transport evidence only. This run does not approve model selection or publication.",
        "",
        f"- Trusted main SHA: `{summary.get('trusted_main_sha')}`",
        f"- Decision question answered yes: `{str(summary.get('decision_question_answered', False)).lower()}`",
        f"- Paid calls: `{summary.get('completed_paid_calls')} / {summary.get('maximum_paid_calls')}`",
        f"- Governed cost: `USD {float(summary.get('observed_total_cost_usd', 0.0)):.6f}`",
        "",
        "| Stage | Model | Classification | Provider | Cost |",
        "| --- | --- | --- | --- | ---: |",
    ]
    for row in summary.get("calls", []):
        lines.append(
            f"| `{row.get('stage')}` | `{row.get('model')}` | "
            f"`{row.get('classification')}` | `{row.get('actual_provider')}` | "
            f"USD {float(row.get('observed_cost_usd', 0.0)):.6f} |"
        )
    lines.extend(
        [
            "",
            "Quality, stability and production suitability remain unassessed.",
            "",
        ]
    )
    return "\n".join(lines)


def _call(
    *,
    root: Path,
    output: Path,
    plan: CalibrationPlan,
    model: CalibrationModel,
    stage: str,
    compact_request: Mapping[str, Any],
    canonical_request: Mapping[str, Any],
    candidates: Sequence[Mapping[str, Any]],
    bundle: Mapping[str, Any],
    prompt_template: str,
    provider_schema: Mapping[str, Any],
    selection_schema: Mapping[str, Any],
    ranking: Any,
    evidence_schema: Mapping[str, Any],
    claim_plan_schema: Mapping[str, Any],
    api_key: str,
    ledger: _Ledger,
    transport: Transport,
    reproduction_provider_slug: str | None,
) -> dict[str, Any]:
    call_dir = output / "models" / model.key / stage
    call_dir.mkdir(parents=True, exist_ok=True)
    request_body = _request_body(
        plan=plan,
        model=model,
        prompt_template=prompt_template,
        compact_request=compact_request,
        provider_schema=provider_schema,
        reproduction_provider_slug=reproduction_provider_slug,
    )
    (call_dir / "request.json").write_bytes(request_body + b"\n")
    ledger.before(stage)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/8ft0-ai/crypto-pulse",
        "X-OpenRouter-Title": "CryptoPulse Phase 8 Transport Calibration",
        "X-OpenRouter-Metadata": "enabled",
    }
    try:
        response = transport.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            body=request_body,
            timeout_seconds=180.0,
        )
    except Exception as exc:
        ledger.charge(plan.maximum_call_cost_usd)
        result = {
            "stage": stage,
            "model_key": model.key,
            "model": model.model,
            "classification": "transport-error",
            "failure_code": str(getattr(exc, "code", None) or "transport_error"),
            "message": " ".join(str(exc).split())[:500].replace(api_key, "[REDACTED]"),
            "observed_cost_usd": plan.maximum_call_cost_usd,
            "metering_status": "reserved-maximum",
            "actual_model": None,
            "actual_provider": None,
            "provider_slug": None,
            "selected_candidate_ids": [],
        }
        _write_json(call_dir / "result.json", result)
        return result

    observation = _initial_observation(
        stage=stage,
        model=model,
        request_body=request_body,
        response=response,
        api_key=api_key,
    )
    # This protected record is written before any JSON, metering, identity or content judgment.
    _write_json(call_dir / "http-response.json", observation)

    try:
        payload = json.loads(response.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        ledger.charge(plan.maximum_call_cost_usd)
        result = {
            "stage": stage,
            "model_key": model.key,
            "model": model.model,
            "classification": "non-json-response",
            "failure_code": "non_json_response",
            "message": "OpenRouter response was not JSON",
            "observed_cost_usd": plan.maximum_call_cost_usd,
            "metering_status": "reserved-maximum",
            "actual_model": None,
            "actual_provider": None,
            "provider_slug": None,
            "selected_candidate_ids": [],
        }
        _write_json(call_dir / "result.json", result)
        return result
    if not isinstance(payload, Mapping):
        ledger.charge(plan.maximum_call_cost_usd)
        result = {
            "stage": stage,
            "model_key": model.key,
            "model": model.model,
            "classification": "invalid-response-shape",
            "failure_code": "response_not_object",
            "message": "OpenRouter response was not an object",
            "observed_cost_usd": plan.maximum_call_cost_usd,
            "metering_status": "reserved-maximum",
            "actual_model": None,
            "actual_provider": None,
            "provider_slug": None,
            "selected_candidate_ids": [],
        }
        _write_json(call_dir / "result.json", result)
        return result

    usage = payload.get("usage") if isinstance(payload.get("usage"), Mapping) else {}
    cost_raw = usage.get("cost")
    if isinstance(cost_raw, bool) or not isinstance(cost_raw, (int, float)):
        cost = plan.maximum_call_cost_usd
        metering_status = "reserved-maximum"
    else:
        cost = float(cost_raw)
        metering_status = "reported"
    ledger.charge(cost)

    metadata = (
        payload.get("openrouter_metadata")
        if isinstance(payload.get("openrouter_metadata"), Mapping)
        else {}
    )
    actual_model = payload.get("model") if isinstance(payload.get("model"), str) else None
    actual_provider = _selected_provider(metadata)
    provider_slug = _provider_slug(plan, actual_provider)
    attempts = metadata.get("attempts") if isinstance(metadata.get("attempts"), list) else []
    router_attempt = metadata.get("attempt") if isinstance(metadata.get("attempt"), int) else None
    choices = payload.get("choices") if isinstance(payload.get("choices"), list) else []
    choice = choices[0] if len(choices) == 1 and isinstance(choices[0], Mapping) else {}
    message = choice.get("message") if isinstance(choice.get("message"), Mapping) else {}
    content = message.get("content") if isinstance(message.get("content"), str) else None
    interpreted = {
        "version": CALIBRATION_VERSION,
        "stage": stage,
        "requested_model": model.model,
        "actual_model": actual_model,
        "actual_provider": actual_provider,
        "provider_slug": provider_slug,
        "generation_id": payload.get("id") if isinstance(payload.get("id"), str) else None,
        "finish_reason": choice.get("finish_reason"),
        "content_present": content is not None and bool(content),
        "content": content,
        "reasoning": message.get("reasoning"),
        "reasoning_details": message.get("reasoning_details"),
        "usage": dict(usage),
        "observed_cost_usd": cost,
        "metering_status": metering_status,
        "router_attempt": router_attempt,
        "router_attempts": attempts,
        "openrouter_metadata": dict(metadata),
        "top_level_error": payload.get("error"),
        "choice_error": choice.get("error"),
    }
    _write_json(call_dir / "interpreted-response.json", interpreted)

    base = {
        "stage": stage,
        "model_key": model.key,
        "model": model.model,
        "actual_model": actual_model,
        "actual_provider": actual_provider,
        "provider_slug": provider_slug,
        "observed_cost_usd": cost,
        "metering_status": metering_status,
        "selected_candidate_ids": [],
        "finish_reason": choice.get("finish_reason"),
        "input_tokens": usage.get("prompt_tokens"),
        "output_tokens": usage.get("completion_tokens"),
        "reasoning_tokens": (
            usage.get("completion_tokens_details", {}).get("reasoning_tokens")
            if isinstance(usage.get("completion_tokens_details"), Mapping)
            else None
        ),
        "router_attempt": router_attempt,
        "router_attempt_count": len(attempts),
    }

    if not 200 <= response.status < 300:
        result = {
            **base,
            "classification": "http-error",
            "failure_code": "http_error",
            "message": f"OpenRouter returned HTTP {response.status}",
        }
        _write_json(call_dir / "result.json", result)
        return result
    if metering_status != "reported":
        result = {
            **base,
            "classification": "incomplete-metering",
            "failure_code": "usage_cost_missing",
            "message": "OpenRouter response did not report usage.cost",
        }
        _write_json(call_dir / "result.json", result)
        return result
    if cost > plan.maximum_call_cost_usd + 1e-12:
        result = {
            **base,
            "classification": "cost-ineligible",
            "failure_code": "call_cost_exceeded",
            "message": "OpenRouter response exceeded the reviewed per-call ceiling",
        }
        _write_json(call_dir / "result.json", result)
        return result
    if actual_model is None or not model_matches(model.model, actual_model):
        result = {
            **base,
            "classification": "identity-failure",
            "failure_code": "model_identity_mismatch",
            "message": "OpenRouter did not preserve the requested model identity",
        }
        _write_json(call_dir / "result.json", result)
        return result
    if not metadata or actual_provider is None:
        result = {
            **base,
            "classification": "router-metadata-missing",
            "failure_code": "provider_identity_missing",
            "message": "OpenRouter did not identify the selected provider",
        }
        _write_json(call_dir / "result.json", result)
        return result
    if provider_slug is None:
        result = {
            **base,
            "classification": "provider-slug-unmapped",
            "failure_code": "provider_slug_unmapped",
            "message": "The observed provider has no reviewed canonical slug mapping",
        }
        _write_json(call_dir / "result.json", result)
        return result
    if reproduction_provider_slug is not None:
        if provider_slug != reproduction_provider_slug:
            result = {
                **base,
                "classification": "identity-failure",
                "failure_code": "reproduction_provider_mismatch",
                "message": "Reproduction did not preserve the discovered provider slug",
            }
            _write_json(call_dir / "result.json", result)
            return result
        if (isinstance(router_attempt, int) and router_attempt > 1) or len(attempts) > 1:
            result = {
                **base,
                "classification": "identity-failure",
                "failure_code": "reproduction_fallback_used",
                "message": "Reproduction used more than one provider attempt",
            }
            _write_json(call_dir / "result.json", result)
            return result
    if len(choices) != 1:
        result = {
            **base,
            "classification": "invalid-response-shape",
            "failure_code": "choice_count_invalid",
            "message": "OpenRouter response did not contain exactly one choice",
        }
        _write_json(call_dir / "result.json", result)
        return result
    if not content:
        result = {
            **base,
            "classification": "empty-content",
            "failure_code": "message_content_missing",
            "message": "OpenRouter returned no final message.content",
        }
        _write_json(call_dir / "result.json", result)
        return result
    try:
        decoded = json.loads(content)
    except json.JSONDecodeError:
        result = {
            **base,
            "classification": "invalid-json-content",
            "failure_code": "content_not_json",
            "message": "The final content was not JSON",
        }
        _write_json(call_dir / "result.json", result)
        return result

    try:
        validation = validate_candidate_selection(
            decoded,
            candidates,
            config=ranking,
            evidence_bundle_id=str(bundle["bundle_id"]),
            selection_schema=selection_schema,
        )
    except SelectorEnvelopeError as exc:
        result = {
            **base,
            "classification": "model-output-invalid",
            "failure_code": exc.code,
            "message": str(exc),
        }
        _write_json(call_dir / "result.json", result)
        return result
    if not validation.is_valid:
        result = {
            **base,
            "classification": "model-output-invalid",
            "failure_code": "candidate_selection_invalid",
            "message": "The candidate-ID envelope failed repository validation",
            "selector_validation": validation.as_dict(),
        }
        _write_json(call_dir / "result.json", result)
        return result

    selected_ids = list(validation.selected_candidate_ids)
    selection = {
        "evidence_bundle_id": bundle["bundle_id"],
        "selected_candidate_ids": selected_ids,
    }
    claim_plan = reconstruct_claim_plan(selection, candidates, config=ranking)
    plan_validation = validate_claim_plan(
        bundle,
        claim_plan,
        evidence_schema=evidence_schema,
        claim_plan_schema=claim_plan_schema,
    )
    if not plan_validation.is_valid:
        result = {
            **base,
            "classification": "reconstruction-invalid",
            "failure_code": "claim_plan_invalid",
            "message": "A valid selection reconstructed to an invalid claim plan",
            "selector_validation": validation.as_dict(),
        }
        _write_json(call_dir / "result.json", result)
        return result
    rendered = render_claim_plan(bundle, claim_plan, plan_validation)
    _write_json(call_dir / "selection.json", selection)
    _write_json(call_dir / "claim-plan.json", claim_plan)
    (call_dir / "rendered-report.md").write_bytes(rendered.markdown)
    result = {
        **base,
        "classification": "completed",
        "failure_code": None,
        "message": "The real candidate-ID request completed the repository boundary",
        "selected_candidate_ids": selected_ids,
        "selector_validation": validation.as_dict(),
        "claim_plan_sha256": content_sha256(claim_plan),
        "rendered_markdown_sha256": _sha256_bytes(rendered.markdown),
    }
    _write_json(call_dir / "result.json", result)
    return result


def execute_transport_calibration(
    *,
    repository_root: str | Path,
    prepared_dir: str | Path,
    output_dir: str | Path,
    api_key: str | None,
    config_path: str | Path = DEFAULT_CONFIG,
    trusted_main_sha: str | None = None,
    transport_factory: Callable[[], Transport] | None = None,
) -> dict[str, Any]:
    """Run discovery and exact-provider reproduction with at most three paid calls."""

    if not api_key:
        raise EvaluationIntegrityError("OPENROUTER_API_KEY is required for Phase 8")
    root = Path(repository_root).resolve()
    prepared = Path(prepared_dir).resolve()
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    plan = load_calibration_plan(root, config_path)
    manifest = _read_object(prepared / STAGE0_PREPARED_MANIFEST)
    if manifest.get("version") != STAGE0_PREPARED_VERSION:
        raise EvaluationIntegrityError("Phase 8 prepared manifest has the wrong version")
    if manifest.get("case_key") != plan.case_key:
        raise EvaluationIntegrityError("Phase 8 prepared case differs from the config")
    if manifest.get("candidate_count") != plan.expected_candidate_count:
        raise EvaluationIntegrityError("Phase 8 prepared candidate count drifted")
    paths = manifest.get("paths")
    if not isinstance(paths, Mapping):
        raise EvaluationIntegrityError("Phase 8 prepared manifest is missing paths")

    bundle = _read_object(prepared / str(paths["bundle"]))
    candidate_payload = _read_object(prepared / str(paths["candidates"]))
    candidates = candidate_payload.get("candidates")
    if not isinstance(candidates, list) or len(candidates) != plan.expected_candidate_count:
        raise EvaluationIntegrityError("Phase 8 candidate catalogue is incomplete")
    canonical_request = _read_object(prepared / str(paths["selector_request"]))
    compact_request = build_compact_candidate_selector_request(canonical_request)
    if content_sha256(compact_request) != manifest.get("compact_request_sha256"):
        raise EvaluationIntegrityError("Phase 8 compact request differs from preparation")

    prompt_template = (root / plan.selector_prompt).read_text(encoding="utf-8")
    selection_schema = _read_object(root / plan.selection_schema)
    provider_schema = project_openai_strict_schema(selection_schema)
    ranking = load_ranking_config(root, plan.ranking_config)
    evidence_schema = _read_object(root / "schemas/crypto-market-evidence-bundle-v1.json")
    claim_plan_schema = _read_object(root / "schemas/crypto-market-claim-plan-v1.json")
    ledger = _Ledger(plan)
    transport_builder = transport_factory or (lambda: UrllibTransport())
    calls: list[dict[str, Any]] = []
    operable: dict[str, Any] | None = None

    for model in plan.models:
        discovery = _call(
            root=root,
            output=output,
            plan=plan,
            model=model,
            stage="discovery",
            compact_request=compact_request,
            canonical_request=canonical_request,
            candidates=candidates,
            bundle=bundle,
            prompt_template=prompt_template,
            provider_schema=provider_schema,
            selection_schema=selection_schema,
            ranking=ranking,
            evidence_schema=evidence_schema,
            claim_plan_schema=claim_plan_schema,
            api_key=api_key,
            ledger=ledger,
            transport=transport_builder(),
            reproduction_provider_slug=None,
        )
        calls.append(discovery)
        if discovery.get("classification") != "completed":
            continue
        provider_slug = discovery.get("provider_slug")
        if not isinstance(provider_slug, str):
            raise EvaluationIntegrityError("completed discovery has no provider slug")
        reproduction = _call(
            root=root,
            output=output,
            plan=plan,
            model=model,
            stage="reproduction",
            compact_request=compact_request,
            canonical_request=canonical_request,
            candidates=candidates,
            bundle=bundle,
            prompt_template=prompt_template,
            provider_schema=provider_schema,
            selection_schema=selection_schema,
            ranking=ranking,
            evidence_schema=evidence_schema,
            claim_plan_schema=claim_plan_schema,
            api_key=api_key,
            ledger=ledger,
            transport=transport_builder(),
            reproduction_provider_slug=provider_slug,
        )
        calls.append(reproduction)
        if reproduction.get("classification") == "completed":
            operable = {
                "model": model.model,
                "provider_name": reproduction.get("actual_provider"),
                "provider_slug": provider_slug,
                "discovery_selected_candidate_ids": discovery.get(
                    "selected_candidate_ids", []
                ),
                "reproduction_selected_candidate_ids": reproduction.get(
                    "selected_candidate_ids", []
                ),
            }
        # A completed discovery consumes the only reproduction authority. Stop after it.
        break

    summary = {
        "version": CALIBRATION_VERSION,
        "trusted_main_sha": trusted_main_sha,
        "config_path": PurePosixPath(str(config_path)).as_posix(),
        "config_sha256": content_sha256(
            {
                "version": plan.version,
                "case_key": plan.case_key,
                "models": [item.model for item in plan.models],
                "max_output_tokens": plan.max_output_tokens,
                "reasoning_effort": plan.reasoning_effort,
                "maximum_call_cost_usd": plan.maximum_call_cost_usd,
                "maximum_total_cost_usd": plan.maximum_total_cost_usd,
            }
        ),
        "prepared_manifest_sha256": content_sha256(manifest),
        "case_key": plan.case_key,
        "candidate_count": len(candidates),
        "compact_request_id": manifest.get("compact_request_id"),
        "compact_request_bytes": manifest.get("compact_request_bytes"),
        "maximum_discovery_calls": plan.maximum_discovery_calls,
        "completed_discovery_calls": ledger.discovery_calls,
        "maximum_reproduction_calls": plan.maximum_reproduction_calls,
        "completed_reproduction_calls": ledger.reproduction_calls,
        "maximum_paid_calls": plan.maximum_paid_calls,
        "completed_paid_calls": ledger.calls,
        "maximum_call_cost_usd": plan.maximum_call_cost_usd,
        "maximum_total_cost_usd": plan.maximum_total_cost_usd,
        "observed_total_cost_usd": ledger.total_cost,
        "calls": calls,
        "decision_question": (
            "Can at least one model complete the real candidate-ID request under an "
            "observable, realistically configured route?"
        ),
        "decision_question_answered": operable is not None,
        "operable_route": operable,
        "quality_conclusion": None,
        "model_selector_enabled": False,
        "semantic_repairs": 0,
        "network_retries": 0,
        "automatic_generation": False,
        "publication": False,
        "repository_write": False,
    }
    _write_json(output / RESULTS_FILE, {"version": CALIBRATION_VERSION, "calls": calls})
    _write_json(output / SUMMARY_FILE, summary)
    (output / ACTIONS_SUMMARY).write_text(_summary_markdown(summary), encoding="utf-8")
    return summary
