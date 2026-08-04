"""Fail-closed command line entry point for the Phase 9 comparison.

The CLI is the governed execution boundary. It derives immutable prompt-injection
safety evidence during secret-free preparation and adapts all terminal execution
paths to the exact reviewed Phase 9 outcomes before the next call can begin.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence

from . import gpt_oss_quality_comparison as _core
from .claim_candidate_gold_corpus import (
    _forbidden_matches,
    load_claim_candidate_gold_manifest,
)
from .contracts import canonical_json_bytes, content_sha256
from .evaluation import EvaluationConfigurationError, EvaluationIntegrityError
from .gpt_oss_quality_comparison_config import DEFAULT_CONFIG, load_phase9_plan
from .gpt_oss_quality_comparison_scoring import score_counts

PROMPT_INJECTION_CASE = "adversarial-prompt-injection"


class _ModelBoundaryFailure(RuntimeError):
    """A deterministic reconstruction, validation or rendering failure."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise EvaluationIntegrityError(f"{path} must contain a JSON object")
    return value


def _call_dir(output: Path, schedule: Mapping[str, Any]) -> Path:
    return (
        output
        / "runs"
        / f"repeat-{int(schedule['repeat_index'])}"
        / str(schedule["case_key"])
    )


def _derive_case_safety(
    *,
    case_definition: Mapping[str, Any],
    candidates: Sequence[Mapping[str, Any]],
    bundle: Mapping[str, Any],
) -> dict[str, Any]:
    """Resolve repository-owned prohibited selection evidence deterministically."""
    case_key = str(case_definition.get("key"))
    prohibited: set[str] = set()
    for rule in case_definition.get("forbidden", []):
        prohibited.update(_forbidden_matches(rule, candidates, bundle))

    # Phase 9 has one explicit prompt-injection selection gate. Deliberate
    # omissions in other cases are not automatically prohibited selections.
    prohibited_evidence_ids = (
        {
            str(identifier)
            for omission in case_definition.get("omissions", [])
            for identifier in omission.get("evidence_ids", [])
        }
        if case_key == PROMPT_INJECTION_CASE
        else set()
    )
    forbidden_text = (
        [str(value) for value in case_definition.get("forbidden_text", [])]
        if case_key == PROMPT_INJECTION_CASE
        else []
    )
    folded_text = [value.casefold() for value in forbidden_text]

    for candidate in candidates:
        identifier = str(candidate.get("candidate_id"))
        evidence_ids = {
            str(value) for value in candidate.get("evidence_ids", [])
        }
        candidate_text = canonical_json_bytes(candidate).decode("utf-8").casefold()
        if evidence_ids & prohibited_evidence_ids:
            prohibited.add(identifier)
        if any(fragment in candidate_text for fragment in folded_text):
            prohibited.add(identifier)

    prohibited_ids = sorted(prohibited)
    evidence_ids = sorted(prohibited_evidence_ids)
    return {
        "prohibited_candidate_ids": prohibited_ids,
        "prohibited_candidate_ids_sha256": content_sha256(prohibited_ids),
        "prohibited_evidence_ids": evidence_ids,
        "prohibited_evidence_ids_sha256": content_sha256(evidence_ids),
        "forbidden_text": forbidden_text,
        "forbidden_text_sha256": content_sha256(forbidden_text),
    }


def _safety_by_case(
    *,
    repository_root: Path,
    prepared_root: Path,
    config_path: str | Path,
) -> dict[str, dict[str, Any]]:
    plan = load_phase9_plan(repository_root, config_path)
    prepared = _object(prepared_root / _core.PREPARED_MANIFEST)
    gold = load_claim_candidate_gold_manifest(repository_root, plan.gold_manifest)
    gold_by_key = {str(row["key"]): row for row in gold["cases"]}
    result: dict[str, dict[str, Any]] = {}

    for prepared_case in prepared.get("cases", []):
        case_key = str(prepared_case["key"])
        paths = prepared_case["paths"]
        candidate_payload = _object(prepared_root / str(paths["candidates"]))
        bundle = _object(prepared_root / str(paths["bundle"]))
        candidates = candidate_payload.get("candidates")
        if not isinstance(candidates, list) or not all(
            isinstance(item, Mapping) for item in candidates
        ):
            raise EvaluationIntegrityError(
                f"{case_key} prepared candidates are not a candidate list"
            )
        result[case_key] = _derive_case_safety(
            case_definition=gold_by_key[case_key],
            candidates=candidates,
            bundle=bundle,
        )
    return result


def _write_safety_manifest(
    *,
    repository_root: Path,
    prepared_root: Path,
    config_path: str | Path,
) -> dict[str, dict[str, Any]]:
    manifest_path = prepared_root / _core.PREPARED_MANIFEST
    manifest = _object(manifest_path)
    safety = _safety_by_case(
        repository_root=repository_root,
        prepared_root=prepared_root,
        config_path=config_path,
    )
    for case in manifest["cases"]:
        case.update(safety[str(case["key"])])
    _core._write_json(manifest_path, manifest)
    return safety


def _verify_safety_manifest(
    *,
    repository_root: Path,
    prepared_root: Path,
    config_path: str | Path,
) -> dict[str, dict[str, Any]]:
    manifest = _object(prepared_root / _core.PREPARED_MANIFEST)
    expected = _safety_by_case(
        repository_root=repository_root,
        prepared_root=prepared_root,
        config_path=config_path,
    )
    actual = {str(case["key"]): case for case in manifest.get("cases", [])}
    for case_key, evidence in expected.items():
        for key, value in evidence.items():
            if actual.get(case_key, {}).get(key) != value:
                raise EvaluationIntegrityError(
                    f"{case_key} prepared prompt-injection safety evidence changed"
                )
    return expected


def prepare_gpt_oss_quality_comparison(
    *,
    repository_root: str | Path,
    output_dir: str | Path,
    config_path: str | Path = DEFAULT_CONFIG,
) -> dict[str, Any]:
    """Prepare the Phase 9 corpus and freeze derived safety evidence."""
    result = _core.prepare_gpt_oss_quality_comparison(
        repository_root=repository_root,
        output_dir=output_dir,
        config_path=config_path,
    )
    safety = _write_safety_manifest(
        repository_root=Path(repository_root).resolve(),
        prepared_root=Path(output_dir).resolve(),
        config_path=config_path,
    )
    result["prompt_injection_prohibited_candidate_count"] = len(
        safety[PROMPT_INJECTION_CASE]["prohibited_candidate_ids"]
    )
    result["prompt_injection_safety_evidence"] = True
    return result


def _interpreted_base(call_dir: Path) -> dict[str, Any]:
    path = call_dir / "interpreted-response.json"
    if not path.is_file():
        return {}
    value = _object(path)
    allowed = {
        "requested_model",
        "actual_model",
        "actual_provider",
        "provider_slug",
        "generation_id",
        "finish_reason",
        "input_tokens",
        "output_tokens",
        "reasoning_tokens",
        "observed_cost_usd",
        "metering_status",
        "latency_ms",
        "router_attempt_count",
        "provider_fallback_used",
        "cross_model_fallback_used",
    }
    return {key: value.get(key) for key in allowed if key in value}


def _write_terminal_result(
    *,
    output: Path,
    schedule: Mapping[str, Any],
    prepared_case: Mapping[str, Any],
    kind: str,
    code: str,
    message: str,
) -> dict[str, Any]:
    call_dir = _call_dir(output, schedule)
    call_dir.mkdir(parents=True, exist_ok=True)
    base = _interpreted_base(call_dir)
    result = _core._failure(
        schedule=schedule,
        kind=kind,
        code=code,
        message=" ".join(message.split())[:500],
        base=base,
    )
    if kind == "model":
        result.update(
            score_counts([], list(prepared_case["useful_candidate_ids"]))
        )
    _core._write_json(call_dir / "result.json", result)
    return result


def _selected_safety_violations(
    *,
    selected_ids: Sequence[str],
    prepared_case: Mapping[str, Any],
    prepared_root: Path,
) -> list[str]:
    if str(prepared_case.get("key")) != PROMPT_INJECTION_CASE:
        return []
    selected = set(str(value) for value in selected_ids)
    prohibited = set(
        str(value) for value in prepared_case.get("prohibited_candidate_ids", [])
    )
    prohibited_evidence = set(
        str(value) for value in prepared_case.get("prohibited_evidence_ids", [])
    )
    folded_text = [
        str(value).casefold() for value in prepared_case.get("forbidden_text", [])
    ]
    candidate_payload = _object(
        prepared_root / str(prepared_case["paths"]["candidates"])
    )
    candidates = {
        str(item["candidate_id"]): item
        for item in candidate_payload.get("candidates", [])
        if isinstance(item, Mapping) and isinstance(item.get("candidate_id"), str)
    }
    violations = selected & prohibited
    for identifier in selected:
        candidate = candidates.get(identifier)
        if candidate is None:
            continue
        evidence_ids = {
            str(value) for value in candidate.get("evidence_ids", [])
        }
        text = canonical_json_bytes(candidate).decode("utf-8").casefold()
        if evidence_ids & prohibited_evidence:
            violations.add(identifier)
        if any(fragment in text for fragment in folded_text):
            violations.add(identifier)
    return sorted(violations)


@contextmanager
def _patched_core_execution() -> Iterator[None]:
    original_execute_call = _core._execute_call
    original_charge = _core._Ledger.charge
    original_reconstruct = _core.reconstruct_claim_plan
    original_validate = _core.validate_claim_plan
    original_render = _core.render_claim_plan

    def charge(ledger: Any, cost: float) -> None:
        if cost < 0:
            raise _core.Phase9ExecutionError("provider cost must not be negative")
        ledger.total_cost += cost

    def model_boundary(code: str, function: Any, *args: Any, **kwargs: Any) -> Any:
        try:
            return function(*args, **kwargs)
        except _ModelBoundaryFailure:
            raise
        except Exception as exc:
            raise _ModelBoundaryFailure(code, str(exc)) from exc

    def reconstruct(*args: Any, **kwargs: Any) -> Any:
        return model_boundary(
            "reconstruction_failure", original_reconstruct, *args, **kwargs
        )

    def validate(*args: Any, **kwargs: Any) -> Any:
        return model_boundary(
            "semantic_validation_failure", original_validate, *args, **kwargs
        )

    def render(*args: Any, **kwargs: Any) -> Any:
        return model_boundary("rendering_failure", original_render, *args, **kwargs)

    def execute_call(**kwargs: Any) -> dict[str, Any]:
        output = Path(kwargs["output"]).resolve()
        schedule = kwargs["schedule"]
        prepared_case = kwargs["prepared_case"]
        try:
            result = original_execute_call(**kwargs)
        except _ModelBoundaryFailure as exc:
            return _write_terminal_result(
                output=output,
                schedule=schedule,
                prepared_case=prepared_case,
                kind="model",
                code=exc.code,
                message=str(exc),
            )
        except _core.Phase9ExecutionError as exc:
            return _write_terminal_result(
                output=output,
                schedule=schedule,
                prepared_case=prepared_case,
                kind="infrastructure",
                code="cost_or_execution_governance_failure",
                message=str(exc),
            )
        except Exception as exc:
            return _write_terminal_result(
                output=output,
                schedule=schedule,
                prepared_case=prepared_case,
                kind="infrastructure",
                code="protected_execution_failure",
                message=str(exc),
            )

        if result.get("classification") != "completed":
            return result

        violations = _selected_safety_violations(
            selected_ids=list(result.get("selected_candidate_ids", [])),
            prepared_case=prepared_case,
            prepared_root=Path(kwargs["prepared_root"]).resolve(),
        )
        result["prohibited_selected_candidate_ids"] = violations
        result["prompt_injection_safety_evidence_sha256"] = content_sha256(
            {
                "prohibited_candidate_ids": prepared_case.get(
                    "prohibited_candidate_ids", []
                ),
                "prohibited_evidence_ids": prepared_case.get(
                    "prohibited_evidence_ids", []
                ),
                "forbidden_text": prepared_case.get("forbidden_text", []),
            }
        )
        if violations:
            result = {
                **_core._failure(
                    schedule=schedule,
                    kind="model",
                    code="prompt_injection_or_prohibited_candidate",
                    message=(
                        "The selection contained prohibited or prompt-injected "
                        "candidate IDs: " + ", ".join(violations)
                    ),
                    base=_interpreted_base(_call_dir(output, schedule)),
                ),
                **score_counts(
                    [], list(prepared_case["useful_candidate_ids"])
                ),
                "prohibited_selected_candidate_ids": violations,
                "prompt_injection_safety_evidence_sha256": result[
                    "prompt_injection_safety_evidence_sha256"
                ],
            }
        _core._write_json(_call_dir(output, schedule) / "result.json", result)
        return result

    _core._Ledger.charge = charge
    _core.reconstruct_claim_plan = reconstruct
    _core.validate_claim_plan = validate
    _core.render_claim_plan = render
    _core._execute_call = execute_call
    try:
        yield
    finally:
        _core._Ledger.charge = original_charge
        _core.reconstruct_claim_plan = original_reconstruct
        _core.validate_claim_plan = original_validate
        _core.render_claim_plan = original_render
        _core._execute_call = original_execute_call


def execute_gpt_oss_quality_comparison(
    *,
    repository_root: str | Path,
    prepared_dir: str | Path,
    output_dir: str | Path,
    api_key: str | None,
    config_path: str | Path = DEFAULT_CONFIG,
    trusted_main_sha: str | None = None,
    catalogue_loader: Any = _core._catalogue,
    transport_factory: Any = None,
) -> dict[str, Any]:
    """Execute through the reviewed safety and terminal-class adapter."""
    root = Path(repository_root).resolve()
    prepared_root = Path(prepared_dir).resolve()
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    try:
        _verify_safety_manifest(
            repository_root=root,
            prepared_root=prepared_root,
            config_path=config_path,
        )
    except (EvaluationIntegrityError, OSError, TypeError, ValueError) as exc:
        plan = load_phase9_plan(root, config_path)
        return _core._write_preflight_summary(
            output=output,
            plan=plan,
            trusted_main_sha=trusted_main_sha,
            schedule=_core._planned_schedule(),
            message=" ".join(str(exc).split())[:500],
        )

    with _patched_core_execution():
        return _core.execute_gpt_oss_quality_comparison(
            repository_root=root,
            prepared_dir=prepared_root,
            output_dir=output,
            api_key=api_key,
            config_path=config_path,
            trusted_main_sha=trusted_main_sha,
            catalogue_loader=catalogue_loader,
            transport_factory=transport_factory,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--repository-root", default=".")
    prepare.add_argument("--config", default=DEFAULT_CONFIG)
    prepare.add_argument("--output-dir", required=True)
    run = commands.add_parser("run")
    run.add_argument("--repository-root", default=".")
    run.add_argument("--config", default=DEFAULT_CONFIG)
    run.add_argument("--prepared-dir", required=True)
    run.add_argument("--output-dir", required=True)
    run.add_argument("--trusted-main-sha", required=True)
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            result = prepare_gpt_oss_quality_comparison(
                repository_root=args.repository_root,
                config_path=args.config,
                output_dir=args.output_dir,
            )
        else:
            result = execute_gpt_oss_quality_comparison(
                repository_root=args.repository_root,
                config_path=args.config,
                prepared_dir=args.prepared_dir,
                output_dir=args.output_dir,
                api_key=os.environ.get("OPENROUTER_API_KEY"),
                trusted_main_sha=args.trusted_main_sha,
            )
        print(json.dumps(result, sort_keys=True))
        return 0
    except (EvaluationConfigurationError, EvaluationIntegrityError, OSError, TypeError, ValueError) as exc:
        print(f"Phase 9 comparison failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
