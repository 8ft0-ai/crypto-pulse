"""Bounded, artefact-only Phase 5 model evaluation."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import statistics
import urllib.request
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterable, Mapping

import yaml

from .contracts import canonical_json_bytes, content_sha256
from .evidence_bundle import EvidenceBundleBuild, EvidenceBundleError, build_evidence_bundle
from .generation_config import ConfigurationError, GenerationConfig, load_generation_config
from .openrouter_client import GenerationError, GenerationResult, OpenRouterClient
from .pipeline import load_json, process_analysis
from .schema_validation import validate_schema

EVALUATION_VERSION = "phase-05-model-evaluation/v1"
CATALOGUE_URL = "https://openrouter.ai/api/v1/models"
REQUIRED_MODEL_PARAMETERS = frozenset({"response_format", "structured_outputs"})
HARD_GOVERNANCE_STAGES = ("schema", "referential", "value", "semantic", "policy")
PREPARED_MANIFEST = "prepared-manifest.json"
AVAILABILITY_FILE = "model-availability.json"
SUMMARY_JSON = "evaluation-summary.json"
DECISION_MARKDOWN = "decision-candidate.md"
ACTIONS_SUMMARY = "actions-summary.md"
REVIEWER_WORKSHEET = "reviewer-scorecard.csv"


class EvaluationConfigurationError(ValueError):
    pass


class EvaluationIntegrityError(ValueError):
    pass


@dataclass(frozen=True)
class EvaluationModel:
    key: str
    model: str
    role: str
    availability_checked_at: str
    known_expiration_date: str | None


@dataclass(frozen=True)
class CorpusCase:
    key: str
    snapshot_path: str
    expected_quality: str
    expected_sha256: str
    scenario_tags: tuple[str, ...]
    rationale: str
    mutation: Mapping[str, Any] | None = None


@dataclass(frozen=True)
class EvaluationPlan:
    version: int
    base_generation_config: str
    corpus_manifest: str
    runs_per_case: int
    models: tuple[EvaluationModel, ...]
    cases: tuple[CorpusCase, ...]


@dataclass(frozen=True)
class PreparedCase:
    key: str
    snapshot_path: str
    snapshot_sha256: str
    quality_status: str
    bundle_id: str
    bundle_file: str
    scenario_tags: tuple[str, ...]
    mutation: Mapping[str, Any] | None


@dataclass(frozen=True)
class ModelAvailability:
    key: str
    model: str
    available: bool
    eligible: bool
    reason: str | None
    pricing_prompt: str | None
    pricing_completion: str | None
    supported_parameters: tuple[str, ...]
    expiration_date: str | None
    checked_at: str


@dataclass(frozen=True)
class RunRecord:
    model_key: str
    requested_model: str
    case_key: str
    repeat: int
    status: str
    hard_pass: bool
    failure_code: str | None
    validation: Mapping[str, Any]
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
    analysis_sha256: str | None
    completion_sha256: str | None
    readability_proxy: float | None
    usefulness_proxy: float | None
    claim_count: int | None
    evidence_reference_count: int | None
    output_dir: str


CatalogueLoader = Callable[[], Mapping[str, Any]]
ClientFactory = Callable[[GenerationConfig], OpenRouterClient]
BundleBuilder = Callable[..., EvidenceBundleBuild]


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


def _date(value: Any, path: str) -> str | None:
    if value is None:
        return None
    text = _string(value, path)
    try:
        date.fromisoformat(text)
    except ValueError as exc:
        raise EvaluationConfigurationError(f"{path} must be YYYY-MM-DD") from exc
    return text


def _sha(value: Any, path: str) -> str:
    text = _string(value, path).lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise EvaluationConfigurationError(f"{path} must be a 64-character SHA-256")
    return text


def _yaml(path: Path) -> Mapping[str, Any]:
    return _mapping(yaml.safe_load(path.read_text(encoding="utf-8")), str(path))


def _validate_mutation(value: Mapping[str, Any], path: str) -> None:
    allowed = {"kind", "subject_type", "subject_id", "field", "replacement"}
    if set(value) - allowed or value.get("kind") not in {"prompt_injection", "source_disagreement"}:
        raise EvaluationConfigurationError(f"{path} is unsupported")
    for key in ("subject_type", "subject_id", "field"):
        _string(value.get(key), f"{path}.{key}")
    replacement = value.get("replacement")
    if isinstance(replacement, bool) or not isinstance(replacement, (str, int, float)):
        raise EvaluationConfigurationError(f"{path}.replacement must be a string or number")


def load_evaluation_plan(repository_root: str | Path, config_path: str | Path) -> EvaluationPlan:
    root = Path(repository_root).resolve()
    config_rel = _relative(str(config_path), "config_path")
    config = _yaml(root / config_rel)
    allowed = {"version", "base_generation_config", "corpus_manifest", "runs_per_case", "models"}
    if set(config) - allowed or config.get("version") != 1:
        raise EvaluationConfigurationError("evaluation config must use the supported version and keys")
    runs = config.get("runs_per_case")
    if isinstance(runs, bool) or not isinstance(runs, int) or not 1 <= runs <= 3:
        raise EvaluationConfigurationError("runs_per_case must be between 1 and 3")
    rows = config.get("models")
    if not isinstance(rows, list) or not 2 <= len(rows) <= 3:
        raise EvaluationConfigurationError("models must contain two or three configurations")
    models: list[EvaluationModel] = []
    keys: set[str] = set()
    slugs: set[str] = set()
    for index, raw in enumerate(rows):
        row = _mapping(raw, f"models[{index}]")
        if set(row) - {"key", "model", "role", "availability_checked_at", "known_expiration_date"}:
            raise EvaluationConfigurationError(f"models[{index}] contains unknown keys")
        key = _string(row.get("key"), f"models[{index}].key")
        slug = _string(row.get("model"), f"models[{index}].model")
        role = _string(row.get("role"), f"models[{index}].role")
        if key in keys or slug in slugs:
            raise EvaluationConfigurationError("model keys and slugs must be unique")
        if slug.startswith("openrouter/") or not slug.endswith(":free"):
            raise EvaluationConfigurationError("models must be explicit free provider/model slugs")
        if role not in {"current_candidate", "eligible_alternative"}:
            raise EvaluationConfigurationError("unsupported model role")
        keys.add(key)
        slugs.add(slug)
        models.append(EvaluationModel(key, slug, role, _date(row.get("availability_checked_at"), "availability_checked_at") or "", _date(row.get("known_expiration_date"), "known_expiration_date")))
    if sum(item.role == "current_candidate" for item in models) != 1 or not any(item.role == "eligible_alternative" for item in models):
        raise EvaluationConfigurationError("one current candidate and at least one alternative are required")

    corpus_rel = _relative(config.get("corpus_manifest"), "corpus_manifest")
    corpus = _yaml(root / corpus_rel)
    case_rows = corpus.get("cases")
    if corpus.get("version") != 1 or set(corpus) - {"version", "cases"} or not isinstance(case_rows, list) or not 3 <= len(case_rows) <= 8:
        raise EvaluationConfigurationError("corpus must contain three to eight cases")
    cases: list[CorpusCase] = []
    seen: set[str] = set()
    prompt_probe = False
    for index, raw in enumerate(case_rows):
        row = _mapping(raw, f"cases[{index}]")
        if set(row) - {"key", "snapshot_path", "expected_quality", "snapshot_sha256", "scenario_tags", "rationale", "mutation"}:
            raise EvaluationConfigurationError(f"cases[{index}] contains unknown keys")
        key = _string(row.get("key"), f"cases[{index}].key")
        if key in seen:
            raise EvaluationConfigurationError("corpus case keys must be unique")
        seen.add(key)
        quality = _string(row.get("expected_quality"), f"cases[{index}].expected_quality")
        if quality not in {"valid-ok", "valid-degraded"}:
            raise EvaluationConfigurationError("unsupported expected quality")
        tags = row.get("scenario_tags")
        if not isinstance(tags, list) or not tags or any(not isinstance(tag, str) or not tag.strip() for tag in tags):
            raise EvaluationConfigurationError("scenario_tags must be non-empty strings")
        mutation = row.get("mutation")
        if mutation is not None:
            mutation = _mapping(mutation, f"cases[{index}].mutation")
            _validate_mutation(mutation, f"cases[{index}].mutation")
            prompt_probe = prompt_probe or mutation.get("kind") == "prompt_injection"
        cases.append(CorpusCase(key, _relative(row.get("snapshot_path"), "snapshot_path"), quality, _sha(row.get("snapshot_sha256"), "snapshot_sha256"), tuple(tag.strip() for tag in tags), _string(row.get("rationale"), "rationale"), mutation))
    if not prompt_probe:
        raise EvaluationConfigurationError("corpus must include a prompt-injection probe")
    return EvaluationPlan(1, _relative(config.get("base_generation_config"), "base_generation_config"), corpus_rel, runs, tuple(models), tuple(cases))


def _mutate(bundle: Mapping[str, Any], mutation: Mapping[str, Any] | None) -> dict[str, Any]:
    result = copy.deepcopy(dict(bundle))
    if mutation is None:
        return result
    matches = []
    for item in result.get("evidence", []):
        subject = item.get("subject") if isinstance(item, dict) else None
        if isinstance(subject, Mapping) and subject.get("type") == mutation["subject_type"] and subject.get("id") == mutation["subject_id"] and item.get("field") == mutation["field"]:
            matches.append(item)
    if len(matches) != 1:
        raise EvaluationIntegrityError(f"evaluation mutation expected one evidence item, found {len(matches)}")
    matches[0]["value"] = mutation["replacement"]
    payload = {key: value for key, value in result.items() if key != "bundle_id"}
    result["bundle_id"] = f"sha256:{content_sha256(payload)}"
    return result


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value) + b"\n")


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise EvaluationIntegrityError(f"expected JSON object: {path}")
    return value


def prepare_evaluation(*, repository_root: str | Path, config_path: str | Path, output_dir: str | Path, bundle_builder: BundleBuilder = build_evidence_bundle) -> tuple[EvaluationPlan, tuple[PreparedCase, ...]]:
    root = Path(repository_root).resolve()
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    plan = load_evaluation_plan(root, config_path)
    schema = load_json(root / "schemas/crypto-market-evidence-bundle-v1.json")
    prepared: list[PreparedCase] = []
    for case in plan.cases:
        build = bundle_builder(case.snapshot_path, repository_root=root, source_config_path="config/crypto_sources.yml", evidence_schema=schema)
        if build.snapshot_sha256 != case.expected_sha256:
            raise EvaluationIntegrityError(f"{case.key} snapshot SHA-256 mismatch: expected {case.expected_sha256}, got {build.snapshot_sha256}")
        if build.quality_status != case.expected_quality:
            raise EvaluationIntegrityError(f"{case.key} quality mismatch: expected {case.expected_quality}, got {build.quality_status}")
        bundle = _mutate(build.bundle, case.mutation)
        if validate_schema(bundle, schema):
            raise EvaluationIntegrityError(f"{case.key} prepared bundle failed schema validation")
        filename = f"bundles/{case.key}.json"
        _write_json(output / filename, bundle)
        prepared.append(PreparedCase(case.key, build.snapshot_path, build.snapshot_sha256, build.quality_status, str(bundle["bundle_id"]), filename, case.scenario_tags, case.mutation))
    _write_json(output / PREPARED_MANIFEST, {"evaluation_version": EVALUATION_VERSION, "config_path": PurePosixPath(str(config_path)).as_posix(), "runs_per_case": plan.runs_per_case, "models": [asdict(item) for item in plan.models], "cases": [asdict(item) for item in prepared]})
    return plan, tuple(prepared)


def _catalogue() -> Mapping[str, Any]:
    request = urllib.request.Request(CATALOGUE_URL, headers={"Accept": "application/json", "User-Agent": "CryptoPulse-Phase5-Evaluation/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        value = json.loads(response.read().decode("utf-8"))
    return _mapping(value, "OpenRouter model catalogue")


def check_model_availability(models: Iterable[EvaluationModel], *, catalogue_loader: CatalogueLoader = _catalogue, now: Callable[[], datetime] = lambda: datetime.now(timezone.utc)) -> tuple[ModelAvailability, ...]:
    payload = catalogue_loader()
    rows = payload.get("data")
    if not isinstance(rows, list):
        raise EvaluationIntegrityError("OpenRouter model catalogue is missing data[]")
    indexed = {row.get("id"): row for row in rows if isinstance(row, Mapping) and isinstance(row.get("id"), str)}
    checked = now().astimezone(timezone.utc)
    results = []
    for model in models:
        row = indexed.get(model.model)
        available = isinstance(row, Mapping)
        eligible = available
        reason = None
        prompt = completion = expiration = None
        supported: tuple[str, ...] = ()
        if isinstance(row, Mapping):
            params = row.get("supported_parameters")
            supported = tuple(sorted(str(item) for item in params)) if isinstance(params, list) else ()
            pricing = row.get("pricing") if isinstance(row.get("pricing"), Mapping) else {}
            prompt = str(pricing.get("prompt")) if pricing.get("prompt") is not None else None
            completion = str(pricing.get("completion")) if pricing.get("completion") is not None else None
            expiration = str(row.get("expiration_date")) if row.get("expiration_date") else None
            missing = sorted(REQUIRED_MODEL_PARAMETERS - set(supported))
            if missing:
                eligible = False
                reason = "missing required parameters: " + ", ".join(missing)
            elif prompt != "0" or completion != "0":
                eligible = False
                reason = "model is not zero-price for prompt and completion"
            elif expiration:
                try:
                    expired = date.fromisoformat(expiration) < checked.date()
                except ValueError:
                    eligible = False
                    reason = "catalogue expiration_date is invalid"
                else:
                    if expired:
                        eligible = False
                        reason = f"model expired on {expiration}"
        else:
            reason = "model slug not present in current OpenRouter catalogue"
        results.append(ModelAvailability(model.key, model.model, available, eligible, reason, prompt, completion, supported, expiration, checked.isoformat().replace("+00:00", "Z")))
    return tuple(results)


def _runtime_config(root: Path, base_path: str, model: EvaluationModel, target: Path) -> GenerationConfig:
    raw = yaml.safe_load((root / base_path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("generation"), dict):
        raise EvaluationConfigurationError("base generation config is invalid")
    raw = copy.deepcopy(raw)
    raw["generation"]["model"] = model.model
    raw["generation"]["cross_model_fallback"] = False
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    return load_generation_config(target)


def _claims(analysis: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    result = [analysis[key] for key in ("headline", "source_evidence_note") if isinstance(analysis.get(key), Mapping)]
    for key in ("market_summary", "key_observations", "risks_and_limitations", "data_quality_notes"):
        value = analysis.get(key)
        if isinstance(value, list):
            result.extend(item for item in value if isinstance(item, Mapping))
    return result


def _soft(analysis: Mapping[str, Any]) -> tuple[float, float, int, int]:
    claims = _claims(analysis)
    texts = [str(item.get("text", "")).strip() for item in claims]
    refs = sum(len(item.get("evidence_ids", [])) for item in claims if isinstance(item.get("evidence_ids"), list))
    headline = analysis.get("headline") if isinstance(analysis.get("headline"), Mapping) else {}
    average = statistics.mean(len(text) for text in texts) if texts else 0
    readability = sum((20 <= len(str(headline.get("text", ""))) <= 180, bool(texts) and 25 <= average <= 260, len(set(texts)) == len(texts), all("\n" not in text for text in texts), len(claims) <= 20))
    kinds = {str(item.get("claim_type")) for item in claims}
    usefulness = sum((len(claims) >= 5, refs >= len(claims), len(kinds) >= 3, bool(analysis.get("key_observations")), bool(analysis.get("data_quality_notes"))))
    return float(readability), float(usefulness), len(claims), refs


def _failure(code: str, message: str) -> dict[str, Any]:
    return {"valid": False, "diagnostics": [{"stage": "generation", "code": code, "path": "$", "message": message}]}


def _run_one(*, root: Path, model: EvaluationModel, config: GenerationConfig, prepared: PreparedCase, prepared_dir: Path, repeat: int, output_dir: Path, api_key: str, client_factory: ClientFactory) -> RunRecord:
    run_dir = output_dir / "runs" / model.key / prepared.key / f"repeat-{repeat}"
    run_dir.mkdir(parents=True, exist_ok=True)
    bundle = _read_json(prepared_dir / prepared.bundle_file)
    analysis_schema = load_json(root / config.analysis_schema_path)
    evidence_schema = load_json(root / "schemas/crypto-market-evidence-bundle-v1.json")
    if validate_schema(bundle, evidence_schema):
        raise EvaluationIntegrityError(f"prepared bundle {prepared.key} failed schema validation")
    try:
        generation = client_factory(config).generate(evidence_bundle=bundle, prompt_template=(root / config.prompt_path).read_text(encoding="utf-8"), analysis_schema=analysis_schema, api_key=api_key)
        (run_dir / "provider-completion.raw.json").write_text(generation.raw_completion + "\n", encoding="utf-8")
        _write_json(run_dir / "generation-metadata.json", {"metadata": asdict(generation.metadata), "provenance": generation.provenance, "request_summary": generation.request_summary})
        pipeline = process_analysis(bundle, generation.analysis, evidence_schema=evidence_schema, analysis_schema=analysis_schema)
        validation = pipeline.report.as_dict()
        _write_json(run_dir / "validation-report.json", validation)
        accepted = pipeline.report.is_valid
        analysis_hash = None
        readability = usefulness = claim_count = ref_count = None
        if accepted:
            if pipeline.normalised_analysis is None or pipeline.markdown is None:
                raise RuntimeError("accepted evaluation run produced no deterministic outputs")
            (run_dir / "accepted-analysis.json").write_bytes(pipeline.normalised_analysis)
            (run_dir / "rendered-preview.md").write_bytes(pipeline.markdown)
            analysis_hash = hashlib.sha256(pipeline.normalised_analysis).hexdigest()
            readability, usefulness, claim_count, ref_count = _soft(generation.analysis)
        metadata = generation.metadata
        record = RunRecord(model.key, model.model, prepared.key, repeat, "accepted" if accepted else "rejected", accepted, None if accepted else "analysis_rejected", validation, metadata.actual_model, metadata.actual_provider, metadata.provider_fallback_used, metadata.cross_model_fallback_used, metadata.latency_ms, metadata.input_tokens, metadata.output_tokens, metadata.total_tokens, metadata.estimated_cost_usd, metadata.generation_id, analysis_hash, hashlib.sha256(generation.raw_completion.encode()).hexdigest(), readability, usefulness, claim_count, ref_count, run_dir.relative_to(output_dir).as_posix())
    except (GenerationError, ConfigurationError, OSError, ValueError, RuntimeError, TypeError) as exc:
        code = getattr(exc, "code", None) or "evaluation_run_failure"
        message = " ".join(str(exc).split())[:500].replace(api_key, "[REDACTED]")
        validation = _failure(code, message)
        _write_json(run_dir / "validation-report.json", validation)
        record = RunRecord(model.key, model.model, prepared.key, repeat, "failed", False, code, validation, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, run_dir.relative_to(output_dir).as_posix())
    _write_json(run_dir / "run-record.json", asdict(record))
    return record


def _mean(values: Iterable[int | float | None]) -> float | None:
    clean = [float(value) for value in values if value is not None]
    return statistics.mean(clean) if clean else None


def _aggregate(plan: EvaluationPlan, availability: tuple[ModelAvailability, ...], records: list[RunRecord]) -> dict[str, Any]:
    available = {item.key: item for item in availability}
    models = []
    for model in plan.models:
        rows = [item for item in records if item.model_key == model.key]
        required = len(plan.cases) * plan.runs_per_case
        accepted = [item for item in rows if item.hard_pass]
        hashes: dict[str, list[str]] = {}
        for item in accepted:
            if item.analysis_sha256:
                hashes.setdefault(item.case_key, []).append(item.analysis_sha256)
        models.append({
            "key": model.key,
            "model": model.model,
            "role": model.role,
            "eligible_at_run_time": available[model.key].eligible,
            "disqualified": not available[model.key].eligible or len(accepted) != required,
            "hard_passes": len(accepted),
            "required_runs": required,
            "hard_failures": [{"case": item.case_key, "repeat": item.repeat, "status": item.status, "failure_code": item.failure_code, "diagnostics": item.validation.get("diagnostics", [])} for item in rows if not item.hard_pass],
            "readability_proxy_mean": _mean(item.readability_proxy for item in accepted),
            "usefulness_proxy_mean": _mean(item.usefulness_proxy for item in accepted),
            "latency_ms_mean": _mean(item.latency_ms for item in accepted),
            "input_tokens_mean": _mean(item.input_tokens for item in accepted),
            "output_tokens_mean": _mean(item.output_tokens for item in accepted),
            "cost_usd_total": sum(item.estimated_cost_usd or 0 for item in rows),
            "actual_providers": sorted({item.actual_provider for item in rows if item.actual_provider}),
            "provider_fallback_runs": sum(bool(item.provider_fallback_used) for item in rows),
            "cross_model_fallback_runs": sum(bool(item.cross_model_fallback_used) for item in rows),
            "exact_reproducible_cases": sum(len(values) == plan.runs_per_case and len(set(values)) == 1 for values in hashes.values()),
            "reproducibility_cases_observed": len(hashes),
        })
    qualified = [item for item in models if not item["disqualified"]]
    if not qualified:
        decision = {"decision": "no-go", "selected_model": None, "reason": "No evaluated model passed every hard governance run while remaining eligible at execution time."}
    else:
        selected = sorted(qualified, key=lambda item: (-(item["usefulness_proxy_mean"] or 0), -(item["readability_proxy_mean"] or 0), -item["exact_reproducible_cases"], item["latency_ms_mean"] if item["latency_ms_mean"] is not None else float("inf"), item["model"]))[0]
        current = next(item for item in models if item["role"] == "current_candidate")
        decision = {"decision": "retain" if selected["model"] == current["model"] else "change", "selected_model": selected["model"], "reason": "Selected among hard-qualified models using usefulness, readability, reproducibility and latency tie-breakers."}
    return {"evaluation_version": EVALUATION_VERSION, "hard_governance_stages": list(HARD_GOVERNANCE_STAGES), "runs_per_case": plan.runs_per_case, "case_count": len(plan.cases), "model_results": models, "decision": decision, "evaluation_output_reused_as_evidence": False}


def _decision_text(summary: Mapping[str, Any], availability: tuple[ModelAvailability, ...]) -> str:
    decision = summary["decision"]
    lines = ["# Phase 5 model evaluation decision candidate", "", f"Decision: **{decision['decision']}**", "", f"Selected model: `{decision['selected_model'] or 'none'}`", "", decision["reason"], "", "This workflow output requires reviewer approval and is never market evidence.", "", "## Model availability at execution time", ""]
    lines.extend(f"- `{item.model}` — available=`{item.available}`, eligible=`{item.eligible}`, expires=`{item.expiration_date or 'not listed'}`, reason=`{item.reason or 'none'}`" for item in availability)
    lines.extend(["", "## Model results", ""])
    for item in summary["model_results"]:
        lines.extend([f"### {item['model']}", "", f"- Disqualified: `{item['disqualified']}`", f"- Hard passes: `{item['hard_passes']}/{item['required_runs']}`", f"- Readability/usefulness proxy means: `{item['readability_proxy_mean']}` / `{item['usefulness_proxy_mean']}`", f"- Exact reproducible cases: `{item['exact_reproducible_cases']}/{item['reproducibility_cases_observed']}`", f"- Mean latency ms: `{item['latency_ms_mean']}`", f"- Mean input/output tokens: `{item['input_tokens_mean']}` / `{item['output_tokens_mean']}`", f"- Total estimated cost USD: `{item['cost_usd_total']}`", f"- Actual providers: `{', '.join(item['actual_providers']) or 'unavailable'}`", f"- Provider/cross-model fallback runs: `{item['provider_fallback_runs']}` / `{item['cross_model_fallback_runs']}`", ""])
    return "\n".join(lines)


def execute_evaluation(*, repository_root: str | Path, config_path: str | Path, prepared_dir: str | Path, output_dir: str | Path, api_key: str | None = None, trusted_main_sha: str | None = None, catalogue_loader: CatalogueLoader = _catalogue, client_factory: ClientFactory = OpenRouterClient) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    prepared_root = Path(prepared_dir)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    plan = load_evaluation_plan(root, config_path)
    manifest = _read_json(prepared_root / PREPARED_MANIFEST)
    rows = manifest.get("cases")
    if not isinstance(rows, list):
        raise EvaluationIntegrityError("prepared manifest is missing cases")
    prepared = tuple(PreparedCase(str(row["key"]), str(row["snapshot_path"]), str(row["snapshot_sha256"]), str(row["quality_status"]), str(row["bundle_id"]), str(row["bundle_file"]), tuple(row.get("scenario_tags", [])), row.get("mutation")) for row in rows if isinstance(row, Mapping))
    if tuple(item.key for item in prepared) != tuple(item.key for item in plan.cases):
        raise EvaluationIntegrityError("prepared corpus does not match source-controlled plan")
    for item in prepared:
        if _read_json(prepared_root / item.bundle_file).get("bundle_id") != item.bundle_id:
            raise EvaluationIntegrityError(f"prepared bundle ID mismatch for {item.key}")
    availability = check_model_availability(plan.models, catalogue_loader=catalogue_loader)
    _write_json(output / AVAILABILITY_FILE, {"models": [asdict(item) for item in availability]})
    if not api_key:
        raise EvaluationIntegrityError("OPENROUTER_API_KEY is required for controlled model evaluation")
    by_key = {item.key: item for item in availability}
    records: list[RunRecord] = []
    for model in plan.models:
        runtime = _runtime_config(root, plan.base_generation_config, model, output / "runtime-configs" / f"{model.key}.yml")
        for case in prepared:
            for repeat in range(1, plan.runs_per_case + 1):
                if by_key[model.key].eligible:
                    records.append(_run_one(root=root, model=model, config=runtime, prepared=case, prepared_dir=prepared_root, repeat=repeat, output_dir=output, api_key=api_key, client_factory=client_factory))
                else:
                    run_dir = output / "runs" / model.key / case.key / f"repeat-{repeat}"
                    run_dir.mkdir(parents=True, exist_ok=True)
                    validation = _failure("model_ineligible", by_key[model.key].reason or "model is ineligible")
                    record = RunRecord(
                        model_key=model.key,
                        requested_model=model.model,
                        case_key=case.key,
                        repeat=repeat,
                        status="ineligible",
                        hard_pass=False,
                        failure_code="model_ineligible",
                        validation=validation,
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
                        analysis_sha256=None,
                        completion_sha256=None,
                        readability_proxy=None,
                        usefulness_proxy=None,
                        claim_count=None,
                        evidence_reference_count=None,
                        output_dir=run_dir.relative_to(output).as_posix(),
                    )
                    _write_json(run_dir / "validation-report.json", validation)
                    _write_json(run_dir / "run-record.json", asdict(record))
                    records.append(record)
    summary = _aggregate(plan, availability, records)
    summary["trusted_main_sha"] = trusted_main_sha
    summary["completed_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    _write_json(output / SUMMARY_JSON, summary)
    decision = _decision_text(summary, availability)
    (output / DECISION_MARKDOWN).write_text(decision, encoding="utf-8")
    worksheet = ["model_key,case_key,repeat,manual_usefulness_0_to_5,manual_readability_0_to_5,reviewer_notes"] + [f"{model.key},{case.key},{repeat},,," for model in plan.models for case in plan.cases for repeat in range(1, plan.runs_per_case + 1)]
    (output / REVIEWER_WORKSHEET).write_text("\n".join(worksheet) + "\n", encoding="utf-8")
    (output / ACTIONS_SUMMARY).write_text(decision + f"\n\n- Trusted main commit: `{trusted_main_sha or 'not-recorded'}`\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    prepare = sub.add_parser("prepare")
    prepare.add_argument("--repository-root", default=".")
    prepare.add_argument("--config", default="config/llm-evaluation.yml")
    prepare.add_argument("--output-dir", required=True)
    run = sub.add_parser("run")
    run.add_argument("--repository-root", default=".")
    run.add_argument("--config", default="config/llm-evaluation.yml")
    run.add_argument("--prepared-dir", required=True)
    run.add_argument("--output-dir", required=True)
    run.add_argument("--trusted-main-sha")
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            plan, cases = prepare_evaluation(repository_root=args.repository_root, config_path=args.config, output_dir=args.output_dir)
            print(json.dumps({"models": len(plan.models), "cases": len(cases), "runs_per_case": plan.runs_per_case}, sort_keys=True))
        else:
            summary = execute_evaluation(repository_root=args.repository_root, config_path=args.config, prepared_dir=args.prepared_dir, output_dir=args.output_dir, trusted_main_sha=args.trusted_main_sha)
            print(json.dumps(summary["decision"], sort_keys=True))
        return 0
    except (EvaluationConfigurationError, EvaluationIntegrityError, EvidenceBundleError, ConfigurationError, OSError, ValueError, TypeError) as exc:
        print(json.dumps({"status": "failed", "error": " ".join(str(exc).split())[:500]}, sort_keys=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
