from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "tests"))
sys.path.insert(0, str(ROOT / "tools" / "operator"))

import build_crypto_observation_hour_comparison_record as comparison_module  # noqa: E402
import phase15_public_temporal_evidence as phase15_module  # noqa: E402
import phase18_multi_asset_temporal_evidence as phase18_module  # noqa: E402
import resolve_crypto_observation_hour_adjacency as adjacency_module  # noqa: E402
from build_crypto_observation_hour_comparison_record import (  # noqa: E402
    build_observation_hour_comparison,
)
from phase15_public_temporal_evidence import (  # noqa: E402
    Phase15PublicTemporalEvidenceError,
)
from phase18_multi_asset_temporal_evidence import (  # noqa: E402
    build_multi_asset_temporal_evidence,
    canonical_bundle_bytes,
    validate_multi_asset_temporal_evidence,
)
from resolve_crypto_observation_hour_adjacency import (  # noqa: E402
    prepare_observation_hour_replay_context,
)
from cryptopulse_operator.commands import phase18_usefulness_bounded  # noqa: E402
from test_phase15_public_temporal_evidence_proof_corpus import (  # noqa: E402
    CORPUS_PATH,
    Phase15PublicTemporalEvidenceProofTests,
)


class Phase18ReplayContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.seed_helper = Phase15PublicTemporalEvidenceProofTests(
            "test_corpus_contract_is_closed"
        )
        cls.seed_helper.corpus = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))

    def _seed(self):
        return self.seed_helper._seed("deterministic-max-hour")

    @staticmethod
    def _fail_first_git_then_recover(message: str):
        real_git = adjacency_module._git
        calls = {"count": 0}

        def side_effect(repository_root: Path, *args: str) -> bytes:
            calls["count"] += 1
            if calls["count"] == 1:
                raise RuntimeError(message)
            return real_git(repository_root, *args)

        return calls, side_effect

    def test_real_phase18_materialisation_scans_population_once_and_builds_each_slot_once(self):
        temporary, repository, commit = self._seed()
        try:
            with (
                patch.object(
                    adjacency_module,
                    "_load_observation_hour_population_exact",
                    wraps=adjacency_module._load_observation_hour_population_exact,
                ) as population_load,
                patch.object(
                    comparison_module,
                    "_build_observation_hour_comparison_uncached",
                    wraps=comparison_module._build_observation_hour_comparison_uncached,
                ) as comparison_build,
                patch.object(
                    adjacency_module,
                    "_git",
                    wraps=adjacency_module._git,
                ) as git_calls,
            ):
                bundle = build_multi_asset_temporal_evidence(repository, commit)
            self.assertIsNotNone(bundle)
            self.assertEqual(population_load.call_count, 1)
            self.assertEqual(comparison_build.call_count, 24)
            self.assertLess(git_calls.call_count, 64)
        finally:
            temporary.cleanup()

    def test_real_phase18_validation_is_one_fresh_independent_replay_context(self):
        temporary, repository, commit = self._seed()
        try:
            bundle = build_multi_asset_temporal_evidence(repository, commit)
            self.assertIsNotNone(bundle)
            assert bundle is not None
            before = canonical_bundle_bytes(copy.deepcopy(bundle))
            with (
                patch.object(
                    adjacency_module,
                    "_load_observation_hour_population_exact",
                    wraps=adjacency_module._load_observation_hour_population_exact,
                ) as population_load,
                patch.object(
                    comparison_module,
                    "_build_observation_hour_comparison_uncached",
                    wraps=comparison_module._build_observation_hour_comparison_uncached,
                ) as comparison_build,
                patch.object(
                    adjacency_module,
                    "_git",
                    wraps=adjacency_module._git,
                ) as git_calls,
            ):
                validated = validate_multi_asset_temporal_evidence(repository, bundle)
            self.assertIs(validated, bundle)
            self.assertEqual(population_load.call_count, 1)
            self.assertEqual(comparison_build.call_count, 24)
            self.assertLess(git_calls.call_count, 64)
            self.assertEqual(canonical_bundle_bytes(bundle), before)
        finally:
            temporary.cleanup()

    def test_independent_materialisations_do_not_share_a_hidden_process_cache(self):
        temporary, repository, commit = self._seed()
        try:
            with patch.object(
                adjacency_module,
                "_load_observation_hour_population_exact",
                wraps=adjacency_module._load_observation_hour_population_exact,
            ) as population_load:
                first = build_multi_asset_temporal_evidence(repository, commit)
                second = build_multi_asset_temporal_evidence(repository, commit)
            self.assertIsNotNone(first)
            self.assertIsNotNone(second)
            assert first is not None and second is not None
            self.assertEqual(population_load.call_count, 2)
            self.assertEqual(canonical_bundle_bytes(first), canonical_bundle_bytes(second))
        finally:
            temporary.cleanup()

    def test_comparison_cache_is_context_scoped_and_returns_defensive_copies(self):
        temporary, repository, commit = self._seed()
        try:
            context = prepare_observation_hour_replay_context(repository, commit)
            slot = max(context.observation_hours())
            with patch.object(
                comparison_module,
                "_build_observation_hour_comparison_uncached",
                wraps=comparison_module._build_observation_hour_comparison_uncached,
            ) as uncached:
                first = build_observation_hour_comparison(
                    repository, commit, slot, replay_context=context
                )
                original_status = first["comparison_status"]
                first["comparison_status"] = "poisoned-by-caller"
                second = build_observation_hour_comparison(
                    repository, commit, slot, replay_context=context
                )
            self.assertEqual(uncached.call_count, 1)
            self.assertEqual(second["comparison_status"], original_status)
            self.assertNotEqual(second["comparison_status"], first["comparison_status"])
        finally:
            temporary.cleanup()

    def test_malformed_member_shape_fails_before_validation_replay_preparation(self):
        temporary, repository, commit = self._seed()
        try:
            bundle = build_multi_asset_temporal_evidence(repository, commit)
            self.assertIsNotNone(bundle)
            assert bundle is not None
            malformed = copy.deepcopy(bundle)
            malformed["series"][0] = []
            with patch.object(
                phase18_module,
                "prepare_observation_hour_replay_context",
                side_effect=AssertionError("replay preparation happened before shape validation"),
            ) as prepare:
                with self.assertRaisesRegex(
                    phase18_module.Phase18MultiAssetTemporalEvidenceError,
                    "bundle member is not an object",
                ):
                    validate_multi_asset_temporal_evidence(repository, malformed)
            prepare.assert_not_called()
        finally:
            temporary.cleanup()

    def test_candidate_set_unorderable_remains_phase15_error_path(self):
        temporary, repository, commit = self.seed_helper._seed("candidate-set-unorderable")
        try:
            with self.assertRaisesRegex(
                Phase15PublicTemporalEvidenceError,
                "candidate-set-unorderable",
            ):
                build_multi_asset_temporal_evidence(repository, commit)
        finally:
            temporary.cleanup()

    def test_validation_contract_mismatch_remains_the_only_phase18_legacy_fallback(self):
        temporary, repository, commit = self._seed()
        try:
            with patch.object(
                phase18_module,
                "prepare_observation_hour_replay_context",
                side_effect=adjacency_module.ObservationHourReplayContextError(
                    "validation-contract-mismatch"
                ),
            ):
                self.assertIsNone(
                    phase18_module._prepare_replay_context_or_legacy(
                        repository, commit, None
                    )
                )
        finally:
            temporary.cleanup()

    def test_runtime_module_read_failure_is_execution_failure(self):
        missing = SimpleNamespace(__file__="/definitely/missing/trusted-module.py")
        with self.assertRaisesRegex(
            RuntimeError,
            "trusted runtime validation module could not be read",
        ):
            adjacency_module._runtime_module_matches(missing, "0" * 40)

    def test_phase15_execution_failure_cannot_retry_through_legacy_population(self):
        temporary, repository, commit = self._seed()
        try:
            calls, fail_once = self._fail_first_git_then_recover(
                "git subprocess timed out"
            )
            with (
                patch.object(adjacency_module, "_git", side_effect=fail_once),
                patch.object(
                    phase15_module,
                    "load_observation_hour_population",
                    side_effect=AssertionError("legacy population fallback was used"),
                ) as legacy_population,
            ):
                with self.assertRaisesRegex(
                    Phase15PublicTemporalEvidenceError,
                    "immutable replay execution failed",
                ):
                    phase15_module.build_public_temporal_evidence(repository, commit)
            self.assertEqual(calls["count"], 1)
            legacy_population.assert_not_called()
        finally:
            temporary.cleanup()

    def test_phase18_execution_failures_cannot_retry_through_legacy_population(self):
        temporary, repository, commit = self._seed()
        try:
            for message in (
                "git subprocess timed out",
                "fatal: immutable object lookup failed",
            ):
                with self.subTest(message=message):
                    calls, fail_once = self._fail_first_git_then_recover(message)
                    with (
                        patch.object(adjacency_module, "_git", side_effect=fail_once),
                        patch.object(
                            phase15_module,
                            "load_observation_hour_population",
                            side_effect=AssertionError(
                                "legacy population fallback was used"
                            ),
                        ) as legacy_population,
                    ):
                        with self.assertRaisesRegex(
                            phase18_module.Phase18MultiAssetTemporalEvidenceError,
                            "immutable replay execution failed",
                        ):
                            build_multi_asset_temporal_evidence(repository, commit)
                    self.assertEqual(calls["count"], 1)
                    legacy_population.assert_not_called()
        finally:
            temporary.cleanup()

    def test_phase18_validation_execution_failure_cannot_retry_to_success(self):
        temporary, repository, commit = self._seed()
        try:
            bundle = build_multi_asset_temporal_evidence(repository, commit)
            self.assertIsNotNone(bundle)
            assert bundle is not None
            calls, fail_once = self._fail_first_git_then_recover(
                "git subprocess timed out"
            )
            with (
                patch.object(adjacency_module, "_git", side_effect=fail_once),
                patch.object(
                    phase15_module,
                    "load_observation_hour_population",
                    side_effect=AssertionError("legacy population fallback was used"),
                ) as legacy_population,
            ):
                with self.assertRaisesRegex(
                    phase18_module.Phase18MultiAssetTemporalEvidenceError,
                    "immutable replay execution failed",
                ):
                    validate_multi_asset_temporal_evidence(repository, bundle)
            self.assertEqual(calls["count"], 1)
            legacy_population.assert_not_called()
        finally:
            temporary.cleanup()

    def test_phase18_population_git_failure_cannot_retry_through_legacy_population(self):
        temporary, repository, commit = self._seed()
        try:
            real_git = adjacency_module._git
            state = {"failed": False}

            def fail_population_once(repository_root: Path, *args: str) -> bytes:
                if args and args[0] == "ls-tree" and not state["failed"]:
                    state["failed"] = True
                    raise RuntimeError("git subprocess timed out")
                return real_git(repository_root, *args)

            with (
                patch.object(
                    adjacency_module,
                    "_git",
                    side_effect=fail_population_once,
                ),
                patch.object(
                    phase15_module,
                    "load_observation_hour_population",
                    side_effect=AssertionError("legacy population fallback was used"),
                ) as legacy_population,
            ):
                with self.assertRaisesRegex(
                    phase18_module.Phase18MultiAssetTemporalEvidenceError,
                    "immutable replay execution failed",
                ):
                    build_multi_asset_temporal_evidence(repository, commit)
            self.assertTrue(state["failed"])
            legacy_population.assert_not_called()
        finally:
            temporary.cleanup()

    def test_operator_renderer_adapter_uses_only_trusted_pure_renderer_after_validation(self):
        pure = Mock(return_value="<section>validated</section>")
        public = Mock(side_effect=AssertionError("public renderer replayed repository evidence"))
        renderer = SimpleNamespace(
            _render_validated_multi_asset_temporal_evidence=pure,
            render_multi_asset_temporal_evidence=public,
        )
        proxy = phase18_usefulness_bounded._ValidatedRendererProxy(renderer)
        bundle = {"bundle_id": "a" * 64}
        self.assertEqual(
            proxy.render_multi_asset_temporal_evidence(Path("/trusted/repo"), bundle),
            "<section>validated</section>",
        )
        pure.assert_called_once_with(bundle)
        public.assert_not_called()

    def test_lower_level_git_timeout_is_bounded_sanitised_and_fail_closed(self):
        poisoned = {
            "GIT_DIR": "/tmp/poison-git-dir",
            "GIT_CONFIG_GLOBAL": "/tmp/poison-git-config",
            "PYTHONPATH": "/tmp/poison-python",
            "DYLD_INSERT_LIBRARIES": "/tmp/poison-dylib",
            "LD_PRELOAD": "/tmp/poison-so",
        }
        with (
            patch.dict(os.environ, poisoned, clear=False),
            patch.object(adjacency_module, "_git_executable", return_value="/usr/bin/git"),
            patch.object(
                adjacency_module.subprocess,
                "run",
                side_effect=subprocess.TimeoutExpired(cmd="git", timeout=30),
            ) as run,
        ):
            with self.assertRaisesRegex(RuntimeError, "git subprocess timed out"):
                adjacency_module._git(Path("/trusted/repository"), "status")

        args, kwargs = run.call_args
        self.assertEqual(args[0][0], "/usr/bin/git")
        self.assertEqual(args[0][1:3], ["-C", "/trusted/repository"])
        self.assertIs(kwargs["stdin"], subprocess.DEVNULL)
        self.assertIs(kwargs["stdout"], subprocess.PIPE)
        self.assertIs(kwargs["stderr"], subprocess.PIPE)
        self.assertFalse(kwargs["shell"])
        self.assertEqual(kwargs["timeout"], adjacency_module._GIT_TIMEOUT_SECONDS)
        self.assertEqual(kwargs["env"]["PATH"], adjacency_module._SAFE_PATH)
        for key in poisoned:
            self.assertNotIn(key, kwargs["env"])


if __name__ == "__main__":
    unittest.main()
