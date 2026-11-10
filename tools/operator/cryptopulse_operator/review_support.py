"""Trusted typed extraction and aggregation for operator-toolkit/v1 Slice B."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from .evidence import Status
from .github_read import GitHubReader, REPOSITORY
from .process import ProcessRunner
from .redact import contains_sensitive_text
from .runtime import inspect_runtime, RuntimeIdentityError


BODY_LIMIT = 8192
GLOBAL_BODY_LIMIT = 65536
FAILURE_CONTEXT_LIMIT = 64

_ACTIONS_RUN_URL = re.compile(
    r"^https://github\.com/8ft0-ai/crypto-pulse/actions/runs/(?P<run_id>[1-9][0-9]*)(?:/.*)?$"
)


class ReviewSupportError(RuntimeError):
    pass


@dataclass(frozen=True)
class SupportResult:
    data: dict[str, Any]
    complete: bool
    findings: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True)
class RuntimeGate:
    runtime: dict[str, Any]
    status: Status | None
    complete: bool
    findings: tuple[dict[str, Any], ...]
    assertions: tuple[dict[str, Any], ...]


class TextBudget:
    def __init__(self, *, per_body: int = BODY_LIMIT, total: int = GLOBAL_BODY_LIMIT) -> None:
        self.per_body = per_body
        self.remaining = total
        self.findings: list[dict[str, Any]] = []

    @property
    def complete(self) -> bool:
        return not self.findings

    def body(self, value: Any, *, kind: str, object_id: Any) -> tuple[str | None, str]:
        if value is None or value == "":
            return None, "empty"
        if not isinstance(value, str):
            self.findings.append({"code": "unsafe-comment-body", "kind": kind, "id": object_id})
            return None, "invalid"
        if len(value) > self.per_body:
            self.findings.append({"code": "comment-body-over-budget", "kind": kind, "id": object_id})
            return None, "over-budget"
        if len(value) > self.remaining:
            self.findings.append({"code": "comment-evidence-budget-exhausted", "kind": kind, "id": object_id})
            return None, "global-budget"
        if contains_sensitive_text(value):
            self.findings.append({"code": "sensitive-comment-body-rejected", "kind": kind, "id": object_id})
            return None, "sensitive"
        self.remaining -= len(value)
        return value, "included"


def _dict(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ReviewSupportError(f"{label} is not an object")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ReviewSupportError(f"{label} is not an array")
    return value


def _str(value: Any, label: str, *, allow_none: bool = False) -> str | None:
    if value is None and allow_none:
        return None
    if not isinstance(value, str):
        raise ReviewSupportError(f"{label} is not a string")
    if contains_sensitive_text(value):
        raise ReviewSupportError(f"{label} contains sensitive-looking text")
    return value


def _int(value: Any, label: str, *, allow_none: bool = False) -> int | None:
    if value is None and allow_none:
        return None
    if not isinstance(value, int) or isinstance(value, bool):
        raise ReviewSupportError(f"{label} is not an integer")
    return value


def _bool(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise ReviewSupportError(f"{label} is not boolean")
    return value


def _optional_bool(value: Any, label: str) -> bool | None:
    if value is None:
        return None
    return _bool(value, label)


def _body_record(budget: TextBudget, item: dict[str, Any], *, kind: str) -> dict[str, Any]:
    object_id = item.get("id")
    body, state = budget.body(item.get("body"), kind=kind, object_id=object_id)
    return {"body": body, "body_state": state}


def _protected_main(value: Any) -> dict[str, Any]:
    main = _dict(value, "main branch")
    required_checks_raw = _list(main.get("required_checks"), "main required checks")
    required_checks: list[dict[str, Any]] = []
    for index, item in enumerate(required_checks_raw):
        check = _dict(item, f"main required check {index}")
        required_checks.append(
            {
                "context": _str(check.get("context"), f"main required check {index} context"),
                "app_id": _int(check.get("app_id"), f"main required check {index} app id", allow_none=True),
            }
        )
    return {
        "sha": _str(main.get("sha"), "main SHA"),
        "tree_sha": _str(main.get("tree_sha"), "main tree SHA"),
        "protected": _bool(main.get("protected"), "main protected"),
        "required_checks": required_checks,
    }


def runtime_gate(runner: ProcessRunner, github: GitHubReader) -> RuntimeGate:
    assertions: list[dict[str, Any]] = []
    tools = {name: runner.has_executable(name) for name in ("git", "gh")}
    auth_ok = bool(tools["gh"] and github.auth_ok())
    assertions.extend(
        [
            {"name": "git-present", "holds": tools["git"]},
            {"name": "gh-present", "holds": tools["gh"]},
            {"name": "gh-authenticated-read", "holds": auth_ok},
        ]
    )
    if not all(tools.values()) or not auth_ok:
        return RuntimeGate(
            runtime={"repository": REPOSITORY, "clean": False, "provenance": None},
            status=Status.ERROR,
            complete=False,
            findings=({"code": "prerequisite-or-authentication-failure"},),
            assertions=tuple(assertions),
        )
    try:
        runtime = inspect_runtime(runner, github)
    except RuntimeIdentityError:
        return RuntimeGate(
            runtime={"repository": REPOSITORY, "clean": False, "provenance": None},
            status=Status.ERROR,
            complete=False,
            findings=({"code": "runtime-identity-error"},),
            assertions=tuple(assertions),
        )
    if not runtime.complete:
        return RuntimeGate(
            runtime=runtime.identity,
            status=Status.INCOMPLETE,
            complete=False,
            findings=({"code": runtime.reason or "runtime-incomplete"},),
            assertions=tuple(assertions),
        )
    if not runtime.trusted:
        return RuntimeGate(
            runtime=runtime.identity,
            status=Status.ERROR,
            complete=True,
            findings=({"code": runtime.reason or "runtime-untrusted"},),
            assertions=tuple(assertions),
        )
    return RuntimeGate(runtime=runtime.identity, status=None, complete=True, findings=(), assertions=tuple(assertions))


def candidate_snapshot(pr_number: int, github: GitHubReader) -> SupportResult:
    budget = TextBudget()
    findings: list[dict[str, Any]] = []

    pr = _dict(github.pull_request(pr_number), "pull request")
    base = _dict(pr.get("base"), "pull request base")
    head = _dict(pr.get("head"), "pull request head")
    base_sha = _str(base.get("sha"), "base SHA")
    head_sha = _str(head.get("sha"), "head SHA")
    commits_total = _int(pr.get("commits"), "pull request commit count")
    files_total = _int(pr.get("changed_files"), "pull request changed-file count")
    mergeable = _optional_bool(pr.get("mergeable"), "pull request mergeable state")
    if mergeable is None:
        findings.append({"code": "pull-request-mergeability-pending"})
    protected_main = _protected_main(github.main_branch())

    head_commit = _dict(github.commit(head_sha), "head commit")
    head_git_commit = _dict(head_commit.get("commit"), "head Git commit")
    head_tree = _dict(head_git_commit.get("tree"), "head commit tree")
    parents = _list(head_commit.get("parents"), "head commit parents")
    if head_commit.get("sha") != head_sha:
        findings.append({"code": "head-commit-sha-mismatch"})

    commits_raw = github.pull_commits(pr_number, expected_total=commits_total)
    commits: list[dict[str, Any]] = []
    for index, item in enumerate(commits_raw):
        commit = _dict(item, f"PR commit {index}")
        git_commit = _dict(commit.get("commit"), f"PR commit {index} Git object")
        tree = _dict(git_commit.get("tree"), f"PR commit {index} tree")
        commit_parents = _list(commit.get("parents"), f"PR commit {index} parents")
        commits.append(
            {
                "sha": _str(commit.get("sha"), f"PR commit {index} SHA"),
                "tree_sha": _str(tree.get("sha"), f"PR commit {index} tree SHA"),
                "parents": [
                    _str(_dict(parent, f"PR commit {index} parent").get("sha"), f"PR commit {index} parent SHA")
                    for parent in commit_parents
                ],
            }
        )

    if commits and commits[-1]["sha"] != head_sha:
        findings.append({"code": "pr-commit-list-head-mismatch"})

    files_raw = github.pull_files(pr_number, expected_total=files_total)
    files: list[dict[str, Any]] = []
    for index, item in enumerate(files_raw):
        file = _dict(item, f"changed file {index}")
        patch = file.get("patch")
        patch_available = isinstance(patch, str)
        if patch is not None and not patch_available:
            findings.append({"code": "changed-file-patch-representation-invalid", "path": file.get("filename")})
        files.append(
            {
                "path": _str(file.get("filename"), f"changed file {index} path"),
                "status": _str(file.get("status"), f"changed file {index} status"),
                "blob_sha": _str(file.get("sha"), f"changed file {index} blob SHA", allow_none=True),
                "additions": _int(file.get("additions"), f"changed file {index} additions"),
                "deletions": _int(file.get("deletions"), f"changed file {index} deletions"),
                "changes": _int(file.get("changes"), f"changed file {index} changes"),
                "patch_available": patch_available,
                "patch_bytes": len(patch.encode("utf-8")) if patch_available else None,
            }
        )

    checks_raw = github.check_runs(head_sha)
    checks: list[dict[str, Any]] = []
    for index, item in enumerate(checks_raw):
        check = _dict(item, f"check run {index}")
        app = check.get("app")
        app_data = app if isinstance(app, dict) else {}
        associations_raw = check.get("pull_requests")
        if associations_raw is None:
            associations_raw = []
        associations: list[dict[str, Any]] = []
        for association_index, association_value in enumerate(_list(associations_raw, f"check run {index} pull requests")):
            association = _dict(association_value, f"check run {index} pull request {association_index}")
            association_base = _dict(association.get("base"), f"check run {index} pull request {association_index} base")
            association_head = _dict(association.get("head"), f"check run {index} pull request {association_index} head")
            associations.append(
                {
                    "number": _int(association.get("number"), f"check run {index} pull request {association_index} number"),
                    "base_sha": _str(association_base.get("sha"), f"check run {index} pull request {association_index} base SHA"),
                    "head_sha": _str(association_head.get("sha"), f"check run {index} pull request {association_index} head SHA"),
                }
            )
        checks.append(
            {
                "id": _int(check.get("id"), f"check run {index} id"),
                "name": _str(check.get("name"), f"check run {index} name"),
                "status": _str(check.get("status"), f"check run {index} status"),
                "conclusion": _str(check.get("conclusion"), f"check run {index} conclusion", allow_none=True),
                "started_at": _str(check.get("started_at"), f"check run {index} started_at", allow_none=True),
                "completed_at": _str(check.get("completed_at"), f"check run {index} completed_at", allow_none=True),
                "details_url": _str(check.get("details_url"), f"check run {index} details URL", allow_none=True),
                "app_id": _int(app_data.get("id"), f"check run {index} app id", allow_none=True),
                "app_slug": _str(app_data.get("slug"), f"check run {index} app slug", allow_none=True),
                "pull_requests": associations,
            }
        )

    reviews_raw = github.pull_reviews(pr_number)
    reviews: list[dict[str, Any]] = []
    for index, item in enumerate(reviews_raw):
        review = _dict(item, f"review {index}")
        user = review.get("user")
        user_data = user if isinstance(user, dict) else {}
        record = {
            "id": _int(review.get("id"), f"review {index} id"),
            "user": _str(user_data.get("login"), f"review {index} user", allow_none=True),
            "state": _str(review.get("state"), f"review {index} state"),
            "commit_id": _str(review.get("commit_id"), f"review {index} commit id", allow_none=True),
            "submitted_at": _str(review.get("submitted_at"), f"review {index} submitted_at", allow_none=True),
        }
        record.update(_body_record(budget, review, kind="review"))
        reviews.append(record)

    issue_comments_raw = github.issue_comments(pr_number)
    issue_comments: list[dict[str, Any]] = []
    for index, item in enumerate(issue_comments_raw):
        comment = _dict(item, f"issue comment {index}")
        user = comment.get("user")
        user_data = user if isinstance(user, dict) else {}
        record = {
            "id": _int(comment.get("id"), f"issue comment {index} id"),
            "user": _str(user_data.get("login"), f"issue comment {index} user", allow_none=True),
            "created_at": _str(comment.get("created_at"), f"issue comment {index} created_at", allow_none=True),
            "updated_at": _str(comment.get("updated_at"), f"issue comment {index} updated_at", allow_none=True),
        }
        record.update(_body_record(budget, comment, kind="issue-comment"))
        issue_comments.append(record)

    review_comments_raw = github.review_comments(pr_number)
    review_comments: list[dict[str, Any]] = []
    review_comment_by_id: dict[int, dict[str, Any]] = {}
    for index, item in enumerate(review_comments_raw):
        comment = _dict(item, f"review comment {index}")
        user = comment.get("user")
        user_data = user if isinstance(user, dict) else {}
        comment_id = _int(comment.get("id"), f"review comment {index} id")
        record = {
            "id": comment_id,
            "user": _str(user_data.get("login"), f"review comment {index} user", allow_none=True),
            "review_id": _int(comment.get("pull_request_review_id"), f"review comment {index} review id", allow_none=True),
            "in_reply_to_id": _int(comment.get("in_reply_to_id"), f"review comment {index} reply id", allow_none=True),
            "commit_id": _str(comment.get("commit_id"), f"review comment {index} commit id", allow_none=True),
            "path": _str(comment.get("path"), f"review comment {index} path", allow_none=True),
            "line": _int(comment.get("line"), f"review comment {index} line", allow_none=True),
            "start_line": _int(comment.get("start_line"), f"review comment {index} start line", allow_none=True),
            "side": _str(comment.get("side"), f"review comment {index} side", allow_none=True),
            "position": _int(comment.get("position"), f"review comment {index} position", allow_none=True),
            "original_position": _int(
                comment.get("original_position"),
                f"review comment {index} original position",
                allow_none=True,
            ),
            "created_at": _str(comment.get("created_at"), f"review comment {index} created_at", allow_none=True),
            "updated_at": _str(comment.get("updated_at"), f"review comment {index} updated_at", allow_none=True),
        }
        record.update(_body_record(budget, comment, kind="review-comment"))
        review_comments.append(record)
        review_comment_by_id[comment_id] = record

    threads_raw = github.review_threads(pr_number)
    threads: list[dict[str, Any]] = []
    for index, item in enumerate(threads_raw):
        thread = _dict(item, f"review thread {index}")
        comments_connection = _dict(thread.get("comments"), f"review thread {index} comments")
        thread_comments = _list(comments_connection.get("nodes"), f"review thread {index} comment nodes")
        comments: list[dict[str, Any]] = []
        for comment_index, comment_value in enumerate(thread_comments):
            comment = _dict(comment_value, f"review thread {index} comment {comment_index}")
            database_id = _int(comment.get("databaseId"), f"review thread {index} comment database id")
            if database_id not in review_comment_by_id:
                findings.append({"code": "review-thread-comment-not-in-rest", "id": database_id})
            comments.append(
                {
                    "node_id": _str(comment.get("id"), f"review thread {index} comment node id"),
                    "database_id": database_id,
                }
            )
        threads.append(
            {
                "id": _str(thread.get("id"), f"review thread {index} id"),
                "resolved": _bool(thread.get("isResolved"), f"review thread {index} resolved"),
                "outdated": _bool(thread.get("isOutdated"), f"review thread {index} outdated"),
                "comments": comments,
            }
        )

    findings.extend(budget.findings)
    complete = not findings
    data = {
        "pr_number": pr_number,
        "state": _str(pr.get("state"), "pull request state"),
        "draft": _bool(pr.get("draft"), "pull request draft state"),
        "mergeable": mergeable,
        "merged": _bool(pr.get("merged"), "pull request merged state"),
        "base": {"ref": _str(base.get("ref"), "base ref"), "sha": base_sha},
        "head": {"ref": _str(head.get("ref"), "head ref"), "sha": head_sha},
        "head_commit": {
            "sha": _str(head_commit.get("sha"), "head commit SHA"),
            "tree_sha": _str(head_tree.get("sha"), "head tree SHA"),
            "parents": [
                _str(_dict(parent, "head parent").get("sha"), "head parent SHA")
                for parent in parents
            ],
        },
        "protected_main": protected_main,
        "commits": commits,
        "files": files,
        "checks": checks,
        "reviews": reviews,
        "issue_comments": issue_comments,
        "review_comments": review_comments,
        "review_threads": threads,
    }
    return SupportResult(data=data, complete=complete, findings=tuple(findings))


def ci_snapshot(run_id: int, github: GitHubReader) -> SupportResult:
    findings: list[dict[str, Any]] = []
    run = _dict(github.workflow_run(run_id), "workflow run")
    attempt = _int(run.get("run_attempt"), "workflow run attempt")
    jobs_raw = github.workflow_jobs(run_id, attempt)

    jobs: list[dict[str, Any]] = []
    failure_context: list[dict[str, Any]] = []
    for index, item in enumerate(jobs_raw):
        job = _dict(item, f"workflow job {index}")
        job_id = _int(job.get("id"), f"workflow job {index} id")
        job_name = _str(job.get("name"), f"workflow job {index} name")
        steps_raw = job.get("steps")
        if steps_raw is None:
            steps_raw = []
        steps = _list(steps_raw, f"workflow job {index} steps")
        step_records: list[dict[str, Any]] = []
        for step_index, item_step in enumerate(steps):
            step = _dict(item_step, f"workflow job {index} step {step_index}")
            step_record = {
                "number": _int(step.get("number"), f"workflow job {index} step {step_index} number"),
                "name": _str(step.get("name"), f"workflow job {index} step {step_index} name"),
                "status": _str(step.get("status"), f"workflow job {index} step {step_index} status"),
                "conclusion": _str(
                    step.get("conclusion"),
                    f"workflow job {index} step {step_index} conclusion",
                    allow_none=True,
                ),
                "started_at": _str(
                    step.get("started_at"),
                    f"workflow job {index} step {step_index} started_at",
                    allow_none=True,
                ),
                "completed_at": _str(
                    step.get("completed_at"),
                    f"workflow job {index} step {step_index} completed_at",
                    allow_none=True,
                ),
            }
            step_records.append(step_record)
            if step_record["conclusion"] not in {None, "success", "skipped"}:
                if len(failure_context) >= FAILURE_CONTEXT_LIMIT:
                    findings.append({"code": "failure-context-over-budget"})
                else:
                    failure_context.append(
                        {
                            "job_id": job_id,
                            "job_name": job_name,
                            "step_number": step_record["number"],
                            "step_name": step_record["name"],
                            "conclusion": step_record["conclusion"],
                        }
                    )
        job_record = {
            "id": job_id,
            "name": job_name,
            "status": _str(job.get("status"), f"workflow job {index} status"),
            "conclusion": _str(job.get("conclusion"), f"workflow job {index} conclusion", allow_none=True),
            "started_at": _str(job.get("started_at"), f"workflow job {index} started_at", allow_none=True),
            "completed_at": _str(job.get("completed_at"), f"workflow job {index} completed_at", allow_none=True),
            "steps": step_records,
        }
        jobs.append(job_record)
        if not step_records and job_record["conclusion"] not in {None, "success", "skipped"}:
            if len(failure_context) >= FAILURE_CONTEXT_LIMIT:
                findings.append({"code": "failure-context-over-budget"})
            else:
                failure_context.append(
                    {
                        "job_id": job_id,
                        "job_name": job_name,
                        "step_number": None,
                        "step_name": None,
                        "conclusion": job_record["conclusion"],
                    }
                )

    head_commit = run.get("head_commit")
    head_tree_sha = None
    if isinstance(head_commit, dict):
        tree_id = head_commit.get("tree_id")
        if tree_id is not None:
            head_tree_sha = _str(tree_id, "workflow run head tree SHA")

    pull_requests_raw = run.get("pull_requests")
    if pull_requests_raw is None:
        pull_requests_raw = []
    pull_requests: list[dict[str, Any]] = []
    for association_index, association_value in enumerate(_list(pull_requests_raw, "workflow run pull requests")):
        association = _dict(association_value, f"workflow run pull request {association_index}")
        association_base = _dict(association.get("base"), f"workflow run pull request {association_index} base")
        association_head = _dict(association.get("head"), f"workflow run pull request {association_index} head")
        pull_requests.append(
            {
                "number": _int(association.get("number"), f"workflow run pull request {association_index} number"),
                "base_sha": _str(association_base.get("sha"), f"workflow run pull request {association_index} base SHA"),
                "head_sha": _str(association_head.get("sha"), f"workflow run pull request {association_index} head SHA"),
            }
        )

    data = {
        "run_id": _int(run.get("id"), "workflow run id"),
        "attempt": attempt,
        "name": _str(run.get("name"), "workflow run name"),
        "workflow_id": _int(run.get("workflow_id"), "workflow id"),
        "workflow_path": _str(run.get("path"), "workflow path"),
        "event": _str(run.get("event"), "workflow event"),
        "head_sha": _str(run.get("head_sha"), "workflow head SHA"),
        "head_tree_sha": head_tree_sha,
        "pull_requests": pull_requests,
        "status": _str(run.get("status"), "workflow status"),
        "conclusion": _str(run.get("conclusion"), "workflow conclusion", allow_none=True),
        "created_at": _str(run.get("created_at"), "workflow created_at", allow_none=True),
        "updated_at": _str(run.get("updated_at"), "workflow updated_at", allow_none=True),
        "run_started_at": _str(run.get("run_started_at"), "workflow run_started_at", allow_none=True),
        "jobs": jobs,
        "failure_context": failure_context,
        "logs_emitted": False,
    }
    return SupportResult(data=data, complete=not findings, findings=tuple(findings))


def actions_run_id(details_url: str | None) -> int | None:
    if details_url is None:
        return None
    match = _ACTIONS_RUN_URL.fullmatch(details_url)
    return int(match.group("run_id")) if match else None


def review_pack_snapshot(pr_number: int, github: GitHubReader) -> tuple[SupportResult, Status, tuple[dict[str, Any], ...]]:
    candidate = candidate_snapshot(pr_number, github)
    findings = list(candidate.findings)
    assertions: list[dict[str, Any]] = []

    main = _dict(candidate.data.get("protected_main"), "candidate protected main")
    protected = _bool(main.get("protected"), "main protected")
    assertions.append({"name": "main-protected", "holds": protected})
    if not protected:
        data = {"candidate": candidate.data, "main": main, "required_check": None, "ci": None}
        status = Status.FAIL if candidate.complete else Status.INCOMPLETE
        return SupportResult(data, complete=candidate.complete, findings=tuple(findings)), status, tuple(assertions)

    current_base = (
        candidate.data["base"]["ref"] == "main"
        and candidate.data["base"]["sha"] == _str(main.get("sha"), "main SHA")
    )
    assertions.append({"name": "candidate-base-is-current-main", "holds": current_base})
    if not current_base:
        findings.append({"code": "candidate-base-not-current-main"})
        data = {"candidate": candidate.data, "main": main, "required_check": None, "ci": None}
        return SupportResult(data, complete=False, findings=tuple(findings)), Status.INCOMPLETE, tuple(assertions)

    if not candidate.complete:
        data = {"candidate": candidate.data, "main": main, "required_check": None, "ci": None}
        return SupportResult(data, complete=False, findings=tuple(findings)), Status.INCOMPLETE, tuple(assertions)

    required_checks = _list(main.get("required_checks"), "required checks")
    if len(required_checks) != 1:
        findings.append({"code": "required-check-set-ambiguous"})
        data = {"candidate": candidate.data, "main": main, "required_check": None, "ci": None}
        return SupportResult(data, complete=False, findings=tuple(findings)), Status.INCOMPLETE, tuple(assertions)

    required = _dict(required_checks[0], "required check")
    context = _str(required.get("context"), "required check context")
    app_id = _int(required.get("app_id"), "required check app id")
    matches = [
        item
        for item in candidate.data["checks"]
        if item.get("name") == context and item.get("app_id") == app_id
    ]
    assertions.append({"name": "required-check-context-app-bound", "holds": len(matches) == 1})
    if len(matches) != 1:
        findings.append({"code": "required-check-missing-or-ambiguous"})
        data = {"candidate": candidate.data, "main": main, "required_check": required, "ci": None}
        return SupportResult(data, complete=False, findings=tuple(findings)), Status.INCOMPLETE, tuple(assertions)

    check = matches[0]
    if check.get("status") != "completed":
        findings.append({"code": "required-check-pending"})
        data = {"candidate": candidate.data, "main": main, "required_check": check, "ci": None}
        return SupportResult(data, complete=False, findings=tuple(findings)), Status.INCOMPLETE, tuple(assertions)

    check_conclusion = check.get("conclusion")
    if check_conclusion is None:
        findings.append({"code": "required-check-conclusion-missing"})
        data = {"candidate": candidate.data, "main": main, "required_check": check, "ci": None}
        return SupportResult(data, complete=False, findings=tuple(findings)), Status.INCOMPLETE, tuple(assertions)
    check_success = check_conclusion == "success"
    assertions.append({"name": "required-check-success", "holds": check_success})

    run_id = actions_run_id(check.get("details_url"))
    if run_id is None:
        findings.append({"code": "required-check-actions-run-unbound"})
        data = {"candidate": candidate.data, "main": main, "required_check": check, "ci": None}
        return SupportResult(data, complete=False, findings=tuple(findings)), Status.INCOMPLETE, tuple(assertions)

    ci = ci_snapshot(run_id, github)
    findings.extend(ci.findings)
    exact_head = ci.data["head_sha"] == candidate.data["head"]["sha"]
    assertions.append({"name": "required-ci-exact-head", "holds": exact_head})
    if not exact_head:
        findings.append({"code": "required-ci-head-mismatch"})
        data = {"candidate": candidate.data, "main": main, "required_check": check, "ci": ci.data}
        return SupportResult(data, complete=False, findings=tuple(findings)), Status.INCOMPLETE, tuple(assertions)

    pull_request_event = ci.data.get("event") == "pull_request"
    assertions.append({"name": "required-ci-pull-request-event", "holds": pull_request_event})
    if not pull_request_event:
        findings.append({"code": "required-ci-not-pull-request-event"})
        data = {"candidate": candidate.data, "main": main, "required_check": check, "ci": ci.data}
        return SupportResult(data, complete=False, findings=tuple(findings)), Status.INCOMPLETE, tuple(assertions)

    ci_associations = [
        item
        for item in ci.data.get("pull_requests", [])
        if item.get("number") == pr_number
        and item.get("head_sha") == candidate.data["head"]["sha"]
        and item.get("base_sha") == candidate.data["base"]["sha"]
    ]
    ci_association_bound = len(ci_associations) == 1
    assertions.append({"name": "required-ci-pr-base-head-bound", "holds": ci_association_bound})
    if not ci_association_bound:
        findings.append({"code": "required-ci-pr-binding-missing-or-ambiguous"})
        data = {"candidate": candidate.data, "main": main, "required_check": check, "ci": ci.data}
        return SupportResult(data, complete=False, findings=tuple(findings)), Status.INCOMPLETE, tuple(assertions)

    ci_tree = ci.data.get("head_tree_sha")
    if ci_tree is not None and ci_tree != candidate.data["head_commit"]["tree_sha"]:
        findings.append({"code": "required-ci-tree-mismatch"})
        data = {"candidate": candidate.data, "main": main, "required_check": check, "ci": ci.data}
        return SupportResult(data, complete=False, findings=tuple(findings)), Status.INCOMPLETE, tuple(assertions)

    if ci.data["status"] != "completed" or ci.data["conclusion"] is None:
        findings.append({"code": "required-ci-pending"})
        data = {"candidate": candidate.data, "main": main, "required_check": check, "ci": ci.data}
        return SupportResult(data, complete=False, findings=tuple(findings)), Status.INCOMPLETE, tuple(assertions)

    if not ci.complete:
        data = {"candidate": candidate.data, "main": main, "required_check": check, "ci": ci.data}
        return SupportResult(data, complete=False, findings=tuple(findings)), Status.INCOMPLETE, tuple(assertions)

    ci_conclusion = ci.data["conclusion"]
    ci_success = ci_conclusion == "success"
    assertions.append({"name": "required-ci-success", "holds": ci_success})
    conclusions_consistent = check_conclusion == ci_conclusion
    assertions.append({"name": "required-check-ci-conclusion-consistent", "holds": conclusions_consistent})
    data = {"candidate": candidate.data, "main": main, "required_check": check, "ci": ci.data}
    if not conclusions_consistent:
        findings.append({"code": "required-check-ci-conclusion-mismatch"})
        return SupportResult(data, complete=False, findings=tuple(findings)), Status.INCOMPLETE, tuple(assertions)

    if not check_success:
        return SupportResult(data, complete=candidate.complete and ci.complete, findings=tuple(findings)), Status.FAIL, tuple(assertions)

    complete = candidate.complete and ci.complete and not findings
    if not complete:
        return SupportResult(data, complete=False, findings=tuple(findings)), Status.INCOMPLETE, tuple(assertions)
    return SupportResult(data, complete=True, findings=()), Status.PASS, tuple(assertions)
