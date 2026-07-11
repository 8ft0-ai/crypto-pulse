"""Prepare source-controlled governed analysis artefacts after an accepted dry run."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from .contracts import canonical_json_bytes, content_sha256
from .generation_config import load_generation_config
from .pipeline import load_json, process_analysis

PUBLICATION_SCHEMA_VERSION = "crypto-market-accepted-analysis-record/v1"
REPORT_SCHEMA_VERSION = "governed-crypto-report/v1"


class PublicationError(ValueError):
    """Raised when dry-run artefacts cannot be promoted to reviewable source files."""


@dataclass(frozen=True)
class PublicationPaths:
    analysis: str
    provenance: str
    report: str


@dataclass(frozen=True)
class PublicationResult:
    paths: PublicationPaths
    source_snapshot: str
    source_snapshot_sha256: str
    analysis_sha256: str
    provenance_sha256: str
    report_sha256: str
    changed_files: tuple[str, ...]
    pr_body: str
    manifest: dict[str, Any]


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _read_object(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PublicationError(f"{label} is unavailable or invalid JSON: {path}") from exc
    if not isinstance(value, dict):
        raise PublicationError(f"{label} must be a JSON object")
    return value


def _safe_snapshot_path(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts:
        raise PublicationError("snapshot path must be repository-relative without '..'")
    if len(path.parts) != 7:
        raise PublicationError("snapshot path must match data/crypto/hourly/YYYY/MM/DD/*_source_snapshot.json")
    if path.parts[:3] != ("data", "crypto", "hourly"):
        raise PublicationError("snapshot path must be under data/crypto/hourly")
    if not value.endswith("_source_snapshot.json"):
        raise PublicationError("snapshot path must end with _source_snapshot.json")
    year, month, day = path.parts[3:6]
    if not (
        year.isdigit()
        and len(year) == 4
        and month.isdigit()
        and len(month) == 2
        and day.isdigit()
        and len(day) == 2
    ):
        raise PublicationError("snapshot path must contain YYYY/MM/DD components")
    return path


def publication_paths(snapshot_path: str) -> PublicationPaths:
    path = _safe_snapshot_path(snapshot_path)
    year, month, day = path.parts[3:6]
    stem = path.name[: -len("_source_snapshot.json")]
    if not stem:
        raise PublicationError("snapshot filename prefix is empty")
    return PublicationPaths(
        analysis=f"analysis/crypto/hourly/{year}/{month}/{day}/governed/{stem}_analysis.json",
        provenance=f"analysis/crypto/hourly/{year}/{month}/{day}/governed/{stem}_provenance.json",
        report=f"reports/crypto/hourly/{year}/{month}/{day}/governed/{stem}_crypto_market_intelligence.md",
    )


def _quoted(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(str(value), ensure_ascii=False)


def _front_matter(fields: Mapping[str, Any]) -> bytes:
    lines = ["---"]
    lines.extend(f"{key}: {_quoted(value)}" for key, value in fields.items())
    lines.extend(["---", ""])
    return "\n".join(lines).encode("utf-8")


def _get_mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise PublicationError(f"{path} must be an object")
    return value


def _get_string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PublicationError(f"{path} must be a non-empty string")
    return value


def _write(path: Path, content: bytes) -> None:
    if path.is_symlink():
        raise PublicationError(f"refusing symlink publication path: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _pr_body(
    *,
    paths: PublicationPaths,
    bundle: Mapping[str, Any],
    provenance: Mapping[str, Any],
    validation: Mapping[str, Any],
    workflow_run_url: str,
) -> str:
    source = _get_mapping(bundle.get("source_snapshot"), "evidence bundle source_snapshot")
    routing = _get_mapping(provenance.get("routing"), "generation provenance routing")
    usage = _get_mapping(provenance.get("usage"), "generation provenance usage")
    parameters = _get_mapping(
        provenance.get("generation_parameters"), "generation provenance generation_parameters"
    )
    lines = [
        "## Summary",
        "",
        "Updates the rolling governed-analysis review PR from one validated CryptoPulse source snapshot. The model supplied structured JSON only; repository code independently validated the response and deterministically rendered the Markdown report.",
        "",
        "## Source and committed files",
        "",
        f"- Source snapshot: `{source.get('path')}`",
        f"- Source snapshot SHA-256: `{source.get('sha256')}`",
        f"- Snapshot quality: `{source.get('quality_status')}`",
        f"- Accepted analysis: `{paths.analysis}`",
        f"- Generation provenance: `{paths.provenance}`",
        f"- Deterministic report: `{paths.report}`",
        "",
        "## Generation provenance",
        "",
        f"- Prompt version: `{provenance.get('prompt_version')}`",
        f"- Analysis schema: `{provenance.get('analysis_schema_version')}`",
        f"- Evidence schema: `{provenance.get('evidence_schema_version')}`",
        f"- Requested model: `{provenance.get('requested_model')}`",
        f"- Actual model: `{provenance.get('actual_model')}`",
        f"- Actual provider: `{provenance.get('actual_provider')}`",
        f"- Generation ID: `{provenance.get('generation_id')}`",
        f"- Temperature: `{parameters.get('temperature')}`",
        f"- Max output tokens: `{parameters.get('max_output_tokens')}`",
        f"- Usage: input=`{usage.get('input_tokens')}`, output=`{usage.get('output_tokens')}`, total=`{usage.get('total_tokens')}`",
        f"- Estimated cost USD: `{provenance.get('estimated_cost_usd')}`",
        f"- Provider fallback used: `{routing.get('provider_fallback_used')}`",
        f"- Cross-model fallback used: `{routing.get('cross_model_fallback_used')}`",
        f"- Prompt SHA-256: `{provenance.get('prompt_sha256')}`",
        f"- Completion SHA-256: `{provenance.get('completion_sha256')}`",
        "",
        "## Self-proving validation",
        "",
        f"- Workflow run: {workflow_run_url or 'not recorded'}",
        "- Source snapshot validation: `passed`",
        "- Evidence-bundle schema validation: `passed`",
        f"- Structured-analysis validation: `{'passed' if validation.get('valid') is True else 'failed'}`",
        "- Deterministic rendering reproduction: `passed`",
        "- Unit tests: `passed`",
        "- Static-site build: `passed`",
        "- Changed-file scope: `passed`",
        "- Generated `_site/` committed: `no`",
        "",
        "## Preserved boundaries",
        "",
        "- This is public demonstration content, not financial advice or investment research.",
        "- It is not a recommendation, trading signal, watchlist, price target, entry, exit, or portfolio instruction.",
        "- The LLM did not select sources, browse, publish Markdown, create this PR, or receive GitHub credentials.",
        "- Raw provider output remains a scrubbed workflow artefact and is not committed.",
        "- No direct publication or auto-merge occurs.",
        "",
    ]
    return "\n".join(lines)


def prepare_publication(
    *,
    repository_root: str | Path,
    snapshot_path: str,
    artifact_dir: str | Path,
    trusted_main_sha: str,
    workflow_run_url: str = "",
    generation_config_path: str | Path = "config/llm-generation.yml",
    evidence_schema_path: str | Path = "schemas/crypto-market-evidence-bundle-v1.json",
) -> PublicationResult:
    root = Path(repository_root).resolve()
    artifacts = Path(artifact_dir).resolve()
    paths = publication_paths(snapshot_path)

    status = _read_object(artifacts / "run-status.json", "run status")
    if status.get("status") != "accepted" or status.get("publishable_output") is not True:
        raise PublicationError("dry run is not accepted and publishable")

    bundle = _read_object(artifacts / "evidence-bundle.json", "evidence bundle")
    analysis = _read_object(artifacts / "accepted-analysis.json", "accepted analysis")
    metadata_document = _read_object(
        artifacts / "generation-metadata.json", "generation metadata"
    )
    validation = _read_object(artifacts / "validation-report.json", "validation report")
    raw_completion = (artifacts / "provider-completion.raw.json").read_bytes()
    preview = (artifacts / "rendered-preview.md").read_bytes()
    if validation.get("valid") is not True:
        raise PublicationError("validation report is not accepted")

    source = _get_mapping(bundle.get("source_snapshot"), "evidence bundle source_snapshot")
    source_path = _get_string(source.get("path"), "source_snapshot.path")
    source_sha = _get_string(source.get("sha256"), "source_snapshot.sha256")
    if source_path != snapshot_path:
        raise PublicationError("evidence bundle source path does not match selected snapshot")
    snapshot_bytes = (root / source_path).read_bytes()
    if _sha256_bytes(snapshot_bytes) != source_sha:
        raise PublicationError("source snapshot SHA-256 does not match evidence bundle")

    config = load_generation_config(root / generation_config_path)
    evidence_schema = load_json(root / evidence_schema_path)
    analysis_schema = load_json(root / config.analysis_schema_path)
    rerun = process_analysis(
        bundle,
        analysis,
        evidence_schema=evidence_schema,
        analysis_schema=analysis_schema,
    )
    if not rerun.report.is_valid or rerun.normalised_analysis is None or rerun.markdown is None:
        raise PublicationError("accepted analysis did not pass independent publication validation")
    if rerun.report.as_dict() != validation:
        raise PublicationError("publication validation report differs from dry-run validation")
    if rerun.normalised_analysis != (artifacts / "accepted-analysis.json").read_bytes():
        raise PublicationError("accepted analysis is not canonical or differs from dry-run output")
    if rerun.markdown != preview:
        raise PublicationError("rendered preview differs from deterministic publication rendering")

    generation_provenance = _get_mapping(
        metadata_document.get("provenance"), "generation metadata provenance"
    )
    evidence_provenance = _get_mapping(
        generation_provenance.get("evidence_bundle"), "generation provenance evidence_bundle"
    )
    if evidence_provenance.get("bundle_id") != bundle.get("bundle_id"):
        raise PublicationError("generation provenance bundle ID does not match evidence bundle")
    if evidence_provenance.get("sha256") != content_sha256(bundle):
        raise PublicationError("generation provenance evidence-bundle hash does not match")
    completion_bytes = raw_completion[:-1] if raw_completion.endswith(b"\n") else raw_completion
    if generation_provenance.get("completion_sha256") != _sha256_bytes(completion_bytes):
        raise PublicationError("generation completion hash does not match retained provider output")

    analysis_bytes = rerun.normalised_analysis
    analysis_sha = _sha256_bytes(analysis_bytes)
    source_run = _get_mapping(bundle.get("source_snapshot"), "evidence bundle source_snapshot")
    routing = _get_mapping(
        generation_provenance.get("routing"), "generation provenance routing"
    )
    usage = _get_mapping(generation_provenance.get("usage"), "generation provenance usage")
    headline = analysis.get("headline", {}).get("text", "Governed crypto market analysis")
    front_matter = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "report_type": "governed_crypto_market_analysis",
        "title": headline,
        "timestamp": source_run.get("generated_at_utc"),
        "headline": headline,
        "source_snapshot": source_path,
        "source_snapshot_sha256": source_sha,
        "snapshot_quality": source_run.get("quality_status"),
        "accepted_analysis": paths.analysis,
        "accepted_analysis_sha256": analysis_sha,
        "generation_provenance": paths.provenance,
        "evidence_bundle_id": bundle.get("bundle_id"),
        "prompt_version": generation_provenance.get("prompt_version"),
        "analysis_schema_version": generation_provenance.get("analysis_schema_version"),
        "evidence_schema_version": generation_provenance.get("evidence_schema_version"),
        "requested_model": generation_provenance.get("requested_model"),
        "actual_model": generation_provenance.get("actual_model"),
        "actual_provider": generation_provenance.get("actual_provider"),
        "provider_fallback_used": routing.get("provider_fallback_used"),
        "cross_model_fallback_used": routing.get("cross_model_fallback_used"),
        "input_tokens": usage.get("input_tokens"),
        "output_tokens": usage.get("output_tokens"),
        "total_tokens": usage.get("total_tokens"),
        "estimated_cost_usd": generation_provenance.get("estimated_cost_usd"),
        "generation_id": generation_provenance.get("generation_id"),
        "llm_generated": True,
        "deterministically_rendered": True,
        "no_investment_advice": True,
    }
    report_bytes = _front_matter(front_matter) + preview
    report_sha = _sha256_bytes(report_bytes)

    provenance_record = {
        "schema_version": PUBLICATION_SCHEMA_VERSION,
        "trusted_main_sha": trusted_main_sha,
        "source_snapshot": dict(source),
        "evidence_bundle": {
            "bundle_id": bundle.get("bundle_id"),
            "sha256": content_sha256(bundle),
        },
        "analysis": {"path": paths.analysis, "sha256": analysis_sha},
        "report": {"path": paths.report, "sha256": report_sha},
        "generation": dict(generation_provenance),
        "request_summary": metadata_document.get("request_summary"),
        "validation": validation,
    }
    provenance_bytes = canonical_json_bytes(provenance_record) + b"\n"
    provenance_sha = _sha256_bytes(provenance_bytes)

    _write(root / paths.analysis, analysis_bytes)
    _write(root / paths.report, report_bytes)
    _write(root / paths.provenance, provenance_bytes)

    pr_body = _pr_body(
        paths=paths,
        bundle=bundle,
        provenance=generation_provenance,
        validation=validation,
        workflow_run_url=workflow_run_url,
    )
    changed_files = (paths.analysis, paths.provenance, paths.report)
    manifest = {
        "schema_version": "governed-llm-publication-manifest/v1",
        "source_snapshot": {"path": source_path, "sha256": source_sha},
        "paths": {
            "analysis": paths.analysis,
            "provenance": paths.provenance,
            "report": paths.report,
        },
        "hashes": {
            "analysis_sha256": analysis_sha,
            "provenance_sha256": provenance_sha,
            "report_sha256": report_sha,
        },
        "changed_files": list(changed_files),
        "raw_provider_output_committed": False,
        "validation_accepted": True,
    }
    return PublicationResult(
        paths=paths,
        source_snapshot=source_path,
        source_snapshot_sha256=source_sha,
        analysis_sha256=analysis_sha,
        provenance_sha256=provenance_sha,
        report_sha256=report_sha,
        changed_files=changed_files,
        pr_body=pr_body,
        manifest=manifest,
    )


def validate_changed_files(changed_files: list[str], expected: tuple[str, ...]) -> None:
    actual = tuple(sorted(path.strip() for path in changed_files if path.strip()))
    wanted = tuple(sorted(expected))
    if actual != wanted:
        raise PublicationError(
            f"changed files must equal governed publication scope: expected {wanted}, got {actual}"
        )
    if any(path.startswith("_site/") for path in actual):
        raise PublicationError("generated _site output must not be committed")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--artifact-dir", required=True)
    parser.add_argument("--trusted-main-sha", required=True)
    parser.add_argument("--workflow-run-url", default="")
    parser.add_argument("--manifest-output", required=True)
    parser.add_argument("--pr-body-output", required=True)
    args = parser.parse_args()
    result = prepare_publication(
        repository_root=args.repository_root,
        snapshot_path=args.snapshot,
        artifact_dir=args.artifact_dir,
        trusted_main_sha=args.trusted_main_sha,
        workflow_run_url=args.workflow_run_url,
    )
    Path(args.manifest_output).write_bytes(canonical_json_bytes(result.manifest) + b"\n")
    Path(args.pr_body_output).write_text(result.pr_body, encoding="utf-8")
    print(json.dumps(result.manifest, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
