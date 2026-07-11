"""Project the canonical analysis schema into OpenAI's strict-output subset.

The canonical repository schema remains authoritative for offline validation. This
module produces a provider-only constrained-decoding schema and removes only the
null placeholders required to represent canonical optional object properties.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from typing import Any, Mapping

from .generation_config import GenerationConfig
from .openrouter_client import GenerationResult, OpenRouterClient, Transport


_UNSUPPORTED_PROVIDER_KEYWORDS = frozenset(
    {
        "allOf",
        "not",
        "dependentRequired",
        "dependentSchemas",
        "if",
        "then",
        "else",
        "uniqueItems",
    }
)
_DOCUMENT_METADATA_KEYWORDS = frozenset({"$schema", "$id"})


def _nullable(schema: Mapping[str, Any]) -> dict[str, Any]:
    """Represent a canonically optional property as a required nullable union."""

    projected = deepcopy(dict(schema))
    if "anyOf" in projected and isinstance(projected["anyOf"], list):
        branches = list(projected["anyOf"])
        if not any(isinstance(item, Mapping) and item.get("type") == "null" for item in branches):
            branches.append({"type": "null"})
        projected["anyOf"] = branches
        return projected
    return {"anyOf": [projected, {"type": "null"}]}


def project_openai_strict_schema(schema: Mapping[str, Any]) -> dict[str, Any]:
    """Return a deterministic OpenAI-compatible projection of a canonical schema.

    The projection deliberately removes constraints that OpenAI cannot enforce.
    Those constraints remain in the unchanged canonical schema and are applied by
    the repository's offline validators after generation.
    """

    def project(value: Any) -> Any:
        if isinstance(value, list):
            return [project(item) for item in value]
        if not isinstance(value, Mapping):
            return deepcopy(value)

        result: dict[str, Any] = {}
        properties = value.get("properties")
        original_required = {
            str(item)
            for item in value.get("required", [])
            if isinstance(item, str)
        }

        for key, item in value.items():
            if key in _DOCUMENT_METADATA_KEYWORDS or key in _UNSUPPORTED_PROVIDER_KEYWORDS:
                continue
            if key == "const":
                result["enum"] = [deepcopy(item)]
                continue
            if key in {"properties", "required", "additionalProperties"} and isinstance(properties, Mapping):
                continue
            result[key] = project(item)

        if isinstance(properties, Mapping):
            projected_properties: dict[str, Any] = {}
            for name, property_schema in properties.items():
                if not isinstance(name, str) or not isinstance(property_schema, Mapping):
                    raise TypeError("schema properties must map string names to objects")
                projected_property = project(property_schema)
                if name not in original_required:
                    projected_property = _nullable(projected_property)
                projected_properties[name] = projected_property
            result["properties"] = projected_properties
            result["required"] = list(projected_properties)
            result["additionalProperties"] = False
        elif value.get("type") == "object":
            result["additionalProperties"] = False

        return result

    projected = project(schema)
    if not isinstance(projected, dict):
        raise TypeError("analysis schema projection must produce an object")
    if projected.get("type") != "object":
        raise ValueError("OpenAI strict-output root schema must be an object")
    return projected


def remove_null_object_properties(value: Any) -> Any:
    """Remove only null-valued object properties from a provider response."""

    if isinstance(value, list):
        return [remove_null_object_properties(item) for item in value]
    if isinstance(value, Mapping):
        return {
            str(key): remove_null_object_properties(item)
            for key, item in value.items()
            if item is not None
        }
    return value


class OpenAICompatibleSchemaClient:
    """OpenRouter client adapter for the public-data OpenAI strict-output path."""

    def __init__(
        self,
        config: GenerationConfig,
        *,
        transport: Transport | None = None,
    ) -> None:
        self._delegate = OpenRouterClient(config, transport=transport)

    def generate(
        self,
        *,
        evidence_bundle: Mapping[str, Any],
        prompt_template: str,
        analysis_schema: Mapping[str, Any],
        api_key: str | None = None,
        environment: Mapping[str, str] | None = None,
    ) -> GenerationResult:
        projected = project_openai_strict_schema(analysis_schema)
        result = self._delegate.generate(
            evidence_bundle=evidence_bundle,
            prompt_template=prompt_template,
            analysis_schema=projected,
            api_key=api_key,
            environment=environment,
        )
        normalised = remove_null_object_properties(result.analysis)
        if not isinstance(normalised, dict):
            raise TypeError("normalised provider analysis must remain an object")
        return replace(result, analysis=normalised)
