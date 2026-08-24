from pathlib import Path
import json
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1] / "tools" / "operator"
sys.path.insert(0, str(ROOT))

from cryptopulse_operator.evidence import Status
from cryptopulse_operator.github_read import GitHubReader
from cryptopulse_operator.process import ProcessResult
from cryptopulse_operator.review_support import SupportResult, review_pack_snapshot
import cryptopulse_operator.review_support as review_support


BASE = "1" * 40
HEAD = "2" * 40
TREE = "3" * 40
APP_ID = 15368
REQUIRED_CHECK = "Build site and check generated output"


class PageRunner:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def gh(self, args, cwd=None):
        self.calls.append(tuple(args))
        return ProcessResult(0, json.dumps(self.payload), "")


class MainOnlyGitHub:
    def main_branch(self):
        return {
            "sha": BASE,
            "tree_sha": "9" * 40,
            "protected": True,
            "required_checks": [{"context": REQUIRED_CHECK, "app_id": APP_ID}],
        }


class CheckRunCompletenessRegressionTests(unittest.TestCase):
    def test_check_runs_explicitly_requests_all_before_paginating(self):
        runner = PageRunner(
            [
                {
                    "total_count": 2,
                    "check_runs": [{"id": 1}, {"id": 2}],
                }
            ]
        )
        items = GitHubReader(runner).check_runs(HEAD)
        self.assertEqual([item["id"] for item in items], [1, 2])
        self.assertEqual(
            runner.calls,
            [
                (
                    "api",
                    "--method",
                    "GET",
                    "--paginate",
                    "--slurp",
                    f"repos/8ft0-ai/crypto-pulse/commits/{HEAD}/check-runs?filter=all",
                )
            ],
        )

    def test_multiple_required_context_app_matches_are_incomplete(self):
        check = {
            "id": 77,
            "name": REQUIRED_CHECK,
            "status": "completed",
            "conclusion": "success",
            "app_id": APP_ID,
        }
        candidate = SupportResult(
            data={
                "pr_number": 513,
                "base": {"ref": "main", "sha": BASE},
                "head": {"ref": "issue-509-operator-slice-b", "sha": HEAD},
                "head_commit": {"sha": HEAD, "tree_sha": TREE, "parents": [BASE]},
                "checks": [dict(check, id=77), dict(check, id=78)],
            },
            complete=True,
        )
        with patch.object(review_support, "candidate_snapshot", return_value=candidate):
            result, status, assertions = review_pack_snapshot(513, MainOnlyGitHub())

        self.assertEqual(status, Status.INCOMPLETE)
        self.assertFalse(result.complete)
        states = {item["name"]: item["holds"] for item in assertions}
        self.assertFalse(states["required-check-context-app-bound"])
        self.assertTrue(
            any(item["code"] == "required-check-missing-or-ambiguous" for item in result.findings)
        )


if __name__ == "__main__":
    unittest.main()
