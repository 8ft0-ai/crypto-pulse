"""Retained-artifact helpers for the offline bounded-selector proof."""
from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .candidate_selection_contract import validate_candidate_selection
from .candidate_selector import (
    BoundedCandidateSelectorResult,
    SelectorClientResponse,
)
from .claim_candidate_contract import derive_candidate_id, order_candidates
from .contracts import canonical_json_bytes, content_sha256
from .deterministic_ranking import DeterministicBaselineResult

CANDIDATE_SELECTION_PROOF_VERSION = "phase-06-candidate-selection-proof/v1"
DEFAULT_PROOF_DIR = "evaluation/phase-06/candidate-selection"
DEFAULT_SUMMARY = f"{DEFAULT_PROOF_DIR}/summary.json"
DEFAULT_SCENARIOS = f"{DEFAULT_PROOF_DIR}/scenarios.json"
DEFAULT_REQUEST = f"{DEFAULT_PROOF_DIR}/representative-request.json"
DEFAULT_PROVIDER_SCHEMA = f"{DEFAULT_PROOF_DIR}/provider-schema.json"
DEFAULT_REPAIR = f"{DEFAULT_PROOF_DIR}/representative-repair.json"
DEFAULT_PLAN = f"{DEFAULT_PROOF_DIR}/representative-plan.json"
DEFAULT_RENDER = f"{DEFAULT_PROOF_DIR}/representative-render.md"
DEFAULT_REPORT = f"{DEFAULT_PROOF_DIR}/review.md"


class CandidateSelectionProofError(ValueError):
    def __init__(self, code: str, path: str, message: str):
        super().__init__(f"{path}: {message}")
        self.code = code
        self.path = path
        self.message = message


@dataclass(frozen=True)
class CandidateSelectionProof:
    summary: dict[str, Any]
    scenarios: dict[str, Any]
    representative_request: dict[str, Any]
    provider_schema: dict[str, Any]
    representative_repair: dict[str, Any]
    representative_plan: dict[str, Any]
    representative_render: bytes
    report_markdown: bytes

    @property
    def outputs(self) -> Mapping[str, bytes]:
        return {
            DEFAULT_SUMMARY: canonical_json_bytes(self.summary) + b"\n",
            DEFAULT_SCENARIOS: canonical_json_bytes(self.scenarios) + b"\n",
            DEFAULT_REQUEST: canonical_json_bytes(self.representative_request) + b"\n",
            DEFAULT_PROVIDER_SCHEMA: canonical_json_bytes(self.provider_schema) + b"\n",
            DEFAULT_REPAIR: canonical_json_bytes(self.representative_repair) + b"\n",
            DEFAULT_PLAN: canonical_json_bytes(self.representative_plan) + b"\n",
            DEFAULT_RENDER: self.representative_render,
            DEFAULT_REPORT: self.report_markdown,
        }


def fail(code: str, path: str, message: str) -> None:
    raise CandidateSelectionProofError(code, path, message)


def scripted_response(payload: Any, *, scenario: str, attempt: int) -> SelectorClientResponse:
    return SelectorClientResponse(
        payload=payload,
        raw_response=canonical_json_bytes(payload).decode("utf-8"),
        metadata={
            "client": "scripted-offline",
            "scripted": True,
            "scenario": scenario,
            "generation_id": f"{scenario}-{attempt}",
        },
    )


def compact_record(
    case_key: str,
    scenario: str,
    result: BoundedCandidateSelectorResult,
    baseline: DeterministicBaselineResult,
) -> dict[str, Any]:
    record = result.record
    fallback_exact = (
        not record["fallback_used"]
        or (
            result.claim_plan_bytes == baseline.claim_plan_bytes
            and result.render.markdown == baseline.render.markdown
            and record["selected_candidate_ids"]
            == baseline.selection["selected_candidate_ids"]
        )
    )
    repair = record.get("repair")
    return {
        "case": case_key,
        "scenario": scenario,
        "request_id": record["request"]["request_id"],
        "candidate_set_id": record["request"]["candidate_set_id"],
        "request_sha256": record["request_sha256"],
        "provider_schema_sha256": record["provider_schema_sha256"],
        "attempts": record["attempts"],
        "repair_sha256": content_sha256(repair) if repair is not None else None,
        "selector_attempt_count": record["selector_attempt_count"],
        "semantic_repair_count": record["semantic_repair_count"],
        "outcome": record["outcome"],
        "fallback_used": record["fallback_used"],
        "fallback_reason": record["fallback_reason"],
        "fallback_exact": fallback_exact,
        "final_diagnostics": record["final_diagnostics"],
        "selected_candidate_ids": record["selected_candidate_ids"],
        "baseline_selected_candidate_ids": record["baseline_selected_candidate_ids"],
        "claim_plan_sha256": record["claim_plan_sha256"],
        "rendered_markdown_sha256": record["rendered_markdown_sha256"],
        "validation": record["validation"],
    }


def assert_outcome(
    result: BoundedCandidateSelectorResult,
    *,
    outcome: str,
    attempts: int,
    repairs: int,
    fallback: bool,
    path: str,
) -> None:
    actual = (
        result.record["outcome"],
        result.record["selector_attempt_count"],
        result.record["semantic_repair_count"],
        result.record["fallback_used"],
    )
    expected = (outcome, attempts, repairs, fallback)
    if actual != expected:
        fail("unexpected_scenario_outcome", path, f"expected {expected!r}, got {actual!r}")


def _redundancy_pair(candidates: Sequence[Mapping[str, Any]], config: Any) -> tuple[str, str]:
    groups: dict[str, list[Mapping[str, Any]]] = {}
    for candidate in order_candidates(candidates):
        features = candidate.get("features")
        section = candidate.get("section")
        intent = candidate.get("intent")
        if not isinstance(features, Mapping) or not isinstance(section, str) or not isinstance(intent, str):
            continue
        if config.section_limits.get(section, 0) < 2 or config.intent_limits.get(intent, 0) < 2:
            continue
        group = features.get("redundancy_group")
        if isinstance(group, str):
            groups.setdefault(group, []).append(candidate)
    for group in sorted(groups):
        if len(groups[group]) >= 2:
            return (
                str(groups[group][0]["candidate_id"]),
                str(groups[group][1]["candidate_id"]),
            )
    fail("missing_redundancy_pair", "$.candidates", "no real redundancy pair was available")


def validation_matrix(
    candidates: Sequence[Mapping[str, Any]],
    *,
    config: Any,
    bundle_id: str,
    selection_schema: Mapping[str, Any],
) -> list[dict[str, Any]]:
    ordered = list(order_candidates(candidates))
    first_id = str(ordered[0]["candidate_id"])
    unknown = "claim-candidate:sha256:" + "0" * 64
    mixed = copy.deepcopy(ordered[0])
    mixed["evidence_bundle_id"] = "sha256:" + "f" * 64
    mixed["candidate_id"] = ""
    mixed["candidate_id"] = derive_candidate_id(mixed)
    checks = [
        ("unknown", {"selected_candidate_ids": [unknown]}, ordered),
        ("duplicate", {"selected_candidate_ids": [first_id, first_id]}, ordered),
        (
            "excessive",
            {
                "selected_candidate_ids": [
                    str(item["candidate_id"])
                    for item in ordered[: config.max_total + 1]
                ]
            },
            ordered,
        ),
        (
            "redundancy",
            {"selected_candidate_ids": list(_redundancy_pair(ordered, config))},
            ordered,
        ),
        ("mixed_bundle", {"selected_candidate_ids": [mixed["candidate_id"]]}, [*ordered, mixed]),
    ]
    result: list[dict[str, Any]] = []
    for name, payload, candidate_set in checks:
        validation = validate_candidate_selection(
            payload,
            candidate_set,
            config=config,
            evidence_bundle_id=bundle_id,
            selection_schema=selection_schema,
        )
        if validation.is_valid:
            fail("validation_matrix_false_accept", f"$.validation_matrix.{name}", "invalid response accepted")
        result.append(
            {
                "name": name,
                "response": payload,
                "diagnostics": [item.as_dict() for item in validation.diagnostics],
            }
        )
    return result


def render_report(summary: Mapping[str, Any]) -> bytes:
    overall = summary["overall"]
    lines = [
        "# Phase 6 bounded candidate-ID selection proof",
        "",
        "> **Classification:** repository-owned offline control-flow evidence. No real model or provider call occurred.",
        "",
        f"- Selection schema: `{summary['selection_schema_path']}`",
        f"- Selection schema SHA-256: `{summary['selection_schema_sha256']}`",
        f"- Prompt: `{summary['prompt_path']}`",
        f"- Cases: `{overall['case_count']}`",
        f"- Scripted scenarios: `{overall['scenario_count']}`",
        f"- First-pass acceptances: `{overall['accepted_initial_count']}`",
        f"- Repaired acceptances: `{overall['accepted_after_repair_count']}`",
        f"- Deterministic fallbacks: `{overall['fallback_count']}`",
        f"- Exact fallback matches: `{overall['fallback_exact_count']} / {overall['fallback_count']}`",
        f"- Maximum semantic repairs: `{overall['maximum_semantic_repair_count']}`",
        f"- Real provider calls: `{overall['provider_call_count']}`",
        "",
        "## Scenario matrix",
        "",
        "| Case | Scenario | Outcome | Attempts | Repairs | Fallback exact |",
        "| --- | --- | --- | ---: | ---: | --- |",
    ]
    for item in summary["scenario_summary"]:
        lines.append(
            f"| `{item['case']}` | `{item['scenario']}` | `{item['outcome']}` | "
            f"{item['selector_attempt_count']} | {item['semantic_repair_count']} | "
            f"`{str(item['fallback_exact']).lower()}` |"
        )
    lines += ["", "## Validation matrix", "", "| Invalid selection | Stable diagnostics |", "| --- | --- |"]
    for item in summary["validation_matrix"]:
        codes = ", ".join(diag["code"] for diag in item["diagnostics"])
        lines.append(f"| `{item['name']}` | `{codes}` |")
    lines += [
        "",
        "## Proven boundaries",
        "",
        "- The canonical response object contains only `selected_candidate_ids`.",
        "- Model list order is ignored; accepted IDs are restored to canonical candidate order.",
        "- Only a structurally complete ID array is eligible for one semantic repair.",
        "- Malformed envelopes and client/provider-class failures fall back immediately.",
        "- A second invalid response falls back without a third attempt.",
        "- Fallback uses the exact Slice 4 selected IDs, claim plan and Markdown.",
        "- Candidate and evidence permutations preserve request and final-output bytes.",
        "- No model-quality, cost or latency comparison is made in Slice 5.",
        "",
    ]
    return "\n".join(lines).encode("utf-8")
