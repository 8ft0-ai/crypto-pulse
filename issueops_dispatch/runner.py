"""GitHub Actions runtime for the reusable IssueOps workflow dispatcher."""

from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from issueops_dispatch.core import (
    ContractError,
    RULESET_REF_INCLUDE,
    Resolution,
    canonical_json_bytes,
    canonical_predicate,
    canonical_subject,
    ensure_comment_unchanged,
    resolve_event,
    sha256_bytes,
)

API_VERSION = "2026-03-10"
ACCEPT = "application/vnd.github+json"
EMPTY_REGISTRY: Mapping[str, Any] = {"schema_version": 2, "authorisations": []}


class GitHubAPI:
    def __init__(self, repository: str, token: str) -> None:
        self.repository = repository
        self.base = f"https://api.github.com/repos/{repository}"
        self.token = token

    def _request(
        self,
        method: str,
        path: str,
        *,
        body: Mapping[str, Any] | None = None,
        expected: tuple[int, ...] = (200,),
    ) -> tuple[int, Any]:
        url = self.base + path
        data = None if body is None else json.dumps(body, separators=(",", ":")).encode()
        request = urllib.request.Request(
            url,
            data=data,
            method=method,
            headers={
                "Accept": ACCEPT,
                "Authorization": f"Bearer {self.token}",
                "X-GitHub-Api-Version": API_VERSION,
                "User-Agent": "cryptopulse-issueops-dispatcher",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                status = response.status
                payload = response.read()
        except urllib.error.HTTPError as exc:
            status = exc.code
            payload = exc.read()
        except (TimeoutError, urllib.error.URLError) as exc:
            raise ContractError(
                f"ambiguous GitHub API response for {method} {path}: {exc}"
            ) from exc
        if status not in expected:
            detail = payload.decode("utf-8", errors="replace")[:1000]
            raise ContractError(f"GitHub API {method} {path} returned {status}: {detail}")
        if not payload:
            return status, None
        try:
            return status, json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ContractError(f"GitHub API {method} {path} returned non-JSON") from exc

    def get_comment(self, comment_id: int) -> Mapping[str, Any]:
        _, payload = self._request("GET", f"/issues/comments/{comment_id}")
        return _mapping(payload, "comment")

    def get_workflow(self, workflow_id: int) -> Mapping[str, Any]:
        _, payload = self._request("GET", f"/actions/workflows/{workflow_id}")
        return _mapping(payload, "workflow")

    def get_contents(self, path: str, ref: str) -> Mapping[str, Any]:
        quoted = urllib.parse.quote(path, safe="/")
        _, payload = self._request(
            "GET", f"/contents/{quoted}?ref={urllib.parse.quote(ref, safe='')}"
        )
        return _mapping(payload, "contents")

    def get_ruleset(self, ruleset_id: int) -> Mapping[str, Any]:
        _, payload = self._request("GET", f"/rulesets/{ruleset_id}")
        return _mapping(payload, "ruleset")

    def get_tag(self, execution_tag: str) -> Mapping[str, Any] | None:
        quoted = urllib.parse.quote(f"tags/{execution_tag}", safe="/")
        try:
            _, payload = self._request("GET", f"/git/ref/{quoted}")
        except ContractError as exc:
            if " returned 404:" in str(exc):
                return None
            raise
        return _mapping(payload, "tag ref")

    def create_tag_once(self, execution_ref: str, source_sha: str) -> Mapping[str, Any]:
        # Sole Git-reference write. No update/delete/content write exists.
        _, payload = self._request(
            "POST",
            "/git/refs",
            body={"ref": execution_ref, "sha": source_sha},
            expected=(201,),
        )
        return _mapping(payload, "created tag")

    def dispatch_once(
        self, workflow_id: int, execution_tag: str, fixed_inputs: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        # Sole Actions write endpoint; no other Actions mutation is implemented.
        _, payload = self._request(
            "POST",
            f"/actions/workflows/{workflow_id}/dispatches",
            body={"ref": execution_tag, "inputs": dict(fixed_inputs)},
            expected=(200,),
        )
        return _mapping(payload, "workflow dispatch response")

    def get_run_attempt(self, run_id: int, attempt: int = 1) -> Mapping[str, Any]:
        _, payload = self._request(
            "GET", f"/actions/runs/{run_id}/attempts/{attempt}"
        )
        return _mapping(payload, "workflow run")


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ContractError(f"{name} response is not an object")
    return value


def load_registry(path: Path) -> Mapping[str, Any]:
    """Load the registry as JSON, a strict YAML 1.2 subset, using stdlib only."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ContractError(
            "authorisation registry must use the canonical JSON/YAML-subset serialisation"
        ) from exc
    if not isinstance(payload, Mapping):
        raise ContractError("authorisation registry is not an object")
    return payload


def load_registry_bytes(payload: bytes) -> Mapping[str, Any]:
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError("parent authorisation registry is not canonical JSON") from exc
    if not isinstance(value, Mapping):
        raise ContractError("parent authorisation registry is not an object")
    return value


def load_parent_registry(config: Path, source_sha: str) -> Mapping[str, Any]:
    """Read the config at the exact source commit's first parent from local git."""
    try:
        parent = subprocess.run(
            ["git", "rev-parse", f"{source_sha}^1"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        ).stdout.strip()
    except subprocess.CalledProcessError as exc:
        raise ContractError("cannot prove exact source commit first parent") from exc
    if not parent:
        raise ContractError("exact source commit first parent is missing")
    try:
        result = subprocess.run(
            ["git", "show", f"{parent}:{config.as_posix()}"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError as exc:
        raise ContractError("cannot inspect first-parent authorisation registry") from exc
    if result.returncode == 0:
        return load_registry_bytes(result.stdout)
    stderr = result.stderr.decode("utf-8", errors="replace")
    if "does not exist in" in stderr or "exists on disk, but not in" in stderr:
        return EMPTY_REGISTRY
    raise ContractError("cannot prove first-parent authorisation registry state")


def load_event(path: Path) -> Mapping[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, Mapping):
        raise ContractError("event payload is not an object")
    return payload


def resolve_from_files(args: argparse.Namespace) -> Resolution | None:
    event = load_event(Path(args.event))
    config_path = Path(args.config)
    registry = load_registry(config_path)
    parent_registry = load_parent_registry(config_path, args.source_sha)
    workflow_bytes = Path(args.dispatcher_workflow).read_bytes()
    return resolve_event(
        event=event,
        registry=registry,
        parent_registry=parent_registry,
        source_sha=args.source_sha,
        dispatcher_workflow_bytes=workflow_bytes,
        run_attempt=args.run_attempt,
        now=datetime.now(timezone.utc),
    )


def _decode_contents(item: Mapping[str, Any]) -> bytes:
    if item.get("type") != "file" or item.get("encoding") != "base64":
        raise ContractError("target workflow contents response is not a base64 file")
    content = item.get("content")
    if not isinstance(content, str):
        raise ContractError("target workflow content is missing")
    try:
        return base64.b64decode(content, validate=False)
    except (ValueError, TypeError) as exc:
        raise ContractError("target workflow content is invalid base64") from exc


def _has_top_level_workflow_dispatch(text: str) -> bool:
    """Recognise workflow_dispatch within the top-level `on:` mapping only."""
    lines = text.splitlines()
    in_on = False
    on_indent = 0
    for raw in lines:
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        if not in_on:
            if indent == 0 and stripped == "on:":
                in_on = True
                on_indent = indent
            continue
        if indent <= on_indent:
            return False
        if stripped.startswith("workflow_dispatch:"):
            return True
    return False


def validate_target_workflow(api: GitHubAPI, resolution: Resolution) -> None:
    record = resolution.record
    workflow = api.get_workflow(record["target_workflow_id"])
    if workflow.get("id") != record["target_workflow_id"]:
        raise ContractError("target workflow numeric identity mismatch")
    if workflow.get("path") != record["target_workflow_path"]:
        raise ContractError("target workflow path mismatch")
    if workflow.get("state") != "active":
        raise ContractError("target workflow is not active")
    content = _decode_contents(
        api.get_contents(record["target_workflow_path"], resolution.source_sha)
    )
    if sha256_bytes(content) != record["target_workflow_sha256"]:
        raise ContractError("target workflow file hash mismatch")
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ContractError("target workflow is not UTF-8") from exc
    if not _has_top_level_workflow_dispatch(text):
        raise ContractError("target workflow is not workflow_dispatch-enabled")


def _rule_types(ruleset: Mapping[str, Any]) -> set[str]:
    rules = ruleset.get("rules")
    if not isinstance(rules, list):
        raise ContractError("ruleset rules are missing")
    types = set()
    for rule in rules:
        if not isinstance(rule, Mapping) or not isinstance(rule.get("type"), str):
            raise ContractError("malformed ruleset rule")
        types.add(rule["type"])
    return types


def validate_runtime_ruleset(ruleset: Mapping[str, Any], resolution: Resolution) -> None:
    record = resolution.record
    if ruleset.get("id") != record["execution_tag_ruleset_id"]:
        raise ContractError("execution-tag ruleset id mismatch")
    if ruleset.get("name") != record["execution_tag_ruleset_name"]:
        raise ContractError("execution-tag ruleset name mismatch")
    if ruleset.get("target") != "tag" or ruleset.get("enforcement") != "active":
        raise ContractError("execution-tag ruleset is not active for tags")
    conditions = ruleset.get("conditions")
    if not isinstance(conditions, Mapping) or set(conditions) != {"ref_name"}:
        raise ContractError("execution-tag ruleset conditions drifted")
    ref_name = conditions.get("ref_name")
    if not isinstance(ref_name, Mapping) or set(ref_name) != {"include", "exclude"}:
        raise ContractError("execution-tag ref-name condition drifted")
    includes = ref_name.get("include")
    excludes = ref_name.get("exclude")
    if includes != [RULESET_REF_INCLUDE]:
        raise ContractError("execution-tag include namespace is not the exact reviewed value")
    if excludes != []:
        raise ContractError("execution-tag exclusions are not permitted in v1")
    rule_types = _rule_types(ruleset)
    if "update" not in rule_types or "deletion" not in rule_types:
        raise ContractError("ruleset must restrict tag update and deletion")
    if "creation" in rule_types:
        raise ContractError("v1 execution-tag ruleset must not restrict creation")
    # bypass_actors is deliberately not interpreted here: GitHub may omit it
    # for callers without ruleset-write authority. Complete bypass review is a
    # separate provisioning-time governance control.


def validate_tag_ref(tag: Mapping[str, Any], resolution: Resolution) -> None:
    if tag.get("ref") != resolution.execution_ref:
        raise ContractError("execution tag read-back ref mismatch")
    obj = tag.get("object")
    if (
        not isinstance(obj, Mapping)
        or obj.get("type") != "commit"
        or obj.get("sha") != resolution.source_sha
    ):
        raise ContractError("execution tag does not point directly to the authorised commit")


def validate_target_run(run: Mapping[str, Any], resolution: Resolution) -> None:
    record = resolution.record
    if run.get("id") is None or not isinstance(run.get("id"), int):
        raise ContractError("target run id is missing")
    if run.get("workflow_id") != record["target_workflow_id"]:
        raise ContractError("target run workflow id mismatch")
    if run.get("path") != record["target_workflow_path"]:
        raise ContractError("target run workflow path mismatch")
    if run.get("event") != "workflow_dispatch":
        raise ContractError("target run event mismatch")
    if run.get("run_attempt") != 1:
        raise ContractError("target rerun is never authorised")
    if run.get("head_sha") != resolution.source_sha:
        raise ContractError("target run SHA mismatch")
    if run.get("head_branch") != resolution.execution_tag:
        raise ContractError("target run ref mismatch")


def consume_and_dispatch(
    *, api: GitHubAPI, event: Mapping[str, Any], resolution: Resolution
) -> Mapping[str, Any]:
    validate_target_workflow(api, resolution)
    ruleset = api.get_ruleset(resolution.record["execution_tag_ruleset_id"])
    validate_runtime_ruleset(ruleset, resolution)

    if api.get_tag(resolution.execution_tag) is not None:
        raise ContractError("execution tag already exists; authorisation is consumed or conflicted")

    # Re-fetch at the last possible point before the atomic consumption write.
    live_comment = api.get_comment(int(event["comment"]["id"]))
    ensure_comment_unchanged(event, live_comment, resolution)

    created = api.create_tag_once(resolution.execution_ref, resolution.source_sha)
    validate_tag_ref(created, resolution)
    read_back = api.get_tag(resolution.execution_tag)
    if read_back is None:
        raise ContractError("execution tag disappeared after creation")
    validate_tag_ref(read_back, resolution)

    response = api.dispatch_once(
        resolution.record["target_workflow_id"],
        resolution.execution_tag,
        resolution.record["fixed_inputs"],
    )
    run_id = response.get("workflow_run_id")
    run_url = response.get("run_url")
    html_url = response.get("html_url")
    if (
        not isinstance(run_id, int)
        or not isinstance(run_url, str)
        or not isinstance(html_url, str)
    ):
        raise ContractError("workflow dispatch did not return direct run identity")
    run = api.get_run_attempt(run_id, 1)
    validate_target_run(run, resolution)
    return {
        "workflow_run_id": run_id,
        "run_url": run_url,
        "html_url": html_url,
        "target_run": dict(run),
    }


def write_attestation_inputs(
    *,
    event: Mapping[str, Any],
    resolution: Resolution,
    dispatcher_run_id: int,
    dispatcher_run_attempt: int,
    target_run: Mapping[str, Any],
    output_dir: Path,
) -> tuple[Path, Path]:
    if dispatcher_run_attempt != 1:
        raise ContractError("dispatcher rerun may not sign")
    validate_target_run(target_run, resolution)
    subject = canonical_subject(resolution=resolution, target_run=target_run)
    predicate = canonical_predicate(
        resolution=resolution,
        event=event,
        dispatcher_run_id=dispatcher_run_id,
        dispatcher_run_attempt=dispatcher_run_attempt,
        target_run=target_run,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    subject_path = output_dir / "issueops-dispatch-target-run.json"
    predicate_path = output_dir / "issueops-dispatch-predicate.json"
    subject_path.write_bytes(canonical_json_bytes(subject))
    predicate_path.write_bytes(canonical_json_bytes(predicate))
    return subject_path, predicate_path


def _github_output(name: str, value: str) -> None:
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(f"{name}={value}\n")
    else:
        print(f"{name}={value}")


def command_resolve(args: argparse.Namespace) -> int:
    resolution = resolve_from_files(args)
    _github_output("authorised", "true" if resolution else "false")
    if resolution:
        _github_output("authorisation_id", resolution.record["authorisation_id"])
        _github_output("execution_tag", resolution.execution_tag)
        _github_output("source_sha", resolution.source_sha)
    return 0


def command_consume(args: argparse.Namespace) -> int:
    resolution = resolve_from_files(args)
    if resolution is None:
        raise ContractError("side-effect job has no active authorisation")
    event = load_event(Path(args.event))
    api = GitHubAPI(args.repository, args.token)
    result = consume_and_dispatch(api=api, event=event, resolution=resolution)
    _github_output("target_run_id", str(result["workflow_run_id"]))
    _github_output("target_run_url", result["html_url"])
    return 0


def command_prepare_attestation(args: argparse.Namespace) -> int:
    resolution = resolve_from_files(args)
    if resolution is None:
        raise ContractError("signing job has no active authorisation")
    event = load_event(Path(args.event))
    api = GitHubAPI(args.repository, args.token)
    # Do not re-authorise against mutable comment state after consumption.
    run = api.get_run_attempt(args.target_run_id, 1)
    validate_target_run(run, resolution)
    subject, predicate = write_attestation_inputs(
        event=event,
        resolution=resolution,
        dispatcher_run_id=args.dispatcher_run_id,
        dispatcher_run_attempt=args.run_attempt,
        target_run=run,
        output_dir=Path(args.output_dir),
    )
    _github_output("subject_path", str(subject))
    _github_output("predicate_path", str(predicate))
    _github_output("subject_sha256", sha256_bytes(subject.read_bytes()))
    _github_output("predicate_type", resolution.record["attestation_predicate_type"])
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    def common(target: argparse.ArgumentParser) -> None:
        target.add_argument("--event", required=True)
        target.add_argument("--config", required=True)
        target.add_argument("--dispatcher-workflow", required=True)
        target.add_argument("--source-sha", required=True)
        target.add_argument("--run-attempt", required=True, type=int)

    resolve = sub.add_parser("resolve")
    common(resolve)
    resolve.set_defaults(func=command_resolve)

    consume = sub.add_parser("consume")
    common(consume)
    consume.add_argument("--repository", required=True)
    consume.add_argument("--token", required=True)
    consume.set_defaults(func=command_consume)

    sign = sub.add_parser("prepare-attestation")
    common(sign)
    sign.add_argument("--repository", required=True)
    sign.add_argument("--token", required=True)
    sign.add_argument("--target-run-id", required=True, type=int)
    sign.add_argument("--dispatcher-run-id", required=True, type=int)
    sign.add_argument("--output-dir", required=True)
    sign.set_defaults(func=command_prepare_attestation)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return args.func(args)
    except ContractError as exc:
        print(f"IssueOps dispatcher rejected: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
