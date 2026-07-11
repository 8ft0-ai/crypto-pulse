"""Manual artefact-only governed LLM dry-run orchestration."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass, is_dataclass
from pathlib import Path
from typing import Any, Callable

from .contracts import canonical_json_bytes
from .evidence_bundle import EvidenceBundleBuild, EvidenceBundleError, build_evidence_bundle
from .generation_config import ConfigurationError, GenerationConfig, load_generation_config
from .openrouter_client import GenerationError, GenerationResult, OpenRouterClient
from .pipeline import load_json, process_analysis
from .schema_validation import validate_schema

EVIDENCE_BUNDLE_FILE = "evidence-bundle.json"
RAW_COMPLETION_FILE = "provider-completion.raw.json"
NORMALISED_ANALYSIS_FILE = "accepted-analysis.json"
MARKDOWN_PREVIEW_FILE = "rendered-preview.md"
VALIDATION_REPORT_FILE = "validation-report.json"
GENERATION_METADATA_FILE = "generation-metadata.json"
RUN_STATUS_FILE = "run-status.json"
ACTIONS_SUMMARY_FILE = "actions-summary.md"

_ALL_FILES = (
    EVIDENCE_BUNDLE_FILE,
    RAW_COMPLETION_FILE,
    NORMALISED_ANALYSIS_FILE,
    MARKDOWN_PREVIEW_FILE,
    VALIDATION_REPORT_FILE,
    GENERATION_METADATA_FILE,
    RUN_STATUS_FILE,
    ACTIONS_SUMMARY_FILE,
)
_PUBLISHABLE_FILES = (NORMALISED_ANALYSIS_FILE, MARKDOWN_PREVIEW_FILE)


@dataclass(frozen=True)
class DryRunOutcome:
    status: str
    exit_code: int
    output_dir: Path
    artifact_files: tuple[str, ...]
    summary_path: Path


def _write_json(path: Path, value: Any) -> None:
    path.write_bytes(canonical_json_bytes(value) + b"\n")


def _metadata_dict(value: Any) -> dict[str, Any]:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "__dict__"):
        return dict(vars(value))
    raise TypeError("generation metadata must be a dataclass or mapping-like object")


def _prepare_output_dir(output_dir: Path) -> None:
    if output_dir.is_symlink():
        raise ValueError(f"refusing symlink output directory: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    for name in _ALL_FILES:
        target = output_dir / name
        if target.is_symlink():
            raise ValueError(f"refusing symlink output path: {target}")
        target.unlink(missing_ok=True)


def _redacted_message(exc: BaseException, api_key: str | None) -> str:
    message = " ".join(str(exc).split())[:500] or type(exc).__name__
    if api_key:
        message = message.replace(api_key, "[REDACTED]")
    return message


def _failure_report(stage: str, code: str, message: str) -> dict[str, Any]:
    return {
        "valid": False,
        "diagnostics": [
            {"stage": stage, "code": code, "path": "$", "message": message}
        ],
    }


def _artifact_files(output_dir: Path) -> tuple[str, ...]:
    return tuple(name for name in _ALL_FILES if (output_dir / name).is_file())


def _summary(
    *,
    build: EvidenceBundleBuild | None,
    config: GenerationConfig | None,
    generation: GenerationResult | None,
    validation: dict[str, Any] | None,
    status: str,
    trusted_main_sha: str | None,
    artifacts: tuple[str, ...],
    failure_code: str | None = None,
) -> str:
    source = build.bundle["source_snapshot"] if build else {}
    metadata = generation.metadata if generation else None
    usage = {
        "input": metadata.input_tokens if metadata else None,
        "output": metadata.output_tokens if metadata else None,
        "total": metadata.total_tokens if metadata else None,
    }
    lines = [
        "# Governed LLM dry run",
        "",
        f"- Outcome: `{status}`",
        f"- Trusted main commit: `{trusted_main_sha or 'not-recorded'}`",
        f"- Snapshot: `{source.get('path', 'unavailable')}`",
        f"- Snapshot SHA-256: `{source.get('sha256', 'unavailable')}`",
        f"- Snapshot quality: `{source.get('quality_status', 'unavailable')}`",
        f"- Evidence bundle: `{build.bundle.get('bundle_id', 'unavailable') if build else 'unavailable'}`",
        f"- Prompt version: `{config.prompt_version if config else 'unavailable'}`",
        f"- Analysis schema: `{config.analysis_schema_version if config else 'unavailable'}`",
        f"- Evidence schema: `{config.evidence_schema_version if config else 'unavailable'}`",
        f"- Requested model: `{config.model if config else 'unavailable'}`",
        f"- Actual model: `{metadata.actual_model if metadata and metadata.actual_model else 'unavailable'}`",
        f"- Actual provider: `{metadata.actual_provider if metadata and metadata.actual_provider else 'unavailable'}`",
        f"- Provider fallback used: `{metadata.provider_fallback_used if metadata else 'unavailable'}`",
        f"- Cross-model fallback used: `{metadata.cross_model_fallback_used if metadata else 'unavailable'}`",
        f"- Token usage: input=`{usage['input']}`, output=`{usage['output']}`, total=`{usage['total']}`",
        f"- Estimated cost USD: `{metadata.estimated_cost_usd if metadata else 'unavailable'}`",
        f"- Validation accepted: `{validation.get('valid') if validation else False}`",
    ]
    if failure_code:
        lines.append(f"- Failure code: `{failure_code}`")
    lines.extend(["", "## Artefact files", ""])
    lines.extend(f"- `{name}`" for name in artifacts)
    lines.extend(
        [
            "",
            "No branch, commit, issue, pull request, deployment or publication was created by this run.",
            "",
        ]
    )
    return "\n".join(lines)


def _load_prepared_bundle(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise EvidenceBundleError("prepared evidence bundle must be a JSON object")
    return value


def _finish_failure(
    *,
    output: Path,
    build: EvidenceBundleBuild | None,
    config: GenerationConfig | None,
    generation: GenerationResult | None,
    validation: dict[str, Any],
    trusted_main_sha: str | None,
    code: str,
    status: str = "failed",
) -> DryRunOutcome:
    for name in _PUBLISHABLE_FILES:
        (output / name).unlink(missing_ok=True)
    _write_json(
        output / RUN_STATUS_FILE,
        {"status": status, "failure_code": code, "publishable_output": False},
    )
    artifacts = _artifact_files(output)
    summary_text = _summary(
        build=build,
        config=config,
        generation=generation,
        validation=validation,
        status=status,
        trusted_main_sha=trusted_main_sha,
        artifacts=artifacts + (ACTIONS_SUMMARY_FILE,),
        failure_code=code,
    )
    (output / ACTIONS_SUMMARY_FILE).write_text(summary_text, encoding="utf-8")
    return DryRunOutcome(status, 2, output, _artifact_files(output), output / ACTIONS_SUMMARY_FILE)


def execute_dry_run(
    *,
    repository_root: str | Path,
    snapshot_path: str,
    output_dir: str | Path,
    prepared_bundle_path: str | Path | None = None,
    generation_config_path: str | Path = "config/llm-generation.yml",
    source_config_path: str | Path = "config/crypto_sources.yml",
    evidence_schema_path: str | Path = "schemas/crypto-market-evidence-bundle-v1.json",
    api_key: str | None = None,
    trusted_main_sha: str | None = None,
    client_factory: Callable[[GenerationConfig], OpenRouterClient] = OpenRouterClient,
    bundle_builder: Callable[..., EvidenceBundleBuild] = build_evidence_bundle,
) -> DryRunOutcome:
    root = Path(repository_root).resolve()
    output = Path(output_dir)
    _prepare_output_dir(output)
    config: GenerationConfig | None = None
    build: EvidenceBundleBuild | None = None
    generation: GenerationResult | None = None
    validation: dict[str, Any] | None = None
    secret = api_key if api_key is not None else os.environ.get("OPENROUTER_API_KEY")

    try:
        evidence_schema = load_json(root / evidence_schema_path)
        build = bundle_builder(
            snapshot_path,
            repository_root=root,
            source_config_path=source_config_path,
            evidence_schema=evidence_schema,
        )
        if prepared_bundle_path:
            prepared = _load_prepared_bundle(Path(prepared_bundle_path))
            if canonical_json_bytes(prepared) != canonical_json_bytes(build.bundle):
                raise EvidenceBundleError(
                    "prepared evidence bundle does not match the selected snapshot at the trusted commit"
                )
        _write_json(output / EVIDENCE_BUNDLE_FILE, build.bundle)

        config = load_generation_config(root / generation_config_path)
        prompt_template = (root / config.prompt_path).read_text(encoding="utf-8")
        analysis_schema = load_json(root / config.analysis_schema_path)
        schema_errors = validate_schema(build.bundle, evidence_schema)
        if schema_errors:
            raise EvidenceBundleError("evidence bundle failed schema validation before provider call")

        client = client_factory(config)
        generation = client.generate(
            evidence_bundle=build.bundle,
            prompt_template=prompt_template,
            analysis_schema=analysis_schema,
            api_key=secret,
        )
        # Provider text only: no credentials, request headers, or environment values are retained.
        (output / RAW_COMPLETION_FILE).write_text(generation.raw_completion + "\n", encoding="utf-8")
        metadata_document = {
            "metadata": _metadata_dict(generation.metadata),
            "provenance": generation.provenance,
            "request_summary": generation.request_summary,
        }
        _write_json(output / GENERATION_METADATA_FILE, metadata_document)

        result = process_analysis(
            build.bundle,
            generation.analysis,
            evidence_schema=evidence_schema,
            analysis_schema=analysis_schema,
        )
        validation = result.report.as_dict()
        _write_json(output / VALIDATION_REPORT_FILE, validation)
        if not result.report.is_valid:
            return _finish_failure(
                output=output,
                build=build,
                config=config,
                generation=generation,
                validation=validation,
                trusted_main_sha=trusted_main_sha,
                code="analysis_rejected",
                status="rejected",
            )

        if result.normalised_analysis is None or result.markdown is None:
            raise RuntimeError("accepted validation produced no deterministic outputs")
        (output / NORMALISED_ANALYSIS_FILE).write_bytes(result.normalised_analysis)
        (output / MARKDOWN_PREVIEW_FILE).write_bytes(result.markdown)
        _write_json(
            output / RUN_STATUS_FILE,
            {"status": "accepted", "failure_code": None, "publishable_output": True},
        )
        artifacts = _artifact_files(output)
        summary_text = _summary(
            build=build,
            config=config,
            generation=generation,
            validation=validation,
            status="accepted",
            trusted_main_sha=trusted_main_sha,
            artifacts=artifacts + (ACTIONS_SUMMARY_FILE,),
        )
        (output / ACTIONS_SUMMARY_FILE).write_text(summary_text, encoding="utf-8")
        return DryRunOutcome("accepted", 0, output, _artifact_files(output), output / ACTIONS_SUMMARY_FILE)

    except (EvidenceBundleError, ConfigurationError, GenerationError, OSError, ValueError, RuntimeError, TypeError) as exc:
        code = getattr(exc, "code", None) or (
            "evidence_preparation"
            if isinstance(exc, EvidenceBundleError)
            else "configuration"
            if isinstance(exc, ConfigurationError)
            else "dry_run_failure"
        )
        message = _redacted_message(exc, secret)
        validation = _failure_report(
            "generation" if isinstance(exc, GenerationError) else "preparation",
            code,
            message,
        )
        _write_json(output / VALIDATION_REPORT_FILE, validation)
        return _finish_failure(
            output=output,
            build=build,
            config=config,
            generation=generation,
            validation=validation,
            trusted_main_sha=trusted_main_sha,
            code=code,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="Run governed LLM analysis and retain review artefacts only")
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--prepared-evidence-bundle")
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--generation-config", default="config/llm-generation.yml")
    parser.add_argument("--source-config", default="config/crypto_sources.yml")
    parser.add_argument("--evidence-schema", default="schemas/crypto-market-evidence-bundle-v1.json")
    parser.add_argument("--trusted-main-sha")
    args = parser.parse_args()
    outcome = execute_dry_run(
        repository_root=args.repository_root,
        snapshot_path=args.snapshot,
        output_dir=args.output_dir,
        prepared_bundle_path=args.prepared_evidence_bundle,
        generation_config_path=args.generation_config,
        source_config_path=args.source_config,
        evidence_schema_path=args.evidence_schema,
        trusted_main_sha=args.trusted_main_sha,
    )
    print(json.dumps({"status": outcome.status, "artifact_files": outcome.artifact_files}, sort_keys=True))
    return outcome.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
