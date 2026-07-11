"""Stable diagnostics for the offline governed-analysis pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

_STAGE_ORDER = {"schema": 0, "referential": 1, "value": 2, "semantic": 3, "policy": 4}


@dataclass(frozen=True)
class Diagnostic:
    stage: str
    code: str
    path: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {"stage": self.stage, "code": self.code, "path": self.path, "message": self.message}


@dataclass(frozen=True)
class ValidationReport:
    diagnostics: tuple[Diagnostic, ...]

    @property
    def is_valid(self) -> bool:
        return not self.diagnostics

    def for_stage(self, stage: str) -> tuple[Diagnostic, ...]:
        return tuple(item for item in self.diagnostics if item.stage == stage)

    def as_dict(self) -> dict[str, object]:
        return {"valid": self.is_valid, "diagnostics": [item.as_dict() for item in self.diagnostics]}


def stable_report(diagnostics: Iterable[Diagnostic]) -> ValidationReport:
    unique = set(diagnostics)
    ordered = sorted(unique, key=lambda item: (_STAGE_ORDER.get(item.stage, 99), item.path, item.code, item.message))
    return ValidationReport(tuple(ordered))
