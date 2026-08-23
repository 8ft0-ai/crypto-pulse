"""Bounded read-only GitHub adapter using authenticated `gh api`."""

from __future__ import annotations

import json
from typing import Any, Iterable

from .process import ProcessRunner


REPOSITORY = "8ft0-ai/crypto-pulse"


class GitHubReadError(RuntimeError):
    pass


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

    def auth_ok(self) -> bool:
        result = self._runner.gh(["auth", "status", "--hostname", "github.com"])
        return result.returncode == 0

    def collection(self, endpoint: str, *, expected_total: int | None = None) -> list[Any]:
        result = self._runner.gh(["api", "--method", "GET", "--paginate", "--slurp", endpoint])
        if result.returncode != 0:
            raise GitHubReadError("paginated GitHub read failed before completeness could be proved")
        try:
            pages = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise GitHubReadError("GitHub returned malformed paginated JSON") from exc
        if not isinstance(pages, list):
            raise GitHubReadError("paginated GitHub response is not an array of pages")
        return flatten_pages(pages, expected_total=expected_total)

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
        return {
            "sha": sha,
            "tree_sha": tree_sha,
            "protected": protected,
            "required_checks": [
                {"context": item.get("context"), "app_id": item.get("app_id")}
                for item in checks
                if isinstance(item, dict)
            ],
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


def flatten_pages(pages: Iterable[list[Any]], *, expected_total: int | None = None) -> list[Any]:
    items: list[Any] = []
    for page in pages:
        if not isinstance(page, list):
            raise GitHubReadError("paginated response page is not an array")
        items.extend(page)
    if expected_total is not None and len(items) != expected_total:
        raise GitHubReadError("paginated response count mismatch")
    return items
