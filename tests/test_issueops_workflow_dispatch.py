from __future__ import annotations

import base64
import copy
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import yaml

from issueops_dispatch import core
from issueops_dispatch import runner

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/issueops-workflow-dispatch.yml"
REGISTRY = ROOT / ".github/issueops-workflow-dispatch.yml"
SOURCE_SHA = "a" * 40
DISPATCHER_BYTES = b"name: dispatcher\n"
TARGET_BYTES = b"on:\n  workflow_dispatch:\npermissions:\n  contents: read\n"


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
        "html_url": "https://github.com/8ft0-ai/crypto-pulse/issues/352#issuecomment-9001",
        "user": {"login": "8ft0-ai", "id": 130460431},
    }
    comment.update(comment_updates)
    return {"action": "created", "issue": {"number": 352}, "comment": comment}


def resolution(item: dict[str, object] | None = None) -> core.Resolution:
    result = core.resolve_event(
        event=event(),
        registry=registry(item or record()),
        source_sha=SOURCE_SHA,
        dispatcher_workflow_bytes=DISPATCHER_BYTES,
        run_attempt=1,
        now=datetime(2026, 8, 8, 7, 1, tzinfo=timezone.utc),
    )
    assert result is not None
    return result


def workflow_response() -> dict[str, object]:
    return {
        "id": 328208073,
        "path": ".github/workflows/governed-gpt-oss-quality-comparison.yml",
        "state": "active",
    }


def contents_response() -> dict[str, object]:
    return {
        "type": "file",
        "encoding": "base64",
        "content": base64.b64encode(TARGET_BYTES).decode("ascii"),
    }


def ruleset_response() -> dict[str, object]:
    return {
        "id": 7654,
        "name": "IssueOps immutable execution tags",
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


def target_run(**updates: object) -> dict[str, object]:
    item: dict[str, object] = {
        "id": 555,
        "workflow_id": 328208073,
        "path": ".github/workflows/governed-gpt-oss-quality-comparison.yml",
        "event": "workflow_dispatch",
        "run_attempt": 1,
        "head_sha": SOURCE_SHA,
        "head_branch": "issueops/dispatch/phase9-once--sha-" + SOURCE_SHA,
    }
    item.update(updates)
    return item


class ResolutionTests(unittest.TestCase):
    def test_registry_is_empty_by_default(self) -> None:
        raw = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
        self.assertEqual(raw, {"schema_version": 2, "authorisations": []})

    def test_valid_created_owner_command_resolves_exact_tag(self) -> None:
        resolved = resolution()
        self.assertEqual(
            resolved.execution_ref,
            "refs/tags/issueops/dispatch/phase9-once--sha-" + SOURCE_SHA,
        )
        self.assertEqual(resolved.record["maximum_dispatch_attempts"], 1)

    def test_wrong_issue_rejects_without_side_effect_authority(self) -> None:
        payload = event()
        payload["issue"]["number"] = 351
        self.assertIsNone(self._resolve(payload))

    def test_wrong_actor_id_rejects(self) -> None:
        self.assertIsNone(self._resolve(event(user={"login": "8ft0-ai", "id": 7})))

    def test_wrong_actor_login_rejects(self) -> None:
        self.assertIsNone(self._resolve(event(user={"login": "renamed", "id": 130460431})))

    def test_wrong_association_rejects(self) -> None:
        self.assertIsNone(self._resolve(event(author_association="MEMBER")))

    def test_pr_comment_rejects(self) -> None:
        payload = event()
        payload["issue"]["pull_request"] = {"url": "x"}
        self.assertIsNone(self._resolve(payload))

    def test_partial_or_wrong_command_rejects(self) -> None:
        self.assertIsNone(self._resolve(event(body="/run-phase9")))

    def test_disabled_authorisation_rejects(self) -> None:
        self.assertIsNone(self._resolve(event(), item=record(enabled=False)))

    def test_expired_authorisation_rejects(self) -> None:
        self.assertIsNone(
            self._resolve(
                event(),
                item=record(expires_at="2026-08-08T06:00:00Z"),
                now=datetime(2026, 8, 8, 7, tzinfo=timezone.utc),
            )
        )

    def test_future_authorisation_rejects(self) -> None:
        self.assertIsNone(
            self._resolve(
                event(),
                item=record(not_before="2026-08-08T08:00:00Z"),
                now=datetime(2026, 8, 8, 7, tzinfo=timezone.utc),
            )
        )

    def test_dispatcher_rerun_rejects(self) -> None:
        with self.assertRaisesRegex(core.ContractError, "reruns"):
            core.resolve_event(
                event=event(),
                registry=registry(record()),
                source_sha=SOURCE_SHA,
                dispatcher_workflow_bytes=DISPATCHER_BYTES,
                run_attempt=2,
                now=datetime.now(timezone.utc),
            )

    def test_dispatcher_workflow_hash_mismatch_rejects(self) -> None:
        with self.assertRaisesRegex(core.ContractError, "workflow hash"):
            core.resolve_event(
                event=event(),
                registry=registry(record()),
                source_sha=SOURCE_SHA,
                dispatcher_workflow_bytes=b"changed",
                run_attempt=1,
                now=datetime.now(timezone.utc),
            )

    def test_duplicate_matching_authorities_reject(self) -> None:
        second = record(authorisation_id="phase9-two")
        with self.assertRaisesRegex(core.ContractError, "more than one"):
            core.resolve_event(
                event=event(),
                registry=registry(record(), second),
                source_sha=SOURCE_SHA,
                dispatcher_workflow_bytes=DISPATCHER_BYTES,
                run_attempt=1,
                now=datetime.now(timezone.utc),
            )

    def test_unknown_or_missing_schema_fields_fail_closed(self) -> None:
        bad = record()
        bad["arbitrary_workflow"] = "malicious.yml"
        with self.assertRaisesRegex(core.ContractError, "schema mismatch"):
            core.validate_registry(registry(bad), now=datetime.now(timezone.utc))

    def test_fixed_inputs_must_be_source_controlled_scalars(self) -> None:
        bad = record(fixed_inputs={"x": {"workflow": "injected"}})
        with self.assertRaisesRegex(core.ContractError, "JSON scalars"):
            core.validate_registry(registry(bad), now=datetime.now(timezone.utc))

    def _resolve(
        self,
        payload: dict[str, object],
        *,
        item: dict[str, object] | None = None,
        now: datetime | None = None,
    ) -> core.Resolution | None:
        return core.resolve_event(
            event=payload,
            registry=registry(item or record()),
            source_sha=SOURCE_SHA,
            dispatcher_workflow_bytes=DISPATCHER_BYTES,
            run_attempt=1,
            now=now or datetime.now(timezone.utc),
        )


class ConsumptionTests(unittest.TestCase):
    def test_edited_comment_rejects_before_consumption(self) -> None:
        live = copy.deepcopy(event()["comment"])
        live["updated_at"] = "2026-08-08T07:02:00Z"
        with self.assertRaisesRegex(core.ContractError, "edited"):
            core.ensure_comment_unchanged(event(), live, resolution())

    def test_ruleset_requires_update_and_deletion_restrictions(self) -> None:
        bad = ruleset_response()
        bad["rules"] = [{"type": "deletion"}]
        with self.assertRaisesRegex(core.ContractError, "update and deletion"):
            runner.validate_runtime_ruleset(bad, resolution())

    def test_ruleset_creation_restriction_is_rejected_for_v1(self) -> None:
        bad = ruleset_response()
        bad["rules"].append({"type": "creation"})
        with self.assertRaisesRegex(core.ContractError, "must not restrict creation"):
            runner.validate_runtime_ruleset(bad, resolution())

    def test_ruleset_bypass_actors_are_not_interpreted_at_runtime(self) -> None:
        value = ruleset_response()
        value.pop("bypass_actors", None)
        runner.validate_runtime_ruleset(value, resolution())

    def test_target_workflow_hash_mismatch_rejects(self) -> None:
        class API:
            def get_workflow(self, _: int) -> dict[str, object]:
                return workflow_response()

            def get_contents(self, path: str, ref: str) -> dict[str, object]:
                value = contents_response()
                value["content"] = base64.b64encode(b"changed").decode()
                return value

        with self.assertRaisesRegex(core.ContractError, "file hash mismatch"):
            runner.validate_target_workflow(API(), resolution())

    def test_preexisting_tag_permanently_rejects_replay(self) -> None:
        class API:
            dispatched = False
            created = False

            def get_workflow(self, _: int) -> dict[str, object]:
                return workflow_response()

            def get_contents(self, path: str, ref: str) -> dict[str, object]:
                return contents_response()

            def get_ruleset(self, _: int) -> dict[str, object]:
                return ruleset_response()

            def get_tag(self, _: str) -> dict[str, object]:
                return {"ref": resolution().execution_ref, "object": {"type": "commit", "sha": SOURCE_SHA}}

            def create_tag_once(self, *args: object) -> dict[str, object]:
                self.created = True
                return {}

            def dispatch_once(self, *args: object) -> dict[str, object]:
                self.dispatched = True
                return {}

        api = API()
        with self.assertRaisesRegex(core.ContractError, "already exists"):
            runner.consume_and_dispatch(api=api, event=event(), resolution=resolution())
        self.assertFalse(api.created)
        self.assertFalse(api.dispatched)

    def test_lost_or_conflicting_create_acknowledgement_never_dispatches(self) -> None:
        class API:
            dispatched = False

            def get_workflow(self, _: int) -> dict[str, object]:
                return workflow_response()

            def get_contents(self, path: str, ref: str) -> dict[str, object]:
                return contents_response()

            def get_ruleset(self, _: int) -> dict[str, object]:
                return ruleset_response()

            def get_tag(self, _: str) -> None:
                return None

            def get_comment(self, _: int) -> dict[str, object]:
                return event()["comment"]

            def create_tag_once(self, *args: object) -> dict[str, object]:
                raise core.ContractError("ambiguous tag creation")

            def dispatch_once(self, *args: object) -> dict[str, object]:
                self.dispatched = True
                return {}

        api = API()
        with self.assertRaisesRegex(core.ContractError, "ambiguous tag"):
            runner.consume_and_dispatch(api=api, event=event(), resolution=resolution())
        self.assertFalse(api.dispatched)

    def test_exact_create_readback_then_direct_200_run_identity_dispatches_once(self) -> None:
        class API:
            tag_reads = 0
            dispatches = 0

            def get_workflow(self, _: int) -> dict[str, object]:
                return workflow_response()

            def get_contents(self, path: str, ref: str) -> dict[str, object]:
                return contents_response()

            def get_ruleset(self, _: int) -> dict[str, object]:
                return ruleset_response()

            def get_tag(self, _: str) -> dict[str, object] | None:
                self.tag_reads += 1
                if self.tag_reads == 1:
                    return None
                return {"ref": resolution().execution_ref, "object": {"type": "commit", "sha": SOURCE_SHA}}

            def get_comment(self, _: int) -> dict[str, object]:
                return event()["comment"]

            def create_tag_once(self, *args: object) -> dict[str, object]:
                return {"ref": resolution().execution_ref, "object": {"type": "commit", "sha": SOURCE_SHA}}

            def dispatch_once(self, workflow_id: int, tag: str, inputs: dict[str, object]) -> dict[str, object]:
                self.dispatches += 1
                self.assertions = (workflow_id, tag, inputs)
                return {"workflow_run_id": 555, "run_url": "api", "html_url": "html"}

            def get_run_attempt(self, _: int, attempt: int = 1) -> dict[str, object]:
                return target_run()

        api = API()
        result = runner.consume_and_dispatch(api=api, event=event(), resolution=resolution())
        self.assertEqual(api.dispatches, 1)
        self.assertEqual(result["workflow_run_id"], 555)
        self.assertEqual(api.assertions, (328208073, resolution().execution_tag, {}))

    def test_missing_direct_run_identity_is_not_inferred_or_retried(self) -> None:
        class API:
            dispatches = 0
            tag_reads = 0

            def get_workflow(self, _: int) -> dict[str, object]:
                return workflow_response()

            def get_contents(self, path: str, ref: str) -> dict[str, object]:
                return contents_response()

            def get_ruleset(self, _: int) -> dict[str, object]:
                return ruleset_response()

            def get_tag(self, _: str) -> dict[str, object] | None:
                self.tag_reads += 1
                return None if self.tag_reads == 1 else {"ref": resolution().execution_ref, "object": {"type": "commit", "sha": SOURCE_SHA}}

            def get_comment(self, _: int) -> dict[str, object]:
                return event()["comment"]

            def create_tag_once(self, *args: object) -> dict[str, object]:
                return {"ref": resolution().execution_ref, "object": {"type": "commit", "sha": SOURCE_SHA}}

            def dispatch_once(self, *args: object) -> dict[str, object]:
                self.dispatches += 1
                return {}

        api = API()
        with self.assertRaisesRegex(core.ContractError, "direct run identity"):
            runner.consume_and_dispatch(api=api, event=event(), resolution=resolution())
        self.assertEqual(api.dispatches, 1)

    def test_target_run_must_be_first_attempt_exact_tag_and_sha(self) -> None:
        for changes in (
            {"run_attempt": 2},
            {"head_sha": "b" * 40},
            {"head_branch": "main"},
            {"event": "issue_comment"},
            {"workflow_id": 1},
        ):
            with self.subTest(changes=changes):
                with self.assertRaises(core.ContractError):
                    runner.validate_target_run(target_run(**changes), resolution())


class ReceiptTests(unittest.TestCase):
    def test_canonical_json_is_sorted_compact_utf8_with_one_lf(self) -> None:
        self.assertEqual(core.canonical_json_bytes({"z": 1, "a": "é"}), b'{"a":"\xc3\xa9","z":1}\n')

    def test_receipt_binds_exact_dispatcher_and_target_run(self) -> None:
        resolved = resolution()
        subject = core.canonical_subject(
            resolution=resolved,
            event=event(),
            dispatcher_run_id=777,
            dispatcher_run_attempt=1,
            target_run=target_run(),
        )
        self.assertEqual(subject["dispatcher_run_id"], 777)
        self.assertEqual(subject["target_run_id"], 555)
        self.assertEqual(subject["target_ref"], resolved.execution_ref)
        predicate = core.canonical_predicate(subject, fixed_inputs_sha256=resolved.fixed_inputs_sha256)
        self.assertEqual(predicate["target_event"], "workflow_dispatch")
        self.assertEqual(predicate["fixed_inputs_sha256"], resolved.fixed_inputs_sha256)

    def test_signing_rerun_rejects(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(core.ContractError, "rerun"):
                runner.write_attestation_inputs(
                    event=event(),
                    resolution=resolution(),
                    dispatcher_run_id=1,
                    dispatcher_run_attempt=2,
                    target_run=target_run(),
                    output_dir=Path(tmp),
                )


class WorkflowStaticTests(unittest.TestCase):
    def test_listener_is_created_issue_comment_only(self) -> None:
        raw = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
        trigger = raw.get("on") if "on" in raw else raw.get(True)
        self.assertEqual(trigger, {"issue_comment": {"types": ["created"]}})
        self.assertEqual(raw["permissions"], {})

    def test_side_effect_job_has_only_required_repository_writes(self) -> None:
        raw = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
        permissions = raw["jobs"]["consume-and-dispatch"]["permissions"]
        self.assertEqual(
            permissions,
            {"actions": "write", "contents": "write", "issues": "read"},
        )
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertNotIn("git push", text)
        self.assertNotIn("pull-requests: write", text)
        self.assertNotIn("statuses: write", text)
        self.assertNotIn("repository_dispatch", text)

    def test_signing_job_cannot_dispatch_or_write_contents(self) -> None:
        raw = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
        permissions = raw["jobs"]["sign-dispatch-receipt"]["permissions"]
        self.assertEqual(permissions["actions"], "read")
        self.assertEqual(permissions["contents"], "read")
        self.assertEqual(permissions["attestations"], "write")
        self.assertEqual(permissions["id-token"], "write")

    def test_attest_action_is_full_sha_pinned(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn(
            "actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6",
            text,
        )
        self.assertNotIn("actions/attest@v", text)

    def test_no_provider_secret_or_protected_environment_is_present(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertNotIn("OPENROUTER_API_KEY", text)
        self.assertNotIn("governed-llm-dry-run", text)
        self.assertNotIn("environment:", text)

    def test_runtime_exposes_only_one_ref_create_and_one_dispatch_write(self) -> None:
        text = (ROOT / "issueops_dispatch/runner.py").read_text(encoding="utf-8")
        self.assertEqual(text.count('"/git/refs"'), 1)
        self.assertEqual(text.count('f"/actions/workflows/{workflow_id}/dispatches"'), 1)
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
