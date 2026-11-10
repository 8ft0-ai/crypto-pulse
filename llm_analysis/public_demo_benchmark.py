"""Bounded GPT-4o mini benchmark for explicitly public market data."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass, replace
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

import yaml

from .evaluation import (
    ACTIONS_SUMMARY,
    DECISION_MARKDOWN,
    PREPARED_MANIFEST,
    SUMMARY_JSON,
    EvaluationConfigurationError,
    EvaluationIntegrityError,
    _read_json,
    _write_json,
)
from .evaluation_viability import ClassifiedTransport
from .generation_config import ConfigurationError, GenerationConfig
from .openrouter_client import OpenRouterClient
from .paid_benchmark import (
    PaidBenchmarkPlan,
    execute_paid_benchmark,
    load_paid_benchmark_plan,
    paid_route_probe,
    prepare_paid_benchmark,
)

PUBLIC_DEMO_VERSION = "phase-05-public-data-demo/v1"
PUBLIC_DEMO_POLICY_FILE = "public-data-demo-policy.json"


@dataclass(frozen=True)
class PublicDemoProfile:
    version: int
    profile: str
    benchmark_config: str
    allowed_classifications: tuple[str, ...]
    allowed_snapshot_prefix: str
    prohibited_classifications: tuple[str, ...]
    zdr: bool
    data_collection: str
    ordinary_provider_retention_accepted: bool
    documented_maximum_abuse_monitoring_days: int
    rationale: str
    structured_output: bool
    cross_model_fallback: bool
    automatic_generation: bool
    publication: bool
    openrouter_prompt_logging_enabled_by_repository: bool
    store_parameter: str


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


def _string_tuple(value: Any, path: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value or any(not isinstance(item, str) or not item.strip() for item in value):
        raise EvaluationConfigurationError(f"{path} must be a non-empty list of strings")
    result = tuple(item.strip() for item in value)
    if len(set(result)) != len(result):
        raise EvaluationConfigurationError(f"{path} must not contain duplicates")
    return result


def load_public_demo_profile(repository_root: str | Path, profile_path: str | Path) -> PublicDemoProfile:
    root = Path(repository_root).resolve()
    profile_rel = _relative(str(profile_path), "profile_path")
    raw = yaml.safe_load((root / profile_rel).read_text(encoding="utf-8"))
    config = _mapping(raw, profile_rel)
    if set(config) != {"version", "profile", "benchmark_config", "input_policy", "provider_policy", "request_policy"}:
        raise EvaluationConfigurationError("public demo profile contains unsupported keys")
    if config.get("version") != 1 or config.get("profile") != "public-data-demo":
        raise EvaluationConfigurationError("public demo profile must use version 1 and profile public-data-demo")

    input_policy = _mapping(config.get("input_policy"), "input_policy")
    if set(input_policy) != {"allowed_classifications", "allowed_snapshot_prefix", "prohibited_classifications"}:
        raise EvaluationConfigurationError("input_policy contains unsupported keys")
    allowed = _string_tuple(input_policy.get("allowed_classifications"), "input_policy.allowed_classifications")
    if set(allowed) != {"public-market-data", "evaluation-only"}:
        raise EvaluationConfigurationError("public demo allows only public-market-data and evaluation-only classifications")
    prohibited = _string_tuple(input_policy.get("prohibited_classifications"), "input_policy.prohibited_classifications")
    required_prohibited = {"customer", "personal", "credential", "internal", "confidential", "sensitive"}
    if not required_prohibited.issubset(set(prohibited)):
        raise EvaluationConfigurationError("public demo prohibited classifications are incomplete")
    prefix = _string(input_policy.get("allowed_snapshot_prefix"), "input_policy.allowed_snapshot_prefix")
    if prefix != "data/crypto/hourly/":
        raise EvaluationConfigurationError("public demo snapshot prefix must remain data/crypto/hourly/")

    provider = _mapping(config.get("provider_policy"), "provider_policy")
    if set(provider) != {"zdr", "data_collection", "ordinary_provider_retention_accepted", "documented_maximum_abuse_monitoring_days", "rationale"}:
        raise EvaluationConfigurationError("provider_policy contains unsupported keys")
    if provider.get("zdr") is not False:
        raise EvaluationConfigurationError("public demo provider_policy.zdr must be false")
    if provider.get("data_collection") != "deny":
        raise EvaluationConfigurationError("public demo data_collection must remain deny")
    if provider.get("ordinary_provider_retention_accepted") is not True:
        raise EvaluationConfigurationError("public demo must explicitly accept ordinary provider retention")
    retention_days = provider.get("documented_maximum_abuse_monitoring_days")
    if retention_days != 30:
        raise EvaluationConfigurationError("documented maximum abuse-monitoring retention must be 30 days")

    request = _mapping(config.get("request_policy"), "request_policy")
    expected_request_keys = {
        "structured_output",
        "cross_model_fallback",
        "automatic_generation",
        "publication",
        "openrouter_prompt_logging_enabled_by_repository",
        "store_parameter",
    }
    if set(request) != expected_request_keys:
        raise EvaluationConfigurationError("request_policy contains unsupported keys")
    if request.get("structured_output") is not True:
        raise EvaluationConfigurationError("structured output must remain required")
    if request.get("cross_model_fallback") is not False:
        raise EvaluationConfigurationError("cross-model fallback must remain disabled")
    if request.get("automatic_generation") is not False or request.get("publication") is not False:
        raise EvaluationConfigurationError("public demo must remain manual and non-publishing")
    if request.get("openrouter_prompt_logging_enabled_by_repository") is not False:
        raise EvaluationConfigurationError("repository prompt logging must remain disabled")
    store_parameter = _string(request.get("store_parameter"), "request_policy.store_parameter")
    if store_parameter != "unsupported-by-openrouter-chat-completions-contract":
        raise EvaluationConfigurationError("store parameter status must match the OpenRouter contract")

    return PublicDemoProfile(
        version=1,
        profile="public-data-demo",
        benchmark_config=_relative(config.get("benchmark_config"), "benchmark_config"),
        allowed_classifications=allowed,
        allowed_snapshot_prefix=prefix,
        prohibited_classifications=prohibited,
        zdr=False,
        data_collection="deny",
        ordinary_provider_retention_accepted=True,
        documented_maximum_abuse_monitoring_days=30,
        rationale=_string(provider.get("rationale"), "provider_policy.rationale"),
        structured_output=True,
        cross_model_fallback=False,
        automatic_generation=False,
        publication=False,
        openrouter_prompt_logging_enabled_by_repository=False,
        store_parameter=store_parameter,
    )


def validate_public_plan(plan: PaidBenchmarkPlan, profile: PublicDemoProfile) -> tuple[dict[str, str], ...]:
    classifications: list[dict[str, str]] = []
    for case in plan.cases:
        if not case.snapshot_path.startswith(profile.allowed_snapshot_prefix):
            raise EvaluationIntegrityError(f"case {case.key} is outside the public snapshot boundary")
        tags = set(case.scenario_tags)
        if case.mutation is None:
            if "historical" not in tags or "evaluation-only" in tags:
                raise EvaluationIntegrityError(f"case {case.key} is not classified as public historical market data")
            classification = "public-market-data"
        else:
            if "evaluation-only" not in tags:
                raise EvaluationIntegrityError(f"mutated case {case.key} must be classified evaluation-only")
            classification = "evaluation-only"
        if classification not in profile.allowed_classifications:
            raise EvaluationIntegrityError(f"case {case.key} has a prohibited input classification")
        if tags.intersection(profile.prohibited_classifications):
            raise EvaluationIntegrityError(f"case {case.key} includes a prohibited classification tag")
        classifications.append({"case_key": case.key, "classification": classification})
    return tuple(classifications)


def public_runtime_config(config: GenerationConfig, profile: PublicDemoProfile) -> GenerationConfig:
    if not config.provider_policy.zdr:
        raise EvaluationConfigurationError("base generation configuration must remain ZDR-required")
    if config.provider_policy.data_collection != "deny" or not config.provider_policy.require_parameters:
        raise EvaluationConfigurationError("public demo may not weaken provider data or parameter controls")
    if config.cross_model_fallback or not config.structured_output:
        raise EvaluationConfigurationError("public demo may not weaken structured output or model identity controls")
    transformed_policy = replace(config.provider_policy, zdr=profile.zdr)
    transformed = replace(config, provider_policy=transformed_policy)
    if replace(transformed.provider_policy, zdr=config.provider_policy.zdr) != config.provider_policy:
        raise EvaluationConfigurationError("public demo runtime transform changed more than ZDR")
    if replace(transformed, provider_policy=config.provider_policy) != config:
        raise EvaluationConfigurationError("public demo runtime transform changed the generation configuration")
    return transformed


def prepare_public_demo(
    *,
    repository_root: str | Path,
    profile_path: str | Path,
    output_dir: str | Path,
    bundle_builder: Any | None = None,
) -> tuple[PaidBenchmarkPlan, tuple[Any, ...]]:
    profile = load_public_demo_profile(repository_root, profile_path)
    plan = load_paid_benchmark_plan(repository_root, profile.benchmark_config)
    classifications = validate_public_plan(plan, profile)
    kwargs: dict[str, Any] = {
        "repository_root": repository_root,
        "config_path": profile.benchmark_config,
        "output_dir": output_dir,
    }
    if bundle_builder is not None:
        kwargs["bundle_builder"] = bundle_builder
    plan, prepared = prepare_paid_benchmark(**kwargs)
    manifest_path = Path(output_dir) / PREPARED_MANIFEST
    manifest = _read_json(manifest_path)
    manifest["public_data_demo"] = {
        "version": PUBLIC_DEMO_VERSION,
        "profile_path": PurePosixPath(str(profile_path)).as_posix(),
        "classifications": list(classifications),
    }
    _write_json(manifest_path, manifest)
    return plan, prepared


def execute_public_demo(
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
    sleeper: Any = None,
    monotonic: Any = None,
    now: Any = None,
    jitter: Any = None,
) -> dict[str, Any]:
    profile = load_public_demo_profile(repository_root, profile_path)
    plan = load_paid_benchmark_plan(repository_root, profile.benchmark_config)
    classifications = validate_public_plan(plan, profile)
    manifest = _read_json(Path(prepared_dir) / PREPARED_MANIFEST)
    prepared_profile = manifest.get("public_data_demo")
    if not isinstance(prepared_profile, Mapping) or prepared_profile.get("version") != PUBLIC_DEMO_VERSION:
        raise EvaluationIntegrityError("prepared corpus is not a public-data demo manifest")
    if prepared_profile.get("classifications") != list(classifications):
        raise EvaluationIntegrityError("prepared public-data classifications do not match the source-controlled plan")

    def probe(config: GenerationConfig, secret: str) -> Mapping[str, Any]:
        return paid_route_probe(public_runtime_config(config, profile), secret)

    def client_builder(config: GenerationConfig) -> OpenRouterClient:
        return OpenRouterClient(public_runtime_config(config, profile), transport=ClassifiedTransport())

    kwargs: dict[str, Any] = {
        "repository_root": repository_root,
        "config_path": profile.benchmark_config,
        "viability_config_path": viability_config_path,
        "prepared_dir": prepared_dir,
        "output_dir": output_dir,
        "api_key": api_key,
        "trusted_main_sha": trusted_main_sha,
        "probe": probe,
        "client_builder": client_builder,
    }
    optional = {
        "catalogue_loader": catalogue_loader,
        "key_status_loader": key_status_loader,
        "sleeper": sleeper,
        "monotonic": monotonic,
        "now": now,
        "jitter": jitter,
    }
    kwargs.update({key: value for key, value in optional.items() if value is not None})
    summary = execute_paid_benchmark(**kwargs)
    summary["evaluation_version"] = PUBLIC_DEMO_VERSION
    summary["public_data_demo"] = {
        "profile": profile.profile,
        "zdr": profile.zdr,
        "data_collection": profile.data_collection,
        "ordinary_provider_retention_accepted": profile.ordinary_provider_retention_accepted,
        "documented_maximum_abuse_monitoring_days": profile.documented_maximum_abuse_monitoring_days,
        "input_classifications": list(classifications),
        "automatic_generation": False,
        "publication": False,
    }
    output = Path(output_dir)
    _write_json(output / PUBLIC_DEMO_POLICY_FILE, asdict(profile))
    _write_json(output / SUMMARY_JSON, summary)
    addition = (
        "\n\n## Public-data demo policy\n\n"
        "- Input boundary: `public-market-data | evaluation-only`\n"
        "- ZDR enforced: `false`\n"
        "- Provider training/data collection: `deny`\n"
        "- Ordinary provider abuse-monitoring retention accepted: `true`\n"
        "- Automatic generation/publication: `false` / `false`\n"
    )
    decision_path = output / DECISION_MARKDOWN
    decision_path.write_text(decision_path.read_text(encoding="utf-8") + addition, encoding="utf-8")
    actions_path = output / ACTIONS_SUMMARY
    actions_path.write_text(actions_path.read_text(encoding="utf-8") + addition, encoding="utf-8")
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
            plan, cases = prepare_public_demo(
                repository_root=args.repository_root,
                profile_path=args.profile,
                output_dir=args.output_dir,
            )
            print(json.dumps({"model": plan.model.model, "cases": len(cases), "maximum_logical_calls": plan.maximum_logical_calls}, sort_keys=True))
        else:
            summary = execute_public_demo(
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
        print(f"public demo benchmark failed: {exc}", file=os.sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
