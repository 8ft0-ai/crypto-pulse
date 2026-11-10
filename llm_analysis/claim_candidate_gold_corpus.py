"""Evaluate the reviewed Phase 6 claim-candidate gold corpus without a model."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

import yaml

from .claim_candidate_compiler import compile_claim_candidates
from .contracts import canonical_json_bytes, content_sha256
from .evaluation import load_evaluation_plan, prepare_evaluation

GOLD_CORPUS_VERSION = "phase-06-claim-candidate-gold/v1"
GOLD_SUMMARY_VERSION = "phase-06-claim-candidate-gold-summary/v1"
DEFAULT_MANIFEST = "evaluation/phase-06/claim-candidate-gold/manifest.yml"
DEFAULT_SUMMARY = "evaluation/phase-06/claim-candidate-gold/summary.json"
DEFAULT_REPORT = "evaluation/phase-06/claim-candidate-gold/review.md"


class ClaimCandidateGoldCorpusError(ValueError):
    """Raised when a gold-corpus record or compiler result is inconsistent."""

    def __init__(self, code: str, path: str, message: str):
        super().__init__(f"{path}: {message}")
        self.code = code
        self.path = path
        self.message = message


@dataclass(frozen=True)
class ClaimCandidateGoldCorpusEvaluation:
    summary: dict[str, Any]
    report_markdown: bytes

    @property
    def summary_bytes(self) -> bytes:
        return canonical_json_bytes(self.summary) + b"\n"


def _fail(code: str, path: str, message: str) -> None:
    raise ClaimCandidateGoldCorpusError(code, path, message)


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


def _relative(value: Any, path: str) -> str:
    text = _string(value, path)
    candidate = PurePosixPath(text)
    if candidate.is_absolute() or ".." in candidate.parts:
        _fail("invalid_path", path, "must be repository-relative without '..'")
    return candidate.as_posix()


def _sha(value: Any, path: str, length: int) -> str:
    text = _string(value, path).lower()
    if len(text) != length or any(char not in "0123456789abcdef" for char in text):
        _fail("invalid_digest", path, f"must be a {length}-character lowercase hex digest")
    return text


def _integer(value: Any, path: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        _fail("invalid_integer", path, f"must be an integer >= {minimum}")
    return value


def _yaml(path: Path, label: str) -> Mapping[str, Any]:
    if not path.is_file():
        _fail("missing_file", label, f"file does not exist: {path}")
    return _mapping(yaml.safe_load(path.read_text(encoding="utf-8")), label)


def _git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def _validate_match(value: Any, path: str, *, partial: bool = False) -> dict[str, Any]:
    row = dict(_mapping(value, path))
    allowed = {"intent", "metric", "comparison_relation", "evidence_ids"}
    required = allowed
    if set(row) - allowed or (not partial and set(row) != required):
        _fail("invalid_match", path, "uses unsupported or missing match keys")
    for key in ("intent", "metric", "comparison_relation"):
        if key in row:
            row[key] = _string(row[key], f"{path}.{key}")
    if "evidence_ids" in row:
        ids = [
            _string(item, f"{path}.evidence_ids")
            for item in _list(row["evidence_ids"], f"{path}.evidence_ids")
        ]
        if not ids or ids != sorted(ids) or len(ids) != len(set(ids)):
            _fail("invalid_evidence_ids", f"{path}.evidence_ids", "must be non-empty, unique and sorted")
        row["evidence_ids"] = ids
    return row


def _validate_expectation(value: Any, path: str, *, features: bool = False) -> dict[str, Any]:
    row = dict(_mapping(value, path))
    expected = {"name", "rationale", "match"} | ({"expected_features"} if features else set())
    if set(row) != expected:
        _fail("invalid_expectation", path, "uses unsupported or missing keys")
    row["name"] = _string(row["name"], f"{path}.name")
    row["rationale"] = _string(row["rationale"], f"{path}.rationale")
    row["match"] = _validate_match(row["match"], f"{path}.match")
    if features:
        raw = dict(_mapping(row["expected_features"], f"{path}.expected_features"))
        allowed = {"cross_source", "conflict_status", "corroboration_count"}
        if set(raw) != allowed or not isinstance(raw.get("cross_source"), bool):
            _fail("invalid_expected_features", f"{path}.expected_features", "uses unsupported or missing keys")
        raw["conflict_status"] = _string(
            raw["conflict_status"], f"{path}.expected_features.conflict_status"
        )
        raw["corroboration_count"] = _integer(
            raw["corroboration_count"], f"{path}.expected_features.corroboration_count"
        )
        row["expected_features"] = raw
    return row


def _validate_forbidden(value: Any, path: str) -> dict[str, Any]:
    row = dict(_mapping(value, path))
    predicate = _string(row.get("predicate"), f"{path}.predicate")
    base = {"name", "rationale", "predicate"}
    extras = {
        "evidence_ids_together": {"evidence_ids"},
        "candidate_match": {"match"},
        "evidence_id_referenced": {"evidence_id"},
        "mixed_source_status": set(),
        "comparison_field_or_unit_mismatch": set(),
    }.get(predicate)
    if extras is None or set(row) != base | extras:
        _fail("invalid_forbidden", path, "uses an unsupported predicate or keys")
    row["name"] = _string(row["name"], f"{path}.name")
    row["rationale"] = _string(row["rationale"], f"{path}.rationale")
    if "evidence_ids" in row:
        ids = [
            _string(item, f"{path}.evidence_ids")
            for item in _list(row["evidence_ids"], f"{path}.evidence_ids")
        ]
        if len(ids) < 2 or ids != sorted(ids) or len(ids) != len(set(ids)):
            _fail("invalid_evidence_ids", f"{path}.evidence_ids", "must contain sorted unique IDs")
        row["evidence_ids"] = ids
    if "evidence_id" in row:
        row["evidence_id"] = _string(row["evidence_id"], f"{path}.evidence_id")
    if "match" in row:
        row["match"] = _validate_match(row["match"], f"{path}.match", partial=True)
    return row


def _validate_omission(value: Any, path: str) -> dict[str, Any]:
    row = dict(_mapping(value, path))
    if set(row) != {"name", "rationale", "evidence_ids"}:
        _fail("invalid_omission", path, "uses unsupported or missing keys")
    row["name"] = _string(row["name"], f"{path}.name")
    row["rationale"] = _string(row["rationale"], f"{path}.rationale")
    ids = [
        _string(item, f"{path}.evidence_ids")
        for item in _list(row["evidence_ids"], f"{path}.evidence_ids")
    ]
    if not ids or ids != sorted(ids) or len(ids) != len(set(ids)):
        _fail("invalid_evidence_ids", f"{path}.evidence_ids", "must be non-empty, unique and sorted")
    row["evidence_ids"] = ids
    return row


def _load_case(root: Path, relative: str, index: int) -> dict[str, Any]:
    row = dict(_yaml(root / relative, f"case_files[{index}]"))
    expected = {
        "key", "classification", "expected_candidate_count",
        "expected_ordered_candidate_sha256", "expectations", "forbidden",
        "forbidden_text", "omissions",
    }
    if set(row) != expected:
        _fail("invalid_case", relative, "uses unsupported or missing keys")
    row["key"] = _string(row["key"], f"{relative}.key")
    row["classification"] = _string(row["classification"], f"{relative}.classification")
    if row["classification"] not in {"historical", "evaluation-only"}:
        _fail("invalid_classification", f"{relative}.classification", "must be historical or evaluation-only")
    row["expected_candidate_count"] = _integer(
        row["expected_candidate_count"], f"{relative}.expected_candidate_count", 1
    )
    row["expected_ordered_candidate_sha256"] = _sha(
        row["expected_ordered_candidate_sha256"],
        f"{relative}.expected_ordered_candidate_sha256", 64,
    )
    row["expectations"] = [
        _validate_expectation(item, f"{relative}.expectations[{idx}]")
        for idx, item in enumerate(_list(row["expectations"], f"{relative}.expectations"))
    ]
    if not row["expectations"]:
        _fail("empty_expectations", f"{relative}.expectations", "must not be empty")
    row["forbidden"] = [
        _validate_forbidden(item, f"{relative}.forbidden[{idx}]")
        for idx, item in enumerate(_list(row["forbidden"], f"{relative}.forbidden"))
    ]
    row["forbidden_text"] = [
        _string(item, f"{relative}.forbidden_text[{idx}]")
        for idx, item in enumerate(_list(row["forbidden_text"], f"{relative}.forbidden_text"))
    ]
    row["omissions"] = [
        _validate_omission(item, f"{relative}.omissions[{idx}]")
        for idx, item in enumerate(_list(row["omissions"], f"{relative}.omissions"))
    ]
    names = [item["name"] for item in row["expectations"] + row["forbidden"] + row["omissions"]]
    if len(names) != len(set(names)):
        _fail("duplicate_name", relative, "expectation, forbidden and omission names must be unique")
    row["source_path"] = relative
    return row


def load_claim_candidate_gold_manifest(
    repository_root: str | Path,
    manifest_path: str | Path = DEFAULT_MANIFEST,
) -> dict[str, Any]:
    root = Path(repository_root).resolve()
    relative = _relative(str(manifest_path), "manifest_path")
    raw = dict(_yaml(root / relative, relative))
    expected = {
        "version", "source_evaluation_config", "source_corpus",
        "source_corpus_git_blob_sha", "case_files", "normalisation_probe_file",
    }
    if set(raw) != expected or raw.get("version") != 1:
        _fail("invalid_manifest", relative, "must use version 1 and exact supported keys")
    raw["source_evaluation_config"] = _relative(
        raw["source_evaluation_config"], f"{relative}.source_evaluation_config"
    )
    raw["source_corpus"] = _relative(raw["source_corpus"], f"{relative}.source_corpus")
    raw["source_corpus_git_blob_sha"] = _sha(
        raw["source_corpus_git_blob_sha"], f"{relative}.source_corpus_git_blob_sha", 40
    )
    files = [
        _relative(item, f"{relative}.case_files[{idx}]")
        for idx, item in enumerate(_list(raw["case_files"], f"{relative}.case_files"))
    ]
    if len(files) != 5 or len(files) != len(set(files)):
        _fail("invalid_case_files", f"{relative}.case_files", "must contain five unique files")
    cases = [_load_case(root, item, idx) for idx, item in enumerate(files)]
    probe_path = _relative(raw["normalisation_probe_file"], f"{relative}.normalisation_probe_file")
    probe = dict(_yaml(root / probe_path, probe_path))
    expected_probe = {
        "classification", "source_case", "kind", "expected_previous_bundle_id",
        "expected_bundle_id", "expected_candidate_count",
        "expected_ordered_candidate_sha256", "expectation", "omissions",
    }
    if set(probe) != expected_probe or probe.get("classification") != "evaluation-only":
        _fail("invalid_probe", probe_path, "must be an evaluation-only record with exact keys")
    probe["source_case"] = _string(probe["source_case"], f"{probe_path}.source_case")
    probe["kind"] = _string(probe["kind"], f"{probe_path}.kind")
    if probe["kind"] != "coinbase_btc_usd_to_canonical_asset_price_v1":
        _fail("unsupported_probe", f"{probe_path}.kind", "normalisation kind is unsupported")
    for key in ("expected_previous_bundle_id", "expected_bundle_id"):
        text = _string(probe[key], f"{probe_path}.{key}")
        if not text.startswith("sha256:"):
            _fail("invalid_bundle_id", f"{probe_path}.{key}", "must use sha256 identity")
        _sha(text.removeprefix("sha256:"), f"{probe_path}.{key}", 64)
        probe[key] = text
    probe["expected_candidate_count"] = _integer(
        probe["expected_candidate_count"], f"{probe_path}.expected_candidate_count", 1
    )
    probe["expected_ordered_candidate_sha256"] = _sha(
        probe["expected_ordered_candidate_sha256"],
        f"{probe_path}.expected_ordered_candidate_sha256", 64,
    )
    probe["expectation"] = _validate_expectation(
        probe["expectation"], f"{probe_path}.expectation", features=True
    )
    probe["omissions"] = [
        _validate_omission(item, f"{probe_path}.omissions[{idx}]")
        for idx, item in enumerate(_list(probe["omissions"], f"{probe_path}.omissions"))
    ]
    probe["source_path"] = probe_path

    plan = load_evaluation_plan(root, raw["source_evaluation_config"])
    if plan.corpus_manifest != raw["source_corpus"]:
        _fail("corpus_path_mismatch", relative, "manifest and evaluation config reference different corpora")
    if _git_blob_sha(root / raw["source_corpus"]) != raw["source_corpus_git_blob_sha"]:
        _fail("corpus_blob_mismatch", raw["source_corpus"], "Phase 5 corpus bytes changed")
    expected_keys = [case.key for case in plan.cases]
    actual_keys = [case["key"] for case in cases]
    if actual_keys != expected_keys:
        _fail("case_order_mismatch", relative, "case files must match the frozen Phase 5 case order")
    indexed_plan = {case.key: case for case in plan.cases}
    for case in cases:
        tags = set(indexed_plan[case["key"]].scenario_tags)
        expected_classification = "evaluation-only" if "evaluation-only" in tags else "historical"
        if case["classification"] != expected_classification:
            _fail("classification_mismatch", case["source_path"], "classification differs from Phase 5 tags")
    if (
        probe["source_case"] not in indexed_plan
        or "evaluation-only" not in indexed_plan[probe["source_case"]].scenario_tags
    ):
        _fail("invalid_probe_source", probe_path, "probe source must be an evaluation-only Phase 5 case")
    return {
        "version": GOLD_CORPUS_VERSION,
        "manifest_path": relative,
        "source_evaluation_config": raw["source_evaluation_config"],
        "source_corpus": raw["source_corpus"],
        "source_corpus_git_blob_sha": raw["source_corpus_git_blob_sha"],
        "cases": cases,
        "normalisation_probe": probe,
    }


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        _fail("invalid_json", str(path), "must contain a JSON object")
    return value


def _candidate_matches(candidate: Mapping[str, Any], match: Mapping[str, Any]) -> bool:
    return all(candidate.get(key) == value for key, value in match.items())


def _evidence_map(bundle: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {
        str(item["evidence_id"]): item
        for item in bundle.get("evidence", [])
        if isinstance(item, Mapping) and isinstance(item.get("evidence_id"), str)
    }


def _forbidden_matches(
    rule: Mapping[str, Any],
    candidates: Sequence[Mapping[str, Any]],
    bundle: Mapping[str, Any],
) -> list[str]:
    predicate = rule["predicate"]
    evidence = _evidence_map(bundle)
    matched: list[str] = []
    if predicate == "candidate_match":
        matched = [
            str(item["candidate_id"])
            for item in candidates
            if _candidate_matches(item, rule["match"])
        ]
    elif predicate == "evidence_ids_together":
        required = set(rule["evidence_ids"])
        matched = [
            str(item["candidate_id"])
            for item in candidates
            if required.issubset(set(item["evidence_ids"]))
        ]
    elif predicate == "evidence_id_referenced":
        identifier = rule["evidence_id"]
        matched = [
            str(item["candidate_id"])
            for item in candidates
            if identifier in item["evidence_ids"]
        ]
    elif predicate == "mixed_source_status":
        for item in candidates:
            if item["intent"] != "source_status":
                continue
            subjects = {
                (record.get("subject") or {}).get("id")
                for identifier in item["evidence_ids"]
                if (record := evidence.get(identifier)) is not None
            }
            if len(subjects) > 1:
                matched.append(str(item["candidate_id"]))
    elif predicate == "comparison_field_or_unit_mismatch":
        for item in candidates:
            if item["intent"] != "comparison":
                continue
            records = [evidence.get(identifier) for identifier in item["evidence_ids"]]
            if len(records) != 2 or any(record is None for record in records):
                matched.append(str(item["candidate_id"]))
                continue
            left, right = records
            if left.get("field") != right.get("field") or left.get("unit") != right.get("unit"):
                matched.append(str(item["candidate_id"]))
    return matched


def _normalise_probe(bundle: Mapping[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(dict(bundle))
    market = [
        item for item in result.get("evidence", [])
        if item.get("evidence_id") == "market.asset.bitcoin.price_usd"
    ]
    exchange = [
        item for item in result.get("evidence", [])
        if item.get("evidence_id") == "exchange.coinbase_exchange.btc-usd.price"
    ]
    if len(market) != 1 or len(exchange) != 1:
        _fail("probe_evidence_cardinality", "$.normalisation_probe", "expected one market and one exchange BTC price")
    exchange[0]["evidence_id"] = "exchange.coinbase_exchange.bitcoin.price_usd"
    exchange[0]["subject"] = copy.deepcopy(market[0]["subject"])
    exchange[0]["field"] = "price_usd"
    payload = {key: value for key, value in result.items() if key != "bundle_id"}
    result["bundle_id"] = f"sha256:{content_sha256(payload)}"
    return result


def _compile(
    bundle: dict[str, Any],
    evidence_schema: dict[str, Any],
    candidate_schema: dict[str, Any],
) -> list[dict[str, Any]]:
    return list(
        compile_claim_candidates(
            bundle,
            evidence_schema=evidence_schema,
            candidate_schema=candidate_schema,
        )
    )


def _check_permutation(
    bundle: dict[str, Any],
    candidates: Sequence[Mapping[str, Any]],
    evidence_schema: dict[str, Any],
    candidate_schema: dict[str, Any],
) -> None:
    permuted = copy.deepcopy(bundle)
    permuted["evidence"] = list(reversed(permuted["evidence"]))
    other = _compile(permuted, evidence_schema, candidate_schema)
    if canonical_json_bytes(candidates) != canonical_json_bytes(other):
        _fail("candidate_permutation_drift", "$.bundle.evidence", "reversing evidence traversal changed candidate output")


def _render_report(manifest: Mapping[str, Any], summary: Mapping[str, Any]) -> bytes:
    lines = [
        "# Phase 6 reviewed claim-candidate gold corpus",
        "",
        "> **Classification:** repository-owned evaluation evidence; no model or provider output.",
        "",
        f"- Manifest: `{manifest['manifest_path']}`",
        f"- Frozen Phase 5 corpus: `{manifest['source_corpus']}`",
        f"- Corpus Git blob: `{manifest['source_corpus_git_blob_sha']}`",
        f"- Overall status: `{summary['overall']['status']}`",
        f"- Expected useful candidate recall: `{summary['overall']['resolved_expected_count']} / {summary['overall']['expected_useful_count']} (100%)`",
        f"- Prohibited-combination checks: `{summary['overall']['forbidden_check_count']}` with `0` matches",
        "",
        "## Case summary",
        "",
        "| Case | Classification | Candidates | Expected | Recall | Ordered set SHA-256 |",
        "| --- | --- | ---: | ---: | ---: | --- |",
    ]
    summary_by_key = {item["key"]: item for item in summary["cases"]}
    for case in manifest["cases"]:
        row = summary_by_key[case["key"]]
        lines.append(
            f"| `{case['key']}` | `{case['classification']}` | {row['candidate_count']} | "
            f"{row['expected_useful_count']} | 100% | `{row['ordered_candidate_sha256']}` |"
        )
    for case in manifest["cases"]:
        row = summary_by_key[case["key"]]
        resolved = {item["name"]: item["candidate_id"] for item in row["resolved_candidates"]}
        lines.extend([
            "", f"## `{case['key']}`", "",
            f"Classification: `{case['classification']}`  ",
            f"Bundle: `{row['bundle_id']}`  ",
            f"Compiler output: `{row['candidate_count']}` candidates, ordered SHA-256 `{row['ordered_candidate_sha256']}`  ",
            f"Reviewed recall: `{row['resolved_expected_count']} / {row['expected_useful_count']}`",
            "", "### Expected useful candidates", "",
            "| Expectation | Candidate ID | Rationale |",
            "| --- | --- | --- |",
        ])
        for expectation in case["expectations"]:
            lines.append(
                f"| `{expectation['name']}` | `{resolved[expectation['name']]}` | {expectation['rationale']} |"
            )
        lines.extend(["", "### Prohibited combinations", ""])
        for rule in case["forbidden"]:
            lines.append(f"- `{rule['name']}` (`{rule['predicate']}`): {rule['rationale']}")
        for text in case["forbidden_text"]:
            lines.append(f"- Candidate output must not contain `{text}`.")
        lines.extend(["", "### Deliberate omissions", ""])
        for omission in case["omissions"]:
            lines.append(f"- `{omission['name']}`: {omission['rationale']}")
    probe = summary["normalisation_probe"]
    probe_manifest = manifest["normalisation_probe"]
    lines.extend([
        "", "## Explicit evaluation-only normalisation probe", "",
        f"- Classification: `{probe['classification']}`",
        f"- Source case: `{probe['source_case']}`",
        f"- Rule: `{probe['kind']}`",
        f"- Previous bundle: `{probe['previous_bundle_id']}`",
        f"- New bundle: `{probe['bundle_id']}`",
        f"- Candidate count: `{probe['candidate_count']}`",
        f"- Ordered candidate SHA-256: `{probe['ordered_candidate_sha256']}`",
        f"- Resolved disagreement candidate: `{probe['resolved_candidate_id']}`",
        "", probe_manifest["expectation"]["rationale"], "",
    ])
    for omission in probe_manifest["omissions"]:
        lines.append(f"- `{omission['name']}`: {omission['rationale']}")
    lines.extend([
        "", "## Scope boundary", "",
        "This corpus evaluates compiler recall, invalid-combination absence and deterministic identity. It does not rank candidates, select a report, reconstruct a production plan, call a provider or publish content.",
        "",
    ])
    return "\n".join(lines).encode("utf-8")


def evaluate_claim_candidate_gold_corpus(
    repository_root: str | Path,
    manifest_path: str | Path = DEFAULT_MANIFEST,
) -> ClaimCandidateGoldCorpusEvaluation:
    root = Path(repository_root).resolve()
    manifest = load_claim_candidate_gold_manifest(root, manifest_path)
    evidence_schema = _read_json(root / "schemas/crypto-market-evidence-bundle-v1.json")
    candidate_schema = _read_json(root / "schemas/crypto-market-claim-candidate-v1.json")
    case_results: list[dict[str, Any]] = []
    bundles: dict[str, dict[str, Any]] = {}

    with tempfile.TemporaryDirectory() as temporary:
        _, prepared = prepare_evaluation(
            repository_root=root,
            config_path=manifest["source_evaluation_config"],
            output_dir=temporary,
        )
        prepared_by_key = {case.key: case for case in prepared}
        for case in manifest["cases"]:
            prepared_case = prepared_by_key[case["key"]]
            bundle = _read_json(Path(temporary) / prepared_case.bundle_file)
            bundles[case["key"]] = bundle
            candidates = _compile(bundle, evidence_schema, candidate_schema)
            _check_permutation(bundle, candidates, evidence_schema, candidate_schema)
            candidate_hash = content_sha256(candidates)
            if len(candidates) != case["expected_candidate_count"]:
                _fail("candidate_count_mismatch", case["source_path"], "compiler candidate count differs from review")
            if candidate_hash != case["expected_ordered_candidate_sha256"]:
                _fail("candidate_hash_mismatch", case["source_path"], "ordered candidate set differs from review")

            resolved: list[dict[str, str]] = []
            for expectation in case["expectations"]:
                matches = [item for item in candidates if _candidate_matches(item, expectation["match"])]
                if len(matches) != 1:
                    _fail(
                        "expectation_cardinality",
                        f"{case['source_path']}.expectations.{expectation['name']}",
                        f"expected exactly one candidate, found {len(matches)}",
                    )
                resolved.append({"name": expectation["name"], "candidate_id": str(matches[0]["candidate_id"])})

            forbidden_checks = 0
            for rule in case["forbidden"]:
                forbidden_checks += 1
                matches = _forbidden_matches(rule, candidates, bundle)
                if matches:
                    _fail(
                        "forbidden_candidate",
                        f"{case['source_path']}.forbidden.{rule['name']}",
                        "matched candidate IDs: " + ", ".join(matches),
                    )
            candidate_text = canonical_json_bytes(candidates).decode("utf-8").casefold()
            for text in case["forbidden_text"]:
                forbidden_checks += 1
                if text.casefold() in candidate_text:
                    _fail("forbidden_text", f"{case['source_path']}.forbidden_text", f"candidate output contains {text!r}")

            case_results.append({
                "key": case["key"],
                "classification": case["classification"],
                "bundle_id": bundle["bundle_id"],
                "candidate_count": len(candidates),
                "ordered_candidate_sha256": candidate_hash,
                "expected_useful_count": len(case["expectations"]),
                "resolved_expected_count": len(resolved),
                "candidate_recall": 1.0,
                "forbidden_check_count": forbidden_checks,
                "forbidden_match_count": 0,
                "deterministic_permutation": True,
                "resolved_candidates": resolved,
            })

        probe_manifest = manifest["normalisation_probe"]
        source_bundle = bundles[probe_manifest["source_case"]]
        if source_bundle["bundle_id"] != probe_manifest["expected_previous_bundle_id"]:
            _fail("probe_previous_bundle_mismatch", probe_manifest["source_path"], "source bundle identity changed")
        normalised = _normalise_probe(source_bundle)
        if normalised["bundle_id"] != probe_manifest["expected_bundle_id"]:
            _fail("probe_bundle_mismatch", probe_manifest["source_path"], "normalised bundle identity changed")
        if normalised["bundle_id"] == source_bundle["bundle_id"]:
            _fail("probe_identity_not_changed", probe_manifest["source_path"], "normalisation must create a new bundle identity")
        probe_candidates = _compile(normalised, evidence_schema, candidate_schema)
        _check_permutation(normalised, probe_candidates, evidence_schema, candidate_schema)
        probe_hash = content_sha256(probe_candidates)
        if len(probe_candidates) != probe_manifest["expected_candidate_count"]:
            _fail("probe_candidate_count_mismatch", probe_manifest["source_path"], "candidate count differs from review")
        if probe_hash != probe_manifest["expected_ordered_candidate_sha256"]:
            _fail("probe_candidate_hash_mismatch", probe_manifest["source_path"], "ordered candidate set differs from review")
        expectation = probe_manifest["expectation"]
        matches = [item for item in probe_candidates if _candidate_matches(item, expectation["match"])]
        if len(matches) != 1:
            _fail("probe_expectation_cardinality", probe_manifest["source_path"], f"expected one candidate, found {len(matches)}")
        selected = matches[0]
        for key, value in expectation["expected_features"].items():
            if selected["features"].get(key) != value:
                _fail("probe_feature_mismatch", probe_manifest["source_path"], f"feature {key} differs from review")
        probe_result = {
            "classification": probe_manifest["classification"],
            "source_case": probe_manifest["source_case"],
            "kind": probe_manifest["kind"],
            "previous_bundle_id": source_bundle["bundle_id"],
            "bundle_id": normalised["bundle_id"],
            "new_bundle_identity": True,
            "candidate_count": len(probe_candidates),
            "ordered_candidate_sha256": probe_hash,
            "expected_useful_count": 1,
            "resolved_expected_count": 1,
            "candidate_recall": 1.0,
            "resolved_candidate_id": selected["candidate_id"],
            "expected_features_match": True,
            "deterministic_permutation": True,
        }

    expected_total = sum(item["expected_useful_count"] for item in case_results)
    forbidden_total = sum(item["forbidden_check_count"] for item in case_results)
    summary = {
        "version": GOLD_SUMMARY_VERSION,
        "manifest_path": manifest["manifest_path"],
        "source_evaluation_config": manifest["source_evaluation_config"],
        "source_corpus": manifest["source_corpus"],
        "source_corpus_git_blob_sha": manifest["source_corpus_git_blob_sha"],
        "cases": case_results,
        "normalisation_probe": probe_result,
        "overall": {
            "status": "pass",
            "case_count": len(case_results),
            "historical_case_count": sum(item["classification"] == "historical" for item in case_results),
            "evaluation_only_case_count": sum(item["classification"] == "evaluation-only" for item in case_results),
            "expected_useful_count": expected_total,
            "resolved_expected_count": expected_total,
            "candidate_recall": 1.0,
            "forbidden_check_count": forbidden_total,
            "forbidden_match_count": 0,
            "deterministic_case_count": len(case_results),
            "normalisation_probe_passed": True,
        },
    }
    return ClaimCandidateGoldCorpusEvaluation(summary, _render_report(manifest, summary))


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate the Phase 6 claim-candidate gold corpus")
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST)
    parser.add_argument("--summary", default=DEFAULT_SUMMARY)
    parser.add_argument("--report", default=DEFAULT_REPORT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    root = Path(args.repository_root).resolve()
    result = evaluate_claim_candidate_gold_corpus(root, args.manifest)
    outputs = {
        root / args.summary: result.summary_bytes,
        root / args.report: result.report_markdown,
    }
    for path, content in outputs.items():
        if args.check:
            if not path.is_file() or path.read_bytes() != content:
                _fail("generated_output_drift", str(path), "checked-in gold-corpus output differs")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
