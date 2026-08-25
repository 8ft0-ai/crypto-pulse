"""Typed privileged GitHub readback for operator-toolkit/v1 Slice C."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib
from typing import Any, Callable

from .evidence import Status
from .github_read import GitHubReader, GitHubReadError
from .redact import contains_sensitive_text


class PrivilegedReadbackError(RuntimeError):
    pass


@dataclass(frozen=True)
class ReadbackResult:
    data: dict[str, Any]
    status: Status
    complete: bool
    assertions: tuple[dict[str, Any], ...] = ()
    findings: tuple[dict[str, Any], ...] = ()


_CONFIG_TYPES: dict[str, type] = {
    "required_check": str,
    "required_check_app_id": int,
    "publication_environment": str,
    "publication_app_id": int,
    "publication_app_slug": str,
    "publication_ruleset_id": int,
    "publication_branch": str,
    "publication_secret_name": str,
    "publication_app_id_variable": str,
    "publication_app_slug_variable": str,
    "publication_activation_variable": str,
    "publication_pilot_run_variable": str,
}

_EXPECTED_APP_PERMISSIONS = {
    "metadata": "read",
    "contents": "write",
    "pull_requests": "write",
}


def load_config() -> dict[str, Any]:
    path = Path(__file__).resolve().parents[1] / "operator.toml"
    try:
        config = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise PrivilegedReadbackError("unable to read trusted Slice C configuration") from exc
    result: dict[str, Any] = {}
    for key, expected_type in _CONFIG_TYPES.items():
        value = config.get(key)
        if not isinstance(value, expected_type) or isinstance(value, bool):
            raise PrivilegedReadbackError(f"trusted Slice C configuration field {key} is invalid")
        if expected_type is str and (not value or contains_sensitive_text(value)):
            raise PrivilegedReadbackError(f"trusted Slice C configuration field {key} is unsafe")
        if expected_type is int and value <= 0:
            raise PrivilegedReadbackError(f"trusted Slice C configuration field {key} is invalid")
        result[key] = value
    return result


def _dict(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PrivilegedReadbackError(f"{label} is not an object")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise PrivilegedReadbackError(f"{label} is not an array")
    return value


def _str(value: Any, label: str, *, allow_none: bool = False) -> str | None:
    if value is None and allow_none:
        return None
    if not isinstance(value, str) or contains_sensitive_text(value):
        raise PrivilegedReadbackError(f"{label} is not a safe string")
    return value


def _nonempty_str(value: Any, label: str, *, allow_none: bool = False) -> str | None:
    text = _str(value, label, allow_none=allow_none)
    if text is None:
        return None
    if not text or any(ord(ch) < 32 for ch in text):
        raise PrivilegedReadbackError(f"{label} is not a non-empty printable string")
    return text


def _int(value: Any, label: str, *, allow_none: bool = False) -> int | None:
    if value is None and allow_none:
        return None
    if not isinstance(value, int) or isinstance(value, bool):
        raise PrivilegedReadbackError(f"{label} is not an integer")
    return value


def _positive_int(value: Any, label: str, *, allow_none: bool = False) -> int | None:
    number = _int(value, label, allow_none=allow_none)
    if number is None:
        return None
    if number <= 0:
        raise PrivilegedReadbackError(f"{label} is not a positive integer")
    return number


def _check_app_id(value: Any, label: str, *, allow_none: bool = False) -> int | None:
    number = _int(value, label, allow_none=allow_none)
    if number is None:
        return None
    if number == -1 or number > 0:
        return number
    raise PrivilegedReadbackError(f"{label} is not a valid required-check App id")


def _git_oid(value: Any, label: str) -> str:
    text = _nonempty_str(value, label)
    if len(text) != 40 or any(ch not in "0123456789abcdefABCDEF" for ch in text):
        raise PrivilegedReadbackError(f"{label} is not a full Git object id")
    return text


def _bool(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise PrivilegedReadbackError(f"{label} is not boolean")
    return value


def _public_value(value: Any, label: str, *, depth: int = 0) -> Any:
    if depth > 6:
        raise PrivilegedReadbackError(f"{label} nesting is too deep")
    if value is None or isinstance(value, bool) or (isinstance(value, int) and not isinstance(value, bool)):
        return value
    if isinstance(value, str):
        return _str(value, label)
    if isinstance(value, list):
        return [_public_value(item, f"{label} item", depth=depth + 1) for item in value]
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str) or contains_sensitive_text(key):
                raise PrivilegedReadbackError(f"{label} key is unsafe")
            result[key] = _public_value(item, f"{label}.{key}", depth=depth + 1)
        return result
    raise PrivilegedReadbackError(f"{label} has unsupported type")


def _parse_deployment_branch_policy(value: Any) -> dict[str, bool]:
    deployment = _dict(value, "deployment branch policy")
    return {
        "protected_branches": _bool(deployment.get("protected_branches"), "deployment branch policy protected_branches"),
        "custom_branch_policies": _bool(
            deployment.get("custom_branch_policies"), "deployment branch policy custom_branch_policies"
        ),
    }


def _parse_environment_reviewers(value: Any, label: str) -> list[dict[str, Any]]:
    reviewers: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()
    for index, raw in enumerate(_list(value, label)):
        entry = _dict(raw, f"{label} {index}")
        reviewer_type = _nonempty_str(entry.get("type"), f"{label} {index} type")
        reviewer = _dict(entry.get("reviewer"), f"{label} {index} reviewer")
        reviewer_id = _positive_int(reviewer.get("id"), f"{label} {index} reviewer id")
        identity = (reviewer_type, reviewer_id)
        if identity in seen:
            raise PrivilegedReadbackError(f"duplicate {label} reviewer")
        seen.add(identity)
        if reviewer_type == "User":
            reviewers.append(
                {
                    "type": reviewer_type,
                    "id": reviewer_id,
                    "login": _nonempty_str(reviewer.get("login"), f"{label} {index} reviewer login"),
                }
            )
        elif reviewer_type == "Team":
            reviewers.append(
                {
                    "type": reviewer_type,
                    "id": reviewer_id,
                    "slug": _nonempty_str(reviewer.get("slug"), f"{label} {index} reviewer slug"),
                }
            )
        else:
            raise PrivilegedReadbackError(f"{label} {index} reviewer type is unsupported")
    return sorted(
        reviewers,
        key=lambda item: (item["type"], item.get("login") or item.get("slug") or "", item["id"]),
    )


def _parse_environment_protection_rules(value: Any) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    seen: set[int] = set()
    for index, raw in enumerate(_list(value, "environment protection rules")):
        rule = _dict(raw, f"environment protection rule {index}")
        rule_id = _positive_int(rule.get("id"), f"environment protection rule {index} id")
        if rule_id in seen:
            raise PrivilegedReadbackError("duplicate environment protection rule id")
        seen.add(rule_id)
        rule_type = _nonempty_str(rule.get("type"), f"environment protection rule {index} type")
        record: dict[str, Any] = {"id": rule_id, "type": rule_type}
        if rule_type == "wait_timer":
            wait_timer = _int(rule.get("wait_timer"), f"environment protection rule {index} wait timer")
            if wait_timer < 0 or wait_timer > 43200:
                raise PrivilegedReadbackError("environment wait timer is outside GitHub bounds")
            record["wait_timer"] = wait_timer
        elif rule_type == "required_reviewers":
            record["prevent_self_review"] = _bool(
                rule.get("prevent_self_review"), f"environment protection rule {index} prevent_self_review"
            )
            record["reviewers"] = _parse_environment_reviewers(
                rule.get("reviewers"), f"environment protection rule {index} reviewers"
            )
        elif rule_type == "branch_policy":
            pass
        else:
            raise PrivilegedReadbackError(f"environment protection rule {index} type is unsupported")
        rules.append(record)
    return sorted(rules, key=lambda item: (item["type"], item["id"]))


def _result(data: dict[str, Any], assertions: list[dict[str, Any]], findings: list[dict[str, Any]] | None = None) -> ReadbackResult:
    findings = list(findings or [])
    failed = [item for item in assertions if not item["holds"]]
    findings.extend({"code": f"assertion-failed:{item['name']}"} for item in failed)
    return ReadbackResult(
        data=data,
        status=Status.FAIL if failed else Status.PASS,
        complete=True,
        assertions=tuple(assertions),
        findings=tuple(findings),
    )


def _incomplete(code: str, data: dict[str, Any] | None = None, assertions: list[dict[str, Any]] | None = None) -> ReadbackResult:
    return ReadbackResult(
        data=data or {},
        status=Status.INCOMPLETE,
        complete=False,
        assertions=tuple(assertions or ()),
        findings=({"code": code},),
    )


def _safe_snapshot(fn: Callable[[], ReadbackResult], code: str) -> ReadbackResult:
    try:
        return fn()
    except (GitHubReadError, PrivilegedReadbackError):
        return _incomplete(code)


def auth_snapshot(github: GitHubReader, config: dict[str, Any]) -> ReadbackResult:
    """Prove the authenticated identity can read every Slice C surface."""

    capabilities: dict[str, bool] = {}
    identity: dict[str, Any] = {}

    def probe(name: str, call: Callable[[], Any], validate: Callable[[Any], None] | None = None) -> Any | None:
        try:
            value = call()
            if validate is not None:
                validate(value)
            capabilities[name] = True
            return value
        except (GitHubReadError, PrivilegedReadbackError):
            capabilities[name] = False
            return None

    def validate_main(value: Any) -> None:
        main = _dict(value, "main branch")
        _git_oid(main.get("sha"), "main SHA")
        _git_oid(main.get("tree_sha"), "main tree SHA")
        _bool(main.get("protected"), "main protected")
        for index, item in enumerate(_list(main.get("required_checks"), "main required checks")):
            check = _dict(item, f"main required check {index}")
            _nonempty_str(check.get("context"), f"main required check {index} context")
            _check_app_id(check.get("app_id"), f"main required check {index} app id", allow_none=True)

    def validate_rulesets(value: Any) -> None:
        seen: set[int] = set()
        for index, item in enumerate(_list(value, "rulesets")):
            summary = _parse_ruleset_summary(item, f"ruleset {index}")
            if summary["id"] in seen:
                raise PrivilegedReadbackError("duplicate ruleset id")
            seen.add(summary["id"])

    def validate_environments(value: Any) -> None:
        seen: set[str] = set()
        for index, item in enumerate(_list(value, "environments")):
            environment = _dict(item, f"environment {index}")
            name = _nonempty_str(environment.get("name"), f"environment {index} name")
            if name in seen:
                raise PrivilegedReadbackError("duplicate environment name")
            seen.add(name)

    def validate_environment(value: Any) -> None:
        environment = _dict(value, "environment")
        _nonempty_str(environment.get("name"), "environment name")
        _parse_environment_protection_rules(environment.get("protection_rules"))
        deployment = environment.get("deployment_branch_policy")
        if deployment is not None:
            _parse_deployment_branch_policy(deployment)
        if "can_admins_bypass" in environment:
            _bool(environment.get("can_admins_bypass"), "environment can_admins_bypass")

    def validate_branch_policies(value: Any) -> None:
        for index, item in enumerate(_list(value, "deployment branch policies")):
            policy = _dict(item, f"deployment branch policy {index}")
            _positive_int(policy.get("id"), f"deployment branch policy {index} id")
            _nonempty_str(policy.get("name"), f"deployment branch policy {index} name")
            _nonempty_str(policy.get("type"), f"deployment branch policy {index} type")

    def validate_app(value: Any) -> None:
        app = _dict(value, "publication App")
        _positive_int(app.get("id"), "publication App id")
        _nonempty_str(app.get("slug"), "publication App slug")
        owner = _dict(app.get("owner"), "publication App owner")
        _nonempty_str(owner.get("login"), "publication App owner login")
        permissions = _dict(app.get("permissions"), "publication App permissions")
        for key, permission in permissions.items():
            if not isinstance(key, str) or not key or contains_sensitive_text(key):
                raise PrivilegedReadbackError("publication App permission name is unsafe")
            _nonempty_str(permission, f"publication App permission {key}")
        for item in _list(app.get("events"), "publication App events"):
            _nonempty_str(item, "publication App event")

    viewer = probe(
        "viewer",
        github.viewer,
        lambda value: _nonempty_str(_dict(value, "viewer").get("login"), "viewer login"),
    )
    if viewer is not None:
        identity["viewer"] = _nonempty_str(_dict(viewer, "viewer").get("login"), "viewer login")

    repository = probe(
        "repository",
        github.repository,
        lambda value: _nonempty_str(_dict(value, "repository").get("full_name"), "repository full name"),
    )
    if repository is not None:
        identity["repository"] = _nonempty_str(_dict(repository, "repository").get("full_name"), "repository full name")

    probe("current_main", github.main_branch, validate_main)
    probe(
        "classic_protection",
        github.branch_protection,
        lambda value: _parse_required_checks(_dict(value, "branch protection")),
    )
    probe("rulesets", github.rulesets, validate_rulesets)
    probe(
        "ruleset_detail",
        lambda: github.ruleset(config["publication_ruleset_id"]),
        _parse_ruleset_detail,
    )
    probe("environments", github.environments, validate_environments)
    probe(
        "environment",
        lambda: github.environment(config["publication_environment"]),
        validate_environment,
    )
    probe(
        "deployment_branch_policies",
        lambda: github.deployment_branch_policies(config["publication_environment"]),
        validate_branch_policies,
    )
    probe(
        "environment_variables",
        lambda: github.environment_variables(config["publication_environment"]),
        lambda value: _unique_named(_list(value, "environment variables"), "environment variable", include_value=True),
    )
    probe(
        "environment_secrets_metadata",
        lambda: github.environment_secrets(config["publication_environment"]),
        lambda value: _unique_named(_list(value, "environment secrets"), "environment secret", include_value=False),
    )
    probe(
        "repository_variables",
        github.repository_variables,
        lambda value: _unique_named(_list(value, "repository variables"), "repository variable", include_value=True),
    )
    probe("publication_app", lambda: github.app(config["publication_app_slug"]), validate_app)

    # GitHub does not expose the publication App's exact installation scope through
    # the permitted ordinary owner/admin credential. The documented /user/installations
    # surfaces require a GitHub App user access token, which is outside Slice C authority.
    capabilities["user_installations"] = False
    capabilities["installation_repositories"] = False

    assertions = [{"name": f"read-{name}", "holds": holds} for name, holds in sorted(capabilities.items())]
    data = {
        "identity": identity,
        "capabilities": capabilities,
        "publication_installation_scope": {
            "required": True,
            "readable": False,
            "reason": "owner-admin-credential-representation-unavailable",
        },
    }
    if not all(capabilities.values()):
        return ReadbackResult(
            data=data,
            status=Status.INCOMPLETE,
            complete=False,
            assertions=tuple(assertions),
            findings=(
                {"code": "publication-app-installation-scope-incomplete"},
                {"code": "privileged-read-capability-incomplete"},
            ),
        )
    return _result(data, assertions)


def _parse_required_checks(protection: dict[str, Any]) -> tuple[bool, list[dict[str, Any]]]:
    required = _dict(protection.get("required_status_checks"), "required status checks")
    strict = _bool(required.get("strict"), "required status checks strict")
    checks_raw = _list(required.get("checks"), "required status check bindings")
    checks: list[dict[str, Any]] = []
    for index, value in enumerate(checks_raw):
        check = _dict(value, f"required check {index}")
        checks.append(
            {
                "context": _nonempty_str(check.get("context"), f"required check {index} context"),
                "app_id": _check_app_id(check.get("app_id"), f"required check {index} app id", allow_none=True),
            }
        )
    return strict, sorted(checks, key=lambda item: (item["context"], -1 if item["app_id"] is None else item["app_id"]))


def _parse_ruleset_summary(value: Any, label: str) -> dict[str, Any]:
    ruleset = _dict(value, label)
    result = {
        "id": _positive_int(ruleset.get("id"), f"{label} id"),
        "name": _nonempty_str(ruleset.get("name"), f"{label} name"),
        "target": _nonempty_str(ruleset.get("target"), f"{label} target"),
        "enforcement": _nonempty_str(ruleset.get("enforcement"), f"{label} enforcement"),
    }
    if "source" in ruleset or "source_type" in ruleset:
        result["source"] = _nonempty_str(ruleset.get("source"), f"{label} source")
        result["source_type"] = _nonempty_str(ruleset.get("source_type"), f"{label} source type")
    return result


def _parse_ruleset_detail(value: Any) -> dict[str, Any]:
    ruleset = _dict(value, "ruleset detail")
    result = _parse_ruleset_summary(ruleset, "ruleset detail")
    conditions = _dict(ruleset.get("conditions"), "ruleset conditions")
    ref_name = _dict(conditions.get("ref_name"), "ruleset ref_name condition")
    includes = [_nonempty_str(item, "ruleset include") for item in _list(ref_name.get("include"), "ruleset includes")]
    excludes = [_nonempty_str(item, "ruleset exclude") for item in _list(ref_name.get("exclude"), "ruleset excludes")]

    rules: list[dict[str, Any]] = []
    for index, value in enumerate(_list(ruleset.get("rules"), "ruleset rules")):
        rule = _dict(value, f"ruleset rule {index}")
        record: dict[str, Any] = {"type": _nonempty_str(rule.get("type"), f"ruleset rule {index} type")}
        if "parameters" in rule:
            record["parameters"] = _public_value(rule.get("parameters"), f"ruleset rule {index} parameters")
        rules.append(record)

    bypass: list[dict[str, Any]] = []
    for index, value in enumerate(_list(ruleset.get("bypass_actors"), "ruleset bypass actors")):
        actor = _dict(value, f"ruleset bypass actor {index}")
        bypass.append(
            {
                "actor_id": _positive_int(actor.get("actor_id"), f"ruleset bypass actor {index} id"),
                "actor_type": _nonempty_str(actor.get("actor_type"), f"ruleset bypass actor {index} type"),
                "bypass_mode": _nonempty_str(actor.get("bypass_mode"), f"ruleset bypass actor {index} mode"),
            }
        )

    result.update(
        {
            "conditions": {"ref_name": {"include": sorted(includes), "exclude": sorted(excludes)}},
            "rules": sorted(rules, key=lambda item: item["type"]),
            "bypass_actors": sorted(bypass, key=lambda item: (item["actor_type"], item["actor_id"], item["bypass_mode"])),
        }
    )
    return result


def protection_snapshot(github: GitHubReader, config: dict[str, Any]) -> ReadbackResult:
    def collect() -> ReadbackResult:
        main = github.main_branch()
        protection = github.branch_protection()
        strict, checks = _parse_required_checks(_dict(protection, "branch protection"))
        summaries = [_parse_ruleset_summary(item, f"ruleset {index}") for index, item in enumerate(github.rulesets())]
        summaries.sort(key=lambda item: item["id"])
        expected = [item for item in summaries if item["id"] == config["publication_ruleset_id"]]
        if len(expected) > 1:
            raise PrivilegedReadbackError("expected ruleset appears more than once")
        detail = _parse_ruleset_detail(github.ruleset(config["publication_ruleset_id"])) if expected else None
        data = {
            "main": {
                "sha": _git_oid(main.get("sha"), "main SHA"),
                "tree_sha": _git_oid(main.get("tree_sha"), "main tree SHA"),
                "protected": _bool(main.get("protected"), "main protected"),
            },
            "classic": {"strict": strict, "required_checks": checks},
            "rulesets": summaries,
            "expected_ruleset": detail,
        }
        assertions = [
            {"name": "main-protected", "holds": data["main"]["protected"]},
            {"name": "expected-ruleset-present", "holds": detail is not None},
        ]
        return _result(data, assertions)

    return _safe_snapshot(collect, "protection-readback-incomplete")


def _unique_named(items: list[Any], label: str, *, include_value: bool) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, value in enumerate(items):
        item = _dict(value, f"{label} {index}")
        name = _nonempty_str(item.get("name"), f"{label} {index} name")
        if name in seen:
            raise PrivilegedReadbackError(f"duplicate {label} name")
        seen.add(name)
        record: dict[str, Any] = {"name": name}
        if include_value:
            record["value"] = _str(item.get("value"), f"{label} {index} value")
        for field in ("created_at", "updated_at"):
            if field in item:
                record[field] = _str(item.get(field), f"{label} {index} {field}", allow_none=True)
        records.append(record)
    return sorted(records, key=lambda item: item["name"])


def environment_snapshot(name: str, github: GitHubReader) -> ReadbackResult:
    def collect() -> ReadbackResult:
        environment = _dict(github.environment(name), "environment")
        actual_name = _nonempty_str(environment.get("name"), "environment name")
        protection_rules = _parse_environment_protection_rules(environment.get("protection_rules"))
        deployment = environment.get("deployment_branch_policy")
        if deployment is not None:
            deployment = _parse_deployment_branch_policy(deployment)
        policies: list[dict[str, Any]] = []
        for index, value in enumerate(github.deployment_branch_policies(name)):
            item = _dict(value, f"deployment branch policy {index}")
            policies.append(
                {
                    "id": _positive_int(item.get("id"), f"deployment branch policy {index} id"),
                    "name": _nonempty_str(item.get("name"), f"deployment branch policy {index} name"),
                    "type": _nonempty_str(item.get("type"), f"deployment branch policy {index} type"),
                }
            )
        policies.sort(key=lambda item: (item["type"], item["name"], item["id"]))
        variables = _unique_named(github.environment_variables(name), "environment variable", include_value=True)
        secrets = _unique_named(github.environment_secrets(name), "environment secret", include_value=False)
        metadata: dict[str, Any] = {"protection_rules": protection_rules}
        if "can_admins_bypass" in environment:
            metadata["can_admins_bypass"] = _bool(environment.get("can_admins_bypass"), "environment can_admins_bypass")
        data = {
            "name": actual_name,
            "deployment_branch_policy": deployment,
            "branch_policies": policies,
            "variables": variables,
            "secrets": secrets,
            "protection_metadata": metadata,
        }
        return _result(data, [{"name": "environment-name-matches", "holds": actual_name == name}])

    return _safe_snapshot(collect, "environment-readback-incomplete")


def _repository_variables(github: GitHubReader) -> list[dict[str, Any]]:
    return _unique_named(github.repository_variables(), "repository variable", include_value=True)


def _app_snapshot(github: GitHubReader, config: dict[str, Any]) -> dict[str, Any]:
    app = _dict(github.app(config["publication_app_slug"]), "publication App")
    owner = _dict(app.get("owner"), "publication App owner")
    permissions = _dict(app.get("permissions"), "publication App permissions")
    typed_permissions: dict[str, str] = {}
    for key, value in permissions.items():
        if not isinstance(key, str) or not key or contains_sensitive_text(key):
            raise PrivilegedReadbackError("publication App permission name is unsafe")
        typed_permissions[key] = _nonempty_str(value, f"publication App permission {key}")
    events = [_nonempty_str(item, "publication App event") for item in _list(app.get("events"), "publication App events")]
    return {
        "id": _positive_int(app.get("id"), "publication App id"),
        "slug": _nonempty_str(app.get("slug"), "publication App slug"),
        "owner": _nonempty_str(owner.get("login"), "publication App owner login"),
        "permissions": dict(sorted(typed_permissions.items())),
        "events": sorted(events),
    }


def publication_snapshot(github: GitHubReader, config: dict[str, Any]) -> ReadbackResult:
    def collect() -> ReadbackResult:
        protection = protection_snapshot(github, config)
        if not protection.complete:
            return _incomplete("publication-protection-incomplete")
        environment = environment_snapshot(config["publication_environment"], github)
        if not environment.complete:
            return _incomplete("publication-environment-incomplete")
        variables = _repository_variables(github)
        app = _app_snapshot(github, config)

        variable_map = {item["name"]: item["value"] for item in variables}
        env_variable_map = {item["name"]: item["value"] for item in environment.data["variables"]}
        secret_names = {item["name"] for item in environment.data["secrets"]}
        classic = protection.data["classic"]
        ruleset = protection.data["expected_ruleset"]

        required_check_holds = {
            "context": config["required_check"],
            "app_id": config["required_check_app_id"],
        } in classic["required_checks"]

        ruleset_main = False
        ruleset_update = False
        bypass_exact = False
        if ruleset is not None:
            ref_condition = ruleset["conditions"]["ref_name"]
            ruleset_main = (
                ruleset["id"] == config["publication_ruleset_id"]
                and ruleset["target"] == "branch"
                and ruleset["enforcement"] == "active"
                and ref_condition["include"] == ["refs/heads/main"]
                and ref_condition["exclude"] == []
            )
            ruleset_update = [item["type"] for item in ruleset["rules"]] == ["update"]
            bypass_exact = ruleset["bypass_actors"] == sorted(
                [
                    {
                        "actor_id": 5,
                        "actor_type": "RepositoryRole",
                        "bypass_mode": "always",
                    },
                    {
                        "actor_id": config["publication_app_id"],
                        "actor_type": "Integration",
                        "bypass_mode": "pull_request",
                    },
                ],
                key=lambda item: (item["actor_type"], item["actor_id"], item["bypass_mode"]),
            )

        deployment = environment.data["deployment_branch_policy"]
        branch_policies = environment.data["branch_policies"]
        environment_policy_ok = (
            len(branch_policies) == 1
            and isinstance(deployment, dict)
            and deployment.get("protected_branches") is False
            and deployment.get("custom_branch_policies") is True
            and branch_policies[0]["name"] == config["publication_branch"]
            and branch_policies[0]["type"] == "branch"
        )

        activation_value = variable_map.get(config["publication_activation_variable"])
        activation_inert = activation_value is None or activation_value == "disabled"
        app_identity_ok = app["id"] == config["publication_app_id"] and app["slug"] == config["publication_app_slug"]
        app_permissions_ok = app["permissions"] == _EXPECTED_APP_PERMISSIONS

        assertions = [
            {"name": "protected-main-readable-and-protected", "holds": protection.data["main"]["protected"]},
            {"name": "classic-required-checks-strict", "holds": classic["strict"]},
            {"name": "required-check-app-binding", "holds": required_check_holds},
            {"name": "publication-ruleset-main-active", "holds": ruleset_main},
            {"name": "publication-ruleset-update-rule", "holds": ruleset_update},
            {"name": "publication-ruleset-bypass-set-exact", "holds": bypass_exact},
            {"name": "publication-app-identity", "holds": app_identity_ok},
            {"name": "publication-app-permissions-exact", "holds": app_permissions_ok},
            {
                "name": "publication-environment-identity",
                "holds": environment.data["name"] == config["publication_environment"],
            },
            {"name": "publication-environment-main-only", "holds": environment_policy_ok},
            {"name": "publication-private-key-secret-present", "holds": config["publication_secret_name"] in secret_names},
            {
                "name": "publication-app-id-environment-variable",
                "holds": env_variable_map.get(config["publication_app_id_variable"]) == str(config["publication_app_id"]),
            },
            {
                "name": "publication-app-slug-environment-variable",
                "holds": env_variable_map.get(config["publication_app_slug_variable"]) == config["publication_app_slug"],
            },
            {"name": "publication-activation-inert", "holds": activation_inert},
        ]

        data = {
            "main": protection.data["main"],
            "protection": {"classic": classic, "ruleset": ruleset},
            "environment": environment.data,
            "repository_variables": variables,
            "publication_app": app,
            "publication_installation_scope": {
                "required": True,
                "readable": False,
                "reason": "owner-admin-credential-representation-unavailable",
            },
            "activation": {
                "value": activation_value,
                "pilot_run_id": variable_map.get(config["publication_pilot_run_variable"]),
            },
        }
        findings = [{"code": "publication-app-installation-scope-incomplete"}]
        findings.extend(
            {"code": f"assertion-failed:{item['name']}"}
            for item in assertions
            if not item["holds"]
        )
        return ReadbackResult(
            data=data,
            status=Status.INCOMPLETE,
            complete=False,
            assertions=tuple(assertions),
            findings=tuple(findings),
        )

    return _safe_snapshot(collect, "publication-readback-incomplete")
