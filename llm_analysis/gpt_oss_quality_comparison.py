"""Protected two-stage Phase 9 GPT-OSS candidate-selection comparison."""
from __future__ import annotations

import csv
import hashlib
import json
import time
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Mapping, Sequence

from .candidate_selection_contract import (
    SelectorEnvelopeError,
    render_candidate_selector_prompt,
    validate_candidate_selection,
)
from .candidate_selection_model_comparison import prepare_candidate_selection_comparison
from .candidate_selector_compact_projection import build_compact_candidate_selector_request
from .claim_candidate_gold_corpus import evaluate_claim_candidate_gold_corpus
from .claim_plan_render import render_claim_plan
from .claim_plan_validation import validate_claim_plan
from .contracts import canonical_json_bytes, content_sha256
from .deterministic_ranking import load_ranking_config
from .deterministic_reconstruction import reconstruct_claim_plan
from .evaluation import EvaluationIntegrityError, _catalogue, _read_json, _write_json
from .generation_config import model_matches
from .gpt_oss_quality_comparison_config import (
    DEFAULT_CONFIG,
    FROZEN_CASE_ORDER,
    PHASE9_CONFIG_VERSION,
    Phase9Plan,
    load_phase9_plan,
)
from .gpt_oss_quality_comparison_scoring import (
    score_counts,
    summarize_complete_corpus,
    summarize_partial,
)
from .openai_schema_projection import project_openai_strict_schema
from .openrouter_client import HttpResponse, Transport, UrllibTransport, _selected_provider

PHASE9_VERSION = "phase-09-gpt-oss-quality-comparison/v1"
PREPARED_VERSION = "phase-09-gpt-oss-quality-comparison-prepared/v1"
PREPARED_MANIFEST = "gpt-oss-quality-comparison-prepared.json"
SUMMARY_FILE = "gpt-oss-quality-comparison-summary.json"
RECORDS_FILE = "gpt-oss-quality-comparison-records.json"
AVAILABILITY_FILE = "gpt-oss-quality-comparison-availability.json"
REVIEWER_CSV = "gpt-oss-quality-comparison-reviewer.csv"
ADDITIONS_CSV = "gpt-oss-quality-comparison-additions-losses.csv"
DECISION_INPUT = "decision-input.md"
ACTIONS_SUMMARY = "actions-summary.md"
REQUIRED_CATALOGUE_PARAMETERS = frozenset({"response_format", "structured_outputs"})


class Phase9ExecutionError(EvaluationIntegrityError):
    """A fail-closed Phase 9 execution error."""


class _Ledger:
    def __init__(self, plan: Phase9Plan) -> None:
        self.plan = plan
        self.calls = 0
        self.total_cost = 0.0

    def before_call(self) -> None:
        if self.calls >= self.plan.maximum_paid_calls:
            raise Phase9ExecutionError("Phase 9 paid-call ceiling would be exceeded")
        if self.total_cost + self.plan.maximum_call_cost_usd > self.plan.maximum_total_cost_usd + 1e-12:
            raise Phase9ExecutionError("Phase 9 total cost reservation would be exceeded")
        self.calls += 1

    def charge(self, cost: float) -> None:
        if cost < 0:
            raise Phase9ExecutionError("provider cost must not be negative")
        self.total_cost += cost
        if self.total_cost > self.plan.maximum_total_cost_usd + 1e-12:
            raise Phase9ExecutionError("observed Phase 9 cost exceeded the whole-run ceiling")


def _object(path: Path) -> dict[str, Any]:
    value = _read_json(path)
    if not isinstance(value, dict):
        raise Phase9ExecutionError(f"{path} must contain a JSON object")
    return value


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _provider_slug(value: str | None) -> str | None:
    if value is None:
        return None
    normalised = "".join(character for character in value.lower() if character.isalnum())
    return "deepinfra" if normalised == "deepinfra" else None


def _safe_headers(headers: Mapping[str, str]) -> dict[str, str]:
    allowed = {"content-type", "x-request-id", "cf-ray", "x-openrouter-request-id"}
    return {
        str(key).lower(): str(value)
        for key, value in headers.items()
        if str(key).lower() in allowed
    }


def _planned_schedule() -> list[dict[str, Any]]:
    return [
        {
            "stage": "A" if repeat_index == 1 else "B",
            "case_key": case_key,
            "repeat_index": repeat_index,
            "planned_order": (repeat_index - 1) * len(FROZEN_CASE_ORDER) + case_index + 1,
        }
        for repeat_index in (1, 2, 3)
        for case_index, case_key in enumerate(FROZEN_CASE_ORDER)
    ]


def _verify_baseline(plan: Phase9Plan, overall: Mapping[str, Any]) -> None:
    actual = {
        "selected_count": int(overall.get("selected_count", -1)),
        "selected_useful_count": int(overall.get("selected_useful_count", -1)),
        "gold_useful_count": int(overall.get("gold_useful_count", -1)),
        "precision": float(overall.get("selected_useful_precision", -1)),
        "recall": float(overall.get("selected_useful_recall", -1)),
    }
    actual["f1"] = 0.0 if actual["precision"] + actual["recall"] == 0 else (
        2 * actual["precision"] * actual["recall"] / (actual["precision"] + actual["recall"])
    )
    expected = asdict(plan.baseline_reference)
    for key in ("selected_count", "selected_useful_count", "gold_useful_count"):
        if actual[key] != expected[key]:
            raise Phase9ExecutionError(f"deterministic baseline {key} drifted")
    for key in ("precision", "recall", "f1"):
        if abs(actual[key] - expected[key]) > 1e-12:
            raise Phase9ExecutionError(f"deterministic baseline {key} drifted")


def prepare_gpt_oss_quality_comparison(
    *,
    repository_root: str | Path,
    output_dir: str | Path,
    config_path: str | Path = DEFAULT_CONFIG,
) -> dict[str, Any]:
    """Regenerate the frozen corpus, baseline and required-ID mappings without a secret."""
    root = Path(repository_root).resolve()
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    plan = load_phase9_plan(root, config_path)
    base_dir = output / "base-comparison"
    base_summary = prepare_candidate_selection_comparison(
        repository_root=root,
        config_path=plan.base_comparison_config,
        output_dir=base_dir,
    )
    base_manifest = _object(base_dir / "candidate-selection-comparison-prepared.json")
    _verify_baseline(plan, base_manifest["baseline"])
    base_cases = base_manifest.get("cases")
    if not isinstance(base_cases, list) or tuple(str(item.get("key")) for item in base_cases) != FROZEN_CASE_ORDER:
        raise Phase9ExecutionError("Phase 9 frozen case order or count drifted")

    gold = evaluate_claim_candidate_gold_corpus(root, plan.gold_manifest).summary
    gold_by_key = {str(item["key"]): item for item in gold["cases"]}
    cases: list[dict[str, Any]] = []
    for base_case in base_cases:
        case_key = str(base_case["key"])
        gold_case = gold_by_key[case_key]
        resolved = {
            str(item["name"]): str(item["candidate_id"])
            for item in gold_case["resolved_candidates"]
        }
        required_names = list(plan.required_expectations.get(case_key, ()))
        if any(name not in resolved for name in required_names):
            raise Phase9ExecutionError(f"{case_key} required expectation did not resolve")
        required_ids = [resolved[name] for name in required_names]
        if len(required_ids) != len(set(required_ids)):
            raise Phase9ExecutionError(f"{case_key} required expectations did not resolve uniquely")
        if len(required_ids) > 7:
            raise Phase9ExecutionError(f"{case_key} required expectation subset exceeds the seven-ID envelope")
        useful_ids = [str(item["candidate_id"]) for item in gold_case["resolved_candidates"]]
        if not useful_ids:
            raise Phase9ExecutionError(f"{case_key} has no reviewed-useful candidate IDs")
        paths = {
            key: PurePosixPath("base-comparison") / str(value)
            for key, value in dict(base_case["paths"]).items()
        }
        cases.append(
            {
                "key": case_key,
                "classification": base_case["classification"],
                "bundle_id": base_case["bundle_id"],
                "candidate_count": base_case["candidate_count"],
                "ordered_candidate_sha256": base_case["ordered_candidate_sha256"],
                "candidate_set_id": base_case["candidate_set_id"],
                "request_id": base_case["request_id"],
                "useful_candidate_ids": sorted(useful_ids),
                "baseline_selected_candidate_ids": list(base_case["baseline_selected_candidate_ids"]),
                "required_expectation_names": required_names,
                "required_expectation_candidate_ids": {
                    name: resolved[name] for name in required_names
                },
                "required_candidate_ids": required_ids,
                "required_candidate_ids_sha256": content_sha256(required_ids),
                "paths": {key: value.as_posix() for key, value in paths.items()},
                "hashes": dict(base_case["hashes"]),
            }
        )

    manifest = {
        "version": PREPARED_VERSION,
        "phase9_version": PHASE9_VERSION,
        "configuration_version": PHASE9_CONFIG_VERSION,
        "config_path": PurePosixPath(str(config_path)).as_posix(),
        "config_sha256": content_sha256(asdict(plan)),
        "base_prepared_manifest_sha256": content_sha256(base_manifest),
        "case_order": list(FROZEN_CASE_ORDER),
        "baseline": base_manifest["baseline"],
        "model": plan.model,
        "provider_slug": plan.provider_slug,
        "planned_schedule": _planned_schedule(),
        "limits": {
            "maximum_stage_a_calls": plan.maximum_stage_a_calls,
            "maximum_stage_b_calls": plan.maximum_stage_b_calls,
            "maximum_paid_calls": plan.maximum_paid_calls,
            "maximum_call_cost_usd": plan.maximum_call_cost_usd,
            "maximum_total_cost_usd": plan.maximum_total_cost_usd,
            "maximum_semantic_repairs": 0,
            "maximum_network_retries": 0,
            "maximum_route_probes": 0,
        },
        "cases": cases,
    }
    _write_json(output / PREPARED_MANIFEST, manifest)
    return {
        "version": PREPARED_VERSION,
        "case_count": len(cases),
        "candidate_counts": {item["key"]: item["candidate_count"] for item in cases},
        "baseline": base_summary["baseline"],
        "required_candidate_counts": {
            item["key"]: len(item["required_candidate_ids"]) for item in cases
        },
        "provider_calls": 0,
    }



def _valid_sha(value: str | None) -> bool:
    return bool(
        isinstance(value, str)
        and len(value) == 40
        and all(character in "0123456789abcdef" for character in value)
    )


def _verify_prepared_integrity(
    plan: Phase9Plan,
    manifest: Mapping[str, Any],
    prepared_root: Path,
) -> dict[str, Mapping[str, Any]]:
    base_manifest_path = prepared_root / "base-comparison/candidate-selection-comparison-prepared.json"
    base_manifest = _object(base_manifest_path)
    if content_sha256(base_manifest) != manifest.get("base_prepared_manifest_sha256"):
        raise Phase9ExecutionError("Phase 9 base prepared manifest hash changed")
    cases = manifest.get("cases")
    if not isinstance(cases, list) or len(cases) != 5:
        raise Phase9ExecutionError("Phase 9 prepared corpus must contain exactly five cases")
    by_case = {str(item.get("key")): item for item in cases if isinstance(item, Mapping)}
    if tuple(by_case) != FROZEN_CASE_ORDER:
        raise Phase9ExecutionError("Phase 9 prepared case order changed")
    for case_key in FROZEN_CASE_ORDER:
        case = by_case[case_key]
        paths = case.get("paths")
        hashes = case.get("hashes")
        if not isinstance(paths, Mapping) or not isinstance(hashes, Mapping):
            raise Phase9ExecutionError(f"{case_key} prepared paths or hashes are missing")
        bundle = _object(prepared_root / str(paths["bundle"]))
        candidate_payload = _object(prepared_root / str(paths["candidates"]))
        selector_request = _object(prepared_root / str(paths["selector_request"]))
        baseline_selection = _object(prepared_root / str(paths["baseline_selection"]))
        checks = {
            "bundle": content_sha256(bundle),
            "candidates": content_sha256(candidate_payload.get("candidates")),
            "selector_request": content_sha256(selector_request),
            "baseline_selection": content_sha256(baseline_selection),
        }
        for key, digest in checks.items():
            if digest != hashes.get(key):
                raise Phase9ExecutionError(f"{case_key} prepared {key} hash changed")
        candidates = candidate_payload.get("candidates")
        if not isinstance(candidates, list) or len(candidates) != int(case.get("candidate_count", -1)):
            raise Phase9ExecutionError(f"{case_key} prepared candidate catalogue changed")
        candidate_ids = {str(item.get("candidate_id")) for item in candidates if isinstance(item, Mapping)}
        useful = set(str(item) for item in case.get("useful_candidate_ids", ()))
        required = list(str(item) for item in case.get("required_candidate_ids", ()))
        if not useful or not useful <= candidate_ids:
            raise Phase9ExecutionError(f"{case_key} reviewed-useful IDs are incomplete")
        if not set(required) <= useful or content_sha256(required) != case.get("required_candidate_ids_sha256"):
            raise Phase9ExecutionError(f"{case_key} required candidate mapping changed")
        if list(baseline_selection.get("selected_candidate_ids", ())) != list(case.get("baseline_selected_candidate_ids", ())):
            raise Phase9ExecutionError(f"{case_key} deterministic selection changed")
        if selector_request.get("request_id") != case.get("request_id"):
            raise Phase9ExecutionError(f"{case_key} selector request identity changed")
    _verify_baseline(plan, manifest["baseline"])
    return by_case


def _write_preflight_summary(
    *,
    output: Path,
    plan: Phase9Plan,
    trusted_main_sha: str | None,
    schedule: Sequence[Mapping[str, Any]],
    message: str,
    availability: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    scoring = summarize_partial(plan, [], schedule, "infrastructure_failure")
    summary = {
        "version": PHASE9_VERSION,
        "trusted_main_sha": trusted_main_sha,
        "status": scoring["status"],
        "outcome": scoring["outcome"],
        "failure_code": "preflight_infrastructure_failure",
        "message": message,
        "completed_paid_calls": 0,
        "maximum_paid_calls": plan.maximum_paid_calls,
        "observed_total_cost_usd": 0.0,
        "availability": dict(availability or {}),
        "scoring": scoring,
        "model_selector_enabled": False,
        "automatic_generation": False,
        "publication": False,
        "repository_write": False,
    }
    _write_json(output / RECORDS_FILE, {"records": [], "planned_schedule": list(schedule)})
    _write_reviewer_csv(output / REVIEWER_CSV, [], schedule)
    _write_json(output / SUMMARY_FILE, summary)
    (output / DECISION_INPUT).write_text(_decision_markdown(summary), encoding="utf-8")
    (output / ACTIONS_SUMMARY).write_text(_decision_markdown(summary), encoding="utf-8")
    return summary

def _price_per_million(value: Any, path: str) -> Decimal:
    try:
        result = Decimal(str(value)) * Decimal(1_000_000)
    except (InvalidOperation, ValueError) as exc:
        raise Phase9ExecutionError(f"{path} is not a valid catalogue price") from exc
    if result < 0:
        raise Phase9ExecutionError(f"{path} must be non-negative")
    return result


def check_phase9_availability(
    plan: Phase9Plan,
    *,
    catalogue_loader: Callable[[], Mapping[str, Any]] = _catalogue,
) -> dict[str, Any]:
    payload = catalogue_loader()
    rows = payload.get("data")
    if not isinstance(rows, list):
        raise Phase9ExecutionError("OpenRouter model catalogue is missing data[]")
    row = next(
        (item for item in rows if isinstance(item, Mapping) and item.get("id") == plan.model),
        None,
    )
    result: dict[str, Any] = {
        "checked_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "model": plan.model,
        "available": isinstance(row, Mapping),
        "eligible": False,
        "reason": None,
    }
    if not isinstance(row, Mapping):
        result["reason"] = "model slug not present in current OpenRouter catalogue"
        return result
    supported = sorted(str(item) for item in row.get("supported_parameters", []) if isinstance(item, str))
    pricing = row.get("pricing") if isinstance(row.get("pricing"), Mapping) else {}
    prompt_raw, completion_raw = pricing.get("prompt"), pricing.get("completion")
    context_length = row.get("context_length") if isinstance(row.get("context_length"), int) else None
    top_provider = row.get("top_provider") if isinstance(row.get("top_provider"), Mapping) else {}
    max_completion = top_provider.get("max_completion_tokens") if isinstance(top_provider.get("max_completion_tokens"), int) else None
    result.update(
        {
            "supported_parameters": supported,
            "prompt_price": prompt_raw,
            "completion_price": completion_raw,
            "context_length": context_length,
            "maximum_completion_tokens": max_completion,
            "expiration_date": row.get("expiration_date"),
        }
    )
    missing = sorted(REQUIRED_CATALOGUE_PARAMETERS - set(supported))
    if missing:
        result["reason"] = "missing required parameters: " + ", ".join(missing)
        return result
    if prompt_raw is None or completion_raw is None:
        result["reason"] = "catalogue pricing is incomplete"
        return result
    prompt = _price_per_million(prompt_raw, "pricing.prompt")
    completion = _price_per_million(completion_raw, "pricing.completion")
    result["prompt_price_per_million"] = float(prompt)
    result["completion_price_per_million"] = float(completion)
    if prompt > Decimal(str(plan.maximum_prompt_price_per_million)):
        result["reason"] = "prompt catalogue price exceeds the reviewed ceiling"
        return result
    if completion > Decimal(str(plan.maximum_completion_price_per_million)):
        result["reason"] = "completion catalogue price exceeds the reviewed ceiling"
        return result
    if context_length is not None and context_length < 16_384:
        result["reason"] = "model context length is below the governed minimum"
        return result
    if max_completion is not None and max_completion < plan.max_output_tokens:
        result["reason"] = "provider completion capacity is below the configured output limit"
        return result
    expiration = row.get("expiration_date")
    if expiration:
        try:
            expired = datetime.fromisoformat(str(expiration)).date() < datetime.now(timezone.utc).date()
        except ValueError:
            result["reason"] = "catalogue expiration_date is invalid"
            return result
        if expired:
            result["reason"] = f"model expired on {expiration}"
            return result
    result["eligible"] = True
    return result


def _request_body(
    plan: Phase9Plan,
    prompt_template: str,
    compact_request: Mapping[str, Any],
    provider_schema: Mapping[str, Any],
) -> bytes:
    prompt = render_candidate_selector_prompt(prompt_template, compact_request, None)
    return canonical_json_bytes(
        {
            "model": plan.model,
            "messages": [{"role": "system", "content": prompt}],
            "max_tokens": plan.max_output_tokens,
            "stream": False,
            "reasoning": {"effort": plan.reasoning_effort, "exclude": True},
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "crypto_market_candidate_selection_v1",
                    "strict": True,
                    "schema": dict(provider_schema),
                },
            },
            "provider": {
                "only": [plan.provider_slug],
                "order": [plan.provider_slug],
                "allow_fallbacks": False,
                "require_parameters": True,
                "data_collection": "deny",
                "max_price": {
                    "prompt": plan.maximum_prompt_price_per_million,
                    "completion": plan.maximum_completion_price_per_million,
                    "request": plan.maximum_call_cost_usd,
                },
            },
        }
    )


def _failure(
    *,
    schedule: Mapping[str, Any],
    kind: str,
    code: str,
    message: str,
    base: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    selected = [] if kind == "model" else None
    return {
        **dict(schedule),
        **dict(base or {}),
        "classification": "model-failure" if kind == "model" else "infrastructure-failure",
        "failure_kind": kind,
        "failure_code": code,
        "message": message,
        "selected_candidate_ids": selected,
        "governance_pass": False,
    }


def _execute_call(
    *,
    output: Path,
    plan: Phase9Plan,
    schedule: Mapping[str, Any],
    prepared_case: Mapping[str, Any],
    prepared_root: Path,
    prompt_template: str,
    provider_schema: Mapping[str, Any],
    selection_schema: Mapping[str, Any],
    ranking: Any,
    evidence_schema: Mapping[str, Any],
    claim_plan_schema: Mapping[str, Any],
    api_key: str,
    ledger: _Ledger,
    transport: Transport,
) -> dict[str, Any]:
    case_key = str(schedule["case_key"])
    repeat_index = int(schedule["repeat_index"])
    call_dir = output / "runs" / f"repeat-{repeat_index}" / case_key
    call_dir.mkdir(parents=True, exist_ok=True)
    paths = prepared_case["paths"]
    bundle = _object(prepared_root / str(paths["bundle"]))
    candidate_payload = _object(prepared_root / str(paths["candidates"]))
    candidates = candidate_payload.get("candidates")
    if not isinstance(candidates, list):
        raise Phase9ExecutionError(f"{case_key} prepared candidates are missing")
    canonical_request = _object(prepared_root / str(paths["selector_request"]))
    compact_request = build_compact_candidate_selector_request(canonical_request)
    request_body = _request_body(plan, prompt_template, compact_request, provider_schema)
    (call_dir / "request.json").write_bytes(request_body + b"\n")
    ledger.before_call()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/8ft0-ai/crypto-pulse",
        "X-OpenRouter-Title": "CryptoPulse Phase 9 GPT-OSS Quality Comparison",
        "X-OpenRouter-Metadata": "enabled",
    }
    started = time.monotonic()
    try:
        response = transport.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers=headers,
            body=request_body,
            timeout_seconds=180.0,
        )
    except Exception as exc:
        latency_ms = round((time.monotonic() - started) * 1000)
        ledger.charge(plan.maximum_call_cost_usd)
        result = _failure(
            schedule=schedule,
            kind="infrastructure",
            code=str(getattr(exc, "code", None) or "transport_error"),
            message=" ".join(str(exc).split())[:500].replace(api_key, "[REDACTED]"),
            base={
                "observed_cost_usd": plan.maximum_call_cost_usd,
                "metering_status": "reserved-maximum",
                "latency_ms": latency_ms,
            },
        )
        _write_json(call_dir / "result.json", result)
        return result
    latency_ms = round((time.monotonic() - started) * 1000)
    raw_text = response.body.decode("utf-8", errors="replace")
    if api_key:
        raw_text = raw_text.replace(api_key, "[REDACTED]")
    # Written before any response JSON, identity, metering or content judgement.
    _write_json(
        call_dir / "http-response.json",
        {
            "version": PHASE9_VERSION,
            **dict(schedule),
            "requested_model": plan.model,
            "http_status": response.status,
            "response_headers": _safe_headers(response.headers),
            "request_sha256": _sha256_bytes(request_body),
            "request_bytes": len(request_body),
            "raw_body_sha256": _sha256_bytes(response.body),
            "raw_body_utf8": raw_text,
            "latency_ms": latency_ms,
        },
    )
    try:
        payload = json.loads(response.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        ledger.charge(plan.maximum_call_cost_usd)
        result = _failure(
            schedule=schedule,
            kind="infrastructure",
            code="non_json_response",
            message="OpenRouter response was not JSON",
            base={"observed_cost_usd": plan.maximum_call_cost_usd, "metering_status": "reserved-maximum", "latency_ms": latency_ms},
        )
        _write_json(call_dir / "result.json", result)
        return result
    if not isinstance(payload, Mapping):
        ledger.charge(plan.maximum_call_cost_usd)
        result = _failure(schedule=schedule, kind="infrastructure", code="response_not_object", message="OpenRouter response was not an object", base={"observed_cost_usd": plan.maximum_call_cost_usd, "metering_status": "reserved-maximum", "latency_ms": latency_ms})
        _write_json(call_dir / "result.json", result)
        return result

    usage = payload.get("usage") if isinstance(payload.get("usage"), Mapping) else {}
    cost_raw = usage.get("cost")
    reported_cost = isinstance(cost_raw, (int, float)) and not isinstance(cost_raw, bool)
    cost = float(cost_raw) if reported_cost else plan.maximum_call_cost_usd
    ledger.charge(cost)
    metadata = payload.get("openrouter_metadata") if isinstance(payload.get("openrouter_metadata"), Mapping) else {}
    attempts = metadata.get("attempts") if isinstance(metadata.get("attempts"), list) else []
    actual_model = payload.get("model") if isinstance(payload.get("model"), str) else None
    actual_provider = _selected_provider(metadata)
    provider_slug = _provider_slug(actual_provider)
    choices = payload.get("choices") if isinstance(payload.get("choices"), list) else []
    choice = choices[0] if len(choices) == 1 and isinstance(choices[0], Mapping) else {}
    message = choice.get("message") if isinstance(choice.get("message"), Mapping) else {}
    content = message.get("content") if isinstance(message.get("content"), str) else None
    completion_details = usage.get("completion_tokens_details") if isinstance(usage.get("completion_tokens_details"), Mapping) else {}
    base = {
        "requested_model": plan.model,
        "actual_model": actual_model,
        "actual_provider": actual_provider,
        "provider_slug": provider_slug,
        "generation_id": payload.get("id") if isinstance(payload.get("id"), str) else None,
        "finish_reason": choice.get("finish_reason"),
        "input_tokens": usage.get("prompt_tokens"),
        "output_tokens": usage.get("completion_tokens"),
        "reasoning_tokens": completion_details.get("reasoning_tokens"),
        "observed_cost_usd": cost,
        "metering_status": "reported" if reported_cost else "reserved-maximum",
        "latency_ms": latency_ms,
        "router_attempt_count": len(attempts),
        "provider_fallback_used": len(attempts) != 1,
        "cross_model_fallback_used": actual_model is not None and actual_model != plan.model,
    }
    # Deliberately exclude any returned reasoning text; retain only observable counts and routing data.
    _write_json(
        call_dir / "interpreted-response.json",
        {
            "version": PHASE9_VERSION,
            **dict(schedule),
            **base,
            "http_status": response.status,
            "content_present": bool(content),
            "openrouter_metadata": dict(metadata),
            "usage": dict(usage),
            "top_level_error": payload.get("error"),
            "choice_error": choice.get("error"),
        },
    )

    def infra(code: str, text: str) -> dict[str, Any]:
        return _failure(schedule=schedule, kind="infrastructure", code=code, message=text, base=base)

    def model_fail(code: str, text: str) -> dict[str, Any]:
        score = score_counts([], list(prepared_case["useful_candidate_ids"]))
        return {**_failure(schedule=schedule, kind="model", code=code, message=text, base=base), **score}

    result: dict[str, Any]
    if not 200 <= response.status < 300:
        result = infra("http_error", f"OpenRouter returned HTTP {response.status}")
    elif not reported_cost:
        result = infra("usage_cost_missing", "OpenRouter response did not report usage.cost")
    elif cost > plan.maximum_call_cost_usd + 1e-12:
        result = infra("call_cost_exceeded", "OpenRouter response exceeded the reviewed per-call ceiling")
    elif actual_model != plan.model:
        result = infra("model_identity_mismatch", "OpenRouter did not preserve the exact requested model")
    elif provider_slug != plan.provider_slug:
        result = infra("provider_identity_mismatch", "OpenRouter did not preserve the pinned DeepInfra route")
    elif not metadata or len(attempts) != 1:
        result = infra("provider_fallback_or_metadata_failure", "Exact one-attempt router evidence was not retained")
    elif not isinstance(attempts[0], Mapping) or attempts[0].get("status") != 200 or _provider_slug(str(attempts[0].get("provider"))) != plan.provider_slug:
        result = infra("provider_attempt_invalid", "Router attempt evidence did not prove one successful DeepInfra attempt")
    elif payload.get("error") is not None or choice.get("error") is not None:
        result = infra("provider_response_error", "OpenRouter response retained a provider or choice error")
    elif len(choices) != 1:
        result = model_fail("choice_count_invalid", "OpenRouter response did not contain exactly one choice")
    elif not isinstance(choice.get("finish_reason"), str):
        result = infra("finish_reason_missing", "OpenRouter response did not retain finish_reason")
    elif any(isinstance(usage.get(key), bool) or not isinstance(usage.get(key), int) for key in ("prompt_tokens", "completion_tokens")):
        result = infra("token_usage_missing", "OpenRouter response did not retain prompt/completion token counts")
    elif isinstance(completion_details.get("reasoning_tokens"), bool) or not isinstance(completion_details.get("reasoning_tokens"), int):
        result = infra("reasoning_usage_missing", "OpenRouter response did not retain reasoning-token count")
    elif not content:
        result = model_fail("message_content_missing", "OpenRouter returned no final message.content")
    else:
        try:
            decoded = json.loads(content)
        except json.JSONDecodeError:
            result = model_fail("content_not_json", "The final content was not JSON")
        else:
            try:
                validation = validate_candidate_selection(
                    decoded,
                    candidates,
                    config=ranking,
                    evidence_bundle_id=str(bundle["bundle_id"]),
                    selection_schema=selection_schema,
                )
            except SelectorEnvelopeError as exc:
                result = model_fail(exc.code, str(exc))
            else:
                if not validation.is_valid:
                    result = model_fail("candidate_selection_invalid", "The candidate-ID envelope failed repository validation")
                else:
                    selected_ids = list(validation.selected_candidate_ids)
                    selection = {"evidence_bundle_id": bundle["bundle_id"], "selected_candidate_ids": selected_ids}
                    claim_plan = reconstruct_claim_plan(selection, candidates, config=ranking)
                    plan_validation = validate_claim_plan(bundle, claim_plan, evidence_schema=evidence_schema, claim_plan_schema=claim_plan_schema)
                    if not plan_validation.is_valid:
                        result = model_fail("claim_plan_invalid", "A valid selection reconstructed to an invalid claim plan")
                    else:
                        rendered = render_claim_plan(bundle, claim_plan, plan_validation)
                        _write_json(call_dir / "selection.json", selection)
                        _write_json(call_dir / "claim-plan.json", claim_plan)
                        (call_dir / "rendered-report.md").write_bytes(rendered.markdown)
                        scores = score_counts(selected_ids, list(prepared_case["useful_candidate_ids"]))
                        result = {
                            **dict(schedule),
                            **base,
                            **scores,
                            "classification": "completed",
                            "failure_kind": None,
                            "failure_code": None,
                            "message": "The candidate-ID request completed the Phase 9 repository boundary",
                            "selected_candidate_ids": selected_ids,
                            "prohibited_selected_candidate_ids": [],
                            "selector_validation": validation.as_dict(),
                            "claim_plan_sha256": content_sha256(claim_plan),
                            "rendered_markdown_sha256": _sha256_bytes(rendered.markdown),
                            "governance_pass": True,
                        }
    _write_json(call_dir / "result.json", result)
    return result


def _write_reviewer_csv(
    path: Path,
    records: Sequence[Mapping[str, Any]],
    planned_schedule: Sequence[Mapping[str, Any]] | None = None,
) -> None:
    fields = [
        "planned_order", "stage", "case_key", "repeat_index", "classification",
        "failure_code", "selected_count", "useful_selected_count", "useful_expected_count",
        "precision", "recall", "f1", "actual_model", "actual_provider",
        "router_attempt_count", "input_tokens", "output_tokens", "reasoning_tokens",
        "latency_ms", "observed_cost_usd",
    ]
    indexed = {
        (str(row["case_key"]), int(row["repeat_index"])): dict(row)
        for row in records
    }
    rows: list[Mapping[str, Any]] = []
    for item in planned_schedule or records:
        key = (str(item["case_key"]), int(item["repeat_index"]))
        rows.append(
            indexed.get(
                key,
                {
                    **dict(item),
                    "classification": "not_attempted",
                    "failure_code": "not_applicable",
                },
            )
        )
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in fields})


def _write_additions_csv(path: Path, case_rows: Sequence[Mapping[str, Any]]) -> None:
    fields = [
        "case_key", "candidate_id", "frequency", "stable_majority", "model_only",
        "deterministic_only", "reviewed_useful", "classification",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for case in case_rows:
            frequencies = case["selection_frequencies"]
            stable = set(case["stable_majority_candidate_ids"])
            model_only = set(case["stable_model_only_candidate_ids"])
            deterministic_only = set(case["stable_deterministic_only_candidate_ids"])
            useful = set(case["reviewed_useful_candidate_ids"])
            all_ids = set(frequencies) | model_only | deterministic_only
            for identifier in sorted(all_ids):
                writer.writerow(
                    {
                        "case_key": case["case_key"],
                        "candidate_id": identifier,
                        "frequency": frequencies.get(identifier, 0),
                        "stable_majority": identifier in stable,
                        "model_only": identifier in model_only,
                        "deterministic_only": identifier in deterministic_only,
                        "reviewed_useful": identifier in useful,
                        "classification": (
                            "stable_useful_addition" if identifier in set(case["stable_useful_addition_candidate_ids"])
                            else "stable_useful_loss" if identifier in set(case["stable_useful_loss_candidate_ids"])
                            else "other"
                        ),
                    }
                )


def _format_percentage(value: Any) -> str:
    percentage = (Decimal(str(value)) * Decimal(100)).quantize(
        Decimal("0.000001"), rounding=ROUND_HALF_UP
    )
    return f"{percentage}%"


def _decision_markdown(summary: Mapping[str, Any]) -> str:
    lines = [
        "# Phase 9 GPT-OSS quality comparison decision input",
        "",
        "> Protected evaluation evidence only. This does not enable model selection or publication.",
        "",
        f"- Trusted main SHA: `{summary.get('trusted_main_sha')}`",
        f"- Outcome: `{summary.get('outcome')}`",
        f"- Evidence status: `{summary.get('status')}`",
        f"- Paid calls: `{summary.get('completed_paid_calls')} / {summary.get('maximum_paid_calls')}`",
        f"- Observed/reserved cost: `USD {float(summary.get('observed_total_cost_usd', 0)):.6f}`",
        "",
    ]
    scoring = summary.get("scoring")
    if isinstance(scoring, Mapping) and isinstance(scoring.get("aggregate"), Mapping):
        aggregate = scoring["aggregate"]
        lines.extend(
            [
                "## Aggregate quality",
                "",
                f"- Precision: `{_format_percentage(aggregate['precision'])}`",
                f"- Recall: `{_format_percentage(aggregate['recall'])}`",
                f"- F1: `{_format_percentage(aggregate['f1'])}`",
                f"- Corpus median Jaccard: `{float(scoring['corpus_median_pairwise_jaccard']):.6f}`",
                "",
                "## Promotion gates",
                "",
            ]
        )
        for key, value in scoring.get("promotion_gates", {}).items():
            lines.append(f"- `{key}`: `{str(value).lower()}`")
    lines.extend(
        [
            "",
            "A separate reviewed decision issue and pull request must accept or reject this evidence. No workflow output can promote the model automatically.",
            "",
        ]
    )
    return "\n".join(lines)


def execute_gpt_oss_quality_comparison(
    *,
    repository_root: str | Path,
    prepared_dir: str | Path,
    output_dir: str | Path,
    api_key: str | None,
    config_path: str | Path = DEFAULT_CONFIG,
    trusted_main_sha: str | None = None,
    catalogue_loader: Callable[[], Mapping[str, Any]] = _catalogue,
    transport_factory: Callable[[], Transport] | None = None,
) -> dict[str, Any]:
    """Execute one sequential, fail-closed Stage A/B comparison with no retry."""
    root = Path(repository_root).resolve()
    prepared_root = Path(prepared_dir).resolve()
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    plan = load_phase9_plan(root, config_path)
    schedule = _planned_schedule()
    availability: dict[str, Any] = {}
    try:
        if not api_key:
            raise Phase9ExecutionError("OPENROUTER_API_KEY is required for protected Phase 9 execution")
        if not _valid_sha(trusted_main_sha):
            raise Phase9ExecutionError("trusted_main_sha must be a 40-character lowercase commit SHA")
        manifest = _object(prepared_root / PREPARED_MANIFEST)
        if manifest.get("version") != PREPARED_VERSION or manifest.get("config_sha256") != content_sha256(asdict(plan)):
            raise Phase9ExecutionError("Phase 9 prepared manifest does not match the reviewed configuration")
        if tuple(manifest.get("case_order", ())) != FROZEN_CASE_ORDER:
            raise Phase9ExecutionError("Phase 9 prepared case order changed")
        schedule = list(manifest.get("planned_schedule", schedule))
        if schedule != _planned_schedule():
            raise Phase9ExecutionError("Phase 9 prepared call schedule changed")
        by_case = _verify_prepared_integrity(plan, manifest, prepared_root)
        availability = check_phase9_availability(plan, catalogue_loader=catalogue_loader)
        _write_json(output / AVAILABILITY_FILE, availability)
        if availability.get("eligible") is not True:
            raise Phase9ExecutionError(str(availability.get("reason") or "model is not catalogue eligible"))
    except (EvaluationIntegrityError, OSError, TypeError, ValueError) as exc:
        return _write_preflight_summary(
            output=output,
            plan=plan,
            trusted_main_sha=trusted_main_sha,
            schedule=schedule,
            message=" ".join(str(exc).split())[:500],
            availability=availability,
        )

    prompt_template = (root / plan.selector_prompt).read_text(encoding="utf-8")
    selection_schema = _object(root / plan.selection_schema)
    provider_schema = project_openai_strict_schema(selection_schema)
    ranking = load_ranking_config(root, plan.ranking_config)
    evidence_schema = _object(root / "schemas/crypto-market-evidence-bundle-v1.json")
    claim_plan_schema = _object(root / "schemas/crypto-market-claim-plan-v1.json")
    ledger = _Ledger(plan)
    transport_builder = transport_factory or (lambda: UrllibTransport())
    records: list[dict[str, Any]] = []
    decisive_key: str | None = None

    for item in schedule:
        result = _execute_call(
            output=output,
            plan=plan,
            schedule=item,
            prepared_case=by_case[str(item["case_key"])],
            prepared_root=prepared_root,
            prompt_template=prompt_template,
            provider_schema=provider_schema,
            selection_schema=selection_schema,
            ranking=ranking,
            evidence_schema=evidence_schema,
            claim_plan_schema=claim_plan_schema,
            api_key=api_key,
            ledger=ledger,
            transport=transport_builder(),
        )
        records.append(result)
        if result["classification"] != "completed":
            decisive_key = "model_failure" if result.get("failure_kind") == "model" else "infrastructure_failure"
            break

    if decisive_key is None and len(records) == 15:
        scoring = summarize_complete_corpus(plan, records, by_case)
    else:
        scoring = summarize_partial(plan, records, schedule, decisive_key or "infrastructure_failure")
    outcome = str(scoring["outcome"])
    summary = {
        "version": PHASE9_VERSION,
        "trusted_main_sha": trusted_main_sha,
        "config_path": PurePosixPath(str(config_path)).as_posix(),
        "config_sha256": content_sha256(asdict(plan)),
        "prepared_manifest_sha256": content_sha256(manifest),
        "model": plan.model,
        "provider_slug": plan.provider_slug,
        "status": scoring["status"],
        "outcome": outcome,
        "maximum_stage_a_calls": plan.maximum_stage_a_calls,
        "maximum_stage_b_calls": plan.maximum_stage_b_calls,
        "maximum_paid_calls": plan.maximum_paid_calls,
        "completed_paid_calls": ledger.calls,
        "maximum_call_cost_usd": plan.maximum_call_cost_usd,
        "maximum_total_cost_usd": plan.maximum_total_cost_usd,
        "observed_total_cost_usd": ledger.total_cost,
        "availability": availability,
        "scoring": scoring,
        "model_selector_enabled": False,
        "semantic_repairs": 0,
        "network_retries": 0,
        "route_probes": 0,
        "automatic_generation": False,
        "publication": False,
        "repository_write": False,
    }
    _write_json(output / RECORDS_FILE, {"version": PHASE9_VERSION, "records": records, "planned_schedule": schedule})
    _write_json(output / SUMMARY_FILE, summary)
    _write_reviewer_csv(output / REVIEWER_CSV, records, schedule)
    if scoring.get("status") == "complete-adjudicable":
        _write_additions_csv(output / ADDITIONS_CSV, scoring["cases"])
    (output / DECISION_INPUT).write_text(_decision_markdown(summary), encoding="utf-8")
    (output / ACTIONS_SUMMARY).write_text(_decision_markdown(summary), encoding="utf-8")
    return summary
