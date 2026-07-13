"""Run one full semantic claim-plan contract call per shortlisted model."""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any, Mapping

import yaml

from .evaluation import ACTIONS_SUMMARY, PREPARED_MANIFEST, EvaluationConfigurationError, EvaluationIntegrityError, _catalogue, _read_json, _write_json
from .evaluation_viability import ATTEMPT_RECORDS_FILE, AttemptPacer, ClassifiedTransport, PacedClientFactory, load_viability_policy
from .generation_config import model_matches
from .openrouter_client import HttpResponse, OpenRouterClient, Transport, UrllibTransport, _selected_provider
from .paid_benchmark import check_paid_model_availability
from .semantic_plan_benchmark import _prepared_cases, _run_one, _validate_profile_chain, load_semantic_plan_profile
from .semantic_plan_model_evaluation import _runtime, _validated_classification_map
from .semantic_plan_model_selection_config import Candidate, load_expectations, load_selection_plan
from .semantic_plan_model_selection_scoring import evaluate_expectation
from .semantic_plan_protected_runner import projected_paid_route_probe

VERSION = "semantic-plan-model-calibration/v1"
SUMMARY_FILE = "model-calibration-summary.json"
DIAGNOSTICS_FILE = "provider-diagnostics.json"


def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise EvaluationConfigurationError(f"{path} must be an object")
    return value


def load_calibration_config(root: Path, path: str | Path) -> tuple[Any, dict[str, dict[str, Any]], str, float]:
    relative = str(path)
    if Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise EvaluationConfigurationError("calibration config path must be repository-relative")
    raw = _mapping(yaml.safe_load((root / relative).read_text(encoding="utf-8")), relative)
    if set(raw) != {"version", "base_selection_config", "smoke_case_key", "maximum_total_cost_usd", "candidates"} or raw.get("version") != 1:
        raise EvaluationConfigurationError("calibration config must use version 1 and exact supported keys")
    base = load_selection_plan(root, str(raw["base_selection_config"]))
    smoke_case_key = str(raw["smoke_case_key"])
    maximum_total_cost = float(raw["maximum_total_cost_usd"])
    if maximum_total_cost != 0.50:
        raise EvaluationConfigurationError("calibration whole-run ceiling must remain USD 0.50")
    overrides = _mapping(raw.get("candidates"), "candidates")
    if set(overrides) != {item.key for item in base.candidates}:
        raise EvaluationConfigurationError("calibration overrides must match the three shortlisted candidates")
    parsed: dict[str, dict[str, Any]] = {}
    for candidate in base.candidates:
        row = _mapping(overrides[candidate.key], f"candidates.{candidate.key}")
        if set(row) != {"maximum_generation_cost_usd", "maximum_model_cost_usd", "max_output_tokens"}:
            raise EvaluationConfigurationError(f"candidates.{candidate.key} has unsupported keys")
        generation_cap = float(row["maximum_generation_cost_usd"])
        model_cap = float(row["maximum_model_cost_usd"])
        max_output_tokens = int(row["max_output_tokens"])
        if generation_cap <= 0 or model_cap < generation_cap * 2:
            raise EvaluationConfigurationError(f"candidates.{candidate.key} cost ceilings are invalid")
        if not 16 <= max_output_tokens <= 16_384:
            raise EvaluationConfigurationError(f"candidates.{candidate.key}.max_output_tokens is invalid")
        parsed[candidate.key] = {
            "maximum_generation_cost_usd": generation_cap,
            "maximum_model_cost_usd": model_cap,
            "max_output_tokens": max_output_tokens,
        }
    if sum(row["maximum_model_cost_usd"] for row in parsed.values()) > maximum_total_cost + 1e-12:
        raise EvaluationConfigurationError("candidate ceilings exceed the whole calibration ceiling")
    return base, parsed, smoke_case_key, maximum_total_cost


class RequestTransform:
    def __init__(self, inner: Transport, *, send_temperature: bool) -> None:
        self.inner = inner
        self.send_temperature = send_temperature

    def post(self, url: str, *, headers: Mapping[str, str], body: bytes, timeout_seconds: float) -> HttpResponse:
        payload = json.loads(body.decode("utf-8"))
        if not isinstance(payload, dict):
            raise EvaluationIntegrityError("OpenRouter request body must be an object")
        if not self.send_temperature:
            payload.pop("temperature", None)
        body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return self.inner.post(url, headers=headers, body=body, timeout_seconds=timeout_seconds)


def _redact(value: Any, secret: str, limit: int = 1000) -> str:
    text = " ".join(str(value or "").split())[:limit]
    return text.replace(secret, "[REDACTED]") if secret else text


def _diagnostic(response: HttpResponse, secret: str) -> dict[str, Any]:
    try:
        payload = json.loads(response.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        payload = {}
    error = payload.get("error") if isinstance(payload, Mapping) else None
    metadata = error.get("metadata") if isinstance(error, Mapping) and isinstance(error.get("metadata"), Mapping) else {}
    usage = payload.get("usage") if isinstance(payload, Mapping) and isinstance(payload.get("usage"), Mapping) else {}
    choices = payload.get("choices") if isinstance(payload, Mapping) else None
    choice = choices[0] if isinstance(choices, list) and choices and isinstance(choices[0], Mapping) else {}
    router = payload.get("openrouter_metadata") if isinstance(payload, Mapping) and isinstance(payload.get("openrouter_metadata"), Mapping) else {}
    cost = usage.get("cost")
    return {
        "http_status": response.status,
        "generation_id": payload.get("id") if isinstance(payload, Mapping) else None,
        "actual_model": payload.get("model") if isinstance(payload, Mapping) else None,
        "actual_provider": _selected_provider(router),
        "finish_reason": choice.get("finish_reason"),
        "input_tokens": usage.get("prompt_tokens"),
        "output_tokens": usage.get("completion_tokens"),
        "total_tokens": usage.get("total_tokens"),
        "estimated_cost_usd": float(cost) if isinstance(cost, (int, float)) and not isinstance(cost, bool) else None,
        "error_code": error.get("code") if isinstance(error, Mapping) else None,
        "message": _redact(error.get("message"), secret, 500) if isinstance(error, Mapping) else None,
        "provider_name": _redact(metadata.get("provider_name"), secret, 240) or None,
        "provider_code": _redact(metadata.get("provider_code"), secret, 240) or None,
        "error_type": _redact(metadata.get("error_type"), secret, 240) or None,
        "provider_raw": _redact(metadata.get("raw"), secret, 1000) or None,
    }


class DiagnosticTransport:
    def __init__(self, inner: Transport, *, secret: str) -> None:
        self.inner = inner
        self.secret = secret
        self.records: list[dict[str, Any]] = []

    def post(self, url: str, *, headers: Mapping[str, str], body: bytes, timeout_seconds: float) -> HttpResponse:
        response = self.inner.post(url, headers=headers, body=body, timeout_seconds=timeout_seconds)
        self.records.append(_diagnostic(response, self.secret))
        return response


def _write_diagnostics(path: Path, records: list[dict[str, Any]]) -> None:
    if records:
        _write_json(path, {"responses": records})


def _summary_markdown(summary: Mapping[str, Any]) -> str:
    lines = [
        "# Semantic claim-plan route calibration",
        "",
        f"- Trusted main: `{summary.get('trusted_main_sha')}`",
        f"- Full-contract calls: `{summary.get('completed_substantive_generations')} / 3`",
        f"- Observed cost: `${float(summary.get('observed_total_cost_usd') or 0):.6f}`",
        "- Cost ceiling: `$0.50`",
        "- Deployment selection: `not performed`",
        "",
    ]
    for row in summary.get("models", []):
        lines.append(
            f"- `{row['model']}`: route `{row['route_status']}`, "
            f"full contract `{row['full_contract_status']}`, "
            f"scored `{'yes' if row['scored'] else 'no'}`"
        )
    return "\n".join(lines) + "\n"


def execute_calibration(
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
        raise EvaluationIntegrityError("OPENROUTER_API_KEY is required for model calibration")
    root = Path(repository_root).resolve()
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    base, overrides, smoke_case_key, maximum_total_cost = load_calibration_config(root, config_path)
    expectations = load_expectations(root, base.expectations_path)
    base_profile = load_semantic_plan_profile(root, base.base_profile)
    public_profile, base_plan, classifications = _validate_profile_chain(root, base_profile)
    classifications_by_case = _validated_classification_map(classifications)
    prepared_cases = _prepared_cases(base_plan, Path(prepared_dir))
    prepared = next((item for item in prepared_cases if item.key == smoke_case_key), None)
    manifest = _read_json(Path(prepared_dir) / PREPARED_MANIFEST)
    if prepared is None or not isinstance(manifest.get("semantic_model_selection"), Mapping):
        raise EvaluationIntegrityError("prepared model-selection corpus is invalid")
    if smoke_case_key not in expectations:
        raise EvaluationIntegrityError("calibration smoke case has no expectation contract")

    catalogue = (catalogue_loader or _catalogue)()
    pacer = AttemptPacer(load_viability_policy(root / base.viability_config))
    availability_rows: list[dict[str, Any]] = []
    route_rows: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    observed_cost = 0.0

    for index, original in enumerate(base.candidates, 1):
        override = overrides[original.key]
        candidate: Candidate = replace(
            original,
            repeats_per_case=1,
            maximum_generation_cost_usd=override["maximum_generation_cost_usd"],
            maximum_model_cost_usd=override["maximum_model_cost_usd"],
        )
        print(f"[calibration] model {index}/3 {candidate.model}: preparing", flush=True)
        profile, candidate_plan, runtime = _runtime(
            root, output, public_profile, base_profile, base_plan, candidate
        )
        runtime = replace(runtime, max_output_tokens=override["max_output_tokens"])
        _write_json(
            output / "runtime-configs" / f"{candidate.key}-calibration.json",
            {
                "model": runtime.model,
                "temperature_sent": candidate.send_temperature,
                "max_output_tokens": runtime.max_output_tokens,
                "max_cost_usd": runtime.max_cost_usd,
                "provider_policy": runtime.provider_policy.as_request(),
                "cross_model_fallback": runtime.cross_model_fallback,
            },
        )
        availability = check_paid_model_availability(candidate_plan, catalogue_loader=lambda: catalogue)
        availability_rows.append({
            "candidate": {**asdict(candidate), "max_output_tokens": override["max_output_tokens"]},
            "availability": asdict(availability.availability),
            "prompt_price_per_million": availability.prompt_price_per_million,
            "completion_price_per_million": availability.completion_price_per_million,
        })
        if not availability.availability.eligible:
            results.append({
                "model": candidate.model, "role": candidate.role,
                "route_status": "not_attempted", "full_contract_status": "not_attempted",
                "failure_code": availability.availability.reason, "scored": False,
                "semantic_coverage": None, "materiality": None, "restraint": None,
                "total_cost_usd": 0.0,
            })
            continue

        route_capture = DiagnosticTransport(UrllibTransport(), secret=api_key)
        try:
            route_result = pacer.call(
                f"calibration-route/{candidate.key}",
                lambda: projected_paid_route_probe(
                    runtime,
                    api_key,
                    transport=RequestTransform(route_capture, send_temperature=candidate.send_temperature),
                ),
            )
            route = {"model_key": candidate.key, "status": "passed", **dict(route_result)}
            route_cost = float(route_result.get("estimated_cost_usd") or 0.0)
            observed_cost += route_cost
        except Exception as exc:
            route = {
                "model_key": candidate.key, "requested_model": candidate.model,
                "status": "failed",
                "failure_code": str(getattr(exc, "code", None) or "route_preflight_failure"),
                "message": _redact(exc, api_key, 500),
            }
            route_cost = 0.0
        route_rows.append(route)
        _write_diagnostics(output / "route-diagnostics" / f"{candidate.key}.json", route_capture.records)
        print(f"[calibration] {candidate.model}: route {route['status']}", flush=True)
        if route["status"] != "passed":
            results.append({
                "model": candidate.model, "role": candidate.role,
                "route_status": "failed", "full_contract_status": "not_attempted",
                "failure_code": route.get("failure_code"), "scored": False,
                "semantic_coverage": None, "materiality": None, "restraint": None,
                "total_cost_usd": route_cost,
            })
            continue

        capture = DiagnosticTransport(UrllibTransport(), secret=api_key)
        transport = RequestTransform(ClassifiedTransport(capture), send_temperature=candidate.send_temperature)
        factory = PacedClientFactory(
            pacer,
            builder=lambda config, transport=transport: OpenRouterClient(config, transport=transport),
        )
        factory.set_logical_id(f"calibration/{candidate.key}/{prepared.key}/repeat-1")
        print(
            f"[calibration] {candidate.model}: full contract started "
            f"(max_output_tokens={override['max_output_tokens']})",
            flush=True,
        )
        record = _run_one(
            root=root, profile=profile, plan=candidate_plan, config=runtime,
            prepared=prepared, prepared_dir=Path(prepared_dir), repeat=1,
            classification=classifications_by_case[prepared.key], output=output,
            api_key=api_key, client_factory=factory,
        )
        response = capture.records[-1] if capture.records else {}
        generation_cost = record.estimated_cost_usd
        if generation_cost is None and isinstance(response.get("estimated_cost_usd"), (int, float)):
            generation_cost = float(response["estimated_cost_usd"])
        observed_cost += float(generation_cost or 0.0)
        run_dir = output / record.output_dir
        _write_diagnostics(run_dir / DIAGNOSTICS_FILE, capture.records)

        canonical = run_dir / "canonical-claim-plan.json"
        scored = canonical.exists()
        expectation = evaluate_expectation(_read_json(canonical), expectations[prepared.key]) if scored else None
        if expectation is not None:
            _write_json(run_dir / "case-expectation.json", asdict(expectation))
        passed = (
            record.status == "accepted" and expectation is not None and expectation.hard_pass
            and record.actual_model is not None and model_matches(candidate.model, record.actual_model)
            and bool(record.actual_provider) and record.cross_model_fallback_used is False
            and generation_cost is not None
        )
        results.append({
            "model": candidate.model, "role": candidate.role,
            "route_status": "passed",
            "full_contract_status": "passed" if passed else record.status,
            "failure_code": None if passed else record.failure_code,
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
            "total_cost_usd": route_cost + float(generation_cost or 0.0),
            "max_output_tokens": override["max_output_tokens"],
            "provider_diagnostics_retained": bool(capture.records),
            "output_dir": record.output_dir,
        })
        print(
            f"[calibration] {candidate.model}: full contract {record.status}"
            + (f" ({record.failure_code})" if record.failure_code else ""),
            flush=True,
        )

    _write_json(output / "model-availability.json", {"models": availability_rows})
    _write_json(output / "route-preflight.json", {"routes": route_rows})
    _write_json(output / ATTEMPT_RECORDS_FILE, {"attempts": [asdict(item) for item in pacer.records]})
    if observed_cost > maximum_total_cost + 1e-12:
        raise EvaluationIntegrityError("observed calibration cost exceeded the USD 0.50 ceiling")
    summary = {
        "version": VERSION, "trusted_main_sha": trusted_main_sha,
        "smoke_case_key": smoke_case_key,
        "maximum_substantive_generations": 3,
        "completed_substantive_generations": sum(
            row["full_contract_status"] != "not_attempted" for row in results
        ),
        "maximum_total_cost_usd": maximum_total_cost,
        "observed_total_cost_usd": observed_cost,
        "deployment_selection": False, "automatic_generation": False, "publication": False,
        "models": results,
    }
    _write_json(output / SUMMARY_FILE, summary)
    (output / ACTIONS_SUMMARY).write_text(_summary_markdown(summary), encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--config", default="config/semantic-plan-model-calibration.yml")
    parser.add_argument("--prepared-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--trusted-main-sha")
    args = parser.parse_args()
    try:
        result = execute_calibration(
            repository_root=args.repository_root, config_path=args.config,
            prepared_dir=args.prepared_dir, output_dir=args.output_dir,
            api_key=os.environ.get("OPENROUTER_API_KEY"),
            trusted_main_sha=args.trusted_main_sha,
        )
        print(json.dumps(result, sort_keys=True))
        return 0
    except (EvaluationConfigurationError, EvaluationIntegrityError, OSError, ValueError, TypeError) as exc:
        print(f"semantic model calibration failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
