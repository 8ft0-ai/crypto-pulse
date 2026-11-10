"""Paced, staged free-model viability evaluation for governed Phase 5 analysis."""

from __future__ import annotations

import json
import random
import statistics
import time
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Protocol

import yaml

from .contracts import canonical_json_bytes
from .evaluation import (
    ACTIONS_SUMMARY,
    AVAILABILITY_FILE,
    DECISION_MARKDOWN,
    PREPARED_MANIFEST,
    REVIEWER_WORKSHEET,
    SUMMARY_JSON,
    CatalogueLoader,
    EvaluationConfigurationError,
    EvaluationIntegrityError,
    EvaluationModel,
    ModelAvailability,
    PreparedCase,
    RunRecord,
    _aggregate,
    _catalogue,
    _decision_text,
    _read_json,
    _write_json,
    check_model_availability,
    load_evaluation_plan,
)
from .evaluation_execution import _run_one
from .generation_config import ConfigurationError, GenerationConfig, load_generation_config, model_matches
from .openrouter_client import (
    AuthenticationGenerationError,
    BillingGenerationError,
    GenerationError,
    GenerationTimeoutError,
    HttpResponse,
    IneligibleRoutingError,
    OpenRouterClient,
    ProviderGenerationError,
    Transport,
    TransportGenerationError,
    UrllibTransport,
    _check_selected_provider,
    _parse_json_bytes,
    _selected_provider,
)

KEY_STATUS_FILE = "key-status.json"
ATTEMPT_RECORDS_FILE = "attempt-records.json"
STAGE_RESULTS_FILE = "viability-stages.json"


@dataclass(frozen=True)
class ViabilityPolicy:
    key_status_endpoint: str
    minimum_interval_seconds: float
    maximum_jitter_seconds: float
    maximum_attempts: int
    fallback_backoff_seconds: tuple[float, ...]
    maximum_delay_seconds: float
    smoke_case_key: str
    maximum_full_corpus_candidates: int


@dataclass(frozen=True)
class AttemptRecord:
    logical_id: str
    attempt: int
    started_at: str
    ended_at: str
    delay_before_seconds: float
    delay_source: str
    status: str
    classification: str
    response_status: int | None
    provider_code: str | None


class ProbeCallable(Protocol):
    def __call__(self, config: GenerationConfig, api_key: str) -> Mapping[str, Any]: ...


class KeyStatusLoader(Protocol):
    def __call__(self, api_key: str) -> Mapping[str, Any]: ...


class AttemptHttpError(GenerationError):
    code = "provider_error"

    def __init__(
        self,
        message: str,
        *,
        status: int | None,
        headers: Mapping[str, str] | None = None,
        provider_code: str | int | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.headers = {str(key).lower(): str(value) for key, value in (headers or {}).items()}
        self.provider_code = str(provider_code) if provider_code is not None else None


class RateLimitedError(AttemptHttpError):
    code = "rate_limited"


class ProviderCapacityError(AttemptHttpError):
    code = "provider_capacity"


class AttemptIneligibleRoutingError(IneligibleRoutingError):
    code = "ineligible_routing"

    def __init__(self, message: str, *, status: int | None, headers: Mapping[str, str] | None = None, provider_code: str | int | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.headers = {str(key).lower(): str(value) for key, value in (headers or {}).items()}
        self.provider_code = str(provider_code) if provider_code is not None else None


class AttemptAuthenticationError(AuthenticationGenerationError):
    def __init__(self, message: str, *, status: int | None, headers: Mapping[str, str] | None = None, provider_code: str | int | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.headers = {str(key).lower(): str(value) for key, value in (headers or {}).items()}
        self.provider_code = str(provider_code) if provider_code is not None else None


class AttemptBillingError(BillingGenerationError):
    def __init__(self, message: str, *, status: int | None, headers: Mapping[str, str] | None = None, provider_code: str | int | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.headers = {str(key).lower(): str(value) for key, value in (headers or {}).items()}
        self.provider_code = str(provider_code) if provider_code is not None else None


class AttemptTimeoutError(GenerationTimeoutError):
    def __init__(self, message: str, *, status: int | None, headers: Mapping[str, str] | None = None, provider_code: str | int | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.headers = {str(key).lower(): str(value) for key, value in (headers or {}).items()}
        self.provider_code = str(provider_code) if provider_code is not None else None


class ClassifiedTransport:
    """Convert non-success HTTP responses into attempt-aware typed errors."""

    def __init__(self, inner: Transport | None = None) -> None:
        self.inner = inner or UrllibTransport()

    def post(self, url: str, *, headers: Mapping[str, str], body: bytes, timeout_seconds: float) -> HttpResponse:
        response = self.inner.post(url, headers=headers, body=body, timeout_seconds=timeout_seconds)
        if 200 <= response.status < 300:
            return response
        try:
            payload = json.loads(response.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            payload = {}
        error = payload.get("error") if isinstance(payload, Mapping) else None
        metadata = error.get("metadata") if isinstance(error, Mapping) and isinstance(error.get("metadata"), Mapping) else {}
        provider_code = metadata.get("provider_code")
        error_type = str(metadata.get("error_type") or "")
        message = "OpenRouter request failed"
        if isinstance(error, Mapping) and isinstance(error.get("message"), str):
            message = " ".join(error["message"].split())[:240]
        authorization = str(headers.get("Authorization", ""))
        secret = authorization.removeprefix("Bearer ").strip()
        if secret:
            message = message.replace(secret, "[REDACTED]")
        common = {
            "status": response.status,
            "headers": response.headers,
            "provider_code": provider_code,
        }
        provider_status = str(provider_code) if provider_code is not None else ""
        if response.status == 429 or provider_status == "429" or error_type == "rate_limit_exceeded":
            raise RateLimitedError(message, **common)
        if response.status in {408, 524} or provider_status in {"408", "524"}:
            raise AttemptTimeoutError(message, **common)
        if response.status in {500, 502, 503, 504, 529} or provider_status in {"500", "502", "503", "504", "529"}:
            raise ProviderCapacityError(message, **common)
        if response.status == 401:
            raise AttemptAuthenticationError(message, **common)
        if response.status == 402:
            raise AttemptBillingError(message, **common)
        if response.status in {403, 404}:
            raise AttemptIneligibleRoutingError(message, **common)
        raise AttemptHttpError(message, **common)


def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise EvaluationConfigurationError(f"{path} must be an object")
    return value


def _number(value: Any, path: str, *, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise EvaluationConfigurationError(f"{path} must be a number")
    result = float(value)
    if not minimum <= result <= maximum:
        raise EvaluationConfigurationError(f"{path} must be between {minimum} and {maximum}")
    return result


def _integer(value: Any, path: str, *, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise EvaluationConfigurationError(f"{path} must be an integer between {minimum} and {maximum}")
    return value


def load_viability_policy(path: str | Path) -> ViabilityPolicy:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    root = _mapping(raw, "viability configuration")
    if set(root) != {"version", "key_status_endpoint", "pacing", "stages"} or root.get("version") != 1:
        raise EvaluationConfigurationError("viability configuration must use version 1 and exact supported keys")
    endpoint = root.get("key_status_endpoint")
    if endpoint != "https://openrouter.ai/api/v1/key":
        raise EvaluationConfigurationError("key_status_endpoint must be the OpenRouter key endpoint")
    pacing = _mapping(root.get("pacing"), "pacing")
    if set(pacing) != {"minimum_interval_seconds", "maximum_jitter_seconds", "maximum_attempts", "fallback_backoff_seconds", "maximum_delay_seconds"}:
        raise EvaluationConfigurationError("pacing contains unsupported keys")
    backoff = pacing.get("fallback_backoff_seconds")
    if not isinstance(backoff, list) or not backoff:
        raise EvaluationConfigurationError("fallback_backoff_seconds must be a non-empty list")
    backoff_values = tuple(_number(value, "fallback_backoff_seconds[]", minimum=0, maximum=300) for value in backoff)
    attempts = _integer(pacing.get("maximum_attempts"), "pacing.maximum_attempts", minimum=1, maximum=3)
    if len(backoff_values) < attempts - 1:
        raise EvaluationConfigurationError("fallback_backoff_seconds must cover every retry")
    stages = _mapping(root.get("stages"), "stages")
    if set(stages) != {"smoke_case_key", "maximum_full_corpus_candidates"}:
        raise EvaluationConfigurationError("stages contains unsupported keys")
    smoke = stages.get("smoke_case_key")
    if not isinstance(smoke, str) or not smoke.strip():
        raise EvaluationConfigurationError("stages.smoke_case_key must be non-empty")
    return ViabilityPolicy(
        key_status_endpoint=endpoint,
        minimum_interval_seconds=_number(pacing.get("minimum_interval_seconds"), "pacing.minimum_interval_seconds", minimum=10, maximum=120),
        maximum_jitter_seconds=_number(pacing.get("maximum_jitter_seconds"), "pacing.maximum_jitter_seconds", minimum=0, maximum=3),
        maximum_attempts=attempts,
        fallback_backoff_seconds=backoff_values,
        maximum_delay_seconds=_number(pacing.get("maximum_delay_seconds"), "pacing.maximum_delay_seconds", minimum=1, maximum=600),
        smoke_case_key=smoke.strip(),
        maximum_full_corpus_candidates=_integer(stages.get("maximum_full_corpus_candidates"), "stages.maximum_full_corpus_candidates", minimum=1, maximum=2),
    )


def _utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _header_delay(headers: Mapping[str, str], name: str, now: datetime) -> float | None:
    value = headers.get(name.lower())
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if name.lower() == "retry-after":
        try:
            return max(0.0, float(text))
        except ValueError:
            try:
                return max(0.0, (parsedate_to_datetime(text).astimezone(timezone.utc) - now.astimezone(timezone.utc)).total_seconds())
            except (TypeError, ValueError, OverflowError):
                return None
    try:
        numeric = float(text)
    except ValueError:
        return None
    if numeric > 1_000_000_000_000:
        target = numeric / 1000.0
    elif numeric > 1_000_000_000:
        target = numeric
    else:
        return max(0.0, numeric)
    return max(0.0, target - now.timestamp())


class AttemptPacer:
    def __init__(
        self,
        policy: ViabilityPolicy,
        *,
        sleeper: Callable[[float], None] = time.sleep,
        monotonic: Callable[[], float] = time.monotonic,
        now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        jitter: Callable[[float, float], float] = random.uniform,
    ) -> None:
        self.policy = policy
        self.sleeper = sleeper
        self.monotonic = monotonic
        self.now = now
        self.jitter = jitter
        self.last_started: float | None = None
        self.records: list[AttemptRecord] = []

    def _delay(self, attempt: int, previous: BaseException | None) -> tuple[float, str]:
        components: list[tuple[float, str]] = []
        current = self.monotonic()
        if self.last_started is not None:
            components.append((max(0.0, self.policy.minimum_interval_seconds - (current - self.last_started)), "minimum_interval"))
        if previous is not None:
            headers = getattr(previous, "headers", {})
            if isinstance(headers, Mapping):
                retry_after = _header_delay(headers, "retry-after", self.now())
                reset = _header_delay(headers, "x-ratelimit-reset", self.now())
                if retry_after is not None:
                    components.append((retry_after, "retry_after"))
                if reset is not None:
                    components.append((reset, "rate_limit_reset"))
            index = min(max(0, attempt - 2), len(self.policy.fallback_backoff_seconds) - 1)
            components.append((self.policy.fallback_backoff_seconds[index], "exponential_backoff"))
        if not components:
            return 0.0, "none"
        base, source = max(components, key=lambda item: item[0])
        jitter = self.jitter(0.0, self.policy.maximum_jitter_seconds) if base > 0 and self.policy.maximum_jitter_seconds else 0.0
        delay = min(self.policy.maximum_delay_seconds, base + jitter)
        return delay, source + ("+jitter" if jitter else "")

    def call(self, logical_id: str, operation: Callable[[], Any]) -> Any:
        previous: BaseException | None = None
        for attempt in range(1, self.policy.maximum_attempts + 1):
            delay, source = self._delay(attempt, previous)
            if delay > 0:
                self.sleeper(delay)
            started_at = self.now()
            self.last_started = self.monotonic()
            try:
                result = operation()
            except BaseException as exc:
                ended_at = self.now()
                code = str(getattr(exc, "code", None) or "evaluation_run_failure")
                self.records.append(AttemptRecord(
                    logical_id=logical_id,
                    attempt=attempt,
                    started_at=_utc(started_at),
                    ended_at=_utc(ended_at),
                    delay_before_seconds=round(delay, 6),
                    delay_source=source,
                    status="failed",
                    classification=code,
                    response_status=getattr(exc, "status", None),
                    provider_code=getattr(exc, "provider_code", None),
                ))
                retryable = isinstance(exc, (RateLimitedError, ProviderCapacityError, GenerationTimeoutError, TransportGenerationError))
                if not retryable or attempt >= self.policy.maximum_attempts:
                    raise
                previous = exc
                continue
            ended_at = self.now()
            self.records.append(AttemptRecord(
                logical_id=logical_id,
                attempt=attempt,
                started_at=_utc(started_at),
                ended_at=_utc(ended_at),
                delay_before_seconds=round(delay, 6),
                delay_source=source,
                status="success",
                classification="success",
                response_status=200,
                provider_code=None,
            ))
            return result
        raise RuntimeError("bounded attempt loop ended without a result")


def _runtime_config(root: Path, base_path: str, model: EvaluationModel, target: Path) -> GenerationConfig:
    raw = yaml.safe_load((root / base_path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("generation"), dict) or not isinstance(raw.get("api"), dict):
        raise EvaluationConfigurationError("base generation config is invalid")
    raw = json.loads(json.dumps(raw))
    raw["generation"]["model"] = model.model
    raw["generation"]["cross_model_fallback"] = False
    raw["api"]["retry_limit"] = 0
    raw["api"]["retry_backoff_seconds"] = 0
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    return load_generation_config(target)


def _provider_code(payload: Mapping[str, Any]) -> str | None:
    error = payload.get("error")
    metadata = error.get("metadata") if isinstance(error, Mapping) and isinstance(error.get("metadata"), Mapping) else {}
    value = metadata.get("provider_code")
    return str(value) if value is not None else None


def route_probe(config: GenerationConfig, api_key: str, *, transport: Transport | None = None) -> Mapping[str, Any]:
    schema = {
        "type": "object",
        "additionalProperties": False,
        "required": ["ok"],
        "properties": {"ok": {"const": True}},
    }
    body = canonical_json_bytes({
        "model": config.model,
        "messages": [{"role": "user", "content": "Return exactly one JSON object with ok set to true."}],
        "temperature": 0,
        "max_tokens": 16,
        "stream": False,
        "response_format": {"type": "json_schema", "json_schema": {"name": "crypto_pulse_route_probe", "strict": True, "schema": schema}},
        "provider": config.provider_policy.as_request(),
    })
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": config.app_referer,
        "X-OpenRouter-Title": config.app_title,
        "X-OpenRouter-Metadata": "enabled",
    }
    response = ClassifiedTransport(transport).post(config.endpoint, headers=headers, body=body, timeout_seconds=config.timeout_seconds)
    payload = _parse_json_bytes(response.body)
    if not isinstance(payload, Mapping):
        raise ProviderGenerationError("OpenRouter route probe response must be an object")
    actual_model = payload.get("model") if isinstance(payload.get("model"), str) else None
    if actual_model is None or not model_matches(config.model, actual_model):
        raise IneligibleRoutingError("OpenRouter route probe did not preserve the requested model")
    choices = payload.get("choices")
    if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], Mapping):
        raise ProviderGenerationError("OpenRouter route probe must return one choice")
    message = choices[0].get("message")
    content = message.get("content") if isinstance(message, Mapping) else None
    if not isinstance(content, str):
        raise ProviderGenerationError("OpenRouter route probe is missing message.content")
    try:
        decoded = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ProviderGenerationError("OpenRouter route probe did not return JSON") from exc
    if decoded != {"ok": True}:
        raise ProviderGenerationError("OpenRouter route probe did not satisfy its strict schema")
    metadata = payload.get("openrouter_metadata") if isinstance(payload.get("openrouter_metadata"), Mapping) else {}
    provider = _selected_provider(metadata)
    _check_selected_provider(config, provider)
    if provider is None:
        raise ProviderGenerationError("OpenRouter route probe did not identify the actual provider")
    return {
        "requested_model": config.model,
        "actual_model": actual_model,
        "actual_provider": provider,
        "generation_id": payload.get("id") if isinstance(payload.get("id"), str) else None,
        "provider_code": _provider_code(payload),
    }


def load_key_status(api_key: str, *, endpoint: str = "https://openrouter.ai/api/v1/key") -> Mapping[str, Any]:
    request = urllib.request.Request(endpoint, headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise EvaluationIntegrityError("OpenRouter key-status preflight failed") from exc
    data = payload.get("data") if isinstance(payload, Mapping) else None
    if not isinstance(data, Mapping):
        raise EvaluationIntegrityError("OpenRouter key-status response is missing data")
    allowed = ("limit", "limit_reset", "limit_remaining", "usage", "usage_daily", "usage_weekly", "usage_monthly", "is_free_tier")
    return {key: data.get(key) for key in allowed}


def _quota_summary(status: Mapping[str, Any], maximum_logical_calls: int) -> dict[str, Any]:
    limit = status.get("limit")
    remaining = status.get("limit_remaining")
    insufficient = isinstance(limit, (int, float)) and not isinstance(limit, bool) and isinstance(remaining, (int, float)) and not isinstance(remaining, bool) and remaining <= 0
    return {
        "is_free_tier": status.get("is_free_tier"),
        "limit": limit,
        "limit_reset": status.get("limit_reset"),
        "limit_remaining": remaining,
        "usage": status.get("usage"),
        "usage_daily": status.get("usage_daily"),
        "usage_weekly": status.get("usage_weekly"),
        "usage_monthly": status.get("usage_monthly"),
        "maximum_logical_calls": maximum_logical_calls,
        "request_budget_assessment": "insufficient" if insufficient else "appears_sufficient",
        "rate_limit_headroom_known": False,
    }


class _PacedClient:
    def __init__(self, base: Any, pacer: AttemptPacer, logical_id: str) -> None:
        self.base = base
        self.pacer = pacer
        self.logical_id = logical_id

    def generate(self, **kwargs: Any) -> Any:
        return self.pacer.call(self.logical_id, lambda: self.base.generate(**kwargs))


class PacedClientFactory:
    def __init__(self, pacer: AttemptPacer, builder: Callable[[GenerationConfig], Any] | None = None) -> None:
        self.pacer = pacer
        self.builder = builder or (lambda config: OpenRouterClient(config, transport=ClassifiedTransport()))
        self.logical_id = "unscoped"

    def set_logical_id(self, logical_id: str) -> None:
        self.logical_id = logical_id

    def __call__(self, config: GenerationConfig) -> _PacedClient:
        return _PacedClient(self.builder(config), self.pacer, self.logical_id)


def _prepared_cases(plan: Any, prepared_root: Path) -> tuple[PreparedCase, ...]:
    manifest = _read_json(prepared_root / PREPARED_MANIFEST)
    rows = manifest.get("cases")
    if not isinstance(rows, list):
        raise EvaluationIntegrityError("prepared manifest is missing cases")
    prepared = tuple(
        PreparedCase(str(row["key"]), str(row["snapshot_path"]), str(row["snapshot_sha256"]), str(row["quality_status"]), str(row["bundle_id"]), str(row["bundle_file"]), tuple(row.get("scenario_tags", [])), row.get("mutation"))
        for row in rows if isinstance(row, Mapping)
    )
    if tuple(item.key for item in prepared) != tuple(item.key for item in plan.cases):
        raise EvaluationIntegrityError("prepared corpus does not match source-controlled plan")
    for item in prepared:
        if _read_json(prepared_root / item.bundle_file).get("bundle_id") != item.bundle_id:
            raise EvaluationIntegrityError(f"prepared bundle ID mismatch for {item.key}")
    return prepared


def _stage(model: EvaluationModel, stage: str, status: str, *, failure_code: str | None = None, details: Mapping[str, Any] | None = None) -> dict[str, Any]:
    return {
        "model_key": model.key,
        "model": model.model,
        "stage": stage,
        "status": status,
        "failure_code": failure_code,
        "details": dict(details or {}),
    }


def execute_viability_evaluation(
    *,
    repository_root: str | Path,
    config_path: str | Path,
    viability_config_path: str | Path,
    prepared_dir: str | Path,
    output_dir: str | Path,
    api_key: str | None = None,
    trusted_main_sha: str | None = None,
    catalogue_loader: CatalogueLoader = _catalogue,
    key_status_loader: KeyStatusLoader = load_key_status,
    probe: ProbeCallable = route_probe,
    client_builder: Callable[[GenerationConfig], Any] | None = None,
    sleeper: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    jitter: Callable[[float, float], float] = random.uniform,
) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    prepared_root = Path(prepared_dir)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    plan = load_evaluation_plan(root, config_path)
    policy = load_viability_policy(root / viability_config_path)
    prepared = _prepared_cases(plan, prepared_root)
    smoke = next((item for item in prepared if item.key == policy.smoke_case_key), None)
    if smoke is None:
        raise EvaluationConfigurationError(f"smoke case {policy.smoke_case_key!r} is not in the prepared corpus")

    availability = check_model_availability(plan.models, catalogue_loader=catalogue_loader)
    _write_json(output / AVAILABILITY_FILE, {"models": [asdict(item) for item in availability]})
    if not api_key:
        raise EvaluationIntegrityError("OPENROUTER_API_KEY is required for controlled model evaluation")

    maximum_logical_calls = len(plan.models) * 2 + min(policy.maximum_full_corpus_candidates, len(plan.models)) * len(plan.cases) * plan.runs_per_case
    key_status = _quota_summary(key_status_loader(api_key), maximum_logical_calls)
    _write_json(output / KEY_STATUS_FILE, key_status)

    pacer = AttemptPacer(policy, sleeper=sleeper, monotonic=monotonic, now=now, jitter=jitter)
    factory = PacedClientFactory(pacer, client_builder)
    by_key: dict[str, ModelAvailability] = {item.key: item for item in availability}
    runtimes: dict[str, GenerationConfig] = {}
    stages: list[dict[str, Any]] = []
    finalists: list[EvaluationModel] = []
    records: list[RunRecord] = []

    if key_status["request_budget_assessment"] != "insufficient":
        for model in plan.models:
            current = by_key[model.key]
            if not current.eligible:
                stages.append(_stage(model, "route_preflight", "ineligible", failure_code="model_ineligible", details={"reason": current.reason}))
                continue
            runtime = _runtime_config(root, plan.base_generation_config, model, output / "runtime-configs" / f"{model.key}.yml")
            runtimes[model.key] = runtime
            logical_id = f"route-preflight/{model.key}"
            try:
                route = pacer.call(logical_id, lambda runtime=runtime: probe(runtime, api_key))
            except (GenerationError, ConfigurationError, OSError, ValueError, RuntimeError, TypeError) as exc:
                stages.append(_stage(model, "route_preflight", "failed", failure_code=str(getattr(exc, "code", None) or "route_preflight_failure")))
                continue
            stages.append(_stage(model, "route_preflight", "passed", details=route))

            factory.set_logical_id(f"contract-smoke/{model.key}/{smoke.key}")
            smoke_record = _run_one(
                root=root,
                model=model,
                config=runtime,
                prepared=smoke,
                prepared_dir=prepared_root,
                repeat=1,
                output_dir=output / "stages" / "smoke",
                api_key=api_key,
                client_factory=factory,
            )
            stages.append(_stage(model, "contract_smoke", "passed" if smoke_record.hard_pass else "failed", failure_code=smoke_record.failure_code, details={"validation": smoke_record.validation, "run_record": smoke_record.output_dir}))
            if smoke_record.hard_pass:
                finalists.append(model)

        finalists.sort(key=lambda model: (by_key[model.key].expiration_date or "9999-12-31", model.model))
        selected_finalists = finalists[: policy.maximum_full_corpus_candidates]
        selected_keys = {item.key for item in selected_finalists}
        for model in finalists:
            stages.append(_stage(model, "full_corpus_selection", "selected" if model.key in selected_keys else "not_selected", details={"rule": "earliest expiry risk, then model slug"}))

        for model in selected_finalists:
            runtime = runtimes[model.key]
            for case in prepared:
                for repeat in range(1, plan.runs_per_case + 1):
                    factory.set_logical_id(f"full-corpus/{model.key}/{case.key}/repeat-{repeat}")
                    records.append(_run_one(
                        root=root,
                        model=model,
                        config=runtime,
                        prepared=case,
                        prepared_dir=prepared_root,
                        repeat=repeat,
                        output_dir=output,
                        api_key=api_key,
                        client_factory=factory,
                    ))
    else:
        for model in plan.models:
            stages.append(_stage(model, "route_preflight", "not_run", failure_code="insufficient_quota"))

    summary = _aggregate(plan, availability, records)
    summary["trusted_main_sha"] = trusted_main_sha
    summary["completed_at"] = _utc(now())
    summary["viability"] = {
        "policy": asdict(policy),
        "key_status": key_status,
        "maximum_logical_calls": maximum_logical_calls,
        "completed_logical_calls": len({item.logical_id for item in pacer.records}),
        "http_attempts": len(pacer.records),
        "route_preflight_candidates": len(plan.models),
        "smoke_passes": sum(item["stage"] == "contract_smoke" and item["status"] == "passed" for item in stages),
        "full_corpus_finalists": [item.key for item in finalists[: policy.maximum_full_corpus_candidates]],
        "stages": stages,
    }
    _write_json(output / ATTEMPT_RECORDS_FILE, {"attempts": [asdict(item) for item in pacer.records]})
    _write_json(output / STAGE_RESULTS_FILE, {"stages": stages})
    _write_json(output / SUMMARY_JSON, summary)

    decision = _decision_text(summary, availability)
    decision += "\n\n## Viability funnel\n\n"
    decision += f"- Maximum logical calls: `{maximum_logical_calls}`\n"
    decision += f"- Completed logical calls: `{summary['viability']['completed_logical_calls']}`\n"
    decision += f"- HTTP attempts: `{summary['viability']['http_attempts']}`\n"
    decision += f"- Smoke-test passes: `{summary['viability']['smoke_passes']}`\n"
    decision += f"- Full-corpus finalists: `{', '.join(summary['viability']['full_corpus_finalists']) or 'none'}`\n"
    (output / DECISION_MARKDOWN).write_text(decision, encoding="utf-8")
    worksheet = ["model_key,case_key,repeat,manual_usefulness_0_to_5,manual_readability_0_to_5,reviewer_notes"] + [
        f"{model.key},{case.key},{repeat},,," for model in plan.models for case in plan.cases for repeat in range(1, plan.runs_per_case + 1)
    ]
    (output / REVIEWER_WORKSHEET).write_text("\n".join(worksheet) + "\n", encoding="utf-8")
    (output / ACTIONS_SUMMARY).write_text(decision + f"\n\n- Trusted main commit: `{trusted_main_sha or 'not-recorded'}`\n", encoding="utf-8")
    return summary
