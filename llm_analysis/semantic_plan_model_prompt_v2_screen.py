"""Run reviewed semantic claim-plan compatibility screens using prompt v2."""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass, replace
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

import yaml

from .contracts import canonical_json_bytes
from .evaluation import (
    ACTIONS_SUMMARY,
    PREPARED_MANIFEST,
    EvaluationConfigurationError,
    EvaluationIntegrityError,
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
from .openrouter_client import HttpResponse, OpenRouterClient, Transport, UrllibTransport
from .paid_benchmark import check_paid_model_availability
from .semantic_plan_benchmark import (
    _prepared_cases,
    _run_one,
    _validate_profile_chain,
    load_semantic_plan_profile,
)
from .semantic_plan_model_calibration import DiagnosticTransport, _redact, _write_diagnostics
from .semantic_plan_model_catalogue_screen import _catalogue_reasoning_failure
from .semantic_plan_model_evaluation import _runtime, _validated_classification_map
from .semantic_plan_model_final_calibration import (
    DIAGNOSTICS_FILE,
    EXECUTION_MESSAGE,
    _prepare_normalised_case,
)
from .semantic_plan_model_selection_config import Candidate, load_expectations, load_selection_plan
from .semantic_plan_model_selection_scoring import evaluate_validated_expectation
from .semantic_plan_protected_runner import projected_paid_route_probe

PROMPT_V2_PATH = "prompts/crypto-market-claim-plan-v2.md"
PROMPT_V2_VERSION = "crypto-market-claim-plan/v2"
SUMMARY_FILE = "model-prompt-v2-screen-summary.json"
REQUEST_TRANSFORMS_FILE = "request-transforms.json"

_REVIEWED_PLANS: dict[str, dict[str, Any]] = {
    "semantic-plan-model-corrective-screen/v1": {
        "models": (
            "openai/gpt-5.6-luna",
            "deepseek/deepseek-v4-flash",
            "qwen/qwen3.6-flash",
        ),
        "maximum_total_cost_usd": 0.10,
        "excluded_models": (
            "xiaomi/mimo-v2.5-pro",
            "bytedance-seed/seed-2.0-mini",
        ),
    },
    "semantic-plan-model-final-calibration/v2": {
        "models": ("openai/gpt-5.6-sol", "nex-agi/nex-n2-mini"),
        "maximum_total_cost_usd": 0.25,
        "excluded_models": ("minimax/minimax-m3",),
    },
}
_ALLOWED_EFFORTS = {"max", "xhigh", "high", "medium", "low", "minimal", "none"}


@dataclass(frozen=True)
class PromptV2ScreenPlan:
    plan_id: str
    base_selection_config: str
    smoke_case_key: str
    maximum_total_cost_usd: float
    candidates: tuple[Candidate, ...]
    overrides: Mapping[str, Mapping[str, Any]]
    excluded_models: tuple[Mapping[str, str], ...]


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


def _number(value: Any, path: str, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EvaluationConfigurationError(f"{path} must be numeric")
    result = float(value)
    if not minimum <= result <= maximum:
        raise EvaluationConfigurationError(f"{path} must be between {minimum} and {maximum}")
    return result


def _checked_date(value: Any, path: str) -> str:
    text = _string(value, path)
    try:
        date.fromisoformat(text)
    except ValueError as exc:
        raise EvaluationConfigurationError(f"{path} must be YYYY-MM-DD") from exc
    return text


def load_prompt_v2_screen_plan(root: Path, path: str | Path) -> PromptV2ScreenPlan:
    relative = _relative(str(path), "config_path")
    raw = _mapping(yaml.safe_load((root / relative).read_text(encoding="utf-8")), relative)
    expected_top = {
        "version",
        "plan_id",
        "prompt",
        "base_selection_config",
        "smoke_case_key",
        "maximum_total_cost_usd",
        "candidates",
        "excluded_models",
    }
    if set(raw) != expected_top or raw.get("version") != 1:
        raise EvaluationConfigurationError("prompt-v2 screen config must use version 1 and exact keys")
    plan_id = _string(raw.get("plan_id"), "plan_id")
    reviewed = _REVIEWED_PLANS.get(plan_id)
    if reviewed is None:
        raise EvaluationConfigurationError("plan_id is not an approved prompt-v2 screen")
    prompt = _mapping(raw.get("prompt"), "prompt")
    if set(prompt) != {"path", "version"}:
        raise EvaluationConfigurationError("prompt must contain exact path and version keys")
    if prompt.get("path") != PROMPT_V2_PATH or prompt.get("version") != PROMPT_V2_VERSION:
        raise EvaluationConfigurationError("screen must use the immutable prompt-v2 contract")
    base_selection_config = _relative(raw.get("base_selection_config"), "base_selection_config")
    load_selection_plan(root, base_selection_config)
    maximum_total = _number(raw.get("maximum_total_cost_usd"), "maximum_total_cost_usd", 0.01, 0.25)
    if maximum_total != reviewed["maximum_total_cost_usd"]:
        raise EvaluationConfigurationError("whole-run ceiling differs from the reviewed plan")

    rows = raw.get("candidates")
    expected_models = reviewed["models"]
    if not isinstance(rows, list) or len(rows) != len(expected_models):
        raise EvaluationConfigurationError("candidate count differs from the reviewed plan")
    candidate_keys = {
        "key",
        "model",
        "role",
        "deployment_eligible",
        "availability_checked_at",
        "known_expiration_date",
        "maximum_prompt_price_per_million",
        "maximum_completion_price_per_million",
        "maximum_generation_cost_usd",
        "maximum_model_cost_usd",
        "send_temperature",
        "max_output_tokens",
        "route_probe_max_output_tokens",
        "ensure_user_message",
        "reasoning",
    }
    candidates: list[Candidate] = []
    overrides: dict[str, dict[str, Any]] = {}
    for index, raw_candidate in enumerate(rows):
        row = _mapping(raw_candidate, f"candidates[{index}]")
        if set(row) != candidate_keys:
            raise EvaluationConfigurationError(f"candidates[{index}] has unsupported keys")
        model = _string(row.get("model"), f"candidates[{index}].model")
        if model != expected_models[index]:
            raise EvaluationConfigurationError("candidate order and exact model slugs are fixed")
        key = _string(row.get("key"), f"candidates[{index}].key")
        role = _string(row.get("role"), f"candidates[{index}].role")
        deployment = row.get("deployment_eligible")
        send_temperature = row.get("send_temperature")
        ensure_user_message = row.get("ensure_user_message")
        if not all(isinstance(value, bool) for value in (deployment, send_temperature, ensure_user_message)):
            raise EvaluationConfigurationError(f"candidates[{index}] booleans are invalid")
        generation_cap = _number(row.get("maximum_generation_cost_usd"), "maximum_generation_cost_usd", 0.000001, 0.15)
        model_cap = _number(row.get("maximum_model_cost_usd"), "maximum_model_cost_usd", 0.000001, 0.20)
        if model_cap <= generation_cap:
            raise EvaluationConfigurationError("model ceiling must exceed generation ceiling")
        max_output = row.get("max_output_tokens")
        route_output = row.get("route_probe_max_output_tokens")
        if isinstance(max_output, bool) or not isinstance(max_output, int) or not 4000 <= max_output <= 16384:
            raise EvaluationConfigurationError("max_output_tokens must be between 4000 and 16384")
        if isinstance(route_output, bool) or not isinstance(route_output, int) or not 32 <= route_output <= 1024:
            raise EvaluationConfigurationError("route_probe_max_output_tokens must be between 32 and 1024")
        reasoning_raw = row.get("reasoning")
        reasoning: dict[str, Any] | None
        if reasoning_raw is None:
            reasoning = None
        else:
            parsed = _mapping(reasoning_raw, f"candidates[{index}].reasoning")
            if set(parsed) != {"enabled", "effort", "exclude"}:
                raise EvaluationConfigurationError("reasoning must use exact enabled, effort and exclude keys")
            enabled = parsed.get("enabled")
            effort = parsed.get("effort")
            if not isinstance(enabled, bool) or parsed.get("exclude") is not True:
                raise EvaluationConfigurationError("reasoning booleans are invalid")
            if effort is not None and effort not in _ALLOWED_EFFORTS:
                raise EvaluationConfigurationError("reasoning effort is unsupported")
            if effort == "none" and enabled is not False:
                raise EvaluationConfigurationError("reasoning effort none must disable reasoning")
            if effort not in (None, "none") and enabled is not True:
                raise EvaluationConfigurationError("configured reasoning effort must enable reasoning")
            if effort is None and enabled is not False:
                raise EvaluationConfigurationError("omitted reasoning effort must explicitly disable reasoning")
            reasoning = {"enabled": enabled, "effort": effort, "exclude": True}
        expiration = row.get("known_expiration_date")
        if expiration is not None:
            expiration = _checked_date(expiration, "known_expiration_date")
        candidate = Candidate(
            key=key,
            model=model,
            role=role,
            deployment_eligible=deployment,
            repeats_per_case=1,
            availability_checked_at=_checked_date(row.get("availability_checked_at"), "availability_checked_at"),
            known_expiration_date=expiration,
            maximum_prompt_price_per_million=_number(row.get("maximum_prompt_price_per_million"), "maximum_prompt_price_per_million", 0.000001, 10),
            maximum_completion_price_per_million=_number(row.get("maximum_completion_price_per_million"), "maximum_completion_price_per_million", 0.000001, 40),
            maximum_generation_cost_usd=generation_cap,
            maximum_model_cost_usd=model_cap,
            send_temperature=send_temperature,
        )
        candidates.append(candidate)
        overrides[key] = {
            "max_output_tokens": max_output,
            "route_probe_max_output_tokens": route_output,
            "ensure_user_message": ensure_user_message,
            "reasoning": reasoning,
        }

    excluded_rows = raw.get("excluded_models")
    if not isinstance(excluded_rows, list):
        raise EvaluationConfigurationError("excluded_models must be a list")
    excluded: list[Mapping[str, str]] = []
    excluded_models: list[str] = []
    for index, item in enumerate(excluded_rows):
        row = _mapping(item, f"excluded_models[{index}]")
        if set(row) != {"model", "reason"}:
            raise EvaluationConfigurationError("excluded model rows must contain model and reason")
        model = _string(row.get("model"), "excluded model")
        reason = _string(row.get("reason"), "excluded reason")
        excluded.append({"model": model, "reason": reason})
        excluded_models.append(model)
    if tuple(excluded_models) != reviewed["excluded_models"]:
        raise EvaluationConfigurationError("excluded models differ from the reviewed plan")
    if sum(item.maximum_model_cost_usd for item in candidates) > maximum_total + 1e-12:
        raise EvaluationConfigurationError("candidate ceilings exceed the whole-run ceiling")
    return PromptV2ScreenPlan(
        plan_id=plan_id,
        base_selection_config=base_selection_config,
        smoke_case_key=_string(raw.get("smoke_case_key"), "smoke_case_key"),
        maximum_total_cost_usd=maximum_total,
        candidates=tuple(candidates),
        overrides=overrides,
        excluded_models=tuple(excluded),
    )


class PromptV2RequestTransform:
    """Apply reviewed message, sampling, reasoning and route-envelope transforms."""

    def __init__(
        self,
        inner: Transport,
        *,
        send_temperature: bool,
        ensure_user_message: bool,
        reasoning: Mapping[str, Any] | None,
        max_output_tokens: int | None = None,
    ) -> None:
        self.inner = inner
        self.send_temperature = send_temperature
        self.ensure_user_message = ensure_user_message
        self.reasoning = dict(reasoning) if reasoning is not None else None
        self.max_output_tokens = max_output_tokens

    def post(self, url: str, *, headers: Mapping[str, str], body: bytes, timeout_seconds: float) -> HttpResponse:
        payload = json.loads(body.decode("utf-8"))
        if not isinstance(payload, dict):
            raise EvaluationIntegrityError("OpenRouter request body must be an object")
        if not self.send_temperature:
            payload.pop("temperature", None)
        messages = payload.get("messages")
        if not isinstance(messages, list) or not all(isinstance(item, Mapping) for item in messages):
            raise EvaluationIntegrityError("OpenRouter request messages must be an array of objects")
        if self.ensure_user_message and not any(item.get("role") == "user" for item in messages):
            messages.append({"role": "user", "content": EXECUTION_MESSAGE})
        if self.reasoning is not None:
            effort = self.reasoning.get("effort")
            if effort is None:
                payload["reasoning"] = {"enabled": False, "exclude": True}
            else:
                payload["reasoning"] = {"effort": effort, "exclude": True}
        if self.max_output_tokens is not None:
            payload["max_tokens"] = self.max_output_tokens
            if "max_completion_tokens" in payload:
                payload["max_completion_tokens"] = self.max_output_tokens
        return self.inner.post(
            url,
            headers=headers,
            body=canonical_json_bytes(payload),
            timeout_seconds=timeout_seconds,
        )


def _summary_markdown(summary: Mapping[str, Any]) -> str:
    lines = [
        "# Prompt-v2 semantic claim-plan compatibility screen",
        "",
        f"- Plan: `{summary.get('plan_id')}`",
        f"- Prompt: `{summary.get('prompt_version')}`",
        f"- Trusted main: `{summary.get('trusted_main_sha')}`",
        f"- Full-contract calls: `{summary.get('completed_substantive_generations')} / {summary.get('maximum_substantive_generations')}`",
        f"- Observed cost: `${float(summary.get('observed_total_cost_usd') or 0):.6f}`",
        f"- Cost ceiling: `${float(summary.get('maximum_total_cost_usd') or 0):.2f}`",
        "- Deployment selection: `not performed`",
        "- Quality leaderboard: `not produced`",
        "",
    ]
    for row in summary.get("models", []):
        lines.append(
            f"- `{row['model']}`: route `{row['route_status']}`, full contract `{row['full_contract_status']}`, "
            f"validator accepted `{'yes' if row['validator_accepted'] else 'no'}`, "
            f"screen passed `{'yes' if row['screen_passed'] else 'no'}`, scored `{'yes' if row['scored'] else 'no'}`"
        )
    return "\n".join(lines) + "\n"


def execute_prompt_v2_screen(
    *,
    repository_root: str | Path,
    config_path: str | Path,
    prepared_dir: str | Path,
    output_dir: str | Path,
    api_key: str | None,
    trusted_main_sha: str | None = None,
    catalogue_loader: Any = None,
) -> dict[str, Any]:
    if not api_key:
        raise EvaluationIntegrityError("OPENROUTER_API_KEY is required for prompt-v2 screening")
    root = Path(repository_root).resolve()
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    plan = load_prompt_v2_screen_plan(root, config_path)
    base = load_selection_plan(root, plan.base_selection_config)
    expectations = load_expectations(root, base.expectations_path)
    base_profile = load_semantic_plan_profile(root, base.base_profile)
    base_profile = replace(
        base_profile,
        prompt_path=PROMPT_V2_PATH,
        prompt_version=PROMPT_V2_VERSION,
    )
    public_profile, base_plan, classifications = _validate_profile_chain(root, base_profile)
    classifications_by_case = _validated_classification_map(classifications)
    prepared_root = Path(prepared_dir)
    prepared_cases = _prepared_cases(base_plan, prepared_root)
    prepared = next((item for item in prepared_cases if item.key == plan.smoke_case_key), None)
    manifest = _read_json(prepared_root / PREPARED_MANIFEST)
    if prepared is None or not isinstance(manifest.get("semantic_model_selection"), Mapping):
        raise EvaluationIntegrityError("prepared model-selection corpus is invalid")
    if plan.smoke_case_key not in expectations:
        raise EvaluationIntegrityError("screen smoke case has no expectation contract")
    normalised_root, normalised_prepared = _prepare_normalised_case(prepared_root, prepared, output)

    catalogue = (catalogue_loader or _catalogue)()
    rows = catalogue.get("data")
    if not isinstance(rows, list):
        raise EvaluationIntegrityError("OpenRouter model catalogue is missing data[]")
    catalogue_by_model = {
        str(item.get("id")): item
        for item in rows
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    }
    pacer = AttemptPacer(load_viability_policy(root / base.viability_config))
    availability_rows: list[dict[str, Any]] = []
    route_rows: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    transform_rows: list[dict[str, Any]] = []
    observed_cost = 0.0

    for index, candidate in enumerate(plan.candidates, 1):
        override = plan.overrides[candidate.key]
        if observed_cost + candidate.maximum_model_cost_usd > plan.maximum_total_cost_usd + 1e-12:
            raise EvaluationIntegrityError(f"whole-run ceiling cannot cover {candidate.model}")
        print(f"[prompt-v2-screen] model {index}/{len(plan.candidates)} {candidate.model}: preparing", flush=True)
        profile, candidate_plan, runtime = _runtime(
            root, output, public_profile, base_profile, base_plan, candidate
        )
        runtime = replace(runtime, max_output_tokens=override["max_output_tokens"])
        transform_record = {
            "model_key": candidate.key,
            "model": candidate.model,
            "prompt_path": profile.prompt_path,
            "prompt_version": profile.prompt_version,
            "temperature_sent": candidate.send_temperature,
            "ensure_user_message": override["ensure_user_message"],
            "reasoning": override["reasoning"],
            "route_probe_max_output_tokens": override["route_probe_max_output_tokens"],
            "max_output_tokens": override["max_output_tokens"],
        }
        transform_rows.append(transform_record)
        _write_json(
            output / "runtime-configs" / f"{candidate.key}-prompt-v2-screen.json",
            {
                **transform_record,
                "max_cost_usd": runtime.max_cost_usd,
                "provider_policy": runtime.provider_policy.as_request(),
                "cross_model_fallback": runtime.cross_model_fallback,
            },
        )
        availability = check_paid_model_availability(candidate_plan, catalogue_loader=lambda: catalogue)
        catalogue_row = catalogue_by_model.get(candidate.model)
        reasoning_failure = None
        if override["reasoning"] is not None:
            reasoning_failure = _catalogue_reasoning_failure(
                catalogue_row if isinstance(catalogue_row, Mapping) else None,
                override["reasoning"],
            )
        availability_rows.append(
            {
                "candidate": {**asdict(candidate), **transform_record},
                "availability": asdict(availability.availability),
                "prompt_price_per_million": availability.prompt_price_per_million,
                "completion_price_per_million": availability.completion_price_per_million,
                "reasoning_compatible": reasoning_failure is None,
                "reasoning_failure": reasoning_failure,
            }
        )
        base_result = {
            "model": candidate.model,
            "role": candidate.role,
            "validator_accepted": False,
            "expectation_hard_pass": False,
            "screen_passed": False,
            "scored": False,
            "semantic_coverage": None,
            "materiality": None,
            "restraint": None,
            **transform_record,
        }
        if not availability.availability.eligible or reasoning_failure is not None:
            results.append(
                {
                    **base_result,
                    "route_status": "not_attempted",
                    "full_contract_status": "not_attempted",
                    "failure_code": availability.availability.reason or reasoning_failure,
                    "total_cost_usd": 0.0,
                }
            )
            continue

        route_capture = DiagnosticTransport(UrllibTransport(), secret=api_key)
        try:
            route_result = pacer.call(
                f"prompt-v2-screen-route/{candidate.key}",
                lambda: projected_paid_route_probe(
                    runtime,
                    api_key,
                    transport=PromptV2RequestTransform(
                        route_capture,
                        send_temperature=candidate.send_temperature,
                        ensure_user_message=override["ensure_user_message"],
                        reasoning=override["reasoning"],
                        max_output_tokens=override["route_probe_max_output_tokens"],
                    ),
                ),
            )
            route = {"model_key": candidate.key, "status": "passed", **dict(route_result)}
            route_cost = float(route_result.get("estimated_cost_usd") or 0.0)
        except Exception as exc:
            route = {
                "model_key": candidate.key,
                "requested_model": candidate.model,
                "status": "failed",
                "failure_code": str(getattr(exc, "code", None) or "route_preflight_failure"),
                "message": _redact(exc, api_key, 500),
            }
            response = route_capture.records[-1] if route_capture.records else {}
            route_cost = float(response.get("estimated_cost_usd") or 0.0)
        observed_cost += route_cost
        route_rows.append(route)
        _write_diagnostics(output / "route-diagnostics" / f"{candidate.key}.json", route_capture.records)
        print(f"[prompt-v2-screen] {candidate.model}: route {route['status']}", flush=True)
        if route_cost > candidate.maximum_model_cost_usd + 1e-12:
            raise EvaluationIntegrityError(f"{candidate.model} route exceeded its model ceiling")
        if route["status"] != "passed":
            results.append(
                {
                    **base_result,
                    "route_status": "failed",
                    "full_contract_status": "not_attempted",
                    "failure_code": route.get("failure_code"),
                    "route_cost_usd": route_cost,
                    "total_cost_usd": route_cost,
                }
            )
            continue

        capture = DiagnosticTransport(UrllibTransport(), secret=api_key)
        transport = PromptV2RequestTransform(
            ClassifiedTransport(capture),
            send_temperature=candidate.send_temperature,
            ensure_user_message=override["ensure_user_message"],
            reasoning=override["reasoning"],
        )
        factory = PacedClientFactory(
            pacer,
            builder=lambda config, transport=transport: OpenRouterClient(config, transport=transport),
        )
        factory.set_logical_id(
            f"prompt-v2-screen/{candidate.key}/{normalised_prepared.key}/repeat-1"
        )
        print(
            f"[prompt-v2-screen] {candidate.model}: full contract started "
            f"(max_output_tokens={override['max_output_tokens']})",
            flush=True,
        )
        record = _run_one(
            root=root,
            profile=profile,
            plan=candidate_plan,
            config=runtime,
            prepared=normalised_prepared,
            prepared_dir=normalised_root,
            repeat=1,
            classification=classifications_by_case[normalised_prepared.key],
            output=output,
            api_key=api_key,
            client_factory=factory,
        )
        response = capture.records[-1] if capture.records else {}
        generation_cost = record.estimated_cost_usd
        if generation_cost is None and isinstance(response.get("estimated_cost_usd"), (int, float)):
            generation_cost = float(response["estimated_cost_usd"])
        observed_cost += float(generation_cost or 0.0)
        run_dir = output / record.output_dir
        _write_diagnostics(run_dir / DIAGNOSTICS_FILE, capture.records)
        canonical = run_dir / "canonical-claim-plan.json"
        validator_accepted = record.status == "accepted" and record.plan_valid and canonical.exists()
        expectation = evaluate_validated_expectation(
            _read_json(canonical) if canonical.exists() else None,
            expectations[normalised_prepared.key],
            validator_accepted=validator_accepted,
        )
        if expectation is not None:
            _write_json(run_dir / "case-expectation.json", asdict(expectation))
        expectation_hard_pass = bool(expectation and expectation.hard_pass)
        identity_ok = (
            record.actual_model is not None
            and model_matches(candidate.model, record.actual_model)
            and bool(record.actual_provider)
            and record.cross_model_fallback_used is False
        )
        screen_passed = validator_accepted and expectation_hard_pass and identity_ok and generation_cost is not None
        if screen_passed:
            failure_code = None
        elif not validator_accepted:
            failure_code = record.failure_code or "validator_rejected"
        elif not expectation_hard_pass:
            failure_code = "expectation_failure"
        elif not identity_ok:
            failure_code = "identity_or_routing_failure"
        else:
            failure_code = "cost_metadata_missing"
        model_cost = route_cost + float(generation_cost or 0.0)
        if model_cost > candidate.maximum_model_cost_usd + 1e-12:
            raise EvaluationIntegrityError(f"{candidate.model} exceeded its model ceiling")
        results.append(
            {
                **base_result,
                "route_status": "passed",
                "full_contract_status": "passed" if screen_passed else record.status,
                "failure_code": failure_code,
                "validator_accepted": validator_accepted,
                "expectation_hard_pass": expectation_hard_pass,
                "screen_passed": screen_passed,
                "scored": expectation is not None,
                "semantic_coverage": expectation.semantic_coverage if expectation else None,
                "materiality": expectation.materiality if expectation else None,
                "restraint": expectation.restraint if expectation else None,
                "actual_model": record.actual_model or response.get("actual_model"),
                "actual_provider": record.actual_provider or response.get("actual_provider"),
                "finish_reason": response.get("finish_reason"),
                "input_tokens": record.input_tokens or response.get("input_tokens"),
                "output_tokens": record.output_tokens or response.get("output_tokens"),
                "latency_ms": record.latency_ms,
                "route_cost_usd": route_cost,
                "generation_cost_usd": generation_cost,
                "total_cost_usd": model_cost,
                "provider_diagnostics_retained": bool(capture.records),
                "output_dir": record.output_dir,
            }
        )
        print(
            f"[prompt-v2-screen] {candidate.model}: full contract {record.status}"
            + (f" ({record.failure_code})" if record.failure_code else ""),
            flush=True,
        )

    _write_json(output / "model-availability.json", {"models": availability_rows})
    _write_json(output / "route-preflight.json", {"routes": route_rows})
    _write_json(output / REQUEST_TRANSFORMS_FILE, {"models": transform_rows})
    _write_json(output / "excluded-models.json", {"models": list(plan.excluded_models)})
    _write_json(output / ATTEMPT_RECORDS_FILE, {"attempts": [asdict(item) for item in pacer.records]})
    if observed_cost > plan.maximum_total_cost_usd + 1e-12:
        raise EvaluationIntegrityError("observed screen cost exceeded the whole-run ceiling")
    summary = {
        "version": "semantic-plan-model-prompt-v2-screen/v1",
        "plan_id": plan.plan_id,
        "prompt_path": PROMPT_V2_PATH,
        "prompt_version": PROMPT_V2_VERSION,
        "trusted_main_sha": trusted_main_sha,
        "smoke_case_key": plan.smoke_case_key,
        "normalised_bundle_id": normalised_prepared.bundle_id,
        "maximum_route_probes": len(plan.candidates),
        "maximum_substantive_generations": len(plan.candidates),
        "completed_substantive_generations": sum(
            row["full_contract_status"] != "not_attempted" for row in results
        ),
        "maximum_total_cost_usd": plan.maximum_total_cost_usd,
        "observed_total_cost_usd": observed_cost,
        "excluded_models": list(plan.excluded_models),
        "deployment_selection": False,
        "quality_leaderboard": False,
        "automatic_generation": False,
        "publication": False,
        "models": results,
    }
    _write_json(output / SUMMARY_FILE, summary)
    (output / ACTIONS_SUMMARY).write_text(_summary_markdown(summary), encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--config", required=True)
    parser.add_argument("--prepared-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--trusted-main-sha")
    args = parser.parse_args()
    try:
        result = execute_prompt_v2_screen(
            repository_root=args.repository_root,
            config_path=args.config,
            prepared_dir=args.prepared_dir,
            output_dir=args.output_dir,
            api_key=os.environ.get("OPENROUTER_API_KEY"),
            trusted_main_sha=args.trusted_main_sha,
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
        print(f"prompt-v2 semantic model screen failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
