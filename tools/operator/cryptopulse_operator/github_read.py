"""Bounded read-only GitHub adapter using authenticated `gh api`."""

from __future__ import annotations

import json
from typing import Any, Iterable

from .process import ProcessRunner


REPOSITORY = "8ft0-ai/crypto-pulse"
_OWNER, _NAME = REPOSITORY.split("/", 1)

_REVIEW_THREADS_QUERY = """
query($owner:String!, $name:String!, $number:Int!, $cursor:String) {
  repository(owner:$owner, name:$name) {
    pullRequest(number:$number) {
      reviewThreads(first:100, after:$cursor) {
        totalCount
        nodes {
          id
          isResolved
          comments(first:100) {
            totalCount
            nodes {
              id
              databaseId
            }
            pageInfo {
              hasNextPage
              endCursor
            }
          }
        }
        pageInfo {
          hasNextPage
          endCursor
        }
      }
    }
  }
}
""".strip()


class GitHubReadError(RuntimeError):
    pass


def _positive_int(value: int, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise GitHubReadError(f"{label} must be a positive integer")
    return value


class GitHubReader:
    def __init__(self, runner: ProcessRunner) -> None:
        self._runner = runner

    def _get(self, endpoint: str) -> Any:
        result = self._runner.gh(["api", "--method", "GET", endpoint])
        if result.returncode != 0:
            raise GitHubReadError("GitHub read failed")
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise GitHubReadError("GitHub returned malformed JSON") from exc

    def _paginated_pages(self, endpoint: str) -> list[Any]:
        result = self._runner.gh(["api", "--method", "GET", "--paginate", "--slurp", endpoint])
        if result.returncode != 0:
            raise GitHubReadError("paginated GitHub read failed before completeness could be proved")
        try:
            pages = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise GitHubReadError("GitHub returned malformed paginated JSON") from exc
        if not isinstance(pages, list):
            raise GitHubReadError("paginated GitHub response is not an array of pages")
        return pages

    def auth_ok(self) -> bool:
        result = self._runner.gh(["auth", "status", "--hostname", "github.com"])
        return result.returncode == 0

    def collection(self, endpoint: str, *, expected_total: int | None = None) -> list[Any]:
        return flatten_pages(self._paginated_pages(endpoint), expected_total=expected_total)

    def keyed_collection(
        self,
        endpoint: str,
        *,
        item_key: str,
        total_key: str = "total_count",
        expected_total: int | None = None,
    ) -> list[Any]:
        pages = self._paginated_pages(endpoint)
        items: list[Any] = []
        reported_total: int | None = None
        for page in pages:
            if not isinstance(page, dict):
                raise GitHubReadError("paginated keyed response page is not an object")
            page_items = page.get(item_key)
            if not isinstance(page_items, list):
                raise GitHubReadError("paginated keyed response is missing its item array")
            total = page.get(total_key)
            if not isinstance(total, int) or isinstance(total, bool) or total < 0:
                raise GitHubReadError("paginated keyed response has an invalid total count")
            if reported_total is None:
                reported_total = total
            elif total != reported_total:
                raise GitHubReadError("paginated keyed response total changed between pages")
            items.extend(page_items)
        if reported_total is None:
            raise GitHubReadError("paginated keyed response is empty")
        required_total = expected_total if expected_total is not None else reported_total
        if reported_total != required_total or len(items) != required_total:
            raise GitHubReadError("paginated keyed response count mismatch")
        return items

    def main_branch(self) -> dict[str, Any]:
        data = self._get(f"repos/{REPOSITORY}/branches/main")
        try:
            commit = data["commit"]
            sha = commit["sha"]
            tree_sha = commit["commit"]["tree"]["sha"]
            protected = bool(data["protected"])
        except (KeyError, TypeError) as exc:
            raise GitHubReadError("GitHub main-branch representation is incomplete") from exc
        protection = data.get("protection") or {}
        checks = (protection.get("required_status_checks") or {}).get("checks") or []
        if not isinstance(checks, list) or any(not isinstance(item, dict) for item in checks):
            raise GitHubReadError("GitHub main-branch required-check representation is incomplete")
        required_checks = []
        for item in checks:
            context = item.get("context")
            app_id = item.get("app_id")
            if not isinstance(context, str) or not context:
                raise GitHubReadError("GitHub main-branch required-check context is incomplete")
            if app_id is not None and (not isinstance(app_id, int) or isinstance(app_id, bool)):
                raise GitHubReadError("GitHub main-branch required-check app binding is incomplete")
            required_checks.append({"context": context, "app_id": app_id})
        return {
            "sha": sha,
            "tree_sha": tree_sha,
            "protected": protected,
            "required_checks": required_checks,
        }

    def runtime_provenance(self, runtime_sha: str, main_sha: str) -> str:
        data = self._get(f"repos/{REPOSITORY}/compare/{runtime_sha}...{main_sha}")
        status = data.get("status") if isinstance(data, dict) else None
        if status == "identical":
            return "current-main"
        if status == "ahead":
            return "ancestor-of-current-main"
        if status in {"behind", "diverged"}:
            return "not-on-current-main-history"
        raise GitHubReadError("GitHub compare representation is incomplete")

    def pull_request(self, pr_number: int) -> dict[str, Any]:
        _positive_int(pr_number, "PR number")
        data = self._get(f"repos/{REPOSITORY}/pulls/{pr_number}")
        if not isinstance(data, dict):
            raise GitHubReadError("pull request representation is incomplete")
        return data

    def commit(self, sha: str) -> dict[str, Any]:
        if not isinstance(sha, str) or len(sha) != 40 or any(ch not in "0123456789abcdefABCDEF" for ch in sha):
            raise GitHubReadError("commit SHA is invalid")
        data = self._get(f"repos/{REPOSITORY}/commits/{sha}")
        if not isinstance(data, dict):
            raise GitHubReadError("commit representation is incomplete")
        return data

    def pull_commits(self, pr_number: int, *, expected_total: int) -> list[Any]:
        _positive_int(pr_number, "PR number")
        return self.collection(f"repos/{REPOSITORY}/pulls/{pr_number}/commits", expected_total=expected_total)

    def pull_files(self, pr_number: int, *, expected_total: int) -> list[Any]:
        _positive_int(pr_number, "PR number")
        return self.collection(f"repos/{REPOSITORY}/pulls/{pr_number}/files", expected_total=expected_total)

    def check_runs(self, sha: str) -> list[Any]:
        if not isinstance(sha, str) or len(sha) != 40 or any(ch not in "0123456789abcdefABCDEF" for ch in sha):
            raise GitHubReadError("check-run SHA is invalid")
        return self.keyed_collection(f"repos/{REPOSITORY}/commits/{sha}/check-runs", item_key="check_runs")

    def pull_reviews(self, pr_number: int) -> list[Any]:
        _positive_int(pr_number, "PR number")
        return self.collection(f"repos/{REPOSITORY}/pulls/{pr_number}/reviews")

    def issue_comments(self, issue_number: int) -> list[Any]:
        _positive_int(issue_number, "issue number")
        return self.collection(f"repos/{REPOSITORY}/issues/{issue_number}/comments")

    def review_comments(self, pr_number: int) -> list[Any]:
        _positive_int(pr_number, "PR number")
        return self.collection(f"repos/{REPOSITORY}/pulls/{pr_number}/comments")

    def review_threads(self, pr_number: int) -> list[dict[str, Any]]:
        _positive_int(pr_number, "PR number")
        cursor: str | None = None
        threads: list[dict[str, Any]] = []
        reported_total: int | None = None
        while True:
            args = [
                "api",
                "graphql",
                "-f",
                f"query={_REVIEW_THREADS_QUERY}",
                "-F",
                f"owner={_OWNER}",
                "-F",
                f"name={_NAME}",
                "-F",
                f"number={pr_number}",
            ]
            if cursor is not None:
                args.extend(["-F", f"cursor={cursor}"])
            result = self._runner.gh(args)
            if result.returncode != 0:
                raise GitHubReadError("GraphQL review-thread read failed before completeness could be proved")
            try:
                payload = json.loads(result.stdout)
            except json.JSONDecodeError as exc:
                raise GitHubReadError("GitHub returned malformed GraphQL JSON") from exc
            if not isinstance(payload, dict) or payload.get("errors"):
                raise GitHubReadError("GitHub GraphQL review-thread response is incomplete")
            try:
                connection = payload["data"]["repository"]["pullRequest"]["reviewThreads"]
                nodes = connection["nodes"]
                page_info = connection["pageInfo"]
                total = connection["totalCount"]
            except (KeyError, TypeError) as exc:
                raise GitHubReadError("GitHub GraphQL review-thread representation is incomplete") from exc
            if not isinstance(nodes, list) or not isinstance(page_info, dict):
                raise GitHubReadError("GitHub GraphQL review-thread page is malformed")
            if not isinstance(total, int) or isinstance(total, bool) or total < 0:
                raise GitHubReadError("GitHub GraphQL review-thread total is invalid")
            if reported_total is None:
                reported_total = total
            elif total != reported_total:
                raise GitHubReadError("GitHub GraphQL review-thread total changed between pages")
            for node in nodes:
                if not isinstance(node, dict):
                    raise GitHubReadError("GitHub GraphQL review-thread node is malformed")
                comments = node.get("comments")
                if not isinstance(comments, dict):
                    raise GitHubReadError("GitHub GraphQL review-thread comments are incomplete")
                comment_nodes = comments.get("nodes")
                comment_page = comments.get("pageInfo")
                comment_total = comments.get("totalCount")
                if not isinstance(comment_nodes, list) or not isinstance(comment_page, dict):
                    raise GitHubReadError("GitHub GraphQL review-thread comments are malformed")
                if not isinstance(comment_total, int) or isinstance(comment_total, bool) or comment_total < 0:
                    raise GitHubReadError("GitHub GraphQL review-thread comment total is invalid")
                if bool(comment_page.get("hasNextPage")) or len(comment_nodes) != comment_total:
                    raise GitHubReadError("review-thread comment pagination exceeds the supported fixed query")
                threads.append(node)
            has_next = bool(page_info.get("hasNextPage"))
            next_cursor = page_info.get("endCursor")
            if not has_next:
                break
            if not isinstance(next_cursor, str) or not next_cursor or next_cursor == cursor:
                raise GitHubReadError("GitHub GraphQL review-thread cursor is incomplete")
            cursor = next_cursor
        if reported_total is None or len(threads) != reported_total:
            raise GitHubReadError("GitHub GraphQL review-thread count mismatch")
        return threads

    def workflow_run(self, run_id: int) -> dict[str, Any]:
        _positive_int(run_id, "workflow run id")
        data = self._get(f"repos/{REPOSITORY}/actions/runs/{run_id}")
        if not isinstance(data, dict):
            raise GitHubReadError("workflow run representation is incomplete")
        return data

    def workflow_jobs(self, run_id: int, attempt: int) -> list[Any]:
        _positive_int(run_id, "workflow run id")
        _positive_int(attempt, "workflow run attempt")
        return self.keyed_collection(
            f"repos/{REPOSITORY}/actions/runs/{run_id}/attempts/{attempt}/jobs",
            item_key="jobs",
        )


def flatten_pages(pages: Iterable[list[Any]], *, expected_total: int | None = None) -> list[Any]:
    items: list[Any] = []
    for page in pages:
        if not isinstance(page, list):
            raise GitHubReadError("paginated response page is not an array")
        items.extend(page)
    if expected_total is not None and len(items) != expected_total:
        raise GitHubReadError("paginated response count mismatch")
    return items
