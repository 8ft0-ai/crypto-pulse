"""Canonical request and response contract for bounded candidate-ID selection."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .claim_candidate_contract import index_candidates_by_id, order_candidates
from .contracts import canonical_json_bytes, content_sha256
from .deterministic_ranking import DeterministicRankingError, RankingConfig
from .deterministic_reconstruction import reconstruct_claim_plan
from .schema_validation import validate_schema

CANDIDATE_SELECTION_SCHEMA_VERSION = "crypto-market-candidate-selection/v1"
CANDIDATE_SELECTOR_REQUEST_VERSION = "phase-06-candidate-selector-request/v1"
CANDIDATE_SELECTOR_REPAIR_VERSION = "phase-06-candidate-selector-repair/v1"
DEFAULT_SELECTION_SCHEMA = "schemas/crypto-market-candidate-selection-v1.json"
DEFAULT_SELECTION_PROMPT = "prompts/crypto-market-candidate-selection-v1.txt"

_ID_RE = re.compile(r"^claim-candidate:sha256:[0-9a-f]{64}$")
_FEATURES = (
    "materiality_bucket",
    "cross_source",
    "conflict_status",
    "recency_bucket",
    "quality_significance",
    "redundancy_group",
    "corroboration_count",
)


class CandidateSelectionError(ValueError):
    def __init__(self, code: str, path: str, message: str):
        super().__init__(f"{path}: {message}")
        self.code = code
        self.path = path
        self.message = message


class SelectorEnvelopeError(CandidateSelectionError):
    """The response is not the single supported JSON envelope."""


@dataclass(frozen=True)
class CandidateSelectionDiagnostic:
    code: str
    path: str
    candidate_id: str | None = None
    limit: int | None = None
    redundancy_group: str | None = None

    def as_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {"code": self.code, "path": self.path}
        for key in ("candidate_id", "limit", "redundancy_group"):
            value = getattr(self, key)
            if value is not None:
                result[key] = value
        return result


@dataclass(frozen=True)
class CandidateSelectionValidation:
    selected_candidate_ids: tuple[str, ...]
    diagnostics: tuple[CandidateSelectionDiagnostic, ...]

    @property
    def is_valid(self) -> bool:
        return not self.diagnostics

    def as_dict(self) -> dict[str, Any]:
        return {
            "valid": self.is_valid,
            "selected_candidate_ids": list(self.selected_candidate_ids),
            "diagnostics": [item.as_dict() for item in self.diagnostics],
        }


def _fail(code: str, path: str, message: str) -> None:
    raise CandidateSelectionError(code, path, message)


def _catalogue_row(candidate: Mapping[str, Any]) -> dict[str, Any]:
    features = candidate.get("features")
    if not isinstance(features, Mapping):
        _fail("invalid_candidate_features", "$.candidates", "candidate features must be an object")
    missing = [key for key in _FEATURES if key not in features]
    if missing:
        _fail("missing_candidate_feature", "$.candidates.features", ", ".join(missing))
    return {
        "candidate_id": candidate["candidate_id"],
        "intent": candidate["intent"],
        "evidence_ids": list(candidate["evidence_ids"]),
        "comparison_relation": candidate["comparison_relation"],
        "section": candidate["section"],
        "subject": dict(candidate["subject"]),
        "metric": candidate["metric"],
        "confidence": candidate["confidence"],
        "features": {key: features[key] for key in _FEATURES},
    }


def build_candidate_selector_request(
    candidates: Sequence[Mapping[str, Any]],
    *,
    config: RankingConfig,
    evidence_bundle_id: str,
) -> dict[str, Any]:
    if not isinstance(evidence_bundle_id, str) or not evidence_bundle_id.startswith("sha256:"):
        _fail("invalid_bundle_id", "$.evidence_bundle_id", "must be a canonical bundle ID")
    ordered = [dict(item) for item in order_candidates(candidates)]
    if not ordered:
        _fail("empty_candidate_set", "$.candidates", "candidate set must not be empty")
    try:
        indexed = index_candidates_by_id(ordered)
    except ValueError as exc:
        _fail("invalid_candidate_identity", "$.candidates", str(exc))
    if len(indexed) != len(ordered):
        _fail("candidate_index_mismatch", "$.candidates", "candidate index is incomplete")
    for index, candidate in enumerate(ordered):
        if candidate.get("evidence_bundle_id") != evidence_bundle_id:
            _fail(
                "candidate_bundle_mismatch",
                f"$.candidates[{index}].evidence_bundle_id",
                "candidate does not reference the selector bundle",
            )
    request = {
        "request_version": CANDIDATE_SELECTOR_REQUEST_VERSION,
        "evidence_bundle_id": evidence_bundle_id,
        "candidate_set_id": "sha256:" + content_sha256(ordered),
        "ranking_version": config.ranking_version,
        "ranking_config_sha256": content_sha256(config.as_dict()),
        "max_selection_count": config.max_total,
        "section_limits": dict(config.section_limits),
        "intent_limits": dict(config.intent_limits),
        "response_schema_version": CANDIDATE_SELECTION_SCHEMA_VERSION,
        "candidates": [_catalogue_row(candidate) for candidate in ordered],
    }
    return {**request, "request_id": "sha256:" + content_sha256(request)}


def render_candidate_selector_prompt(
    template: str,
    request: Mapping[str, Any],
    repair: Mapping[str, Any] | None = None,
) -> str:
    request_marker = "{{CANDIDATE_SELECTOR_REQUEST_JSON}}"
    repair_marker = "{{CANDIDATE_SELECTOR_REPAIR_JSON}}"
    if template.count(request_marker) != 1 or template.count(repair_marker) != 1:
        _fail("invalid_prompt_template", "$.prompt", "selector markers must each appear once")
    repair_json = "null" if repair is None else canonical_json_bytes(repair).decode("utf-8")
    return template.replace(
        request_marker, canonical_json_bytes(request).decode("utf-8")
    ).replace(repair_marker, repair_json)


def build_candidate_selector_repair(
    request: Mapping[str, Any],
    *,
    previous_raw_response_sha256: str,
    previous_response: Mapping[str, Any],
    diagnostics: Sequence[CandidateSelectionDiagnostic],
) -> dict[str, Any]:
    return {
        "repair_version": CANDIDATE_SELECTOR_REPAIR_VERSION,
        "request_id": request["request_id"],
        "previous_raw_response_sha256": previous_raw_response_sha256,
        "previous_response": dict(previous_response),
        "diagnostics": [item.as_dict() for item in diagnostics],
        "response_schema_version": CANDIDATE_SELECTION_SCHEMA_VERSION,
    }


def validate_candidate_selection(
    response: Any,
    candidates: Sequence[Mapping[str, Any]],
    *,
    config: RankingConfig,
    evidence_bundle_id: str,
    selection_schema: Mapping[str, Any],
) -> CandidateSelectionValidation:
    if not isinstance(response, Mapping):
        raise SelectorEnvelopeError("selection_response_not_object", "$", "must be one object")
    if set(response) != {"selected_candidate_ids"}:
        raise SelectorEnvelopeError(
            "selection_response_shape", "$", "must contain only selected_candidate_ids"
        )
    identifiers = response.get("selected_candidate_ids")
    if not isinstance(identifiers, list):
        raise SelectorEnvelopeError(
            "selection_ids_not_array", "$.selected_candidate_ids", "must be an array"
        )

    selected: list[str] = []
    diagnostics: list[CandidateSelectionDiagnostic] = []
    if not identifiers:
        diagnostics.append(CandidateSelectionDiagnostic("empty_selection", "$.selected_candidate_ids"))
    if len(identifiers) > config.max_total:
        diagnostics.append(
            CandidateSelectionDiagnostic(
                "excessive_selection", "$.selected_candidate_ids", limit=config.max_total
            )
        )
    seen: set[str] = set()
    for index, value in enumerate(identifiers):
        path = f"$.selected_candidate_ids[{index}]"
        if not isinstance(value, str) or not _ID_RE.fullmatch(value):
            diagnostics.append(CandidateSelectionDiagnostic("invalid_candidate_id", path))
            continue
        selected.append(value)
        if value in seen:
            diagnostics.append(
                CandidateSelectionDiagnostic("duplicate_selection", path, candidate_id=value)
            )
        seen.add(value)

    try:
        indexed = index_candidates_by_id(candidates)
    except ValueError as exc:
        _fail("invalid_candidate_identity", "$.candidates", str(exc))
    for index, identifier in enumerate(selected):
        if identifier not in indexed:
            diagnostics.append(
                CandidateSelectionDiagnostic(
                    "unknown_selected_candidate_id",
                    f"$.selected_candidate_ids[{index}]",
                    candidate_id=identifier,
                )
            )

    if not diagnostics:
        try:
            reconstruct_claim_plan(
                {
                    "evidence_bundle_id": evidence_bundle_id,
                    "selected_candidate_ids": selected,
                },
                candidates,
                config=config,
            )
        except DeterministicRankingError as exc:
            group = None
            marker = "redundancy group selected more than once: "
            if exc.code == "selection_redundancy_violation" and marker in str(exc):
                group = str(exc).rsplit(marker, 1)[-1]
            diagnostics.append(
                CandidateSelectionDiagnostic(exc.code, exc.path, redundancy_group=group)
            )

    schema_diagnostics = validate_schema(dict(response), dict(selection_schema), path="$")
    if schema_diagnostics and not diagnostics:
        diagnostics.append(
            CandidateSelectionDiagnostic("selection_schema_invalid", schema_diagnostics[0].path)
        )
    if diagnostics:
        canonical = tuple(selected)
    else:
        selected_set = set(selected)
        canonical = tuple(
            str(candidate["candidate_id"])
            for candidate in order_candidates(candidates)
            if candidate.get("candidate_id") in selected_set
        )
    return CandidateSelectionValidation(canonical, tuple(diagnostics))
