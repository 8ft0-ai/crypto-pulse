from __future__ import annotations

import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_crypto_snapshot_comparison_record import (  # noqa: E402
    CONFIG_BLOB_SHA,
    CONFIG_PATH,
    VALIDATOR_BLOB_SHA,
    VALIDATOR_PATH,
    build_comparison_record,
)
from compare_crypto_snapshot_fields import (  # noqa: E402
    METRIC_SPECS,
    SOURCE_ORDER,
    build_metric_and_source_evidence,
)
from validate_crypto_snapshot_comparison import (  # noqa: E402
    canonical_json_bytes,
    comparison_id_for_record,
    validate_comparison_record,
)

CORPUS_PATH = ROOT / "tests" / "fixtures" / "phase10_comparison_proof_v1.json"
CASE_ORDER = (
    "01-comparison-available-mixed-evidence",
    "02-comparison-available-valid-degraded",
    "03-validation-contract-mismatch",
    "04-current-invalid",
    "05-current-identity-invalid",
    "06-candidate-set-unorderable",
    "07-predecessor-missing",
    "08-predecessor-ambiguous",
    "09-predecessor-invalid",
    "10-predecessor-identity-invalid",
    "11-predecessor-out-of-window",
    "12-pair-schema-incompatible",
    "13-pair-semantics-incompatible",
    "14-pure-adapter-missing-invalid-evidence",
)
EXPECTED_STATUS = {
    "01-comparison-available-mixed-evidence": "comparison-available",
    "02-comparison-available-valid-degraded": "comparison-available",
    "03-validation-contract-mismatch": "validation-contract-mismatch",
    "04-current-invalid": "current-invalid",
    "05-current-identity-invalid": "current-identity-invalid",
    "06-candidate-set-unorderable": "candidate-set-unorderable",
    "07-predecessor-missing": "predecessor-missing",
    "08-predecessor-ambiguous": "predecessor-ambiguous",
    "09-predecessor-invalid": "predecessor-invalid",
    "10-predecessor-identity-invalid": "predecessor-identity-invalid",
    "11-predecessor-out-of-window": "predecessor-out-of-window",
    "12-pair-schema-incompatible": "pair-schema-incompatible",
    "13-pair-semantics-incompatible": "pair-semantics-incompatible",
}
CORPUS_KEYS = {
    "schema_version",
    "frozen_contract",
    "seed_commit",
    "case_order",
    "cases",
}
CONTRACT_KEYS = {
    "comparison_schema_version",
    "predecessor_policy_version",
    "semantic_contract_version",
    "validator",
    "config",
}
CONTRACT_REF_KEYS = {"path", "git_blob_sha"}
SEED_KEYS = {
    "author_name",
    "author_email",
    "author_date",
    "committer_name",
    "committer_email",
    "committer_date",
    "message",
}
COMPARISON_CASE_KEYS = {
    "kind",
    "repository_files",
    "current_repository_path",
    "contract_override",
    "expected",
}
ADAPTER_CASE_KEYS = {
    "kind",
    "current_snapshot",
    "predecessor_snapshot",
    "expected",
}


def _git(
    repository: Path,
    *args: str,
    input_bytes: bytes | None = None,
    extra_env: dict[str, str] | None = None,
) -> bytes:
    env = os.environ.copy()
    env.update(
        {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_OPTIONAL_LOCKS": "0",
            "LC_ALL": "C",
        }
    )
    if extra_env:
        env.update(extra_env)
    completed = subprocess.run(
        ["git", "-C", str(repository), *args],
        check=False,
        input=input_bytes,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise AssertionError(detail or f"git {' '.join(args)} failed")
    return completed.stdout


def _text(raw: bytes) -> str:
    return raw.decode("utf-8", errors="strict").strip()


def _assert_repository_path(path: str) -> None:
    candidate = PurePosixPath(path)
    if not path or "\\" in path or candidate.is_absolute() or ".." in candidate.parts:
        raise AssertionError(f"unsafe corpus repository path: {path!r}")


class ComparisonProofCorpusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.corpus = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))

    def assert_exact_keys(self, value: Any, expected: set[str], path: str) -> dict[str, Any]:
        self.assertIsInstance(value, dict, path)
        self.assertEqual(set(value), expected, path)
        return value

    def test_corpus_contract_is_closed_and_frozen(self) -> None:
        corpus = self.assert_exact_keys(self.corpus, CORPUS_KEYS, "corpus")
        self.assertEqual(corpus["schema_version"], "phase10-comparison-proof-corpus/v1")
        self.assertEqual(corpus["case_order"], list(CASE_ORDER))
        self.assertEqual(list(corpus["cases"]), list(CASE_ORDER))

        contract = self.assert_exact_keys(
            corpus["frozen_contract"], CONTRACT_KEYS, "frozen_contract"
        )
        self.assertEqual(contract["comparison_schema_version"], "crypto-snapshot-comparison/v1")
        self.assertEqual(
            contract["predecessor_policy_version"], "phase10-predecessor-exact-hour/v1"
        )
        self.assertEqual(
            contract["semantic_contract_version"], "phase10-snapshot-semantics-0.2/v1"
        )
        validator = self.assert_exact_keys(
            contract["validator"], CONTRACT_REF_KEYS, "frozen_contract.validator"
        )
        config = self.assert_exact_keys(
            contract["config"], CONTRACT_REF_KEYS, "frozen_contract.config"
        )
        self.assertEqual(validator, {"path": VALIDATOR_PATH, "git_blob_sha": VALIDATOR_BLOB_SHA})
        self.assertEqual(config, {"path": CONFIG_PATH, "git_blob_sha": CONFIG_BLOB_SHA})
        self.assert_exact_keys(corpus["seed_commit"], SEED_KEYS, "seed_commit")

        for case_id in CASE_ORDER:
            case = corpus["cases"][case_id]
            if case_id == CASE_ORDER[-1]:
                self.assert_exact_keys(case, ADAPTER_CASE_KEYS, case_id)
                self.assertEqual(case["kind"], "pure-adapter")
            else:
                self.assert_exact_keys(case, COMPARISON_CASE_KEYS, case_id)
                self.assertEqual(case["kind"], "comparison-record")
                self.assertIsInstance(case["repository_files"], dict)
                self.assertTrue(case["repository_files"])
                for path, content in case["repository_files"].items():
                    _assert_repository_path(path)
                    self.assertIsInstance(content, str)
                self.assertIsInstance(case["current_repository_path"], str)
                self.assertIsInstance(case["contract_override"], dict)
                for path, content in case["contract_override"].items():
                    self.assertIn(path, {VALIDATOR_PATH, CONFIG_PATH})
                    self.assertIsInstance(content, str)

    def _seed_repository(
        self, case: dict[str, Any]
    ) -> tuple[tempfile.TemporaryDirectory[str], Path, str, str, dict[str, str]]:
        temporary = tempfile.TemporaryDirectory(prefix="phase10-proof-")
        repository = Path(temporary.name)
        _git(repository, "init", "-q")

        contract_files = {
            VALIDATOR_PATH: (ROOT / VALIDATOR_PATH).read_text(encoding="utf-8"),
            CONFIG_PATH: (ROOT / CONFIG_PATH).read_text(encoding="utf-8"),
        }
        local_blobs = {
            path: _text(_git(repository, "hash-object", "--stdin", input_bytes=content.encode()))
            for path, content in contract_files.items()
        }
        self.assertEqual(local_blobs[VALIDATOR_PATH], VALIDATOR_BLOB_SHA)
        self.assertEqual(local_blobs[CONFIG_PATH], CONFIG_BLOB_SHA)

        files = dict(contract_files)
        files.update(case["contract_override"])
        files.update(case["repository_files"])
        blob_ids: dict[str, str] = {}
        for path in sorted(files):
            _assert_repository_path(path)
            blob = _text(
                _git(repository, "hash-object", "-w", "--stdin", input_bytes=files[path].encode())
            )
            blob_ids[path] = blob
            _git(repository, "update-index", "--add", "--cacheinfo", f"100644,{blob},{path}")

        tree = _text(_git(repository, "write-tree"))
        seed = self.corpus["seed_commit"]
        commit_env = {
            "GIT_AUTHOR_NAME": seed["author_name"],
            "GIT_AUTHOR_EMAIL": seed["author_email"],
            "GIT_AUTHOR_DATE": seed["author_date"],
            "GIT_COMMITTER_NAME": seed["committer_name"],
            "GIT_COMMITTER_EMAIL": seed["committer_email"],
            "GIT_COMMITTER_DATE": seed["committer_date"],
        }
        commit = _text(
            _git(
                repository,
                "-c",
                "commit.gpgsign=false",
                "commit-tree",
                tree,
                input_bytes=(seed["message"] + "\n").encode(),
                extra_env=commit_env,
            )
        )
        return temporary, repository, commit, tree, blob_ids

    def _run_comparison_case(
        self, case: dict[str, Any]
    ) -> tuple[str, str, dict[str, str], dict[str, Any], bytes]:
        temporary, repository, commit, tree, blob_ids = self._seed_repository(case)
        try:
            first = build_comparison_record(
                repository,
                commit,
                case["current_repository_path"],
            )
            second = build_comparison_record(
                repository,
                commit,
                case["current_repository_path"],
            )
            validate_comparison_record(first)
            validate_comparison_record(second)
            first_bytes = canonical_json_bytes(first)
            self.assertEqual(first_bytes, canonical_json_bytes(second))
            return commit, tree, blob_ids, first, first_bytes
        finally:
            temporary.cleanup()

    def _assert_bound_input(self, item: Any, files: dict[str, str]) -> None:
        if not isinstance(item, dict) or item["path"] is None or item["sha256"] is None:
            return
        self.assertIn(item["path"], files)
        expected = hashlib.sha256(files[item["path"]].encode()).hexdigest()
        self.assertEqual(item["sha256"], expected)

    def test_full_record_corpus_matches_golden_outputs_and_repeats(self) -> None:
        for case_id in CASE_ORDER[:-1]:
            with self.subTest(case=case_id):
                case = self.corpus["cases"][case_id]
                first = self._run_comparison_case(case)
                second = self._run_comparison_case(case)
                first_commit, first_tree, first_blobs, record, record_bytes = first
                second_commit, second_tree, second_blobs, repeated, repeated_bytes = second

                self.assertEqual(first_commit, second_commit)
                self.assertEqual(first_tree, second_tree)
                self.assertEqual(first_blobs, second_blobs)
                self.assertEqual(record_bytes, repeated_bytes)
                self.assertEqual(record, case["expected"])
                self.assertEqual(record_bytes, canonical_json_bytes(case["expected"]))
                self.assertEqual(record["comparison_status"], EXPECTED_STATUS[case_id])
                self.assertEqual(record["repository_context"]["commit_sha"], first_commit)
                self.assertEqual(record["repository_context"]["tree_sha"], first_tree)
                self.assertEqual(
                    record["repository_context"]["validator"]["git_blob_sha"],
                    first_blobs[VALIDATOR_PATH],
                )
                self.assertEqual(
                    record["repository_context"]["config"]["git_blob_sha"],
                    first_blobs[CONFIG_PATH],
                )
                self.assertEqual(record["comparison_id"], comparison_id_for_record(record))
                self._assert_bound_input(record["current"], case["repository_files"])
                self._assert_bound_input(record["predecessor"], case["repository_files"])

                if record["comparison_status"] == "comparison-available":
                    self.assertEqual(len(record["metric_comparisons"]), len(METRIC_SPECS))
                    self.assertEqual(len(record["source_availability_changes"]), len(SOURCE_ORDER))
                    self.assertEqual(
                        [
                            (item["family"], item["symbol"], item["field"])
                            for item in record["metric_comparisons"]
                        ],
                        [(family, symbol, field) for family, symbol, field, _ in METRIC_SPECS],
                    )
                    self.assertEqual(
                        [item["source"] for item in record["source_availability_changes"]],
                        list(SOURCE_ORDER),
                    )
                else:
                    self.assertEqual(record["metric_comparisons"], [])
                    self.assertEqual(record["source_availability_changes"], [])

    def test_mixed_available_case_retains_metric_and_source_semantics(self) -> None:
        record = self.corpus["cases"][CASE_ORDER[0]]["expected"]
        metrics = {
            (item["symbol"], item["field"]): item for item in record["metric_comparisons"]
        }
        self.assertEqual(metrics[("BTC", "price_usd")]["relation"], "current-greater")
        self.assertEqual(metrics[("BTC", "market_cap_usd")]["relation"], "current-less")
        self.assertEqual(metrics[("BTC", "volume_24h_usd")]["relation"], "equal")
        self.assertEqual(metrics[("BTC", "market_cap_rank")]["relation"], "current-less")
        self.assertNotIn("direction", metrics[("BTC", "market_cap_rank")])

        sources = {
            item["source"]: item for item in record["source_availability_changes"]
        }
        self.assertEqual(sources["kraken"]["availability_change"], "gained")
        self.assertEqual(sources["coinbase_exchange"]["availability_change"], "lost")
        self.assertEqual(sources["bybit"]["predecessor_status"], "missing")
        self.assertEqual(sources["cryptocompare"]["current_status"], "missing")
        self.assertTrue(sources["binance"]["status_changed"])
        self.assertEqual(sources["binance"]["availability_change"], "unchanged")
        self.assertFalse(sources["defillama"]["status_changed"])

    def test_valid_degraded_case_retains_warnings(self) -> None:
        record = self.corpus["cases"][CASE_ORDER[1]]["expected"]
        degraded = [
            item
            for item in (record["current"], record["predecessor"])
            if item["quality_status"] == "valid-degraded"
        ]
        self.assertTrue(degraded)
        self.assertTrue(all(item["non_blocking_warnings"] for item in degraded))

    def test_pure_adapter_case_matches_golden_and_preserves_defects(self) -> None:
        case = self.corpus["cases"][CASE_ORDER[-1]]
        first_metrics, first_sources = build_metric_and_source_evidence(
            copy.deepcopy(case["current_snapshot"]),
            copy.deepcopy(case["predecessor_snapshot"]),
        )
        second_metrics, second_sources = build_metric_and_source_evidence(
            copy.deepcopy(case["current_snapshot"]),
            copy.deepcopy(case["predecessor_snapshot"]),
        )
        actual = {
            "metric_comparisons": first_metrics,
            "source_availability_changes": first_sources,
        }
        repeated = {
            "metric_comparisons": second_metrics,
            "source_availability_changes": second_sources,
        }
        self.assertEqual(canonical_json_bytes(actual), canonical_json_bytes(repeated))
        self.assertEqual(actual, case["expected"])
        self.assertEqual(len(first_metrics), len(METRIC_SPECS))
        self.assertEqual(len(first_sources), len(SOURCE_ORDER))

        metrics = {
            (item["symbol"], item["field"]): item for item in first_metrics
        }
        self.assertEqual(
            metrics[("BTC", "price_usd")]["comparison_state"], "unavailable-current"
        )
        self.assertFalse(metrics[("BTC", "price_usd")]["current"]["present"])
        self.assertFalse(metrics[("BTC", "price_usd")]["predecessor"]["present"])
        self.assertEqual(
            metrics[("BTC", "market_cap_usd")]["comparison_state"],
            "unavailable-predecessor",
        )
        self.assertEqual(
            metrics[("BTC", "volume_24h_usd")]["comparison_state"], "invalid-current"
        )
        self.assertEqual(
            metrics[("BTC", "change_1h_pct")]["comparison_state"], "invalid-predecessor"
        )
        self.assertEqual(
            metrics[("BTC", "change_24h_pct")]["comparison_state"], "invalid-current"
        )
        self.assertEqual(metrics[("BTC", "change_24h_pct")]["current"]["value"], "bad")
        self.assertEqual(
            metrics[("BTC", "change_24h_pct")]["predecessor"]["value"], "Infinity"
        )


if __name__ == "__main__":
    unittest.main()
