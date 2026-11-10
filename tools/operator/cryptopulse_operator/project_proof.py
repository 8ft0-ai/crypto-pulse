"""Project-specific read-only proof helpers for operator-toolkit/v1 Slice D."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import tomllib
from typing import Any

from .evidence import Status
from .github_read import GitHubReader, GitHubReadError
from .redact import contains_sensitive_text


class ProjectProofError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProjectProofResult:
    data: dict[str, Any]
    status: Status
    complete: bool
    assertions: tuple[dict[str, Any], ...] = ()
    findings: tuple[dict[str, Any], ...] = ()


EXPECTED_CONTRACTS = (
    "deterministic-site-publication/v3",
    "phase15-public-temporal-evidence/v1",
    "reader-facing-evidence-experience/v1",
    "operator-toolkit/v1",
)
EXPECTED_BOUNDARIES = {
    "publication_authority": "main only",
    "publication_activation_expectation": "absent/disabled",
    "pages_workflow_name": "Publish CryptoPulse Pages",
    "pages_workflow_path": ".github/workflows/pages.yml",
    "live_workflow_name": "Verify CryptoPulse Live Pages",
    "live_workflow_path": ".github/workflows/verify-live-pages.yml",
    "live_evidence_artifact": "cryptopulse-live-site-evidence",
    "public_base_url": "https://8ft0-ai.github.io/crypto-pulse/",
}
_CONFIG_STRINGS = (
    "pages_workflow_name",
    "pages_workflow_path",
    "pages_workflow_file",
    "pages_build_job",
    "pages_deploy_job",
    "live_workflow_name",
    "live_workflow_path",
    "live_workflow_file",
    "live_verify_job",
    "live_evidence_artifact",
    "public_base_url",
    "publication_authority",
    "publication_activation_expectation",
)
_SHA_RE = re.compile(r"^[0-9a-fA-F]{40}$")
_COMPARE_FILE_LIMIT = 300


def _safe_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or any(ord(ch) < 32 for ch in value):
        raise ProjectProofError(f"{label} is not a non-empty printable string")
    if contains_sensitive_text(value):
        raise ProjectProofError(f"{label} contains sensitive-looking text")
    return value


def _string_list(value: Any, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise ProjectProofError(f"{label} is not a non-empty array")
    result = tuple(_safe_string(item, f"{label} item") for item in value)
    if len(set(result)) != len(result):
        raise ProjectProofError(f"{label} contains duplicates")
    return result


def load_config() -> dict[str, Any]:
    path = Path(__file__).resolve().parents[1] / "operator.toml"
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ProjectProofError("unable to read trusted Slice D configuration") from exc
    config: dict[str, Any] = {}
    for key in _CONFIG_STRINGS:
        config[key] = _safe_string(raw.get(key), f"trusted Slice D configuration field {key}")
    config["pages_trigger_paths"] = _string_list(raw.get("pages_trigger_paths"), "pages_trigger_paths")
    config["project_contracts"] = _string_list(raw.get("project_contracts"), "project_contracts")
    if config["project_contracts"] != EXPECTED_CONTRACTS:
        raise ProjectProofError("trusted Slice D contract index differs from the reviewed contract set")
    for key, expected in EXPECTED_BOUNDARIES.items():
        if config[key] != expected:
            raise ProjectProofError(f"trusted Slice D boundary {key} differs from the reviewed value")
    if config["pages_workflow_file"] != Path(config["pages_workflow_path"]).name:
        raise ProjectProofError("Pages workflow file/path configuration mismatch")
    if config["live_workflow_file"] != Path(config["live_workflow_path"]).name:
        raise ProjectProofError("live workflow file/path configuration mismatch")
    return config


def _dict(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ProjectProofError(f"{label} is not an object")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ProjectProofError(f"{label} is not an array")
    return value


def _string(value: Any, label: str, *, allow_none: bool = False) -> str | None:
    if value is None and allow_none:
        return None
    return _safe_string(value, label)


def _int(value: Any, label: str, *, positive: bool = False, allow_none: bool = False) -> int | None:
    if value is None and allow_none:
        return None
    if not isinstance(value, int) or isinstance(value, bool):
        raise ProjectProofError(f"{label} is not an integer")
    if positive and value <= 0:
        raise ProjectProofError(f"{label} is not a positive integer")
    return value


def _bool(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise ProjectProofError(f"{label} is not boolean")
    return value


def _git_oid(value: Any, label: str) -> str:
    text = _string(value, label)
    assert text is not None
    if not _SHA_RE.fullmatch(text):
        raise ProjectProofError(f"{label} is not a full Git object id")
    return text.lower()


def _run_rank(run: dict[str, Any]) -> tuple[int, int, int]:
    return (run["run_number"], run["run_attempt"], run["id"])


def _workflow_run(raw: Any, label: str) -> dict[str, Any]:
    run = _dict(raw, label)
    return {
        "id": _int(run.get("id"), f"{label} id", positive=True),
        "run_number": _int(run.get("run_number"), f"{label} run_number", positive=True),
        "run_attempt": _int(run.get("run_attempt"), f"{label} run_attempt", positive=True),
        "name": _string(run.get("name"), f"{label} name"),
        "path": _string(run.get("path"), f"{label} path"),
        "event": _string(run.get("event"), f"{label} event"),
        "status": _string(run.get("status"), f"{label} status"),
        "conclusion": _string(run.get("conclusion"), f"{label} conclusion", allow_none=True),
        "head_branch": _string(run.get("head_branch"), f"{label} head_branch", allow_none=True),
        "head_sha": _git_oid(run.get("head_sha"), f"{label} head_sha"),
    }


def _workflow_job(raw: Any, label: str) -> dict[str, Any]:
    job = _dict(raw, label)
    return {
        "id": _int(job.get("id"), f"{label} id", positive=True),
        "name": _string(job.get("name"), f"{label} name"),
        "status": _string(job.get("status"), f"{label} status"),
        "conclusion": _string(job.get("conclusion"), f"{label} conclusion", allow_none=True),
        "run_id": _int(job.get("run_id"), f"{label} run_id", positive=True, allow_none=True),
        "run_attempt": _int(job.get("run_attempt"), f"{label} run_attempt", positive=True, allow_none=True),
    }


def _expected_jobs(github: GitHubReader, run: dict[str, Any], names: tuple[str, ...]) -> tuple[dict[str, dict[str, Any]], Status | None, tuple[dict[str, Any], ...]]:
    try:
        raw_jobs = github.workflow_jobs(run["id"], run["run_attempt"])
        jobs = [_workflow_job(item, f"workflow job {index}") for index, item in enumerate(raw_jobs)]
    except (GitHubReadError, ProjectProofError):
        return {}, Status.INCOMPLETE, ({"code": "workflow-job-evidence-incomplete"},)
    selected: dict[str, dict[str, Any]] = {}
    for name in names:
        matches = [job for job in jobs if job["name"] == name]
        if len(matches) != 1:
            return {}, Status.INCOMPLETE, ({"code": "workflow-job-identity-ambiguous", "job": name},)
        selected[name] = matches[0]
    for name in names:
        job = selected[name]
        if job["run_id"] is not None and job["run_id"] != run["id"]:
            return selected, Status.INCOMPLETE, ({"code": "workflow-job-run-binding-incomplete", "job": name},)
        if job["run_attempt"] is not None and job["run_attempt"] != run["run_attempt"]:
            return selected, Status.INCOMPLETE, ({"code": "workflow-job-attempt-binding-incomplete", "job": name},)
        if job["status"] != "completed":
            return selected, Status.INCOMPLETE, ({"code": "workflow-job-not-complete", "job": name},)
        if job["conclusion"] != "success":
            return selected, Status.FAIL, ({"code": "workflow-job-failed", "job": name, "conclusion": job["conclusion"]},)
    return selected, None, ()


def _glob_regex(pattern: str) -> re.Pattern[str]:
    pieces: list[str] = ["^"]
    index = 0
    while index < len(pattern):
        char = pattern[index]
        if char == "*":
            if index + 1 < len(pattern) and pattern[index + 1] == "*":
                if index + 2 < len(pattern) and pattern[index + 2] == "/":
                    pieces.append("(?:.*/)?")
                    index += 3
                else:
                    pieces.append(".*")
                    index += 2
            else:
                pieces.append("[^/]*")
                index += 1
        elif char == "?":
            pieces.append("[^/]")
            index += 1
        else:
            pieces.append(re.escape(char))
            index += 1
    pieces.append("$")
    return re.compile("".join(pieces))


def path_triggers_pages(path: str, patterns: tuple[str, ...]) -> bool:
    return any(_glob_regex(pattern).fullmatch(path) is not None for pattern in patterns)


def _publication_relation(github: GitHubReader, deployment_sha: str, main_sha: str, trigger_paths: tuple[str, ...]) -> ProjectProofResult:
    if deployment_sha == main_sha:
        return ProjectProofResult(data={"relation": "current-main", "intervening_paths": [], "triggering_paths": []}, status=Status.PASS, complete=True, assertions=({"name": "pages-deployment-publication-equivalent-current-main", "holds": True},))
    try:
        comparison = _dict(github.compare_commits(deployment_sha, main_sha), "commit comparison")
        status = _string(comparison.get("status"), "commit comparison status")
        base = _dict(comparison.get("base_commit"), "commit comparison base")
        merge_base = _dict(comparison.get("merge_base_commit"), "commit comparison merge base")
        base_sha = _git_oid(base.get("sha"), "commit comparison base SHA")
        merge_base_sha = _git_oid(merge_base.get("sha"), "commit comparison merge-base SHA")
        ahead_by = _int(comparison.get("ahead_by"), "commit comparison ahead_by")
        behind_by = _int(comparison.get("behind_by"), "commit comparison behind_by")
        total_commits = _int(comparison.get("total_commits"), "commit comparison total_commits")
        commits_raw = _list(comparison.get("commits"), "commit comparison commits")
        files_raw = _list(comparison.get("files"), "commit comparison files")
    except (GitHubReadError, ProjectProofError):
        return ProjectProofResult(data={}, status=Status.INCOMPLETE, complete=False, findings=({"code": "pages-compare-evidence-incomplete"},))
    if status != "ahead" or base_sha != deployment_sha or merge_base_sha != deployment_sha or behind_by != 0:
        return ProjectProofResult(data={"relation": "not-ancestor-of-current-main"}, status=Status.FAIL, complete=True, assertions=({"name": "pages-deployment-publication-equivalent-current-main", "holds": False},), findings=({"code": "pages-deployment-not-on-current-main-history"},))
    assert ahead_by is not None and total_commits is not None
    if ahead_by <= 0 or total_commits != ahead_by or len(commits_raw) != ahead_by:
        return ProjectProofResult(data={}, status=Status.INCOMPLETE, complete=False, findings=({"code": "pages-compare-commit-evidence-incomplete"},))
    try:
        commit_shas = [_git_oid(_dict(item, f"comparison commit {index}").get("sha"), f"comparison commit {index} SHA") for index, item in enumerate(commits_raw)]
        paths: list[str] = []
        for index, item in enumerate(files_raw):
            file_data = _dict(item, f"comparison file {index}")
            filename = _string(file_data.get("filename"), f"comparison file {index} path")
            file_status = _string(file_data.get("status"), f"comparison file {index} status")
            assert filename is not None and file_status is not None
            if file_status not in {"added", "removed", "modified", "renamed"}:
                raise ProjectProofError(f"comparison file {index} status is unsupported")
            paths.append(filename)
            if file_status == "renamed":
                previous_filename = _string(file_data.get("previous_filename"), f"comparison file {index} previous path")
                assert previous_filename is not None
                paths.append(previous_filename)
    except ProjectProofError:
        return ProjectProofResult(data={}, status=Status.INCOMPLETE, complete=False, findings=({"code": "pages-compare-file-evidence-incomplete"},))
    if not commit_shas or commit_shas[-1] != main_sha:
        return ProjectProofResult(data={}, status=Status.INCOMPLETE, complete=False, findings=({"code": "pages-compare-head-binding-incomplete"},))
    if len(files_raw) >= _COMPARE_FILE_LIMIT:
        return ProjectProofResult(data={}, status=Status.INCOMPLETE, complete=False, findings=({"code": "pages-compare-file-limit-reached"},))
    triggering = sorted(path for path in paths if path_triggers_pages(path, trigger_paths))
    relation_data = {"relation": "publication-equivalent-ancestor" if not triggering else "pages-affecting-main-ahead", "intervening_paths": sorted(paths), "triggering_paths": triggering}
    if triggering:
        return ProjectProofResult(data=relation_data, status=Status.FAIL, complete=True, assertions=({"name": "pages-deployment-publication-equivalent-current-main", "holds": False},), findings=({"code": "pages-affecting-change-after-deployment", "paths": triggering},))
    return ProjectProofResult(data=relation_data, status=Status.PASS, complete=True, assertions=({"name": "pages-deployment-publication-equivalent-current-main", "holds": True},))


def pages_snapshot(github: GitHubReader, config: dict[str, Any]) -> ProjectProofResult:
    try:
        main = _dict(github.main_branch(), "main branch")
        main_sha = _git_oid(main.get("sha"), "main SHA")
        main_tree = _git_oid(main.get("tree_sha"), "main tree SHA")
        protected = _bool(main.get("protected"), "main protected")
        runs = [_workflow_run(item, f"Pages run {index}") for index, item in enumerate(github.workflow_runs(config["pages_workflow_file"]))]
    except (GitHubReadError, ProjectProofError):
        return ProjectProofResult(data={}, status=Status.INCOMPLETE, complete=False, findings=({"code": "pages-run-enumeration-incomplete"},))
    main_runs = [run for run in runs if run["head_branch"] == "main"]
    main_data = {"sha": main_sha, "tree_sha": main_tree, "protected": protected}
    if not main_runs:
        return ProjectProofResult(data={"main": main_data}, status=Status.INCOMPLETE, complete=False, findings=({"code": "pages-main-run-missing"},))
    run = max(main_runs, key=_run_rank)
    data: dict[str, Any] = {"main": main_data, "workflow": {"name": config["pages_workflow_name"], "path": config["pages_workflow_path"]}, "run": run}
    identity_ok = run["name"] == config["pages_workflow_name"] and run["path"] == config["pages_workflow_path"] and run["event"] in {"push", "workflow_dispatch"}
    assertions: list[dict[str, Any]] = [{"name": "current-main-protected", "holds": protected}, {"name": "pages-workflow-run-identity", "holds": identity_ok}]
    if not protected:
        return ProjectProofResult(data=data, status=Status.FAIL, complete=True, assertions=tuple(assertions), findings=({"code": "current-main-not-protected"},))
    if not identity_ok:
        return ProjectProofResult(data=data, status=Status.INCOMPLETE, complete=False, assertions=tuple(assertions), findings=({"code": "pages-workflow-run-identity-incomplete"},))
    if run["status"] != "completed":
        return ProjectProofResult(data=data, status=Status.INCOMPLETE, complete=False, assertions=tuple(assertions), findings=({"code": "pages-run-not-complete"},))
    run_success = run["conclusion"] == "success"
    assertions.append({"name": "pages-run-completed-successfully", "holds": run_success})
    if not run_success:
        return ProjectProofResult(data=data, status=Status.FAIL, complete=True, assertions=tuple(assertions), findings=({"code": "pages-run-failed", "conclusion": run["conclusion"]},))
    jobs, job_status, job_findings = _expected_jobs(github, run, (config["pages_build_job"], config["pages_deploy_job"]))
    if jobs:
        data["jobs"] = jobs
    if job_status is not None:
        return ProjectProofResult(data=data, status=job_status, complete=job_status is Status.FAIL, assertions=tuple(assertions), findings=job_findings)
    assertions.extend(({"name": "pages-build-job-success", "holds": True}, {"name": "pages-deploy-job-success", "holds": True}))
    relation = _publication_relation(github, run["head_sha"], main_sha, config["pages_trigger_paths"])
    data["publication_relation"] = relation.data
    return ProjectProofResult(data=data, status=relation.status, complete=relation.complete, assertions=tuple(assertions) + relation.assertions, findings=relation.findings)


def _artifact(raw: Any, label: str) -> dict[str, Any]:
    artifact = _dict(raw, label)
    workflow = _dict(artifact.get("workflow_run"), f"{label} workflow_run")
    size = _int(artifact.get("size_in_bytes"), f"{label} size_in_bytes")
    assert size is not None
    if size < 0:
        raise ProjectProofError(f"{label} size_in_bytes is negative")
    return {"id": _int(artifact.get("id"), f"{label} id", positive=True), "name": _string(artifact.get("name"), f"{label} name"), "expired": _bool(artifact.get("expired"), f"{label} expired"), "size_in_bytes": size, "created_at": _string(artifact.get("created_at"), f"{label} created_at"), "expires_at": _string(artifact.get("expires_at"), f"{label} expires_at"), "workflow_run_id": _int(workflow.get("id"), f"{label} workflow_run id", positive=True), "workflow_head_sha": _git_oid(workflow.get("head_sha"), f"{label} workflow_run head_sha")}


def live_snapshot(github: GitHubReader, config: dict[str, Any], *, pages: ProjectProofResult | None = None) -> ProjectProofResult:
    pages_result = pages if pages is not None else pages_snapshot(github, config)
    if pages_result.status is not Status.PASS:
        return ProjectProofResult(data={"pages": pages_result.data}, status=pages_result.status, complete=pages_result.complete, assertions=pages_result.assertions, findings=pages_result.findings)
    deployment_sha = pages_result.data["run"]["head_sha"]
    try:
        runs = [_workflow_run(item, f"live run {index}") for index, item in enumerate(github.workflow_runs(config["live_workflow_file"]))]
    except (GitHubReadError, ProjectProofError):
        return ProjectProofResult(data={"deployment_sha": deployment_sha}, status=Status.INCOMPLETE, complete=False, findings=({"code": "live-run-enumeration-incomplete"},))

    dispatch_runs = [run for run in runs if run["event"] == "workflow_dispatch" and run["head_sha"] == deployment_sha]
    if not dispatch_runs:
        workflow_run_seen = any(run["event"] == "workflow_run" for run in runs)
        finding = "live-workflow-run-source-binding-unavailable" if workflow_run_seen else "exact-bound-live-run-missing"
        return ProjectProofResult(
            data={"deployment_sha": deployment_sha},
            status=Status.INCOMPLETE,
            complete=False,
            findings=({"code": finding},),
        )

    run = max(dispatch_runs, key=_run_rank)
    data: dict[str, Any] = {"deployment_sha": deployment_sha, "workflow": {"name": config["live_workflow_name"], "path": config["live_workflow_path"]}, "run": run}
    identity_ok = run["name"] == config["live_workflow_name"] and run["path"] == config["live_workflow_path"] and run["event"] == "workflow_dispatch"
    assertions: list[dict[str, Any]] = [{"name": "live-workflow-run-identity", "holds": identity_ok}, {"name": "live-run-bound-to-pages-deployment", "holds": run["head_sha"] == deployment_sha}]
    if not identity_ok:
        return ProjectProofResult(data=data, status=Status.INCOMPLETE, complete=False, assertions=tuple(assertions), findings=({"code": "live-workflow-run-identity-incomplete"},))
    if run["status"] != "completed":
        return ProjectProofResult(data=data, status=Status.INCOMPLETE, complete=False, assertions=tuple(assertions), findings=({"code": "live-run-not-complete"},))
    run_success = run["conclusion"] == "success"
    assertions.append({"name": "live-run-completed-successfully", "holds": run_success})
    if not run_success:
        return ProjectProofResult(data=data, status=Status.FAIL, complete=True, assertions=tuple(assertions), findings=({"code": "live-run-failed", "conclusion": run["conclusion"]},))
    jobs, job_status, job_findings = _expected_jobs(github, run, (config["live_verify_job"],))
    if jobs:
        data["jobs"] = jobs
    if job_status is not None:
        return ProjectProofResult(data=data, status=job_status, complete=job_status is Status.FAIL, assertions=tuple(assertions), findings=job_findings)
    assertions.append({"name": "live-verify-job-success", "holds": True})
    try:
        artifacts = [_artifact(item, f"live artifact {index}") for index, item in enumerate(github.workflow_artifacts(run["id"]))]
    except (GitHubReadError, ProjectProofError):
        return ProjectProofResult(data=data, status=Status.INCOMPLETE, complete=False, assertions=tuple(assertions), findings=({"code": "live-artifact-enumeration-incomplete"},))
    expected = [item for item in artifacts if item["name"] == config["live_evidence_artifact"]]
    if len(expected) != 1:
        return ProjectProofResult(data=data, status=Status.INCOMPLETE, complete=False, assertions=tuple(assertions), findings=({"code": "live-evidence-artifact-ambiguous", "count": len(expected)},))
    artifact = expected[0]
    data["artifact"] = artifact
    if artifact["workflow_run_id"] != run["id"] or artifact["workflow_head_sha"] != run["head_sha"]:
        return ProjectProofResult(data=data, status=Status.INCOMPLETE, complete=False, assertions=tuple(assertions), findings=({"code": "live-evidence-artifact-run-binding-incomplete"},))
    if artifact["expired"]:
        return ProjectProofResult(data=data, status=Status.INCOMPLETE, complete=False, assertions=tuple(assertions), findings=({"code": "live-evidence-artifact-expired"},))
    assertions.append({"name": "live-evidence-artifact-retained", "holds": True})
    return ProjectProofResult(data=data, status=Status.PASS, complete=True, assertions=tuple(assertions))


def provenance_snapshot(github: GitHubReader, config: dict[str, Any]) -> ProjectProofResult:
    pages = pages_snapshot(github, config)
    if pages.status is not Status.PASS:
        return ProjectProofResult(data={"pages": pages.data}, status=pages.status, complete=pages.complete, assertions=pages.assertions, findings=pages.findings)
    live = live_snapshot(github, config, pages=pages)
    data = {"main": pages.data["main"], "pages": {"run": pages.data["run"], "publication_relation": pages.data["publication_relation"]}, "live": live.data}
    return ProjectProofResult(data=data, status=live.status, complete=live.complete, assertions=pages.assertions + live.assertions, findings=pages.findings + live.findings)


def contracts_snapshot(config: dict[str, Any]) -> ProjectProofResult:
    boundaries = {"publication_authority": config["publication_authority"], "publication_activation_expectation": config["publication_activation_expectation"], "pages_workflow": {"name": config["pages_workflow_name"], "path": config["pages_workflow_path"]}, "live_verification_workflow": {"name": config["live_workflow_name"], "path": config["live_workflow_path"]}, "live_evidence_artifact": config["live_evidence_artifact"], "public_base_url": config["public_base_url"]}
    contracts_ok = tuple(config["project_contracts"]) == EXPECTED_CONTRACTS
    boundaries_ok = all(config[key] == value for key, value in EXPECTED_BOUNDARIES.items())
    return ProjectProofResult(data={"contracts": list(config["project_contracts"]), "boundaries": boundaries, "pages_trigger_paths": list(config["pages_trigger_paths"])}, status=Status.PASS if contracts_ok and boundaries_ok else Status.FAIL, complete=True, assertions=({"name": "project-contract-index-reviewed", "holds": contracts_ok}, {"name": "project-operational-boundaries-reviewed", "holds": boundaries_ok}), findings=() if contracts_ok and boundaries_ok else ({"code": "project-contract-index-drift"},))
