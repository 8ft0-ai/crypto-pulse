"""Typed evidence envelope and deterministic status/exit semantics."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
from typing import Any, Mapping

from . import EVIDENCE_CONTRACT
from .redact import assert_safe


class Status(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    INCOMPLETE = "INCOMPLETE"
    ERROR = "ERROR"


EXIT_CODE = {
    Status.PASS: 0,
    Status.FAIL: 2,
    Status.INCOMPLETE: 3,
    Status.ERROR: 4,
}


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_hex(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


@dataclass(frozen=True)
class Evidence:
    command: str
    repository: str
    invocation_target: Mapping[str, Any]
    runtime: Mapping[str, Any]
    remote: Mapping[str, Any]
    local: Mapping[str, Any]
    status: Status
    completeness: Mapping[str, Any]
    assertions: tuple[Mapping[str, Any], ...] = ()
    findings: tuple[Mapping[str, Any], ...] = ()
    redaction_summary: Mapping[str, Any] | None = None

    def payload_without_hash(self) -> dict[str, Any]:
        payload = {
            "contract": EVIDENCE_CONTRACT,
            "command": self.command,
            "repository": self.repository,
            "invocation_target": dict(self.invocation_target),
            "runtime": dict(self.runtime),
            "remote": dict(self.remote),
            "local": dict(self.local),
            "status": self.status.value,
            "completeness": dict(self.completeness),
            "assertions": [dict(item) for item in self.assertions],
            "findings": [dict(item) for item in self.findings],
            "redaction_summary": dict(self.redaction_summary or {"rejected_fields": 0}),
        }
        assert_safe(payload)
        return payload

    def payload(self) -> dict[str, Any]:
        payload = self.payload_without_hash()
        payload["evidence_sha256"] = sha256_hex(canonical_json_bytes(payload))
        return payload

    def json_text(self) -> str:
        return canonical_json_bytes(self.payload()).decode("utf-8")

    def envelope(self) -> str:
        return f"{EVIDENCE_CONTRACT}\n{self.json_text()}\n"
