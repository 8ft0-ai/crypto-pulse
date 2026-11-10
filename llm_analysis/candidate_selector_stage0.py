"""Prepare and execute the Phase 7 low-cost candidate-selector Stage 0 screen."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
from dataclasses import asdict
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Mapping, Sequence

from .candidate_selection_contract import (
    SelectorEnvelopeError,
    validate_candidate_selection,
)
from .candidate_selection_model_comparison import (
    PREPARED_MANIFEST as PHASE6_PREPARED_MANIFEST,
    prepare_candidate_selection_comparison,
)
from .candidate_selector_compact_projection import (
    MAX_COMPACT_REQUEST_BYTES,
    build_compact_candidate_selector_request,
)
from .candidate_selector_stage0_config import (
    DEFAULT_STAGE0_CONFIG,
    STAGE0_CONFIG_VERSION,
    Stage0Model,
    Stage0Plan,
    load_stage0_plan,
)
from .claim_plan_render import render_claim_plan
from .claim_plan_validation import validate_claim_plan
from .compact_candidate_selector_client import CompactCandidateSelectorClient
from .contracts import canonical_json_bytes, content_sha256
from .deterministic_ranking import load_ranking_config, run_deterministic_baseline
from .deterministic_reconstruction import reconstruct_claim_plan
from .evaluation import (
    EvaluationIntegrityError,
    EvaluationModel,
    _catalogue,
    _read_json,
    _write_json,
)
from .evaluation_viability import ClassifiedTransport
from .generation_config import GenerationConfig, ProviderPolicy
from .openai_schema_projection import project_openai_strict_schema
from .openrouter_candidate_selector import OpenRouterCandidateSelectorClient
from .openrouter_client import Transport
from .paid_benchmark import PaidBenchmarkPlan, check_paid_model_availability

STAGE0_VERSION = "phase-07-low-cost-candidate-selector-stage-0/v1"
STAGE0_PREPARED_VERSION = "phase-07-low-cost-candidate-selector-stage-0-prepared/v1"
STAGE0_PREPARED_MANIFEST = "low-cost-selector-stage-0-prepared.json"
STAGE0_SUMMARY = "low-cost-selector-stage-0-summary.json"
STAGE0_RESULTS = "low-cost-selector-stage-0-results.json"
STAGE0_ACTIONS_SUMMARY = "actions-summary.md"


class _BudgetLedger:
    def __init__(self, plan: Stage0Plan) -> None:
        self.plan = plan
        self.total_cost = 0.0
        self.route_probes = 0
        self.selector_generations = 0
        self.model_costs = {item.key: 0.0 for item in plan.models}

    def _check(self, model: Stage0Model, maximum: float) -> None:
        if self.total_cost + maximum > self.plan.maximum_total_cost_usd + 1e-12:
            raise EvaluationIntegrityError("Stage 0 whole-run cost ceiling would be exceeded")
        if self.model_costs[model.key] + maximum > model.maximum_model_cost_usd + 1e-12:
            raise EvaluationIntegrityError(f"{model.key} model cost ceiling would be exceeded")

    def before_route(self, model: Stage0Model) -> None:
        if self.route_probes >= self.plan.maximum_route_probes:
            raise EvaluationIntegrityError("Stage 0 route-probe ceiling would be exceeded")
        self._check(model, model.maximum_route_cost_usd)
        self.route_probes += 1

    def before_generation(self, model: Stage0Model, maximum: float) -> None:
        if self.selector_generations >= self.plan.maximum_selector_generations:
            raise EvaluationIntegrityError("Stage 0 selector-generation ceiling would be exceeded")
        if abs(maximum - model.maximum_generation_cost_usd) > 1e-12:
            raise EvaluationIntegrityError("selector client requested an unreviewed call ceiling")
        self._check(model, maximum)
        self.selector_generations += 1

    def add(self, model: Stage0Model, actual: float) -> None:
        if actual < 0:
            raise EvaluationIntegrityError("provider cost must not be negative")
        self.total_cost += actual
        self.model_costs[model.key] += actual
        if self.total_cost > self.plan.maximum_total_cost_usd + 1e-12:
            raise EvaluationIntegrityError("observed Stage 0 cost exceeded the whole-run ceiling")
        if self.model_costs[model.key] > model.maximum_model_cost_usd + 1e-12:
            raise EvaluationIntegrityError(f"observed {model.key} cost exceeded its ceiling")

    @property
    def paid_calls(self) -> int:
        return self.route_probes + self.selector_generations


def _read_object(path: Path) -> dict[str, Any]:
    value = _read_json(path)
    if not isinstance(value, dict):
        raise EvaluationIntegrityError(f"{path} must contain a JSON object")
    return value


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _relative(root: Path, path: Path) -> str:
    return PurePosixPath(path.relative_to(root).as_posix()).as_posix()


def prepare_stage0(
    *,
    repository_root: str | Path,
    config_path: str | Path = DEFAULT_STAGE0_CONFIG,
    output_dir: str | Path,
) -> dict[str, Any]:
    """Regenerate the real Phase 6 case and retain one Stage 0 input bundle."""

    root = Path(repository_root).resolve()
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    plan = load_stage0_plan(root, config_path)

    phase6_root = output / "phase6-prepared"
    prepare_candidate_selection_comparison(
        repository_root=root,
        config_path=plan.phase6_comparison_config,
        output_dir=phase6_root,
    )
    phase6_manifest = _read_object(phase6_root / PHASE6_PREPARED_MANIFEST)
    rows = phase6_manifest.get("cases")
    if not isinstance(rows, list):
        raise EvaluationIntegrityError("Phase 6 prepared manifest is missing cases")
    matches = [row for row in rows if isinstance(row, Mapping) and row.get("key") == plan.case_key]
    if len(matches) != 1:
        raise EvaluationIntegrityError("Stage 0 case is not unique in the prepared Phase 6 corpus")
    case = dict(matches[0])
    if case.get("candidate_count") != plan.expected_candidate_count:
        raise EvaluationIntegrityError("Stage 0 candidate count differs from the reviewed contract")
    paths = case.get("paths")
    if not isinstance(paths, Mapping):
        raise EvaluationIntegrityError("Stage 0 prepared case is missing paths")

    selected = output / "selected-case"
    selected.mkdir(parents=True, exist_ok=True)
    copied: dict[str, str] = {}
    for key in (
        "bundle",
        "candidates",
        "baseline_selection",
        "baseline_plan",
        "baseline_render",
        "selector_request",
        "reviewed_ids",
    ):
        source_rel = paths.get(key)
        if not isinstance(source_rel, str):
            raise EvaluationIntegrityError(f"Stage 0 prepared case is missing {key}")
        source = phase6_root / source_rel
        suffix = source.suffix or ".json"
        destination = selected / f"{key.replace('_', '-')}{suffix}"
        shutil.copyfile(source, destination)
        copied[key] = _relative(output, destination)

    candidate_payload = _read_object(output / copied["candidates"])
    candidates = candidate_payload.get("candidates")
    if not isinstance(candidates, list) or len(candidates) != plan.expected_candidate_count:
        raise EvaluationIntegrityError("Stage 0 candidate catalogue is incomplete")
    canonical_request = _read_object(output / copied["selector_request"])
    canonical_ids = [
        item.get("candidate_id") if isinstance(item, Mapping) else None
        for item in candidates
    ]
    request_candidates = canonical_request.get("candidates")
    if not isinstance(request_candidates, list):
        raise EvaluationIntegrityError("Stage 0 canonical selector request is missing candidates")
    request_ids = [
        item.get("candidate_id") if isinstance(item, Mapping) else None
        for item in request_candidates
    ]
    if request_ids != canonical_ids:
        raise EvaluationIntegrityError("Stage 0 selector request changed candidate identity or order")

    compact = build_compact_candidate_selector_request(canonical_request)
    compact_ids = [
        row[0]
        for row in compact.get("candidates", [])
        if isinstance(row, list) and row
    ]
    if compact_ids != canonical_ids:
        raise EvaluationIntegrityError("Stage 0 compact projection changed candidate identity or order")
    compact_bytes = canonical_json_bytes(compact)
    if len(compact_bytes) > MAX_COMPACT_REQUEST_BYTES:
        raise EvaluationIntegrityError("Stage 0 compact selector request exceeds 65,536 bytes")
    compact_path = selected / "compact-selector-request.json"
    _write_json(compact_path, compact)
    copied["compact_request"] = _relative(output, compact_path)

    manifest = {
        "version": STAGE0_PREPARED_VERSION,
        "stage0_version": STAGE0_VERSION,
        "configuration_version": STAGE0_CONFIG_VERSION,
        "config_path": PurePosixPath(str(config_path)).as_posix(),
        "config_sha256": content_sha256(asdict(plan)),
        "phase6_prepared_manifest_sha256": content_sha256(phase6_manifest),
        "case_key": plan.case_key,
        "classification": case.get("classification"),
        "candidate_count": len(candidates),
        "ordered_candidate_sha256": content_sha256(candidates),
        "canonical_request_id": canonical_request.get("request_id"),
        "canonical_request_sha256": content_sha256(canonical_request),
        "compact_request_id": compact.get("compact_request_id"),
        "compact_request_sha256": content_sha256(compact),
        "compact_request_bytes": len(compact_bytes),
        "paths": copied,
        "models": [asdict(item) for item in plan.models],
        "limits": {
            "maximum_route_probes": plan.maximum_route_probes,
            "maximum_selector_generations": plan.maximum_selector_generations,
            "maximum_paid_calls": plan.maximum_paid_calls,
            "maximum_semantic_repairs": plan.maximum_semantic_repairs,
            "maximum_network_retries": plan.maximum_network_retries,
            "maximum_total_cost_usd": plan.maximum_total_cost_usd,
        },
    }
    _write_json(output / STAGE0_PREPARED_MANIFEST, manifest)
    return {
        "version": STAGE0_PREPARED_VERSION,
        "case_key": plan.case_key,
        "candidate_count": len(candidates),
        "compact_request_bytes": len(compact_bytes),
        "compact_request_id": compact.get("compact_request_id"),
        "models": [item.model for item in plan.models],
        "provider_calls": 0,
    }


def _availability_plan(model: Stage0Model) -> PaidBenchmarkPlan:
    return PaidBenchmarkPlan(
        version=1,
        base_generation_config="config/llm-generation.yml",
        corpus_source_config="config/llm-evaluation.yml",
        runs_per_case=1,
        model=EvaluationModel(
            key=model.key,
            model=model.model,
            role="current_candidate",
            availability_checked_at=model.availability_checked_at,
            known_expiration_date=model.known_expiration_date,
        ),
        cases=(),
        maximum_prompt_price_per_million=model.maximum_prompt_price_per_million,
        maximum_completion_price_per_million=model.maximum_completion_price_per_million,
        maximum_generation_cost_usd=model.maximum_generation_cost_usd,
        maximum_experiment_cost_usd=model.maximum_model_cost_usd,
    )


def _runtime_config(
    plan: Stage0Plan,
    model: Stage0Model,
    *,
    call_cap: float,
) -> GenerationConfig:
    return GenerationConfig(
        provider="openrouter",
        endpoint="https://openrouter.ai/api/v1/chat/completions",
        model=model.model,
        prompt_path=plan.selector_prompt,
        analysis_schema_path=plan.selection_schema,
        prompt_version="crypto-market-candidate-selection-compact/v1",
        analysis_schema_version="crypto-market-candidate-selection/v1",
        evidence_schema_version="crypto-market-evidence-bundle/v1",
        temperature=0.0,
        max_output_tokens=model.max_output_tokens,
        timeout_seconds=180.0,
        retry_limit=0,
        retry_backoff_seconds=0.0,
        max_request_bytes=5_000_000,
        max_cost_usd=call_cap,
        structured_output=True,
        cross_model_fallback=False,
        router_metadata=True,
        app_referer="https://github.com/8ft0-ai/crypto-pulse",
        app_title="CryptoPulse Phase 7 Stage 0",
        provider_policy=ProviderPolicy(
            require_parameters=True,
            data_collection="deny",
            zdr=False,
            allow_fallbacks=False,
            order=(),
            only=(model.allowed_actual_provider,),
            ignore=(),
            sort=None,
            max_prompt_price_per_million=model.maximum_prompt_price_per_million,
            max_completion_price_per_million=model.maximum_completion_price_per_million,
            max_request_price=call_cap,
        ),
    )


def _failure_classification(message: str, code: str | None, *, route: bool) -> str:
    text = f"{code or ''} {message}".lower()
    if any(
        token in text
        for token in (
            "trustworthy usage",
            "usage metadata",
            "missing usage",
            "missing cost",
            "complete metering",
            "metering",
        )
    ):
        return "inconclusive-infrastructure"
    if any(token in text for token in ("cost", "price", "budget", "ceiling")):
        return "cost-ineligible"
    if any(
        token in text
        for token in (
            "preserve the requested model",
            "unapproved provider",
            "provider fallback",
            "cross-model",
            "cross model",
            "actual provider",
            "actual model",
        )
    ):
        return "identity-failure"
    if any(
        token in text
        for token in (
            "json schema",
            "json_schema",
            "structured output",
            "structured_output",
            "response_format",
            "required parameter",
            "unsupported parameter",
        )
    ):
        return "schema-incompatible"
    if route and any(
        token in text
        for token in (
            "no endpoints",
            "no endpoint",
            "ineligible_routing",
            "routing failed",
            "provider unavailable",
            "404",
            "403",
        )
    ):
        return "route-ineligible"
    return "inconclusive-infrastructure"


def _safe_call_records(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {key: value for key, value in record.items() if key != "raw_completion"}
        for record in records
    ]


def _result_markdown(summary: Mapping[str, Any]) -> str:
    lines = [
        "# Phase 7 Stage 0 low-cost selector compatibility screen",
        "",
        "> Compatibility evidence only. This run does not approve Stage 1 or enable a model selector.",
        "",
        f"- Trusted main SHA: `{summary.get('trusted_main_sha')}`",
        f"- Paid calls: `{summary.get('completed_paid_calls')} / {summary.get('maximum_paid_calls')}`",
        f"- Observed cost: `USD {float(summary.get('observed_total_cost_usd', 0.0)):.6f}`",
        f"- Stage 1 authorised: `{str(summary.get('stage1_authorized', False)).lower()}`",
        "",
        "| Model | Provider target | Classification | Route | Selector calls | Cost |",
        "| --- | --- | --- | --- | ---: | ---: |",
    ]
    for row in summary.get("models", []):
        lines.append(
            f"| `{row['model']}` | `{row['allowed_actual_provider']}` | "
            f"`{row['classification']}` | `{row['route_status']}` | "
            f"{row['selector_call_count']} | USD {row['observed_cost_usd']:.6f} |"
        )
    lines.extend(
        [
            "",
            "Any Stage 1 proposal requires a separate reviewed issue, budget and decision rule.",
            "",
        ]
    )
    return "\n".join(lines)


def execute_stage0(
    *,
    repository_root: str | Path,
    config_path: str | Path = DEFAULT_STAGE0_CONFIG,
    prepared_dir: str | Path,
    output_dir: str | Path,
    api_key: str | None,
    trusted_main_sha: str | None = None,
    catalogue_loader: Callable[[], Mapping[str, Any]] | None = None,
    route_probe: Callable[..., Mapping[str, Any]] | None = None,
    transport_factory: Callable[[], Transport] | None = None,
) -> dict[str, Any]:
    """Execute one route probe and one real selector call per configured model."""

    if not api_key:
        raise EvaluationIntegrityError("OPENROUTER_API_KEY is required for Stage 0")
    root = Path(repository_root).resolve()
    prepared_root = Path(prepared_dir).resolve()
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    plan = load_stage0_plan(root, config_path)
    manifest = _read_object(prepared_root / STAGE0_PREPARED_MANIFEST)
    if manifest.get("version") != STAGE0_PREPARED_VERSION:
        raise EvaluationIntegrityError("Stage 0 prepared manifest has the wrong version")
    if manifest.get("config_sha256") != content_sha256(asdict(plan)):
        raise EvaluationIntegrityError("Stage 0 prepared inputs and checked-in config differ")
    if manifest.get("case_key") != plan.case_key:
        raise EvaluationIntegrityError("Stage 0 prepared case differs from the reviewed config")
    if manifest.get("candidate_count") != plan.expected_candidate_count:
        raise EvaluationIntegrityError("Stage 0 prepared candidate count drifted")

    paths = manifest.get("paths")
    if not isinstance(paths, Mapping):
        raise EvaluationIntegrityError("Stage 0 prepared manifest is missing paths")
    bundle = _read_object(prepared_root / str(paths["bundle"]))
    candidate_payload = _read_object(prepared_root / str(paths["candidates"]))
    candidates = candidate_payload.get("candidates")
    if not isinstance(candidates, list):
        raise EvaluationIntegrityError("Stage 0 prepared candidates are missing")
    if content_sha256(candidates) != manifest.get("ordered_candidate_sha256"):
        raise EvaluationIntegrityError("Stage 0 prepared candidates changed")
    canonical_request = _read_object(prepared_root / str(paths["selector_request"]))
    compact_request = _read_object(prepared_root / str(paths["compact_request"]))
    if content_sha256(canonical_request) != manifest.get("canonical_request_sha256"):
        raise EvaluationIntegrityError("Stage 0 canonical request changed")
    if content_sha256(compact_request) != manifest.get("compact_request_sha256"):
        raise EvaluationIntegrityError("Stage 0 compact request changed")

    evidence_schema = _read_object(root / "schemas/crypto-market-evidence-bundle-v1.json")
    candidate_schema = _read_object(root / "schemas/crypto-market-claim-candidate-v1.json")
    claim_plan_schema = _read_object(root / "schemas/crypto-market-claim-plan-v1.json")
    selection_schema = _read_object(root / plan.selection_schema)
    provider_schema = project_openai_strict_schema(selection_schema)
    ranking = load_ranking_config(root, plan.ranking_config)
    prompt_template = (root / plan.selector_prompt).read_text(encoding="utf-8")
    baseline = run_deterministic_baseline(
        bundle,
        candidates,
        config=ranking,
        evidence_schema=evidence_schema,
        candidate_schema=candidate_schema,
        claim_plan_schema=claim_plan_schema,
    )
    expected_baseline = _read_object(prepared_root / str(paths["baseline_selection"]))
    if baseline.selection != expected_baseline:
        raise EvaluationIntegrityError("Stage 0 deterministic baseline drifted")

    if route_probe is None:
        from .candidate_selection_model_comparison_runner import (
            metered_fail_closed_route_probe,
        )

        route_probe = metered_fail_closed_route_probe
    catalogue = (catalogue_loader or _catalogue)()
    transport_builder = transport_factory or (lambda: ClassifiedTransport())
    ledger = _BudgetLedger(plan)
    results: list[dict[str, Any]] = []

    for model in plan.models:
        model_dir = output / "models" / model.key
        model_dir.mkdir(parents=True, exist_ok=True)
        availability = check_paid_model_availability(
            _availability_plan(model),
            catalogue_loader=lambda current=catalogue: current,
        )
        availability_row = {
            "availability": asdict(availability.availability),
            "prompt_price_per_million": availability.prompt_price_per_million,
            "completion_price_per_million": availability.completion_price_per_million,
            "context_length": availability.context_length,
            "maximum_completion_tokens": availability.maximum_completion_tokens,
        }
        _write_json(model_dir / "availability.json", availability_row)
        result: dict[str, Any] = {
            "model_key": model.key,
            "model": model.model,
            "allowed_actual_provider": model.allowed_actual_provider,
            "classification": None,
            "route_status": "not_attempted",
            "route": None,
            "selector_call_count": 0,
            "selector_outcome": None,
            "selector_validation": None,
            "selected_candidate_ids": [],
            "claim_plan_sha256": None,
            "rendered_markdown_sha256": None,
            "provider_calls": [],
            "observed_cost_usd": 0.0,
            "stage1_authorized": False,
        }
        if not availability.availability.eligible:
            reason = availability.availability.reason or "catalogue ineligible"
            result["classification"] = (
                "cost-ineligible" if "price" in reason.lower() else "route-ineligible"
            )
            result["failure_code"] = "catalogue_ineligible"
            result["message"] = reason
            _write_json(model_dir / "result.json", result)
            results.append(result)
            continue

        route_runtime = _runtime_config(
            plan,
            model,
            call_cap=model.maximum_route_cost_usd,
        )
        ledger.before_route(model)
        route = dict(
            route_probe(
                route_runtime,
                api_key,
                transport=transport_builder(),
            )
        )
        route_cost = route.get("estimated_cost_usd")
        if isinstance(route_cost, bool) or not isinstance(route_cost, (int, float)):
            route_cost = model.maximum_route_cost_usd
            route["estimated_cost_usd"] = route_cost
            route["metering_status"] = "reserved-maximum"
        ledger.add(model, float(route_cost))
        result["route"] = route
        result["observed_cost_usd"] = float(route_cost)
        result["route_status"] = str(route.get("probe_status") or "passed")
        _write_json(model_dir / "route.json", route)
        if result["route_status"] != "passed":
            message = str(route.get("message") or "route probe failed")
            code = str(route.get("failure_code") or "route_preflight_failure")
            result["classification"] = _failure_classification(message, code, route=True)
            result["failure_code"] = code
            result["message"] = message
            _write_json(model_dir / "result.json", result)
            results.append(result)
            continue
        if route.get("actual_provider") != model.allowed_actual_provider or route.get(
            "actual_model"
        ) not in {model.model, None}:
            result["classification"] = "identity-failure"
            result["failure_code"] = "route_identity_mismatch"
            result["message"] = "route did not preserve the reviewed provider/model identity"
            _write_json(model_dir / "result.json", result)
            results.append(result)
            continue

        selector_runtime = _runtime_config(
            plan,
            model,
            call_cap=model.maximum_generation_cost_usd,
        )
        provider_client = OpenRouterCandidateSelectorClient(
            selector_runtime,
            prompt_template=prompt_template,
            api_key=api_key,
            logical_id=f"stage-0/{model.key}/{plan.case_key}",
            transport=transport_builder(),
            pacer=None,
            send_temperature=model.send_temperature,
            before_provider_call=lambda maximum, current=model: ledger.before_generation(
                current, maximum
            ),
            after_provider_call=lambda actual, current=model: ledger.add(current, actual),
            evidence_root=output / "provider-evidence",
        )
        client = CompactCandidateSelectorClient(provider_client)
        try:
            response = client.select(
                request=canonical_request,
                response_schema=provider_schema,
                repair=None,
            )
        except Exception as exc:
            message = " ".join(str(exc).split())[:500].replace(api_key, "[REDACTED]")
            calls = [item.protected_dict() for item in provider_client.call_records]
            result["provider_calls"] = _safe_call_records(calls)
            result["selector_call_count"] = len(calls)
            result["observed_cost_usd"] = ledger.model_costs[model.key]
            result["classification"] = _failure_classification(
                message,
                str(getattr(exc, "code", None) or "selector_call_failure"),
                route=False,
            )
            result["failure_code"] = str(
                getattr(exc, "code", None) or "selector_call_failure"
            )
            result["message"] = message
            _write_json(model_dir / "result.json", result)
            results.append(result)
            continue

        calls = [item.protected_dict() for item in provider_client.call_records]
        if len(calls) != 1:
            raise EvaluationIntegrityError("Stage 0 selector must perform exactly one call")
        result["provider_calls"] = _safe_call_records(calls)
        result["selector_call_count"] = 1
        result["observed_cost_usd"] = ledger.model_costs[model.key]
        _write_json(model_dir / "provider-calls-protected.json", {"calls": calls})
        _write_json(
            model_dir / "compact-request.json",
            client.compact_requests[-1],
        )

        try:
            validation = validate_candidate_selection(
                response.payload,
                candidates,
                config=ranking,
                evidence_bundle_id=bundle["bundle_id"],
                selection_schema=selection_schema,
            )
        except SelectorEnvelopeError as exc:
            result["classification"] = "model-output-invalid"
            result["selector_outcome"] = "malformed_envelope"
            result["failure_code"] = exc.code
            result["message"] = str(exc)
            _write_json(model_dir / "result.json", result)
            results.append(result)
            continue
        result["selector_validation"] = validation.as_dict()
        if not validation.is_valid:
            result["classification"] = "model-output-invalid"
            result["selector_outcome"] = "selection_rejected"
            result["failure_code"] = "candidate_selection_invalid"
            result["message"] = "the one Stage 0 selection failed the existing contract"
            _write_json(model_dir / "result.json", result)
            results.append(result)
            continue

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
            raise EvaluationIntegrityError(
                "accepted Stage 0 selection reconstructed to an invalid claim plan"
            )
        rendered = render_claim_plan(bundle, claim_plan, plan_validation)
        _write_json(model_dir / "selection.json", selection)
        _write_json(model_dir / "claim-plan.json", claim_plan)
        (model_dir / "rendered-report.md").write_bytes(rendered.markdown)
        result.update(
            {
                "classification": "compatible",
                "selector_outcome": "accepted_initial",
                "selected_candidate_ids": selected_ids,
                "claim_plan_sha256": content_sha256(claim_plan),
                "rendered_markdown_sha256": _sha256_bytes(rendered.markdown),
            }
        )
        _write_json(model_dir / "result.json", result)
        results.append(result)

    if ledger.paid_calls > plan.maximum_paid_calls:
        raise EvaluationIntegrityError("Stage 0 exceeded its paid-call ceiling")
    summary = {
        "version": STAGE0_VERSION,
        "trusted_main_sha": trusted_main_sha,
        "config_path": PurePosixPath(str(config_path)).as_posix(),
        "config_sha256": content_sha256(asdict(plan)),
        "prepared_manifest_sha256": content_sha256(manifest),
        "case_key": plan.case_key,
        "candidate_count": len(candidates),
        "compact_request_id": manifest.get("compact_request_id"),
        "compact_request_bytes": manifest.get("compact_request_bytes"),
        "maximum_route_probes": plan.maximum_route_probes,
        "completed_route_probes": ledger.route_probes,
        "maximum_selector_generations": plan.maximum_selector_generations,
        "completed_selector_generations": ledger.selector_generations,
        "maximum_paid_calls": plan.maximum_paid_calls,
        "completed_paid_calls": ledger.paid_calls,
        "maximum_total_cost_usd": plan.maximum_total_cost_usd,
        "observed_total_cost_usd": ledger.total_cost,
        "model_costs_usd": dict(ledger.model_costs),
        "models": results,
        "compatible_models": [
            row["model"] for row in results if row["classification"] == "compatible"
        ],
        "stage1_authorized": False,
        "winner_selected": False,
        "semantic_repairs": 0,
        "network_retries": 0,
        "automatic_generation": False,
        "publication": False,
        "repository_write": False,
    }
    _write_json(output / STAGE0_RESULTS, {"version": STAGE0_VERSION, "models": results})
    _write_json(output / STAGE0_SUMMARY, summary)
    text = _result_markdown(summary)
    (output / STAGE0_ACTIONS_SUMMARY).write_text(text, encoding="utf-8")
    return summary
