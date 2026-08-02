"""Deterministic ranking, bounded selection and claim-plan reconstruction."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

import yaml

from .claim_candidate_contract import candidate_sort_key, index_candidates_by_id, order_candidates
from .claim_plan_render import ClaimPlanRender, render_claim_plan
from .claim_plan_validation import validate_claim_plan
from .contracts import (
    CLAIM_PLAN_INTENTS,
    CLAIM_PLAN_PROMPT_VERSION,
    CLAIM_PLAN_SCHEMA_VERSION,
    CLAIM_PLAN_SECTION_KINDS,
    canonical_json_bytes,
    content_sha256,
)
from .diagnostics import ValidationReport
from .schema_validation import validate_schema

DETERMINISTIC_RANKING_VERSION = "phase-06-deterministic-ranking/v1"
DEFAULT_RANKING_CONFIG = "config/claim-candidate-ranking-v1.yml"

_FEATURE_KEYS = (
    "conflict_status",
    "quality_significance",
    "materiality_bucket",
    "intent",
    "cross_source",
    "corroboration_count",
    "recency_bucket",
)
_SIGNAL_NAMES = ("divergent_conflict", "material_quality")


class DeterministicRankingError(ValueError):
    """The deterministic baseline cannot safely rank, select or reconstruct."""

    def __init__(self, code: str, path: str, message: str):
        super().__init__(f"{path}: {message}")
        self.code = code
        self.path = path
        self.message = message


@dataclass(frozen=True)
class RankingConfig:
    ranking_version: str
    max_total: int
    max_per_section: int
    section_order: tuple[str, ...]
    required_sections_if_available: tuple[str, ...]
    section_limits: Mapping[str, int]
    intent_limits: Mapping[str, int]
    priorities: Mapping[str, tuple[Any, ...]]

    def as_dict(self) -> dict[str, Any]:
        return {
            "ranking_version": self.ranking_version,
            "max_total": self.max_total,
            "max_per_section": self.max_per_section,
            "section_order": list(self.section_order),
            "required_sections_if_available": list(self.required_sections_if_available),
            "section_limits": dict(self.section_limits),
            "intent_limits": dict(self.intent_limits),
            "priorities": {
                key: list(value) for key, value in self.priorities.items()
            },
        }


@dataclass(frozen=True)
class DeterministicBaselineResult:
    selection: dict[str, Any]
    claim_plan: dict[str, Any]
    validation: ValidationReport
    render: ClaimPlanRender

    @property
    def selection_bytes(self) -> bytes:
        return canonical_json_bytes(self.selection)

    @property
    def claim_plan_bytes(self) -> bytes:
        return canonical_json_bytes(self.claim_plan)


def _fail(code: str, path: str, message: str) -> None:
    raise DeterministicRankingError(code, path, message)


def _mapping(value: Any, path: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _fail("invalid_mapping", path, "must be an object")
    return value


def _list(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        _fail("invalid_list", path, "must be a list")
    return value


def _string(value: Any, path: str) -> str:
    if not isinstance(value, str) or not value.strip():
        _fail("invalid_string", path, "must be a non-empty string")
    return value.strip()


def _integer(value: Any, path: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        _fail("invalid_integer", path, f"must be an integer >= {minimum}")
    return value


def _relative(value: Any, path: str) -> str:
    text = _string(value, path)
    candidate = PurePosixPath(text)
    if candidate.is_absolute() or ".." in candidate.parts:
        _fail("invalid_path", path, "must be repository-relative without '..'")
    return candidate.as_posix()


def _priority(
    raw: Mapping[str, Any],
    key: str,
    expected_values: Sequence[Any],
    path: str,
) -> tuple[Any, ...]:
    values = tuple(_list(raw.get(key), f"{path}.{key}"))
    if len(values) != len(expected_values) or set(values) != set(expected_values):
        _fail(
            "invalid_priority",
            f"{path}.{key}",
            f"must contain each supported value exactly once: {list(expected_values)!r}",
        )
    return values


def load_ranking_config(
    repository_root: str | Path,
    config_path: str | Path = DEFAULT_RANKING_CONFIG,
) -> RankingConfig:
    root = Path(repository_root).resolve()
    relative = _relative(str(config_path), "config_path")
    path = root / relative
    if not path.is_file():
        _fail("missing_config", relative, "ranking configuration does not exist")
    raw = _mapping(yaml.safe_load(path.read_text(encoding="utf-8")), relative)
    expected = {
        "version",
        "ranking_version",
        "max_total",
        "max_per_section",
        "section_order",
        "required_sections_if_available",
        "section_limits",
        "intent_limits",
        "priorities",
    }
    if set(raw) != expected or raw.get("version") != 1:
        _fail("invalid_config", relative, "must use version 1 and exact supported keys")
    ranking_version = _string(raw["ranking_version"], f"{relative}.ranking_version")
    if ranking_version != DETERMINISTIC_RANKING_VERSION:
        _fail("unsupported_version", f"{relative}.ranking_version", "ranking version is unsupported")
    max_total = _integer(raw["max_total"], f"{relative}.max_total", 1)
    max_per_section = _integer(raw["max_per_section"], f"{relative}.max_per_section", 1)
    if max_total > 40 or max_per_section > 8:
        _fail("unsafe_bound", relative, "max_total must be <= 40 and max_per_section <= 8")

    section_order = tuple(
        _string(item, f"{relative}.section_order")
        for item in _list(raw["section_order"], f"{relative}.section_order")
    )
    if section_order != CLAIM_PLAN_SECTION_KINDS:
        _fail("invalid_section_order", f"{relative}.section_order", "must use canonical claim-plan section order")
    required_sections = tuple(
        _string(item, f"{relative}.required_sections_if_available")
        for item in _list(
            raw["required_sections_if_available"],
            f"{relative}.required_sections_if_available",
        )
    )
    if (
        not required_sections
        or len(required_sections) != len(set(required_sections))
        or any(item not in section_order for item in required_sections)
    ):
        _fail(
            "invalid_required_sections",
            f"{relative}.required_sections_if_available",
            "must contain unique canonical sections",
        )

    raw_sections = _mapping(raw["section_limits"], f"{relative}.section_limits")
    if set(raw_sections) != set(section_order):
        _fail("invalid_section_limits", f"{relative}.section_limits", "must define every canonical section")
    section_limits = {
        section: _integer(raw_sections[section], f"{relative}.section_limits.{section}", 0)
        for section in section_order
    }
    if any(value > max_per_section for value in section_limits.values()):
        _fail("unsafe_section_limit", f"{relative}.section_limits", "section limit exceeds max_per_section")
    if sum(section_limits.values()) < max_total:
        _fail("impossible_total_bound", relative, "section limits cannot accommodate max_total")

    raw_intents = _mapping(raw["intent_limits"], f"{relative}.intent_limits")
    if set(raw_intents) != set(CLAIM_PLAN_INTENTS):
        _fail("invalid_intent_limits", f"{relative}.intent_limits", "must define every claim-plan intent")
    intent_limits = {
        intent: _integer(raw_intents[intent], f"{relative}.intent_limits.{intent}", 0)
        for intent in CLAIM_PLAN_INTENTS
    }
    if sum(intent_limits.values()) < max_total:
        _fail("impossible_intent_bound", relative, "intent limits cannot accommodate max_total")

    priorities_raw = _mapping(raw["priorities"], f"{relative}.priorities")
    if set(priorities_raw) != set(_FEATURE_KEYS) - {"corroboration_count"}:
        _fail("invalid_priorities", f"{relative}.priorities", "uses unsupported or missing priority keys")
    priorities = {
        "conflict_status": _priority(
            priorities_raw,
            "conflict_status",
            ("divergent", "corroborated", "none"),
            f"{relative}.priorities",
        ),
        "quality_significance": _priority(
            priorities_raw,
            "quality_significance",
            ("material", "minor", "not_applicable"),
            f"{relative}.priorities",
        ),
        "materiality_bucket": _priority(
            priorities_raw,
            "materiality_bucket",
            ("high", "medium", "low", "not_applicable"),
            f"{relative}.priorities",
        ),
        "intent": _priority(
            priorities_raw,
            "intent",
            CLAIM_PLAN_INTENTS,
            f"{relative}.priorities",
        ),
        "cross_source": _priority(
            priorities_raw,
            "cross_source",
            (True, False),
            f"{relative}.priorities",
        ),
        "recency_bucket": _priority(
            priorities_raw,
            "recency_bucket",
            ("current", "recent", "unknown", "stale"),
            f"{relative}.priorities",
        ),
    }
    return RankingConfig(
        ranking_version,
        max_total,
        max_per_section,
        section_order,
        required_sections,
        section_limits,
        intent_limits,
        priorities,
    )


def _priority_value(config: RankingConfig, key: str, value: Any, path: str) -> int:
    ordered = config.priorities[key]
    try:
        index = ordered.index(value)
    except ValueError:
        _fail("unknown_feature_value", path, f"unsupported {key}: {value!r}")
    return len(ordered) - index - 1


def _candidate_subject(candidate: Mapping[str, Any]) -> tuple[str, str]:
    subject = candidate.get("subject")
    if not isinstance(subject, Mapping):
        return ("", "")
    return (str(subject.get("type", "")), str(subject.get("id", "")))


def _base_score(candidate: Mapping[str, Any], config: RankingConfig) -> tuple[int, ...]:
    features = _mapping(candidate.get("features"), "$.candidate.features")
    corroboration = _integer(
        features.get("corroboration_count"),
        "$.candidate.features.corroboration_count",
        0,
    )
    return (
        _priority_value(
            config,
            "conflict_status",
            features.get("conflict_status"),
            "$.candidate.features.conflict_status",
        ),
        _priority_value(
            config,
            "quality_significance",
            features.get("quality_significance"),
            "$.candidate.features.quality_significance",
        ),
        _priority_value(
            config,
            "materiality_bucket",
            features.get("materiality_bucket"),
            "$.candidate.features.materiality_bucket",
        ),
        _priority_value(
            config,
            "intent",
            candidate.get("intent"),
            "$.candidate.intent",
        ),
        _priority_value(
            config,
            "cross_source",
            features.get("cross_source"),
            "$.candidate.features.cross_source",
        ),
        min(corroboration, 9),
        _priority_value(
            config,
            "recency_bucket",
            features.get("recency_bucket"),
            "$.candidate.features.recency_bucket",
        ),
    )


def _selection_score(
    candidate: Mapping[str, Any],
    config: RankingConfig,
    seen_subjects: set[tuple[str, str]],
) -> tuple[int, ...]:
    base = _base_score(candidate, config)
    diversity = int(_candidate_subject(candidate) not in seen_subjects)
    return (*base[:3], diversity, *base[3:])


def _best_candidate(
    candidates: Sequence[Mapping[str, Any]],
    config: RankingConfig,
    seen_subjects: set[tuple[str, str]],
) -> Mapping[str, Any]:
    return min(
        candidates,
        key=lambda candidate: (
            tuple(-value for value in _selection_score(candidate, config, seen_subjects)),
            candidate_sort_key(candidate),
            str(candidate.get("candidate_id", "")),
        ),
    )


def _is_divergent(candidate: Mapping[str, Any]) -> bool:
    features = candidate.get("features")
    return isinstance(features, Mapping) and features.get("conflict_status") == "divergent"


def _is_material_quality(candidate: Mapping[str, Any]) -> bool:
    features = candidate.get("features")
    return isinstance(features, Mapping) and features.get("quality_significance") == "material"


def _candidate_eligible(
    candidate: Mapping[str, Any],
    *,
    config: RankingConfig,
    selected_ids: set[str],
    redundancy_groups: set[str],
    section_counts: Counter[str],
    intent_counts: Counter[str],
) -> bool:
    candidate_id = str(candidate.get("candidate_id", ""))
    features = _mapping(candidate.get("features"), "$.candidate.features")
    redundancy_group = _string(
        features.get("redundancy_group"),
        "$.candidate.features.redundancy_group",
    )
    section = str(candidate.get("section", ""))
    intent = str(candidate.get("intent", ""))
    return (
        candidate_id not in selected_ids
        and redundancy_group not in redundancy_groups
        and section in config.section_limits
        and intent in config.intent_limits
        and section_counts[section] < config.section_limits[section]
        and section_counts[section] < config.max_per_section
        and intent_counts[intent] < config.intent_limits[intent]
    )


def _select_one(
    pool: Sequence[Mapping[str, Any]],
    *,
    config: RankingConfig,
    selected: list[dict[str, Any]],
    selected_ids: set[str],
    redundancy_groups: set[str],
    section_counts: Counter[str],
    intent_counts: Counter[str],
    seen_subjects: set[tuple[str, str]],
    stage: str,
) -> bool:
    eligible = [
        candidate
        for candidate in pool
        if _candidate_eligible(
            candidate,
            config=config,
            selected_ids=selected_ids,
            redundancy_groups=redundancy_groups,
            section_counts=section_counts,
            intent_counts=intent_counts,
        )
    ]
    if not eligible or len(selected) >= config.max_total:
        return False
    candidate = _best_candidate(eligible, config, seen_subjects)
    candidate_id = _string(candidate.get("candidate_id"), "$.candidate.candidate_id")
    features = _mapping(candidate.get("features"), "$.candidate.features")
    redundancy_group = _string(
        features.get("redundancy_group"),
        "$.candidate.features.redundancy_group",
    )
    score = _selection_score(candidate, config, seen_subjects)
    selected.append(
        {
            "candidate_id": candidate_id,
            "section": candidate["section"],
            "intent": candidate["intent"],
            "subject": dict(_mapping(candidate["subject"], "$.candidate.subject")),
            "metric": candidate["metric"],
            "redundancy_group": redundancy_group,
            "selection_stage": stage,
            "score_vector": list(score),
        }
    )
    selected_ids.add(candidate_id)
    redundancy_groups.add(redundancy_group)
    section_counts[str(candidate["section"])] += 1
    intent_counts[str(candidate["intent"])] += 1
    seen_subjects.add(_candidate_subject(candidate))
    return True


def select_deterministic_candidates(
    candidates: Sequence[Mapping[str, Any]],
    *,
    config: RankingConfig,
    candidate_schema: dict[str, Any],
    evidence_bundle_id: str,
) -> dict[str, Any]:
    ordered = [dict(candidate) for candidate in order_candidates(candidates)]
    if not ordered:
        _fail("empty_candidate_set", "$.candidates", "candidate set must not be empty")
    for index, candidate in enumerate(ordered):
        diagnostics = validate_schema(
            candidate,
            candidate_schema,
            path=f"$.candidates[{index}]",
        )
        if diagnostics:
            first = diagnostics[0]
            _fail("invalid_candidate", first.path, first.message)
        if candidate.get("evidence_bundle_id") != evidence_bundle_id:
            _fail(
                "candidate_bundle_mismatch",
                f"$.candidates[{index}].evidence_bundle_id",
                "candidate does not reference the supplied evidence bundle",
            )
    try:
        indexed = index_candidates_by_id(ordered)
    except ValueError as exc:
        _fail("invalid_candidate_identity", "$.candidates", str(exc))
    if len(indexed) != len(ordered):
        _fail("candidate_index_mismatch", "$.candidates", "candidate index is incomplete")

    selected: list[dict[str, Any]] = []
    selected_ids: set[str] = set()
    redundancy_groups: set[str] = set()
    section_counts: Counter[str] = Counter()
    intent_counts: Counter[str] = Counter()
    seen_subjects: set[tuple[str, str]] = set()

    for section in config.required_sections_if_available:
        pool = [candidate for candidate in ordered if candidate.get("section") == section]
        if pool and not _select_one(
            pool,
            config=config,
            selected=selected,
            selected_ids=selected_ids,
            redundancy_groups=redundancy_groups,
            section_counts=section_counts,
            intent_counts=intent_counts,
            seen_subjects=seen_subjects,
            stage=f"required_section:{section}",
        ):
            _fail(
                "required_section_unselectable",
                f"$.config.required_sections_if_available.{section}",
                "eligible candidates exist but configured limits prevent required coverage",
            )

    signal_pools = {
        "divergent_conflict": [candidate for candidate in ordered if _is_divergent(candidate)],
        "material_quality": [candidate for candidate in ordered if _is_material_quality(candidate)],
    }
    for signal in _SIGNAL_NAMES:
        pool = signal_pools[signal]
        if pool:
            _select_one(
                pool,
                config=config,
                selected=selected,
                selected_ids=selected_ids,
                redundancy_groups=redundancy_groups,
                section_counts=section_counts,
                intent_counts=intent_counts,
                seen_subjects=seen_subjects,
                stage=f"material_signal:{signal}",
            )

    while len(selected) < config.max_total:
        if not _select_one(
            ordered,
            config=config,
            selected=selected,
            selected_ids=selected_ids,
            redundancy_groups=redundancy_groups,
            section_counts=section_counts,
            intent_counts=intent_counts,
            seen_subjects=seen_subjects,
            stage="ranked_fill",
        ):
            break

    if not selected:
        _fail("empty_selection", "$.selection", "configured baseline selected no candidates")
    selected_candidate_ids = [item["candidate_id"] for item in selected]
    if len(selected_candidate_ids) != len(set(selected_candidate_ids)):
        _fail("duplicate_selection", "$.selection", "selected candidate IDs must be unique")
    if len(redundancy_groups) != len(selected):
        _fail("redundancy_violation", "$.selection", "selected redundancy groups must be unique")

    return {
        "ranking_version": config.ranking_version,
        "ranking_config_sha256": content_sha256(config.as_dict()),
        "evidence_bundle_id": evidence_bundle_id,
        "candidate_count": len(ordered),
        "ordered_candidate_sha256": content_sha256(ordered),
        "selected_candidate_ids": selected_candidate_ids,
        "selected_candidates": selected,
        "selected_count": len(selected),
        "section_counts": {
            section: section_counts[section]
            for section in config.section_order
            if section_counts[section]
        },
        "intent_counts": {
            intent: intent_counts[intent]
            for intent in CLAIM_PLAN_INTENTS
            if intent_counts[intent]
        },
        "subject_count": len(seen_subjects),
        "redundancy_group_count": len(redundancy_groups),
    }


def _claim_id(candidate_id: str) -> str:
    prefix = "claim-candidate:sha256:"
    if not candidate_id.startswith(prefix):
        _fail("invalid_candidate_id", "$.selection.candidate_id", "candidate ID prefix is unsupported")
    digest = candidate_id.removeprefix(prefix)
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        _fail("invalid_candidate_id", "$.selection.candidate_id", "candidate ID digest is invalid")
    return f"claim-{digest}"


def reconstruct_claim_plan(
    selection: Mapping[str, Any],
    candidates: Sequence[Mapping[str, Any]],
    *,
    config: RankingConfig,
) -> dict[str, Any]:
    try:
        indexed = index_candidates_by_id(candidates)
    except ValueError as exc:
        _fail("invalid_candidate_identity", "$.candidates", str(exc))
    identifiers = _list(selection.get("selected_candidate_ids"), "$.selection.selected_candidate_ids")
    if not identifiers:
        _fail("empty_selection", "$.selection.selected_candidate_ids", "must not be empty")
    if len(identifiers) != len(set(identifiers)):
        _fail("duplicate_selection", "$.selection.selected_candidate_ids", "must be unique")
    missing = [identifier for identifier in identifiers if identifier not in indexed]
    if missing:
        _fail(
            "unknown_selected_candidate_id",
            "$.selection.selected_candidate_ids",
            "unknown candidate IDs: " + ", ".join(str(item) for item in missing),
        )

    selected = [indexed[str(identifier)] for identifier in identifiers]
    grouped: dict[str, list[dict[str, Any]]] = {}
    claim_ids: set[str] = set()
    for candidate in selected:
        section = _string(candidate.get("section"), "$.candidate.section")
        if section not in config.section_order:
            _fail("unsupported_section", "$.candidate.section", f"unsupported section: {section}")
        claim_id = _claim_id(_string(candidate.get("candidate_id"), "$.candidate.candidate_id"))
        if claim_id in claim_ids:
            _fail("claim_id_collision", "$.claim_plan", f"duplicate claim ID: {claim_id}")
        claim_ids.add(claim_id)
        grouped.setdefault(section, []).append(
            {
                "claim_id": claim_id,
                "intent": candidate["intent"],
                "evidence_ids": list(candidate["evidence_ids"]),
                "comparison_relation": candidate["comparison_relation"],
                "confidence": candidate["confidence"],
            }
        )

    analysis_order = [section for section in config.section_order if section in grouped]
    sections = [
        {"section_kind": section, "claims": grouped[section]}
        for section in analysis_order
    ]
    plan = {
        "claim_plan_version": CLAIM_PLAN_SCHEMA_VERSION,
        "prompt_version": CLAIM_PLAN_PROMPT_VERSION,
        "evidence_bundle_id": selection["evidence_bundle_id"],
        "analysis_order": analysis_order,
        "sections": sections,
    }
    return plan


def run_deterministic_baseline(
    bundle: dict[str, Any],
    candidates: Sequence[Mapping[str, Any]],
    *,
    config: RankingConfig,
    evidence_schema: dict[str, Any],
    candidate_schema: dict[str, Any],
    claim_plan_schema: dict[str, Any],
) -> DeterministicBaselineResult:
    diagnostics = validate_schema(bundle, evidence_schema, path="$.bundle")
    if diagnostics:
        first = diagnostics[0]
        _fail("invalid_evidence_bundle", first.path, first.message)
    bundle_id = _string(bundle.get("bundle_id"), "$.bundle.bundle_id")
    selection = select_deterministic_candidates(
        candidates,
        config=config,
        candidate_schema=candidate_schema,
        evidence_bundle_id=bundle_id,
    )
    plan = reconstruct_claim_plan(selection, candidates, config=config)
    report = validate_claim_plan(
        bundle,
        plan,
        evidence_schema=evidence_schema,
        claim_plan_schema=claim_plan_schema,
    )
    if not report.is_valid:
        first = report.diagnostics[0]
        _fail(
            "reconstructed_plan_invalid",
            first.path,
            f"{first.stage}/{first.code}: {first.message}",
        )
    rendered = render_claim_plan(bundle, plan, report)
    return DeterministicBaselineResult(selection, plan, report, rendered)
