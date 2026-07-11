"""Strict reviewer-visible configuration for governed OpenRouter generation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Mapping
from urllib.parse import urlparse

import yaml

from .contracts import (
    ANALYSIS_SCHEMA_VERSION,
    EVIDENCE_SCHEMA_VERSION,
    PROMPT_VERSION,
)


class ConfigurationError(ValueError):
    """Raised when generation configuration weakens the governed boundary."""


@dataclass(frozen=True)
class ProviderPolicy:
    require_parameters: bool
    data_collection: str
    zdr: bool
    allow_fallbacks: bool
    order: tuple[str, ...]
    only: tuple[str, ...]
    ignore: tuple[str, ...]
    sort: str | None
    max_prompt_price_per_million: float
    max_completion_price_per_million: float
    max_request_price: float

    def as_request(self) -> dict[str, Any]:
        value: dict[str, Any] = {
            "require_parameters": self.require_parameters,
            "data_collection": self.data_collection,
            "zdr": self.zdr,
            "allow_fallbacks": self.allow_fallbacks,
            "max_price": {
                "prompt": self.max_prompt_price_per_million,
                "completion": self.max_completion_price_per_million,
                "request": self.max_request_price,
            },
        }
        if self.order:
            value["order"] = list(self.order)
        if self.only:
            value["only"] = list(self.only)
        if self.ignore:
            value["ignore"] = list(self.ignore)
        if self.sort:
            value["sort"] = self.sort
        return value

    @property
    def recorded_preferences(self) -> tuple[str, ...]:
        if self.order:
            return self.order
        if self.only:
            return self.only
        return ()


@dataclass(frozen=True)
class GenerationConfig:
    provider: str
    endpoint: str
    model: str
    prompt_path: str
    analysis_schema_path: str
    prompt_version: str
    analysis_schema_version: str
    evidence_schema_version: str
    temperature: float
    max_output_tokens: int
    timeout_seconds: float
    retry_limit: int
    retry_backoff_seconds: float
    max_request_bytes: int
    max_cost_usd: float
    structured_output: bool
    cross_model_fallback: bool
    router_metadata: bool
    app_referer: str
    app_title: str
    provider_policy: ProviderPolicy


_TOP_LEVEL_KEYS = {
    "version",
    "provider",
    "api",
    "generation",
    "provider_policy",
    "app_attribution",
}
_API_KEYS = {
    "endpoint",
    "timeout_seconds",
    "retry_limit",
    "retry_backoff_seconds",
    "router_metadata",
}
_GENERATION_KEYS = {
    "model",
    "prompt_path",
    "analysis_schema_path",
    "prompt_version",
    "analysis_schema_version",
    "evidence_schema_version",
    "temperature",
    "max_output_tokens",
    "max_request_bytes",
    "max_cost_usd",
    "structured_output",
    "cross_model_fallback",
}
_POLICY_KEYS = {
    "require_parameters",
    "data_collection",
    "zdr",
    "allow_fallbacks",
    "order",
    "only",
    "ignore",
    "sort",
    "max_price",
}
_MAX_PRICE_KEYS = {"prompt", "completion", "request"}
_APP_KEYS = {"referer", "title"}


def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ConfigurationError(f"{path} must be an object")
    return value


def _exact_keys(value: Mapping[str, Any], allowed: set[str], path: str) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise ConfigurationError(f"{path} contains unknown keys: {', '.join(unknown)}")


def _string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigurationError(f"{path} must be a non-empty string")
    return value.strip()


def _bool(value: Any, path: str) -> bool:
    if not isinstance(value, bool):
        raise ConfigurationError(f"{path} must be a boolean")
    return value


def _number(value: Any, path: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigurationError(f"{path} must be a number")
    return float(value)


def _integer(value: Any, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigurationError(f"{path} must be an integer")
    return value


def _string_tuple(value: Any, path: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise ConfigurationError(f"{path} must be a list of non-empty strings")
    result = tuple(item.strip() for item in value)
    if len(set(result)) != len(result):
        raise ConfigurationError(f"{path} must not contain duplicates")
    return result


def _header_value(value: Any, path: str) -> str:
    text = _string(value, path)
    if "\r" in text or "\n" in text:
        raise ConfigurationError(f"{path} must not contain line breaks")
    return text


def _app_referer(value: Any) -> str:
    text = _header_value(value, "app_attribution.referer")
    parsed = urlparse(text)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ConfigurationError("app_attribution.referer must be an https URL")
    return text


def _relative_repository_path(value: Any, path: str) -> str:
    text = _string(value, path)
    candidate = PurePosixPath(text)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ConfigurationError(f"{path} must be a repository-relative path without '..'")
    return text


def _validate_endpoint(value: Any) -> str:
    endpoint = _string(value, "api.endpoint")
    parsed = urlparse(endpoint)
    if parsed.scheme != "https" or parsed.netloc != "openrouter.ai":
        raise ConfigurationError("api.endpoint must use https://openrouter.ai")
    if parsed.path != "/api/v1/chat/completions":
        raise ConfigurationError("api.endpoint must be the OpenRouter chat completions endpoint")
    return endpoint


def _base_model_slug(value: str) -> str:
    for suffix in (":free", ":nitro", ":floor", ":exacto"):
        if value.endswith(suffix):
            return value[: -len(suffix)]
    return value


def model_matches(requested: str, actual: str) -> bool:
    return _base_model_slug(requested) == _base_model_slug(actual)


def load_generation_config(path: str | Path) -> GenerationConfig:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    root = _mapping(raw, "configuration")
    _exact_keys(root, _TOP_LEVEL_KEYS, "configuration")
    if root.get("version") != 1:
        raise ConfigurationError("configuration.version must be 1")
    if root.get("provider") != "openrouter":
        raise ConfigurationError("configuration.provider must be 'openrouter'")

    api = _mapping(root.get("api"), "api")
    generation = _mapping(root.get("generation"), "generation")
    policy = _mapping(root.get("provider_policy"), "provider_policy")
    app = _mapping(root.get("app_attribution"), "app_attribution")
    _exact_keys(api, _API_KEYS, "api")
    _exact_keys(generation, _GENERATION_KEYS, "generation")
    _exact_keys(policy, _POLICY_KEYS, "provider_policy")
    _exact_keys(app, _APP_KEYS, "app_attribution")

    model = _string(generation.get("model"), "generation.model")
    if model in {"openrouter/free", "openrouter/auto"} or model.startswith("openrouter/"):
        raise ConfigurationError("generation.model must pin one explicit provider/model slug")
    if "/" not in _base_model_slug(model):
        raise ConfigurationError("generation.model must use an explicit provider/model slug")

    prompt_version = _string(generation.get("prompt_version"), "generation.prompt_version")
    analysis_schema_version = _string(
        generation.get("analysis_schema_version"), "generation.analysis_schema_version"
    )
    evidence_schema_version = _string(
        generation.get("evidence_schema_version"), "generation.evidence_schema_version"
    )
    if prompt_version != PROMPT_VERSION:
        raise ConfigurationError(f"generation.prompt_version must be {PROMPT_VERSION}")
    if analysis_schema_version != ANALYSIS_SCHEMA_VERSION:
        raise ConfigurationError(
            f"generation.analysis_schema_version must be {ANALYSIS_SCHEMA_VERSION}"
        )
    if evidence_schema_version != EVIDENCE_SCHEMA_VERSION:
        raise ConfigurationError(
            f"generation.evidence_schema_version must be {EVIDENCE_SCHEMA_VERSION}"
        )

    temperature = _number(generation.get("temperature"), "generation.temperature")
    if not 0 <= temperature <= 2:
        raise ConfigurationError("generation.temperature must be between 0 and 2")
    max_output_tokens = _integer(
        generation.get("max_output_tokens"), "generation.max_output_tokens"
    )
    if not 1 <= max_output_tokens <= 16_384:
        raise ConfigurationError("generation.max_output_tokens must be between 1 and 16384")
    max_request_bytes = _integer(
        generation.get("max_request_bytes"), "generation.max_request_bytes"
    )
    if not 1_024 <= max_request_bytes <= 5_000_000:
        raise ConfigurationError("generation.max_request_bytes must be between 1024 and 5000000")
    max_cost_usd = _number(generation.get("max_cost_usd"), "generation.max_cost_usd")
    if not 0 <= max_cost_usd <= 10:
        raise ConfigurationError("generation.max_cost_usd must be between 0 and 10")
    structured_output = _bool(
        generation.get("structured_output"), "generation.structured_output"
    )
    if not structured_output:
        raise ConfigurationError("generation.structured_output must remain true")
    cross_model_fallback = _bool(
        generation.get("cross_model_fallback"), "generation.cross_model_fallback"
    )
    if cross_model_fallback:
        raise ConfigurationError("generation.cross_model_fallback must remain false")

    timeout_seconds = _number(api.get("timeout_seconds"), "api.timeout_seconds")
    if not 1 <= timeout_seconds <= 300:
        raise ConfigurationError("api.timeout_seconds must be between 1 and 300")
    retry_limit = _integer(api.get("retry_limit"), "api.retry_limit")
    if not 0 <= retry_limit <= 2:
        raise ConfigurationError("api.retry_limit must be between 0 and 2")
    retry_backoff_seconds = _number(
        api.get("retry_backoff_seconds"), "api.retry_backoff_seconds"
    )
    if not 0 <= retry_backoff_seconds <= 30:
        raise ConfigurationError("api.retry_backoff_seconds must be between 0 and 30")
    router_metadata = _bool(api.get("router_metadata"), "api.router_metadata")
    if not router_metadata:
        raise ConfigurationError("api.router_metadata must remain true for routing auditability")

    require_parameters = _bool(
        policy.get("require_parameters"), "provider_policy.require_parameters"
    )
    if not require_parameters:
        raise ConfigurationError("provider_policy.require_parameters must remain true")
    data_collection = _string(
        policy.get("data_collection"), "provider_policy.data_collection"
    )
    if data_collection != "deny":
        raise ConfigurationError("provider_policy.data_collection must be 'deny'")
    zdr = _bool(policy.get("zdr"), "provider_policy.zdr")
    if not zdr:
        raise ConfigurationError("provider_policy.zdr must remain true")
    allow_fallbacks = _bool(
        policy.get("allow_fallbacks"), "provider_policy.allow_fallbacks"
    )
    order = _string_tuple(policy.get("order", []), "provider_policy.order")
    only = _string_tuple(policy.get("only", []), "provider_policy.only")
    ignore = _string_tuple(policy.get("ignore", []), "provider_policy.ignore")
    if set(only) & set(ignore):
        raise ConfigurationError("provider_policy.only and ignore must not overlap")
    sort_value = policy.get("sort")
    if sort_value is not None:
        sort_value = _string(sort_value, "provider_policy.sort")
        if sort_value not in {"price", "throughput", "latency"}:
            raise ConfigurationError(
                "provider_policy.sort must be price, throughput, latency, or null"
            )

    max_price = _mapping(policy.get("max_price"), "provider_policy.max_price")
    _exact_keys(max_price, _MAX_PRICE_KEYS, "provider_policy.max_price")
    max_prompt_price = _number(
        max_price.get("prompt"), "provider_policy.max_price.prompt"
    )
    max_completion_price = _number(
        max_price.get("completion"), "provider_policy.max_price.completion"
    )
    max_request_price = _number(
        max_price.get("request"), "provider_policy.max_price.request"
    )
    if min(max_prompt_price, max_completion_price, max_request_price) < 0:
        raise ConfigurationError("provider_policy.max_price values must be non-negative")

    return GenerationConfig(
        provider="openrouter",
        endpoint=_validate_endpoint(api.get("endpoint")),
        model=model,
        prompt_path=_relative_repository_path(
            generation.get("prompt_path"), "generation.prompt_path"
        ),
        analysis_schema_path=_relative_repository_path(
            generation.get("analysis_schema_path"), "generation.analysis_schema_path"
        ),
        prompt_version=prompt_version,
        analysis_schema_version=analysis_schema_version,
        evidence_schema_version=evidence_schema_version,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        timeout_seconds=timeout_seconds,
        retry_limit=retry_limit,
        retry_backoff_seconds=retry_backoff_seconds,
        max_request_bytes=max_request_bytes,
        max_cost_usd=max_cost_usd,
        structured_output=structured_output,
        cross_model_fallback=cross_model_fallback,
        router_metadata=router_metadata,
        app_referer=_app_referer(app.get("referer")),
        app_title=_header_value(app.get("title"), "app_attribution.title"),
        provider_policy=ProviderPolicy(
            require_parameters=require_parameters,
            data_collection=data_collection,
            zdr=zdr,
            allow_fallbacks=allow_fallbacks,
            order=order,
            only=only,
            ignore=ignore,
            sort=sort_value,
            max_prompt_price_per_million=max_prompt_price,
            max_completion_price_per_million=max_completion_price,
            max_request_price=max_request_price,
        ),
    )
