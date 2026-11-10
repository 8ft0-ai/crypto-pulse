from __future__ import annotations

import base64
import copy
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from issueops_dispatch import core, protected_dispatch
from issueops_dispatch import target_guard as legacy_guard
from issueops_dispatch import target_guard_main as guard

SHA = "a" * 40
AUTH_ID = "phase9-once"
RUN_ID = 555
NOW = datetime(2026, 8, 11, 0, 0, tzinfo=timezone.utc)
TARGET_BYTES = b"name: target\non:\n  workflow_dispatch:\n"
DISPATCHER_BYTES = b"name: dispatcher\n"


def record() -> dict[str, object]:
    return {
        "authorisation_id": AUTH_ID,
        "governing_issue": 352,
        "command": "/run-phase9-once",
        "actor_login": core.ACTOR_LOGIN,
        "actor_user_id": core.ACTOR_USER_ID,
        "required_author_association": core.AUTHOR_ASSOCIATION,
        "target_workflow_id": legacy_guard.TARGET_WORKFLOW_ID,
        "target_workflow_path": legacy_guard.TARGET_WORKFLOW_PATH,
        "target_ref_policy": core.TARGET_REF_POLICY,
        "target_workflow_sha256": core.sha256_bytes(TARGET_BYTES),
        "fixed_inputs": {},
        "maximum_dispatch_attempts": 1,
        "enabled": True,
        "not_before": None,
        "expires_at": None,
        "consumption_mechanism": core.CONSUMPTION_MECHANISM,
        "provenance_mechanism": core.PROVENANCE_MECHANISM,
        "attestation_predicate_type": core.PREDICATE_TYPE,
        "dispatcher_workflow_path": core.DISPATCHER_WORKFLOW_PATH,
        "dispatcher_workflow_sha256": core.sha256_bytes(DISPATCHER_BYTES),
        "execution_tag_ruleset_id": legacy_guard.RULESET_ID,
        "execution_tag_ruleset_name": legacy_guard.RULESET_NAME,
        "purpose": "remaining deterministic acceptance coverage",
    }


def resolution() -> core.Resolution:
    item = record()
    execution_tag = f"issueops/dispatch/{AUTH_ID}--sha-{SHA}"
    return core.Resolution(
        record=item,
        source_sha=SHA,
        record_sha256=core.sha256_bytes(core.canonical_json_bytes(item)),
        comment_body_sha256=core.sha256_text(str(item["command"])),
        fixed_inputs_sha256=core.sha256_bytes(
            core.canonical_json_bytes(item["fixed_inputs"])
        ),
        execution_tag=execution_tag,
        execution_ref=f"refs/tags/{execution_tag}",
    )


def event() -> dict[str, object]:
    return {
        "action": "created",
        "issue": {"number": 352},
        "comment": {
            "id": 9001,
            "body": "/run-phase9-once",
            "author_association": core.AUTHOR_ASSOCIATION,
            "created_at": "2026-08-11T00:00:00Z",
            "updated_at": "2026-08-11T00:00:00Z",
            "issue_url": "https://api.github.com/repos/8ft0-ai/crypto-pulse/issues/352",
            "html_url": "https://github.com/8ft0-ai/crypto-pulse/issues/352#issuecomment-9001",
            "user": {"login": core.ACTOR_LOGIN, "id": core.ACTOR_USER_ID},
        },
    }


def ruleset() -> dict[str, object]:
    return {
        "id": legacy_guard.RULESET_ID,
        "name": legacy_guard.RULESET_NAME,
        "target": "tag",
        "enforcement": "active",
        "conditions": {
            "ref_name": {
                "include": [core.RULESET_REF_INCLUDE],
                "exclude": [],
            }
        },
        "rules": [{"type": "update"}, {"type": "deletion"}],
    }


def tag() -> dict[str, object]:
    return {
        "ref": resolution().execution_ref,
        "object": {"type": "commit", "sha": SHA},
    }


def target_run(**updates: object) -> dict[str, object]:
    value: dict[str, object] = {
        "id": RUN_ID,
        "workflow_id": legacy_guard.TARGET_WORKFLOW_ID,
        "path": legacy_guard.TARGET_WORKFLOW_PATH,
        "event": "workflow_dispatch",
        "run_attempt": 1,
        "head_sha": SHA,
        "head_branch": protected_dispatch.TARGET_BRANCH,
        "repository": {
            "id": core.REPOSITORY_ID,
            "full_name": core.REPOSITORY,
        },
    }
    value.update(updates)
    return value


class NoReceiptAPI:
    def get_tag(self, _: str) -> dict[str, object]:
        return tag()

    def get_ruleset(self, _: int) -> dict[str, object]:
        return ruleset()

    def list_attestations(self, _: str) -> list[dict[str, object]]:
        return []


class DispatchAPI:
    def __init__(self, run: dict[str, object]) -> None:
        self.created = False
        self.dispatches = 0
        self.run = run

    def get_workflow(self, _: int) -> dict[str, object]:
        return {
            "id": legacy_guard.TARGET_WORKFLOW_ID,
            "path": legacy_guard.TARGET_WORKFLOW_PATH,
            "state": "active",
        }

    def get_contents(self, path: str, ref: str) -> dict[str, object]:
        return {
            "type": "file",
            "encoding": "base64",
            "content": base64.b64encode(TARGET_BYTES).decode(),
        }

    def get_ruleset(self, _: int) -> dict[str, object]:
        return ruleset()

    def get_comment(self, _: int) -> dict[str, object]:
        return copy.deepcopy(event()["comment"])

    def get_tag(self, _: str) -> dict[str, object] | None:
        return tag() if self.created else None

    def create_tag_once(self, execution_ref: str, source_sha: str) -> dict[str, object]:
        self.created = True
        return tag()

    def dispatch_main_once(
        self,
        workflow_id: int,
        fixed_inputs: dict[str, object],
        authorisation_id: str,
    ) -> dict[str, object]:
        self.dispatches += 1
        return {
            "workflow_run_id": RUN_ID,
            "run_url": "https://api.github.com/run",
            "html_url": "https://github.com/run",
        }

    def get_run_attempt(self, run_id: int, attempt: int = 1) -> dict[str, object]:
        return copy.deepcopy(self.run)


class RemainingAcceptanceCoverageTests(unittest.TestCase):
    def test_direct_main_dispatch_without_target_bound_receipt_rejects(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".github/workflows").mkdir(parents=True)
            (root / ".github/issueops-workflow-dispatch.yml").write_text(
                json.dumps({"schema_version": 2, "authorisations": [record()]}),
                encoding="utf-8",
            )
            (root / legacy_guard.TARGET_WORKFLOW_PATH).write_bytes(TARGET_BYTES)
            (root / core.DISPATCHER_WORKFLOW_PATH).write_bytes(DISPATCHER_BYTES)

            with self.assertRaisesRegex(legacy_guard.GuardError, "bounded wait"):
                guard.execute_guard(
                    repository_root=root,
                    authorisation_id=AUTH_ID,
                    github_ref="refs/heads/main",
                    github_sha=SHA,
                    workflow_sha=SHA,
                    run_id=RUN_ID,
                    run_attempt=1,
                    repository=core.REPOSITORY,
                    token="unused",
                    gh_binary=root / "unused-gh",
                    now=NOW,
                    api=NoReceiptAPI(),
                    sleep_fn=lambda _: None,
                )

    def test_malformed_pagination_link_fails_closed(self) -> None:
        class API(legacy_guard.GitHubReadAPI):
            def __init__(self) -> None:
                self.repository = core.REPOSITORY
                self.base = f"https://api.github.com/repos/{core.REPOSITORY}"
                self.token = "unused"

            def _request_url(self, url: str):
                return (
                    {"attestations": []},
                    {
                        "Link": (
                            "https://api.github.com/repos/8ft0-ai/crypto-pulse/"
                            "attestations/x?page=2; rel=\"next\""
                        )
                    },
                )

        with self.assertRaisesRegex(legacy_guard.GuardError, "malformed"):
            API().list_attestations("a" * 64)

    def test_post_dispatch_run_identity_mismatches_reject_after_one_dispatch(self) -> None:
        cases = (
            target_run(id=RUN_ID + 1),
            target_run(workflow_id=legacy_guard.TARGET_WORKFLOW_ID + 1),
            target_run(path=".github/workflows/other.yml"),
            target_run(
                repository={
                    "id": core.REPOSITORY_ID + 1,
                    "full_name": core.REPOSITORY,
                }
            ),
            target_run(
                repository={
                    "id": core.REPOSITORY_ID,
                    "full_name": "8ft0-ai/other",
                }
            ),
        )
        for changed in cases:
            api = DispatchAPI(changed)
            with self.subTest(changed=changed), self.assertRaises(core.ContractError):
                protected_dispatch.consume_and_dispatch_main(
                    api=api,
                    event=event(),
                    resolution=resolution(),
                )
            self.assertEqual(api.dispatches, 1)


if __name__ == "__main__":
    unittest.main()
