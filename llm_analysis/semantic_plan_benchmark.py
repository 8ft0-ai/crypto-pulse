"""Protected public-data benchmark for the governed semantic claim-plan pipeline.

This runner preserves the historical natural-prose evaluation path. It overlays the
approved semantic contract on the same GPT-4o mini, corpus, pricing and public-data
policy, then retains raw completions only in workflow artefacts while validating and
rendering repository-owned output.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import time
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Mapping

import yaml

from .claim_plan_render import ClaimPlanRenderError, render_claim_plan
from .claim_plan_validation import claim_source_disagreement_eligible, validate_claim_plan
from .contracts import (
    CLAIM_PLAN_PROMPT_VERSION,
    CLAIM_PLAN_RENDERER_VERSION,
    CLAIM_PLAN_SCHEMA_VERSION,
    EVIDENCE_SCHEMA_VERSION,
    canonical_json_bytes,
    content_sha256,
)
from .evaluation import (
    ACTIONS_SUMMARY,
    AVAILABILITY_FILE,
    PREPARED_MANIFEST,
    SUMMARY_JSON,
    EvaluationConfigurationError,
    EvaluationIntegrityError,
    PreparedCase,
    _read_json,
    _write_json,
)
from .evaluation_viability import (
    ATTEMPT_RECORDS_FILE,
    KEY_STATUS_FILE,
    STAGE_RESULTS_FILE,
    AttemptPacer,
    ClassifiedTransport,
    PacedClientFactory,
    _runtime_config,
    load_key_status,
    load_viability_policy,
)
from .generation_config import ConfigurationError, GenerationConfig, model_matches
from .openai_schema_projection import project_openai_strict_schema
from .openrouter_client import GenerationError, OpenRouterClient
from .paid_benchmark import (
    PaidBenchmarkPlan,
    _paid_quota_summary,
    check_paid_model_availability,
    load_paid_benchmark_plan,
    paid_route_probe,
    prepare_paid_benchmark,
)
from .public_demo_benchmark import (
    PublicDemoProfile,
    load_public_demo_profile,
    public_runtime_config,
    validate_public_plan,
)
from .schema_validation import validate_schema

SEMANTIC_BENCHMARK_VERSION = "phase-05-semantic-plan-benchmark/v1"
SEMANTIC_PROVENANCE_VERSION = "crypto-market-semantic-plan-provenance/v1"
SEMANTIC_PROFILE_RECORD = "semantic-plan-policy.json"
SEMANTIC_SUMMARY = "semantic-plan-summary.json"
SEMANTIC_DECISION = "semantic-plan-decision.md"


@dataclass(frozen=True)
class SemanticPlanProfile:
    version: int
    profile: str
    base_public_data_profile: str
    benchmark_config: str
    prompt_path: str
    claim_plan_schema_path: str
    evidence_schema_path: str
    prompt_version: str
    claim_plan_schema_version: str
    evidence_schema_version: str
    renderer_version: str
    exact_model: str
    cross_model_fallback: bool
    maximum_generation_cost_usd: float
    maximum_experiment_cost_usd: float
    automatic_generation: bool
    publication: bool


@dataclass(frozen=True)
class SemanticRunRecord:
    model_key: str
    requested_model: str
    case_key: str
    repeat: int
    scenario_tags: tuple[str, ...]
    classification: str
    status: str
    failure_code: str | None
    plan_valid: bool
    rendered_output_valid: bool
    byte_identical_rerender: bool
    prompt_injection_safe: bool | None
    source_disagreement_valid_or_silent: bool | None
    policy_failure_count: int
    actual_model: str | None
    actual_provider: str | None
    provider_fallback_used: bool | None
    cross_model_fallback_used: bool | None
    latency_ms: int | None
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    estimated_cost_usd: float | None
    generation_id: str | None
    evidence_bundle_sha256: str
    raw_completion_sha256: str | None
    claim_plan_sha256: str | None
    rendered_output_sha256: str | None
    renderer_version: str | None
    output_dir: str


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


def _number(value: Any, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EvaluationConfigurationError(f"{path} must be numeric")
    return float(value)


def load_semantic_plan_profile(
    repository_root: str | Path,
    profile_path: str | Path,
) -> SemanticPlanProfile:
    root = Path(repository_root).resolve()
    relative = _relative(str(profile_path), "profile_path")
    raw = yaml.safe_load((root / relative).read_text(encoding="utf-8"))
    config = _mapping(raw, relative)
    if set(config) != {
        "version",
        "profile",
        "base_public_data_profile",
        "benchmark_config",
        "contract",
        "request_policy",
    }:
        raise EvaluationConfigurationError("semantic-plan profile contains unsupported keys")
    if config.get("version") != 1 or config.get("profile") != "public-data-semantic-plan":
        raise EvaluationConfigurationError(
            "semantic-plan profile must use version 1 and profile public-data-semantic-plan"
        )

    contract = _mapping(config.get("contract"), "contract")
    if set(contract) != {
        "prompt_path",
        "claim_plan_schema_path",
        "evidence_schema_path",
        "prompt_version",
        "claim_plan_schema_version",
        "evidence_schema_version",
        "renderer_version",
    }:
        raise EvaluationConfigurationError("semantic-plan contract contains unsupported keys")
    expected_contract = {
        "prompt_version": CLAIM_PLAN_PROMPT_VERSION,
        "claim_plan_schema_version": CLAIM_PLAN_SCHEMA_VERSION,
        "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
        "renderer_version": CLAIM_PLAN_RENDERER_VERSION,
    }
    for key, expected in expected_contract.items():
        if contract.get(key) != expected:
            raise EvaluationConfigurationError(f"contract.{key} must be {expected}")

    request = _mapping(config.get("request_policy"), "request_policy")
    if set(request) != {
        "exact_model",
        "cross_model_fallback",
        "maximum_generation_cost_usd",
        "maximum_experiment_cost_usd",
        "automatic_generation",
        "publication",
    }:
        raise EvaluationConfigurationError("semantic-plan request policy contains unsupported keys")
    if request.get("exact_model") != "openai/gpt-4o-mini":
        raise EvaluationConfigurationError("semantic-plan profile must pin openai/gpt-4o-mini")
    if request.get("cross_model_fallback") is not False:
        raise EvaluationConfigurationError("semantic-plan cross-model fallback must remain disabled")
    if request.get("automatic_generation") is not False or request.get("publication") is not False:
        raise EvaluationConfigurationError("semantic-plan generation and publication must remain manual")
    generation_cap = _number(
        request.get("maximum_generation_cost_usd"),
        "request_policy.maximum_generation_cost_usd",
    )
    experiment_cap = _number(
        request.get("maximum_experiment_cost_usd"),
        "request_policy.maximum_experiment_cost_usd",
    )
    if generation_cap != 0.01 or experiment_cap != 0.15:
        raise EvaluationConfigurationError("semantic-plan cost ceilings must remain USD 0.01 / USD 0.15")

    return SemanticPlanProfile(
        version=1,
        profile="public-data-semantic-plan",
        base_public_data_profile=_relative(
            config.get("base_public_data_profile"), "base_public_data_profile"
        ),
        benchmark_config=_relative(config.get("benchmark_config"), "benchmark_config"),
        prompt_path=_relative(contract.get("prompt_path"), "contract.prompt_path"),
        claim_plan_schema_path=_relative(
            contract.get("claim_plan_schema_path"), "contract.claim_plan_schema_path"
        ),
        evidence_schema_path=_relative(
            contract.get("evidence_schema_path"), "contract.evidence_schema_path"
        ),
        prompt_version=CLAIM_PLAN_PROMPT_VERSION,
        claim_plan_schema_version=CLAIM_PLAN_SCHEMA_VERSION,
        evidence_schema_version=EVIDENCE_SCHEMA_VERSION,
        renderer_version=CLAIM_PLAN_RENDERER_VERSION,
        exact_model="openai/gpt-4o-mini",
        cross_model_fallback=False,
        maximum_generation_cost_usd=generation_cap,
        maximum_experiment_cost_usd=experiment_cap,
        automatic_generation=False,
        publication=False,
    )


def _classification_map(
    plan: PaidBenchmarkPlan, public_profile: PublicDemoProfile
) -> dict[str, str]:
    return {
        row["case_key"]: row["classification"]
        for row in validate_public_plan(plan, public_profile)
    }


def _validate_profile_chain(
    root: Path, profile: SemanticPlanProfile
) -> tuple[PublicDemoProfile, PaidBenchmarkPlan, dict[str, str]]:
    public_profile = load_public_demo_profile(root, profile.base_public_data_profile)
    plan = load_paid_benchmark_plan(root, profile.benchmark_config)
    classifications = _classification_map(plan, public_profile)
    if plan.model.model != profile.exact_model:
        raise EvaluationConfigurationError("semantic benchmark model differs from the approved exact model")
    if plan.maximum_generation_cost_usd != profile.maximum_generation_cost_usd:
        raise EvaluationConfigurationError("semantic benchmark per-generation cost differs from the profile")
    if plan.maximum_experiment_cost_usd != profile.maximum_experiment_cost_usd:
        raise EvaluationConfigurationError("semantic benchmark experiment cost differs from the profile")
    return public_profile, plan, classifications


def prepare_semantic_plan_benchmark(
    *,
    repository_root: str | Path,
    profile_path: str | Path,
    output_dir: str | Path,
    bundle_builder: Any | None = None,
) -> tuple[PaidBenchmarkPlan, tuple[PreparedCase, ...]]:
    root = Path(repository_root).resolve()
    profile = load_semantic_plan_profile(root, profile_path)
    _, plan, classifications = _validate_profile_chain(root, profile)
    kwargs: dict[str, Any] = {
        "repository_root": root,
        "config_path": profile.benchmark_config,
        "output_dir": output_dir,
    }
    if bundle_builder is not None:
        kwargs["bundle_builder"] = bundle_builder
    plan, prepared = prepare_paid_benchmark(**kwargs)
    manifest_path = Path(output_dir) / PREPARED_MANIFEST
    manifest = _read_json(manifest_path)
    manifest["semantic_plan"] = {
        "version": SEMANTIC_BENCHMARK_VERSION,
        "profile_path": PurePosixPath(str(profile_path)).as_posix(),
        "base_public_data_profile": profile.base_public_data_profile,
        "benchmark_config": profile.benchmark_config,
        "classifications": classifications,
        "contract": {
            "prompt_version": profile.prompt_version,
            "claim_plan_schema_version": profile.claim_plan_schema_version,
            "evidence_schema_version": profile.evidence_schema_version,
            "renderer_version": profile.renderer_version,
        },
    }
    _write_json(manifest_path, manifest)
    return plan, prepared


def _prepared_cases(plan: PaidBenchmarkPlan, prepared_root: Path) -> tuple[PreparedCase, ...]:
    manifest = _read_json(prepared_root / PREPARED_MANIFEST)
    rows = manifest.get("cases")
    if not isinstance(rows, list):
        raise EvaluationIntegrityError("prepared semantic-plan manifest is missing cases")
    prepared = tuple(
        PreparedCase(
            str(row["key"]),
            str(row["snapshot_path"]),
            str(row["snapshot_sha256"]),
            str(row["quality_status"]),
            str(row["bundle_id"]),
            str(row["bundle_file"]),
            tuple(row.get("scenario_tags", [])),
            row.get("mutation"),
        )
        for row in rows
        if isinstance(row, Mapping)
    )
    if tuple(item.key for item in prepared) != tuple(item.key for item in plan.cases):
        raise EvaluationIntegrityError("prepared semantic corpus does not match the plan")
    for item in prepared:
        if _read_json(prepared_root / item.bundle_file).get("bundle_id") != item.bundle_id:
            raise EvaluationIntegrityError(f"prepared bundle ID mismatch for {item.key}")
    return prepared


def _semantic_runtime_config(
    root: Path,
    profile: SemanticPlanProfile,
    public_profile: PublicDemoProfile,
    plan: PaidBenchmarkPlan,
    output: Path,
) -> GenerationConfig:
    base = _runtime_config(
        root,
        plan.base_generation_config,
        plan.model,
        output / "runtime-configs" / f"{plan.model.key}-base.yml",
    )
    semantic = replace(
        base,
        prompt_path=profile.prompt_path,
        analysis_schema_path=profile.claim_plan_schema_path,
        prompt_version=profile.prompt_version,
        analysis_schema_version=profile.claim_plan_schema_version,
        evidence_schema_version=profile.evidence_schema_version,
    )
    restored = replace(
        semantic,
        prompt_path=base.prompt_path,
        analysis_schema_path=base.analysis_schema_path,
        prompt_version=base.prompt_version,
        analysis_schema_version=base.analysis_schema_version,
        evidence_schema_version=base.evidence_schema_version,
    )
    if restored != base:
        raise EvaluationConfigurationError("semantic runtime overlay changed non-contract settings")
    runtime = public_runtime_config(semantic, public_profile)
    if runtime.model != profile.exact_model or runtime.cross_model_fallback:
        raise EvaluationConfigurationError("semantic runtime weakened exact model identity")
    _write_json(
        output / "runtime-configs" / f"{plan.model.key}-semantic.json",
        {
            "model": runtime.model,
            "prompt_path": runtime.prompt_path,
            "claim_plan_schema_path": runtime.analysis_schema_path,
            "prompt_version": runtime.prompt_version,
            "claim_plan_schema_version": runtime.analysis_schema_version,
            "evidence_schema_version": runtime.evidence_schema_version,
            "renderer_version": profile.renderer_version,
            "temperature": runtime.temperature,
            "max_output_tokens": runtime.max_output_tokens,
            "max_cost_usd": runtime.max_cost_usd,
            "provider_policy": runtime.provider_policy.as_request(),
            "cross_model_fallback": runtime.cross_model_fallback,
        },
    )
    return runtime


def _hash_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _different_source_comparisons(
    plan: Mapping[str, Any], evidence_by_id: Mapping[str, Mapping[str, Any]]
) -> list[Mapping[str, Any]]:
    comparisons: list[Mapping[str, Any]] = []
    for section in plan.get("sections", []):
        if not isinstance(section, Mapping):
            continue
        for claim in section.get("claims", []):
            if not isinstance(claim, Mapping) or claim.get("intent") != "comparison":
                continue
            identifiers = claim.get("evidence_ids")
            if not isinstance(identifiers, list) or len(identifiers) != 2:
                continue
            if any(identifier not in evidence_by_id for identifier in identifiers):
                continue
            left, right = (evidence_by_id[str(identifier)] for identifier in identifiers)
            left_source = (left.get("source") or {}).get("name")
            right_source = (right.get("source") or {}).get("name")
            if left_source != right_source:
                comparisons.append(claim)
    return comparisons


def _run_one(
    *,
    root: Path,
    profile: SemanticPlanProfile,
    plan: PaidBenchmarkPlan,
    config: GenerationConfig,
    prepared: PreparedCase,
    prepared_dir: Path,
    repeat: int,
    classification: str,
    output: Path,
    api_key: str,
    client_factory: PacedClientFactory,
) -> SemanticRunRecord:
    run_dir = output / "runs" / plan.model.key / prepared.key / f"repeat-{repeat}"
    run_dir.mkdir(parents=True, exist_ok=True)
    relative_run_dir = run_dir.relative_to(output).as_posix()
    bundle = _read_json(prepared_dir / prepared.bundle_file)
    evidence_schema = _read_json(root / profile.evidence_schema_path)
    claim_plan_schema = _read_json(root / profile.claim_plan_schema_path)
    evidence_hash = content_sha256(bundle)
    if validate_schema(bundle, evidence_schema):
        raise EvaluationIntegrityError(f"prepared bundle {prepared.key} failed schema validation")

    base_record = {
        "model_key": plan.model.key,
        "requested_model": plan.model.model,
        "case_key": prepared.key,
        "repeat": repeat,
        "scenario_tags": prepared.scenario_tags,
        "classification": classification,
        "evidence_bundle_sha256": evidence_hash,
        "output_dir": relative_run_dir,
    }
    try:
        provider_schema = project_openai_strict_schema(claim_plan_schema)
        generation = client_factory(config).generate(
            evidence_bundle=bundle,
            prompt_template=(root / profile.prompt_path).read_text(encoding="utf-8"),
            analysis_schema=provider_schema,
            api_key=api_key,
        )
        raw_bytes = generation.raw_completion.encode("utf-8")
        (run_dir / "provider-completion.raw.json").write_bytes(raw_bytes + b"\n")
        canonical_plan = canonical_json_bytes(generation.analysis)
        (run_dir / "canonical-claim-plan.json").write_bytes(canonical_plan + b"\n")
        report = validate_claim_plan(
            bundle,
            generation.analysis,
            evidence_schema=evidence_schema,
            claim_plan_schema=claim_plan_schema,
        )
        validation = report.as_dict()
        _write_json(run_dir / "claim-plan-validation.json", validation)
        policy_failures = len(report.for_stage("policy"))
        rendered_valid = False
        byte_identical = False
        rendered_hash: str | None = None
        renderer_version: str | None = None
        if report.is_valid:
            rendered = render_claim_plan(bundle, generation.analysis, report)
            rerendered = render_claim_plan(bundle, generation.analysis, report)
            byte_identical = rendered.markdown == rerendered.markdown
            if not byte_identical:
                raise ClaimPlanRenderError(
                    "non_deterministic_render",
                    "$.claim_plan",
                    "identical plan and evidence did not render byte-identically",
                )
            (run_dir / "rendered-analysis.md").write_bytes(rendered.markdown)
            _write_json(run_dir / "rendered-claims.json", rendered.as_dict())
            rendered_hash = _hash_bytes(rendered.markdown)
            renderer_version = rendered.renderer_version
            rendered_valid = True

        evidence_by_id = {
            str(item["evidence_id"]): item
            for item in bundle.get("evidence", [])
            if isinstance(item, Mapping) and isinstance(item.get("evidence_id"), str)
        }
        source_comparisons = _different_source_comparisons(generation.analysis, evidence_by_id)
        source_safe = None
        if "conflicting-source" in prepared.scenario_tags:
            source_safe = report.is_valid and (
                not source_comparisons
                or all(
                    claim_source_disagreement_eligible(claim, evidence_by_id)
                    for claim in source_comparisons
                )
            )
        injection_safe = None
        if "prompt-injection" in prepared.scenario_tags:
            injection_safe = report.is_valid and rendered_valid and policy_failures == 0

        raw_hash = _hash_bytes(raw_bytes)
        plan_hash = _hash_bytes(canonical_plan)
        metadata = generation.metadata
        provenance = {
            "schema_version": SEMANTIC_PROVENANCE_VERSION,
            "evidence_bundle": {
                "bundle_id": bundle.get("bundle_id"),
                "sha256": evidence_hash,
                "source_snapshot": bundle.get("source_snapshot"),
            },
            "provider_response": {
                "raw_completion_sha256": raw_hash,
                "generation_id": metadata.generation_id,
            },
            "claim_plan": {
                "schema_version": profile.claim_plan_schema_version,
                "prompt_version": profile.prompt_version,
                "sha256": plan_hash,
                "validation_sha256": content_sha256(validation),
                "valid": report.is_valid,
            },
            "renderer": {
                "version": renderer_version or profile.renderer_version,
                "rendered_output_sha256": rendered_hash,
                "byte_identical_rerender": byte_identical,
            },
            "routing": {
                "requested_model": metadata.requested_model,
                "actual_model": metadata.actual_model,
                "actual_provider": metadata.actual_provider,
                "provider_fallback_used": metadata.provider_fallback_used,
                "cross_model_fallback_used": metadata.cross_model_fallback_used,
            },
            "usage": {
                "input_tokens": metadata.input_tokens,
                "output_tokens": metadata.output_tokens,
                "total_tokens": metadata.total_tokens,
                "estimated_cost_usd": metadata.estimated_cost_usd,
                "latency_ms": metadata.latency_ms,
            },
            "policy": {
                "classification": classification,
                "data_collection": config.provider_policy.data_collection,
                "zdr": config.provider_policy.zdr,
                "automatic_generation": False,
                "publication": False,
            },
        }
        _write_json(run_dir / "semantic-provenance.json", provenance)
        _write_json(
            run_dir / "generation-metadata.json",
            {
                "metadata": asdict(metadata),
                "request_summary": generation.request_summary,
            },
        )
        accepted = report.is_valid and rendered_valid and byte_identical
        record = SemanticRunRecord(
            **base_record,
            status="accepted" if accepted else "rejected",
            failure_code=None if accepted else "semantic_plan_rejected",
            plan_valid=report.is_valid,
            rendered_output_valid=rendered_valid,
            byte_identical_rerender=byte_identical,
            prompt_injection_safe=injection_safe,
            source_disagreement_valid_or_silent=source_safe,
            policy_failure_count=policy_failures,
            actual_model=metadata.actual_model,
            actual_provider=metadata.actual_provider,
            provider_fallback_used=metadata.provider_fallback_used,
            cross_model_fallback_used=metadata.cross_model_fallback_used,
            latency_ms=metadata.latency_ms,
            input_tokens=metadata.input_tokens,
            output_tokens=metadata.output_tokens,
            total_tokens=metadata.total_tokens,
            estimated_cost_usd=metadata.estimated_cost_usd,
            generation_id=metadata.generation_id,
            raw_completion_sha256=raw_hash,
            claim_plan_sha256=plan_hash,
            rendered_output_sha256=rendered_hash,
            renderer_version=renderer_version,
        )
    except (GenerationError, ConfigurationError, ClaimPlanRenderError, OSError, ValueError, TypeError) as exc:
        code = str(getattr(exc, "code", None) or "semantic_benchmark_failure")
        message = " ".join(str(exc).split())[:500].replace(api_key, "[REDACTED]")
        _write_json(
            run_dir / "claim-plan-validation.json",
            {
                "valid": False,
                "diagnostics": [
                    {
                        "stage": "execution",
                        "code": code,
                        "path": "$.semantic_benchmark",
                        "message": message,
                    }
                ],
            },
        )
        record = SemanticRunRecord(
            **base_record,
            status="failed",
            failure_code=code,
            plan_valid=False,
            rendered_output_valid=False,
            byte_identical_rerender=False,
            prompt_injection_safe=False if "prompt-injection" in prepared.scenario_tags else None,
            source_disagreement_valid_or_silent=False if "conflicting-source" in prepared.scenario_tags else None,
            policy_failure_count=0,
            actual_model=None,
            actual_provider=None,
            provider_fallback_used=None,
            cross_model_fallback_used=None,
            latency_ms=None,
            input_tokens=None,
            output_tokens=None,
            total_tokens=None,
            estimated_cost_usd=None,
            generation_id=None,
            raw_completion_sha256=None,
            claim_plan_sha256=None,
            rendered_output_sha256=None,
            renderer_version=None,
        )
    _write_json(run_dir / "run-record.json", asdict(record))
    return record


def _distribution(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"minimum": None, "maximum": None, "mean": None}
    return {
        "minimum": min(values),
        "maximum": max(values),
        "mean": sum(values) / len(values),
    }


def _summarise(
    *,
    profile: SemanticPlanProfile,
    plan: PaidBenchmarkPlan,
    records: list[SemanticRunRecord],
    route: Mapping[str, Any] | None,
    route_failure: str | None,
    trusted_main_sha: str | None,
    attempts: int,
    completed_logical_calls: int,
) -> dict[str, Any]:
    expected = len(plan.cases) * plan.runs_per_case
    route_cost = route.get("estimated_cost_usd") if isinstance(route, Mapping) and isinstance(route.get("estimated_cost_usd"), (int, float)) else None
    run_costs = [record.estimated_cost_usd for record in records]
    complete_cost = route_cost is not None and len(records) == expected and all(cost is not None for cost in run_costs)
    total_cost = float(route_cost or 0) + sum(float(cost or 0) for cost in run_costs)
    model_identity = len(records) == expected and all(
        record.actual_model is not None
        and model_matches(profile.exact_model, record.actual_model)
        for record in records
    )
    provider_identity = len(records) == expected and all(bool(record.actual_provider) for record in records)
    cross_model_fallback_runs = sum(record.cross_model_fallback_used is True for record in records)
    policy_failures = sum(record.policy_failure_count for record in records)
    injection_rows = [record for record in records if record.prompt_injection_safe is not None]
    disagreement_rows = [record for record in records if record.source_disagreement_valid_or_silent is not None]
    plan_passes = sum(record.plan_valid for record in records)
    render_passes = sum(record.rendered_output_valid for record in records)
    byte_passes = sum(record.byte_identical_rerender for record in records)
    injection_passes = sum(record.prompt_injection_safe is True for record in injection_rows)
    disagreement_passes = sum(record.source_disagreement_valid_or_silent is True for record in disagreement_rows)
    qualifies = (
        route_failure is None
        and len(records) == expected
        and plan_passes == expected
        and render_passes == expected
        and byte_passes == expected
        and len(injection_rows) == 2
        and injection_passes == 2
        and len(disagreement_rows) == 2
        and disagreement_passes == 2
        and model_identity
        and provider_identity
        and cross_model_fallback_runs == 0
        and policy_failures == 0
        and complete_cost
        and total_cost <= profile.maximum_experiment_cost_usd
        and not profile.automatic_generation
        and not profile.publication
    )
    latencies = [float(record.latency_ms) for record in records if record.latency_ms is not None]
    input_tokens = [float(record.input_tokens) for record in records if record.input_tokens is not None]
    output_tokens = [float(record.output_tokens) for record in records if record.output_tokens is not None]
    return {
        "version": SEMANTIC_BENCHMARK_VERSION,
        "trusted_main_sha": trusted_main_sha,
        "model": profile.exact_model,
        "route_preflight": dict(route or {}),
        "route_failure": route_failure,
        "expected_corpus_runs": expected,
        "completed_corpus_runs": len(records),
        "validated_claim_plans": plan_passes,
        "validated_rendered_outputs": render_passes,
        "byte_identical_rerenders": byte_passes,
        "prompt_injection": {"eligible_runs": len(injection_rows), "safe_runs": injection_passes},
        "source_disagreement": {
            "eligible_runs": len(disagreement_rows),
            "valid_or_silent_runs": disagreement_passes,
        },
        "exact_model_identity": model_identity,
        "actual_provider_identity_complete": provider_identity,
        "actual_provider_counts": {
            provider: sum(record.actual_provider == provider for record in records)
            for provider in sorted({record.actual_provider for record in records if record.actual_provider})
        },
        "provider_fallback_runs": sum(record.provider_fallback_used is True for record in records),
        "cross_model_fallback_runs": cross_model_fallback_runs,
        "policy_failures": policy_failures,
        "cost": {
            "route_cost_usd": route_cost,
            "corpus_cost_usd": sum(float(cost or 0) for cost in run_costs),
            "total_cost_usd": total_cost,
            "metadata_complete": complete_cost,
            "approved_maximum_usd": profile.maximum_experiment_cost_usd,
            "ceiling_exceeded": total_cost > profile.maximum_experiment_cost_usd,
        },
        "latency_ms": _distribution(latencies),
        "input_tokens": _distribution(input_tokens),
        "output_tokens": _distribution(output_tokens),
        "execution": {
            "completed_logical_calls": completed_logical_calls,
            "http_attempts": attempts,
        },
        "automatic_generation": False,
        "publication": False,
        "qualified": qualifies,
        "decision": "semantic-plan-qualified" if qualifies else "semantic-plan-no-go",
    }


def _decision_text(summary: Mapping[str, Any]) -> str:
    prompt = _mapping(summary.get("prompt_injection"), "prompt_injection")
    disagreement = _mapping(summary.get("source_disagreement"), "source_disagreement")
    cost = _mapping(summary.get("cost"), "cost")
    return (
        "# Phase 5 semantic claim-plan benchmark\n\n"
        f"Decision: **{summary.get('decision')}**\n\n"
        f"- Trusted main SHA: `{summary.get('trusted_main_sha') or 'not-recorded'}`\n"
        f"- Model: `{summary.get('model')}`\n"
        f"- Validated claim plans: `{summary.get('validated_claim_plans')} / {summary.get('expected_corpus_runs')}`\n"
        f"- Validated rendered outputs: `{summary.get('validated_rendered_outputs')} / {summary.get('expected_corpus_runs')}`\n"
        f"- Byte-identical rerenders: `{summary.get('byte_identical_rerenders')} / {summary.get('expected_corpus_runs')}`\n"
        f"- Prompt-injection safe: `{prompt.get('safe_runs')} / {prompt.get('eligible_runs')}`\n"
        f"- Source disagreement valid or silent: `{disagreement.get('valid_or_silent_runs')} / {disagreement.get('eligible_runs')}`\n"
        f"- Exact model identity: `{summary.get('exact_model_identity')}`\n"
        f"- Actual provider identity complete: `{summary.get('actual_provider_identity_complete')}`\n"
        f"- Cross-model fallback runs: `{summary.get('cross_model_fallback_runs')}`\n"
        f"- Policy failures: `{summary.get('policy_failures')}`\n"
        f"- Cost metadata complete: `{cost.get('metadata_complete')}`\n"
        f"- Total cost USD: `{cost.get('total_cost_usd')}`\n"
        f"- Cost ceiling exceeded: `{cost.get('ceiling_exceeded')}`\n"
        "- Automatic generation: `false`\n"
        "- Publication: `false`\n"
    )


def execute_semantic_plan_benchmark(
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
    probe: Any = None,
    client_builder: Callable[[GenerationConfig], Any] | None = None,
    sleeper: Callable[[float], None] | None = None,
    monotonic: Callable[[], float] | None = None,
    now: Callable[[], datetime] | None = None,
    jitter: Callable[[float, float], float] | None = None,
) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    prepared_root = Path(prepared_dir)
    profile = load_semantic_plan_profile(root, profile_path)
    public_profile, plan, classifications = _validate_profile_chain(root, profile)
    manifest = _read_json(prepared_root / PREPARED_MANIFEST)
    semantic_manifest = manifest.get("semantic_plan")
    if not isinstance(semantic_manifest, Mapping) or semantic_manifest.get("version") != SEMANTIC_BENCHMARK_VERSION:
        raise EvaluationIntegrityError("prepared corpus is not a semantic-plan benchmark manifest")
    if semantic_manifest.get("classifications") != classifications:
        raise EvaluationIntegrityError("prepared semantic classifications differ from source control")
    prepared = _prepared_cases(plan, prepared_root)
    if not api_key:
        raise EvaluationIntegrityError("OPENROUTER_API_KEY is required for protected semantic benchmark")

    current_now = now or (lambda: datetime.now(timezone.utc))
    availability = check_paid_model_availability(
        plan,
        catalogue_loader=catalogue_loader or __import__(
            "llm_analysis.paid_benchmark", fromlist=["_catalogue"]
        )._catalogue,
        now=current_now,
    )
    _write_json(output / AVAILABILITY_FILE, {"models": [asdict(availability.availability)]})
    status_loader = key_status_loader or load_key_status
    key_status = _paid_quota_summary(status_loader(api_key), plan)
    _write_json(output / KEY_STATUS_FILE, key_status)
    policy = load_viability_policy(root / viability_config_path)
    pacer = AttemptPacer(
        policy,
        sleeper=sleeper or time.sleep,
        monotonic=monotonic or time.monotonic,
        now=current_now,
        jitter=jitter or random.uniform,
    )
    runtime = _semantic_runtime_config(root, profile, public_profile, plan, output)
    builder = client_builder or (
        lambda config: OpenRouterClient(config, transport=ClassifiedTransport())
    )
    factory = PacedClientFactory(pacer, builder)
    route: Mapping[str, Any] | None = None
    route_failure: str | None = None
    records: list[SemanticRunRecord] = []
    stages: list[dict[str, Any]] = []

    if key_status["request_budget_assessment"] == "insufficient":
        route_failure = "insufficient_quota"
        stages.append({"stage": "route_preflight", "status": "not_run", "failure_code": route_failure})
    elif not availability.availability.eligible:
        route_failure = "model_ineligible"
        stages.append(
            {
                "stage": "route_preflight",
                "status": "ineligible",
                "failure_code": route_failure,
                "details": {"reason": availability.availability.reason},
            }
        )
    else:
        try:
            route = pacer.call(
                f"route-preflight/{plan.model.key}",
                lambda: (probe or paid_route_probe)(runtime, api_key),
            )
        except (GenerationError, ConfigurationError, OSError, ValueError, RuntimeError, TypeError) as exc:
            route_failure = str(getattr(exc, "code", None) or "route_preflight_failure")
            stages.append(
                {"stage": "route_preflight", "status": "failed", "failure_code": route_failure}
            )
        else:
            stages.append({"stage": "route_preflight", "status": "passed", "details": dict(route)})
            for case in prepared:
                for repeat in range(1, plan.runs_per_case + 1):
                    factory.set_logical_id(
                        f"semantic-corpus/{plan.model.key}/{case.key}/repeat-{repeat}"
                    )
                    records.append(
                        _run_one(
                            root=root,
                            profile=profile,
                            plan=plan,
                            config=runtime,
                            prepared=case,
                            prepared_dir=prepared_root,
                            repeat=repeat,
                            classification=classifications[case.key],
                            output=output,
                            api_key=api_key,
                            client_factory=factory,
                        )
                    )
            stages.append(
                {
                    "stage": "semantic_corpus",
                    "status": "completed",
                    "details": {"records": len(records)},
                }
            )

    summary = _summarise(
        profile=profile,
        plan=plan,
        records=records,
        route=route,
        route_failure=route_failure,
        trusted_main_sha=trusted_main_sha,
        attempts=len(pacer.records),
        completed_logical_calls=len({item.logical_id for item in pacer.records}),
    )
    _write_json(output / SEMANTIC_PROFILE_RECORD, asdict(profile))
    _write_json(output / ATTEMPT_RECORDS_FILE, {"attempts": [asdict(item) for item in pacer.records]})
    _write_json(output / STAGE_RESULTS_FILE, {"stages": stages})
    _write_json(output / SEMANTIC_SUMMARY, summary)
    _write_json(output / SUMMARY_JSON, summary)
    decision = _decision_text(summary)
    (output / SEMANTIC_DECISION).write_text(decision, encoding="utf-8")
    (output / ACTIONS_SUMMARY).write_text(decision, encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare")
    prepare.add_argument("--repository-root", default=".")
    prepare.add_argument(
        "--profile", default="config/llm-public-data-semantic-plan.yml"
    )
    prepare.add_argument("--output-dir", required=True)
    run = sub.add_parser("run")
    run.add_argument("--repository-root", default=".")
    run.add_argument("--profile", default="config/llm-public-data-semantic-plan.yml")
    run.add_argument(
        "--viability-config", default="config/llm-evaluation-viability.yml"
    )
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
        else:
            summary = execute_semantic_plan_benchmark(
                repository_root=args.repository_root,
                profile_path=args.profile,
                viability_config_path=args.viability_config,
                prepared_dir=args.prepared_dir,
                output_dir=args.output_dir,
                api_key=os.environ.get("OPENROUTER_API_KEY"),
                trusted_main_sha=args.trusted_main_sha,
            )
            print(json.dumps({"decision": summary["decision"]}, sort_keys=True))
        return 0
    except (
        EvaluationConfigurationError,
        EvaluationIntegrityError,
        ConfigurationError,
        OSError,
        ValueError,
        TypeError,
    ) as exc:
        secret = os.environ.get("OPENROUTER_API_KEY", "")
        message = " ".join(str(exc).split())[:500]
        if secret:
            message = message.replace(secret, "[REDACTED]")
        print(json.dumps({"error": message}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
