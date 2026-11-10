from __future__ import annotations

import base64
import copy
import json
import subprocess
import tempfile
import unittest
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from issueops_dispatch import core, runner

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/issueops-workflow-dispatch.yml"
REGISTRY = ROOT / ".github/issueops-workflow-dispatch.yml"
SOURCE_SHA = "a" * 40
DISPATCHER_BYTES = b"name: dispatcher\n"
TARGET_BYTES = b"on:\n  workflow_dispatch:\npermissions:\n  contents: read\n"
NOW = datetime(2026, 8, 8, 7, 1, tzinfo=timezone.utc)


def record(**updates: object) -> dict[str, object]:
    item: dict[str, object] = {
        "authorisation_id": "phase9-once",
        "governing_issue": 352,
        "command": "/run-phase9-once",
        "actor_login": "8ft0-ai",
        "actor_user_id": 130460431,
        "required_author_association": "OWNER",
        "target_workflow_id": 328208073,
        "target_workflow_path": ".github/workflows/governed-gpt-oss-quality-comparison.yml",
        "target_ref_policy": "consumed_execution_tag_v1",
        "target_workflow_sha256": core.sha256_bytes(TARGET_BYTES),
        "fixed_inputs": {},
        "maximum_dispatch_attempts": 1,
        "enabled": True,
        "not_before": None,
        "expires_at": None,
        "consumption_mechanism": "execution_tag_v1",
        "provenance_mechanism": "dispatch_attestation_v1",
        "attestation_predicate_type": core.PREDICATE_TYPE,
        "dispatcher_workflow_path": core.DISPATCHER_WORKFLOW_PATH,
        "dispatcher_workflow_sha256": core.sha256_bytes(DISPATCHER_BYTES),
        "execution_tag_ruleset_id": 7654,
        "execution_tag_ruleset_name": "IssueOps immutable execution tags",
        "purpose": "test-only authorisation",
    }
    item.update(updates)
    return item


def registry(*records: dict[str, object]) -> dict[str, object]:
    return {"schema_version": 2, "authorisations": list(records)}


def event(**comment_updates: object) -> dict[str, object]:
    comment: dict[str, object] = {
        "id": 9001,
        "body": "/run-phase9-once",
        "author_association": "OWNER",
        "created_at": "2026-08-08T07:00:00Z",
        "updated_at": "2026-08-08T07:00:00Z",
        "issue_url": "https://api.github.com/repos/8ft0-ai/crypto-pulse/issues/352",
        "html_url": "https://github.com/8ft0-ai/crypto-pulse/issues/352#issuecomment-9001",
        "user": {"login": "8ft0-ai", "id": 130460431},
    }
    comment.update(comment_updates)
    return {"action": "created", "issue": {"number": 352}, "comment": comment}


def resolve(
    item: dict[str, object] | None = None,
    *,
    parent: dict[str, object] | None = None,
) -> core.Resolution:
    result = core.resolve_event(
        event=event(),
        registry=registry(item or record()),
        parent_registry=parent or registry(),
        source_sha=SOURCE_SHA,
        dispatcher_workflow_bytes=DISPATCHER_BYTES,
        run_attempt=1,
        now=NOW,
    )
    assert result is not None
    return result


def workflow_response() -> dict[str, object]:
    return {
        "id": 328208073,
        "path": ".github/workflows/governed-gpt-oss-quality-comparison.yml",
        "state": "active",
    }


def contents_response(data: bytes = TARGET_BYTES) -> dict[str, object]:
    return {
        "type": "file",
        "encoding": "base64",
        "content": base64.b64encode(data).decode(),
    }


def ruleset_response() -> dict[str, object]:
    return {
        "id": 7654,
        "name": "IssueOps immutable execution tags",
        "target": "tag",
        "enforcement": "active",
        "conditions": {
            "ref_name": {"include": [core.RULESET_REF_INCLUDE], "exclude": []}
        },
        "rules": [{"type": "update"}, {"type": "deletion"}],
    }


def target_run(**updates: object) -> dict[str, object]:
    value: dict[str, object] = {
        "id": 555,
        "workflow_id": 328208073,
        "path": ".github/workflows/governed-gpt-oss-quality-comparison.yml",
        "event": "workflow_dispatch",
        "run_attempt": 1,
        "head_sha": SOURCE_SHA,
        "head_branch": "issueops/dispatch/phase9-once--sha-" + SOURCE_SHA,
        "repository": {
            "id": 1233729904,
            "full_name": "8ft0-ai/crypto-pulse",
        },
    }
    value.update(updates)
    return value


class ResolutionTests(unittest.TestCase):
    def call(
        self,
        payload: dict[str, object] | None = None,
        *,
        item: dict[str, object] | None = None,
        parent: dict[str, object] | None = None,
        attempt: int = 1,
        workflow: bytes = DISPATCHER_BYTES,
        now: datetime = NOW,
    ) -> core.Resolution | None:
        return core.resolve_event(
            event=payload or event(),
            registry=registry(item or record()),
            parent_registry=parent or registry(),
            source_sha=SOURCE_SHA,
            dispatcher_workflow_bytes=workflow,
            run_attempt=attempt,
            now=now,
        )

    def test_registry_schema_and_stdlib_json(self) -> None:
        registry_data = json.loads(REGISTRY.read_text())
        self.assertEqual(registry_data["schema_version"], core.SCHEMA_VERSION)
        self.assertIsInstance(registry_data["authorisations"], list)
        core.validate_registry(registry_data, now=NOW)
        runtime = (ROOT / "issueops_dispatch/runner.py").read_text()
        self.assertNotIn("import yaml", runtime)
        self.assertNotIn("yaml.safe_load", runtime)

    def test_valid_new_authorisation_resolves_exact_tag(self) -> None:
        self.assertEqual(
            resolve().execution_ref,
            "refs/tags/issueops/dispatch/phase9-once--sha-" + SOURCE_SHA,
        )

    def test_modified_authorisation_at_exact_source_passes(self) -> None:
        self.assertIsNotNone(self.call(parent=registry(record(command="/old"))))

    def test_stale_unchanged_authorisation_rejects(self) -> None:
        with self.assertRaisesRegex(core.ContractError, "not added or modified"):
            self.call(parent=registry(record()))

    def test_wrong_issue_actor_login_id_association_pr_and_partial_reject(self) -> None:
        cases = []
        p = event()
        p["issue"]["number"] = 351
        cases.append(p)
        cases.append(event(user={"login": "8ft0-ai", "id": 7}))
        cases.append(event(user={"login": "renamed", "id": 130460431}))
        cases.append(event(author_association="MEMBER"))
        p = event()
        p["issue"]["pull_request"] = {"url": "x"}
        cases.append(p)
        cases.append(event(body="/run-phase9"))
        for payload in cases:
            with self.subTest(payload=payload):
                self.assertIsNone(self.call(payload))

    def test_disabled_expired_and_future_reject(self) -> None:
        self.assertIsNone(self.call(item=record(enabled=False)))
        self.assertIsNone(self.call(item=record(expires_at="2026-08-08T06:00:00Z")))
        self.assertIsNone(self.call(item=record(not_before="2026-08-08T08:00:00Z")))

    def test_invalid_window_rejects(self) -> None:
        with self.assertRaisesRegex(core.ContractError, "earlier"):
            self.call(
                item=record(
                    not_before="2026-08-08T08:00:00Z",
                    expires_at="2026-08-08T07:00:00Z",
                )
            )

    def test_rerun_rejects(self) -> None:
        with self.assertRaisesRegex(core.ContractError, "reruns"):
            self.call(attempt=2)

    def test_dispatcher_hash_drift_rejects(self) -> None:
        with self.assertRaisesRegex(core.ContractError, "workflow hash"):
            self.call(workflow=b"changed")

    def test_duplicate_matching_authorities_reject(self) -> None:
        with self.assertRaisesRegex(core.ContractError, "more than one"):
            core.resolve_event(
                event=event(),
                registry=registry(record(), record(authorisation_id="other")),
                parent_registry=registry(),
                source_sha=SOURCE_SHA,
                dispatcher_workflow_bytes=DISPATCHER_BYTES,
                run_attempt=1,
                now=NOW,
            )

    def test_missing_and_extra_schema_fields_fail_closed(self) -> None:
        missing = record()
        missing.pop("purpose")
        extra = record()
        extra["arbitrary_workflow"] = "evil.yml"
        for bad in (missing, extra):
            with self.assertRaisesRegex(core.ContractError, "schema mismatch"):
                core.validate_registry(registry(bad), now=NOW)

    def test_nested_fixed_input_injection_rejects(self) -> None:
        with self.assertRaisesRegex(core.ContractError, "JSON scalars"):
            core.validate_registry(
                registry(record(fixed_inputs={"x": {"workflow": "evil"}})), now=NOW
            )


class ParentAndCommentTests(unittest.TestCase):
    def test_parent_registry_is_read_from_exact_first_parent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            subprocess.run(
                ["git", "init"], cwd=repo, check=True, stdout=subprocess.DEVNULL
            )
            subprocess.run(
                ["git", "config", "user.email", "test@example.com"],
                cwd=repo,
                check=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test"], cwd=repo, check=True
            )
            path = repo / ".github/issueops-workflow-dispatch.yml"
            path.parent.mkdir()
            path.write_text(json.dumps(registry(record(command="/old"))))
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            subprocess.run(
                ["git", "commit", "-m", "parent"],
                cwd=repo,
                check=True,
                stdout=subprocess.DEVNULL,
            )
            path.write_text(json.dumps(registry(record())))
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            subprocess.run(
                ["git", "commit", "-m", "source"],
                cwd=repo,
                check=True,
                stdout=subprocess.DEVNULL,
            )
            sha = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=repo, text=True
            ).strip()
            old = Path.cwd()
            try:
                import os

                os.chdir(repo)
                parent = runner.load_parent_registry(
                    Path(".github/issueops-workflow-dispatch.yml"), sha
                )
            finally:
                os.chdir(old)
            self.assertEqual(parent["authorisations"][0]["command"], "/old")

    def test_parent_proof_failure_is_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            old = Path.cwd()
            try:
                import os

                os.chdir(tmp)
                with self.assertRaisesRegex(core.ContractError, "first parent"):
                    runner.load_parent_registry(Path("x"), SOURCE_SHA)
            finally:
                os.chdir(old)

    def test_edited_missing_relationship_and_missing_timestamps_reject(self) -> None:
        r = resolve()
        variants = []
        v = copy.deepcopy(event()["comment"])
        v["updated_at"] = "later"
        variants.append(v)
        v = copy.deepcopy(event()["comment"])
        v.pop("issue_url")
        variants.append(v)
        v = copy.deepcopy(event()["comment"])
        v["html_url"] = (
            "https://github.com/8ft0-ai/crypto-pulse/issues/351#issuecomment-9001"
        )
        variants.append(v)
        v = copy.deepcopy(event()["comment"])
        v.pop("created_at")
        variants.append(v)
        for live in variants:
            with self.subTest(live=live), self.assertRaises(core.ContractError):
                core.ensure_comment_unchanged(event(), live, r)


class RuntimeValidationTests(unittest.TestCase):
    def test_exact_ruleset_passes(self) -> None:
        runner.validate_runtime_ruleset(ruleset_response(), resolve())

    def test_ruleset_rule_and_condition_drift_rejects(self) -> None:
        variants = []
        v = ruleset_response()
        v["rules"] = [{"type": "deletion"}]
        variants.append(v)
        v = ruleset_response()
        v["rules"].append({"type": "creation"})
        variants.append(v)
        v = ruleset_response()
        v["conditions"]["ref_name"]["include"] = ["~ALL"]
        variants.append(v)
        v = ruleset_response()
        v["conditions"]["ref_name"]["include"] = ["issueops/dispatch/*"]
        variants.append(v)
        v = ruleset_response()
        v["conditions"]["ref_name"]["exclude"] = ["refs/tags/foo/*"]
        variants.append(v)
        v = ruleset_response()
        v["conditions"]["other"] = {}
        variants.append(v)
        for value in variants:
            with self.subTest(value=value), self.assertRaises(core.ContractError):
                runner.validate_runtime_ruleset(value, resolve())

    def test_missing_bypass_actors_is_not_interpreted(self) -> None:
        value = ruleset_response()
        value.pop("bypass_actors", None)
        runner.validate_runtime_ruleset(value, resolve())

    def test_target_workflow_hash_and_trigger_drift_reject(self) -> None:
        class API:
            def get_workflow(self, _: int):
                return workflow_response()

            def get_contents(self, path: str, ref: str):
                return contents_response(b"on:\n  push:\n")

        with self.assertRaises(core.ContractError):
            runner.validate_target_workflow(API(), resolve())
        bad = record(target_workflow_sha256="0" * 64)
        with self.assertRaises(core.ContractError):
            runner.validate_target_workflow(API(), resolve(bad))

    def test_target_run_must_match_path_attempt_event_ref_sha_and_id(self) -> None:
        changes = (
            {"path": "evil.yml"},
            {"run_attempt": 2},
            {"event": "issue_comment"},
            {"head_branch": "main"},
            {"head_sha": "b" * 40},
            {"workflow_id": 1},
        )
        for change in changes:
            with self.subTest(change=change), self.assertRaises(core.ContractError):
                runner.validate_target_run(target_run(**change), resolve())

    def test_target_run_requires_direct_id_and_exact_repository_identity(self) -> None:
        with self.assertRaisesRegex(core.ContractError, "direct dispatch identity"):
            runner.validate_target_run(
                target_run(id=556), resolve(), expected_run_id=555
            )
        with self.assertRaisesRegex(core.ContractError, "repository identity is missing"):
            missing = target_run()
            missing.pop("repository")
            runner.validate_target_run(missing, resolve(), expected_run_id=555)
        with self.assertRaisesRegex(core.ContractError, "repository identity mismatch"):
            runner.validate_target_run(
                target_run(
                    repository={
                        "id": 999,
                        "full_name": "8ft0-ai/other",
                    }
                ),
                resolve(),
                expected_run_id=555,
            )


class ConsumptionTests(unittest.TestCase):
    class API:
        def __init__(
            self,
            *,
            existing: bool = False,
            create_error: Exception | None = None,
            dispatch_response: dict[str, object] | None = None,
            rulesets: list[dict[str, object]] | None = None,
            workflows: list[dict[str, object]] | None = None,
            materialize_after_create: bool = True,
            created_tag: dict[str, object] | None = None,
            read_back_tag: dict[str, object] | None = None,
            tags_after_create: list[dict[str, object] | None] | None = None,
            run_response: dict[str, object] | None = None,
        ) -> None:
            self.existing = existing
            self.create_error = create_error
            self.dispatches = 0
            self.create_attempts = 0
            self.tag_reads = 0
            self.ruleset_reads = 0
            self.workflow_reads = 0
            self.create_attempted = False
            self.materialize_after_create = materialize_after_create
            self.created_tag = created_tag
            self.read_back_tag = read_back_tag
            self.tags_after_create = tags_after_create
            self.after_create_tag_reads = 0
            self.rulesets = rulesets or [ruleset_response(), ruleset_response()]
            self.workflows = workflows or [workflow_response(), workflow_response()]
            self.run_response = run_response or target_run()
            self.dispatch_response = (
                {"workflow_run_id": 555, "run_url": "api", "html_url": "html"}
                if dispatch_response is None
                else dispatch_response
            )

        @staticmethod
        def good_tag() -> dict[str, object]:
            return {
                "ref": resolve().execution_ref,
                "object": {"type": "commit", "sha": SOURCE_SHA},
            }

        def get_workflow(self, _: int):
            index = min(self.workflow_reads, len(self.workflows) - 1)
            self.workflow_reads += 1
            return copy.deepcopy(self.workflows[index])

        def get_contents(self, path: str, ref: str):
            return contents_response()

        def get_ruleset(self, _: int):
            index = min(self.ruleset_reads, len(self.rulesets) - 1)
            self.ruleset_reads += 1
            return copy.deepcopy(self.rulesets[index])

        def get_comment(self, _: int):
            return event()["comment"]

        def get_tag(self, _: str):
            self.tag_reads += 1
            if self.existing:
                return self.good_tag()
            if self.create_attempted and self.tags_after_create is not None:
                index = min(
                    self.after_create_tag_reads, len(self.tags_after_create) - 1
                )
                self.after_create_tag_reads += 1
                return copy.deepcopy(self.tags_after_create[index])
            if self.create_attempted and self.materialize_after_create:
                return self.read_back_tag or self.good_tag()
            return None

        def create_tag_once(self, *args):
            self.create_attempts += 1
            self.create_attempted = True
            if self.create_error:
                raise self.create_error
            return self.created_tag or self.good_tag()

        def dispatch_once(self, *args):
            self.dispatches += 1
            return self.dispatch_response

        def get_run_attempt(self, *_):
            return copy.deepcopy(self.run_response)

    def test_preexisting_tag_rejects_without_dispatch(self) -> None:
        api = self.API(existing=True)
        with self.assertRaisesRegex(core.ContractError, "already exists"):
            runner.consume_and_dispatch(api=api, event=event(), resolution=resolve())
        self.assertEqual(api.dispatches, 0)
        self.assertEqual(api.create_attempts, 0)

    def test_ambiguous_tag_creation_reconciles_existing_ref_without_dispatch(self) -> None:
        api = self.API(
            create_error=runner.AmbiguousGitHubResponse("lost create response")
        )
        with self.assertRaisesRegex(core.ContractError, "authority consumed"):
            runner.consume_and_dispatch(api=api, event=event(), resolution=resolve())
        self.assertEqual(api.create_attempts, 1)
        self.assertEqual(api.tag_reads, 2)
        self.assertEqual(api.dispatches, 0)

    def test_ambiguous_tag_creation_reconciles_absence_without_dispatch(self) -> None:
        api = self.API(
            create_error=runner.AmbiguousGitHubResponse("reset"),
            materialize_after_create=False,
        )
        with self.assertRaisesRegex(core.ContractError, "canonical ref absent"):
            runner.consume_and_dispatch(api=api, event=event(), resolution=resolve())
        self.assertEqual(api.create_attempts, 1)
        self.assertEqual(api.tag_reads, 2)
        self.assertEqual(api.dispatches, 0)

    def test_unverifiable_201_mapping_reconciles_existing_ref_without_dispatch(self) -> None:
        api = self.API(created_tag={"ref": resolve().execution_ref})
        with self.assertRaisesRegex(core.ContractError, "authority consumed"):
            runner.consume_and_dispatch(api=api, event=event(), resolution=resolve())
        self.assertEqual(api.create_attempts, 1)
        self.assertEqual(api.tag_reads, 2)
        self.assertEqual(api.dispatches, 0)

    def test_unverifiable_201_mapping_reconciles_absence_without_dispatch(self) -> None:
        api = self.API(
            created_tag={"ref": resolve().execution_ref},
            materialize_after_create=False,
        )
        with self.assertRaisesRegex(core.ContractError, "canonical ref absent"):
            runner.consume_and_dispatch(api=api, event=event(), resolution=resolve())
        self.assertEqual(api.create_attempts, 1)
        self.assertEqual(api.tag_reads, 2)
        self.assertEqual(api.dispatches, 0)

    def test_definitive_tag_create_failure_does_not_reconcile_or_dispatch(self) -> None:
        api = self.API(create_error=core.ContractError("HTTP 422"))
        with self.assertRaisesRegex(core.ContractError, "422"):
            runner.consume_and_dispatch(api=api, event=event(), resolution=resolve())
        self.assertEqual(api.create_attempts, 1)
        self.assertEqual(api.tag_reads, 1)
        self.assertEqual(api.dispatches, 0)

    def test_exact_create_readback_rechecks_ruleset_tag_target_and_target_workflow(self) -> None:
        api = self.API()
        result = runner.consume_and_dispatch(api=api, event=event(), resolution=resolve())
        self.assertEqual(api.dispatches, 1)
        self.assertEqual(api.ruleset_reads, 2)
        self.assertEqual(api.tag_reads, 3)
        self.assertEqual(api.workflow_reads, 2)
        self.assertEqual(result["workflow_run_id"], 555)

    def test_post_consumption_ruleset_drift_rejects_without_dispatch(self) -> None:
        drifted = ruleset_response()
        drifted["enforcement"] = "disabled"
        api = self.API(rulesets=[ruleset_response(), drifted])
        with self.assertRaisesRegex(core.ContractError, "not active"):
            runner.consume_and_dispatch(api=api, event=event(), resolution=resolve())
        self.assertEqual(api.create_attempts, 1)
        self.assertEqual(api.ruleset_reads, 2)
        self.assertEqual(api.dispatches, 0)

    def test_post_consumption_tag_disappearance_rejects_without_dispatch(self) -> None:
        api = self.API(tags_after_create=[self.API.good_tag(), None])
        with self.assertRaisesRegex(core.ContractError, "disappeared before dispatch"):
            runner.consume_and_dispatch(api=api, event=event(), resolution=resolve())
        self.assertEqual(api.create_attempts, 1)
        self.assertEqual(api.tag_reads, 3)
        self.assertEqual(api.dispatches, 0)

    def test_post_consumption_tag_target_drift_rejects_without_dispatch(self) -> None:
        bad = self.API.good_tag()
        bad["object"] = {"type": "commit", "sha": "b" * 40}
        api = self.API(tags_after_create=[self.API.good_tag(), bad])
        with self.assertRaisesRegex(core.ContractError, "authorised commit"):
            runner.consume_and_dispatch(api=api, event=event(), resolution=resolve())
        self.assertEqual(api.tag_reads, 3)
        self.assertEqual(api.dispatches, 0)

    def test_post_consumption_target_workflow_drift_rejects_without_dispatch(self) -> None:
        disabled = workflow_response()
        disabled["state"] = "disabled_manually"
        api = self.API(workflows=[workflow_response(), disabled])
        with self.assertRaisesRegex(core.ContractError, "not active"):
            runner.consume_and_dispatch(api=api, event=event(), resolution=resolve())
        self.assertEqual(api.workflow_reads, 2)
        self.assertEqual(api.create_attempts, 1)
        self.assertEqual(api.dispatches, 0)

    def test_tag_readback_mismatch_rejects_without_dispatch(self) -> None:
        bad = self.API.good_tag()
        bad["object"] = {"type": "commit", "sha": "b" * 40}
        api = self.API(read_back_tag=bad)
        with self.assertRaisesRegex(core.ContractError, "authorised commit"):
            runner.consume_and_dispatch(api=api, event=event(), resolution=resolve())
        self.assertEqual(api.dispatches, 0)
        self.assertEqual(api.ruleset_reads, 1)

    def test_direct_run_id_or_repository_mismatch_rejects_after_single_dispatch(self) -> None:
        variants = [
            target_run(id=556),
            target_run(repository={"id": 999, "full_name": "8ft0-ai/other"}),
        ]
        for run in variants:
            with self.subTest(run=run):
                api = self.API(run_response=run)
                with self.assertRaises(core.ContractError):
                    runner.consume_and_dispatch(
                        api=api, event=event(), resolution=resolve()
                    )
                self.assertEqual(api.dispatches, 1)

    def test_missing_direct_run_identity_is_not_inferred_or_retried(self) -> None:
        api = self.API(dispatch_response={})
        with self.assertRaisesRegex(core.ContractError, "direct run identity"):
            runner.consume_and_dispatch(api=api, event=event(), resolution=resolve())
        self.assertEqual(api.dispatches, 1)
        self.assertEqual(api.ruleset_reads, 2)


class TransportTests(unittest.TestCase):
    def test_timeout_urlerror_and_http_failures_are_single_attempt(self) -> None:
        api = runner.GitHubAPI("8ft0-ai/crypto-pulse", "token")
        failures = [urllib.error.URLError("reset")]
        for status in (400, 403, 500, 503):
            err = urllib.error.HTTPError(
                "https://api.github.com/x", status, "x", hdrs=None, fp=None
            )
            err.read = lambda: b'{"message":"failure"}'  # type: ignore[method-assign]
            failures.append(err)
        for failure in failures:
            with self.subTest(failure=failure), mock.patch(
                "urllib.request.urlopen", side_effect=failure
            ) as call:
                with self.assertRaises(core.ContractError):
                    api.dispatch_once(1, "tag", {})
                self.assertEqual(call.call_count, 1)

    def test_non_json_success_is_classified_ambiguous(self) -> None:
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.status = 201
        response.read.return_value = b"not-json"
        with mock.patch("urllib.request.urlopen", return_value=response):
            api = runner.GitHubAPI("8ft0-ai/crypto-pulse", "token")
            with self.assertRaises(runner.AmbiguousGitHubResponse):
                api.create_tag_once("refs/tags/x", SOURCE_SHA)


class ReceiptTests(unittest.TestCase):
    def test_subject_exact_fields_schema_and_no_audit_extras(self) -> None:
        subject = core.canonical_subject(resolution=resolve(), target_run=target_run())
        self.assertEqual(tuple(subject), core.SUBJECT_KEYS)
        self.assertEqual(subject["schema"], core.ATTESTATION_SCHEMA)
        self.assertNotIn("actor_user_id", subject)
        self.assertNotIn("dispatcher_run_id", subject)

    def test_predicate_has_schema_and_rich_bindings(self) -> None:
        p = core.canonical_predicate(
            resolution=resolve(),
            event=event(),
            dispatcher_run_id=777,
            dispatcher_run_attempt=1,
            target_run=target_run(),
        )
        self.assertEqual(tuple(p), core.PREDICATE_KEYS)
        self.assertEqual(p["schema"], "dispatch_attestation_v1")
        self.assertEqual(p["dispatcher_run_id"], 777)
        self.assertEqual(p["actor_user_id"], 130460431)
        self.assertEqual(p["target_event"], "workflow_dispatch")

    def test_canonical_subject_bytes_are_stable(self) -> None:
        subject = core.canonical_subject(resolution=resolve(), target_run=target_run())
        expected = (
            '{"authorisation_id":"phase9-once","authorisation_sha":"'
            + SOURCE_SHA
            + '","execution_ref":"refs/tags/issueops/dispatch/phase9-once--sha-'
            + SOURCE_SHA
            + '","repository":"8ft0-ai/crypto-pulse","repository_id":1233729904,'
            '"schema":"dispatch_attestation_v1","target_ref":"refs/tags/issueops/dispatch/phase9-once--sha-'
            + SOURCE_SHA
            + '","target_run_id":555,"target_sha":"'
            + SOURCE_SHA
            + '","target_workflow_id":328208073,"target_workflow_path":".github/workflows/governed-gpt-oss-quality-comparison.yml"}\n'
        ).encode()
        self.assertEqual(core.canonical_json_bytes(subject), expected)

    def test_signing_rerun_rejects(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, self.assertRaisesRegex(
            core.ContractError, "rerun"
        ):
            runner.write_attestation_inputs(
                event=event(),
                resolution=resolve(),
                dispatcher_run_id=1,
                dispatcher_run_attempt=2,
                target_run=target_run(),
                output_dir=Path(tmp),
            )


class WorkflowStaticTests(unittest.TestCase):
    def test_listener_permissions_and_no_provider_boundary(self) -> None:
        text = WORKFLOW.read_text()
        self.assertIn("issue_comment:\n    types: [created]", text)
        self.assertIn("permissions: {}", text)
        self.assertNotIn("OPENROUTER_API_KEY", text)
        self.assertNotIn("governed-llm-dry-run", text)
        self.assertNotIn("environment:", text)

    def test_privileged_and_signing_permissions_are_separated(self) -> None:
        text = WORKFLOW.read_text()
        side = text.split("consume-and-dispatch:", 1)[1].split(
            "sign-dispatch-receipt:", 1
        )[0]
        sign = text.split("sign-dispatch-receipt:", 1)[1]
        self.assertIn("actions: write", side)
        self.assertIn("contents: write", side)
        self.assertIn("issues: read", side)
        self.assertIn("actions: read", sign)
        self.assertIn("contents: read", sign)
        self.assertIn("attestations: write", sign)
        self.assertIn("id-token: write", sign)
        self.assertNotIn("actions: write", sign)
        self.assertNotIn("contents: write", sign)
        self.assertNotIn("issues: read", sign)

    def test_every_external_action_is_full_sha_pinned_and_expected(self) -> None:
        text = WORKFLOW.read_text()
        uses = [
            line.strip().split("uses: ", 1)[1]
            for line in text.splitlines()
            if "uses: " in line
        ]
        self.assertGreaterEqual(len(uses), 3)
        import re

        for action in uses:
            self.assertRegex(action, r"^[^@]+@[0-9a-f]{40}$")
        self.assertIn(
            "actions/checkout@11d5960a326750d5838078e36cf38b85af677262", uses
        )
        self.assertIn(
            "actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065", uses
        )
        self.assertIn(
            "actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6", uses
        )

    def test_checkout_fetches_first_parent_and_runtime_has_no_network_package_install(
        self,
    ) -> None:
        text = WORKFLOW.read_text()
        runtime = (ROOT / "issueops_dispatch/runner.py").read_text()
        self.assertEqual(text.count("fetch-depth: 2"), 3)
        self.assertNotIn("fetch-depth: 1", text)
        self.assertNotIn("pip install", text)
        self.assertNotIn("import yaml", runtime)
        self.assertNotIn("yaml.safe_load", runtime)

    def test_runtime_exposes_only_one_ref_create_and_one_dispatch_write(self) -> None:
        text = (ROOT / "issueops_dispatch/runner.py").read_text()
        self.assertEqual(text.count('"/git/refs"'), 1)
        self.assertEqual(
            text.count('f"/actions/workflows/{workflow_id}/dispatches"'), 1
        )
        for prohibited in (
            '"PATCH",',
            '"DELETE",',
            "/rerun",
            "/cancel",
            "/enable",
            "/disable",
            "/git/refs/",
        ):
            self.assertNotIn(prohibited, text)


if __name__ == "__main__":
    unittest.main()
