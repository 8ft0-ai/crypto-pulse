"""OpenRouter adapter for the repository-owned Slice 5 candidate selector."""
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from .candidate_selection_contract import render_candidate_selector_prompt
from .candidate_selector import SelectorClientResponse
from .contracts import canonical_json_bytes
from .evaluation import EvaluationIntegrityError
from .evaluation_viability import AttemptPacer
from .generation_config import GenerationConfig, model_matches
from .openrouter_client import (
    GenerationError,
    InvalidResponseError,
    Transport,
    _parse_json_bytes,
    _selected_provider,
)


@dataclass(frozen=True)
class CandidateSelectorCallRecord:
    call_number: int
    logical_id: str
    requested_model: str
    actual_model: str | None
    actual_provider: str | None
    generation_id: str | None
    raw_completion: str
    raw_completion_sha256: str
    request_sha256: str
    request_bytes: int
    response_schema_sha256: str
    repair_sha256: str | None
    latency_ms: int
    input_tokens: int
    output_tokens: int
    reasoning_tokens: int | None
    total_tokens: int
    estimated_cost_usd: float
    provider_fallback_used: bool
    cross_model_fallback_used: bool
    finish_reason: str | None

    def protected_dict(self) -> dict[str, Any]:
        return {
            "call_number": self.call_number,
            "logical_id": self.logical_id,
            "requested_model": self.requested_model,
            "actual_model": self.actual_model,
            "actual_provider": self.actual_provider,
            "generation_id": self.generation_id,
            "raw_completion": self.raw_completion,
            "raw_completion_sha256": self.raw_completion_sha256,
            "request_sha256": self.request_sha256,
            "request_bytes": self.request_bytes,
            "response_schema_sha256": self.response_schema_sha256,
            "repair_sha256": self.repair_sha256,
            "latency_ms": self.latency_ms,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "reasoning_tokens": self.reasoning_tokens,
            "total_tokens": self.total_tokens,
            "estimated_cost_usd": self.estimated_cost_usd,
            "provider_fallback_used": self.provider_fallback_used,
            "cross_model_fallback_used": self.cross_model_fallback_used,
            "finish_reason": self.finish_reason,
        }


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _required_int(value: Any, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise InvalidResponseError(f"OpenRouter response is missing {path}")
    return value


def _provider_fallback(metadata: Mapping[str, Any]) -> bool:
    router_attempt = metadata.get("attempt")
    attempts = metadata.get("attempts")
    return bool(
        (isinstance(router_attempt, int) and router_attempt > 1)
        or (isinstance(attempts, list) and len(attempts) > 1)
    )


class OpenRouterCandidateSelectorClient:
    """Translate the Slice 5 request into one governed strict-output call."""

    def __init__(
        self,
        config: GenerationConfig,
        *,
        prompt_template: str,
        api_key: str,
        logical_id: str,
        transport: Transport,
        pacer: AttemptPacer | None = None,
        send_temperature: bool = True,
        monotonic: Any = time.monotonic,
        before_provider_call: Callable[[float], None] | None = None,
        after_provider_call: Callable[[float], None] | None = None,
        evidence_root: str | Path | None = None,
    ) -> None:
        if not api_key or not api_key.strip() or "\n" in api_key or "\r" in api_key:
            raise ValueError("a valid OPENROUTER_API_KEY is required")
        if not config.provider_policy.only or len(config.provider_policy.only) != 1:
            raise ValueError("candidate selector must pin exactly one actual provider")
        if config.provider_policy.allow_fallbacks:
            raise ValueError("candidate selector provider fallback must remain disabled")
        if config.cross_model_fallback:
            raise ValueError("candidate selector cross-model fallback must remain disabled")
        self.config = config
        self.prompt_template = prompt_template
        self.api_key = api_key.strip()
        self.logical_id = logical_id
        self.transport = transport
        self.pacer = pacer
        self.send_temperature = send_temperature
        self.monotonic = monotonic
        self.before_provider_call = before_provider_call
        self.after_provider_call = after_provider_call
        configured_evidence = evidence_root or os.environ.get(
            "CRYPTOPULSE_SELECTOR_EVIDENCE_DIR"
        )
        self.evidence_root = (
            Path(configured_evidence).resolve() if configured_evidence else None
        )
        self.call_records: list[CandidateSelectorCallRecord] = []
        self._network_started: set[int] = set()

    def _evidence_path(self, call_number: int, suffix: str) -> Path | None:
        if self.evidence_root is None:
            return None
        return (
            self.evidence_root
            / Path(*self.logical_id.split("/"))
            / f"provider-call-{call_number}-{suffix}.json"
        )

    def _write_evidence(self, call_number: int, suffix: str, value: Mapping[str, Any]) -> None:
        path = self._evidence_path(call_number, suffix)
        if path is None:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(canonical_json_bytes(dict(value)) + b"\n")

    def select(
        self,
        *,
        request: Mapping[str, Any],
        response_schema: Mapping[str, Any],
        repair: Mapping[str, Any] | None,
    ) -> SelectorClientResponse:
        call_number = len(self.call_records) + 1
        operation = lambda: self._select_once(
            call_number=call_number,
            request=request,
            response_schema=response_schema,
            repair=repair,
        )
        try:
            return (
                self.pacer.call(f"{self.logical_id}/provider-call-{call_number}", operation)
                if self.pacer is not None
                else operation()
            )
        except GenerationError as exc:
            network_started = call_number in self._network_started
            if network_started and self.after_provider_call is not None:
                # Usage is unavailable, so reserve the reviewed per-call maximum.
                self.after_provider_call(self.config.max_cost_usd)
            message = " ".join(str(exc).split())[:500].replace(
                self.api_key, "[REDACTED]"
            )
            self._write_evidence(
                call_number,
                "unmetered-error",
                {
                    "call_number": call_number,
                    "logical_id": self.logical_id,
                    "requested_model": self.config.model,
                    "network_started": network_started,
                    "reserved_cost_usd": (
                        self.config.max_cost_usd if network_started else 0.0
                    ),
                    "code": str(getattr(exc, "code", "provider_error")),
                    "message": message,
                },
            )
            raise EvaluationIntegrityError(
                f"{self.logical_id} provider call lacked complete metering: {message}"
            ) from exc

    def _select_once(
        self,
        *,
        call_number: int,
        request: Mapping[str, Any],
        response_schema: Mapping[str, Any],
        repair: Mapping[str, Any] | None,
    ) -> SelectorClientResponse:
        prompt = render_candidate_selector_prompt(
            self.prompt_template,
            request,
            repair,
        )
        request_body: dict[str, Any] = {
            "model": self.config.model,
            "messages": [{"role": "system", "content": prompt}],
            "max_tokens": self.config.max_output_tokens,
            "stream": False,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "crypto_market_candidate_selection_v1",
                    "strict": True,
                    "schema": dict(response_schema),
                },
            },
            "provider": self.config.provider_policy.as_request(),
        }
        if self.send_temperature:
            request_body["temperature"] = self.config.temperature
        body = canonical_json_bytes(request_body)
        if len(body) > self.config.max_request_bytes:
            raise InvalidResponseError(
                f"candidate selector request is {len(body)} bytes; limit is {self.config.max_request_bytes}"
            )
        if self.before_provider_call is not None:
            self.before_provider_call(self.config.max_cost_usd)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.config.app_referer,
            "X-OpenRouter-Title": self.config.app_title,
            "X-OpenRouter-Metadata": "enabled",
        }
        self._network_started.add(call_number)
        started = self.monotonic()
        response = self.transport.post(
            self.config.endpoint,
            headers=headers,
            body=body,
            timeout_seconds=self.config.timeout_seconds,
        )
        latency_ms = max(0, int(round((self.monotonic() - started) * 1000)))
        payload = _parse_json_bytes(response.body)
        if not isinstance(payload, Mapping):
            raise InvalidResponseError("OpenRouter candidate selector response must be an object")

        usage = payload.get("usage") if isinstance(payload.get("usage"), Mapping) else {}
        cost_raw = usage.get("cost")
        if isinstance(cost_raw, bool) or not isinstance(cost_raw, (int, float)):
            raise InvalidResponseError("OpenRouter candidate selector did not report usage.cost")
        cost = float(cost_raw)
        input_tokens = _required_int(usage.get("prompt_tokens"), "usage.prompt_tokens")
        output_tokens = _required_int(
            usage.get("completion_tokens"), "usage.completion_tokens"
        )
        total_tokens = _required_int(usage.get("total_tokens"), "usage.total_tokens")
        details = usage.get("completion_tokens_details")
        reasoning_tokens = (
            details.get("reasoning_tokens")
            if isinstance(details, Mapping)
            and isinstance(details.get("reasoning_tokens"), int)
            and not isinstance(details.get("reasoning_tokens"), bool)
            else None
        )

        actual_model = payload.get("model") if isinstance(payload.get("model"), str) else None
        router_metadata = (
            payload.get("openrouter_metadata")
            if isinstance(payload.get("openrouter_metadata"), Mapping)
            else {}
        )
        actual_provider = _selected_provider(router_metadata)
        provider_fallback = _provider_fallback(router_metadata)
        cross_model_fallback = not (
            isinstance(actual_model, str)
            and model_matches(self.config.model, actual_model)
        )

        choices = payload.get("choices")
        choice = (
            choices[0]
            if isinstance(choices, list)
            and len(choices) == 1
            and isinstance(choices[0], Mapping)
            else {}
        )
        finish_reason = (
            choice.get("finish_reason")
            if isinstance(choice.get("finish_reason"), str)
            else None
        )
        message = choice.get("message")
        completion_value = message.get("content") if isinstance(message, Mapping) else None
        completion = completion_value if isinstance(completion_value, str) else ""
        decoded: Any = None
        if finish_reason == "stop" and completion:
            try:
                decoded = json.loads(completion)
            except json.JSONDecodeError:
                decoded = None

        generation_id = payload.get("id") if isinstance(payload.get("id"), str) else None
        record = CandidateSelectorCallRecord(
            call_number=call_number,
            logical_id=self.logical_id,
            requested_model=self.config.model,
            actual_model=actual_model,
            actual_provider=actual_provider,
            generation_id=generation_id,
            raw_completion=completion,
            raw_completion_sha256=_sha256_text(completion),
            request_sha256=_sha256_bytes(body),
            request_bytes=len(body),
            response_schema_sha256=_sha256_bytes(canonical_json_bytes(response_schema)),
            repair_sha256=(
                _sha256_bytes(canonical_json_bytes(repair)) if repair is not None else None
            ),
            latency_ms=latency_ms,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            reasoning_tokens=reasoning_tokens,
            total_tokens=total_tokens,
            estimated_cost_usd=cost,
            provider_fallback_used=provider_fallback,
            cross_model_fallback_used=cross_model_fallback,
            finish_reason=finish_reason,
        )
        self.call_records.append(record)
        self._write_evidence(call_number, "metered-response", record.protected_dict())

        # Account for the paid response before evaluating provider identity or model output.
        if self.after_provider_call is not None:
            self.after_provider_call(cost)
        if cost > self.config.max_cost_usd + 1e-12:
            raise EvaluationIntegrityError(
                f"OpenRouter candidate selector cost {cost:.6f} USD exceeds configured limit"
            )
        if actual_provider != self.config.provider_policy.only[0]:
            raise EvaluationIntegrityError(
                f"{self.logical_id} selected unapproved provider {actual_provider!r}"
            )
        if provider_fallback:
            raise EvaluationIntegrityError(
                f"{self.logical_id} used provider fallback"
            )
        if cross_model_fallback:
            raise EvaluationIntegrityError(
                f"{self.logical_id} did not preserve model {self.config.model!r}"
            )

        return SelectorClientResponse(
            payload=decoded,
            raw_response=completion,
            metadata={
                "client": "openrouter",
                "model": actual_model or "",
                "provider": actual_provider or "",
                "generation_id": generation_id or "",
                "latency_ms": latency_ms,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "estimated_cost_usd": cost,
            },
        )
