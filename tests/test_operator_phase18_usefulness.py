from contextlib import contextmanager, redirect_stdout
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1] / "tools" / "operator"
sys.path.insert(0, str(ROOT))

from cryptopulse_operator import cli
from cryptopulse_operator.commands import phase18_usefulness
from cryptopulse_operator.evidence import Evidence, Status
from cryptopulse_operator.process import ProcessRunner


MAIN_SHA = "1" * 40
MAIN_TREE = "2" * 40
SERIES_KEYS = ("BTC.price_usd", "ETH.price_usd", "SOL.price_usd")
_MISSING_MODULE = object()


@contextmanager
def isolated_modules(names):
    """Restore only the selected module names touched by a loader test."""
    saved = {name: sys.modules.get(name, _MISSING_MODULE) for name in names}
    for name in names:
        sys.modules.pop(name, None)
    try:
        yield
    finally:
        for name in names:
            sys.modules.pop(name, None)
        for name, module in saved.items():
            if module is not _MISSING_MODULE:
                sys.modules[name] = module


def trusted_gate(*, commit_sha=MAIN_SHA, tree_sha=MAIN_TREE):
    return SimpleNamespace(
        runtime={
            "repository": "8ft0-ai/crypto-pulse",
            "commit_sha": commit_sha,
            "tree_sha": tree_sha,
            "clean": True,
            "provenance": "current-main",
        },
        status=None,
        complete=True,
        findings=(),
        assertions=({"name": "runtime-trusted", "holds": True},),
    )


def blocked_gate(status):
    return SimpleNamespace(
        runtime={
            "repository": "8ft0-ai/crypto-pulse",
            "clean": status is not Status.ERROR,
            "provenance": None,
        },
        status=status,
        complete=status is not Status.INCOMPLETE,
        findings=({"code": f"gate-{status.value.lower()}"},),
        assertions=({"name": "runtime-trusted", "holds": False},),
    )


class FakeGitHub:
    def __init__(self, *, sha=MAIN_SHA, tree=MAIN_TREE, protected=True):
        self.sha = sha
        self.tree = tree
        self.protected = protected

    def main_branch(self):
        return {
            "sha": self.sha,
            "tree_sha": self.tree,
            "protected": self.protected,
            "required_checks": [],
        }


def base_bundle():
    return {
        "contract": "phase18-public-multi-asset-price-evidence/v1",
        "repository_context": {"commit_sha": MAIN_SHA},
        "window": {
            "start_utc": "2026-08-21T06:00:00Z",
            "end_utc": "2026-08-22T05:00:00Z",
        },
        "series": [{"series_key": key} for key in SERIES_KEYS],
        "bundle_id": "a" * 64,
    }


def fake_contracts(
    *,
    pair_counts=None,
    second_bundle=None,
    phase15_match=True,
    render_values=None,
    validator_error=False,
    first_build_error=False,
    materialised=True,
    second_build_error=False,
    second_materialised=True,
    phase15_error=False,
    phase15_materialised=True,
    projection_error=False,
    render_error=False,
):
    pair_counts = dict(pair_counts or {key: 2 for key in SERIES_KEYS})
    first = base_bundle()
    calls = {
        "phase18_build_commits": [],
        "phase15_build_commits": [],
        "validated": 0,
        "projection_keys": [],
        "rendered": 0,
    }
    build_count = {"value": 0}

    def canonical_bundle_bytes(value):
        return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def build_phase18(_root, commit_sha):
        calls["phase18_build_commits"].append(commit_sha)
        build_count["value"] += 1
        if build_count["value"] == 1:
            if first_build_error:
                raise RuntimeError("first build failed")
            if not materialised:
                return None
            return copy.deepcopy(first)
        if second_build_error:
            raise RuntimeError("second build failed")
        if not second_materialised:
            return None
        if second_bundle is not None:
            return copy.deepcopy(second_bundle)
        return copy.deepcopy(first)

    def validate(_root, bundle):
        calls["validated"] += 1
        if validator_error:
            raise ValueError("invalid")
        return bundle

    phase18 = SimpleNamespace(
        PHASE18_CONTRACT_VERSION=first["contract"],
        PUBLIC_SERIES_KEYS=SERIES_KEYS,
        build_multi_asset_temporal_evidence=build_phase18,
        validate_multi_asset_temporal_evidence=validate,
        canonical_bundle_bytes=canonical_bundle_bytes,
    )

    def build_phase15(_root, commit_sha):
        calls["phase15_build_commits"].append(commit_sha)
        if phase15_error:
            raise RuntimeError("phase15 failed")
        if not phase15_materialised:
            return None
        record = copy.deepcopy(first["series"][0])
        if not phase15_match:
            record["series_key"] = "BTC.other"
        return record

    def canonical_phase15(record):
        return json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")

    phase15 = SimpleNamespace(
        build_public_temporal_evidence=build_phase15,
        canonical_public_evidence_bytes=canonical_phase15,
    )

    def project(_member, series_key):
        calls["projection_keys"].append(series_key)
        if projection_error:
            raise RuntimeError("projection failed")
        return {
            "value_count": 7,
            "continuous_pair_count": pair_counts[series_key],
        }

    reader = SimpleNamespace(_reader_projection_for_series=project)

    render_queue = list(
        render_values or ["<section>same</section>", "<section>same</section>"]
    )

    def render(_root, _bundle):
        calls["rendered"] += 1
        if render_error:
            raise RuntimeError("render failed")
        return render_queue.pop(0) if render_queue else "<section>same</section>"

    renderer = SimpleNamespace(render_multi_asset_temporal_evidence=render)
    return {
        "phase18": phase18,
        "phase15": phase15,
        "reader": reader,
        "renderer": renderer,
    }, calls


class GitRepositoryFixture:
    def __init__(self, testcase):
        self.testcase = testcase
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.scripts = self.root / "scripts"
        self.scripts.mkdir()
        self.runner = ProcessRunner()
        if not self.runner.has_executable("git"):
            testcase.skipTest("git executable unavailable")
        for name in {
            *phase18_usefulness._CONTRACT_MODULE_NAMES,
            "crypto_observation_hour_series",
        }:
            (self.scripts / f"{name}.py").write_text(
                f'NAME = "{name}"\n',
                encoding="utf-8",
            )
        self._git("init")
        self._git("config", "user.name", "CryptoPulse test")
        self._git("config", "user.email", "cryptopulse-test@example.invalid")
        self._git("add", "scripts")
        self._git("commit", "-m", "fixture")

    def _git(self, *args):
        result = self.runner.git(["-C", str(self.root), *args])
        self.testcase.assertEqual(
            result.returncode,
            0,
            msg=f"git {' '.join(args)} failed: {result.stderr}",
        )
        return result

    def close(self):
        self.temp.cleanup()


class Phase18ContractLoaderTests(unittest.TestCase):
    def test_runtime_gate_blocks_before_repository_modules_load(self):
        loader = Mock()
        with (
            patch.object(
                phase18_usefulness,
                "runtime_gate",
                return_value=blocked_gate(Status.ERROR),
            ),
            patch.object(phase18_usefulness, "_load_contracts", loader),
        ):
            result = phase18_usefulness.run(object(), FakeGitHub())
        self.assertEqual(result.status, Status.ERROR)
        loader.assert_not_called()

    def test_preloaded_transitive_repository_module_blocks_authoritative_execution(self):
        fixture = GitRepositoryFixture(self)
        names = {
            *phase18_usefulness._CONTRACT_MODULE_NAMES,
            "crypto_observation_hour_series",
        }
        try:
            with isolated_modules(names):
                poisoned = ModuleType("crypto_observation_hour_series")
                poisoned.__file__ = "/tmp/poisoned/crypto_observation_hour_series.py"
                sys.modules["crypto_observation_hour_series"] = poisoned
                with (
                    patch.object(
                        phase18_usefulness,
                        "runtime_gate",
                        return_value=trusted_gate(),
                    ),
                    patch.object(
                        phase18_usefulness,
                        "runtime_root",
                        return_value=fixture.root,
                    ),
                ):
                    result = phase18_usefulness.run(fixture.runner, FakeGitHub())
        finally:
            fixture.close()

        self.assertEqual(result.status, Status.ERROR)
        self.assertEqual(result.findings[-1]["code"], "phase18-contract-load-failed")
        self.assertEqual(result.local["USEFULNESS_GATE"], "ERROR")

    def test_real_deferred_loader_accepts_exact_regular_head_blobs(self):
        fixture = GitRepositoryFixture(self)
        names = {
            *phase18_usefulness._CONTRACT_MODULE_NAMES,
            "crypto_observation_hour_series",
        }
        try:
            with isolated_modules(names):
                contracts = phase18_usefulness._load_contracts(
                    fixture.root,
                    fixture.runner,
                )
                self.assertEqual(
                    set(contracts),
                    {"phase18", "phase15", "reader", "renderer"},
                )
        finally:
            fixture.close()

    def test_skip_worktree_modified_contract_is_rejected(self):
        fixture = GitRepositoryFixture(self)
        target = "scripts/phase18_multi_asset_temporal_evidence.py"
        try:
            fixture._git("update-index", "--skip-worktree", target)
            (fixture.root / target).write_text("NAME = 'poisoned'\n", encoding="utf-8")
            status = fixture._git("status", "--porcelain=v1", "--untracked-files=all")
            self.assertEqual(status.stdout.strip(), "")
            with self.assertRaisesRegex(RuntimeError, "hidden index state|bytes differ"):
                phase18_usefulness._load_contracts(fixture.root, fixture.runner)
        finally:
            fixture.close()

    def test_untracked_repository_shadow_is_rejected(self):
        fixture = GitRepositoryFixture(self)
        try:
            (fixture.scripts / "shadow.py").write_text("POISON = True\n", encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "untracked repository scripts"):
                phase18_usefulness._load_contracts(fixture.root, fixture.runner)
        finally:
            fixture.close()

    def test_ignored_bytecode_shadow_is_rejected(self):
        fixture = GitRepositoryFixture(self)
        try:
            (fixture.root / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
            fixture._git("add", ".gitignore")
            fixture._git("commit", "-m", "ignore bytecode")
            cache = fixture.scripts / "__pycache__"
            cache.mkdir()
            (cache / "phase18_multi_asset_temporal_evidence.cpython-312.pyc").write_bytes(
                b"not-real-bytecode"
            )
            with self.assertRaisesRegex(RuntimeError, "ignored repository scripts"):
                phase18_usefulness._load_contracts(fixture.root, fixture.runner)
        finally:
            fixture.close()

    def test_contract_loader_rejects_wrong_direct_module_origin(self):
        fixture = GitRepositoryFixture(self)
        names = {
            *phase18_usefulness._CONTRACT_MODULE_NAMES,
            "crypto_observation_hour_series",
        }
        actual_module_origin = phase18_usefulness._module_origin

        def fake_origin(module):
            if getattr(module, "__name__", None) == "phase18_multi_asset_temporal_evidence":
                return (fixture.root / "outside.py").resolve()
            return actual_module_origin(module)

        try:
            with isolated_modules(names):
                with patch.object(
                    phase18_usefulness,
                    "_module_origin",
                    side_effect=fake_origin,
                ):
                    with self.assertRaisesRegex(
                        RuntimeError,
                        "repository contract module origin mismatch",
                    ):
                        phase18_usefulness._load_contracts(
                            fixture.root,
                            fixture.runner,
                        )
        finally:
            fixture.close()


class Phase18UsefulnessCommandTests(unittest.TestCase):
    def run_with(self, contracts, *, gate=None, github=None):
        gate = gate or trusted_gate()
        github = github or FakeGitHub()
        with (
            patch.object(phase18_usefulness, "runtime_gate", return_value=gate),
            patch.object(phase18_usefulness, "_load_contracts", return_value=contracts),
            patch.object(
                phase18_usefulness,
                "runtime_root",
                return_value=Path("/trusted/repo"),
            ),
        ):
            return phase18_usefulness.run(object(), github)

    def test_incomplete_and_untrusted_runtime_statuses_propagate(self):
        for status in (Status.INCOMPLETE, Status.ERROR):
            with self.subTest(status=status):
                contracts, _ = fake_contracts()
                result = self.run_with(contracts, gate=blocked_gate(status))
                self.assertEqual(result.status, status)
                self.assertEqual(result.local["USEFULNESS_GATE"], status.value)

    def test_ancestor_or_candidate_runtime_cannot_execute_authoritative_proof(self):
        contracts, _ = fake_contracts()
        loader = Mock(return_value=contracts)
        gate = trusted_gate(commit_sha="3" * 40)
        with (
            patch.object(phase18_usefulness, "runtime_gate", return_value=gate),
            patch.object(phase18_usefulness, "_load_contracts", loader),
        ):
            result = phase18_usefulness.run(object(), FakeGitHub())
        self.assertEqual(result.status, Status.ERROR)
        self.assertEqual(
            result.findings[-1]["code"],
            "runtime-not-current-protected-main",
        )
        loader.assert_not_called()

    def test_tree_mismatch_cannot_execute_authoritative_proof(self):
        contracts, _ = fake_contracts()
        loader = Mock(return_value=contracts)
        gate = trusted_gate(tree_sha="4" * 40)
        with (
            patch.object(phase18_usefulness, "runtime_gate", return_value=gate),
            patch.object(phase18_usefulness, "_load_contracts", loader),
        ):
            result = phase18_usefulness.run(object(), FakeGitHub())
        self.assertEqual(result.status, Status.ERROR)
        self.assertEqual(
            result.findings[-1]["code"],
            "runtime-tree-not-current-protected-main",
        )
        loader.assert_not_called()

    def test_unprotected_main_cannot_execute_authoritative_proof(self):
        contracts, _ = fake_contracts()
        loader = Mock(return_value=contracts)
        with (
            patch.object(phase18_usefulness, "runtime_gate", return_value=trusted_gate()),
            patch.object(phase18_usefulness, "_load_contracts", loader),
        ):
            result = phase18_usefulness.run(object(), FakeGitHub(protected=False))
        self.assertEqual(result.status, Status.ERROR)
        self.assertEqual(result.findings[-1]["code"], "main-not-protected")
        loader.assert_not_called()

    def test_exact_current_main_reuses_all_merged_contracts_and_commit_binding(self):
        contracts, calls = fake_contracts()
        result = self.run_with(contracts)
        self.assertEqual(result.status, Status.PASS)
        self.assertEqual(calls["phase18_build_commits"], [MAIN_SHA, MAIN_SHA])
        self.assertEqual(calls["phase15_build_commits"], [MAIN_SHA])
        self.assertEqual(calls["validated"], 1)
        self.assertEqual(calls["projection_keys"], list(SERIES_KEYS))
        self.assertEqual(calls["rendered"], 2)
        self.assertEqual(result.remote["protected_main_commit"], MAIN_SHA)
        self.assertEqual(result.remote["protected_main_tree"], MAIN_TREE)
        self.assertEqual(result.local["series_order"], list(SERIES_KEYS))
        self.assertEqual(result.local["USEFULNESS_GATE"], "PASS")
        for symbol in ("BTC", "ETH", "SOL"):
            self.assertEqual(result.local[f"{symbol}_asserted_slots"], 7)
            self.assertEqual(result.local[f"{symbol}_continuous_pairs"], 2)

    def test_first_materialisation_unavailable_is_incomplete(self):
        contracts, _ = fake_contracts(materialised=False)
        result = self.run_with(contracts)
        self.assertEqual(result.status, Status.INCOMPLETE)
        self.assertEqual(result.local["USEFULNESS_GATE"], "INCOMPLETE")

    def test_first_materialisation_exception_is_error(self):
        contracts, _ = fake_contracts(first_build_error=True)
        result = self.run_with(contracts)
        self.assertEqual(result.status, Status.ERROR)
        self.assertEqual(result.local["USEFULNESS_GATE"], "ERROR")

    def test_validator_exception_is_error_and_stops_downstream_derivation(self):
        contracts, calls = fake_contracts(validator_error=True)
        result = self.run_with(contracts)
        self.assertEqual(result.status, Status.ERROR)
        self.assertEqual(result.local["phase18_replay_validation"], "ERROR")
        self.assertEqual(result.local["USEFULNESS_GATE"], "ERROR")
        self.assertEqual(calls["phase18_build_commits"], [MAIN_SHA])
        self.assertEqual(calls["phase15_build_commits"], [])
        self.assertEqual(calls["projection_keys"], [])
        self.assertEqual(calls["rendered"], 0)
        self.assertNotIn("bundle_canonical_identity_or_sha256", result.local)

    def test_second_materialisation_exception_is_error(self):
        contracts, _ = fake_contracts(second_build_error=True)
        result = self.run_with(contracts)
        self.assertEqual(result.status, Status.ERROR)
        self.assertEqual(
            result.findings[-1]["code"],
            "independent-bundle-reproduction-error",
        )

    def test_second_materialisation_unavailable_is_incomplete(self):
        contracts, _ = fake_contracts(second_materialised=False)
        result = self.run_with(contracts)
        self.assertEqual(result.status, Status.INCOMPLETE)
        self.assertEqual(
            result.findings[-1]["code"],
            "independent-bundle-reproduction-unavailable",
        )

    def test_independent_rebuild_mismatch_is_completed_fail(self):
        changed = base_bundle()
        changed["bundle_id"] = "b" * 64
        contracts, _ = fake_contracts(second_bundle=changed)
        result = self.run_with(contracts)
        self.assertEqual(result.status, Status.FAIL)
        self.assertTrue(result.completeness["complete"])
        self.assertEqual(result.local["independent_bundle_reproduction"], "FAIL")

    def test_phase15_exception_is_error(self):
        contracts, _ = fake_contracts(phase15_error=True)
        result = self.run_with(contracts)
        self.assertEqual(result.status, Status.ERROR)
        self.assertEqual(
            result.findings[-1]["code"],
            "phase15-btc-compatibility-error",
        )

    def test_phase15_unavailable_is_incomplete(self):
        contracts, _ = fake_contracts(phase15_materialised=False)
        result = self.run_with(contracts)
        self.assertEqual(result.status, Status.INCOMPLETE)
        self.assertEqual(
            result.findings[-1]["code"],
            "phase15-btc-evidence-unavailable",
        )

    def test_phase15_btc_mismatch_is_completed_fail(self):
        contracts, _ = fake_contracts(phase15_match=False)
        result = self.run_with(contracts)
        self.assertEqual(result.status, Status.FAIL)
        self.assertTrue(result.completeness["complete"])
        self.assertEqual(result.local["phase15_btc_compatibility"], "FAIL")

    def test_projection_exception_is_error(self):
        contracts, _ = fake_contracts(projection_error=True)
        result = self.run_with(contracts)
        self.assertEqual(result.status, Status.ERROR)
        self.assertEqual(
            result.findings[-1]["code"],
            "phase18-reader-projection-error",
        )

    def test_each_series_requires_a_continuous_pair(self):
        for failed_key in SERIES_KEYS:
            with self.subTest(series_key=failed_key):
                counts = {key: 2 for key in SERIES_KEYS}
                counts[failed_key] = 0
                contracts, _ = fake_contracts(pair_counts=counts)
                result = self.run_with(contracts)
                self.assertEqual(result.status, Status.FAIL)
                self.assertTrue(result.completeness["complete"])
                self.assertEqual(
                    result.local[f"{failed_key.split('.', 1)[0]}_continuous_pairs"],
                    0,
                )

    def test_renderer_exception_is_error(self):
        contracts, _ = fake_contracts(render_error=True)
        result = self.run_with(contracts)
        self.assertEqual(result.status, Status.ERROR)
        self.assertEqual(
            result.findings[-1]["code"],
            "phase18-renderer-execution-error",
        )

    def test_repeated_render_digest_mismatch_is_completed_fail(self):
        contracts, _ = fake_contracts(
            render_values=["<section>first</section>", "<section>second</section>"]
        )
        result = self.run_with(contracts)
        self.assertEqual(result.status, Status.FAIL)
        self.assertTrue(result.completeness["complete"])
        self.assertFalse(result.local["renderer_deterministic"])
        self.assertNotEqual(
            result.local["renderer_sha256_first"],
            result.local["renderer_sha256_second"],
        )

    def test_successful_evidence_is_deterministic_and_complete(self):
        first_contracts, _ = fake_contracts()
        second_contracts, _ = fake_contracts()
        first = self.run_with(first_contracts)
        second = self.run_with(second_contracts)
        self.assertEqual(first.envelope(), second.envelope())
        self.assertTrue(first.completeness["complete"])
        required = {
            "phase18_contract",
            "bundle_id",
            "bundle_canonical_identity_or_sha256",
            "window_start_utc",
            "window_end_utc",
            "series_order",
            "phase18_replay_validation",
            "independent_bundle_reproduction",
            "phase15_btc_compatibility",
            "BTC_asserted_slots",
            "BTC_continuous_pairs",
            "ETH_asserted_slots",
            "ETH_continuous_pairs",
            "SOL_asserted_slots",
            "SOL_continuous_pairs",
            "renderer_sha256_first",
            "renderer_sha256_second",
            "renderer_deterministic",
            "USEFULNESS_GATE",
        }
        self.assertTrue(required.issubset(first.local))


class Phase18UsefulnessCliTests(unittest.TestCase):
    def evidence(self, status=Status.PASS):
        return Evidence(
            command="phase18-usefulness",
            repository="8ft0-ai/crypto-pulse",
            invocation_target={"kind": "phase18-usefulness"},
            runtime={"repository": "8ft0-ai/crypto-pulse"},
            remote={},
            local={"USEFULNESS_GATE": status.value},
            status=status,
            completeness={"complete": status is Status.PASS},
        )

    def test_cli_registers_human_json_and_evidence_modes_with_exit_mapping(self):
        cases = (
            ([], "phase18-usefulness: FAIL\n"),
            (["--json"], '"command":"phase18-usefulness"'),
            (["--evidence"], "CRYPTOPULSE_OPERATOR_EVIDENCE/v1\n"),
        )
        for suffix, expected in cases:
            with self.subTest(suffix=suffix):
                output = io.StringIO()
                with (
                    patch.object(cli, "ProcessRunner", return_value=object()),
                    patch.object(cli, "GitHubReader", return_value=object()),
                    patch.object(
                        cli.phase18_usefulness,
                        "run",
                        return_value=self.evidence(Status.FAIL),
                    ),
                    redirect_stdout(output),
                ):
                    code = cli.main(["phase18-usefulness", *suffix])
                self.assertEqual(code, 2)
                self.assertIn(expected, output.getvalue())

    def test_cli_parser_exposes_only_output_options_for_command(self):
        args = cli.parser().parse_args(["phase18-usefulness", "--evidence"])
        self.assertEqual(args.command, "phase18-usefulness")
        self.assertTrue(args.evidence)
        self.assertFalse(args.as_json)


if __name__ == "__main__":
    unittest.main()
