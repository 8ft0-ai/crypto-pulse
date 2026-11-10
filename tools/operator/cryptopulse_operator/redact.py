"""Defensive secret detection for paste-safe operator evidence."""

from __future__ import annotations

import re
from typing import Any


class RedactionError(ValueError):
    pass


_PATTERNS = (
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |)PRIVATE KEY-----"),
    re.compile(r"(?i)\b(?:token|secret|password|api[_-]?key)\s*[:=]\s*[^\s,;]+"),
)


def contains_sensitive_text(value: str) -> bool:
    return any(pattern.search(value) for pattern in _PATTERNS)


def assert_safe(value: Any, *, path: str = "$") -> None:
    if isinstance(value, str):
        if contains_sensitive_text(value):
            raise RedactionError(f"sensitive-looking value rejected at {path}")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            assert_safe(item, path=f"{path}.{key}")
        return
    if isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            assert_safe(item, path=f"{path}[{index}]")
