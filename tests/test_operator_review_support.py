from pathlib import Path
import json
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1] / "tools" / "operator"
sys.path.insert(0, str(ROOT))

from cryptopulse_operator.cli import parser
from cryptopulse_operator.commands import candidate as candidate_command
from cryptopulse_operator.commands import ci as ci_command
from cryptopulse_operator.commands import review_pack as review_pack_command
from cryptopulse_operator.evidence import Status
from cryptopulse_operator.github_read import GitHubReadError, GitHubReader
from cryptopulse_operator.process import ProcessResult
from cryptopulse_operator.review_support import (
    BODY_LIMIT,
    SupportResult,
    candidate_snapshot,
    ci_snapshot,
    review_pack_snapshot,
)
from cryptopulse_operator.runtime import RuntimeCheck
import cryptopulse_operator.review_support as review_support


BASE = "1" * 40
HEAD = "2" * 40
TREE = "3" * 40
PARENT = "4" * 40
APP_ID = 15368
RUN_ID = 123456


class PageRunner:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = []

    def gh(self, args, cwd=None):
        self.calls.append(tuple(args))
        if not self.outputs:
            raise AssertionError("unexpected gh call")
        code, payload = self.outputs.pop(0)
        text = payload if isinstance(payload, str) else json.dumps(payload)
        return ProcessResult(code, text, "")


class NoProcessRunner:
    def __init__(self):
        self.calls = []

    def has_executable(self, name):
        return True

    def run(self, argv, cwd=None):
        self.calls.append(tuple(argv))
        return ProcessResult(0, "", "")

    def git(self, args, cwd=None):
        self.calls.append(("git", *args))
        return ProcessResult(0, "", "")

    def gh(self, args, cwd=None):
        self.calls.append(("gh", *args))
        return ProcessResult(0, "", "")


def pr_payload(*, base=BASE, base_ref="main", head=HEAD, state="open", mergeable=True):
    return {
        "state": state,
        "draft": False,
        "mergeable": mergeable,
        "merged": False,
        "base": {"ref": base_ref, "sha": base},
        "head": {"ref": "issue-509-slice-b", "sha": head},
        "commits": 1,
        "changed_files": 1,
    }


def head_commit_payload():
    return {
        "sha": HEAD,
        "commit": {"tree": {"sha": TREE}},
        "parents": [{"sha": PARENT}],
    }


def commit_list():
    return [
        {
            "sha": HEAD,
            "commit": {"tree": {"sha": TREE}},
            "parents": [{"sha": PARENT}],
        }
    ]


def file_list(*, filename="tools/operator/example.py"):
    return [
        {
            "filename": filename,
            "status": "modified",
            "sha": "5" * 40,
            "additions": 2,
            "deletions": 1,
            "changes": 3,
            "patch": "@@ -1 +1 @@\n-old\n+new",
        }
    ]


def check_run(*, status="completed", conclusion="success", app_id=APP_ID, details=None, pr_base=BASE, pr_head=HEAD, include_pr=True):
    return {
        "id": 77,
        "name": "Build site and check generated output",
        "status": status,
        "conclusion": conclusion,
        "started_at": "2026-08-24T00:00:00Z",
        "completed_at": "2026-08-24T00:01:00Z" if status == "completed" else None,
        "details_url": details or f"https://github.com/8ft0-ai/crypto-pulse/actions/runs/{RUN_ID}/job/999",
        "app": {"id": app_id, "slug": "github-actions"},
        "pull_requests": ([{"number": 512, "base": {"sha": pr_base}, "head": {"sha": pr_head}}] if include_pr else []),
    }


def run_payload(*, head=HEAD, conclusion="success", status="completed", pr_base=BASE, pr_head=HEAD, include_pr=True, event="pull_request"):
    return {
        "id": RUN_ID,
        "run_attempt": 1,
        "name": "Validate CryptoPulse PR",
        "workflow_id": 274454472,
        "path": ".github/workflows/pr-validation.yml",
        "event": event,
        "head_sha": head,
        "status": status,
        "conclusion": conclusion,
        "created_at": "2026-08-24T00:00:00Z",
        "updated_at": "2026-08-24T00:02:00Z",
        "run_started_at": "2026-08-24T00:00:00Z",
        "head_commit": {"id": head, "tree_id": TREE},
        "pull_requests": ([{"number": 512, "base": {"sha": pr_base}, "head": {"sha": pr_head}}] if include_pr else []),
    }


def job_list(*, conclusion="success"):
    return [
        {
            "id": 999,
            "name": "Build site and check generated output",
            "status": "completed",
            "conclusion": conclusion,
            "started_at": "2026-08-24T00:00:00Z",
            "completed_at": "2026-08-24T00:01:00Z",
            "steps": [
                {
                    "number": 1,
                    "name": "Run unit tests",
                    "status": "completed",
                    "conclusion": conclusion,
                    "started_at": "2026-08-24T00:00:10Z",
                    "completed_at": "2026-08-24T00:00:40Z",
                }
            ],
        }
    ]


class ReviewGitHub:
    def __init__(
        self,
        *,
        base=BASE,
        base_ref="main",
        head=HEAD,
        mergeable=True,
        check_status="completed",
        check_conclusion="success",
        check_app=APP_ID,
        check_pr_base=None,
        check_pr_head=None,
        include_check_pr=True,
        run_head=HEAD,
        run_status="completed",
        run_conclusion="success",
        run_pr_base=None,
        run_pr_head=None,
        include_run_pr=True,
        run_event="pull_request",
        comment_body="APPROVED",
        required_checks=None,
        thread_rest_id=301,
        thread_outdated=False,
    ):
        self.base = base
        self.base_ref = base_ref
        self.head = head
        self.mergeable = mergeable
        self.check_status = check_status
        self.check_conclusion = check_conclusion
        self.check_app = check_app
        self.check_pr_base = base if check_pr_base is None else check_pr_base
        self.check_pr_head = head if check_pr_head is None else check_pr_head
        self.include_check_pr = include_check_pr
        self.run_head = run_head
        self.run_status = run_status
        self.run_conclusion = run_conclusion
        self.run_pr_base = base if run_pr_base is None else run_pr_base
        self.run_pr_head = head if run_pr_head is None else run_pr_head
        self.include_run_pr = include_run_pr
        self.run_event = run_event
        self.comment_body = comment_body
        self.required_checks = required_checks
        self.thread_rest_id = thread_rest_id
        self.thread_outdated = thread_outdated

    def auth_ok(self):
        return True

    def pull_request(self, pr_number):
        return pr_payload(base=self.base, base_ref=self.base_ref, head=self.head, mergeable=self.mergeable)

    def commit(self, sha):
        data = head_commit_payload()
        data["sha"] = self.head
        return data

    def pull_commits(self, pr_number, expected_total):
        data = commit_list()
        data[0]["sha"] = self.head
        return data

    def pull_files(self, pr_number, expected_total):
        return file_list()

    def check_runs(self, sha):
        return [
            check_run(
                status=self.check_status,
                conclusion=self.check_conclusion,
                app_id=self.check_app,
                pr_base=self.check_pr_base,
                pr_head=self.check_pr_head,
                include_pr=self.include_check_pr,
            )
        ]

    def pull_reviews(self, pr_number):
        return [
            {
                "id": 101,
                "user": {"login": "reviewer"},
                "state": "COMMENTED",
                "commit_id": self.head,
                "submitted_at": "2026-08-24T00:02:00Z",
                "body": self.comment_body,
            }
        ]

    def issue_comments(self, issue_number):
        return [
            {
                "id": 201,
                "user": {"login": "owner"},
                "created_at": "2026-08-24T00:03:00Z",
                "updated_at": "2026-08-24T00:03:00Z",
                "body": "handoff",
            }
        ]

    def review_comments(self, pr_number):
        return [
            {
                "id": self.thread_rest_id,
                "user": {"login": "reviewer"},
                "pull_request_review_id": 101,
                "in_reply_to_id": None,
                "commit_id": self.head,
                "path": "tools/operator/example.py",
                "line": 10,
                "start_line": None,
                "side": "RIGHT",
                "position": 10,
                "original_position": 10,
                "created_at": "2026-08-24T00:04:00Z",
                "updated_at": "2026-08-24T00:04:00Z",
                "body": "bounded review comment",
            }
        ]

    def review_threads(self, pr_number):
        return [
            {
                "id": "PRRT_thread",
                "isResolved": True,
                "isOutdated": self.thread_outdated,
                "comments": {
                    "totalCount": 1,
                    "nodes": [{"id": "PRRC_node", "databaseId": 301}],
                    "pageInfo": {"hasNextPage": False, "endCursor": None},
                },
            }
        ]

    def main_branch(self):
        checks = self.required_checks
        if checks is None:
            checks = [{"context": "Build site and check generated output", "app_id": APP_ID}]
        return {
            "sha": BASE,
            "tree_sha": "9" * 40,
            "protected": True,
            "required_checks": checks,
        }

    def workflow_run(self, run_id):
        return run_payload(
            head=self.run_head,
            status=self.run_status,
            conclusion=self.run_conclusion,
            pr_base=self.run_pr_base,
            pr_head=self.run_pr_head,
            include_pr=self.include_run_pr,
            event=self.run_event,
        )

    def workflow_jobs(self, run_id, attempt):
        return job_list(conclusion=self.run_conclusion or "success")


class GitHubReaderPaginationTests(unittest.TestCase):
    def test_keyed_collection_exhausts_pages_and_verifies_total(self):
        runner = PageRunner(
            [
                (
                    0,
                    [
                        {"total_count": 3, "check_runs": [{"id": 1}, {"id": 2}]},
                        {"total_count": 3, "check_runs": [{"id": 3}]},
                    ],
                )
            ]
        )
        reader = GitHubReader(runner)
        items = reader.keyed_collection("repos/x/y/check-runs", item_key="check_runs")
        self.assertEqual([item["id"] for item in items], [1, 2, 3])
        self.assertIn("--paginate", runner.calls[0])
        self.assertIn("--slurp", runner.calls[0])

    def test_check_runs_explicitly_requests_complete_all_filter(self):
        runner = PageRunner(
            [
                (
                    0,
                    [
                        {
                            "total_count": 2,
                            "check_runs": [{"id": 1}, {"id": 2}],
                        }
                    ],
                )
            ]
        )
        items = GitHubReader(runner).check_runs(HEAD)
        self.assertEqual([item["id"] for item in items], [1, 2])
        self.assertEqual(
            runner.calls[0],
            (
                "api",
                "--method",
                "GET",
                "--paginate",
                "--slurp",
                f"repos/8ft0-ai/crypto-pulse/commits/{HEAD}/check-runs?filter=all",
            ),
        )

    def test_keyed_collection_count_mismatch_and_malformed_page_fail_closed(self):
        mismatch = PageRunner([(0, [{"total_count": 2, "jobs": [{"id": 1}]}])])
        with self.assertRaises(GitHubReadError):
            GitHubReader(mismatch).keyed_collection("repos/x/y/jobs", item_key="jobs")

        malformed = PageRunner([(0, [["not", "an", "object"]])])
        with self.assertRaises(GitHubReadError):
            GitHubReader(malformed).keyed_collection("repos/x/y/jobs", item_key="jobs")

        failed = PageRunner([(1, "")])
        with self.assertRaises(GitHubReadError):
            GitHubReader(failed).collection("repos/x/y/items")

    def test_review_threads_exhaust_fixed_query_cursor(self):
        first = {
            "data": {
                "repository": {
                    "pullRequest": {
                        "reviewThreads": {
                            "totalCount": 2,
                            "nodes": [
                                {
                                    "id": "T1",
                                    "isResolved": False,
                                    "isOutdated": False,
                                    "comments": {
                                        "totalCount": 1,
                                        "nodes": [{"id": "C1", "databaseId": 11}],
                                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                                    },
                                }
                            ],
                            "pageInfo": {"hasNextPage": True, "endCursor": "CURSOR-1"},
                        }
                    }
                }
            }
        }
        second = {
            "data": {
                "repository": {
                    "pullRequest": {
                        "reviewThreads": {
                            "totalCount": 2,
                            "nodes": [
                                {
                                    "id": "T2",
                                    "isResolved": True,
                                    "isOutdated": True,
                                    "comments": {
                                        "totalCount": 1,
                                        "nodes": [{"id": "C2", "databaseId": 12}],
                                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                                    },
                                }
                            ],
                            "pageInfo": {"hasNextPage": False, "endCursor": None},
                        }
                    }
                }
            }
        }
        runner = PageRunner([(0, first), (0, second)])
        threads = GitHubReader(runner).review_threads(512)
        self.assertEqual([item["id"] for item in threads], ["T1", "T2"])
        self.assertFalse(threads[0]["isOutdated"])
        self.assertTrue(threads[1]["isOutdated"])
        self.assertIn("cursor=CURSOR-1", runner.calls[1])
        self.assertIn("isOutdated", " ".join(runner.calls[0]))
        for call in runner.calls:
            joined = " ".join(call)
            self.assertNotIn("tools/operator", joined)
            self.assertNotIn("scripts/", joined)

    def test_review_thread_nested_comment_overflow_is_incomplete(self):
        payload = {
            "data": {
                "repository": {
                    "pullRequest": {
                        "reviewThreads": {
                            "totalCount": 1,
                            "nodes": [
                                {
                                    "id": "T1",
                                    "isResolved": False,
                                    "isOutdated": False,
                                    "comments": {
                                        "totalCount": 101,
                                        "nodes": [{"id": "C1", "databaseId": 11}],
                                        "pageInfo": {"hasNextPage": True, "endCursor": "MORE"},
                                    },
                                }
                            ],
                            "pageInfo": {"hasNextPage": False, "endCursor": None},
                        }
                    }
                }
            }
        }
        with self.assertRaises(GitHubReadError):
            GitHubReader(PageRunner([(0, payload)])).review_threads(512)


class ReviewSupportExtractionTests(unittest.TestCase):
    def test_candidate_reconstructs_exact_identities_and_thread_state(self):
        result = candidate_snapshot(512, ReviewGitHub())
        self.assertTrue(result.complete)
        self.assertEqual(result.data["base"]["sha"], BASE)
        self.assertEqual(result.data["head"]["sha"], HEAD)
        self.assertEqual(result.data["head_commit"]["tree_sha"], TREE)
        self.assertEqual(result.data["head_commit"]["parents"], [PARENT])
        self.assertEqual(result.data["protected_main"]["sha"], BASE)
        self.assertTrue(result.data["protected_main"]["protected"])
        self.assertEqual(
            result.data["protected_main"]["required_checks"],
            [{"context": "Build site and check generated output", "app_id": APP_ID}],
        )
        self.assertEqual(result.data["commits"][0]["sha"], HEAD)
        self.assertTrue(result.data["files"][0]["patch_available"])
        self.assertEqual(result.data["checks"][0]["app_id"], APP_ID)
        self.assertTrue(result.data["review_threads"][0]["resolved"])
        self.assertFalse(result.data["review_threads"][0]["outdated"])

    def test_candidate_uses_authoritative_thread_outdated_state(self):
        result = candidate_snapshot(512, ReviewGitHub(thread_outdated=True))
        self.assertTrue(result.complete)
        self.assertTrue(result.data["review_threads"][0]["outdated"])
        self.assertEqual(result.data["review_comments"][0]["position"], 10)
        self.assertNotIn("outdated", result.data["review_comments"][0])
        self.assertNotIn("outdated", result.data["review_threads"][0]["comments"][0])

    def test_pending_mergeability_is_incomplete(self):
        result = candidate_snapshot(512, ReviewGitHub(mergeable=None))
        self.assertFalse(result.complete)
        self.assertIsNone(result.data["mergeable"])
        self.assertTrue(any(item["code"] == "pull-request-mergeability-pending" for item in result.findings))

    def test_candidate_reports_binary_or_unavailable_patch_without_guessing(self):
        class BinaryGitHub(ReviewGitHub):
            def pull_files(self, pr_number, expected_total):
                item = file_list()[0]
                item.pop("patch")
                return [item]

        result = candidate_snapshot(512, BinaryGitHub())
        self.assertTrue(result.complete)
        self.assertFalse(result.data["files"][0]["patch_available"])
        self.assertIsNone(result.data["files"][0]["patch_bytes"])

    def test_sensitive_or_oversized_review_text_fails_closed_without_emission(self):
        secret = "ghp_" + "A" * 40
        sensitive = candidate_snapshot(512, ReviewGitHub(comment_body=f"do not print {secret}"))
        self.assertFalse(sensitive.complete)
        review = sensitive.data["reviews"][0]
        self.assertIsNone(review["body"])
        self.assertEqual(review["body_state"], "sensitive")
        self.assertNotIn(secret, repr(sensitive.data))

        oversized = candidate_snapshot(512, ReviewGitHub(comment_body="x" * (BODY_LIMIT + 1)))
        self.assertFalse(oversized.complete)
        self.assertEqual(oversized.data["reviews"][0]["body_state"], "over-budget")

    def test_missing_rest_comment_identity_makes_thread_state_incomplete(self):
        result = candidate_snapshot(512, ReviewGitHub(thread_rest_id=999))
        self.assertFalse(result.complete)
        self.assertTrue(any(item["code"] == "review-thread-comment-not-in-rest" for item in result.findings))

    def test_ci_reconstructs_attempt_jobs_steps_and_bounded_failure_metadata(self):
        result = ci_snapshot(RUN_ID, ReviewGitHub(run_conclusion="failure"))
        self.assertTrue(result.complete)
        self.assertEqual(result.data["head_sha"], HEAD)
        self.assertEqual(result.data["head_tree_sha"], TREE)
        self.assertEqual(result.data["pull_requests"][0], {"number": 512, "base_sha": BASE, "head_sha": HEAD})
        self.assertEqual(result.data["jobs"][0]["steps"][0]["name"], "Run unit tests")
        self.assertEqual(result.data["failure_context"][0]["conclusion"], "failure")
        self.assertFalse(result.data["logs_emitted"])
        self.assertNotIn("stdout", repr(result.data))
        self.assertNotIn("stderr", repr(result.data))


class ReviewPackTests(unittest.TestCase):
    def test_review_pack_pass_binds_current_base_required_app_and_exact_head_ci(self):
        result, status, assertions = review_pack_snapshot(512, ReviewGitHub())
        self.assertEqual(status, Status.PASS)
        self.assertTrue(result.complete)
        states = {item["name"]: item["holds"] for item in assertions}
        self.assertTrue(states["main-protected"])
        self.assertTrue(states["candidate-base-is-current-main"])
        self.assertTrue(states["required-check-context-app-bound"])
        self.assertTrue(states["required-ci-exact-head"])
        self.assertTrue(states["required-ci-pull-request-event"])
        self.assertTrue(states["required-ci-pr-base-head-bound"])
        self.assertTrue(states["required-ci-success"])
        self.assertTrue(states["required-check-ci-conclusion-consistent"])
        self.assertEqual(result.data["ci"]["run_id"], RUN_ID)

    def test_non_main_base_ref_at_current_main_sha_is_incomplete(self):
        result, status, assertions = review_pack_snapshot(512, ReviewGitHub(base_ref="release"))
        self.assertEqual(status, Status.INCOMPLETE)
        self.assertFalse(result.complete)
        states = {item["name"]: item["holds"] for item in assertions}
        self.assertFalse(states["candidate-base-is-current-main"])
        self.assertTrue(any(item["code"] == "candidate-base-not-current-main" for item in result.findings))

    def test_multiple_required_context_app_matches_are_incomplete(self):
        class DuplicateCheckGitHub(ReviewGitHub):
            def check_runs(self, sha):
                first = super().check_runs(sha)[0]
                return [first, dict(first, id=78)]

        result, status, assertions = review_pack_snapshot(512, DuplicateCheckGitHub())
        self.assertEqual(status, Status.INCOMPLETE)
        self.assertFalse(result.complete)
        states = {item["name"]: item["holds"] for item in assertions}
        self.assertFalse(states["required-check-context-app-bound"])
        self.assertTrue(any(item["code"] == "required-check-missing-or-ambiguous" for item in result.findings))

    def test_missing_pending_or_wrong_app_required_check_is_incomplete(self):
        missing, status, _ = review_pack_snapshot(
            512, ReviewGitHub(required_checks=[{"context": "Different required check", "app_id": APP_ID}])
        )
        self.assertEqual(status, Status.INCOMPLETE)
        self.assertFalse(missing.complete)

        pending, status, _ = review_pack_snapshot(512, ReviewGitHub(check_status="in_progress", check_conclusion=None))
        self.assertEqual(status, Status.INCOMPLETE)
        self.assertFalse(pending.complete)

        missing_conclusion, status, _ = review_pack_snapshot(512, ReviewGitHub(check_conclusion=None))
        self.assertEqual(status, Status.INCOMPLETE)
        self.assertFalse(missing_conclusion.complete)

        wrong_app, status, _ = review_pack_snapshot(512, ReviewGitHub(check_app=999))
        self.assertEqual(status, Status.INCOMPLETE)
        self.assertFalse(wrong_app.complete)

    def test_missing_stale_or_non_pr_ci_binding_is_incomplete_for_success_and_failure(self):
        for conclusion in ("success", "failure"):
            kwargs = {"check_conclusion": conclusion, "run_conclusion": conclusion}

            missing, status, assertions = review_pack_snapshot(
                512, ReviewGitHub(include_run_pr=False, **kwargs)
            )
            self.assertEqual(status, Status.INCOMPLETE)
            self.assertFalse(missing.complete)
            self.assertFalse(
                {item["name"]: item["holds"] for item in assertions}["required-ci-pr-base-head-bound"]
            )

            stale_base, status, _ = review_pack_snapshot(
                512, ReviewGitHub(run_pr_base="a" * 40, **kwargs)
            )
            self.assertEqual(status, Status.INCOMPLETE)
            self.assertFalse(stale_base.complete)

            stale_head, status, _ = review_pack_snapshot(
                512, ReviewGitHub(run_pr_head="a" * 40, **kwargs)
            )
            self.assertEqual(status, Status.INCOMPLETE)
            self.assertFalse(stale_head.complete)

            wrong_event, status, _ = review_pack_snapshot(
                512, ReviewGitHub(run_event="workflow_dispatch", **kwargs)
            )
            self.assertEqual(status, Status.INCOMPLETE)
            self.assertFalse(wrong_event.complete)

    def test_completed_failed_required_check_is_fail_only_after_bound_failing_ci(self):
        result, status, assertions = review_pack_snapshot(
            512, ReviewGitHub(check_conclusion="failure", run_conclusion="failure")
        )
        self.assertEqual(status, Status.FAIL)
        self.assertTrue(result.complete)
        states = {item["name"]: item["holds"] for item in assertions}
        self.assertFalse(states["required-check-success"])
        self.assertFalse(states["required-ci-success"])
        self.assertTrue(states["required-check-ci-conclusion-consistent"])
        self.assertTrue(states["required-ci-pr-base-head-bound"])
        self.assertEqual(result.data["ci"]["run_id"], RUN_ID)
        self.assertEqual(result.data["ci"]["failure_context"][0]["conclusion"], "failure")

    def test_stale_base_or_wrong_run_head_is_incomplete_not_timestamp_inferred(self):
        stale, status, _ = review_pack_snapshot(512, ReviewGitHub(base="0" * 40))
        self.assertEqual(status, Status.INCOMPLETE)
        self.assertFalse(stale.complete)

        wrong_head, status, _ = review_pack_snapshot(512, ReviewGitHub(run_head="f" * 40))
        self.assertEqual(status, Status.INCOMPLETE)
        self.assertFalse(wrong_head.complete)

    def test_check_and_bound_ci_conclusion_mismatch_is_incomplete(self):
        for check_conclusion, run_conclusion in (("failure", "success"), ("success", "failure")):
            result, status, assertions = review_pack_snapshot(
                512,
                ReviewGitHub(check_conclusion=check_conclusion, run_conclusion=run_conclusion),
            )
            self.assertEqual(status, Status.INCOMPLETE)
            self.assertFalse(result.complete)
            states = {item["name"]: item["holds"] for item in assertions}
            self.assertFalse(states["required-check-ci-conclusion-consistent"])
            self.assertTrue(any(item["code"] == "required-check-ci-conclusion-mismatch" for item in result.findings))


class CommandBoundaryTests(unittest.TestCase):
    def trusted_runtime(self):
        return RuntimeCheck(
            {
                "repository": "8ft0-ai/crypto-pulse",
                "commit_sha": "a" * 40,
                "tree_sha": "b" * 40,
                "toolkit_identity": {"launcher_blob": "c" * 40, "package_tree": "d" * 40},
                "config_identity": "e" * 40,
                "clean": True,
                "provenance": "ancestor-of-current-main",
            },
            complete=True,
            trusted=True,
            reason=None,
        )

    def test_cli_accepts_only_positive_numeric_pr_and_run_ids(self):
        parsed = parser().parse_args(["candidate", "512", "--evidence"])
        self.assertEqual(parsed.pr, 512)
        parsed = parser().parse_args(["ci", "123", "--json"])
        self.assertEqual(parsed.run_id, 123)
        for argv in (["candidate", "0"], ["candidate", "abc"], ["ci", "-1"], ["review-pack", "x"]):
            with self.assertRaises(SystemExit):
                parser().parse_args(argv)

    def test_candidate_ci_and_review_pack_never_send_candidate_paths_to_process_adapter(self):
        runner = NoProcessRunner()
        github = ReviewGitHub()
        with patch.object(review_support, "inspect_runtime", return_value=self.trusted_runtime()):
            candidate = candidate_command.run(512, runner, github)
            ci = ci_command.run(RUN_ID, runner, github)
            pack = review_pack_command.run(512, runner, github)
        self.assertEqual(candidate.status, Status.PASS)
        self.assertEqual(ci.status, Status.PASS)
        self.assertEqual(pack.status, Status.PASS)
        self.assertEqual(runner.calls, [])

    def test_candidate_changes_to_launcher_config_workflow_or_scripts_remain_data_only(self):
        marker = "scripts/exfiltrate-credential.sh"

        class MaliciousGitHub(ReviewGitHub):
            def pull_files(self, pr_number, expected_total):
                return file_list(filename=marker)

            def issue_comments(self, issue_number):
                return [
                    {
                        "id": 201,
                        "user": {"login": "owner"},
                        "created_at": "2026-08-24T00:03:00Z",
                        "updated_at": "2026-08-24T00:03:00Z",
                        "body": "candidate changes tools/operator/cp and .github/workflows/pr-validation.yml",
                    }
                ]

        runner = NoProcessRunner()
        with patch.object(review_support, "inspect_runtime", return_value=self.trusted_runtime()):
            evidence = candidate_command.run(512, runner, MaliciousGitHub())
        self.assertEqual(evidence.status, Status.PASS)
        self.assertEqual(evidence.remote["files"][0]["path"], marker)
        self.assertEqual(runner.calls, [])

    def test_equivalent_slice_b_input_produces_deterministic_evidence_and_binds_runtime(self):
        runner = NoProcessRunner()
        github = ReviewGitHub()
        with patch.object(review_support, "inspect_runtime", return_value=self.trusted_runtime()):
            first = candidate_command.run(512, runner, github)
            second = candidate_command.run(512, runner, github)
        self.assertEqual(first.json_text(), second.json_text())
        payload = first.payload()
        self.assertEqual(payload["runtime"]["commit_sha"], "a" * 40)
        self.assertEqual(payload["runtime"]["provenance"], "ancestor-of-current-main")


if __name__ == "__main__":
    unittest.main()
