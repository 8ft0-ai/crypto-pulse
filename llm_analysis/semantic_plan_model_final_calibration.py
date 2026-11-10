"""Run the final two-call semantic claim-plan compatibility calibration."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any, Mapping

import yaml

from .contracts import canonical_json_bytes
from .evaluation import (
    ACTIONS_SUMMARY,
    PREPARED_MANIFEST,
    EvaluationConfigurationError,
    EvaluationIntegrityError,
    PreparedCase,
    _catalogue,
    _read_json,
    _write_json,
)
from .evaluation_viability import (
    ATTEMPT_RECORDS_FILE,
    AttemptPacer,
    ClassifiedTransport,
    PacedClientFactory,
    load_viability_policy,
)
from .generation_config import model_matches
from .openrouter_client import HttpResponse, OpenRouterClient, Transport, UrllibTransport
from .paid_benchmark import check_paid_model_availability
from .semantic_plan_benchmark import (
    _prepared_cases,
    _run_one,
    _validate_profile_chain,
    load_semantic_plan_profile,
)
from .semantic_plan_model_calibration import (
    DiagnosticTransport,
    _redact,
    _write_diagnostics,
)
from .semantic_plan_model_evaluation import _runtime, _validated_classification_map
from .semantic_plan_model_selection_config import Candidate, load_expectations, load_selection_plan
from .semantic_plan_model_selection_scoring import evaluate_validated_expectation
from .semantic_plan_protected_runner import projected_paid_route_probe

VERSION = "semantic-plan-model-final-calibration/v1"
SUMMARY_FILE = "model-final-calibration-summary.json"
NORMALISATION_FILE = "evidence-normalisation.json"
DIAGNOSTICS_FILE = "provider-diagnostics.json"
EXECUTION_MESSAGE = "Return the JSON claim plan required by the system instructions."
EXPECTED_CANDIDATES = ("gpt-5-6-sol", "nex-n2-mini")


def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise EvaluationConfigurationError(f"{path} must be an object")
    return value


def load_final_calibration_config(
    root: Path, path: str | Path
) -> tuple[Any, tuple[Candidate, ...], dict[str, dict[str, Any]], str, float]:
    relative = str(path)
    candidate_path = Path(relative)
    if candidate_path.is_absolute() or ".." in candidate_path.parts:
        raise EvaluationConfigurationError("final calibration config path must be repository-relative")
    raw = _mapping(yaml.safe_load((root / relative).read_text(encoding="utf-8")), relative)
    expected_keys = {
        "version",
        "base_selection_config",
        "smoke_case_key",
        "maximum_total_cost_usd",
        "candidates",
    }
    if set(raw) != expected_keys or raw.get("version") != 1:
        raise EvaluationConfigurationError(
            "final calibration config must use version 1 and exact supported keys"
        )
    base = load_selection_plan(root, str(raw["base_selection_config"]))
    indexed = {candidate.key: candidate for candidate in base.candidates}
    if any(key not in indexed for key in EXPECTED_CANDIDATES):
        raise EvaluationConfigurationError("base selection config is missing a final candidate")
    selected = tuple(indexed[key] for key in EXPECTED_CANDIDATES)
    overrides = _mapping(raw.get("candidates"), "candidates")
    if tuple(overrides) != EXPECTED_CANDIDATES:
        raise EvaluationConfigurationError(
            "final calibration candidates must be GPT-5.6 Sol then Nex N2 Mini"
        )
    maximum_total_cost = float(raw["maximum_total_cost_usd"])
    if maximum_total_cost != 0.25:
        raise EvaluationConfigurationError("final calibration whole-run ceiling must remain USD 0.25")
    parsed: dict[str, dict[str, Any]] = {}
    for candidate in selected:
        row = _mapping(overrides[candidate.key], f"candidates.{candidate.key}")
        expected = {
            "maximum_generation_cost_usd",
            "maximum_model_cost_usd",
            "max_output_tokens",
            "ensure_user_message",
        }
        if set(row) != expected:
            raise EvaluationConfigurationError(f"candidates.{candidate.key} has unsupported keys")
        generation_cap = float(row["maximum_generation_cost_usd"])
        model_cap = float(row["maximum_model_cost_usd"])
        max_output_tokens = int(row["max_output_tokens"])
        ensure_user_message = row["ensure_user_message"]
        if generation_cap <= 0 or model_cap <= generation_cap:
            raise EvaluationConfigurationError(f"candidates.{candidate.key} cost ceilings are invalid")
        if not 16 <= max_output_tokens <= 16_384:
            raise EvaluationConfigurationError(
                f"candidates.{candidate.key}.max_output_tokens is invalid"
            )
        if not isinstance(ensure_user_message, bool):
            raise EvaluationConfigurationError(
                f"candidates.{candidate.key}.ensure_user_message must be boolean"
            )
        parsed[candidate.key] = {
            "maximum_generation_cost_usd": generation_cap,
            "maximum_model_cost_usd": model_cap,
            "max_output_tokens": max_output_tokens,
            "ensure_user_message": ensure_user_message,
        }
    if parsed["gpt-5-6-sol"]["ensure_user_message"] is not False:
        raise EvaluationConfigurationError("GPT-5.6 must preserve the existing message shape")
    if parsed["nex-n2-mini"]["ensure_user_message"] is not True:
        raise EvaluationConfigurationError("Nex N2 Mini must receive the user-role compatibility message")
    if sum(row["maximum_model_cost_usd"] for row in parsed.values()) > maximum_total_cost:
        raise EvaluationConfigurationError("candidate ceilings exceed the whole final calibration ceiling")
    return base, selected, parsed, str(raw["smoke_case_key"]), maximum_total_cost


class FinalRequestTransform:
    """Apply only the checked per-route compatibility transforms."""

    def __init__(
        self,
        inner: Transport,
        *,
        send_temperature: bool,
        ensure_user_message: bool,
    ) -> None:
        self.inner = inner
        self.send_temperature = send_temperature
        self.ensure_user_message = ensure_user_message

    def post(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        body: bytes,
        timeout_seconds: float,
    ) -> HttpResponse:
        payload = json.loads(body.decode("utf-8"))
        if not isinstance(payload, dict):
            raise EvaluationIntegrityError("OpenRouter request body must be an object")
        if not self.send_temperature:
            payload.pop("temperature", None)
        messages = payload.get("messages")
        if not isinstance(messages, list) or not all(isinstance(item, Mapping) for item in messages):
            raise EvaluationIntegrityError("OpenRouter request messages must be an array of objects")
        if self.ensure_user_message and not any(item.get("role") == "user" for item in messages):
            messages.append({"role": "user", "content": EXECUTION_MESSAGE})
        transformed = canonical_json_bytes(payload)
        return self.inner.post(
            url,
            headers=headers,
            body=transformed,
            timeout_seconds=timeout_seconds,
        )


def normalise_cross_source_prices(bundle: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Normalise Coinbase USD spot price fields to the canonical price_usd measure."""
    normalised = json.loads(canonical_json_bytes(bundle).decode("utf-8"))
    evidence = normalised.get("evidence")
    if not isinstance(evidence, list):
        raise EvaluationIntegrityError("evidence bundle is missing evidence records")
    changes: list[dict[str, str]] = []
    for record in evidence:
        if not isinstance(record, dict):
            continue
        source = record.get("source")
        if (
            isinstance(source, Mapping)
            and source.get("name") == "coinbase_exchange"
            and record.get("field") == "price"
            and record.get("unit") == "usd"
            and isinstance(record.get("evidence_id"), str)
            and record["evidence_id"].endswith(".price")
        ):
            record["field"] = "price_usd"
            changes.append(
                {
                    "evidence_id": record["evidence_id"],
                    "from_field": "price",
                    "to_field": "price_usd",
                }
            )
    if not changes:
        raise EvaluationIntegrityError("no Coinbase USD spot prices were available to normalise")
    previous_bundle_id = normalised.get("bundle_id")
    without_id = dict(normalised)
    without_id.pop("bundle_id", None)
    normalised["bundle_id"] = "sha256:" + hashlib.sha256(
        canonical_json_bytes(without_id)
    ).hexdigest()
    return normalised, {
        "version": "crypto-pulse-evidence-normalisation/v1",
        "rule": "coinbase_exchange.usd_spot.price->price_usd",
        "previous_bundle_id": previous_bundle_id,
        "normalised_bundle_id": normalised["bundle_id"],
        "changes": changes,
    }


def _prepare_normalised_case(
    prepared_root: Path,
    prepared: PreparedCase,
    output: Path,
) -> tuple[Path, PreparedCase]:
    source_bundle = _read_json(prepared_root / prepared.bundle_file)
    normalised, record = normalise_cross_source_prices(source_bundle)
    derived_root = output / "normalised-prepared"
    _write_json(derived_root / prepared.bundle_file, normalised)
    _write_json(output / NORMALISATION_FILE, record)
    return derived_root, replace(prepared, bundle_id=normalised["bundle_id"])


def _summary_markdown(summary: Mapping[str, Any]) -> str:
    maximum = int(summary.get("maximum_substantive_generations") or 0)
    lines = [
        "# Final semantic claim-plan model calibration",
        "",
        f"- Trusted main: `{summary.get('trusted_main_sha')}`",
        f"- Full-contract calls: `{summary.get('completed_substantive_generations')} / {maximum}`",
        f"- Observed cost: `${float(summary.get('observed_total_cost_usd') or 0):.6f}`",
        f"- Cost ceiling: `${float(summary.get('maximum_total_cost_usd') or 0):.2f}`",
        "- Deployment selection: `not performed`",
        "",
    ]
    for row in summary.get("models", []):
        lines.append(
            f"- `{row['model']}`: route `{row['route_status']}`, "
            f"full contract `{row['full_contract_status']}`, "
            f"validator accepted `{'yes' if row['validator_accepted'] else 'no'}`, "
            f"scored `{'yes' if row['scored'] else 'no'}`"
        )
    return "\n".join(lines) + "\n"


def execute_final_calibration(
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
        raise EvaluationIntegrityError("OPENROUTER_API_KEY is required for final model calibration")
    root = Path(repository_root).resolve()
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    base, selected, overrides, smoke_case_key, maximum_total_cost = load_final_calibration_config(
        root, config_path
    )
    expectations = load_expectations(root, base.expectations_path)
    base_profile = load_semantic_plan_profile(root, base.base_profile)
    public_profile, base_plan, classifications = _validate_profile_chain(root, base_profile)
    classifications_by_case = _validated_classification_map(classifications)
    prepared_root = Path(prepared_dir)
    prepared_cases = _prepared_cases(base_plan, prepared_root)
    prepared = next((item for item in prepared_cases if item.key == smoke_case_key), None)
    manifest = _read_json(prepared_root / PREPARED_MANIFEST)
    if prepared is None or not isinstance(manifest.get("semantic_model_selection"), Mapping):
        raise EvaluationIntegrityError("prepared model-selection corpus is invalid")
    if smoke_case_key not in expectations:
        raise EvaluationIntegrityError("final calibration smoke case has no expectation contract")
    normalised_root, normalised_prepared = _prepare_normalised_case(
        prepared_root, prepared, output
    )

    catalogue = (catalogue_loader or _catalogue)()
    pacer = AttemptPacer(load_viability_policy(root / base.viability_config))
    availability_rows: list[dict[str, Any]] = []
    route_rows: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    observed_cost = 0.0

    for index, original in enumerate(selected, 1):
        override = overrides[original.key]
        candidate: Candidate = replace(
            original,
            repeats_per_case=1,
            maximum_generation_cost_usd=override["maximum_generation_cost_usd"],
            maximum_model_cost_usd=override["maximum_model_cost_usd"],
        )
        print(f"[final-calibration] model {index}/2 {candidate.model}: preparing", flush=True)
        profile, candidate_plan, runtime = _runtime(
            root, output, public_profile, base_profile, base_plan, candidate
        )
        runtime = replace(runtime, max_output_tokens=override["max_output_tokens"])
        _write_json(
            output / "runtime-configs" / f"{candidate.key}-final-calibration.json",
            {
                "model": runtime.model,
                "temperature_sent": candidate.send_temperature,
                "ensure_user_message": override["ensure_user_message"],
                "max_output_tokens": runtime.max_output_tokens,
                "max_cost_usd": runtime.max_cost_usd,
                "provider_policy": runtime.provider_policy.as_request(),
                "cross_model_fallback": runtime.cross_model_fallback,
            },
        )
        availability = check_paid_model_availability(
            candidate_plan, catalogue_loader=lambda: catalogue
        )
        availability_rows.append(
            {
                "candidate": {
                    **asdict(candidate),
                    "max_output_tokens": override["max_output_tokens"],
                    "ensure_user_message": override["ensure_user_message"],
                },
                "availability": asdict(availability.availability),
                "prompt_price_per_million": availability.prompt_price_per_million,
                "completion_price_per_million": availability.completion_price_per_million,
            }
        )
        if not availability.availability.eligible:
            results.append(
                {
                    "model": candidate.model,
                    "role": candidate.role,
                    "route_status": "not_attempted",
                    "full_contract_status": "not_attempted",
                    "failure_code": availability.availability.reason,
                    "validator_accepted": False,
                    "scored": False,
                    "semantic_coverage": None,
                    "materiality": None,
                    "restraint": None,
                    "total_cost_usd": 0.0,
                }
            )
            continue

        route_capture = DiagnosticTransport(UrllibTransport(), secret=api_key)
        try:
            route_result = pacer.call(
                f"final-calibration-route/{candidate.key}",
                lambda: projected_paid_route_probe(
                    runtime,
                    api_key,
                    transport=FinalRequestTransform(
                        route_capture,
                        send_temperature=candidate.send_temperature,
                        ensure_user_message=False,
                    ),
                ),
            )
            route = {"model_key": candidate.key, "status": "passed", **dict(route_result)}
            route_cost = float(route_result.get("estimated_cost_usd") or 0.0)
            observed_cost += route_cost
        except Exception as exc:
            route = {
                "model_key": candidate.key,
                "requested_model": candidate.model,
                "status": "failed",
                "failure_code": str(
                    getattr(exc, "code", None) or "route_preflight_failure"
                ),
                "message": _redact(exc, api_key, 500),
            }
            route_cost = 0.0
        route_rows.append(route)
        _write_diagnostics(
            output / "route-diagnostics" / f"{candidate.key}.json",
            route_capture.records,
        )
        print(f"[final-calibration] {candidate.model}: route {route['status']}", flush=True)
        if route["status"] != "passed":
            results.append(
                {
                    "model": candidate.model,
                    "role": candidate.role,
                    "route_status": "failed",
                    "full_contract_status": "not_attempted",
                    "failure_code": route.get("failure_code"),
                    "validator_accepted": False,
                    "scored": False,
                    "semantic_coverage": None,
                    "materiality": None,
                    "restraint": None,
                    "route_cost_usd": route_cost,
                    "total_cost_usd": route_cost,
                }
            )
            continue

        capture = DiagnosticTransport(UrllibTransport(), secret=api_key)
        transport = FinalRequestTransform(
            ClassifiedTransport(capture),
            send_temperature=candidate.send_temperature,
            ensure_user_message=override["ensure_user_message"],
        )
        factory = PacedClientFactory(
            pacer,
            builder=lambda config, transport=transport: OpenRouterClient(
                config, transport=transport
            ),
        )
        factory.set_logical_id(
            f"final-calibration/{candidate.key}/{normalised_prepared.key}/repeat-1"
        )
        print(
            f"[final-calibration] {candidate.model}: full contract started "
            f"(max_output_tokens={override['max_output_tokens']})",
            flush=True,
        )
        record = _run_one(
            root=root,
            profile=profile,
            plan=candidate_plan,
            config=runtime,
            prepared=normalised_prepared,
            prepared_dir=normalised_root,
            repeat=1,
            classification=classifications_by_case[normalised_prepared.key],
            output=output,
            api_key=api_key,
            client_factory=factory,
        )
        response = capture.records[-1] if capture.records else {}
        generation_cost = record.estimated_cost_usd
        if generation_cost is None and isinstance(
            response.get("estimated_cost_usd"), (int, float)
        ):
            generation_cost = float(response["estimated_cost_usd"])
        observed_cost += float(generation_cost or 0.0)
        run_dir = output / record.output_dir
        _write_diagnostics(run_dir / DIAGNOSTICS_FILE, capture.records)

        canonical = run_dir / "canonical-claim-plan.json"
        validator_accepted = (
            record.status == "accepted" and record.plan_valid and canonical.exists()
        )
        expectation = evaluate_validated_expectation(
            _read_json(canonical) if canonical.exists() else None,
            expectations[normalised_prepared.key],
            validator_accepted=validator_accepted,
        )
        scored = expectation is not None
        if expectation is not None:
            _write_json(run_dir / "case-expectation.json", asdict(expectation))
        passed = (
            validator_accepted
            and expectation is not None
            and expectation.hard_pass
            and record.actual_model is not None
            and model_matches(candidate.model, record.actual_model)
            and bool(record.actual_provider)
            and record.cross_model_fallback_used is False
            and generation_cost is not None
        )
        model_cost = route_cost + float(generation_cost or 0.0)
        if model_cost > candidate.maximum_model_cost_usd + 1e-12:
            raise EvaluationIntegrityError(
                f"{candidate.model} exceeded its final calibration model ceiling"
            )
        results.append(
            {
                "model": candidate.model,
                "role": candidate.role,
                "route_status": "passed",
                "full_contract_status": "passed" if passed else record.status,
                "failure_code": None if passed else record.failure_code,
                "validator_accepted": validator_accepted,
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
                "total_cost_usd": model_cost,
                "max_output_tokens": override["max_output_tokens"],
                "user_message_added": override["ensure_user_message"],
                "provider_diagnostics_retained": bool(capture.records),
                "output_dir": record.output_dir,
            }
        )
        print(
            f"[final-calibration] {candidate.model}: full contract {record.status}"
            + (f" ({record.failure_code})" if record.failure_code else ""),
            flush=True,
        )

    _write_json(output / "model-availability.json", {"models": availability_rows})
    _write_json(output / "route-preflight.json", {"routes": route_rows})
    _write_json(
        output / ATTEMPT_RECORDS_FILE,
        {"attempts": [asdict(item) for item in pacer.records]},
    )
    if observed_cost > maximum_total_cost + 1e-12:
        raise EvaluationIntegrityError(
            "observed final calibration cost exceeded the USD 0.25 ceiling"
        )
    summary = {
        "version": VERSION,
        "trusted_main_sha": trusted_main_sha,
        "smoke_case_key": smoke_case_key,
        "normalised_bundle_id": normalised_prepared.bundle_id,
        "maximum_substantive_generations": 2,
        "completed_substantive_generations": sum(
            row["full_contract_status"] != "not_attempted" for row in results
        ),
        "maximum_total_cost_usd": maximum_total_cost,
        "observed_total_cost_usd": observed_cost,
        "deployment_selection": False,
        "automatic_generation": False,
        "publication": False,
        "models": results,
    }
    _write_json(output / SUMMARY_FILE, summary)
    (output / ACTIONS_SUMMARY).write_text(_summary_markdown(summary), encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", default=".")
    parser.add_argument(
        "--config", default="config/semantic-plan-model-final-calibration.yml"
    )
    parser.add_argument("--prepared-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--trusted-main-sha")
    args = parser.parse_args()
    try:
        result = execute_final_calibration(
            repository_root=args.repository_root,
            config_path=args.config,
            prepared_dir=args.prepared_dir,
            output_dir=args.output_dir,
            api_key=os.environ.get("OPENROUTER_API_KEY"),
            trusted_main_sha=args.trusted_main_sha,
        )
        print(json.dumps(result, sort_keys=True))
        return 0
    except (
        EvaluationConfigurationError,
        EvaluationIntegrityError,
        OSError,
        ValueError,
        TypeError,
    ) as exc:
        print(f"final semantic model calibration failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
