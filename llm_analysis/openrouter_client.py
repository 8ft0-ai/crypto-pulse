"""Governed, bounded OpenRouter client for Phase 5 structured analysis."""

from __future__ import annotations

import hashlib
import json
import os
import socket
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .contracts import (
    ANALYSIS_SCHEMA_VERSION,
    EVIDENCE_SCHEMA_VERSION,
    PROVENANCE_SCHEMA_VERSION,
    PROMPT_VERSION,
    canonical_json_bytes,
    content_sha256,
)
from .generation_config import GenerationConfig, model_matches


class GenerationError(RuntimeError):
    code = "generation_error"

    def __init__(self, message: str):
        super().__init__(message)


class MissingSecretError(GenerationError):
    code = "missing_secret"


class InputLimitError(GenerationError):
    code = "input_limit"


class GenerationTimeoutError(GenerationError):
    code = "timeout"


class TransportGenerationError(GenerationError):
    code = "transport_error"


class AuthenticationGenerationError(GenerationError):
    code = "authentication_error"


class BillingGenerationError(GenerationError):
    code = "billing_error"


class ProviderGenerationError(GenerationError):
    code = "provider_error"


class InvalidResponseError(GenerationError):
    code = "invalid_response"


class IneligibleRoutingError(GenerationError):
    code = "ineligible_routing"


class CostLimitError(GenerationError):
    code = "cost_limit"


@dataclass(frozen=True)
class HttpResponse:
    status: int
    body: bytes
    headers: Mapping[str, str]


class Transport(Protocol):
    def post(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        body: bytes,
        timeout_seconds: float,
    ) -> HttpResponse: ...


class UrllibTransport:
    """Small standard-library transport; HTTP errors are returned for typed handling."""

    def post(
        self,
        url: str,
        *,
        headers: Mapping[str, str],
        body: bytes,
        timeout_seconds: float,
    ) -> HttpResponse:
        request = Request(url, data=body, headers=dict(headers), method="POST")
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                return HttpResponse(
                    status=response.status,
                    body=response.read(),
                    headers=dict(response.headers.items()),
                )
        except HTTPError as exc:
            return HttpResponse(
                status=exc.code,
                body=exc.read(),
                headers=dict(exc.headers.items()) if exc.headers else {},
            )
        except (TimeoutError, socket.timeout) as exc:
            raise GenerationTimeoutError("OpenRouter request timed out") from exc
        except URLError as exc:
            reason = getattr(exc, "reason", None)
            if isinstance(reason, (TimeoutError, socket.timeout)):
                raise GenerationTimeoutError("OpenRouter request timed out") from exc
            raise TransportGenerationError("OpenRouter transport failed") from exc


@dataclass(frozen=True)
class GenerationMetadata:
    requested_model: str
    actual_model: str | None
    actual_provider: str | None
    generation_id: str | None
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    estimated_cost_usd: float | None
    latency_ms: int
    provider_fallback_used: bool
    cross_model_fallback_used: bool
    provider_preferences: tuple[str, ...]
    router_attempt: int | None
    finish_reason: str | None


@dataclass(frozen=True)
class GenerationResult:
    analysis: dict[str, Any]
    raw_completion: str
    metadata: GenerationMetadata
    provenance: dict[str, Any]
    request_summary: dict[str, Any]


_RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504, 524, 529}
_TIMEOUT_STATUS = {408, 524}


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def render_prompt(prompt_template: str, evidence_bundle: Mapping[str, Any]) -> str:
    marker = "{{EVIDENCE_BUNDLE_JSON}}"
    if prompt_template.count(marker) != 1:
        raise InvalidResponseError("prompt template must contain exactly one evidence marker")
    evidence_json = canonical_json_bytes(evidence_bundle).decode("utf-8")
    return prompt_template.replace(marker, evidence_json)


def build_request_body(
    config: GenerationConfig,
    *,
    prompt_text: str,
    analysis_schema: Mapping[str, Any],
) -> dict[str, Any]:
    return {
        "model": config.model,
        "messages": [{"role": "system", "content": prompt_text}],
        "temperature": config.temperature,
        "max_tokens": config.max_output_tokens,
        "stream": False,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "crypto_market_analysis_v1",
                "strict": True,
                "schema": dict(analysis_schema),
            },
        },
        "provider": config.provider_policy.as_request(),
    }


def _safe_message(payload: Any, api_key: str) -> str:
    message = "OpenRouter request failed"
    if isinstance(payload, Mapping):
        error = payload.get("error")
        if isinstance(error, Mapping) and isinstance(error.get("message"), str):
            message = " ".join(error["message"].split())[:240]
    if api_key:
        message = message.replace(api_key, "[REDACTED]")
    return message


def _parse_json_bytes(body: bytes) -> Any:
    try:
        return json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise InvalidResponseError("OpenRouter returned a non-JSON response") from exc


def _selected_provider(metadata: Mapping[str, Any]) -> str | None:
    endpoints = metadata.get("endpoints")
    if isinstance(endpoints, Mapping):
        available = endpoints.get("available")
        if isinstance(available, list):
            for endpoint in available:
                if (
                    isinstance(endpoint, Mapping)
                    and endpoint.get("selected") is True
                    and isinstance(endpoint.get("provider"), str)
                ):
                    return endpoint["provider"]
    attempts = metadata.get("attempts")
    if isinstance(attempts, list):
        for attempt in reversed(attempts):
            if (
                isinstance(attempt, Mapping)
                and attempt.get("status") == 200
                and isinstance(attempt.get("provider"), str)
            ):
                return attempt["provider"]
    return None


def _normalise_provider(value: str) -> str:
    return "".join(character for character in value.lower() if character.isalnum())


def _check_selected_provider(config: GenerationConfig, provider: str | None) -> None:
    if provider is None:
        return
    selected = _normalise_provider(provider)
    if config.provider_policy.only:
        allowed = {_normalise_provider(item) for item in config.provider_policy.only}
        if selected not in allowed:
            raise IneligibleRoutingError("OpenRouter selected a provider outside provider_policy.only")
    ignored = {_normalise_provider(item) for item in config.provider_policy.ignore}
    if selected in ignored:
        raise IneligibleRoutingError("OpenRouter selected a provider in provider_policy.ignore")


def _provenance(
    *,
    config: GenerationConfig,
    evidence_bundle: Mapping[str, Any],
    prompt_text: str,
    completion: str,
    metadata: GenerationMetadata,
    generated_at: datetime,
) -> dict[str, Any]:
    source_snapshot = evidence_bundle.get("source_snapshot")
    if not isinstance(source_snapshot, Mapping):
        raise InvalidResponseError("evidence bundle is missing source_snapshot provenance")
    source_path = source_snapshot.get("path")
    source_sha = source_snapshot.get("sha256")
    bundle_id = evidence_bundle.get("bundle_id")
    if not isinstance(source_path, str) or not isinstance(source_sha, str):
        raise InvalidResponseError("evidence bundle source_snapshot provenance is invalid")
    if not isinstance(bundle_id, str):
        raise InvalidResponseError("evidence bundle is missing bundle_id")
    return {
        "schema_version": PROVENANCE_SCHEMA_VERSION,
        "provider": "openrouter",
        "requested_model": config.model,
        "actual_model": metadata.actual_model,
        "actual_provider": metadata.actual_provider,
        "prompt_version": PROMPT_VERSION,
        "analysis_schema_version": ANALYSIS_SCHEMA_VERSION,
        "evidence_schema_version": EVIDENCE_SCHEMA_VERSION,
        "source_snapshot": {"path": source_path, "sha256": source_sha},
        "evidence_bundle": {
            "bundle_id": bundle_id,
            "sha256": content_sha256(evidence_bundle),
        },
        "generated_at": generated_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "generation_parameters": {
            "temperature": config.temperature,
            "max_output_tokens": config.max_output_tokens,
        },
        "usage": {
            "input_tokens": metadata.input_tokens,
            "output_tokens": metadata.output_tokens,
            "total_tokens": metadata.total_tokens,
        },
        "generation_id": metadata.generation_id,
        "prompt_sha256": _sha256_text(prompt_text),
        "completion_sha256": _sha256_text(completion),
        "routing": {
            "provider_fallback_used": metadata.provider_fallback_used,
            "cross_model_fallback_used": False,
            "provider_preferences": list(metadata.provider_preferences),
        },
        "estimated_cost_usd": metadata.estimated_cost_usd,
    }


class OpenRouterClient:
    def __init__(
        self,
        config: GenerationConfig,
        *,
        transport: Transport | None = None,
        sleeper: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self.config = config
        self.transport = transport or UrllibTransport()
        self.sleeper = sleeper
        self.monotonic = monotonic
        self.now = now

    def generate(
        self,
        *,
        evidence_bundle: Mapping[str, Any],
        prompt_template: str,
        analysis_schema: Mapping[str, Any],
        api_key: str | None = None,
        environment: Mapping[str, str] | None = None,
    ) -> GenerationResult:
        env = os.environ if environment is None else environment
        secret = api_key if api_key is not None else env.get("OPENROUTER_API_KEY")
        if not secret or not secret.strip():
            raise MissingSecretError("OPENROUTER_API_KEY is required for optional LLM generation")
        secret = secret.strip()
        if "\r" in secret or "\n" in secret:
            raise MissingSecretError("OPENROUTER_API_KEY contains invalid line breaks")

        prompt_text = render_prompt(prompt_template, evidence_bundle)
        request_body = build_request_body(
            self.config,
            prompt_text=prompt_text,
            analysis_schema=analysis_schema,
        )
        body = canonical_json_bytes(request_body)
        if len(body) > self.config.max_request_bytes:
            raise InputLimitError(
                f"OpenRouter request is {len(body)} bytes; limit is {self.config.max_request_bytes}"
            )
        headers = {
            "Authorization": f"Bearer {secret}",
            "Content-Type": "application/json",
            "HTTP-Referer": self.config.app_referer,
            "X-OpenRouter-Title": self.config.app_title,
            "X-OpenRouter-Metadata": "enabled",
        }

        started = self.monotonic()
        response: HttpResponse | None = None
        for attempt in range(self.config.retry_limit + 1):
            try:
                response = self.transport.post(
                    self.config.endpoint,
                    headers=headers,
                    body=body,
                    timeout_seconds=self.config.timeout_seconds,
                )
            except GenerationTimeoutError:
                if attempt >= self.config.retry_limit:
                    raise
                self.sleeper(self.config.retry_backoff_seconds * (2**attempt))
                continue
            except TransportGenerationError:
                if attempt >= self.config.retry_limit:
                    raise
                self.sleeper(self.config.retry_backoff_seconds * (2**attempt))
                continue

            if response.status in _RETRYABLE_STATUS and attempt < self.config.retry_limit:
                self.sleeper(self.config.retry_backoff_seconds * (2**attempt))
                continue
            break

        if response is None:
            raise TransportGenerationError("OpenRouter request did not produce a response")
        latency_ms = max(0, int(round((self.monotonic() - started) * 1000)))
        payload = _parse_json_bytes(response.body)
        if not 200 <= response.status < 300:
            message = _safe_message(payload, secret)
            if response.status in _TIMEOUT_STATUS:
                raise GenerationTimeoutError(message)
            if response.status == 401:
                raise AuthenticationGenerationError(message)
            if response.status == 402:
                raise BillingGenerationError(message)
            if response.status in {403, 404}:
                raise IneligibleRoutingError(message)
            raise ProviderGenerationError(message)
        if not isinstance(payload, Mapping):
            raise InvalidResponseError("OpenRouter response must be a JSON object")

        generation_id = payload.get("id") if isinstance(payload.get("id"), str) else None
        actual_model = payload.get("model") if isinstance(payload.get("model"), str) else None
        if actual_model is not None and not model_matches(self.config.model, actual_model):
            raise IneligibleRoutingError("OpenRouter returned a different model than configured")

        choices = payload.get("choices")
        if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], Mapping):
            raise InvalidResponseError("OpenRouter response must contain exactly one choice")
        choice = choices[0]
        finish_reason = choice.get("finish_reason") if isinstance(choice.get("finish_reason"), str) else None
        if finish_reason != "stop":
            raise InvalidResponseError(f"OpenRouter completion ended with {finish_reason!r}")
        message = choice.get("message")
        if not isinstance(message, Mapping) or not isinstance(message.get("content"), str):
            raise InvalidResponseError("OpenRouter choice is missing message.content")
        completion = message["content"]
        try:
            analysis = json.loads(completion)
        except json.JSONDecodeError as exc:
            raise InvalidResponseError("OpenRouter completion is not valid JSON") from exc
        if not isinstance(analysis, dict):
            raise InvalidResponseError("OpenRouter completion must decode to a JSON object")

        usage = payload.get("usage")
        if not isinstance(usage, Mapping):
            usage = {}
        input_tokens = usage.get("prompt_tokens") if isinstance(usage.get("prompt_tokens"), int) else None
        output_tokens = (
            usage.get("completion_tokens") if isinstance(usage.get("completion_tokens"), int) else None
        )
        total_tokens = usage.get("total_tokens") if isinstance(usage.get("total_tokens"), int) else None
        cost = usage.get("cost")
        estimated_cost = float(cost) if isinstance(cost, (int, float)) and not isinstance(cost, bool) else None
        if estimated_cost is not None and estimated_cost > self.config.max_cost_usd:
            raise CostLimitError(
                f"OpenRouter response cost {estimated_cost:.6f} USD exceeds configured limit"
            )

        router_metadata = payload.get("openrouter_metadata")
        if not isinstance(router_metadata, Mapping):
            router_metadata = {}
        actual_provider = _selected_provider(router_metadata)
        _check_selected_provider(self.config, actual_provider)
        router_attempt = (
            router_metadata.get("attempt") if isinstance(router_metadata.get("attempt"), int) else None
        )
        attempts = router_metadata.get("attempts")
        provider_fallback_used = bool(
            (router_attempt is not None and router_attempt > 1)
            or (isinstance(attempts, list) and len(attempts) > 1)
        )
        metadata = GenerationMetadata(
            requested_model=self.config.model,
            actual_model=actual_model,
            actual_provider=actual_provider,
            generation_id=generation_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            estimated_cost_usd=estimated_cost,
            latency_ms=latency_ms,
            provider_fallback_used=provider_fallback_used,
            cross_model_fallback_used=False,
            provider_preferences=self.config.provider_policy.recorded_preferences,
            router_attempt=router_attempt,
            finish_reason=finish_reason,
        )
        provenance = _provenance(
            config=self.config,
            evidence_bundle=evidence_bundle,
            prompt_text=prompt_text,
            completion=completion,
            metadata=metadata,
            generated_at=self.now(),
        )
        return GenerationResult(
            analysis=analysis,
            raw_completion=completion,
            metadata=metadata,
            provenance=provenance,
            request_summary={
                "endpoint": self.config.endpoint,
                "model": self.config.model,
                "request_bytes": len(body),
                "timeout_seconds": self.config.timeout_seconds,
                "retry_limit": self.config.retry_limit,
                "provider_policy": self.config.provider_policy.as_request(),
                "structured_output": True,
            },
        )
