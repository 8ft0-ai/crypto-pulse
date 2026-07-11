"""Compatibility runner for the GPT-4o mini public-data demo route probe."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Mapping

from . import public_demo_benchmark as base
from .contracts import canonical_json_bytes
from .evaluation import (
    ACTIONS_SUMMARY,
    DECISION_MARKDOWN,
    SUMMARY_JSON,
    EvaluationConfigurationError,
    EvaluationIntegrityError,
    _write_json,
)
from .evaluation_viability import ClassifiedTransport, STAGE_RESULTS_FILE
from .generation_config import ConfigurationError, GenerationConfig, model_matches
from .openrouter_client import (
    CostLimitError,
    IneligibleRoutingError,
    ProviderGenerationError,
    Transport,
    _check_selected_provider,
    _parse_json_bytes,
    _selected_provider,
)


def compatible_paid_route_probe(
    config: GenerationConfig,
    api_key: str,
    *,
    transport: Transport | None = None,
) -> Mapping[str, Any]:
    """Probe strict structured output using the smallest explicitly typed schema."""

    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["ok"],
        "properties": {"ok": {"type": "boolean"}},
    }
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
                    "name": "crypto_pulse_public_demo_route_probe",
                    "strict": True,
                    "schema": schema,
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
    response = ClassifiedTransport(transport).post(
        config.endpoint,
        headers=headers,
        body=body,
        timeout_seconds=config.timeout_seconds,
    )
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
        raise ProviderGenerationError("OpenRouter route probe returned JSON but not the required true result")
    metadata = payload.get("openrouter_metadata") if isinstance(payload.get("openrouter_metadata"), Mapping) else {}
    provider = _selected_provider(metadata)
    _check_selected_provider(config, provider)
    if provider is None:
        raise ProviderGenerationError("OpenRouter route probe did not identify the actual provider")
    usage = payload.get("usage") if isinstance(payload.get("usage"), Mapping) else {}
    cost_raw = usage.get("cost")
    if isinstance(cost_raw, bool) or not isinstance(cost_raw, (int, float)):
        raise CostLimitError("OpenRouter public-demo route probe did not report usage.cost")
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


def safe_provider_diagnostic(exc: BaseException, api_key: str | None) -> str:
    """Return a bounded single-line diagnostic with secrets removed."""

    message = " ".join(str(exc).split())[:500] or exc.__class__.__name__
    if api_key:
        message = message.replace(api_key, "[REDACTED]")
    return message.replace("`", "'")


def _record_route_diagnostic(summary: dict[str, Any], output_dir: str | Path, message: str) -> None:
    stages = summary.get("viability", {}).get("stages", [])
    for stage in stages:
        if isinstance(stage, dict) and stage.get("stage") == "route_preflight" and stage.get("status") == "failed":
            details = stage.get("details")
            if not isinstance(details, dict):
                details = {}
                stage["details"] = details
            details["safe_provider_message"] = message
            break

    output = Path(output_dir)
    _write_json(output / SUMMARY_JSON, summary)
    _write_json(output / STAGE_RESULTS_FILE, {"stages": stages})
    addition = (
        "\n\n## Route preflight diagnostic\n\n"
        f"- Safe provider message: `{message}`\n"
        "- Raw response body and request secrets retained: `false`\n"
    )
    for filename in (DECISION_MARKDOWN, ACTIONS_SUMMARY):
        path = output / filename
        if path.is_file():
            path.write_text(path.read_text(encoding="utf-8") + addition, encoding="utf-8")


def execute_public_demo_compat(**kwargs: Any) -> dict[str, Any]:
    """Run the public demo with the compatible route probe and safe diagnostics."""

    diagnostic: dict[str, str] = {}
    api_key = kwargs.get("api_key")
    original_probe = base.paid_route_probe

    def probe(config: GenerationConfig, secret: str) -> Mapping[str, Any]:
        try:
            return compatible_paid_route_probe(config, secret)
        except BaseException as exc:
            diagnostic["message"] = safe_provider_diagnostic(exc, secret)
            raise

    base.paid_route_probe = probe
    try:
        summary = base.execute_public_demo(**kwargs)
    finally:
        base.paid_route_probe = original_probe

    if diagnostic:
        _record_route_diagnostic(summary, kwargs["output_dir"], diagnostic["message"])
    if api_key:
        serialized = json.dumps(summary, sort_keys=True)
        if api_key in serialized:
            raise EvaluationIntegrityError("public demo summary retained the API key")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare")
    prepare.add_argument("--repository-root", default=".")
    prepare.add_argument("--profile", default="config/llm-public-data-demo.yml")
    prepare.add_argument("--output-dir", required=True)
    run = sub.add_parser("run")
    run.add_argument("--repository-root", default=".")
    run.add_argument("--profile", default="config/llm-public-data-demo.yml")
    run.add_argument("--viability-config", default="config/llm-evaluation-viability.yml")
    run.add_argument("--prepared-dir", required=True)
    run.add_argument("--output-dir", required=True)
    run.add_argument("--trusted-main-sha")
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            plan, cases = base.prepare_public_demo(
                repository_root=args.repository_root,
                profile_path=args.profile,
                output_dir=args.output_dir,
            )
            print(
                json.dumps(
                    {
                        "model": plan.model.model,
                        "cases": len(cases),
                        "maximum_logical_calls": plan.maximum_logical_calls,
                    },
                    sort_keys=True,
                )
            )
        else:
            summary = execute_public_demo_compat(
                repository_root=args.repository_root,
                profile_path=args.profile,
                viability_config_path=args.viability_config,
                prepared_dir=args.prepared_dir,
                output_dir=args.output_dir,
                api_key=os.environ.get("OPENROUTER_API_KEY"),
                trusted_main_sha=args.trusted_main_sha,
            )
            print(json.dumps(summary["decision"], sort_keys=True))
        return 0
    except (EvaluationConfigurationError, EvaluationIntegrityError, ConfigurationError, OSError, ValueError, TypeError) as exc:
        secret = os.environ.get("OPENROUTER_API_KEY", "")
        message = safe_provider_diagnostic(exc, secret)
        print(f"public demo compatibility benchmark failed: {message}", file=os.sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
