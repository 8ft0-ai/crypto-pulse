"""Hardened protected entry point for the Phase 5 semantic claim-plan proof.

This module keeps the approved semantic benchmark unchanged while making the paid
route preflight use the repository's OpenAI strict-schema compatibility boundary.
It also distinguishes an infrastructure failure from a completed benchmark no-go
and preserves bounded, sanitised provider diagnostics in workflow artefacts.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Mapping

from .contracts import canonical_json_bytes
from .evaluation import (
    ACTIONS_SUMMARY,
    SUMMARY_JSON,
    EvaluationConfigurationError,
    EvaluationIntegrityError,
    _read_json,
    _write_json,
)
from .evaluation_viability import (
    STAGE_RESULTS_FILE,
    AttemptAuthenticationError,
    AttemptBillingError,
    AttemptHttpError,
    AttemptIneligibleRoutingError,
    AttemptTimeoutError,
    ProviderCapacityError,
    RateLimitedError,
)
from .generation_config import ConfigurationError, GenerationConfig, model_matches
from .openai_schema_projection import project_openai_strict_schema
from .openrouter_client import (
    CostLimitError,
    GenerationError,
    HttpResponse,
    IneligibleRoutingError,
    ProviderGenerationError,
    Transport,
    UrllibTransport,
    _check_selected_provider,
    _parse_json_bytes,
    _selected_provider,
)
from .semantic_plan_benchmark import (
    SEMANTIC_DECISION,
    SEMANTIC_SUMMARY,
    _decision_text,
    execute_semantic_plan_benchmark,
    prepare_semantic_plan_benchmark,
)

INFRASTRUCTURE_DECISION = "semantic-plan-infrastructure-failure"


def _sanitise_message(value: Any, api_key: str) -> str:
    message = " ".join(str(value or "OpenRouter request failed").split())[:500]
    if api_key:
        message = message.replace(api_key, "[REDACTED]")
    return message


def _error_payload(response: HttpResponse) -> tuple[str, str | None, str | None]:
    try:
        payload = json.loads(response.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        payload = {}
    error = payload.get("error") if isinstance(payload, Mapping) else None
    metadata = (
        error.get("metadata")
        if isinstance(error, Mapping) and isinstance(error.get("metadata"), Mapping)
        else {}
    )
    message = (
        error.get("message")
        if isinstance(error, Mapping) and isinstance(error.get("message"), str)
        else "OpenRouter request failed"
    )
    provider_code = metadata.get("provider_code")
    error_type = metadata.get("error_type")
    return (
        message,
        str(provider_code) if provider_code is not None else None,
        str(error_type) if error_type is not None else None,
    )


def _raise_route_http_error(response: HttpResponse, *, api_key: str) -> None:
    message, provider_code, error_type = _error_payload(response)
    message = _sanitise_message(message, api_key)
    common = {
        "status": response.status,
        "headers": response.headers,
        "provider_code": provider_code,
    }
    provider_status = provider_code or ""
    if response.status == 429 or provider_status == "429" or error_type == "rate_limit_exceeded":
        error: AttemptHttpError = RateLimitedError(message, **common)
    elif response.status in {408, 524} or provider_status in {"408", "524"}:
        error = AttemptTimeoutError(message, **common)
    elif response.status in {500, 502, 503, 504, 529} or provider_status in {
        "500",
        "502",
        "503",
        "504",
        "529",
    }:
        error = ProviderCapacityError(message, **common)
    elif response.status == 401:
        error = AttemptAuthenticationError(message, **common)
    elif response.status == 402:
        error = AttemptBillingError(message, **common)
    elif response.status in {403, 404}:
        error = AttemptIneligibleRoutingError(message, **common)
    else:
        error = AttemptHttpError(message, **common)
    setattr(error, "error_type", error_type)
    raise error


def projected_paid_route_probe(
    config: GenerationConfig,
    api_key: str,
    *,
    transport: Transport | None = None,
) -> Mapping[str, Any]:
    """Probe the exact paid route using the shared strict-schema projection."""

    canonical_schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["ok"],
        "properties": {"ok": {"const": True}},
    }
    provider_schema = project_openai_strict_schema(canonical_schema)
    body = canonical_json_bytes(
        {
            "model": config.model,
            "messages": [
                {
                    "role": "user",
                    "content": "Return exactly one JSON object with ok set to true.",
                }
            ],
            "temperature": 0,
            "max_tokens": 16,
            "stream": False,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "crypto_pulse_paid_route_probe",
                    "strict": True,
                    "schema": provider_schema,
                },
            },
            "provider": config.provider_policy.as_request(),
        }
    )
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": config.app_referer,
        "X-OpenRouter-Title": config.app_title,
        "X-OpenRouter-Metadata": "enabled",
    }
    response = (transport or UrllibTransport()).post(
        config.endpoint,
        headers=headers,
        body=body,
        timeout_seconds=config.timeout_seconds,
    )
    if not 200 <= response.status < 300:
        _raise_route_http_error(response, api_key=api_key)

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
    metadata = (
        payload.get("openrouter_metadata")
        if isinstance(payload.get("openrouter_metadata"), Mapping)
        else {}
    )
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
        raise CostLimitError(
            f"OpenRouter route probe cost {cost:.6f} USD exceeds configured limit"
        )
    return {
        "requested_model": config.model,
        "actual_model": actual_model,
        "actual_provider": provider,
        "generation_id": payload.get("id") if isinstance(payload.get("id"), str) else None,
        "estimated_cost_usd": cost,
    }


def _failure_details(exc: BaseException, api_key: str) -> dict[str, Any]:
    return {
        "failure_code": str(getattr(exc, "code", None) or "route_preflight_failure"),
        "http_status": getattr(exc, "status", None),
        "provider_code": getattr(exc, "provider_code", None),
        "error_type": getattr(exc, "error_type", None),
        "message": _sanitise_message(exc, api_key),
    }


def _patch_stage_results(output: Path, details: Mapping[str, Any]) -> None:
    path = output / STAGE_RESULTS_FILE
    payload = _read_json(path)
    stages = payload.get("stages")
    if not isinstance(stages, list):
        return
    for stage in stages:
        if (
            isinstance(stage, dict)
            and stage.get("stage") == "route_preflight"
            and stage.get("status") != "passed"
        ):
            for key in ("http_status", "provider_code", "error_type", "message"):
                stage[key] = details.get(key)
            break
    _write_json(path, payload)


def _rewrite_outputs(output: Path, summary: dict[str, Any]) -> None:
    _write_json(output / SEMANTIC_SUMMARY, summary)
    _write_json(output / SUMMARY_JSON, summary)
    decision = _decision_text(summary)
    infrastructure = summary.get("infrastructure_failure")
    if isinstance(infrastructure, Mapping):
        decision += (
            "\n## Execution status\n\n"
            f"- Completed corpus runs: `{summary.get('completed_corpus_runs')} / {summary.get('expected_corpus_runs')}`\n"
            f"- Failure stage: `{infrastructure.get('stage')}`\n"
            f"- Failure code: `{infrastructure.get('failure_code')}`\n"
            f"- HTTP status: `{infrastructure.get('http_status')}`\n"
            f"- Provider code: `{infrastructure.get('provider_code')}`\n"
            f"- Error type: `{infrastructure.get('error_type')}`\n"
            "- Model capability conclusion: `none`\n"
        )
    (output / SEMANTIC_DECISION).write_text(decision, encoding="utf-8")
    (output / ACTIONS_SUMMARY).write_text(decision, encoding="utf-8")


def execute_protected_semantic_plan_benchmark(
    *,
    repository_root: str | Path,
    profile_path: str | Path,
    viability_config_path: str | Path,
    prepared_dir: str | Path,
    output_dir: str | Path,
    api_key: str | None = None,
    trusted_main_sha: str | None = None,
    catalogue_loader: Any = None,
    key_status_loader: Any = None,
    route_transport: Transport | None = None,
    client_builder: Any = None,
    sleeper: Any = None,
    monotonic: Any = None,
    now: Any = None,
    jitter: Any = None,
) -> dict[str, Any]:
    """Execute the approved benchmark and harden only its protected boundary."""

    if not api_key:
        raise EvaluationIntegrityError("OPENROUTER_API_KEY is required for protected semantic benchmark")
    output = Path(output_dir)
    captured_failure: dict[str, Any] = {}

    def probe(config: GenerationConfig, secret: str) -> Mapping[str, Any]:
        try:
            return projected_paid_route_probe(config, secret, transport=route_transport)
        except BaseException as exc:
            captured_failure.update(_failure_details(exc, secret))
            raise

    summary = execute_semantic_plan_benchmark(
        repository_root=repository_root,
        profile_path=profile_path,
        viability_config_path=viability_config_path,
        prepared_dir=prepared_dir,
        output_dir=output,
        api_key=api_key,
        trusted_main_sha=trusted_main_sha,
        catalogue_loader=catalogue_loader,
        key_status_loader=key_status_loader,
        probe=probe,
        client_builder=client_builder,
        sleeper=sleeper,
        monotonic=monotonic,
        now=now,
        jitter=jitter,
    )
    expected = summary.get("expected_corpus_runs")
    completed = summary.get("completed_corpus_runs")
    route_failure = summary.get("route_failure")
    infrastructure_failed = bool(route_failure) or completed != expected
    if not infrastructure_failed:
        return summary

    details = dict(captured_failure)
    details.setdefault("failure_code", route_failure or "incomplete_corpus")
    details.setdefault("http_status", None)
    details.setdefault("provider_code", None)
    details.setdefault("error_type", None)
    details.setdefault(
        "message",
        "Route preflight failed" if route_failure else "The semantic corpus did not complete",
    )
    details["stage"] = "route_preflight" if route_failure else "semantic_corpus"
    summary["qualified"] = False
    summary["decision"] = INFRASTRUCTURE_DECISION
    summary["infrastructure_failure"] = details
    _patch_stage_results(output, details)
    _rewrite_outputs(output, summary)
    return summary


def decision_exit_code(summary: Mapping[str, Any]) -> int:
    return 3 if summary.get("decision") == INFRASTRUCTURE_DECISION else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare")
    prepare.add_argument("--repository-root", default=".")
    prepare.add_argument("--profile", default="config/llm-public-data-semantic-plan.yml")
    prepare.add_argument("--output-dir", required=True)
    run = sub.add_parser("run")
    run.add_argument("--repository-root", default=".")
    run.add_argument("--profile", default="config/llm-public-data-semantic-plan.yml")
    run.add_argument("--viability-config", default="config/llm-evaluation-viability.yml")
    run.add_argument("--prepared-dir", required=True)
    run.add_argument("--output-dir", required=True)
    run.add_argument("--trusted-main-sha")
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            plan, cases = prepare_semantic_plan_benchmark(
                repository_root=args.repository_root,
                profile_path=args.profile,
                output_dir=args.output_dir,
            )
            print(
                json.dumps(
                    {
                        "model": plan.model.model,
                        "cases": len(cases),
                        "runs_per_case": plan.runs_per_case,
                    },
                    sort_keys=True,
                )
            )
            return 0
        summary = execute_protected_semantic_plan_benchmark(
            repository_root=args.repository_root,
            profile_path=args.profile,
            viability_config_path=args.viability_config,
            prepared_dir=args.prepared_dir,
            output_dir=args.output_dir,
            api_key=os.environ.get("OPENROUTER_API_KEY"),
            trusted_main_sha=args.trusted_main_sha,
        )
        print(json.dumps({"decision": summary["decision"]}, sort_keys=True))
        return decision_exit_code(summary)
    except (
        EvaluationConfigurationError,
        EvaluationIntegrityError,
        ConfigurationError,
        GenerationError,
        OSError,
        RuntimeError,
        ValueError,
        TypeError,
    ) as exc:
        secret = os.environ.get("OPENROUTER_API_KEY", "")
        print(json.dumps({"error": _sanitise_message(exc, secret)}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
