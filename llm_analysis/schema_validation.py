"""Small offline JSON Schema Draft 2020-12 subset used by Phase 5 contracts.

The repository schemas deliberately use a compact subset of the draft. Keeping the
validator here avoids a runtime network dependency and still validates from the
reviewer-visible schema documents rather than duplicating their object shapes in
business logic.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from .contracts import canonical_json_bytes
from .diagnostics import Diagnostic


def _resolve_ref(root: dict[str, Any], ref: str) -> dict[str, Any]:
    if not ref.startswith("#/"):
        raise ValueError(f"only local JSON Schema references are supported: {ref}")
    value: Any = root
    for raw in ref[2:].split("/"):
        key = raw.replace("~1", "/").replace("~0", "~")
        value = value[key]
    if not isinstance(value, dict):
        raise ValueError(f"schema reference does not resolve to an object: {ref}")
    return value


def _is_type(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    return False


def _valid_datetime(value: str) -> bool:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None


def validate_schema(instance: Any, schema: dict[str, Any], *, root: dict[str, Any] | None = None, path: str = "$") -> list[Diagnostic]:
    root = root or schema
    errors: list[Diagnostic] = []

    if "$ref" in schema:
        return validate_schema(instance, _resolve_ref(root, schema["$ref"]), root=root, path=path)

    if "allOf" in schema:
        for child in schema["allOf"]:
            errors.extend(validate_schema(instance, child, root=root, path=path))

    if "oneOf" in schema:
        matches = [validate_schema(instance, child, root=root, path=path) for child in schema["oneOf"]]
        if sum(not result for result in matches) != 1:
            errors.append(Diagnostic("schema", "one_of", path, "value must match exactly one permitted schema"))

    condition = schema.get("if")
    if isinstance(condition, dict):
        branch = schema.get("then") if not validate_schema(instance, condition, root=root, path=path) else schema.get("else")
        if isinstance(branch, dict):
            errors.extend(validate_schema(instance, branch, root=root, path=path))

    expected = schema.get("type")
    if expected is not None:
        choices = expected if isinstance(expected, list) else [expected]
        if not any(_is_type(instance, item) for item in choices):
            errors.append(Diagnostic("schema", "type", path, f"expected type {' or '.join(choices)}"))
            return errors

    if "const" in schema and instance != schema["const"]:
        errors.append(Diagnostic("schema", "const", path, f"value must equal {schema['const']!r}"))
    if "enum" in schema and instance not in schema["enum"]:
        errors.append(Diagnostic("schema", "enum", path, "value is not in the permitted enumeration"))

    if isinstance(instance, str):
        if len(instance) < schema.get("minLength", 0):
            errors.append(Diagnostic("schema", "min_length", path, "string is shorter than permitted"))
        if "maxLength" in schema and len(instance) > schema["maxLength"]:
            errors.append(Diagnostic("schema", "max_length", path, "string is longer than permitted"))
        pattern = schema.get("pattern")
        if pattern and not re.search(pattern, instance):
            errors.append(Diagnostic("schema", "pattern", path, "string does not match the required pattern"))
        if schema.get("format") == "date-time" and not _valid_datetime(instance):
            errors.append(Diagnostic("schema", "format", path, "string is not an RFC 3339 date-time with timezone"))

    if isinstance(instance, list):
        if len(instance) < schema.get("minItems", 0):
            errors.append(Diagnostic("schema", "min_items", path, "array has too few items"))
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            errors.append(Diagnostic("schema", "max_items", path, "array has too many items"))
        if schema.get("uniqueItems"):
            encoded = [canonical_json_bytes(item) for item in instance]
            if len(encoded) != len(set(encoded)):
                errors.append(Diagnostic("schema", "unique_items", path, "array items must be unique"))
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(instance):
                errors.extend(validate_schema(item, item_schema, root=root, path=f"{path}[{index}]"))

    if isinstance(instance, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in instance:
                errors.append(Diagnostic("schema", "required", f"{path}.{key}", "required property is missing"))
        properties = schema.get("properties", {})
        for key, value in instance.items():
            if key in properties:
                errors.extend(validate_schema(value, properties[key], root=root, path=f"{path}.{key}"))
            elif schema.get("additionalProperties") is False:
                errors.append(Diagnostic("schema", "additional_property", f"{path}.{key}", "property is not permitted by the schema"))

    return errors
