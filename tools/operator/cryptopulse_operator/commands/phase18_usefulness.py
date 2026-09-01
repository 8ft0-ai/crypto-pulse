"""Authoritative protected-main usefulness proof for Phase 18."""

from __future__ import annotations

import hashlib
import importlib
from pathlib import Path
import sys
from typing import Any

from ..evidence import Evidence, Status
from ..github_read import GitHubReadError, GitHubReader, REPOSITORY
from ..process import ProcessRunner
from ..review_support import runtime_gate
from ..runtime import runtime_root


COMMAND = "phase18-usefulness"
TARGET = {"kind": "phase18-usefulness"}
_CONTRACT_MODULE_NAMES = (
    "phase18_multi_asset_temporal_evidence",
    "phase15_public_temporal_evidence",
    "render_crypto_observation_hour_series",
    "render_phase18_multi_asset_temporal_evidence",
)


def _evidence(
    *,
    runtime: dict[str, Any],
    remote: dict[str, Any],
    local: dict[str, Any],
    status: Status,
    complete: bool,
    assertions: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    findings: list[dict[str, Any]] | tuple[dict[str, Any], ...],
) -> Evidence:
    return Evidence(
        command=COMMAND,
        repository=REPOSITORY,
        invocation_target=TARGET,
        runtime=runtime,
        remote=remote,
        local=local,
        status=status,
        completeness={"complete": complete, "runtime": True, "phase18_usefulness": complete},
        assertions=tuple(assertions),
        findings=tuple(findings),
    )


def _module_origin(module: Any) -> Path:
    origin = getattr(module, "__file__", None)
    if not isinstance(origin, str):
        raise RuntimeError("repository script module origin is unavailable")
    return Path(origin).resolve()


def _load_contracts(root: Path) -> dict[str, Any]:
    """Load exact-checkout repository contracts only after exact-main trust succeeds."""
    scripts = (root / "scripts").resolve()
    if not scripts.is_dir():
        raise RuntimeError("repository scripts directory is unavailable")

    repository_module_names = {
        path.stem
        for path in scripts.glob("*.py")
        if path.is_file()
    }
    preloaded = sorted(
        name for name in repository_module_names if name in sys.modules
    )
    if preloaded:
        raise RuntimeError(
            "repository script module loaded before exact-main trust: "
            + ", ".join(preloaded)
        )

    script_text = str(scripts)
    sys.path.insert(0, script_text)
    try:
        importlib.invalidate_caches()
        loaded = {
            name: importlib.import_module(name)
            for name in _CONTRACT_MODULE_NAMES
        }

        for module_name, module in loaded.items():
            expected = (scripts / f"{module_name}.py").resolve()
            if _module_origin(module) != expected:
                raise RuntimeError(
                    f"repository contract module origin mismatch: {module_name}"
                )

        for module_name in repository_module_names:
            module = sys.modules.get(module_name)
            if module is None:
                continue
            expected = (scripts / f"{module_name}.py").resolve()
            if _module_origin(module) != expected:
                raise RuntimeError(
                    f"repository transitive module origin mismatch: {module_name}"
                )

        return {
            "phase18": loaded["phase18_multi_asset_temporal_evidence"],
            "phase15": loaded["phase15_public_temporal_evidence"],
            "reader": loaded["render_crypto_observation_hour_series"],
            "renderer": loaded["render_phase18_multi_asset_temporal_evidence"],
        }
    finally:
        try:
            sys.path.remove(script_text)
        except ValueError:
            pass


def _gate_failure(
    gate: Any,
    *,
    status: Status,
    finding: str,
    assertions: list[dict[str, Any]] | None = None,
    remote: dict[str, Any] | None = None,
) -> Evidence:
    return _evidence(
        runtime=gate.runtime,
        remote=remote or {},
        local={"USEFULNESS_GATE": status.value},
        status=status,
        complete=False,
        assertions=list(gate.assertions) + list(assertions or []),
        findings=list(gate.findings) + [{"code": finding}],
    )


def run(runner: ProcessRunner, github: GitHubReader) -> Evidence:
    gate = runtime_gate(runner, github)
    if gate.status is not None:
        return Evidence(
            command=COMMAND,
            repository=REPOSITORY,
            invocation_target=TARGET,
            runtime=gate.runtime,
            remote={},
            local={"USEFULNESS_GATE": gate.status.value},
            status=gate.status,
            completeness={
                "complete": False,
                "runtime": gate.complete,
                "phase18_usefulness": False,
            },
            assertions=gate.assertions,
            findings=gate.findings,
        )

    try:
        main = github.main_branch()
    except GitHubReadError:
        return _gate_failure(
            gate,
            status=Status.INCOMPLETE,
            finding="protected-main-evidence-unavailable",
        )

    remote = {
        "protected_main_commit": main.get("sha"),
        "protected_main_tree": main.get("tree_sha"),
        "protected": main.get("protected"),
    }
    exact_assertions = [
        {"name": "protected-main", "holds": main.get("protected") is True},
        {
            "name": "runtime-is-current-protected-main-commit",
            "holds": gate.runtime.get("commit_sha") == main.get("sha"),
        },
        {
            "name": "runtime-is-current-protected-main-tree",
            "holds": gate.runtime.get("tree_sha") == main.get("tree_sha"),
        },
    ]
    if not all(item["holds"] for item in exact_assertions):
        if main.get("protected") is not True:
            code = "main-not-protected"
        elif gate.runtime.get("commit_sha") != main.get("sha"):
            code = "runtime-not-current-protected-main"
        else:
            code = "runtime-tree-not-current-protected-main"
        return _gate_failure(
            gate,
            status=Status.ERROR,
            finding=code,
            assertions=exact_assertions,
            remote=remote,
        )

    root = runtime_root().resolve()
    try:
        contracts = _load_contracts(root)
    except Exception:
        return _gate_failure(
            gate,
            status=Status.ERROR,
            finding="phase18-contract-load-failed",
            assertions=exact_assertions,
            remote=remote,
        )

    phase18 = contracts["phase18"]
    phase15 = contracts["phase15"]
    reader = contracts["reader"]
    renderer = contracts["renderer"]
    commit_sha = main["sha"]
    assertions = list(gate.assertions) + exact_assertions
    findings: list[dict[str, Any]] = []

    try:
        bundle = phase18.build_multi_asset_temporal_evidence(root, commit_sha)
    except Exception:
        return _evidence(
            runtime=gate.runtime,
            remote=remote,
            local={"USEFULNESS_GATE": Status.ERROR.value},
            status=Status.ERROR,
            complete=False,
            assertions=assertions,
            findings=[{"code": "phase18-materialisation-failed"}],
        )
    if bundle is None:
        return _evidence(
            runtime=gate.runtime,
            remote=remote,
            local={"USEFULNESS_GATE": Status.INCOMPLETE.value},
            status=Status.INCOMPLETE,
            complete=False,
            assertions=assertions + [{"name": "phase18-materialised", "holds": False}],
            findings=[{"code": "phase18-evidence-unavailable"}],
        )
    assertions.append({"name": "phase18-materialised", "holds": True})

    try:
        validated = phase18.validate_multi_asset_temporal_evidence(root, bundle)
    except Exception:
        return _evidence(
            runtime=gate.runtime,
            remote=remote,
            local={
                "phase18_replay_validation": "FAIL",
                "USEFULNESS_GATE": Status.FAIL.value,
            },
            status=Status.FAIL,
            complete=True,
            assertions=assertions
            + [{"name": "phase18-replay-validation", "holds": False}],
            findings=[{"code": "phase18-replay-validation-failed"}],
        )
    assertions.append({"name": "phase18-replay-validation", "holds": True})

    canonical_first = phase18.canonical_bundle_bytes(validated)
    bundle_sha256 = hashlib.sha256(canonical_first).hexdigest()

    try:
        rebuilt = phase18.build_multi_asset_temporal_evidence(root, commit_sha)
        rebuild_ok = (
            rebuilt is not None
            and phase18.canonical_bundle_bytes(rebuilt) == canonical_first
        )
    except Exception:
        rebuilt = None
        rebuild_ok = False
    assertions.append({"name": "independent-bundle-reproduction", "holds": rebuild_ok})
    if not rebuild_ok:
        findings.append({"code": "independent-bundle-reproduction-mismatch"})

    series = validated.get("series") if isinstance(validated, dict) else None
    expected_order = tuple(phase18.PUBLIC_SERIES_KEYS)
    actual_order = (
        tuple(member.get("series_key") for member in series)
        if isinstance(series, list) and all(isinstance(member, dict) for member in series)
        else ()
    )
    order_ok = actual_order == expected_order
    assertions.append({"name": "fixed-series-order", "holds": order_ok})
    if not order_ok:
        findings.append({"code": "phase18-series-order-mismatch"})

    phase15_ok = False
    try:
        phase15_btc = phase15.build_public_temporal_evidence(root, commit_sha)
        if phase15_btc is not None and isinstance(series, list) and series:
            phase15_ok = (
                phase15.canonical_public_evidence_bytes(phase15_btc)
                == phase15.canonical_public_evidence_bytes(series[0])
            )
    except Exception:
        phase15_ok = False
    assertions.append({"name": "phase15-btc-compatibility", "holds": phase15_ok})
    if not phase15_ok:
        findings.append({"code": "phase15-btc-compatibility-mismatch"})

    projections: dict[str, dict[str, Any]] = {}
    projection_ok = order_ok
    if order_ok:
        try:
            for member, series_key in zip(series, expected_order):
                projections[series_key] = reader._reader_projection_for_series(member, series_key)
        except Exception:
            projection_ok = False
    assertions.append({"name": "reader-projection-reused", "holds": projection_ok})
    if not projection_ok:
        findings.append({"code": "phase18-reader-projection-failed"})

    pair_assertions: list[dict[str, Any]] = []
    if projection_ok:
        for series_key in expected_order:
            pair_assertions.append(
                {
                    "name": f"{series_key}-continuous-pair-available",
                    "holds": projections[series_key]["continuous_pair_count"] > 0,
                }
            )
    else:
        for series_key in expected_order:
            pair_assertions.append(
                {"name": f"{series_key}-continuous-pair-available", "holds": False}
            )
    assertions.extend(pair_assertions)
    for item in pair_assertions:
        if not item["holds"]:
            findings.append(
                {
                    "code": "phase18-continuous-pair-unavailable",
                    "series_key": item["name"].split("-continuous", 1)[0],
                }
            )

    render_first = render_second = None
    renderer_deterministic = False
    try:
        render_first = renderer.render_multi_asset_temporal_evidence(root, validated)
        render_second = renderer.render_multi_asset_temporal_evidence(root, validated)
        renderer_deterministic = (
            render_first.encode("utf-8") == render_second.encode("utf-8")
        )
    except Exception:
        renderer_deterministic = False
    assertions.append({"name": "renderer-deterministic", "holds": renderer_deterministic})
    if not renderer_deterministic:
        findings.append({"code": "phase18-renderer-not-deterministic"})

    renderer_sha256_first = (
        hashlib.sha256(render_first.encode("utf-8")).hexdigest()
        if isinstance(render_first, str)
        else None
    )
    renderer_sha256_second = (
        hashlib.sha256(render_second.encode("utf-8")).hexdigest()
        if isinstance(render_second, str)
        else None
    )

    mandatory_holds = all(item["holds"] for item in assertions[len(gate.assertions):])
    status = Status.PASS if mandatory_holds else Status.FAIL

    window = validated.get("window") if isinstance(validated, dict) else {}
    local: dict[str, Any] = {
        "phase18_contract": getattr(phase18, "PHASE18_CONTRACT_VERSION", None),
        "bundle_id": validated.get("bundle_id") if isinstance(validated, dict) else None,
        "bundle_canonical_identity_or_sha256": bundle_sha256,
        "window_start_utc": window.get("start_utc") if isinstance(window, dict) else None,
        "window_end_utc": window.get("end_utc") if isinstance(window, dict) else None,
        "series_order": list(actual_order),
        "phase18_replay_validation": "PASS",
        "independent_bundle_reproduction": "PASS" if rebuild_ok else "FAIL",
        "phase15_btc_compatibility": "PASS" if phase15_ok else "FAIL",
        "renderer_sha256_first": renderer_sha256_first,
        "renderer_sha256_second": renderer_sha256_second,
        "renderer_deterministic": renderer_deterministic,
        "USEFULNESS_GATE": status.value,
    }
    for series_key in expected_order:
        symbol = series_key.split(".", 1)[0]
        projection = projections.get(series_key, {})
        local[f"{symbol}_asserted_slots"] = projection.get("value_count")
        local[f"{symbol}_continuous_pairs"] = projection.get("continuous_pair_count")

    return _evidence(
        runtime=gate.runtime,
        remote=remote,
        local=local,
        status=status,
        complete=True,
        assertions=assertions,
        findings=findings,
    )
