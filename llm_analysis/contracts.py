"""Versioned contract constants and deterministic identifier helpers.

This module deliberately does not call an LLM, validate model output, or render a
report. It provides the small shared vocabulary that later implementation slices
must consume without duplicating contract strings in workflow YAML or provider
code.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

EVIDENCE_SCHEMA_VERSION = "crypto-market-evidence-bundle/v1"
ANALYSIS_SCHEMA_VERSION = "crypto-market-analysis/v1"
PROVENANCE_SCHEMA_VERSION = "crypto-market-generation-provenance/v1"
PROMPT_VERSION = "crypto-market-analysis/v1"
CLAIM_PLAN_SCHEMA_VERSION = "crypto-market-claim-plan/v1"
CLAIM_PLAN_PROMPT_VERSION = "crypto-market-claim-plan/v1"

CLAIM_TYPES = (
    "absolute_observation",
    "directional_observation",
    "comparison",
    "data_quality_limitation",
    "source_disagreement",
    "qualitative_interpretation",
)

CLAIM_PLAN_INTENTS = (
    "absolute_observation",
    "directional_observation",
    "comparison",
    "source_status",
    "data_quality_limitation",
    "snapshot_status",
)

CLAIM_PLAN_SECTION_KINDS = (
    "market_summary",
    "key_observations",
    "risks_and_limitations",
    "data_quality",
    "source_status",
)

CLAIM_PLAN_COMPARISON_RELATIONS = (
    "none",
    "greater_than",
    "less_than",
    "approximately_equal",
    "not_equal",
    "opposite_direction",
)

CLAIM_PLAN_CONFIDENCE_LEVELS = ("high", "medium", "low")

EVIDENCE_TYPES = (
    "number",
    "string",
    "timestamp",
    "status",
    "boolean",
    "set",
)

# A stable identifier contains a namespace plus at least one additional segment.
# Segments are lower-case and may use dots, underscores, or hyphens as separators.
EVIDENCE_ID_PATTERN = r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)+$"
_EVIDENCE_ID_RE = re.compile(EVIDENCE_ID_PATTERN)


def evidence_id(*segments: str) -> str:
    """Build a deterministic evidence identifier from stable semantic segments.

    Callers must use stable source/entity keys, never array positions or display
    ordering. For example::

        evidence_id("market", "asset", "bitcoin", "change_24h_pct")

    produces ``market.asset.bitcoin.change_24h_pct``.
    """

    normalised = [segment.strip().lower() for segment in segments]
    if len(normalised) < 2 or any(not segment for segment in normalised):
        raise ValueError("evidence IDs require at least two non-empty segments")

    value = ".".join(normalised)
    if not _EVIDENCE_ID_RE.fullmatch(value):
        raise ValueError(f"invalid evidence ID: {value!r}")
    return value


def canonical_json_bytes(value: Any) -> bytes:
    """Return the canonical JSON encoding used for contract hashes.

    UTF-8, sorted keys, compact separators, and no NaN/Infinity values make the
    result stable for semantically identical JSON objects.
    """

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def content_sha256(value: Any) -> str:
    """Return a lower-case SHA-256 hex digest for canonical JSON content."""

    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()
