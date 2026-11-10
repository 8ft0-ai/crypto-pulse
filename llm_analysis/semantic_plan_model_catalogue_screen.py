"""Run a bounded five-model semantic claim-plan catalogue compatibility screen."""
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
from .semantic_plan_model_calibration import (
    DiagnosticTransport,
    _redact,
    _write_diagnostics,
)
from .semantic_plan_model_evaluation import _runtime, _validated_classification_map
from .semantic_plan_model_final_calibration import (
    DIAGNOSTICS_FILE,
    EXECUTION_MESSAGE,
    _prepare_normalised_case,
)
from .semantic_plan_model_selection_config import (
    Candidate,
    SelectionPlan,
    load_expectations,
    load_selection_plan,
)
from .semantic_plan_model_selection_scoring import evaluate_validated_expectation
from .semantic_plan_protected_runner import projected_paid_route_probe

VERSION = "semantic-plan-model-catalogue-screen/v1"
SUMMARY_FILE = "model-catalogue-screen-summary.json"
REQUEST_TRANSFORMS_FILE = "request-transforms.json"
EXPECTED_MODELS = (
    ("deepseek-v4-flash", "deepseek/deepseek-v4-flash"),
    ("gpt-5-6-luna", "openai/gpt-5.6-luna"),
    ("qwen3-6-flash", "qwen/qwen3.6-flash"),
    ("mimo-v2-5-pro", "xiaomi/mimo-v2.5-pro"),
    ("seed-2-0-mini", "bytedance-seed/seed-2.0-mini"),
)
_ALLOWED_EFFORTS = {"max", "xhigh", "high", "medium", "low", "minimal", "none"}


@dataclass(frozen=True)
class CatalogueScreenPlan:
    plan_id: str
    base: SelectionPlan
    smoke_case_key: str
    maximum_total_cost_usd: float
    candidates: tuple[Candidate, ...]
    overrides: Mapping[str, Mapping[str, Any]]


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


def load_catalogue_screen_config(root: Path, path: str | Path) -> CatalogueScreenPlan:
    relative = _relative(str(path), "config_path")
    raw = _mapping(yaml.safe_load((root / relative).read_text(encoding="utf-8")), relative)
    expected_top = {
        "version",
        "plan_id",
        "base_selection_config",
        "smoke_case_key",
        "maximum_total_cost_usd",
        "candidates",
    }
    if set(raw) != expected_top or raw.get("version") != 1:
        raise EvaluationConfigurationError(
            "catalogue screen config must use version 1 and exact supported keys"
        )
    plan_id = _string(raw.get("plan_id"), "plan_id")
    if plan_id != VERSION:
        raise EvaluationConfigurationError(f"plan_id must be {VERSION}")
    base = load_selection_plan(
        root, _relative(raw.get("base_selection_config"), "base_selection_config")
    )
    smoke_case = _string(raw.get("smoke_case_key"), "smoke_case_key")
    maximum_total_cost = _number(
        raw.get("maximum_total_cost_usd"), "maximum_total_cost_usd", 0.01, 0.15
    )
    if maximum_total_cost != 0.15:
        raise EvaluationConfigurationError(
            "catalogue screen whole-run ceiling must remain USD 0.15"
        )
    rows = raw.get("candidates")
    if not isinstance(rows, list) or len(rows) != len(EXPECTED_MODELS):
        raise EvaluationConfigurationError(
            "catalogue screen must contain exactly five candidates"
        )

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
        "ensure_user_message",
        "reasoning",
    }
    candidates: list[Candidate] = []
    overrides: dict[str, dict[str, Any]] = {}
    seen_keys: set[str] = set()
    seen_models: set[str] = set()

    for index, raw_candidate in enumerate(rows):
        row = _mapping(raw_candidate, f"candidates[{index}]")
        if set(row) != candidate_keys:
            raise EvaluationConfigurationError(
                f"candidates[{index}] must use exact supported keys"
            )
        key = _string(row.get("key"), f"candidates[{index}].key")
        model = _string(row.get("model"), f"candidates[{index}].model")
        expected_key, expected_model = EXPECTED_MODELS[index]
        if (key, model) != (expected_key, expected_model):
            raise EvaluationConfigurationError(
                "catalogue screen candidate order and exact model slugs are fixed"
            )
        if key in seen_keys or model in seen_models:
            raise EvaluationConfigurationError(
                "catalogue screen candidate keys and models must be unique"
            )
        if row.get("role") != "catalogue_candidate" or row.get("deployment_eligible") is not True:
            raise EvaluationConfigurationError(
                f"candidates[{index}] must be a deployment-eligible catalogue_candidate"
            )
        send_temperature = row.get("send_temperature")
        ensure_user_message = row.get("ensure_user_message")
        if not isinstance(send_temperature, bool) or not isinstance(ensure_user_message, bool):
            raise EvaluationConfigurationError(f"candidates[{index}] booleans are invalid")
        generation_cap = _number(
            row.get("maximum_generation_cost_usd"),
            f"candidates[{index}].maximum_generation_cost_usd",
            0.000001,
            0.05,
        )
        model_cap = _number(
            row.get("maximum_model_cost_usd"),
            f"candidates[{index}].maximum_model_cost_usd",
            0.000001,
            0.06,
        )
        if model_cap <= generation_cap:
            raise EvaluationConfigurationError(
                f"candidates[{index}] model ceiling must exceed the generation ceiling"
            )
        max_output_tokens = row.get("max_output_tokens")
        if (
            isinstance(max_output_tokens, bool)
            or not isinstance(max_output_tokens, int)
            or not 16 <= max_output_tokens <= 16_384
        ):
            raise EvaluationConfigurationError(
                f"candidates[{index}].max_output_tokens is invalid"
            )
        reasoning = _mapping(row.get("reasoning"), f"candidates[{index}].reasoning")
        if set(reasoning) != {"enabled", "effort", "exclude"}:
            raise EvaluationConfigurationError(
                f"candidates[{index}].reasoning must use exact supported keys"
            )
        enabled = reasoning.get("enabled")
        effort = reasoning.get("effort")
        exclude = reasoning.get("exclude")
        if not isinstance(enabled, bool) or exclude is not True:
            raise EvaluationConfigurationError(
                f"candidates[{index}].reasoning booleans are invalid"
            )
        if effort is not None and effort not in _ALLOWED_EFFORTS:
            raise EvaluationConfigurationError(
                f"candidates[{index}].reasoning.effort is unsupported"
            )
        if effort == "none" and enabled is not False:
            raise EvaluationConfigurationError(
                f"candidates[{index}] effort none must disable reasoning"
            )
        if effort not in (None, "none") and enabled is not True:
            raise EvaluationConfigurationError(
                f"candidates[{index}] configured effort must enable reasoning"
            )
        if effort is None and enabled is not False:
            raise EvaluationConfigurationError(
                f"candidates[{index}] omitted effort must explicitly disable reasoning"
            )
        known_expiration = row.get("known_expiration_date")
        if known_expiration is not None:
            known_expiration = _checked_date(
                known_expiration, f"candidates[{index}].known_expiration_date"
            )
        candidate = Candidate(
            key=key,
            model=model,
            role="catalogue_candidate",
            deployment_eligible=True,
            repeats_per_case=1,
            availability_checked_at=_checked_date(
                row.get("availability_checked_at"),
                f"candidates[{index}].availability_checked_at",
            ),
            known_expiration_date=known_expiration,
            maximum_prompt_price_per_million=_number(
                row.get("maximum_prompt_price_per_million"),
                f"candidates[{index}].maximum_prompt_price_per_million",
                0.000001,
                10.0,
            ),
            maximum_completion_price_per_million=_number(
                row.get("maximum_completion_price_per_million"),
                f"candidates[{index}].maximum_completion_price_per_million",
                0.000001,
                10.0,
            ),
            maximum_generation_cost_usd=generation_cap,
            maximum_model_cost_usd=model_cap,
            send_temperature=send_temperature,
        )
        candidates.append(candidate)
        overrides[key] = {
            "max_output_tokens": max_output_tokens,
            "ensure_user_message": ensure_user_message,
            "reasoning": {
                "enabled": enabled,
                "effort": effort,
                "exclude": True,
            },
        }
        seen_keys.add(key)
        seen_models.add(model)

    expected_policies = {
        "deepseek-v4-flash": (True, "high", True, True),
        "gpt-5-6-luna": (False, "none", False, False),
        "qwen3-6-flash": (False, None, True, True),
        "mimo-v2-5-pro": (False, None, True, True),
        "seed-2-0-mini": (True, "minimal", True, True),
    }
    for candidate in candidates:
        override = overrides[candidate.key]
        reasoning = override["reasoning"]
        actual = (
            reasoning["enabled"],
            reasoning["effort"],
            override["ensure_user_message"],
            candidate.send_temperature,
        )
        if actual != expected_policies[candidate.key]:
            raise EvaluationConfigurationError(
                f"{candidate.key} request compatibility policy is not the reviewed policy"
            )

    if sum(item.maximum_model_cost_usd for item in candidates) > maximum_total_cost + 1e-12:
        raise EvaluationConfigurationError(
            "catalogue candidate ceilings exceed the whole-run ceiling"
        )
    return CatalogueScreenPlan(
        plan_id=plan_id,
        base=base,
        smoke_case_key=smoke_case,
        maximum_total_cost_usd=maximum_total_cost,
        candidates=tuple(candidates),
        overrides=overrides,
    )


def _catalogue_reasoning_failure(
    catalogue_row: Mapping[str, Any] | None,
    reasoning: Mapping[str, Any],
) -> str | None:
    if not isinstance(catalogue_row, Mapping):
        return "catalogue model record is missing"
    supported_parameters = catalogue_row.get("supported_parameters")
    if not isinstance(supported_parameters, list) or "reasoning" not in supported_parameters:
        return "catalogue does not advertise the reasoning request parameter"
    metadata = catalogue_row.get("reasoning")
    if not isinstance(metadata, Mapping):
        return "catalogue does not expose reasoning compatibility metadata"
    enabled = bool(reasoning.get("enabled"))
    effort = reasoning.get("effort")
    if metadata.get("mandatory") is True and not enabled:
        return "catalogue reports mandatory reasoning but the reviewed plan disables it"
    supported_efforts = metadata.get("supported_efforts")
    if effort is not None:
        if not isinstance(supported_efforts, list) or effort not in supported_efforts:
            return f"catalogue does not advertise reviewed reasoning effort {effort}"
    return None


class CatalogueRequestTransform:
    """Apply the checked message, sampling and reasoning policy for one candidate."""

    def __init__(
        self,
        inner: Transport,
        *,
        send_temperature: bool,
        ensure_user_message: bool,
        reasoning: Mapping[str, Any],
    ) -> None:
        self.inner = inner
        self.send_temperature = send_temperature
        self.ensure_user_message = ensure_user_message
        self.reasoning = dict(reasoning)

    def post(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        body: bytes,
        timeout_seconds: float,
    ) -> HttpResponse:
        payload = json.loads(body.decode("utf-8"))
        if not isinstance(payload, dict):
            raise EvaluationIntegrityError("OpenRouter request body must be an object")
        if not self.send_temperature:
            payload.pop("temperature", None)
        messages = payload.get("messages")
        if not isinstance(messages, list) or not all(isinstance(item, Mapping) for item in messages):
            raise EvaluationIntegrityError(
                "OpenRouter request messages must be an array of objects"
            )
        if self.ensure_user_message and not any(item.get("role") == "user" for item in messages):
            messages.append({"role": "user", "content": EXECUTION_MESSAGE})
        effort = self.reasoning.get("effort")
        if effort is None:
            payload["reasoning"] = {
                "enabled": bool(self.reasoning.get("enabled")),
                "exclude": True,
            }
        else:
            payload["reasoning"] = {"effort": effort, "exclude": True}
        return self.inner.post(
            url,
            headers=headers,
            body=canonical_json_bytes(payload),
            timeout_seconds=timeout_seconds,
        )


def _summary_markdown(summary: Mapping[str, Any]) -> str:
    maximum = int(summary.get("maximum_substantive_generations") or 0)
    lines = [
        "# Five-model semantic claim-plan catalogue screen",
        "",
        f"- Plan: `{summary.get('plan_id')}`",
        f"- Trusted main: `{summary.get('trusted_main_sha')}`",
        f"- Full-contract calls: `{summary.get('completed_substantive_generations')} / {maximum}`",
        f"- Observed cost: `${float(summary.get('observed_total_cost_usd') or 0):.6f}`",
        f"- Cost ceiling: `${float(summary.get('maximum_total_cost_usd') or 0):.2f}`",
        "- Deployment selection: `not performed`",
        "- Quality leaderboard: `not produced`",
        "",
    ]
    for row in summary.get("models", []):
        lines.append(
            f"- `{row['model']}`: route `{row['route_status']}`, "
            f"full contract `{row['full_contract_status']}`, "
            f"validator accepted `{'yes' if row['validator_accepted'] else 'no'}`, "
            f"expectation passed `{'yes' if row['expectation_hard_pass'] else 'no'}`, "
            f"screen passed `{'yes' if row['screen_passed'] else 'no'}`, "
            f"scored `{'yes' if row['scored'] else 'no'}`"
        )
    return "\n".join(lines) + "\n"


def execute_catalogue_screen(
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
        raise EvaluationIntegrityError(
            "OPENROUTER_API_KEY is required for catalogue screening"
        )
    root = Path(repository_root).resolve()
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    plan = load_catalogue_screen_config(root, config_path)
    expectations = load_expectations(root, plan.base.expectations_path)
    base_profile = load_semantic_plan_profile(root, plan.base.base_profile)
    public_profile, base_plan, classifications = _validate_profile_chain(root, base_profile)
    classifications_by_case = _validated_classification_map(classifications)
    prepared_root = Path(prepared_dir)
    prepared_cases = _prepared_cases(base_plan, prepared_root)
    prepared = next(
        (item for item in prepared_cases if item.key == plan.smoke_case_key), None
    )
    manifest = _read_json(prepared_root / PREPARED_MANIFEST)
    if prepared is None or not isinstance(manifest.get("semantic_model_selection"), Mapping):
        raise EvaluationIntegrityError("prepared model-selection corpus is invalid")
    if plan.smoke_case_key not in expectations:
        raise EvaluationIntegrityError(
            "catalogue screen smoke case has no expectation contract"
        )
    normalised_root, normalised_prepared = _prepare_normalised_case(
        prepared_root, prepared, output
    )

    catalogue = (catalogue_loader or _catalogue)()
    catalogue_rows = catalogue.get("data")
    if not isinstance(catalogue_rows, list):
        raise EvaluationIntegrityError("OpenRouter model catalogue is missing data[]")
    catalogue_by_model = {
        str(item.get("id")): item
        for item in catalogue_rows
        if isinstance(item, Mapping) and isinstance(item.get("id"), str)
    }
    pacer = AttemptPacer(load_viability_policy(root / plan.base.viability_config))
    availability_rows: list[dict[str, Any]] = []
    route_rows: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    transform_rows: list[dict[str, Any]] = []
    observed_cost = 0.0

    for index, candidate in enumerate(plan.candidates, 1):
        override = plan.overrides[candidate.key]
        if observed_cost + candidate.maximum_model_cost_usd > plan.maximum_total_cost_usd + 1e-12:
            raise EvaluationIntegrityError(
                f"whole-run ceiling cannot cover {candidate.model}"
            )
        print(
            f"[catalogue-screen] model {index}/{len(plan.candidates)} "
            f"{candidate.model}: preparing",
            flush=True,
        )
        profile, candidate_plan, runtime = _runtime(
            root, output, public_profile, base_profile, base_plan, candidate
        )
        runtime = replace(runtime, max_output_tokens=override["max_output_tokens"])
        transform_record = {
            "model_key": candidate.key,
            "model": candidate.model,
            "temperature_sent": candidate.send_temperature,
            "ensure_user_message": override["ensure_user_message"],
            "reasoning": dict(override["reasoning"]),
            "max_output_tokens": runtime.max_output_tokens,
        }
        transform_rows.append(transform_record)
        _write_json(
            output / "runtime-configs" / f"{candidate.key}-catalogue-screen.json",
            {
                **transform_record,
                "max_cost_usd": runtime.max_cost_usd,
                "provider_policy": runtime.provider_policy.as_request(),
                "cross_model_fallback": runtime.cross_model_fallback,
            },
        )

        availability = check_paid_model_availability(
            candidate_plan, catalogue_loader=lambda: catalogue
        )
        catalogue_row = catalogue_by_model.get(candidate.model)
        reasoning_failure = _catalogue_reasoning_failure(
            catalogue_row if isinstance(catalogue_row, Mapping) else None,
            override["reasoning"],
        )
        availability_rows.append(
            {
                "candidate": {
                    **asdict(candidate),
                    "max_output_tokens": override["max_output_tokens"],
                    "ensure_user_message": override["ensure_user_message"],
                    "reasoning": dict(override["reasoning"]),
                },
                "availability": asdict(availability.availability),
                "prompt_price_per_million": availability.prompt_price_per_million,
                "completion_price_per_million": availability.completion_price_per_million,
                "context_length": availability.context_length,
                "maximum_completion_tokens": availability.maximum_completion_tokens,
                "supported_parameters": sorted(
                    str(item)
                    for item in (
                        catalogue_row.get("supported_parameters", [])
                        if isinstance(catalogue_row, Mapping)
                        else []
                    )
                ),
                "catalogue_reasoning": (
                    dict(catalogue_row["reasoning"])
                    if isinstance(catalogue_row, Mapping)
                    and isinstance(catalogue_row.get("reasoning"), Mapping)
                    else None
                ),
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
            "reasoning": dict(override["reasoning"]),
            "user_message_added": override["ensure_user_message"],
            "temperature_sent": candidate.send_temperature,
            "max_output_tokens": override["max_output_tokens"],
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
        route_transform = CatalogueRequestTransform(
            route_capture,
            send_temperature=candidate.send_temperature,
            ensure_user_message=override["ensure_user_message"],
            reasoning=override["reasoning"],
        )
        try:
            route_result = pacer.call(
                f"catalogue-screen-route/{candidate.key}",
                lambda: projected_paid_route_probe(
                    runtime, api_key, transport=route_transform
                ),
            )
            route = {"model_key": candidate.key, "status": "passed", **dict(route_result)}
            route_cost = float(route_result.get("estimated_cost_usd") or 0.0)
            observed_cost += route_cost
        except Exception as exc:
            route = {
                "model_key": candidate.key,
                "requested_model": candidate.model,
                "status": "failed",
                "failure_code": str(
                    getattr(exc, "code", None) or "route_preflight_failure"
                ),
                "message": _redact(exc, api_key, 500),
            }
            route_response = route_capture.records[-1] if route_capture.records else {}
            route_cost = (
                float(route_response["estimated_cost_usd"])
                if isinstance(route_response.get("estimated_cost_usd"), (int, float))
                else 0.0
            )
            observed_cost += route_cost
        route_rows.append(route)
        _write_diagnostics(
            output / "route-diagnostics" / f"{candidate.key}.json",
            route_capture.records,
        )
        print(
            f"[catalogue-screen] {candidate.model}: route {route['status']}",
            flush=True,
        )
        if route_cost > candidate.maximum_model_cost_usd + 1e-12:
            raise EvaluationIntegrityError(
                f"{candidate.model} route exceeded its model ceiling"
            )
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
        if observed_cost + candidate.maximum_generation_cost_usd > plan.maximum_total_cost_usd + 1e-12:
            raise EvaluationIntegrityError(
                f"whole-run ceiling cannot cover the full call for {candidate.model}"
            )

        capture = DiagnosticTransport(UrllibTransport(), secret=api_key)
        transport = CatalogueRequestTransform(
            ClassifiedTransport(capture),
            send_temperature=candidate.send_temperature,
            ensure_user_message=override["ensure_user_message"],
            reasoning=override["reasoning"],
        )
        factory = PacedClientFactory(
            pacer,
            builder=lambda config, transport=transport: OpenRouterClient(
                config, transport=transport
            ),
        )
        factory.set_logical_id(
            f"catalogue-screen/{candidate.key}/{normalised_prepared.key}/repeat-1"
        )
        print(
            f"[catalogue-screen] {candidate.model}: full contract started "
            f"(max_output_tokens={override['max_output_tokens']}, "
            f"reasoning={override['reasoning']})",
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
        if generation_cost is None and isinstance(
            response.get("estimated_cost_usd"), (int, float)
        ):
            generation_cost = float(response["estimated_cost_usd"])
        observed_cost += float(generation_cost or 0.0)
        run_dir = output / record.output_dir
        _write_diagnostics(run_dir / DIAGNOSTICS_FILE, capture.records)

        canonical = run_dir / "canonical-claim-plan.json"
        validator_accepted = (
            record.status == "accepted" and record.plan_valid and canonical.exists()
        )
        expectation = evaluate_validated_expectation(
            _read_json(canonical) if canonical.exists() else None,
            expectations[normalised_prepared.key],
            validator_accepted=validator_accepted,
        )
        scored = expectation is not None
        if expectation is not None:
            _write_json(run_dir / "case-expectation.json", asdict(expectation))
        expectation_hard_pass = bool(expectation and expectation.hard_pass)
        identity_ok = (
            record.actual_model is not None
            and model_matches(candidate.model, record.actual_model)
            and bool(record.actual_provider)
            and record.cross_model_fallback_used is False
        )
        screen_passed = (
            validator_accepted
            and expectation_hard_pass
            and identity_ok
            and generation_cost is not None
        )
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
            raise EvaluationIntegrityError(
                f"{candidate.model} exceeded its catalogue screen model ceiling"
            )
        results.append(
            {
                **base_result,
                "route_status": "passed",
                "full_contract_status": "passed" if screen_passed else record.status,
                "failure_code": failure_code,
                "validator_accepted": validator_accepted,
                "expectation_hard_pass": expectation_hard_pass,
                "screen_passed": screen_passed,
                "scored": scored,
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
            f"[catalogue-screen] {candidate.model}: full contract {record.status}"
            + (f" ({record.failure_code})" if record.failure_code else ""),
            flush=True,
        )

    _write_json(output / "model-availability.json", {"models": availability_rows})
    _write_json(output / "route-preflight.json", {"routes": route_rows})
    _write_json(output / REQUEST_TRANSFORMS_FILE, {"models": transform_rows})
    _write_json(
        output / ATTEMPT_RECORDS_FILE,
        {"attempts": [asdict(item) for item in pacer.records]},
    )
    if observed_cost > plan.maximum_total_cost_usd + 1e-12:
        raise EvaluationIntegrityError(
            "observed catalogue screen cost exceeded the USD 0.15 ceiling"
        )
    summary = {
        "version": VERSION,
        "plan_id": plan.plan_id,
        "trusted_main_sha": trusted_main_sha,
        "smoke_case_key": plan.smoke_case_key,
        "normalised_bundle_id": normalised_prepared.bundle_id,
        "maximum_substantive_generations": len(plan.candidates),
        "completed_substantive_generations": sum(
            row["full_contract_status"] != "not_attempted" for row in results
        ),
        "maximum_total_cost_usd": plan.maximum_total_cost_usd,
        "observed_total_cost_usd": observed_cost,
        "deployment_selection": False,
        "quality_leaderboard": False,
        "automatic_generation": False,
        "publication": False,
        "models": results,
    }
    _write_json(output / SUMMARY_FILE, summary)
    (output / ACTIONS_SUMMARY).write_text(
        _summary_markdown(summary), encoding="utf-8"
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", default=".")
    parser.add_argument(
        "--config", default="config/semantic-plan-model-catalogue-screen.yml"
    )
    parser.add_argument("--prepared-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--trusted-main-sha")
    args = parser.parse_args()
    try:
        result = execute_catalogue_screen(
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
        print(f"semantic model catalogue screen failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
