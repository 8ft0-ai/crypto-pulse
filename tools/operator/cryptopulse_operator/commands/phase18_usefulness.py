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


def _git_output(runner: ProcessRunner, root: Path, args: list[str], label: str) -> str:
    result = runner.git(["-C", str(root), *args])
    if result.returncode != 0:
        raise RuntimeError(f"unable to establish {label}")
    return result.stdout


def _trusted_checkout_identity(
    root: Path,
    runner: ProcessRunner,
    *,
    expected_commit_sha: str | None = None,
    expected_tree_sha: str | None = None,
) -> tuple[str, str]:
    """Require checkout identity to remain bound to the established trusted commit/tree."""
    commit_sha = _git_output(
        runner,
        root,
        ["rev-parse", "HEAD"],
        "repository checkout commit",
    ).strip()
    tree_sha = _git_output(
        runner,
        root,
        ["rev-parse", "HEAD^{tree}"],
        "repository checkout tree",
    ).strip()
    if expected_commit_sha is not None and commit_sha != expected_commit_sha:
        raise RuntimeError("repository checkout commit moved after exact-main trust")
    if expected_tree_sha is not None and tree_sha != expected_tree_sha:
        raise RuntimeError("repository checkout tree moved after exact-main trust")
    return commit_sha, tree_sha


def _verified_repository_module_names(
    root: Path,
    runner: ProcessRunner,
    *,
    expected_commit_sha: str | None = None,
    expected_tree_sha: str | None = None,
) -> set[str]:
    """Bind executable repository scripts to exact regular trusted-commit blobs."""
    trusted_commit, _trusted_tree = _trusted_checkout_identity(
        root,
        runner,
        expected_commit_sha=expected_commit_sha,
        expected_tree_sha=expected_tree_sha,
    )
    scripts_path = root / "scripts"
    if scripts_path.is_symlink() or not scripts_path.is_dir():
        raise RuntimeError("repository scripts directory is unavailable or unsafe")
    scripts = scripts_path.resolve()

    tree_text = _git_output(
        runner,
        root,
        ["ls-tree", "-r", trusted_commit, "--", "scripts"],
        "repository script tree",
    )
    tracked: dict[str, tuple[str, str]] = {}
    for line in tree_text.splitlines():
        if not line:
            continue
        try:
            metadata, path = line.split("\t", 1)
            mode, object_type, blob_sha = metadata.split(" ", 2)
        except ValueError as exc:
            raise RuntimeError("repository script tree entry is malformed") from exc
        if not path.startswith("scripts/") or not path.endswith(".py"):
            continue
        if mode not in {"100644", "100755"} or object_type != "blob":
            raise RuntimeError(f"repository script is not a regular tracked blob: {path}")
        tracked[path] = (mode, blob_sha)

    if not tracked:
        raise RuntimeError("repository script set is unavailable")

    flags_text = _git_output(
        runner,
        root,
        ["ls-files", "-v", "--", "scripts"],
        "repository script index flags",
    )
    seen_flagged_paths: set[str] = set()
    for line in flags_text.splitlines():
        if len(line) < 3:
            continue
        prefix, path = line[:2], line[2:]
        if not path.endswith(".py"):
            continue
        seen_flagged_paths.add(path)
        if prefix != "H ":
            raise RuntimeError(f"repository script has hidden index state: {path}")
    if seen_flagged_paths != set(tracked):
        raise RuntimeError("repository script index/tree set mismatch")

    for args, label in (
        (
            ["ls-files", "--others", "--exclude-standard", "--", "scripts"],
            "untracked repository scripts",
        ),
        (
            ["ls-files", "--others", "--ignored", "--exclude-standard", "--", "scripts"],
            "ignored repository scripts",
        ),
    ):
        extra_text = _git_output(runner, root, args, label)
        extras = [
            line
            for line in extra_text.splitlines()
            if line
            and (
                line.endswith((".py", ".pyc", ".so", ".pyd", ".dylib"))
                or "/__pycache__/" in line
            )
        ]
        if extras:
            raise RuntimeError(f"{label} are present")

    repository_module_names: set[str] = set()
    for path, (_mode, expected_blob) in sorted(tracked.items()):
        relative = Path(path)
        if relative.parent != Path("scripts"):
            continue
        candidate = root / relative
        if candidate.is_symlink() or not candidate.is_file():
            raise RuntimeError(f"repository script working-tree path is unsafe: {path}")
        try:
            candidate.resolve().relative_to(scripts)
        except ValueError as exc:
            raise RuntimeError(f"repository script escapes trusted checkout: {path}") from exc
        actual = runner.git(
            ["-C", str(root), "hash-object", "--no-filters", path]
        )
        if actual.returncode != 0 or actual.stdout.strip() != expected_blob:
            raise RuntimeError(f"repository script bytes differ from trusted commit: {path}")
        repository_module_names.add(relative.stem)

    missing = sorted(set(_CONTRACT_MODULE_NAMES) - repository_module_names)
    if missing:
        raise RuntimeError(
            "required repository contract module is not a tracked trusted-commit blob: "
            + ", ".join(missing)
        )
    return repository_module_names


def _load_contracts(
    root: Path,
    runner: ProcessRunner,
    *,
    expected_commit_sha: str | None = None,
    expected_tree_sha: str | None = None,
) -> dict[str, Any]:
    """Load repository contracts only after exact-main and exact-blob trust succeeds."""
    trusted_commit, trusted_tree = _trusted_checkout_identity(
        root,
        runner,
        expected_commit_sha=expected_commit_sha,
        expected_tree_sha=expected_tree_sha,
    )
    repository_module_names = _verified_repository_module_names(
        root,
        runner,
        expected_commit_sha=trusted_commit,
        expected_tree_sha=trusted_tree,
    )
    scripts = (root / "scripts").resolve()

    preloaded = sorted(
        name for name in repository_module_names if name in sys.modules
    )
    if preloaded:
        raise RuntimeError(
            "repository script module loaded before exact-main trust: "
            + ", ".join(preloaded)
        )

    script_text = str(scripts)
    previous_dont_write_bytecode = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
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

        # Recheck the immutable checkout identity and exact script bytes after
        # imports so a moved HEAD or ordinary working-tree change cannot be
        # accepted as authoritative protected-main proof code.
        _verified_repository_module_names(
            root,
            runner,
            expected_commit_sha=trusted_commit,
            expected_tree_sha=trusted_tree,
        )

        return {
            "phase18": loaded["phase18_multi_asset_temporal_evidence"],
            "phase15": loaded["phase15_public_temporal_evidence"],
            "reader": loaded["render_crypto_observation_hour_series"],
            "renderer": loaded["render_phase18_multi_asset_temporal_evidence"],
        }
    finally:
        sys.dont_write_bytecode = previous_dont_write_bytecode
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


def _proof_stop(
    gate: Any,
    *,
    remote: dict[str, Any],
    local: dict[str, Any],
    assertions: list[dict[str, Any]],
    findings: list[dict[str, Any]],
    status: Status,
    finding: str,
    assertion_name: str | None = None,
) -> Evidence:
    stopped_assertions = list(assertions)
    if assertion_name is not None:
        stopped_assertions.append({"name": assertion_name, "holds": False})
    stopped_findings = list(findings) + [{"code": finding}]
    stopped_local = dict(local)
    stopped_local["USEFULNESS_GATE"] = status.value
    return _evidence(
        runtime=gate.runtime,
        remote=remote,
        local=stopped_local,
        status=status,
        complete=False,
        assertions=stopped_assertions,
        findings=stopped_findings,
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
        contracts = _load_contracts(
            root,
            runner,
            expected_commit_sha=main["sha"],
            expected_tree_sha=main["tree_sha"],
        )
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
    local: dict[str, Any] = {}

    try:
        bundle = phase18.build_multi_asset_temporal_evidence(root, commit_sha)
    except Exception:
        return _proof_stop(
            gate,
            remote=remote,
            local=local,
            assertions=assertions,
            findings=findings,
            status=Status.ERROR,
            finding="phase18-materialisation-failed",
            assertion_name="phase18-materialised",
        )
    if bundle is None:
        return _proof_stop(
            gate,
            remote=remote,
            local=local,
            assertions=assertions,
            findings=findings,
            status=Status.INCOMPLETE,
            finding="phase18-evidence-unavailable",
            assertion_name="phase18-materialised",
        )
    assertions.append({"name": "phase18-materialised", "holds": True})

    try:
        validated = phase18.validate_multi_asset_temporal_evidence(root, bundle)
    except Exception:
        local["phase18_replay_validation"] = "ERROR"
        return _proof_stop(
            gate,
            remote=remote,
            local=local,
            assertions=assertions,
            findings=findings,
            status=Status.ERROR,
            finding="phase18-replay-validation-error",
            assertion_name="phase18-replay-validation",
        )
    assertions.append({"name": "phase18-replay-validation", "holds": True})
    local["phase18_replay_validation"] = "PASS"

    try:
        canonical_first = phase18.canonical_bundle_bytes(validated)
    except Exception:
        return _proof_stop(
            gate,
            remote=remote,
            local=local,
            assertions=assertions,
            findings=findings,
            status=Status.ERROR,
            finding="phase18-canonicalisation-failed",
        )
    bundle_sha256 = hashlib.sha256(canonical_first).hexdigest()

    try:
        rebuilt = phase18.build_multi_asset_temporal_evidence(root, commit_sha)
    except Exception:
        return _proof_stop(
            gate,
            remote=remote,
            local=local,
            assertions=assertions,
            findings=findings,
            status=Status.ERROR,
            finding="independent-bundle-reproduction-error",
            assertion_name="independent-bundle-reproduction",
        )
    if rebuilt is None:
        return _proof_stop(
            gate,
            remote=remote,
            local=local,
            assertions=assertions,
            findings=findings,
            status=Status.INCOMPLETE,
            finding="independent-bundle-reproduction-unavailable",
            assertion_name="independent-bundle-reproduction",
        )
    try:
        rebuilt_bytes = phase18.canonical_bundle_bytes(rebuilt)
    except Exception:
        return _proof_stop(
            gate,
            remote=remote,
            local=local,
            assertions=assertions,
            findings=findings,
            status=Status.ERROR,
            finding="independent-bundle-canonicalisation-failed",
            assertion_name="independent-bundle-reproduction",
        )
    rebuild_ok = rebuilt_bytes == canonical_first
    assertions.append({"name": "independent-bundle-reproduction", "holds": rebuild_ok})
    local["independent_bundle_reproduction"] = "PASS" if rebuild_ok else "FAIL"
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

    try:
        phase15_btc = phase15.build_public_temporal_evidence(root, commit_sha)
    except Exception:
        return _proof_stop(
            gate,
            remote=remote,
            local=local,
            assertions=assertions,
            findings=findings,
            status=Status.ERROR,
            finding="phase15-btc-compatibility-error",
            assertion_name="phase15-btc-compatibility",
        )
    if phase15_btc is None:
        return _proof_stop(
            gate,
            remote=remote,
            local=local,
            assertions=assertions,
            findings=findings,
            status=Status.INCOMPLETE,
            finding="phase15-btc-evidence-unavailable",
            assertion_name="phase15-btc-compatibility",
        )
    if not isinstance(series, list) or not series:
        phase15_ok = False
    else:
        try:
            phase15_ok = (
                phase15.canonical_public_evidence_bytes(phase15_btc)
                == phase15.canonical_public_evidence_bytes(series[0])
            )
        except Exception:
            return _proof_stop(
                gate,
                remote=remote,
                local=local,
                assertions=assertions,
                findings=findings,
                status=Status.ERROR,
                finding="phase15-btc-canonicalisation-failed",
                assertion_name="phase15-btc-compatibility",
            )
    assertions.append({"name": "phase15-btc-compatibility", "holds": phase15_ok})
    local["phase15_btc_compatibility"] = "PASS" if phase15_ok else "FAIL"
    if not phase15_ok:
        findings.append({"code": "phase15-btc-compatibility-mismatch"})

    projections: dict[str, dict[str, Any]] = {}
    if order_ok:
        try:
            for member, series_key in zip(series, expected_order):
                projection = reader._reader_projection_for_series(member, series_key)
                if not isinstance(projection, dict):
                    raise RuntimeError("reader projection is not an object")
                pair_count = projection.get("continuous_pair_count")
                value_count = projection.get("value_count")
                if (
                    not isinstance(pair_count, int)
                    or isinstance(pair_count, bool)
                    or pair_count < 0
                    or not isinstance(value_count, int)
                    or isinstance(value_count, bool)
                    or value_count < 0
                ):
                    raise RuntimeError("reader projection counts are invalid")
                projections[series_key] = projection
        except Exception:
            return _proof_stop(
                gate,
                remote=remote,
                local=local,
                assertions=assertions,
                findings=findings,
                status=Status.ERROR,
                finding="phase18-reader-projection-error",
                assertion_name="reader-projection-reused",
            )
        projection_ok = True
    else:
        projection_ok = False
    assertions.append({"name": "reader-projection-reused", "holds": projection_ok})
    if not projection_ok:
        findings.append({"code": "phase18-reader-projection-unavailable"})

    pair_assertions: list[dict[str, Any]] = []
    for series_key in expected_order:
        pair_assertions.append(
            {
                "name": f"{series_key}-continuous-pair-available",
                "holds": (
                    projection_ok
                    and projections[series_key]["continuous_pair_count"] > 0
                ),
            }
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

    try:
        render_first = renderer.render_multi_asset_temporal_evidence(root, validated)
        render_second = renderer.render_multi_asset_temporal_evidence(root, validated)
        if not isinstance(render_first, str) or not isinstance(render_second, str):
            raise RuntimeError("renderer output is not text")
        renderer_sha256_first = hashlib.sha256(render_first.encode("utf-8")).hexdigest()
        renderer_sha256_second = hashlib.sha256(render_second.encode("utf-8")).hexdigest()
    except Exception:
        return _proof_stop(
            gate,
            remote=remote,
            local=local,
            assertions=assertions,
            findings=findings,
            status=Status.ERROR,
            finding="phase18-renderer-execution-error",
            assertion_name="renderer-deterministic",
        )

    renderer_deterministic = renderer_sha256_first == renderer_sha256_second
    assertions.append({"name": "renderer-deterministic", "holds": renderer_deterministic})
    if not renderer_deterministic:
        findings.append({"code": "phase18-renderer-not-deterministic"})

    mandatory_holds = all(item["holds"] for item in assertions[len(gate.assertions):])
    status = Status.PASS if mandatory_holds else Status.FAIL

    window = validated.get("window") if isinstance(validated, dict) else {}
    local.update(
        {
            "phase18_contract": getattr(phase18, "PHASE18_CONTRACT_VERSION", None),
            "bundle_id": validated.get("bundle_id") if isinstance(validated, dict) else None,
            "bundle_canonical_identity_or_sha256": bundle_sha256,
            "window_start_utc": window.get("start_utc") if isinstance(window, dict) else None,
            "window_end_utc": window.get("end_utc") if isinstance(window, dict) else None,
            "series_order": list(actual_order),
            "renderer_sha256_first": renderer_sha256_first,
            "renderer_sha256_second": renderer_sha256_second,
            "renderer_deterministic": renderer_deterministic,
            "USEFULNESS_GATE": status.value,
        }
    )
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
