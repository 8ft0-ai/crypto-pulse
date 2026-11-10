"""Fail-closed provenance guard for protected IssueOps target workflows."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from issueops_dispatch.core import (
    ACTOR_LOGIN,
    ACTOR_USER_ID,
    ATTESTATION_SCHEMA,
    DISPATCHER_WORKFLOW_PATH,
    PREDICATE_TYPE,
    REPOSITORY,
    REPOSITORY_ID,
    REPOSITORY_OWNER_ID,
    RULESET_REF_INCLUDE,
    Resolution,
    canonical_json_bytes,
    canonical_subject,
    sha256_bytes,
    sha256_text,
    validate_registry,
)
from issueops_dispatch.runner import load_registry

API_VERSION = "2026-03-10"
TARGET_WORKFLOW_ID = 328208073
TARGET_WORKFLOW_PATH = ".github/workflows/governed-gpt-oss-quality-comparison.yml"
PINNED_GH_VERSION = "2.97.0"
PINNED_GH_ASSET = "gh_2.97.0_linux_amd64.tar.gz"
PINNED_GH_SHA256 = "a2c9b8497e1f85b1ad0dfcb78b5a622e098801b8e461e459e88e1ee12f018112"
RULESET_ID = 20623136
RULESET_NAME = "IssueOps immutable execution tags"
EXECUTION_REF_RE = re.compile(
    r"^refs/tags/issueops/dispatch/"
    r"(?P<authorisation_id>[A-Za-z0-9._-]{1,48})"
    r"--sha-(?P<sha>[0-9a-f]{40})$"
)
RUN_INVOCATION_RE = re.compile(
    r"^https://github\.com/8ft0-ai/crypto-pulse/actions/runs/"
    r"(?P<run_id>[1-9][0-9]*)/attempts/1$"
)
EXPECTED_SIGNER_URI = (
    "https://github.com/8ft0-ai/crypto-pulse/"
    ".github/workflows/issueops-workflow-dispatch.yml@refs/heads/main"
)
EXPECTED_SOURCE_URI = "https://github.com/8ft0-ai/crypto-pulse"
EXPECTED_SOURCE_REF = "refs/heads/main"
EXPECTED_OIDC_ISSUER = "https://token.actions.githubusercontent.com"


class GuardError(RuntimeError):
    """Raised when protected target authority cannot be proven exactly."""


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise GuardError(f"{name} is not an object")
    return value


def _list(value: Any, name: str) -> list[Any]:
    if not isinstance(value, list):
        raise GuardError(f"{name} is not an array")
    return value


def _parse_time(value: str | None, name: str) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise GuardError(f"{name} must be RFC3339 text or null")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise GuardError(f"{name} is not valid RFC3339") from exc
    if result.tzinfo is None:
        raise GuardError(f"{name} must include timezone")
    return result.astimezone(timezone.utc)


def parse_execution_ref(ref: str) -> tuple[str, str]:
    match = EXECUTION_REF_RE.fullmatch(ref)
    if match is None:
        raise GuardError(
            "protected target requires the exact IssueOps execution-tag ref grammar"
        )
    return match.group("authorisation_id"), match.group("sha")


def select_authorisation(
    registry: Mapping[str, Any], *, authorisation_id: str, now: datetime
) -> dict[str, Any]:
    try:
        records = validate_registry(registry, now=now)
    except Exception as exc:
        raise GuardError(f"authorisation registry validation failed: {exc}") from exc
    matches = [r for r in records if r["authorisation_id"] == authorisation_id]
    if len(matches) != 1:
        raise GuardError(
            "execution tag does not resolve to exactly one source-controlled authorisation"
        )
    record = matches[0]
    if not record["enabled"]:
        raise GuardError("selected authorisation is disabled")
    now_utc = now.astimezone(timezone.utc)
    not_before = _parse_time(record["not_before"], "not_before")
    expires_at = _parse_time(record["expires_at"], "expires_at")
    if not_before is not None and now_utc < not_before:
        raise GuardError("selected authorisation is not active yet")
    if expires_at is not None and now_utc >= expires_at:
        raise GuardError("selected authorisation is expired")
    if record["target_workflow_id"] != TARGET_WORKFLOW_ID:
        raise GuardError("authorisation targets a different workflow ID")
    if record["target_workflow_path"] != TARGET_WORKFLOW_PATH:
        raise GuardError("authorisation targets a different workflow path")
    if record["execution_tag_ruleset_id"] != RULESET_ID:
        raise GuardError("authorisation freezes a different execution-tag ruleset ID")
    if record["execution_tag_ruleset_name"] != RULESET_NAME:
        raise GuardError("authorisation freezes a different execution-tag ruleset name")
    return record


def build_resolution(
    *, record: Mapping[str, Any], source_sha: str, execution_ref: str
) -> Resolution:
    execution_tag = execution_ref.removeprefix("refs/tags/")
    return Resolution(
        record=dict(record),
        source_sha=source_sha,
        record_sha256=sha256_bytes(canonical_json_bytes(record)),
        comment_body_sha256=sha256_text(str(record["command"])),
        fixed_inputs_sha256=sha256_bytes(canonical_json_bytes(record["fixed_inputs"])),
        execution_tag=execution_tag,
        execution_ref=execution_ref,
    )


def verify_workflow_hash(record: Mapping[str, Any], workflow_path: Path) -> None:
    actual = sha256_bytes(workflow_path.read_bytes())
    if actual != record["target_workflow_sha256"]:
        raise GuardError(
            "target workflow SHA-256 does not match source-controlled authority"
        )


def verify_tag_ref(
    tag_ref: Mapping[str, Any], *, execution_ref: str, source_sha: str
) -> None:
    if tag_ref.get("ref") != execution_ref:
        raise GuardError("execution-tag API readback returned the wrong ref")
    obj = _mapping(tag_ref.get("object"), "execution-tag object")
    if obj.get("type") != "commit":
        raise GuardError("execution tag must be a lightweight ref directly to a commit")
    if obj.get("sha") != source_sha:
        raise GuardError("execution tag does not point directly to the authorised SHA")


def verify_ruleset(ruleset: Mapping[str, Any], record: Mapping[str, Any]) -> None:
    if ruleset.get("id") != record["execution_tag_ruleset_id"]:
        raise GuardError("runtime ruleset ID mismatch")
    if ruleset.get("name") != record["execution_tag_ruleset_name"]:
        raise GuardError("runtime ruleset name mismatch")
    if ruleset.get("target") != "tag" or ruleset.get("enforcement") != "active":
        raise GuardError("execution-tag ruleset is not an active tag ruleset")
    conditions = _mapping(ruleset.get("conditions"), "ruleset conditions")
    ref_name = _mapping(conditions.get("ref_name"), "ruleset ref_name conditions")
    if ref_name.get("include") != [RULESET_REF_INCLUDE] or ref_name.get("exclude") != []:
        raise GuardError("execution-tag ruleset namespace conditions changed")
    rules = _list(ruleset.get("rules"), "ruleset rules")
    types = [_mapping(rule, "ruleset rule").get("type") for rule in rules]
    if types.count("update") != 1 or types.count("deletion") != 1:
        raise GuardError("execution-tag update/deletion restriction changed")
    if "creation" in types:
        raise GuardError("execution-tag creation restriction is prohibited in v1")
    if set(types) != {"update", "deletion"}:
        raise GuardError("execution-tag ruleset has unexpected additional runtime rules")


def parse_run_invocation_uri(value: Any) -> int:
    if not isinstance(value, str):
        raise GuardError("verified certificate runInvocationURI is missing")
    match = RUN_INVOCATION_RE.fullmatch(value)
    if match is None:
        raise GuardError(
            "verified certificate runInvocationURI is not the canonical dispatcher attempt-1 URI"
        )
    return int(match.group("run_id"))


def verify_certificate(certificate: Mapping[str, Any], *, source_sha: str) -> int:
    expected = {
        "issuer": EXPECTED_OIDC_ISSUER,
        "subjectAlternativeName": EXPECTED_SIGNER_URI,
        "githubWorkflowTrigger": "issue_comment",
        "githubWorkflowSHA": source_sha,
        "githubWorkflowRepository": REPOSITORY,
        "githubWorkflowRef": EXPECTED_SOURCE_REF,
        "buildSignerURI": EXPECTED_SIGNER_URI,
        "buildSignerDigest": source_sha,
        "runnerEnvironment": "github-hosted",
        "sourceRepositoryURI": EXPECTED_SOURCE_URI,
        "sourceRepositoryDigest": source_sha,
        "sourceRepositoryRef": EXPECTED_SOURCE_REF,
        "sourceRepositoryIdentifier": str(REPOSITORY_ID),
        "sourceRepositoryOwnerIdentifier": str(REPOSITORY_OWNER_ID),
        "buildConfigURI": EXPECTED_SIGNER_URI,
        "buildConfigDigest": source_sha,
        "buildTrigger": "issue_comment",
    }
    for key, value in expected.items():
        if certificate.get(key) != value:
            raise GuardError(f"verified certificate {key} mismatch")
    return parse_run_invocation_uri(certificate.get("runInvocationURI"))


def verify_dispatcher_run(
    run: Mapping[str, Any], *, dispatcher_run_id: int, source_sha: str
) -> None:
    if run.get("id") != dispatcher_run_id:
        raise GuardError("dispatcher run-attempt API returned the wrong run ID")
    if run.get("run_attempt") != 1:
        raise GuardError("dispatcher certificate-bound run is not attempt 1")
    if run.get("event") != "issue_comment":
        raise GuardError("dispatcher certificate-bound run has the wrong event")
    if run.get("head_sha") != source_sha:
        raise GuardError("dispatcher certificate-bound run has the wrong source SHA")
    if run.get("path") != DISPATCHER_WORKFLOW_PATH:
        raise GuardError("dispatcher certificate-bound run has the wrong workflow path")
    if run.get("head_branch") != "main":
        raise GuardError("dispatcher certificate-bound run is not sourced from main")
    actor = _mapping(run.get("actor"), "dispatcher run actor")
    triggering = _mapping(run.get("triggering_actor"), "dispatcher triggering actor")
    if actor.get("id") != ACTOR_USER_ID or triggering.get("id") != ACTOR_USER_ID:
        raise GuardError("dispatcher run actor identity does not match frozen owner ID")
    if actor.get("login") not in (None, ACTOR_LOGIN):
        raise GuardError("dispatcher run actor login mismatch")
    if triggering.get("login") not in (None, ACTOR_LOGIN):
        raise GuardError("dispatcher triggering actor login mismatch")
    repository = _mapping(run.get("repository"), "dispatcher run repository")
    if repository.get("full_name") != REPOSITORY:
        raise GuardError("dispatcher run repository mismatch")


def verify_statement_and_predicate(
    statement: Mapping[str, Any],
    *,
    resolution: Resolution,
    target_run_id: int,
    dispatcher_run_id: int,
) -> None:
    if statement.get("predicateType") != PREDICATE_TYPE:
        raise GuardError("verified statement predicate type mismatch")
    subjects = _list(statement.get("subject"), "verified statement subject")
    if len(subjects) != 1:
        raise GuardError("verified statement must contain exactly one subject")
    subject = _mapping(subjects[0], "verified subject")
    digest = _mapping(subject.get("digest"), "verified subject digest")
    expected_subject = canonical_subject(
        resolution=resolution, target_run={"id": target_run_id}
    )
    expected_digest = sha256_bytes(canonical_json_bytes(expected_subject))
    if digest.get("sha256") != expected_digest:
        raise GuardError("verified attestation subject digest mismatch")

    predicate = _mapping(statement.get("predicate"), "verified statement predicate")
    required = {
        "schema": ATTESTATION_SCHEMA,
        "repository": REPOSITORY,
        "repository_id": REPOSITORY_ID,
        "repository_owner_id": REPOSITORY_OWNER_ID,
        "authorisation_id": resolution.record["authorisation_id"],
        "authorisation_sha": resolution.source_sha,
        "authorisation_record_sha256": resolution.record_sha256,
        "triggering_issue": resolution.record["governing_issue"],
        "triggering_comment_body_sha256": resolution.comment_body_sha256,
        "actor_login": resolution.record["actor_login"],
        "actor_user_id": resolution.record["actor_user_id"],
        "required_author_association": resolution.record[
            "required_author_association"
        ],
        "execution_ref": resolution.execution_ref,
        "dispatcher_workflow_path": DISPATCHER_WORKFLOW_PATH,
        "dispatcher_workflow_sha": resolution.source_sha,
        "dispatcher_run_id": dispatcher_run_id,
        "dispatcher_run_attempt": 1,
        "target_workflow_id": resolution.record["target_workflow_id"],
        "target_workflow_path": resolution.record["target_workflow_path"],
        "target_run_id": target_run_id,
        "target_ref": resolution.execution_ref,
        "target_sha": resolution.source_sha,
        "target_event": "workflow_dispatch",
        "fixed_inputs_sha256": resolution.fixed_inputs_sha256,
    }
    for key, value in required.items():
        if predicate.get(key) != value:
            raise GuardError(f"signed dispatcher predicate {key} mismatch")
    comment_id = predicate.get("triggering_comment_id")
    if not isinstance(comment_id, int) or comment_id <= 0:
        raise GuardError(
            "signed dispatcher predicate has invalid triggering_comment_id"
        )


def verify_gh_result(
    payload: Any,
    *,
    resolution: Resolution,
    target_run_id: int,
    run_lookup: Callable[[int], Mapping[str, Any]],
) -> int:
    entries = _list(payload, "gh attestation verification output")
    if len(entries) != 1:
        raise GuardError(
            "one candidate bundle must produce exactly one verification result"
        )
    result = _mapping(entries[0], "verification result entry")
    verification = _mapping(result.get("verificationResult"), "verificationResult")
    signature = _mapping(verification.get("signature"), "verification signature")
    certificate = _mapping(signature.get("certificate"), "verification certificate")
    timestamps = _list(
        verification.get("verifiedTimestamps"), "verified timestamps"
    )
    if not timestamps:
        raise GuardError(
            "verified attestation contains no independently verified timestamp"
        )
    dispatcher_run_id = verify_certificate(certificate, source_sha=resolution.source_sha)
    run = run_lookup(dispatcher_run_id)
    verify_dispatcher_run(
        run, dispatcher_run_id=dispatcher_run_id, source_sha=resolution.source_sha
    )
    statement = _mapping(verification.get("statement"), "verified statement")
    verify_statement_and_predicate(
        statement,
        resolution=resolution,
        target_run_id=target_run_id,
        dispatcher_run_id=dispatcher_run_id,
    )
    return dispatcher_run_id


def _link_parameter(segment: str) -> tuple[str, str]:
    if "=" not in segment:
        raise GuardError("malformed attestation pagination Link parameter")
    name, raw_value = (item.strip() for item in segment.split("=", 1))
    token_chars = "!#$%&'*+-.^_`|~"
    if not name or any(not (char.isalnum() or char in token_chars) for char in name):
        raise GuardError("malformed attestation pagination Link parameter")
    if raw_value.startswith('"'):
        if len(raw_value) < 2 or not raw_value.endswith('"'):
            raise GuardError("malformed attestation pagination Link parameter")
        value = raw_value[1:-1]
        if '"' in value or "\\" in value:
            raise GuardError("malformed attestation pagination Link parameter")
    else:
        if not raw_value or any(
            char.isspace() or char in '\",;' for char in raw_value
        ):
            raise GuardError("malformed attestation pagination Link parameter")
        value = raw_value
    return name.lower(), value


def _next_link(value: str | None, *, expected_path: str | None = None) -> str | None:
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise GuardError("malformed attestation pagination Link header")

    next_urls: list[str] = []
    for raw_part in value.split(","):
        part = raw_part.strip()
        if not part or not part.startswith("<"):
            raise GuardError("malformed attestation pagination Link header")
        close = part.find(">")
        if close <= 1 or "<" in part[1:close]:
            raise GuardError("malformed attestation pagination Link header")
        target = part[1:close]
        remainder = part[close + 1 :].strip()
        if not remainder.startswith(";"):
            raise GuardError("malformed attestation pagination Link header")

        parameters: dict[str, str] = {}
        for raw_parameter in remainder.split(";")[1:]:
            segment = raw_parameter.strip()
            if not segment:
                raise GuardError("malformed attestation pagination Link header")
            name, parameter_value = _link_parameter(segment)
            if name in parameters:
                raise GuardError("duplicate attestation pagination Link parameter")
            parameters[name] = parameter_value

        relation = parameters.get("rel")
        if relation is None:
            raise GuardError("attestation pagination Link relation is missing")
        relations = relation.split()
        if not relations or any(
            not re.fullmatch(r"[A-Za-z][A-Za-z0-9._-]*", item)
            for item in relations
        ):
            raise GuardError("malformed attestation pagination Link relation")
        if "next" not in relations:
            continue

        parsed = urllib.parse.urlparse(target)
        if (
            parsed.scheme != "https"
            or parsed.netloc != "api.github.com"
            or parsed.params
            or parsed.fragment
        ):
            raise GuardError("attestation pagination escaped api.github.com")
        if expected_path is not None and parsed.path != expected_path:
            raise GuardError("attestation pagination escaped the exact collection path")
        try:
            query = urllib.parse.parse_qs(
                parsed.query, keep_blank_values=True, strict_parsing=True
            )
        except ValueError as exc:
            raise GuardError("malformed attestation pagination query") from exc
        if expected_path is not None:
            if set(query) != {"predicate_type", "per_page", "page"}:
                raise GuardError("attestation pagination query changed")
            if query.get("predicate_type") != [PREDICATE_TYPE]:
                raise GuardError("attestation pagination predicate filter changed")
            if query.get("per_page") != ["100"]:
                raise GuardError("attestation pagination page size changed")
            page = query.get("page")
            if (
                page is None
                or len(page) != 1
                or not page[0].isdigit()
                or int(page[0]) < 1
            ):
                raise GuardError("attestation pagination page is invalid")
        next_urls.append(target)

    if len(next_urls) > 1:
        raise GuardError("multiple attestation pagination next links")
    return next_urls[0] if next_urls else None


class GitHubReadAPI:
    """Read-only GitHub API surface used by the target provenance guard."""

    def __init__(self, repository: str, token: str) -> None:
        self.repository = repository
        self.base = f"https://api.github.com/repos/{repository}"
        self.token = token

    def _request_url(self, url: str) -> tuple[Any, Mapping[str, str]]:
        request = urllib.request.Request(
            url,
            method="GET",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "X-GitHub-Api-Version": API_VERSION,
                "User-Agent": "cryptopulse-issueops-target-guard",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = response.read()
                headers = dict(response.headers.items())
                status = response.status
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:1000]
            raise GuardError(
                f"GitHub API GET {url} returned {exc.code}: {detail}"
            ) from exc
        except (TimeoutError, urllib.error.URLError) as exc:
            raise GuardError(f"GitHub API GET {url} was ambiguous: {exc}") from exc
        if status != 200:
            raise GuardError(f"GitHub API GET {url} returned unexpected {status}")
        try:
            return json.loads(payload), headers
        except json.JSONDecodeError as exc:
            raise GuardError(
                f"GitHub API GET {url} returned malformed JSON"
            ) from exc

    def get(self, path: str) -> Mapping[str, Any]:
        payload, _ = self._request_url(self.base + path)
        return _mapping(payload, path)

    def get_tag(self, execution_tag: str) -> Mapping[str, Any]:
        quoted = urllib.parse.quote(f"tags/{execution_tag}", safe="/")
        return self.get(f"/git/ref/{quoted}")

    def get_ruleset(self, ruleset_id: int) -> Mapping[str, Any]:
        return self.get(f"/rulesets/{ruleset_id}")

    def get_run_attempt(self, run_id: int) -> Mapping[str, Any]:
        return self.get(f"/actions/runs/{run_id}/attempts/1")

    def list_attestations(self, subject_sha256: str) -> list[Mapping[str, Any]]:
        query = urllib.parse.urlencode(
            {"predicate_type": PREDICATE_TYPE, "per_page": 100}
        )
        path = f"/repos/{self.repository}/attestations/sha256:{subject_sha256}"
        url = f"https://api.github.com{path}?{query}"
        results: list[Mapping[str, Any]] = []
        seen: set[str] = set()
        while url:
            if url in seen:
                raise GuardError("attestation pagination loop detected")
            seen.add(url)
            payload, headers = self._request_url(url)
            page = _mapping(payload, "attestation collection")
            for item in _list(page.get("attestations"), "attestations"):
                results.append(_mapping(item, "attestation item"))
            upper_link = headers.get("Link")
            lower_link = headers.get("link")
            if (
                upper_link is not None
                and lower_link is not None
                and upper_link != lower_link
            ):
                raise GuardError("conflicting attestation pagination Link headers")
            link = upper_link if upper_link is not None else lower_link
            url = _next_link(link, expected_path=path)
        return results

    def fetch_bundle(self, url: str) -> bytes:
        if not isinstance(url, str) or not url.startswith("https://"):
            raise GuardError("attestation bundle_url is missing or not HTTPS")
        request = urllib.request.Request(
            url,
            method="GET",
            headers={"User-Agent": "cryptopulse-issueops-target-guard"},
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                if response.status != 200:
                    raise GuardError(
                        "attestation bundle download returned non-200"
                    )
                return response.read()
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            raise GuardError(f"attestation bundle download failed: {exc}") from exc


def verify_pinned_gh(binary: Path) -> None:
    if not binary.is_file():
        raise GuardError("pinned gh verifier binary is missing")
    result = subprocess.run(
        [str(binary), "--version"], text=True, capture_output=True, check=False
    )
    if result.returncode != 0:
        raise GuardError("pinned gh verifier cannot report its version")
    first = result.stdout.splitlines()[0] if result.stdout else ""
    if f"gh version {PINNED_GH_VERSION} " not in first:
        raise GuardError("gh verifier version is not exactly the frozen version")


def run_gh_verify(
    *,
    gh_binary: Path,
    subject_path: Path,
    bundle_path: Path,
    source_sha: str,
    token: str,
) -> Any | None:
    command = [
        str(gh_binary),
        "attestation",
        "verify",
        str(subject_path),
        "--bundle",
        str(bundle_path),
        "--repo",
        REPOSITORY,
        "--cert-oidc-issuer",
        EXPECTED_OIDC_ISSUER,
        "--signer-workflow",
        f"{REPOSITORY}/{DISPATCHER_WORKFLOW_PATH}",
        "--signer-digest",
        source_sha,
        "--source-digest",
        source_sha,
        "--source-ref",
        EXPECTED_SOURCE_REF,
        "--predicate-type",
        PREDICATE_TYPE,
        "--deny-self-hosted-runners",
        "--format",
        "json",
    ]
    env = dict(os.environ)
    env["GH_TOKEN"] = token
    result = subprocess.run(
        command, text=False, capture_output=True, env=env, check=False
    )
    if result.returncode != 0:
        return None
    try:
        stdout = result.stdout.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise GuardError(
            "pinned gh returned non-UTF-8 JSON after successful verification"
        ) from exc
    try:
        return json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise GuardError(
            "pinned gh returned malformed JSON after successful verification"
        ) from exc


def execute_guard(
    *,
    repository_root: Path,
    github_ref: str,
    github_sha: str,
    workflow_sha: str,
    run_id: int,
    run_attempt: int,
    repository: str,
    token: str,
    gh_binary: Path,
    now: datetime,
    api: GitHubReadAPI | None = None,
) -> dict[str, Any]:
    if repository != REPOSITORY:
        raise GuardError("protected target is running in the wrong repository")
    if run_attempt != 1:
        raise GuardError("protected target reruns are not authorised")
    authorisation_id, encoded_sha = parse_execution_ref(github_ref)
    if encoded_sha != github_sha:
        raise GuardError("execution-tag encoded SHA does not equal github.sha")
    if workflow_sha != github_sha:
        raise GuardError(
            "github.workflow_sha must equal github.sha on the protected tag path"
        )

    registry = load_registry(repository_root / ".github/issueops-workflow-dispatch.yml")
    record = select_authorisation(
        registry, authorisation_id=authorisation_id, now=now
    )
    verify_workflow_hash(record, repository_root / TARGET_WORKFLOW_PATH)
    resolution = build_resolution(
        record=record, source_sha=github_sha, execution_ref=github_ref
    )

    client = api or GitHubReadAPI(repository, token)
    verify_tag_ref(
        client.get_tag(resolution.execution_tag),
        execution_ref=github_ref,
        source_sha=github_sha,
    )
    verify_ruleset(
        client.get_ruleset(record["execution_tag_ruleset_id"]), record
    )

    subject = canonical_subject(resolution=resolution, target_run={"id": run_id})
    subject_bytes = canonical_json_bytes(subject)
    subject_digest = sha256_bytes(subject_bytes)
    attestations = client.list_attestations(subject_digest)
    if not attestations:
        raise GuardError(
            "no dispatcher attestation exists for this exact target run"
        )

    verify_pinned_gh(gh_binary)
    verified: list[tuple[int, int]] = []
    signer_verified_but_conflicting = 0
    with tempfile.TemporaryDirectory(prefix="issueops-target-guard-") as tmp:
        root = Path(tmp)
        subject_path = root / "dispatch-subject.json"
        subject_path.write_bytes(subject_bytes)
        for index, item in enumerate(attestations):
            bundle_url = item.get("bundle_url")
            if not isinstance(bundle_url, str):
                raise GuardError(
                    "attestation collection contains an item without bundle_url"
                )
            bundle_path = root / f"bundle-{index}.json"
            bundle_path.write_bytes(client.fetch_bundle(bundle_url))
            payload = run_gh_verify(
                gh_binary=gh_binary,
                subject_path=subject_path,
                bundle_path=bundle_path,
                source_sha=github_sha,
                token=token,
            )
            if payload is None:
                continue
            try:
                dispatcher_run_id = verify_gh_result(
                    payload,
                    resolution=resolution,
                    target_run_id=run_id,
                    run_lookup=client.get_run_attempt,
                )
            except GuardError:
                signer_verified_but_conflicting += 1
                continue
            verified.append((index, dispatcher_run_id))

    if signer_verified_but_conflicting:
        raise GuardError(
            "a cryptographically verified canonical-signer receipt conflicts with the frozen target authority"
        )
    if len(verified) != 1:
        raise GuardError(
            "protected target requires exactly one qualifying canonical dispatcher receipt"
        )

    return {
        "authorisation_id": authorisation_id,
        "authorisation_sha": github_sha,
        "execution_ref": github_ref,
        "target_run_id": run_id,
        "subject_sha256": subject_digest,
        "dispatcher_run_id": verified[0][1],
        "ruleset_id": record["execution_tag_ruleset_id"],
        "ruleset_name": record["execution_tag_ruleset_name"],
    }


def _parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, default=Path("."))
    parser.add_argument("--gh-bin", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(sys.argv[1:] if argv is None else argv)
    try:
        result = execute_guard(
            repository_root=args.repository_root,
            github_ref=os.environ["GITHUB_REF"],
            github_sha=os.environ["GITHUB_SHA"],
            workflow_sha=os.environ["GITHUB_WORKFLOW_SHA"],
            run_id=int(os.environ["GITHUB_RUN_ID"]),
            run_attempt=int(os.environ["GITHUB_RUN_ATTEMPT"]),
            repository=os.environ["GITHUB_REPOSITORY"],
            token=os.environ["GITHUB_TOKEN"],
            gh_binary=args.gh_bin,
            now=datetime.now(timezone.utc),
        )
    except (KeyError, ValueError, GuardError) as exc:
        print(f"IssueOps target provenance rejected: {exc}", file=sys.stderr)
        return 1
    payload = json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())