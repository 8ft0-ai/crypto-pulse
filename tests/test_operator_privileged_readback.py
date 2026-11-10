from pathlib import Path
import json
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1] / "tools" / "operator"
sys.path.insert(0, str(ROOT))

from cryptopulse_operator.cli import parser
from cryptopulse_operator.evidence import EXIT_CODE, Evidence, Status
from cryptopulse_operator.github_read import GitHubReadError, GitHubReader
from cryptopulse_operator.privileged_readback import (
    auth_snapshot,
    environment_snapshot,
    protection_snapshot,
    publication_snapshot,
)
from cryptopulse_operator.process import ProcessResult

CONFIG = {
    "required_check": "Build site and check generated output",
    "required_check_app_id": 15368,
    "publication_environment": "deterministic-publication-control",
    "publication_app_id": 4618782,
    "publication_app_slug": "cryptopulse-deterministic-pub",
    "publication_ruleset_id": 20795849,
    "publication_branch": "main",
    "publication_secret_name": "DETERMINISTIC_PUBLICATION_APP_PRIVATE_KEY",
    "publication_app_id_variable": "DETERMINISTIC_PUBLICATION_APP_ID",
    "publication_app_slug_variable": "DETERMINISTIC_PUBLICATION_APP_SLUG",
    "publication_activation_variable": "DETERMINISTIC_PUBLICATION_ACTIVATION",
    "publication_pilot_run_variable": "DETERMINISTIC_PUBLICATION_PILOT_RUN_ID",
}


class PageRunner:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = []

    def gh(self, args, cwd=None):
        self.calls.append(tuple(args))
        if not self.outputs:
            raise AssertionError("unexpected gh call")
        code, payload = self.outputs.pop(0)
        return ProcessResult(code, payload if isinstance(payload, str) else json.dumps(payload), "")


class FakeGitHub:
    def __init__(self):
        self.activation = None
        self.strict = True
        self.check_app_id = 15368
        self.include_required_check = True
        self.app_id = 4618782
        self.app_slug = "cryptopulse-deterministic-pub"
        self.app_permissions = {"metadata": "read", "contents": "write", "pull_requests": "write"}
        self.app_bypass_mode = "pull_request"
        self.branch_policy_name = "main"
        self.secret_present = True
        self.env_app_id = "4618782"
        self.env_app_slug = "cryptopulse-deterministic-pub"
        self.protection_rules = []
        self.deny = None
        self.duplicate_env_variable = False
        self.sensitive_env_value = False

    def _maybe(self, name):
        if self.deny == name:
            raise GitHubReadError("denied")

    def viewer(self):
        self._maybe("viewer"); return {"login": "8ft0-ai"}

    def repository(self):
        self._maybe("repository"); return {"full_name": "8ft0-ai/crypto-pulse"}

    def main_branch(self):
        self._maybe("main_branch")
        return {"sha": "a" * 40, "tree_sha": "b" * 40, "protected": True, "required_checks": []}

    def branch_protection(self):
        self._maybe("branch_protection")
        checks = [] if not self.include_required_check else [{
            "context": "Build site and check generated output", "app_id": self.check_app_id
        }]
        return {"required_status_checks": {"strict": self.strict, "checks": checks}}

    def rulesets(self):
        self._maybe("rulesets")
        return [{"id": 20795849, "name": "Protect main", "target": "branch", "enforcement": "active"}]

    def ruleset(self, ruleset_id):
        self._maybe("ruleset")
        return {
            "id": 20795849, "name": "Protect main", "target": "branch", "enforcement": "active",
            "conditions": {"ref_name": {"include": ["refs/heads/main"], "exclude": []}},
            "rules": [{"type": "update"}],
            "bypass_actors": [
                {"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always"},
                {"actor_id": 4618782, "actor_type": "Integration", "bypass_mode": self.app_bypass_mode},
            ],
        }

    def environments(self):
        self._maybe("environments"); return [{"name": "deterministic-publication-control"}]

    def environment(self, name):
        self._maybe("environment")
        return {
            "name": name,
            "protection_rules": self.protection_rules,
            "deployment_branch_policy": {
                "protected_branches": False, "custom_branch_policies": True
            },
        }

    def deployment_branch_policies(self, name):
        self._maybe("deployment_branch_policies")
        return [{"id": 57519277, "name": self.branch_policy_name, "type": "branch"}]

    def environment_variables(self, name):
        self._maybe("environment_variables")
        slug = "token=github_pat_ABCDEFGHIJKLMNOPQRSTUV" if self.sensitive_env_value else self.env_app_slug
        values = [
            {"name": "DETERMINISTIC_PUBLICATION_APP_ID", "value": self.env_app_id},
            {"name": "DETERMINISTIC_PUBLICATION_APP_SLUG", "value": slug},
        ]
        if self.duplicate_env_variable:
            values.append(values[0].copy())
        return values

    def environment_secrets(self, name):
        self._maybe("environment_secrets")
        return [{"name": "DETERMINISTIC_PUBLICATION_APP_PRIVATE_KEY"}] if self.secret_present else []

    def repository_variables(self):
        self._maybe("repository_variables")
        return [] if self.activation is None else [{"name": "DETERMINISTIC_PUBLICATION_ACTIVATION", "value": self.activation}]

    def app(self, slug):
        self._maybe("app")
        return {"id": self.app_id, "slug": self.app_slug, "owner": {"login": "8ft0-ai"},
                "permissions": self.app_permissions, "events": []}

    def user_installations(self):
        self._maybe("user_installations")
        raise GitHubReadError(
            "publication App installation scope is unavailable through the permitted owner/admin credential"
        )

    def installation_repositories(self, installation_id):
        self._maybe("installation_repositories")
        raise GitHubReadError(
            "publication App installation repositories are unavailable through the permitted owner/admin credential"
        )


class SnapshotTests(unittest.TestCase):
    def test_capability_reports_installation_scope_unavailable(self):
        result = auth_snapshot(FakeGitHub(), CONFIG)
        self.assertEqual(result.status, Status.INCOMPLETE)
        self.assertFalse(result.complete)
        self.assertFalse(result.data["capabilities"]["user_installations"])
        self.assertFalse(result.data["capabilities"]["installation_repositories"])
        self.assertTrue(all(
            holds for name, holds in result.data["capabilities"].items()
            if name not in {"user_installations", "installation_repositories"}
        ))
        self.assertIn({"code": "privileged-read-capability-incomplete"}, result.findings)

        github = FakeGitHub(); github.deny = "branch_protection"
        denied = auth_snapshot(github, CONFIG)
        self.assertEqual(denied.status, Status.INCOMPLETE)
        self.assertFalse(denied.data["capabilities"]["classic_protection"])

    def test_auth_malformed_decision_critical_representations_are_incomplete(self):
        cases = [
            ("main", lambda github: setattr(github, "main_branch", lambda: {
                "sha": "a" * 40, "tree_sha": "b" * 40, "protected": "true", "required_checks": []
            })),
            ("classic", lambda github: setattr(github, "branch_protection", lambda: {})),
            ("rulesets", lambda github: setattr(github, "rulesets", lambda: [{
                "id": "20795849", "name": "Protect main", "target": "branch", "enforcement": "active"
            }])),
            ("ruleset-detail", lambda github: setattr(github, "ruleset", lambda _ruleset_id: {
                "id": 20795849, "name": "Protect main", "target": "branch", "enforcement": "active"
            })),
            ("environment-variables", lambda github: setattr(github, "environment_variables", lambda _name: [
                {"name": "DETERMINISTIC_PUBLICATION_APP_ID"}
            ])),
            ("app", lambda github: setattr(github, "app", lambda _slug: {
                "id": 4618782, "slug": "cryptopulse-deterministic-pub", "owner": {},
                "permissions": {"metadata": "read"}, "events": []
            })),
        ]
        capability = {
            "main": "current_main",
            "classic": "classic_protection",
            "rulesets": "rulesets",
            "ruleset-detail": "ruleset_detail",
            "environment-variables": "environment_variables",
            "app": "publication_app",
        }
        for label, mutate in cases:
            with self.subTest(label=label):
                github = FakeGitHub(); mutate(github)
                result = auth_snapshot(github, CONFIG)
                self.assertEqual(result.status, Status.INCOMPLETE)
                self.assertFalse(result.data["capabilities"][capability[label]])

    def test_auth_semantically_malformed_scalars_are_incomplete(self):
        cases = [
            ("main-sha", lambda github: setattr(github, "main_branch", lambda: {
                "sha": "x", "tree_sha": "b" * 40, "protected": True, "required_checks": []
            })),
            ("empty-check-context", lambda github: setattr(github, "branch_protection", lambda: {
                "required_status_checks": {"strict": True, "checks": [{"context": "", "app_id": 15368}]}
            })),
            ("zero-ruleset-id", lambda github: setattr(github, "rulesets", lambda: [{
                "id": 0, "name": "Protect main", "target": "branch", "enforcement": "active"
            }])),
            ("empty-bypass-mode", lambda github: setattr(github, "ruleset", lambda _ruleset_id: {
                "id": 20795849, "name": "Protect main", "target": "branch", "enforcement": "active",
                "conditions": {"ref_name": {"include": ["refs/heads/main"], "exclude": []}},
                "rules": [{"type": "update"}],
                "bypass_actors": [{"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": ""}],
            })),
            ("zero-policy-id", lambda github: setattr(github, "deployment_branch_policies", lambda _name: [
                {"id": 0, "name": "main", "type": "branch"}
            ])),
            ("zero-app-id", lambda github: setattr(github, "app", lambda _slug: {
                "id": 0, "slug": "cryptopulse-deterministic-pub", "owner": {"login": "8ft0-ai"},
                "permissions": {"metadata": "read"}, "events": []
            })),
        ]
        capability = {
            "main-sha": "current_main",
            "empty-check-context": "classic_protection",
            "zero-ruleset-id": "rulesets",
            "empty-bypass-mode": "ruleset_detail",
            "zero-policy-id": "deployment_branch_policies",
            "zero-app-id": "publication_app",
        }
        for label, mutate in cases:
            with self.subTest(label=label):
                github = FakeGitHub(); mutate(github)
                result = auth_snapshot(github, CONFIG)
                self.assertEqual(result.status, Status.INCOMPLETE)
                self.assertFalse(result.data["capabilities"][capability[label]])

    def test_malformed_main_identity_is_incomplete_across_composites(self):
        github = FakeGitHub()
        github.main_branch = lambda: {
            "sha": "not-a-git-oid", "tree_sha": "b" * 40, "protected": True, "required_checks": []
        }
        self.assertEqual(protection_snapshot(github, CONFIG).status, Status.INCOMPLETE)
        self.assertEqual(publication_snapshot(github, CONFIG).status, Status.INCOMPLETE)

    def test_auth_readable_contract_drift_keeps_non_scope_capabilities_readable(self):
        github = FakeGitHub()
        github.strict = False
        github.check_app_id = 999
        github.branch_policy_name = "release"
        github.app_permissions = {"metadata": "read"}
        github.activation = "pilot"
        result = auth_snapshot(github, CONFIG)
        self.assertEqual(result.status, Status.INCOMPLETE)
        self.assertTrue(result.data["capabilities"]["classic_protection"])
        self.assertTrue(result.data["capabilities"]["deployment_branch_policies"])
        self.assertTrue(result.data["capabilities"]["publication_app"])
        self.assertTrue(result.data["capabilities"]["repository_variables"])

    def test_malformed_privileged_response_is_incomplete(self):
        github = FakeGitHub()
        github.branch_protection = lambda: {"required_status_checks": {"strict": "true", "checks": []}}
        self.assertEqual(protection_snapshot(github, CONFIG).status, Status.INCOMPLETE)

    def test_parent_ruleset_source_metadata_is_typed_and_malformed_source_fails_closed(self):
        github = FakeGitHub()
        github.rulesets = lambda: [
            {"id": 20795849, "name": "Protect main", "target": "branch", "enforcement": "active"},
            {"id": 30000000, "name": "Org baseline", "target": "branch", "enforcement": "active",
             "source": "8ft0-ai", "source_type": "Organization"},
        ]
        result = protection_snapshot(github, CONFIG)
        self.assertEqual(result.status, Status.PASS)
        parent = next(item for item in result.data["rulesets"] if item["id"] == 30000000)
        self.assertEqual((parent["source"], parent["source_type"]), ("8ft0-ai", "Organization"))

        github = FakeGitHub()
        github.rulesets = lambda: [
            {"id": 20795849, "name": "Protect main", "target": "branch", "enforcement": "active"},
            {"id": 30000000, "name": "Org baseline", "target": "branch", "enforcement": "active",
             "source_type": "Organization"},
        ]
        self.assertEqual(protection_snapshot(github, CONFIG).status, Status.INCOMPLETE)

    def test_environment_protection_rules_are_typed(self):
        github = FakeGitHub()
        github.protection_rules = [
            {"id": 10, "type": "wait_timer", "wait_timer": 30},
            {
                "id": 11,
                "type": "required_reviewers",
                "prevent_self_review": True,
                "reviewers": [
                    {"type": "User", "reviewer": {"id": 1, "login": "octocat"}},
                    {"type": "Team", "reviewer": {"id": 2, "slug": "release-managers"}},
                ],
            },
            {"id": 12, "type": "branch_policy"},
        ]
        result = environment_snapshot(CONFIG["publication_environment"], github)
        self.assertEqual(result.status, Status.PASS)
        self.assertEqual(
            result.data["protection_metadata"]["protection_rules"],
            [
                {"id": 12, "type": "branch_policy"},
                {
                    "id": 11,
                    "type": "required_reviewers",
                    "prevent_self_review": True,
                    "reviewers": [
                        {"type": "Team", "id": 2, "slug": "release-managers"},
                        {"type": "User", "id": 1, "login": "octocat"},
                    ],
                },
                {"id": 10, "type": "wait_timer", "wait_timer": 30},
            ],
        )

    def test_malformed_environment_protection_rules_are_incomplete(self):
        cases = [
            [{"id": 10, "type": "wait_timer", "wait_timer": "30"}],
            [{"id": 0, "type": "wait_timer", "wait_timer": 30}],
            [{"id": 11, "type": "required_reviewers", "prevent_self_review": False, "reviewers": None}],
            [{"id": 12, "type": "unexpected-rule"}],
        ]
        for rules in cases:
            with self.subTest(rules=rules):
                github = FakeGitHub(); github.protection_rules = rules
                self.assertEqual(environment_snapshot(CONFIG["publication_environment"], github).status, Status.INCOMPLETE)
                auth = auth_snapshot(github, CONFIG)
                self.assertEqual(auth.status, Status.INCOMPLETE)
                self.assertFalse(auth.data["capabilities"]["environment"])

    def test_environment_duplicate_or_sensitive_value_is_incomplete(self):
        for field in ("duplicate_env_variable", "sensitive_env_value"):
            with self.subTest(field=field):
                github = FakeGitHub(); setattr(github, field, True)
                self.assertEqual(environment_snapshot(CONFIG["publication_environment"], github).status, Status.INCOMPLETE)

    def test_publication_is_incomplete_when_installation_scope_is_unavailable(self):
        for value in (None, "disabled", "pilot", "recurring"):
            with self.subTest(value=value):
                github = FakeGitHub(); github.activation = value
                result = publication_snapshot(github, CONFIG)
                self.assertEqual(result.status, Status.INCOMPLETE)
                self.assertFalse(result.complete)
                self.assertIn({"code": "publication-app-installation-scope-incomplete"}, result.findings)
                self.assertFalse(result.data["publication_installation_scope"]["readable"])
                self.assertTrue(result.data["publication_installation_scope"]["required"])

    def test_protection_contract_drift_remains_observable_while_publication_is_incomplete(self):
        cases = (("strict", False), ("include_required_check", False), ("check_app_id", 999),
                 ("app_bypass_mode", "always"))
        for field, value in cases:
            with self.subTest(field=field):
                github = FakeGitHub(); setattr(github, field, value)
                self.assertTrue(protection_snapshot(github, CONFIG).complete)
                result = publication_snapshot(github, CONFIG)
                self.assertEqual(result.status, Status.INCOMPLETE)
                self.assertTrue(any(not item["holds"] for item in result.assertions))

    def test_environment_contract_drift_remains_observable_while_publication_is_incomplete(self):
        cases = (("branch_policy_name", "release"), ("secret_present", False),
                 ("env_app_id", "999"), ("env_app_slug", "wrong-app"))
        for field, value in cases:
            with self.subTest(field=field):
                github = FakeGitHub(); setattr(github, field, value)
                self.assertTrue(environment_snapshot(CONFIG["publication_environment"], github).complete)
                result = publication_snapshot(github, CONFIG)
                self.assertEqual(result.status, Status.INCOMPLETE)
                self.assertTrue(any(not item["holds"] for item in result.assertions))

    def test_app_identity_and_permission_drift_cannot_override_scope_incompleteness(self):
        cases = [
            ("app_id", 99), ("app_slug", "other-app"),
            ("app_permissions", {"metadata": "read", "contents": "write"}),
        ]
        for field, value in cases:
            with self.subTest(field=field):
                github = FakeGitHub(); setattr(github, field, value)
                result = publication_snapshot(github, CONFIG)
                self.assertEqual(result.status, Status.INCOMPLETE)
                self.assertTrue(any(not item["holds"] for item in result.assertions))

    def test_evidence_is_deterministic_and_secret_metadata_only(self):
        first = publication_snapshot(FakeGitHub(), CONFIG)
        second = publication_snapshot(FakeGitHub(), CONFIG)
        def render(result):
            return Evidence(command="publication", repository="8ft0-ai/crypto-pulse",
                invocation_target={"kind": "deterministic-publication-control"},
                runtime={"commit_sha": "a" * 40}, remote=result.data, local={}, status=result.status,
                completeness={"complete": result.complete}, assertions=result.assertions,
                findings=result.findings).json_text()
        self.assertEqual(render(first), render(second))
        self.assertIn("DETERMINISTIC_PUBLICATION_APP_PRIVATE_KEY", render(first))
        self.assertNotIn("private-key-value", render(first))


class ReaderTests(unittest.TestCase):
    def test_rulesets_pagination_and_failures(self):
        runner = PageRunner([(0, [[{"id": 1}], [{"id": 2}]])])
        self.assertEqual(GitHubReader(runner).rulesets(), [{"id": 1}, {"id": 2}])
        self.assertIn("--paginate", runner.calls[0]); self.assertIn("--slurp", runner.calls[0])
        self.assertIn("includes_parents=true", runner.calls[0][-1])
        self.assertNotIn("includes_parents=false", runner.calls[0][-1])
        with self.assertRaises(GitHubReadError):
            GitHubReader(PageRunner([(1, "")])).rulesets()
        with self.assertRaises(GitHubReadError):
            GitHubReader(PageRunner([(0, [{"total_count": 2, "variables": [{"name": "A"}]}])])).repository_variables()

    def test_main_branch_rejects_non_boolean_protected_state(self):
        payload = {
            "commit": {"sha": "a" * 40, "commit": {"tree": {"sha": "b" * 40}}},
            "protected": "true",
            "protection": {"required_status_checks": {"checks": []}},
        }
        with self.assertRaises(GitHubReadError):
            GitHubReader(PageRunner([(0, payload)])).main_branch()

    def test_environment_name_encoded_and_secret_endpoint_metadata_only(self):
        runner = PageRunner([(0, {}), (0, [{"total_count": 0, "secrets": []}])])
        reader = GitHubReader(runner); reader.environment("prod/a b")
        self.assertTrue(runner.calls[0][-1].endswith("/environments/prod%2Fa%20b"))
        self.assertEqual(reader.environment_secrets("deterministic-publication-control"), [])
        self.assertTrue(runner.calls[1][-1].endswith("/secrets?per_page=100"))

    def test_all_slice_c_reader_calls_are_fixed_gets(self):
        outputs = [
            (0, {"login": "8ft0-ai"}), (0, {"full_name": "8ft0-ai/crypto-pulse"}),
            (0, {"required_status_checks": {"strict": True, "checks": []}}), (0, [[{"id": 20795849}]]),
            (0, {"id": 20795849}), (0, [{"total_count": 1, "environments": [{"name": "e"}]}]),
            (0, {"name": "e"}), (0, [{"total_count": 1, "branch_policies": [{"id": 1}]}]),
            (0, [{"total_count": 1, "variables": [{"name": "A", "value": "B"}]}]),
            (0, [{"total_count": 1, "secrets": [{"name": "S"}]}]),
            (0, [{"total_count": 1, "variables": [{"name": "R", "value": "V"}]}]),
            (0, {"id": 4618782}),
        ]
        runner = PageRunner(outputs); reader = GitHubReader(runner)
        reader.viewer(); reader.repository(); reader.branch_protection(); reader.rulesets(); reader.ruleset(20795849)
        reader.environments(); reader.environment("e"); reader.deployment_branch_policies("e")
        reader.environment_variables("e"); reader.environment_secrets("e"); reader.repository_variables()
        reader.app("cryptopulse-deterministic-pub")
        for call in runner.calls:
            self.assertEqual(call[0:3], ("api", "--method", "GET"))
            self.assertFalse({"POST", "PUT", "PATCH", "DELETE"}.intersection(call))

    def test_installation_scope_owner_credential_path_is_explicitly_unavailable(self):
        runner = PageRunner([])
        reader = GitHubReader(runner)
        with self.assertRaisesRegex(GitHubReadError, "permitted owner/admin credential"):
            reader.user_installations()
        with self.assertRaisesRegex(GitHubReadError, "permitted owner/admin credential"):
            reader.installation_repositories(77)
        self.assertEqual(runner.calls, [])

    def test_complete_multi_page_environment_collections(self):
        pages = [
            (0, [{"total_count": 2, "branch_policies": [{"id": 1}]}, {"total_count": 2, "branch_policies": [{"id": 2}]}]),
            (0, [{"total_count": 2, "variables": [{"name": "A"}]}, {"total_count": 2, "variables": [{"name": "B"}]}]),
            (0, [{"total_count": 2, "secrets": [{"name": "A"}]}, {"total_count": 2, "secrets": [{"name": "B"}]}]),
        ]
        reader = GitHubReader(PageRunner(pages))
        self.assertEqual(len(reader.deployment_branch_policies("e")), 2)
        self.assertEqual(len(reader.environment_variables("e")), 2)
        self.assertEqual(len(reader.environment_secrets("e")), 2)


class CliTests(unittest.TestCase):
    def test_slice_c_args_and_exit_codes(self):
        self.assertEqual(parser().parse_args(["auth", "--json"]).command, "auth")
        self.assertEqual(parser().parse_args(["protection", "--evidence"]).command, "protection")
        self.assertEqual(parser().parse_args(["environment", "deterministic-publication-control"]).name,
                         "deterministic-publication-control")
        self.assertEqual(parser().parse_args(["publication"]).command, "publication")
        with self.assertRaises(SystemExit):
            parser().parse_args(["environment", "bad\nname"])
        self.assertEqual([EXIT_CODE[s] for s in (Status.PASS, Status.FAIL, Status.INCOMPLETE, Status.ERROR)], [0, 2, 3, 4])


if __name__ == "__main__":
    unittest.main()
