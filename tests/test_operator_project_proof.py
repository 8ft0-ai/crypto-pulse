from __future__ import annotations

from pathlib import Path
import json
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
OPERATOR = ROOT / "tools" / "operator"
sys.path.insert(0, str(OPERATOR))

from cryptopulse_operator.evidence import Evidence, Status
from cryptopulse_operator.github_read import GitHubReadError, GitHubReader
from cryptopulse_operator.process import ProcessResult
from cryptopulse_operator.project_proof import (
    EXPECTED_CONTRACTS,
    contracts_snapshot,
    live_snapshot,
    load_config,
    pages_snapshot,
    path_triggers_pages,
    provenance_snapshot,
)
from cryptopulse_operator.review_support import RuntimeGate
from cryptopulse_operator.commands import pages as pages_command
from cryptopulse_operator.commands import live as live_command
from cryptopulse_operator.commands import provenance as provenance_command
from cryptopulse_operator.commands import contracts as contracts_command

MAIN = "a" * 40
DEPLOY = "b" * 40
TREE = "c" * 40
OTHER = "d" * 40
CONFIG = load_config()


def run_record(*, workflow="pages", sha=MAIN, status="completed", conclusion="success", number=10, attempt=1, event=None):
    if workflow == "pages":
        return {
            "id": 1000 + number,
            "run_number": number,
            "run_attempt": attempt,
            "name": CONFIG["pages_workflow_name"],
            "path": CONFIG["pages_workflow_path"],
            "event": event or "push",
            "status": status,
            "conclusion": conclusion,
            "head_branch": "main",
            "head_sha": sha,
        }
    return {
        "id": 2000 + number,
        "run_number": number,
        "run_attempt": attempt,
        "name": CONFIG["live_workflow_name"],
        "path": CONFIG["live_workflow_path"],
        "event": event or "workflow_dispatch",
        "status": status,
        "conclusion": conclusion,
        "head_branch": "main",
        "head_sha": sha,
    }


def job_record(name, run, *, status="completed", conclusion="success"):
    return {
        "id": run["id"] * 10 + len(name),
        "name": name,
        "status": status,
        "conclusion": conclusion,
        "run_id": run["id"],
        "run_attempt": run["run_attempt"],
    }


def artifact_record(run, *, name=None, expired=False, head_sha=None, run_id=None):
    return {
        "id": 9001,
        "name": name or CONFIG["live_evidence_artifact"],
        "expired": expired,
        "size_in_bytes": 4096,
        "created_at": "2026-08-25T00:00:00Z",
        "expires_at": "2026-09-24T00:00:00Z",
        "workflow_run": {
            "id": run["id"] if run_id is None else run_id,
            "head_sha": run["head_sha"] if head_sha is None else head_sha,
        },
    }


class FakeGitHub:
    def __init__(self, *, main_sha=MAIN, deploy_sha=MAIN):
        self.main_sha = main_sha
        self.main_tree = TREE
        self.protected = True
        self.pages_runs = [run_record(sha=deploy_sha)]
        self.live_runs = [run_record(workflow="live", sha=deploy_sha)]
        self.jobs = {}
        for run in self.pages_runs:
            self.jobs[(run["id"], run["run_attempt"])] = [
                job_record(CONFIG["pages_build_job"], run),
                job_record(CONFIG["pages_deploy_job"], run),
            ]
        for run in self.live_runs:
            self.jobs[(run["id"], run["run_attempt"])] = [job_record(CONFIG["live_verify_job"], run)]
        self.artifacts = {self.live_runs[0]["id"]: [artifact_record(self.live_runs[0])]}
        self.compare = None
        self.deny = set()

    def _maybe(self, name):
        if name in self.deny:
            raise GitHubReadError("denied")

    def main_branch(self):
        self._maybe("main_branch")
        return {"sha": self.main_sha, "tree_sha": self.main_tree, "protected": self.protected, "required_checks": []}

    def workflow_runs(self, workflow_file):
        self._maybe("workflow_runs")
        if workflow_file == CONFIG["pages_workflow_file"]:
            return self.pages_runs
        if workflow_file == CONFIG["live_workflow_file"]:
            return self.live_runs
        raise AssertionError(workflow_file)

    def workflow_jobs(self, run_id, attempt):
        self._maybe("workflow_jobs")
        return self.jobs.get((run_id, attempt), [])

    def workflow_artifacts(self, run_id):
        self._maybe("workflow_artifacts")
        return self.artifacts.get(run_id, [])

    def compare_commits(self, base_sha, head_sha):
        self._maybe("compare_commits")
        if self.compare is None:
            raise GitHubReadError("no compare fixture")
        return self.compare


def compare_fixture(paths, *, base=DEPLOY, head=MAIN, commits=2):
    return {
        "status": "ahead",
        "ahead_by": commits,
        "behind_by": 0,
        "total_commits": commits,
        "base_commit": {"sha": base},
        "merge_base_commit": {"sha": base},
        "commits": [{"sha": OTHER}] * (commits - 1) + [{"sha": head}],
        "files": [{"filename": path, "status": "modified"} for path in paths],
    }


class ProofTests(unittest.TestCase):
    def test_pages_exact_current_main_success(self):
        result = pages_snapshot(FakeGitHub(), CONFIG)
        self.assertEqual(result.status, Status.PASS)
        self.assertTrue(result.complete)
        self.assertEqual(result.data["publication_relation"]["relation"], "current-main")

    def test_pages_ancestor_non_triggering_is_publication_equivalent(self):
        github = FakeGitHub(main_sha=MAIN, deploy_sha=DEPLOY)
        github.compare = compare_fixture(["tools/operator/README.md", "tests/test_operator_project_proof.py"])
        result = pages_snapshot(github, CONFIG)
        self.assertEqual(result.status, Status.PASS)
        self.assertEqual(result.data["publication_relation"]["relation"], "publication-equivalent-ancestor")

    def test_pages_affecting_advance_fails(self):
        github = FakeGitHub(main_sha=MAIN, deploy_sha=DEPLOY)
        github.compare = compare_fixture(["site_generator/reader_evidence.py"])
        result = pages_snapshot(github, CONFIG)
        self.assertEqual(result.status, Status.FAIL)
        self.assertIn("site_generator/reader_evidence.py", result.data["publication_relation"]["triggering_paths"])

    def test_pages_rename_from_triggering_path_fails(self):
        github = FakeGitHub(main_sha=MAIN, deploy_sha=DEPLOY)
        github.compare = compare_fixture(["docs/moved.css"])
        github.compare["files"][0].update({
            "status": "renamed",
            "previous_filename": "site/assets/moved.css",
        })
        result = pages_snapshot(github, CONFIG)
        self.assertEqual(result.status, Status.FAIL)
        self.assertIn("site/assets/moved.css", result.data["publication_relation"]["triggering_paths"])
        self.assertIn("docs/moved.css", result.data["publication_relation"]["intervening_paths"])

    def test_pages_renamed_file_missing_previous_filename_is_incomplete(self):
        github = FakeGitHub(main_sha=MAIN, deploy_sha=DEPLOY)
        github.compare = compare_fixture(["docs/moved.css"])
        github.compare["files"][0]["status"] = "renamed"
        result = pages_snapshot(github, CONFIG)
        self.assertEqual(result.status, Status.INCOMPLETE)
        self.assertFalse(result.complete)
        self.assertIn({"code": "pages-compare-file-evidence-incomplete"}, result.findings)

    def test_pages_unsupported_file_status_is_incomplete(self):
        github = FakeGitHub(main_sha=MAIN, deploy_sha=DEPLOY)
        github.compare = compare_fixture(["docs/moved.css"])
        github.compare["files"][0]["status"] = "copied"
        result = pages_snapshot(github, CONFIG)
        self.assertEqual(result.status, Status.INCOMPLETE)
        self.assertFalse(result.complete)
        self.assertIn({"code": "pages-compare-file-evidence-incomplete"}, result.findings)

    def test_pages_compare_incomplete_fails_closed(self):
        github = FakeGitHub(main_sha=MAIN, deploy_sha=DEPLOY)
        github.compare = {"status": "ahead"}
        result = pages_snapshot(github, CONFIG)
        self.assertEqual(result.status, Status.INCOMPLETE)
        self.assertFalse(result.complete)

    def test_pages_compare_commit_count_mismatch_is_incomplete(self):
        github = FakeGitHub(main_sha=MAIN, deploy_sha=DEPLOY)
        github.compare = compare_fixture(["docs/readme.md"])
        github.compare["total_commits"] = 3
        result = pages_snapshot(github, CONFIG)
        self.assertEqual(result.status, Status.INCOMPLETE)

    def test_pages_pending_is_incomplete(self):
        github = FakeGitHub()
        github.pages_runs[0]["status"] = "in_progress"
        github.pages_runs[0]["conclusion"] = None
        self.assertEqual(pages_snapshot(github, CONFIG).status, Status.INCOMPLETE)

    def test_pages_failed_is_fail(self):
        github = FakeGitHub()
        github.pages_runs[0]["conclusion"] = "failure"
        self.assertEqual(pages_snapshot(github, CONFIG).status, Status.FAIL)

    def test_pages_cancelled_is_fail(self):
        github = FakeGitHub()
        github.pages_runs[0]["conclusion"] = "cancelled"
        self.assertEqual(pages_snapshot(github, CONFIG).status, Status.FAIL)

    def test_pages_job_missing_is_incomplete(self):
        github = FakeGitHub()
        run = github.pages_runs[0]
        github.jobs[(run["id"], run["run_attempt"])] = [job_record(CONFIG["pages_build_job"], run)]
        self.assertEqual(pages_snapshot(github, CONFIG).status, Status.INCOMPLETE)

    def test_pages_malformed_run_is_incomplete(self):
        github = FakeGitHub()
        github.pages_runs[0]["head_sha"] = "bad"
        self.assertEqual(pages_snapshot(github, CONFIG).status, Status.INCOMPLETE)

    def test_live_exact_bound_dispatch_success_and_retained_artifact(self):
        result = live_snapshot(FakeGitHub(), CONFIG)
        self.assertEqual(result.status, Status.PASS)
        self.assertEqual(result.data["artifact"]["name"], CONFIG["live_evidence_artifact"])

    def test_live_workflow_run_outer_sha_match_is_not_source_binding(self):
        github = FakeGitHub()
        github.live_runs[0]["event"] = "workflow_run"
        result = live_snapshot(github, CONFIG)
        self.assertEqual(result.status, Status.INCOMPLETE)
        self.assertIn({"code": "live-workflow-run-source-binding-unavailable"}, result.findings)

    def test_live_workflow_run_outer_sha_difference_is_not_source_binding(self):
        github = FakeGitHub()
        github.live_runs[0]["event"] = "workflow_run"
        github.live_runs[0]["head_sha"] = OTHER
        result = live_snapshot(github, CONFIG)
        self.assertEqual(result.status, Status.INCOMPLETE)
        self.assertIn({"code": "live-workflow-run-source-binding-unavailable"}, result.findings)

    def test_live_different_dispatch_sha_never_substitutes(self):
        github = FakeGitHub()
        github.live_runs[0]["head_sha"] = OTHER
        self.assertEqual(live_snapshot(github, CONFIG).status, Status.INCOMPLETE)

    def test_live_completed_failure_is_fail(self):
        github = FakeGitHub()
        github.live_runs[0]["conclusion"] = "failure"
        self.assertEqual(live_snapshot(github, CONFIG).status, Status.FAIL)

    def test_live_pending_is_incomplete(self):
        github = FakeGitHub()
        github.live_runs[0]["status"] = "queued"
        github.live_runs[0]["conclusion"] = None
        self.assertEqual(live_snapshot(github, CONFIG).status, Status.INCOMPLETE)

    def test_live_missing_artifact_is_incomplete(self):
        github = FakeGitHub()
        github.artifacts[github.live_runs[0]["id"]] = []
        self.assertEqual(live_snapshot(github, CONFIG).status, Status.INCOMPLETE)

    def test_live_duplicate_artifact_is_incomplete(self):
        github = FakeGitHub()
        run = github.live_runs[0]
        github.artifacts[run["id"]] = [artifact_record(run), artifact_record(run)]
        self.assertEqual(live_snapshot(github, CONFIG).status, Status.INCOMPLETE)

    def test_live_expired_artifact_is_incomplete(self):
        github = FakeGitHub()
        run = github.live_runs[0]
        github.artifacts[run["id"]] = [artifact_record(run, expired=True)]
        self.assertEqual(live_snapshot(github, CONFIG).status, Status.INCOMPLETE)

    def test_live_artifact_wrong_run_binding_is_incomplete(self):
        github = FakeGitHub()
        run = github.live_runs[0]
        github.artifacts[run["id"]] = [artifact_record(run, run_id=999999)]
        self.assertEqual(live_snapshot(github, CONFIG).status, Status.INCOMPLETE)

    def test_provenance_aggregates_exact_dispatch_chain(self):
        result = provenance_snapshot(FakeGitHub(), CONFIG)
        self.assertEqual(result.status, Status.PASS)
        self.assertEqual(result.data["pages"]["run"]["head_sha"], result.data["live"]["deployment_sha"])

    def test_provenance_does_not_weaken_workflow_run_binding_gap(self):
        github = FakeGitHub()
        github.live_runs[0]["event"] = "workflow_run"
        self.assertEqual(provenance_snapshot(github, CONFIG).status, Status.INCOMPLETE)

    def test_provenance_does_not_weaken_live_failure(self):
        github = FakeGitHub()
        github.live_runs[0]["conclusion"] = "failure"
        self.assertEqual(provenance_snapshot(github, CONFIG).status, Status.FAIL)

    def test_contract_index_is_exact_and_deterministic(self):
        first = contracts_snapshot(CONFIG)
        second = contracts_snapshot(CONFIG)
        self.assertEqual(first.status, Status.PASS)
        self.assertEqual(tuple(first.data["contracts"]), EXPECTED_CONTRACTS)
        self.assertEqual(first, second)

    def test_pages_path_matching(self):
        patterns = CONFIG["pages_trigger_paths"]
        self.assertTrue(path_triggers_pages("site_generator/foo.py", patterns))
        self.assertTrue(path_triggers_pages("reports/crypto/hourly/2026/08/25/a.md", patterns))
        self.assertFalse(path_triggers_pages("tools/operator/README.md", patterns))
        self.assertFalse(path_triggers_pages("tests/test_operator_project_proof.py", patterns))

    def test_pages_trigger_config_matches_workflow_fixture(self):
        text = (ROOT / ".github" / "workflows" / "pages.yml").read_text(encoding="utf-8")
        lines = text.splitlines()
        start = next(i for i, line in enumerate(lines) if line.strip() == "paths:")
        observed = []
        for line in lines[start + 1:]:
            stripped = line.strip()
            if stripped == "workflow_dispatch:":
                break
            if stripped.startswith("- "):
                observed.append(stripped[2:].strip().strip('"'))
        self.assertEqual(tuple(observed), CONFIG["pages_trigger_paths"])


class PageRunner:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = []
    def gh(self, args, cwd=None):
        self.calls.append(tuple(args))
        code, payload = self.outputs.pop(0)
        return ProcessResult(code, payload if isinstance(payload, str) else json.dumps(payload), "")


class AdapterTests(unittest.TestCase):
    def test_workflow_runs_pagination_success(self):
        runner = PageRunner([(0, [{"total_count": 2, "workflow_runs": [{"id": 1}]}, {"total_count": 2, "workflow_runs": [{"id": 2}]}])])
        reader = GitHubReader(runner)
        self.assertEqual([item["id"] for item in reader.workflow_runs("pages.yml")], [1, 2])
        self.assertIn("--method", runner.calls[0])
        self.assertIn("GET", runner.calls[0])

    def test_workflow_runs_count_mismatch_is_incomplete_at_adapter(self):
        runner = PageRunner([(0, [{"total_count": 2, "workflow_runs": [{"id": 1}]}])])
        with self.assertRaises(GitHubReadError):
            GitHubReader(runner).workflow_runs("pages.yml")

    def test_mid_pagination_failure_is_error(self):
        runner = PageRunner([(1, "")])
        with self.assertRaises(GitHubReadError):
            GitHubReader(runner).workflow_runs("pages.yml")

    def test_slice_d_adapter_calls_are_fixed_get_only(self):
        runner = PageRunner([
            (0, [{"total_count": 0, "workflow_runs": []}]),
            (0, [{"total_count": 0, "artifacts": []}]),
            (0, {"status": "ahead"}),
        ])
        reader = GitHubReader(runner)
        reader.workflow_runs("pages.yml")
        reader.workflow_artifacts(123)
        reader.compare_commits(MAIN, OTHER)
        for call in runner.calls:
            self.assertEqual(call[:3], ("api", "--method", "GET"))


class CommandGateTests(unittest.TestCase):
    def test_all_slice_d_commands_pass_existing_runtime_gate_first(self):
        gate = RuntimeGate(
            runtime={"repository": "8ft0-ai/crypto-pulse", "clean": False, "provenance": None},
            status=Status.ERROR,
            complete=False,
            findings=({"code": "runtime-test-stop"},),
            assertions=({"name": "runtime-gate-test", "holds": False},),
        )
        for module in (pages_command, live_command, provenance_command, contracts_command):
            with self.subTest(module=module.__name__), patch.object(module, "runtime_gate", return_value=gate):
                evidence = module.run(object(), object())
                self.assertEqual(evidence.status, Status.ERROR)
                self.assertIn({"code": "runtime-test-stop"}, evidence.findings)

    def test_deterministic_evidence_hash_for_contracts(self):
        gate = RuntimeGate(runtime={"repository": "8ft0-ai/crypto-pulse", "clean": True, "provenance": "current-main"}, status=None, complete=True, findings=(), assertions=())
        with patch.object(contracts_command, "runtime_gate", return_value=gate):
            one = contracts_command.run(object(), object()).json_text()
            two = contracts_command.run(object(), object()).json_text()
        self.assertEqual(one, two)

    def test_synthetic_credential_like_value_is_rejected(self):
        bad = Evidence(
            command="contracts", repository="8ft0-ai/crypto-pulse", invocation_target={}, runtime={},
            remote={"value": "token=github_pat_ABCDEFGHIJKLMNOPQRSTUV123456"}, local={}, status=Status.PASS,
            completeness={"complete": True},
        )
        with self.assertRaises(ValueError):
            bad.payload()


if __name__ == "__main__":
    unittest.main()
