"""Failure-safe provider execution for the governed Phase 5 model evaluation."""

from __future__ import annotations

import hashlib
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .evaluation import (
    ACTIONS_SUMMARY,
    AVAILABILITY_FILE,
    DECISION_MARKDOWN,
    PREPARED_MANIFEST,
    REVIEWER_WORKSHEET,
    SUMMARY_JSON,
    CatalogueLoader,
    ClientFactory,
    EvaluationIntegrityError,
    EvaluationModel,
    ModelAvailability,
    PreparedCase,
    RunRecord,
    _aggregate,
    _catalogue,
    _decision_text,
    _failure,
    _read_json,
    _runtime_config,
    _soft,
    _write_json,
    check_model_availability,
    load_evaluation_plan,
)
from .generation_config import ConfigurationError, GenerationConfig
from .openrouter_client import GenerationError, OpenRouterClient
from .pipeline import load_json, process_analysis
from .schema_validation import validate_schema


def _empty_run_record(
    *,
    model: EvaluationModel,
    prepared: PreparedCase,
    repeat: int,
    status: str,
    failure_code: str,
    validation: Mapping[str, Any],
    output_dir: str,
) -> RunRecord:
    """Create a complete typed failure record without positional padding."""
    return RunRecord(
        model_key=model.key,
        requested_model=model.model,
        case_key=prepared.key,
        repeat=repeat,
        status=status,
        hard_pass=False,
        failure_code=failure_code,
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
        output_dir=output_dir,
    )


def _run_one(
    *,
    root: Path,
    model: EvaluationModel,
    config: GenerationConfig,
    prepared: PreparedCase,
    prepared_dir: Path,
    repeat: int,
    output_dir: Path,
    api_key: str,
    client_factory: ClientFactory,
) -> RunRecord:
    run_dir = output_dir / "runs" / model.key / prepared.key / f"repeat-{repeat}"
    run_dir.mkdir(parents=True, exist_ok=True)
    relative_run_dir = run_dir.relative_to(output_dir).as_posix()
    bundle = _read_json(prepared_dir / prepared.bundle_file)
    analysis_schema = load_json(root / config.analysis_schema_path)
    evidence_schema = load_json(root / "schemas/crypto-market-evidence-bundle-v1.json")
    if validate_schema(bundle, evidence_schema):
        raise EvaluationIntegrityError(f"prepared bundle {prepared.key} failed schema validation")

    try:
        generation = client_factory(config).generate(
            evidence_bundle=bundle,
            prompt_template=(root / config.prompt_path).read_text(encoding="utf-8"),
            analysis_schema=analysis_schema,
            api_key=api_key,
        )
        (run_dir / "provider-completion.raw.json").write_text(
            generation.raw_completion + "\n",
            encoding="utf-8",
        )
        _write_json(
            run_dir / "generation-metadata.json",
            {
                "metadata": asdict(generation.metadata),
                "provenance": generation.provenance,
                "request_summary": generation.request_summary,
            },
        )
        pipeline = process_analysis(
            bundle,
            generation.analysis,
            evidence_schema=evidence_schema,
            analysis_schema=analysis_schema,
        )
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
        record = RunRecord(
            model_key=model.key,
            requested_model=model.model,
            case_key=prepared.key,
            repeat=repeat,
            status="accepted" if accepted else "rejected",
            hard_pass=accepted,
            failure_code=None if accepted else "analysis_rejected",
            validation=validation,
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
            analysis_sha256=analysis_hash,
            completion_sha256=hashlib.sha256(generation.raw_completion.encode()).hexdigest(),
            readability_proxy=readability,
            usefulness_proxy=usefulness,
            claim_count=claim_count,
            evidence_reference_count=ref_count,
            output_dir=relative_run_dir,
        )
    except (GenerationError, ConfigurationError, OSError, ValueError, RuntimeError, TypeError) as exc:
        code = getattr(exc, "code", None) or "evaluation_run_failure"
        message = " ".join(str(exc).split())[:500].replace(api_key, "[REDACTED]")
        validation = _failure(code, message)
        _write_json(run_dir / "validation-report.json", validation)
        record = _empty_run_record(
            model=model,
            prepared=prepared,
            repeat=repeat,
            status="failed",
            failure_code=code,
            validation=validation,
            output_dir=relative_run_dir,
        )

    _write_json(run_dir / "run-record.json", asdict(record))
    return record


def execute_evaluation(
    *,
    repository_root: str | Path,
    config_path: str | Path,
    prepared_dir: str | Path,
    output_dir: str | Path,
    api_key: str | None = None,
    trusted_main_sha: str | None = None,
    catalogue_loader: CatalogueLoader = _catalogue,
    client_factory: ClientFactory = OpenRouterClient,
) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    prepared_root = Path(prepared_dir)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    plan = load_evaluation_plan(root, config_path)
    manifest = _read_json(prepared_root / PREPARED_MANIFEST)
    rows = manifest.get("cases")
    if not isinstance(rows, list):
        raise EvaluationIntegrityError("prepared manifest is missing cases")

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
        raise EvaluationIntegrityError("prepared corpus does not match source-controlled plan")
    for item in prepared:
        if _read_json(prepared_root / item.bundle_file).get("bundle_id") != item.bundle_id:
            raise EvaluationIntegrityError(f"prepared bundle ID mismatch for {item.key}")

    availability = check_model_availability(plan.models, catalogue_loader=catalogue_loader)
    _write_json(output / AVAILABILITY_FILE, {"models": [asdict(item) for item in availability]})
    if not api_key:
        raise EvaluationIntegrityError("OPENROUTER_API_KEY is required for controlled model evaluation")

    by_key: dict[str, ModelAvailability] = {item.key: item for item in availability}
    records: list[RunRecord] = []
    for model in plan.models:
        runtime = _runtime_config(
            root,
            plan.base_generation_config,
            model,
            output / "runtime-configs" / f"{model.key}.yml",
        )
        for case in prepared:
            for repeat in range(1, plan.runs_per_case + 1):
                if by_key[model.key].eligible:
                    records.append(
                        _run_one(
                            root=root,
                            model=model,
                            config=runtime,
                            prepared=case,
                            prepared_dir=prepared_root,
                            repeat=repeat,
                            output_dir=output,
                            api_key=api_key,
                            client_factory=client_factory,
                        )
                    )
                    continue

                run_dir = output / "runs" / model.key / case.key / f"repeat-{repeat}"
                run_dir.mkdir(parents=True, exist_ok=True)
                validation = _failure(
                    "model_ineligible",
                    by_key[model.key].reason or "model is ineligible",
                )
                record = _empty_run_record(
                    model=model,
                    prepared=case,
                    repeat=repeat,
                    status="ineligible",
                    failure_code="model_ineligible",
                    validation=validation,
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
    worksheet = [
        "model_key,case_key,repeat,manual_usefulness_0_to_5,manual_readability_0_to_5,reviewer_notes"
    ] + [
        f"{model.key},{case.key},{repeat},,,"
        for model in plan.models
        for case in plan.cases
        for repeat in range(1, plan.runs_per_case + 1)
    ]
    (output / REVIEWER_WORKSHEET).write_text("\n".join(worksheet) + "\n", encoding="utf-8")
    (output / ACTIONS_SUMMARY).write_text(
        decision + f"\n\n- Trusted main commit: `{trusted_main_sha or 'not-recorded'}`\n",
        encoding="utf-8",
    )
    return summary
