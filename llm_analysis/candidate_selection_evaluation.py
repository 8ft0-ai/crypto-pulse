"""Evaluate the bounded candidate-ID selector with deterministic scripted clients."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any, Sequence

from .candidate_selection_contract import (
    DEFAULT_SELECTION_PROMPT,
    DEFAULT_SELECTION_SCHEMA,
    build_candidate_selector_request,
    render_candidate_selector_prompt,
)
from .candidate_selection_proof_support import (
    CANDIDATE_SELECTION_PROOF_VERSION,
    CandidateSelectionProof,
    assert_outcome,
    compact_record,
    fail,
    render_report,
    scripted_response,
)
from .candidate_selection_validation_proof import validation_matrix
from .candidate_selector import (
    CANDIDATE_SELECTOR_RUN_VERSION,
    BoundedCandidateSelectorResult,
    ScriptedCandidateSelectorClient,
    SelectorClientError,
    SelectorClientResponse,
    run_bounded_candidate_selector,
)
from .claim_candidate_compiler import compile_claim_candidates
from .claim_candidate_gold_corpus import (
    DEFAULT_MANIFEST as DEFAULT_GOLD_MANIFEST,
    load_claim_candidate_gold_manifest,
)
from .contracts import content_sha256
from .deterministic_ranking import (
    DEFAULT_RANKING_CONFIG,
    load_ranking_config,
    run_deterministic_baseline,
)
from .evaluation import prepare_evaluation
from .openai_schema_projection import project_openai_strict_schema


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        fail("invalid_json", str(path), "must contain a JSON object")
    return value


def _run(
    bundle: dict[str, Any],
    candidates: Sequence[dict[str, Any]],
    steps: Sequence[SelectorClientResponse | SelectorClientError],
    *,
    config: Any,
    evidence_schema: dict[str, Any],
    candidate_schema: dict[str, Any],
    claim_plan_schema: dict[str, Any],
    selection_schema: dict[str, Any],
) -> BoundedCandidateSelectorResult:
    return run_bounded_candidate_selector(
        bundle,
        candidates,
        client=ScriptedCandidateSelectorClient(steps),
        config=config,
        evidence_schema=evidence_schema,
        candidate_schema=candidate_schema,
        claim_plan_schema=claim_plan_schema,
        selection_schema=selection_schema,
    )


def evaluate_candidate_selection_proof(
    repository_root: str | Path,
    *,
    ranking_config_path: str | Path = DEFAULT_RANKING_CONFIG,
    gold_manifest_path: str | Path = DEFAULT_GOLD_MANIFEST,
    selection_schema_path: str | Path = DEFAULT_SELECTION_SCHEMA,
    prompt_path: str | Path = DEFAULT_SELECTION_PROMPT,
) -> CandidateSelectionProof:
    root = Path(repository_root).resolve()
    config = load_ranking_config(root, ranking_config_path)
    manifest = load_claim_candidate_gold_manifest(root, gold_manifest_path)
    selection_schema = _read_json(root / selection_schema_path)
    provider_schema = project_openai_strict_schema(selection_schema)
    prompt_template = (root / prompt_path).read_text(encoding="utf-8")
    evidence_schema = _read_json(root / "schemas/crypto-market-evidence-bundle-v1.json")
    candidate_schema = _read_json(root / "schemas/crypto-market-claim-candidate-v1.json")
    claim_plan_schema = _read_json(root / "schemas/crypto-market-claim-plan-v1.json")

    scenario_records: list[dict[str, Any]] = []
    case_summaries: list[dict[str, Any]] = []
    representative_request = representative_repair = representative_plan = None
    representative_render = None
    matrix = None

    with tempfile.TemporaryDirectory() as temporary:
        _, prepared = prepare_evaluation(
            repository_root=root,
            config_path=manifest["source_evaluation_config"],
            output_dir=temporary,
        )
        for prepared_case, case_manifest in zip(prepared, manifest["cases"], strict=True):
            bundle = _read_json(Path(temporary) / prepared_case.bundle_file)
            candidates = list(
                compile_claim_candidates(
                    bundle,
                    evidence_schema=evidence_schema,
                    candidate_schema=candidate_schema,
                )
            )
            baseline = run_deterministic_baseline(
                bundle,
                candidates,
                config=config,
                evidence_schema=evidence_schema,
                candidate_schema=candidate_schema,
                claim_plan_schema=claim_plan_schema,
            )
            baseline_ids = list(baseline.selection["selected_candidate_ids"])
            model_ids = list(reversed(baseline_ids[:5]))
            valid = {"selected_candidate_ids": model_ids}
            unknown = {
                "selected_candidate_ids": [
                    "claim-candidate:sha256:" + "0" * 64,
                    *model_ids[1:],
                ]
            }
            duplicate = {"selected_candidate_ids": [model_ids[0], model_ids[0]]}
            scenarios = [
                (
                    "accepted_initial",
                    [scripted_response(valid, scenario="accepted_initial", attempt=1)],
                    ("accepted_initial", 1, 0, False),
                ),
                (
                    "accepted_after_repair",
                    [
                        scripted_response(unknown, scenario="accepted_after_repair", attempt=1),
                        scripted_response(valid, scenario="accepted_after_repair", attempt=2),
                    ],
                    ("accepted_after_repair", 2, 1, False),
                ),
                (
                    "invalid_repair_fallback",
                    [
                        scripted_response(unknown, scenario="invalid_repair_fallback", attempt=1),
                        scripted_response(duplicate, scenario="invalid_repair_fallback", attempt=2),
                    ],
                    ("deterministic_fallback", 2, 1, True),
                ),
                (
                    "malformed_envelope_fallback",
                    [scripted_response({"ids": model_ids}, scenario="malformed_envelope_fallback", attempt=1)],
                    ("deterministic_fallback", 1, 0, True),
                ),
                (
                    "client_failure_fallback",
                    [SelectorClientError("transport_error", "scripted transport failure")],
                    ("deterministic_fallback", 1, 0, True),
                ),
            ]

            case_records: list[dict[str, Any]] = []
            accepted: BoundedCandidateSelectorResult | None = None
            for name, steps, expected in scenarios:
                result = _run(
                    bundle,
                    candidates,
                    steps,
                    config=config,
                    evidence_schema=evidence_schema,
                    candidate_schema=candidate_schema,
                    claim_plan_schema=claim_plan_schema,
                    selection_schema=selection_schema,
                )
                assert_outcome(
                    result,
                    outcome=expected[0],
                    attempts=expected[1],
                    repairs=expected[2],
                    fallback=expected[3],
                    path=f"$.cases.{prepared_case.key}.{name}",
                )
                compact = compact_record(prepared_case.key, name, result, baseline)
                if not compact["fallback_exact"]:
                    fail("fallback_drift", f"$.cases.{prepared_case.key}.{name}", "fallback changed")
                scenario_records.append(compact)
                case_records.append(compact)
                if name == "accepted_initial":
                    accepted = result
                if name == "accepted_after_repair" and prepared_case.key == "historical-material-move":
                    representative_repair = result.record["repair"]

            if accepted is None:
                fail("missing_accepted_scenario", f"$.cases.{prepared_case.key}", "missing")
            reversed_result = _run(
                bundle,
                list(reversed(candidates)),
                [scripted_response(valid, scenario="accepted_initial", attempt=1)],
                config=config,
                evidence_schema=evidence_schema,
                candidate_schema=candidate_schema,
                claim_plan_schema=claim_plan_schema,
                selection_schema=selection_schema,
            )
            if (
                accepted.record_bytes != reversed_result.record_bytes
                or accepted.claim_plan_bytes != reversed_result.claim_plan_bytes
                or accepted.render.markdown != reversed_result.render.markdown
            ):
                fail("candidate_permutation_drift", prepared_case.key, "output changed")

            permuted_bundle = copy.deepcopy(bundle)
            permuted_bundle["evidence"] = list(reversed(permuted_bundle["evidence"]))
            permuted_candidates = list(
                compile_claim_candidates(
                    permuted_bundle,
                    evidence_schema=evidence_schema,
                    candidate_schema=candidate_schema,
                )
            )
            evidence_result = _run(
                permuted_bundle,
                permuted_candidates,
                [scripted_response(valid, scenario="accepted_initial", attempt=1)],
                config=config,
                evidence_schema=evidence_schema,
                candidate_schema=candidate_schema,
                claim_plan_schema=claim_plan_schema,
                selection_schema=selection_schema,
            )
            if (
                accepted.record_bytes != evidence_result.record_bytes
                or accepted.claim_plan_bytes != evidence_result.claim_plan_bytes
                or accepted.render.markdown != evidence_result.render.markdown
            ):
                fail("evidence_permutation_drift", prepared_case.key, "output changed")

            request = build_candidate_selector_request(
                candidates, config=config, evidence_bundle_id=bundle["bundle_id"]
            )
            initial_prompt = render_candidate_selector_prompt(prompt_template, request)
            case_summaries.append(
                {
                    "key": prepared_case.key,
                    "classification": case_manifest["classification"],
                    "candidate_count": len(candidates),
                    "candidate_set_id": request["candidate_set_id"],
                    "request_id": request["request_id"],
                    "request_sha256": content_sha256(request),
                    "initial_prompt_sha256": hashlib.sha256(initial_prompt.encode()).hexdigest(),
                    "candidate_permutation_stable": True,
                    "evidence_permutation_stable": True,
                    "scenario_count": len(case_records),
                    "fallback_exact_count": sum(
                        item["fallback_used"] and item["fallback_exact"] for item in case_records
                    ),
                }
            )
            if prepared_case.key == "historical-material-move":
                representative_request = request
                representative_plan = accepted.claim_plan
                representative_render = accepted.render.markdown
                matrix = validation_matrix(
                    candidates,
                    config=config,
                    bundle_id=bundle["bundle_id"],
                    selection_schema=selection_schema,
                )

    if any(
        value is None
        for value in (
            representative_request,
            representative_repair,
            representative_plan,
            representative_render,
            matrix,
        )
    ):
        fail("missing_representative_artifact", "$", "proof artefacts missing")

    scenario_summary = [
        {
            "case": item["case"],
            "scenario": item["scenario"],
            "outcome": item["outcome"],
            "selector_attempt_count": item["selector_attempt_count"],
            "semantic_repair_count": item["semantic_repair_count"],
            "fallback_exact": item["fallback_exact"],
        }
        for item in scenario_records
    ]
    fallbacks = [item for item in scenario_records if item["fallback_used"]]
    overall = {
        "status": "pass",
        "case_count": len(case_summaries),
        "scenario_count": len(scenario_records),
        "accepted_initial_count": sum(item["outcome"] == "accepted_initial" for item in scenario_records),
        "accepted_after_repair_count": sum(item["outcome"] == "accepted_after_repair" for item in scenario_records),
        "fallback_count": len(fallbacks),
        "fallback_exact_count": sum(item["fallback_exact"] for item in fallbacks),
        "maximum_semantic_repair_count": max(item["semantic_repair_count"] for item in scenario_records),
        "scripted_selector_attempt_count": sum(item["selector_attempt_count"] for item in scenario_records),
        "candidate_permutation_stable_count": len(case_summaries),
        "evidence_permutation_stable_count": len(case_summaries),
        "provider_call_count": 0,
        "automatic_generation_enabled": False,
        "publication_enabled": False,
    }
    repair_prompt = render_candidate_selector_prompt(
        prompt_template, representative_request, representative_repair
    )
    summary = {
        "version": CANDIDATE_SELECTION_PROOF_VERSION,
        "selector_run_version": CANDIDATE_SELECTOR_RUN_VERSION,
        "selection_schema_path": str(selection_schema_path),
        "selection_schema_sha256": content_sha256(selection_schema),
        "provider_schema_sha256": content_sha256(provider_schema),
        "prompt_path": str(prompt_path),
        "prompt_sha256": hashlib.sha256(prompt_template.encode()).hexdigest(),
        "representative_request_sha256": content_sha256(representative_request),
        "representative_repair_sha256": content_sha256(representative_repair),
        "representative_plan_sha256": content_sha256(representative_plan),
        "representative_rendered_markdown_sha256": hashlib.sha256(representative_render).hexdigest(),
        "initial_prompt_sha256": hashlib.sha256(
            render_candidate_selector_prompt(prompt_template, representative_request).encode()
        ).hexdigest(),
        "repair_prompt_sha256": hashlib.sha256(repair_prompt.encode()).hexdigest(),
        "cases": case_summaries,
        "scenario_summary": scenario_summary,
        "validation_matrix": matrix,
        "overall": overall,
    }
    scenarios = {"version": CANDIDATE_SELECTION_PROOF_VERSION, "records": scenario_records}
    return CandidateSelectionProof(
        summary,
        scenarios,
        representative_request,
        provider_schema,
        representative_repair,
        representative_plan,
        representative_render,
        render_report(summary),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Write or verify Slice 5 selector proof")
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = Path(args.repository_root).resolve()
    proof = evaluate_candidate_selection_proof(root)
    for relative, content in proof.outputs.items():
        path = root / relative
        if args.check:
            if not path.is_file() or path.read_bytes() != content:
                fail("generated_output_drift", relative, "checked-in proof differs")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
