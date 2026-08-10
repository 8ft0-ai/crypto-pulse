from __future__ import annotations

import base64
import copy
import json
import tempfile
import unittest
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from issueops_dispatch import core, protected_dispatch
from issueops_dispatch import target_guard as legacy_guard
from issueops_dispatch import target_guard_main as guard

SHA = "a" * 40
OTHER_SHA = "b" * 40
AUTH_ID = "phase9-once"
RUN_ID = 555
DISPATCHER_RUN_ID = 777
NOW = datetime(2026, 8, 10, 12, 0, tzinfo=timezone.utc)
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
        "execution_tag_ruleset_id": 20623136,
        "execution_tag_ruleset_name": "IssueOps immutable execution tags",
        "purpose": "test authority",
    }


def resolution() -> core.Resolution:
    item = record()
    return core.Resolution(
        record=item,
        source_sha=SHA,
        record_sha256=core.sha256_bytes(core.canonical_json_bytes(item)),
        comment_body_sha256=core.sha256_text(str(item["command"])),
        fixed_inputs_sha256=core.sha256_bytes(
            core.canonical_json_bytes(item["fixed_inputs"])
        ),
        execution_tag=f"issueops/dispatch/{AUTH_ID}--sha-{SHA}",
        execution_ref=f"refs/tags/issueops/dispatch/{AUTH_ID}--sha-{SHA}",
    )


def event() -> dict[str, object]:
    return {
        "action": "created",
        "issue": {"number": 352},
        "comment": {
            "id": 9001,
            "body": "/run-phase9-once",
            "author_association": core.AUTHOR_ASSOCIATION,
            "created_at": "2026-08-10T11:59:00Z",
            "updated_at": "2026-08-10T11:59:00Z",
            "issue_url": "https://api.github.com/repos/8ft0-ai/crypto-pulse/issues/352",
            "html_url": "https://github.com/8ft0-ai/crypto-pulse/issues/352#issuecomment-9001",
            "user": {"login": core.ACTOR_LOGIN, "id": core.ACTOR_USER_ID},
        },
    }


def ruleset() -> dict[str, object]:
    return {
        "id": 20623136,
        "name": "IssueOps immutable execution tags",
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


def dispatcher_run(**updates: object) -> dict[str, object]:
    value: dict[str, object] = {
        "id": DISPATCHER_RUN_ID,
        "run_attempt": 1,
        "event": "issue_comment",
        "head_sha": SHA,
        "path": core.DISPATCHER_WORKFLOW_PATH,
        "head_branch": "main",
        "actor": {"id": core.ACTOR_USER_ID, "login": core.ACTOR_LOGIN},
        "triggering_actor": {
            "id": core.ACTOR_USER_ID,
            "login": core.ACTOR_LOGIN,
        },
        "repository": {"full_name": core.REPOSITORY},
    }
    value.update(updates)
    return value


def attestation_page_url(digest: str, page: int) -> str:
    query = urllib.parse.urlencode(
        {
            "predicate_type": core.PREDICATE_TYPE,
            "per_page": 100,
            "page": page,
        }
    )
    return (
        f"https://api.github.com/repos/{core.REPOSITORY}/attestations/"
        f"sha256:{digest}?{query}"
    )


def verified_payload(
    *,
    item: dict[str, object] | None = None,
    source_sha: str = SHA,
) -> list[dict[str, object]]:
    res = resolution()
    if item is not None:
        res = core.Resolution(
            record=item,
            source_sha=source_sha,
            record_sha256=core.sha256_bytes(core.canonical_json_bytes(item)),
            comment_body_sha256=core.sha256_text(str(item["command"])),
            fixed_inputs_sha256=core.sha256_bytes(
                core.canonical_json_bytes(item["fixed_inputs"])
            ),
            execution_tag=f"issueops/dispatch/{AUTH_ID}--sha-{source_sha}",
            execution_ref=f"refs/tags/issueops/dispatch/{AUTH_ID}--sha-{source_sha}",
        )
    subject = protected_dispatch.canonical_subject_main(
        resolution=res, target_run={"id": RUN_ID}
    )
    predicate = protected_dispatch.canonical_predicate_main(
        resolution=res,
        event=event(),
        dispatcher_run_id=DISPATCHER_RUN_ID,
        dispatcher_run_attempt=1,
        target_run={"id": RUN_ID},
    )
    certificate = {
        "issuer": legacy_guard.EXPECTED_OIDC_ISSUER,
        "subjectAlternativeName": legacy_guard.EXPECTED_SIGNER_URI,
        "githubWorkflowTrigger": "issue_comment",
        "githubWorkflowSHA": source_sha,
        "githubWorkflowRepository": core.REPOSITORY,
        "githubWorkflowRef": legacy_guard.EXPECTED_SOURCE_REF,
        "buildSignerURI": legacy_guard.EXPECTED_SIGNER_URI,
        "buildSignerDigest": source_sha,
        "runnerEnvironment": "github-hosted",
        "sourceRepositoryURI": legacy_guard.EXPECTED_SOURCE_URI,
        "sourceRepositoryDigest": source_sha,
        "sourceRepositoryRef": legacy_guard.EXPECTED_SOURCE_REF,
        "sourceRepositoryIdentifier": str(core.REPOSITORY_ID),
        "sourceRepositoryOwnerIdentifier": str(core.REPOSITORY_OWNER_ID),
        "buildConfigURI": legacy_guard.EXPECTED_SIGNER_URI,
        "buildConfigDigest": source_sha,
        "buildTrigger": "issue_comment",
        "runInvocationURI": (
            f"https://github.com/{core.REPOSITORY}/actions/runs/"
            f"{DISPATCHER_RUN_ID}/attempts/1"
        ),
    }
    return [
        {
            "verificationResult": {
                "signature": {"certificate": certificate},
                "verifiedTimestamps": [{"source": "test"}],
                "statement": {
                    "predicateType": core.PREDICATE_TYPE,
                    "subject": [
                        {
                            "name": "dispatch-subject.json",
                            "digest": {
                                "sha256": core.sha256_bytes(
                                    core.canonical_json_bytes(subject)
                                )
                            },
                        }
                    ],
                    "predicate": predicate,
                },
            }
        }
    ]


class DispatchAPI:
    def __init__(self, *, run: dict[str, object] | None = None) -> None:
        self.created = False
        self.dispatches = 0
        self.run = run or target_run()

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
        self.workflow_id = workflow_id
        self.fixed_inputs = fixed_inputs
        self.authorisation_id = authorisation_id
        return {"workflow_run_id": RUN_ID, "run_url": "api", "html_url": "html"}

    def get_run_attempt(self, run_id: int, attempt: int = 1) -> dict[str, object]:
        return copy.deepcopy(self.run)


class TrustedMainDispatchTests(unittest.TestCase):
    def test_consumption_tag_is_retained_but_target_dispatch_is_main(self) -> None:
        api = DispatchAPI()
        result = protected_dispatch.consume_and_dispatch_main(
            api=api, event=event(), resolution=resolution()
        )
        self.assertEqual(result["workflow_run_id"], RUN_ID)
        self.assertEqual(api.dispatches, 1)
        self.assertEqual(api.authorisation_id, AUTH_ID)
        self.assertEqual(api.fixed_inputs, {})

    def test_main_sha_or_ref_mismatch_rejects_after_one_dispatch(self) -> None:
        for changed in (
            target_run(head_sha=OTHER_SHA),
            target_run(head_branch="issueops/dispatch/evil"),
        ):
            api = DispatchAPI(run=changed)
            with self.subTest(changed=changed), self.assertRaises(core.ContractError):
                protected_dispatch.consume_and_dispatch_main(
                    api=api, event=event(), resolution=resolution()
                )
            self.assertEqual(api.dispatches, 1)

    def test_dispatch_api_uses_main_and_reserved_authorisation_input(self) -> None:
        class API(protected_dispatch.GitHubAPI):
            def __init__(self) -> None:
                pass

            def _request(self, method, path, *, body=None, expected=(200,)):
                self.request = (method, path, body, expected)
                return 200, {
                    "workflow_run_id": RUN_ID,
                    "run_url": "api",
                    "html_url": "html",
                }

        api = API()
        api.dispatch_main_once(123, {"x": "y"}, AUTH_ID)
        self.assertEqual(api.request[2]["ref"], "main")
        self.assertEqual(
            api.request[2]["inputs"][protected_dispatch.AUTHORISATION_INPUT],
            AUTH_ID,
        )
        with self.assertRaises(core.ContractError):
            api.dispatch_main_once(
                123,
                {protected_dispatch.AUTHORISATION_INPUT: "evil"},
                AUTH_ID,
            )

    def test_receipt_distinguishes_consumption_ref_from_target_ref(self) -> None:
        subject = protected_dispatch.canonical_subject_main(
            resolution=resolution(), target_run={"id": RUN_ID}
        )
        predicate = protected_dispatch.canonical_predicate_main(
            resolution=resolution(),
            event=event(),
            dispatcher_run_id=DISPATCHER_RUN_ID,
            dispatcher_run_attempt=1,
            target_run={"id": RUN_ID},
        )
        self.assertTrue(subject["execution_ref"].startswith("refs/tags/issueops/"))
        self.assertEqual(subject["target_ref"], "refs/heads/main")
        self.assertEqual(predicate["target_ref"], "refs/heads/main")


class AvailabilityAndPaginationTests(unittest.TestCase):
    def test_bounded_wait_accepts_eventual_clean_appearance(self) -> None:
        class API:
            def __init__(self) -> None:
                self.calls = 0

            def list_attestations(self, _: str):
                self.calls += 1
                return [] if self.calls < 3 else [{"bundle_url": "https://x"}]

        sleeps: list[float] = []
        api = API()
        result = guard.wait_for_attestations(
            api, "d" * 64, sleep_fn=sleeps.append
        )
        self.assertEqual(len(result), 1)
        self.assertEqual(api.calls, 3)
        self.assertEqual(sleeps, [5, 5])

    def test_bounded_wait_rejects_after_exact_bound(self) -> None:
        class API:
            calls = 0

            def list_attestations(self, _: str):
                self.calls += 1
                return []

        api = API()
        sleeps: list[float] = []
        with self.assertRaisesRegex(legacy_guard.GuardError, "bounded wait"):
            guard.wait_for_attestations(
                api, "d" * 64, sleep_fn=sleeps.append
            )
        self.assertEqual(api.calls, 12)
        self.assertEqual(len(sleeps), 11)

    def test_authoritative_attestation_pagination_is_exhaustive(self) -> None:
        digest = "a" * 64

        class API(legacy_guard.GitHubReadAPI):
            def __init__(self) -> None:
                self.repository = core.REPOSITORY
                self.base = f"https://api.github.com/repos/{core.REPOSITORY}"
                self.token = "unused"
                self.calls = 0

            def _request_url(self, url: str):
                self.calls += 1
                if self.calls == 1:
                    return (
                        {"attestations": [{"bundle_url": "https://one"}]},
                        {"Link": f'<{attestation_page_url(digest, 2)}>; rel="next"'},
                    )
                return (
                    {"attestations": [{"bundle_url": "https://two"}]},
                    {},
                )

        api = API()
        items = api.list_attestations(digest)
        self.assertEqual(
            [x["bundle_url"] for x in items],
            ["https://one", "https://two"],
        )
        self.assertEqual(api.calls, 2)

    def test_pagination_loop_and_off_domain_next_fail_closed(self) -> None:
        with self.assertRaises(legacy_guard.GuardError):
            legacy_guard._next_link(
                '<https://evil.example/page=2>; rel="next"'
            )

        digest = "a" * 64
        loop_url = attestation_page_url(digest, 2)

        class LoopAPI(legacy_guard.GitHubReadAPI):
            def __init__(self) -> None:
                self.repository = core.REPOSITORY
                self.base = f"https://api.github.com/repos/{core.REPOSITORY}"
                self.token = "unused"

            def _request_url(self, url: str):
                return (
                    {"attestations": []},
                    {"Link": f'<{loop_url}>; rel="next"'},
                )

        with self.assertRaisesRegex(legacy_guard.GuardError, "loop"):
            LoopAPI().list_attestations(digest)


class CertificateAndReceiptTests(unittest.TestCase):
    def test_valid_receipt_binds_main_target_and_exact_dispatcher_actor(self) -> None:
        result = guard.verify_gh_result_main(
            verified_payload(),
            resolution=resolution(),
            target_run_id=RUN_ID,
            run_lookup=lambda _: dispatcher_run(),
        )
        self.assertEqual(result, DISPATCHER_RUN_ID)

    def test_wrong_signer_later_sha_actor_and_predicate_cannot_substitute(self) -> None:
        cases = []

        payload = verified_payload()
        payload[0]["verificationResult"]["signature"]["certificate"][
            "subjectAlternativeName"
        ] = "https://github.com/8ft0-ai/crypto-pulse/.github/workflows/evil.yml@refs/heads/main"
        cases.append((payload, dispatcher_run()))

        payload = verified_payload()
        payload[0]["verificationResult"]["signature"]["certificate"][
            "sourceRepositoryDigest"
        ] = OTHER_SHA
        cases.append((payload, dispatcher_run()))

        payload = verified_payload()
        cases.append((payload, dispatcher_run(actor={"id": 42, "login": core.ACTOR_LOGIN})))

        payload = verified_payload()
        payload[0]["verificationResult"]["statement"]["predicate"]["actor_user_id"] = 42
        cases.append((payload, dispatcher_run()))

        for payload, run in cases:
            with self.subTest(payload=payload), self.assertRaises(legacy_guard.GuardError):
                guard.verify_gh_result_main(
                    payload,
                    resolution=resolution(),
                    target_run_id=RUN_ID,
                    run_lookup=lambda _, run=run: run,
                )

    def test_malformed_verifier_output_fails_closed(self) -> None:
        for value in ({}, [], [{"verificationResult": {}}]):
            with self.subTest(value=value), self.assertRaises(legacy_guard.GuardError):
                guard.verify_gh_result_main(
                    value,
                    resolution=resolution(),
                    target_run_id=RUN_ID,
                    run_lookup=lambda _: dispatcher_run(),
                )

    def test_wrong_asset_checksum_is_rejected_before_binary_use(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / legacy_guard.PINNED_GH_ASSET
            path.write_bytes(b"not-the-pinned-release")
            with self.assertRaisesRegex(legacy_guard.GuardError, "SHA-256"):
                guard.verify_asset_checksum(path)

    def test_pinned_version_rejects_other_gh(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "gh"
            path.write_text("#!/bin/sh\necho 'gh version 2.96.0 (test)'\n")
            path.chmod(0o755)
            with self.assertRaisesRegex(legacy_guard.GuardError, "version"):
                legacy_guard.verify_pinned_gh(path)


class EndToEndGuardPolicyTests(unittest.TestCase):
    class API:
        def __init__(self, count: int = 1) -> None:
            self.attestations = [
                {"bundle_url": f"https://bundles.example/{n}"} for n in range(count)
            ]

        def get_tag(self, _: str):
            return tag()

        def get_ruleset(self, _: int):
            return ruleset()

        def list_attestations(self, _: str):
            return self.attestations

        def fetch_bundle(self, _: str):
            return b"{}\n"

        def get_run_attempt(self, _: int):
            return dispatcher_run()

    def repository(self, root: Path) -> None:
        (root / ".github/workflows").mkdir(parents=True)
        (root / ".github/issueops-workflow-dispatch.yml").write_text(
            json.dumps({"schema_version": 2, "authorisations": [record()]})
        )
        (root / legacy_guard.TARGET_WORKFLOW_PATH).write_bytes(TARGET_BYTES)
        (root / core.DISPATCHER_WORKFLOW_PATH).write_bytes(DISPATCHER_BYTES)

    def call(self, root: Path, api, **updates):
        args = {
            "repository_root": root,
            "authorisation_id": AUTH_ID,
            "github_ref": "refs/heads/main",
            "github_sha": SHA,
            "workflow_sha": SHA,
            "run_id": RUN_ID,
            "run_attempt": 1,
            "repository": core.REPOSITORY,
            "token": "unused",
            "gh_binary": root / "gh",
            "now": NOW,
            "api": api,
            "sleep_fn": lambda _: None,
        }
        args.update(updates)
        return guard.execute_guard(**args)

    def test_tag_sourced_or_rerun_target_is_rejected_before_external_proof(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for updates in (
                {"github_ref": resolution().execution_ref},
                {"run_attempt": 2},
            ):
                with self.subTest(updates=updates), self.assertRaises(legacy_guard.GuardError):
                    self.call(root, self.API(), **updates)

    def test_invalid_plus_valid_candidate_accepts_only_one_qualifying_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.repository(root)
            api = self.API(count=2)
            with mock.patch.object(legacy_guard, "verify_pinned_gh"), mock.patch.object(
                legacy_guard,
                "run_gh_verify",
                side_effect=[None, verified_payload()],
            ):
                result = self.call(root, api)
            self.assertEqual(result["dispatcher_run_id"], DISPATCHER_RUN_ID)

    def test_duplicate_valid_receipts_reject(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.repository(root)
            api = self.API(count=2)
            with mock.patch.object(legacy_guard, "verify_pinned_gh"), mock.patch.object(
                legacy_guard,
                "run_gh_verify",
                side_effect=[verified_payload(), verified_payload()],
            ):
                with self.assertRaisesRegex(legacy_guard.GuardError, "exactly one"):
                    self.call(root, api)

    def test_verified_canonical_signer_conflict_rejects_even_with_valid_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.repository(root)
            api = self.API(count=2)
            conflicting = verified_payload()
            conflicting[0]["verificationResult"]["statement"]["predicate"][
                "target_run_id"
            ] = RUN_ID + 1
            with mock.patch.object(legacy_guard, "verify_pinned_gh"), mock.patch.object(
                legacy_guard,
                "run_gh_verify",
                side_effect=[verified_payload(), conflicting],
            ):
                with self.assertRaisesRegex(legacy_guard.GuardError, "conflicts"):
                    self.call(root, api)


class WorkflowBoundaryTests(unittest.TestCase):
    def test_target_workflow_is_trusted_main_and_receipt_gated(self) -> None:
        target = (
            Path(__file__).resolve().parents[1]
            / ".github/workflows/governed-gpt-oss-quality-comparison.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("issueops_authorisation_id:", target)
        self.assertIn("refs/heads/main", target)
        self.assertIn("issueops_dispatch.target_guard_main guard", target)
        self.assertNotIn("issueops_dispatch.target_guard \\", target)
        guard_text = target.split("  prepare:", 1)[0]
        compare_text = target.split("  compare:", 1)[1]
        self.assertNotIn("OPENROUTER_API_KEY", guard_text)
        self.assertNotIn("environment: governed-llm-dry-run", guard_text)
        self.assertIn("needs.guard.result == 'success'", compare_text)
        self.assertIn("environment: governed-llm-dry-run", compare_text)

    def test_dispatcher_consumes_tag_but_dispatches_via_trusted_main_adapter(self) -> None:
        dispatcher = (
            Path(__file__).resolve().parents[1]
            / ".github/workflows/issueops-workflow-dispatch.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("issueops_dispatch.protected_dispatch consume", dispatcher)
        self.assertIn(
            "issueops_dispatch.protected_dispatch prepare-attestation", dispatcher
        )
        self.assertNotIn("issueops_dispatch.runner consume \\", dispatcher)
        self.assertIn("Target ref: \\`refs/heads/main\\`", dispatcher)


if __name__ == "__main__":
    unittest.main()
