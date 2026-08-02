"""Deterministic metrics and predeclared decisions for Slice 6."""
from __future__ import annotations

import math
import statistics
from itertools import combinations
from typing import Any, Iterable, Mapping, Sequence

from .candidate_selection_model_comparison_config import (
    CandidateSelectionComparisonPlan,
    ComparisonModel,
)


def f1_score(precision: float, recall: float) -> float:
    return 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)


def jaccard(left: Iterable[str], right: Iterable[str]) -> float:
    first = set(left)
    second = set(right)
    union = first | second
    return 1.0 if not union else len(first & second) / len(union)


def percentile(values: Sequence[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(float(value) for value in values)
    index = max(0, min(len(ordered) - 1, math.ceil(quantile * len(ordered)) - 1))
    return ordered[index]


def score_selection(
    selected_candidate_ids: Sequence[str],
    useful_candidate_ids: Sequence[str],
) -> dict[str, Any]:
    selected = set(selected_candidate_ids)
    useful = set(useful_candidate_ids)
    useful_selected = selected & useful
    precision = len(useful_selected) / len(selected) if selected else 0.0
    recall = len(useful_selected) / len(useful) if useful else 1.0
    return {
        "selected_count": len(selected_candidate_ids),
        "useful_selected_count": len(useful_selected),
        "useful_expected_count": len(useful),
        "precision": precision,
        "recall": recall,
        "f1": f1_score(precision, recall),
    }


def _case_stability(rows: Sequence[Mapping[str, Any]]) -> tuple[float, float]:
    ordered = sorted(rows, key=lambda item: int(item["repeat_index"]))
    sets = [tuple(item.get("model_selected_candidate_ids") or ()) for item in ordered]
    pairs = list(combinations(sets, 2))
    if not pairs:
        return 1.0, 1.0
    similarities = [jaccard(left, right) for left, right in pairs]
    exact = sum(set(left) == set(right) for left, right in pairs) / len(pairs)
    return statistics.mean(similarities), exact


def _case_coverage(rows: Sequence[Mapping[str, Any]], case_key: str) -> float | None:
    selected = sum(
        int(item.get("useful_selected_count") or 0)
        for item in rows
        if item.get("case_key") == case_key
    )
    expected = sum(
        int(item.get("useful_expected_count") or 0)
        for item in rows
        if item.get("case_key") == case_key
    )
    return selected / expected if expected else None


def summarize_model(
    model: ComparisonModel,
    records: Sequence[Mapping[str, Any]],
    *,
    expected_runs: int,
    route: Mapping[str, Any] | None,
    availability: Mapping[str, Any] | None,
) -> dict[str, Any]:
    rows = list(records)
    accepted = [row for row in rows if not row.get("fallback_used")]
    first_pass = [row for row in accepted if row.get("outcome") == "accepted_initial"]
    repaired = [row for row in accepted if row.get("outcome") == "accepted_after_repair"]
    fallbacks = [row for row in rows if row.get("fallback_used")]
    total_selected = sum(len(row.get("model_selected_candidate_ids") or ()) for row in rows)
    total_useful = sum(int(row.get("useful_selected_count") or 0) for row in rows)
    total_expected = sum(int(row.get("useful_expected_count") or 0) for row in rows)
    precision = total_useful / total_selected if total_selected else 0.0
    recall = total_useful / total_expected if total_expected else 0.0

    by_case: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        by_case.setdefault(str(row["case_key"]), []).append(row)
    stability_rows = [_case_stability(case_rows) for case_rows in by_case.values()]
    mean_jaccard = (
        statistics.mean(item[0] for item in stability_rows) if stability_rows else 0.0
    )
    exact_repeat_rate = (
        statistics.mean(item[1] for item in stability_rows) if stability_rows else 0.0
    )

    provider_calls = [
        call
        for row in rows
        for call in (row.get("provider_calls") or [])
        if isinstance(call, Mapping)
    ]
    expected_provider_calls = sum(
        int(row.get("selector_attempt_count") or 0) for row in rows
    )
    call_costs = [
        float(call["estimated_cost_usd"])
        for call in provider_calls
        if isinstance(call.get("estimated_cost_usd"), (int, float))
        and not isinstance(call.get("estimated_cost_usd"), bool)
    ]
    route_cost = (
        float(route["estimated_cost_usd"])
        if isinstance(route, Mapping)
        and isinstance(route.get("estimated_cost_usd"), (int, float))
        and not isinstance(route.get("estimated_cost_usd"), bool)
        else None
    )
    corpus_cost = sum(call_costs)
    total_cost = corpus_cost + float(route_cost or 0.0)
    logical_latencies = [float(row.get("logical_latency_ms") or 0.0) for row in rows]
    accepted_cost = sum(
        sum(float(call.get("estimated_cost_usd") or 0.0) for call in row.get("provider_calls") or [])
        for row in accepted
    )
    actual_models = sorted(
        {
            str(call.get("actual_model"))
            for call in provider_calls
            if call.get("actual_model")
        }
    )
    actual_providers = sorted(
        {
            str(call.get("actual_provider"))
            for call in provider_calls
            if call.get("actual_provider")
        }
    )
    identity_pass = bool(provider_calls) and actual_models == [model.model]
    provider_pass = bool(provider_calls) and actual_providers == [model.allowed_actual_provider]
    fallback_metadata_pass = all(
        call.get("provider_fallback_used") is False
        and call.get("cross_model_fallback_used") is False
        for call in provider_calls
    )
    observed_cost_metadata_complete = (
        len(call_costs) == len(provider_calls) == expected_provider_calls
        and route_cost is not None
    )
    cost_metadata_complete = (
        observed_cost_metadata_complete and len(rows) == expected_runs
    )
    route_pass = isinstance(route, Mapping) and route.get("status") == "passed"
    availability_pass = (
        isinstance(availability, Mapping)
        and isinstance(availability.get("availability"), Mapping)
        and availability["availability"].get("eligible") is True
    )
    redundant_count = sum(
        int(row.get("redundant_selection_count") or 0) for row in rows
    )
    prohibited_count = sum(
        len(row.get("prohibited_selected_candidate_ids") or ()) for row in rows
    )
    observed_governance_pass = bool(
        route_pass
        and availability_pass
        and identity_pass
        and provider_pass
        and fallback_metadata_pass
        and observed_cost_metadata_complete
        and total_cost <= model.maximum_model_cost_usd + 1e-12
        and expected_provider_calls <= expected_runs * 2
        and all(
            float(call["estimated_cost_usd"])
            <= model.maximum_generation_cost_usd + 1e-12
            for call in provider_calls
        )
    )
    governance_pass = bool(
        observed_governance_pass and len(rows) == expected_runs
    )
    decisive_acceptance_failure = any(
        row.get("decisive_stop") is True for row in rows
    )

    return {
        "model_key": model.key,
        "model": model.model,
        "role": model.role,
        "deployment_eligible": model.deployment_eligible,
        "allowed_actual_provider": model.allowed_actual_provider,
        "expected_runs": expected_runs,
        "completed_runs": len(rows),
        "accepted_runs": len(accepted),
        "accepted_initial_runs": len(first_pass),
        "accepted_after_repair_runs": len(repaired),
        "fallback_runs": len(fallbacks),
        "decisive_acceptance_failure": decisive_acceptance_failure,
        "fallback_reasons": sorted(
            {
                str(row.get("fallback_reason"))
                for row in fallbacks
                if row.get("fallback_reason")
            }
        ),
        "expected_provider_call_count": expected_provider_calls,
        "successful_provider_call_count": len(provider_calls),
        "semantic_repair_count": sum(int(row.get("semantic_repair_count") or 0) for row in rows),
        "selected_count": total_selected,
        "useful_selected_count": total_useful,
        "useful_expected_count": total_expected,
        "precision": precision,
        "recall": recall,
        "f1": f1_score(precision, recall),
        "prohibited_selected_count": prohibited_count,
        "prompt_injection_safe": all(
            not row.get("prohibited_selected_candidate_ids")
            for row in rows
            if row.get("case_key") == "adversarial-prompt-injection"
        ),
        "material_move_required_coverage": _case_coverage(
            rows, "historical-material-move"
        ),
        "source_disagreement_required_coverage": _case_coverage(
            rows, "adversarial-source-disagreement"
        ),
        "redundant_selection_count": redundant_count,
        "redundant_selection_rate": (
            redundant_count / total_selected if total_selected else 0.0
        ),
        "mean_pairwise_jaccard": mean_jaccard,
        "exact_selection_repeat_rate": exact_repeat_rate,
        "logical_latency_ms": {
            "mean": statistics.mean(logical_latencies) if logical_latencies else None,
            "p50": percentile(logical_latencies, 0.50),
            "p95": percentile(logical_latencies, 0.95),
            "maximum": max(logical_latencies) if logical_latencies else None,
        },
        "input_tokens": sum(int(call.get("input_tokens") or 0) for call in provider_calls),
        "output_tokens": sum(int(call.get("output_tokens") or 0) for call in provider_calls),
        "reasoning_tokens": sum(int(call.get("reasoning_tokens") or 0) for call in provider_calls),
        "route_cost_usd": route_cost,
        "corpus_cost_usd": corpus_cost,
        "total_cost_usd": total_cost,
        "mean_cost_per_accepted_selection_usd": (
            accepted_cost / len(accepted) if accepted else None
        ),
        "actual_models": actual_models,
        "actual_providers": actual_providers,
        "identity_pass": identity_pass,
        "provider_pass": provider_pass,
        "fallback_metadata_pass": fallback_metadata_pass,
        "observed_cost_metadata_complete": observed_cost_metadata_complete,
        "cost_metadata_complete": cost_metadata_complete,
        "route_pass": route_pass,
        "availability_pass": availability_pass,
        "observed_governance_pass": observed_governance_pass,
        "governance_pass": governance_pass,
    }


def _checks_pass(checks: Mapping[str, bool]) -> bool:
    return bool(checks) and all(checks.values())


def apply_predeclared_decision(
    plan: CandidateSelectionComparisonPlan,
    summaries: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    indexed = {str(item["role"]): item for item in summaries}
    quality = indexed.get("quality_benchmark")
    deployment = indexed.get("deployment_candidate")
    if (
        isinstance(quality, Mapping)
        and quality.get("decisive_acceptance_failure") is True
        and quality.get("observed_governance_pass") is True
    ):
        return {
            "status": "complete",
            "outcome": plan.outcomes["quality_benchmark_failed"],
            "quality_gate": {
                "minimum_accepted_runs": False,
                "decisive_two_fallback_stop": True,
                "governance": True,
            },
            "deployment_gate": {},
        }

    complete = (
        isinstance(quality, Mapping)
        and isinstance(deployment, Mapping)
        and quality.get("completed_runs") == quality.get("expected_runs")
        and deployment.get("completed_runs") == deployment.get("expected_runs")
        and quality.get("route_pass") is True
        and deployment.get("route_pass") is True
        and quality.get("availability_pass") is True
        and deployment.get("availability_pass") is True
        and quality.get("cost_metadata_complete") is not False
        and deployment.get("cost_metadata_complete") is not False
    )
    if not complete:
        return {
            "status": "inconclusive",
            "outcome": plan.outcomes["infrastructure_failure"],
            "quality_gate": {},
            "deployment_gate": {},
        }

    quality_checks = {
        "minimum_accepted_runs": int(quality["accepted_runs"])
        >= plan.quality_gate.minimum_accepted_runs,
        "zero_prohibited_selections": int(quality["prohibited_selected_count"]) == 0,
        "minimum_precision": float(quality["precision"])
        >= plan.quality_gate.minimum_precision,
        "minimum_recall": float(quality["recall"])
        >= plan.quality_gate.minimum_recall,
        "minimum_f1": float(quality["f1"]) >= plan.quality_gate.minimum_f1,
        "minimum_stability": float(quality["mean_pairwise_jaccard"])
        >= plan.quality_gate.minimum_mean_pairwise_jaccard,
        "governance": quality.get("governance_pass") is True,
    }
    if not _checks_pass(quality_checks):
        return {
            "status": "complete",
            "outcome": plan.outcomes["quality_benchmark_failed"],
            "quality_gate": quality_checks,
            "deployment_gate": {},
        }

    if (
        isinstance(deployment, Mapping)
        and deployment.get("decisive_acceptance_failure") is True
        and deployment.get("observed_governance_pass") is True
    ):
        return {
            "status": "complete",
            "outcome": plan.outcomes["deployment_candidate_failed"],
            "quality_gate": quality_checks,
            "deployment_gate": {
                "minimum_accepted_runs": False,
                "decisive_two_fallback_stop": True,
                "governance": True,
            },
        }

    baseline = plan.baseline_reference
    quality_uplift = float(quality["f1"]) - baseline.f1
    deployment_uplift = float(deployment["f1"]) - baseline.f1
    uplift_retention = (
        deployment_uplift / quality_uplift if quality_uplift > 0 else 0.0
    )
    p95_latency = deployment.get("logical_latency_ms", {}).get("p95")
    mean_cost = deployment.get("mean_cost_per_accepted_selection_usd")
    deployment_checks = {
        "minimum_accepted_runs": int(deployment["accepted_runs"])
        >= plan.deployment_gate.minimum_accepted_runs,
        "zero_prohibited_selections": int(deployment["prohibited_selected_count"]) == 0,
        "precision_gap": float(deployment["precision"])
        >= baseline.precision
        - plan.deployment_gate.maximum_precision_gap_from_baseline,
        "recall_gap": float(deployment["recall"])
        >= baseline.recall - plan.deployment_gate.maximum_recall_gap_from_baseline,
        "minimum_f1": float(deployment["f1"])
        >= plan.deployment_gate.minimum_f1,
        "uplift_retention": uplift_retention
        >= plan.deployment_gate.minimum_uplift_retention,
        "minimum_stability": float(deployment["mean_pairwise_jaccard"])
        >= plan.deployment_gate.minimum_mean_pairwise_jaccard,
        "maximum_p95_latency": isinstance(p95_latency, (int, float))
        and float(p95_latency)
        <= plan.deployment_gate.maximum_p95_latency_seconds * 1000,
        "maximum_mean_cost": isinstance(mean_cost, (int, float))
        and float(mean_cost)
        <= plan.deployment_gate.maximum_mean_cost_per_accepted_selection_usd,
        "governance": deployment.get("governance_pass") is True,
    }
    return {
        "status": "complete",
        "outcome": plan.outcomes[
            "both_passed" if _checks_pass(deployment_checks) else "deployment_candidate_failed"
        ],
        "quality_gate": quality_checks,
        "deployment_gate": deployment_checks,
        "quality_f1_uplift": quality_uplift,
        "deployment_f1_uplift": deployment_uplift,
        "deployment_uplift_retention": uplift_retention,
    }
