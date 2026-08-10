from __future__ import annotations

import copy
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from issueops_dispatch import target_guard as guard
from issueops_dispatch.core import (
    ATTESTATION_SCHEMA,
    DISPATCHER_WORKFLOW_PATH,
    PREDICATE_TYPE,
    REPOSITORY,
    REPOSITORY_ID,
    REPOSITORY_OWNER_ID,
    canonical_json_bytes,
    canonical_subject,
    sha256_bytes,
    sha256_text,
)

SHA = "a" * 40
AUTH_ID = "phase9-quality-v1"
EXECUTION_REF = f"refs/tags/issueops/dispatch/{AUTH_ID}--sha-{SHA}"
RUN_ID = 123456789
DISPATCHER_RUN_ID = 987654321
NOW = datetime(2026, 8, 10, 11, 0, tzinfo=timezone.utc)


def record_for(workflow_bytes: bytes) -> dict[str, object]:
    return {
        "authorisation_id": AUTH_ID,
        "governing_issue": 352,
        "command": "/run-phase9-quality-v1",
        "actor_login": "8ft0-ai",
        "actor_user_id": 130460431,
        "required_author_association": "OWNER",
        "target_workflow_id": guard.TARGET_WORKFLOW_ID,
        "target_workflow_path": guard.TARGET_WORKFLOW_PATH,
        "target_ref_policy": "consumed_execution_tag_v1",
        "target_workflow_sha256": sha256_bytes(workflow_bytes),
        "fixed_inputs": {},
        "maximum_dispatch_attempts": 1,
        "enabled": True,
        "not_before": "2026-08-10T10:00:00Z",
        "expires_at": "2026-08-11T10:00:00Z",
        "consumption_mechanism": "execution_tag_v1",
        "provenance_mechanism": "dispatch_attestation_v1",
        "attestation_predicate_type": PREDICATE_TYPE,
        "dispatcher_workflow_path": DISPATCHER_WORKFLOW_PATH,
        "dispatcher_workflow_sha256": "b" * 64,
        "execution_tag_ruleset_id": guard.RULESET_ID,
        "execution_tag_ruleset_name": guard.RULESET_NAME,
        "purpose": "one protected Phase 9 comparison",
    }


def ruleset() -> dict[str, object]:
    return {
        "id": guard.RULESET_ID,
        "name": guard.RULESET_NAME,
        "target": "tag",
        "enforcement": "active",
        "conditions": {
            "ref_name": {
                "include": ["refs/tags/issueops/dispatch/*"],
                "exclude": [],
            }
        },
        "rules": [{"type": "update"}, {"type": "deletion"}],
    }


def dispatcher_run() -> dict[str, object]:
    return {
        "id": DISPATCHER_RUN_ID,
        "run_attempt": 1,
        "event": "issue_comment",
        "head_sha": SHA,
        "head_branch": "main",
        "path": DISPATCHER_WORKFLOW_PATH,
        "actor": {"id": 130460431, "login": "8ft0-ai"},
        "triggering_actor": {"id": 130460431, "login": "8ft0-ai"},
        "repository": {"full_name": REPOSITORY},
    }


def verified_payload(record: dict[str, object]) -> list[dict[str, object]]:
    resolution = guard.build_resolution(
        record=record, source_sha=SHA, execution_ref=EXECUTION_REF
    )
    expected_subject = canonical_subject(
        resolution=resolution, target_run={"id": RUN_ID}
    )
    predicate = {
        "schema": ATTESTATION_SCHEMA,
        "repository": REPOSITORY,
        "repository_id": REPOSITORY_ID,
        "repository_owner_id": REPOSITORY_OWNER_ID,
        "authorisation_id": AUTH_ID,
        "authorisation_sha": SHA,
        "authorisation_record_sha256": resolution.record_sha256,
        "triggering_issue": 352,
        "triggering_comment_id": 12345,
        "triggering_comment_body_sha256": sha256_text(
            str(record["command"])
        ),
        "actor_login": "8ft0-ai",
        "actor_user_id": 130460431,
        "required_author_association": "OWNER",
        "execution_ref": EXECUTION_REF,
        "dispatcher_workflow_path": DISPATCHER_WORKFLOW_PATH,
        "dispatcher_workflow_sha": SHA,
        "dispatcher_run_id": DISPATCHER_RUN_ID,
        "dispatcher_run_attempt": 1,
        "target_workflow_id": guard.TARGET_WORKFLOW_ID,
        "target_workflow_path": guard.TARGET_WORKFLOW_PATH,
        "target_run_id": RUN_ID,
        "target_ref": EXECUTION_REF,
        "target_sha": SHA,
        "target_event": "workflow_dispatch",
        "fixed_inputs_sha256": resolution.fixed_inputs_sha256,
    }
    certificate = {
        "issuer": guard.EXPECTED_OIDC_ISSUER,
        "subjectAlternativeName": guard.EXPECTED_SIGNER_URI,
        "githubWorkflowTrigger": "issue_comment",
        "githubWorkflowSHA": SHA,
        "githubWorkflowRepository": REPOSITORY,
        "githubWorkflowRef": "refs/heads/main",
        "buildSignerURI": guard.EXPECTED_SIGNER_URI,
        "buildSignerDigest": SHA,
        "runnerEnvironment": "github-hosted",
        "sourceRepositoryURI": "https://github.com/8ft0-ai/crypto-pulse",
        "sourceRepositoryDigest": SHA,
        "sourceRepositoryRef": "refs/heads/main",
        "sourceRepositoryIdentifier": str(REPOSITORY_ID),
        "sourceRepositoryOwnerIdentifier": str(REPOSITORY_OWNER_ID),
        "buildConfigURI": guard.EXPECTED_SIGNER_URI,
        "buildConfigDigest": SHA,
        "buildTrigger": "issue_comment",
        "runInvocationURI": (
            "https://github.com/8ft0-ai/crypto-pulse/actions/runs/"
            f"{DISPATCHER_RUN_ID}/attempts/1"
        ),
    }
    return [
        {
            "verificationResult": {
                "signature": {"certificate": certificate},
                "verifiedTimestamps": [{"type": "Tlog"}],
                "statement": {
                    "subject": [
                        {
                            "name": "dispatch-subject.json",
                            "digest": {
                                "sha256": sha256_bytes(
                                    canonical_json_bytes(expected_subject)
                                )
                            },
                        }
                    ],
                    "predicateType": PREDICATE_TYPE,
                    "predicate": predicate,
                },
            }
        }
    ]


class FakeAPI:
    def __init__(self, *, attestations: list[dict[str, object]] | None = None) -> None:
        self.attestations = (
            [{"bundle_url": "https://example.invalid/bundle.json"}]
            if attestations is None
            else attestations
        )
        self.run = dispatcher_run()
        self.rule = ruleset()
        self.tag = {
            "ref": EXECUTION_REF,
            "object": {"type": "commit", "sha": SHA},
        }

    def get_tag(self, _: str) -> dict[str, object]:
        return self.tag

    def get_ruleset(self, _: int) -> dict[str, object]:
        return self.rule

    def list_attestations(self, _: str) -> list[dict[str, object]]:
        return self.attestations

    def fetch_bundle(self, _: str) -> bytes:
        return b"{}\n"

    def get_run_attempt(self, _: int) -> dict[str, object]:
        return self.run


class IssueOpsTargetGuardTests(unittest.TestCase):
    def test_execution_ref_grammar_is_exact(self) -> None:
        self.assertEqual(guard.parse_execution_ref(EXECUTION_REF), (AUTH_ID, SHA))
        for invalid in (
            "refs/heads/main",
            f"refs/tags/issueops/dispatch/{AUTH_ID}--sha-{'A' * 40}",
            f"refs/tags/issueops/dispatch/a/b--sha-{SHA}",
            f"refs/tags/issueops/dispatch/{AUTH_ID}--sha-{SHA}/extra",
        ):
            with self.assertRaises(guard.GuardError):
                guard.parse_execution_ref(invalid)

    def test_tag_must_be_lightweight_and_exact_sha(self) -> None:
        guard.verify_tag_ref(
            {"ref": EXECUTION_REF, "object": {"type": "commit", "sha": SHA}},
            execution_ref=EXECUTION_REF,
            source_sha=SHA,
        )
        for changed in (
            {"ref": EXECUTION_REF, "object": {"type": "tag", "sha": SHA}},
            {
                "ref": EXECUTION_REF,
                "object": {"type": "commit", "sha": "b" * 40},
            },
        ):
            with self.assertRaises(guard.GuardError):
                guard.verify_tag_ref(
                    changed, execution_ref=EXECUTION_REF, source_sha=SHA
                )

    def test_ruleset_requires_exact_v1_runtime_semantics(self) -> None:
        record = record_for(b"workflow")
        guard.verify_ruleset(ruleset(), record)
        changed = ruleset()
        changed["rules"] = [
            {"type": "update"},
            {"type": "deletion"},
            {"type": "creation"},
        ]
        with self.assertRaises(guard.GuardError):
            guard.verify_ruleset(changed, record)

    def test_certificate_run_invocation_is_exact_attempt_one(self) -> None:
        payload = verified_payload(record_for(b"workflow"))
        cert = payload[0]["verificationResult"]["signature"]["certificate"]
        self.assertEqual(guard.verify_certificate(cert, source_sha=SHA), DISPATCHER_RUN_ID)
        for uri in (
            f"https://github.com/8ft0-ai/crypto-pulse/actions/runs/{DISPATCHER_RUN_ID}/attempts/2",
            f"https://github.com/other/repo/actions/runs/{DISPATCHER_RUN_ID}/attempts/1",
            f"https://evil.example/actions/runs/{DISPATCHER_RUN_ID}/attempts/1",
        ):
            changed = dict(cert)
            changed["runInvocationURI"] = uri
            with self.assertRaises(guard.GuardError):
                guard.verify_certificate(changed, source_sha=SHA)

    def test_repository_owner_certificate_id_cannot_substitute_actor_proof(self) -> None:
        changed = dispatcher_run()
        changed["actor"] = {"id": REPOSITORY_OWNER_ID + 1, "login": "8ft0-ai"}
        with self.assertRaises(guard.GuardError):
            guard.verify_dispatcher_run(
                changed, dispatcher_run_id=DISPATCHER_RUN_ID, source_sha=SHA
            )

    def test_actor_and_triggering_actor_must_both_match(self) -> None:
        changed = dispatcher_run()
        changed["triggering_actor"] = {"id": 42, "login": "8ft0-ai"}
        with self.assertRaises(guard.GuardError):
            guard.verify_dispatcher_run(
                changed, dispatcher_run_id=DISPATCHER_RUN_ID, source_sha=SHA
            )

    def test_predicate_cannot_override_certificate_identity(self) -> None:
        record = record_for(b"workflow")
        payload = verified_payload(record)
        payload[0]["verificationResult"]["statement"]["predicate"][
            "actor_user_id"
        ] = 42
        resolution = guard.build_resolution(
            record=record, source_sha=SHA, execution_ref=EXECUTION_REF
        )
        with self.assertRaises(guard.GuardError):
            guard.verify_gh_result(
                payload,
                resolution=resolution,
                target_run_id=RUN_ID,
                run_lookup=lambda _: dispatcher_run(),
            )

    def test_valid_canonical_receipt_passes_full_pure_policy(self) -> None:
        record = record_for(b"workflow")
        resolution = guard.build_resolution(
            record=record, source_sha=SHA, execution_ref=EXECUTION_REF
        )
        result = guard.verify_gh_result(
            verified_payload(record),
            resolution=resolution,
            target_run_id=RUN_ID,
            run_lookup=lambda _: dispatcher_run(),
        )
        self.assertEqual(result, DISPATCHER_RUN_ID)

    def test_end_to_end_guard_fails_without_attestation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow = b"workflow-definition\n"
            (root / ".github/workflows").mkdir(parents=True)
            (root / ".github/workflows/governed-gpt-oss-quality-comparison.yml").write_bytes(
                workflow
            )
            record = record_for(workflow)
            (root / ".github/issueops-workflow-dispatch.yml").write_text(
                json.dumps({"schema_version": 2, "authorisations": [record]}),
                encoding="utf-8",
            )
            with self.assertRaises(guard.GuardError):
                guard.execute_guard(
                    repository_root=root,
                    github_ref=EXECUTION_REF,
                    github_sha=SHA,
                    workflow_sha=SHA,
                    run_id=RUN_ID,
                    run_attempt=1,
                    repository=REPOSITORY,
                    token="unused",
                    gh_binary=root / "missing-gh",
                    now=NOW,
                    api=FakeAPI(attestations=[]),
                )

    def test_end_to_end_guard_accepts_one_exact_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow = b"workflow-definition\n"
            (root / ".github/workflows").mkdir(parents=True)
            (root / ".github/workflows/governed-gpt-oss-quality-comparison.yml").write_bytes(
                workflow
            )
            record = record_for(workflow)
            (root / ".github/issueops-workflow-dispatch.yml").write_text(
                json.dumps({"schema_version": 2, "authorisations": [record]}),
                encoding="utf-8",
            )
            api = FakeAPI()
            with patch.object(guard, "verify_pinned_gh"), patch.object(
                guard, "run_gh_verify", return_value=verified_payload(record)
            ):
                result = guard.execute_guard(
                    repository_root=root,
                    github_ref=EXECUTION_REF,
                    github_sha=SHA,
                    workflow_sha=SHA,
                    run_id=RUN_ID,
                    run_attempt=1,
                    repository=REPOSITORY,
                    token="unused",
                    gh_binary=root / "fake-gh",
                    now=NOW,
                    api=api,
                )
            self.assertEqual(result["dispatcher_run_id"], DISPATCHER_RUN_ID)
            self.assertEqual(result["authorisation_id"], AUTH_ID)

    def test_conflicting_verified_receipt_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow = b"workflow-definition\n"
            (root / ".github/workflows").mkdir(parents=True)
            (root / ".github/workflows/governed-gpt-oss-quality-comparison.yml").write_bytes(
                workflow
            )
            record = record_for(workflow)
            (root / ".github/issueops-workflow-dispatch.yml").write_text(
                json.dumps({"schema_version": 2, "authorisations": [record]}),
                encoding="utf-8",
            )
            conflicting = verified_payload(record)
            conflicting[0]["verificationResult"]["statement"]["predicate"][
                "target_run_id"
            ] = RUN_ID + 1
            api = FakeAPI()
            with patch.object(guard, "verify_pinned_gh"), patch.object(
                guard, "run_gh_verify", return_value=conflicting
            ):
                with self.assertRaises(guard.GuardError):
                    guard.execute_guard(
                        repository_root=root,
                        github_ref=EXECUTION_REF,
                        github_sha=SHA,
                        workflow_sha=SHA,
                        run_id=RUN_ID,
                        run_attempt=1,
                        repository=REPOSITORY,
                        token="unused",
                        gh_binary=root / "fake-gh",
                        now=NOW,
                        api=api,
                    )

    def test_rerun_is_rejected_before_external_proof(self) -> None:
        with self.assertRaises(guard.GuardError):
            guard.execute_guard(
                repository_root=Path("."),
                github_ref=EXECUTION_REF,
                github_sha=SHA,
                workflow_sha=SHA,
                run_id=RUN_ID,
                run_attempt=2,
                repository=REPOSITORY,
                token="unused",
                gh_binary=Path("missing"),
                now=NOW,
                api=FakeAPI(),
            )


if __name__ == "__main__":
    unittest.main()
