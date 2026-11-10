"""One bounded selector attempt, one semantic repair, then deterministic fallback."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence

from .candidate_selection_contract import (
    CandidateSelectionDiagnostic,
    SelectorEnvelopeError,
    build_candidate_selector_repair,
    build_candidate_selector_request,
    validate_candidate_selection,
)
from .claim_plan_render import ClaimPlanRender, render_claim_plan
from .claim_plan_validation import validate_claim_plan
from .contracts import canonical_json_bytes, content_sha256
from .deterministic_ranking import (
    DeterministicBaselineResult,
    RankingConfig,
    run_deterministic_baseline,
)
from .deterministic_reconstruction import reconstruct_claim_plan
from .openai_schema_projection import project_openai_strict_schema

CANDIDATE_SELECTOR_RUN_VERSION = "phase-06-bounded-candidate-selector-run/v1"


class SelectorClientError(RuntimeError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class SelectorClientResponse:
    payload: Any
    raw_response: str
    metadata: Mapping[str, Any]


class CandidateSelectorClient(Protocol):
    def select(
        self,
        *,
        request: Mapping[str, Any],
        response_schema: Mapping[str, Any],
        repair: Mapping[str, Any] | None,
    ) -> SelectorClientResponse: ...


class ScriptedCandidateSelectorClient:
    """Offline-only client used to prove selector control flow without a provider."""

    def __init__(self, steps: Sequence[SelectorClientResponse | SelectorClientError]):
        self._steps = list(steps)
        self.calls: list[dict[str, Any]] = []

    def select(
        self,
        *,
        request: Mapping[str, Any],
        response_schema: Mapping[str, Any],
        repair: Mapping[str, Any] | None,
    ) -> SelectorClientResponse:
        self.calls.append(
            {
                "request_sha256": content_sha256(request),
                "response_schema_sha256": content_sha256(response_schema),
                "repair_sha256": content_sha256(repair) if repair is not None else None,
            }
        )
        if not self._steps:
            raise SelectorClientError("script_exhausted", "no scripted response remains")
        step = self._steps.pop(0)
        if isinstance(step, SelectorClientError):
            raise step
        return step


@dataclass(frozen=True)
class BoundedCandidateSelectorResult:
    record: dict[str, Any]
    claim_plan: dict[str, Any]
    render: ClaimPlanRender

    @property
    def record_bytes(self) -> bytes:
        return canonical_json_bytes(self.record)

    @property
    def claim_plan_bytes(self) -> bytes:
        return canonical_json_bytes(self.claim_plan)


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _metadata(value: Mapping[str, Any]) -> dict[str, Any]:
    allowed = (
        "client",
        "model",
        "provider",
        "generation_id",
        "latency_ms",
        "input_tokens",
        "output_tokens",
        "estimated_cost_usd",
        "scripted",
        "scenario",
    )
    return {
        key: value[key]
        for key in allowed
        if key in value and isinstance(value[key], (str, int, float, bool))
    }


def _response_attempt(
    number: int,
    kind: str,
    response: SelectorClientResponse,
    validation: Any,
) -> dict[str, Any]:
    return {
        "attempt": number,
        "kind": kind,
        "raw_response_sha256": _hash_text(response.raw_response),
        "response": response.payload if isinstance(response.payload, Mapping) else None,
        "metadata": _metadata(response.metadata),
        "client_error": None,
        "validation": validation.as_dict(),
    }


def _error_attempt(
    number: int,
    kind: str,
    code: str,
    raw_response: str | None = None,
) -> dict[str, Any]:
    return {
        "attempt": number,
        "kind": kind,
        "raw_response_sha256": _hash_text(raw_response) if raw_response is not None else None,
        "response": None,
        "metadata": {},
        "client_error": code,
        "validation": None,
    }


def _record(
    *,
    request: Mapping[str, Any],
    provider_schema: Mapping[str, Any],
    baseline: DeterministicBaselineResult,
    attempts: Sequence[Mapping[str, Any]],
    outcome: str,
    selected_candidate_ids: Sequence[str],
    claim_plan: Mapping[str, Any],
    render: ClaimPlanRender,
    validation: Mapping[str, Any],
    fallback_reason: str | None = None,
    diagnostics: Sequence[CandidateSelectionDiagnostic] = (),
    repair: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    fallback = outcome == "deterministic_fallback"
    return {
        "version": CANDIDATE_SELECTOR_RUN_VERSION,
        "request": dict(request),
        "request_sha256": content_sha256(request),
        "provider_schema_sha256": content_sha256(provider_schema),
        "attempts": [dict(item) for item in attempts],
        "repair": dict(repair) if repair is not None else None,
        "selector_attempt_count": len(attempts),
        "semantic_repair_count": sum(item.get("kind") == "repair" for item in attempts),
        "outcome": outcome,
        "fallback_used": fallback,
        "fallback_reason": fallback_reason,
        "final_diagnostics": [item.as_dict() for item in diagnostics],
        "selected_candidate_ids": list(selected_candidate_ids),
        "baseline_selected_candidate_ids": list(baseline.selection["selected_candidate_ids"]),
        "baseline_selection_sha256": content_sha256(baseline.selection),
        "claim_plan_sha256": content_sha256(claim_plan),
        "rendered_markdown_sha256": hashlib.sha256(render.markdown).hexdigest(),
        "validation": dict(validation),
    }


def _fallback(
    *,
    request: Mapping[str, Any],
    provider_schema: Mapping[str, Any],
    baseline: DeterministicBaselineResult,
    attempts: Sequence[Mapping[str, Any]],
    reason: str,
    diagnostics: Sequence[CandidateSelectionDiagnostic] = (),
    repair: Mapping[str, Any] | None = None,
) -> BoundedCandidateSelectorResult:
    record = _record(
        request=request,
        provider_schema=provider_schema,
        baseline=baseline,
        attempts=attempts,
        outcome="deterministic_fallback",
        selected_candidate_ids=baseline.selection["selected_candidate_ids"],
        claim_plan=baseline.claim_plan,
        render=baseline.render,
        validation=baseline.validation.as_dict(),
        fallback_reason=reason,
        diagnostics=diagnostics,
        repair=repair,
    )
    return BoundedCandidateSelectorResult(record, baseline.claim_plan, baseline.render)


def run_bounded_candidate_selector(
    bundle: dict[str, Any],
    candidates: Sequence[Mapping[str, Any]],
    *,
    client: CandidateSelectorClient,
    config: RankingConfig,
    evidence_schema: dict[str, Any],
    candidate_schema: dict[str, Any],
    claim_plan_schema: dict[str, Any],
    selection_schema: dict[str, Any],
) -> BoundedCandidateSelectorResult:
    baseline = run_deterministic_baseline(
        bundle,
        candidates,
        config=config,
        evidence_schema=evidence_schema,
        candidate_schema=candidate_schema,
        claim_plan_schema=claim_plan_schema,
    )
    request = build_candidate_selector_request(
        candidates, config=config, evidence_bundle_id=bundle["bundle_id"]
    )
    provider_schema = project_openai_strict_schema(selection_schema)
    attempts: list[dict[str, Any]] = []
    repair: dict[str, Any] | None = None

    try:
        first = client.select(request=request, response_schema=provider_schema, repair=None)
    except SelectorClientError as exc:
        attempts.append(_error_attempt(1, "initial", exc.code))
        return _fallback(
            request=request,
            provider_schema=provider_schema,
            baseline=baseline,
            attempts=attempts,
            reason=f"client_error:{exc.code}",
        )
    try:
        validation = validate_candidate_selection(
            first.payload,
            candidates,
            config=config,
            evidence_bundle_id=bundle["bundle_id"],
            selection_schema=selection_schema,
        )
    except SelectorEnvelopeError as exc:
        attempts.append(_error_attempt(1, "initial", exc.code, first.raw_response))
        return _fallback(
            request=request,
            provider_schema=provider_schema,
            baseline=baseline,
            attempts=attempts,
            reason=f"malformed_envelope:{exc.code}",
        )
    attempts.append(_response_attempt(1, "initial", first, validation))
    selected_ids = validation.selected_candidate_ids

    if not validation.is_valid:
        repair = build_candidate_selector_repair(
            request,
            previous_raw_response_sha256=_hash_text(first.raw_response),
            previous_response=first.payload,
            diagnostics=validation.diagnostics,
        )
        try:
            second = client.select(
                request=request, response_schema=provider_schema, repair=repair
            )
        except SelectorClientError as exc:
            attempts.append(_error_attempt(2, "repair", exc.code))
            return _fallback(
                request=request,
                provider_schema=provider_schema,
                baseline=baseline,
                attempts=attempts,
                reason=f"repair_client_error:{exc.code}",
                diagnostics=validation.diagnostics,
                repair=repair,
            )
        try:
            repaired = validate_candidate_selection(
                second.payload,
                candidates,
                config=config,
                evidence_bundle_id=bundle["bundle_id"],
                selection_schema=selection_schema,
            )
        except SelectorEnvelopeError as exc:
            attempts.append(_error_attempt(2, "repair", exc.code, second.raw_response))
            return _fallback(
                request=request,
                provider_schema=provider_schema,
                baseline=baseline,
                attempts=attempts,
                reason=f"repair_malformed_envelope:{exc.code}",
                diagnostics=validation.diagnostics,
                repair=repair,
            )
        attempts.append(_response_attempt(2, "repair", second, repaired))
        if not repaired.is_valid:
            return _fallback(
                request=request,
                provider_schema=provider_schema,
                baseline=baseline,
                attempts=attempts,
                reason="semantic_repair_rejected",
                diagnostics=repaired.diagnostics,
                repair=repair,
            )
        selected_ids = repaired.selected_candidate_ids

    selection = {
        "evidence_bundle_id": bundle["bundle_id"],
        "selected_candidate_ids": list(selected_ids),
    }
    plan = reconstruct_claim_plan(selection, candidates, config=config)
    plan_validation = validate_claim_plan(
        bundle,
        plan,
        evidence_schema=evidence_schema,
        claim_plan_schema=claim_plan_schema,
    )
    if not plan_validation.is_valid:
        raise RuntimeError("validated candidate selection reconstructed to an invalid plan")
    rendered = render_claim_plan(bundle, plan, plan_validation)
    outcome = "accepted_after_repair" if repair is not None else "accepted_initial"
    record = _record(
        request=request,
        provider_schema=provider_schema,
        baseline=baseline,
        attempts=attempts,
        outcome=outcome,
        selected_candidate_ids=selected_ids,
        claim_plan=plan,
        render=rendered,
        validation=plan_validation.as_dict(),
        repair=repair,
    )
    return BoundedCandidateSelectorResult(record, plan, rendered)
