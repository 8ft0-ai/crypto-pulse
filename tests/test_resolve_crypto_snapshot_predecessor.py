from __future__ import annotations

import copy
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from resolve_crypto_snapshot_predecessor import (
    PINNED_CONFIG_BLOB_SHA,
    PINNED_CONFIG_PATH,
    PINNED_VALIDATOR_BLOB_SHA,
    PINNED_VALIDATOR_PATH,
    resolve_predecessor,
)

FIXTURES = ROOT / "tests" / "fixtures"
BASE_TIME = datetime(2026, 7, 8, 4, 34, 52, tzinfo=timezone.utc)


def _fixture(name: str = "valid_ok_snapshot.json") -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _utc_text(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _retime(payload: dict, when: datetime) -> None:
    when = when.astimezone(timezone.utc)
    timezone_name = payload["run"].get("timezone", "Australia/Sydney")
    zone = ZoneInfo(timezone_name)
    local = when.astimezone(zone)
    payload["run"]["generated_at_utc"] = _utc_text(when)
    payload["run"]["generated_at_local"] = local.isoformat()
    payload["run"]["timezone"] = timezone_name
    payload["run"]["timezone_abbreviation"] = local.tzname()

    for source in payload.get("sources", {}).values():
        if isinstance(source, dict) and "fetched_at_utc" in source:
            source["fetched_at_utc"] = _utc_text(when)
    for asset in payload.get("market", {}).get("assets", []):
        if isinstance(asset, dict) and "last_updated" in asset:
            asset["last_updated"] = _utc_text(when)


def _expected_relative(when: datetime, timezone_name: str = "Australia/Sydney") -> Path:
    local = when.astimezone(ZoneInfo(timezone_name))
    tz_name = local.tzname() or "LOCAL"
    safe_tz = "".join(ch for ch in tz_name if ch.isalnum()) or "LOCAL"
    return (
        Path(f"{local.year:04d}")
        / f"{local.month:02d}"
        / f"{local.day:02d}"
        / f"{local.hour:02d}{local.minute:02d}_{safe_tz}_source_snapshot.json"
    )


def _write_snapshot(
    snapshot_root: Path,
    when: datetime,
    *,
    fixture: str = "valid_ok_snapshot.json",
    mutate=None,
    relative_override: Path | None = None,
) -> Path:
    payload = copy.deepcopy(_fixture(fixture))
    _retime(payload, when)
    if mutate is not None:
        mutate(payload)
    relative = relative_override or _expected_relative(when, payload["run"]["timezone"])
    path = snapshot_root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    return path


def _git(repository_root: Path, *args: str) -> bytes:
    return subprocess.run(
        ["git", "-C", str(repository_root), *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout


def _commit(repository_root: Path, message: str = "fixture") -> None:
    _git(repository_root, "add", ".")
    _git(repository_root, "commit", "-q", "-m", message)


def _repository_context(repository_root: Path) -> dict:
    commit_sha = _git(repository_root, "rev-parse", "HEAD").decode().strip()
    tree_sha = _git(repository_root, "rev-parse", "HEAD^{tree}").decode().strip()
    return {
        "commit_sha": commit_sha,
        "tree_sha": tree_sha,
        "validator": {
            "path": PINNED_VALIDATOR_PATH,
            "git_blob_sha": PINNED_VALIDATOR_BLOB_SHA,
        },
        "config": {
            "path": PINNED_CONFIG_PATH,
            "git_blob_sha": PINNED_CONFIG_BLOB_SHA,
        },
    }


def _repository_path(repository_root: Path, path: Path) -> str:
    return path.relative_to(repository_root).as_posix()


def _current_identity(repository_root: Path, context: dict, path: Path) -> dict:
    repository_path = _repository_path(repository_root, path)
    raw = _git(
        repository_root,
        "cat-file",
        "blob",
        f"{context['commit_sha']}:{repository_path}",
    )
    payload = json.loads(raw)
    return {
        "path": repository_path,
        "sha256": hashlib.sha256(raw).hexdigest(),
        "schema_version": payload["schema_version"],
        "generated_at_utc": payload["run"]["generated_at_utc"],
    }


class ResolveCryptoSnapshotPredecessorTests(unittest.TestCase):
    def _repository(self, tmp: str) -> tuple[Path, Path]:
        repository_root = Path(tmp)
        _git(repository_root, "init", "-q")
        _git(repository_root, "config", "user.email", "tests@example.invalid")
        _git(repository_root, "config", "user.name", "CryptoPulse Tests")

        validator = repository_root / PINNED_VALIDATOR_PATH
        validator.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / PINNED_VALIDATOR_PATH, validator)

        config = repository_root / PINNED_CONFIG_PATH
        config.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / PINNED_CONFIG_PATH, config)

        snapshot_root = repository_root / "data" / "crypto" / "hourly"
        snapshot_root.mkdir(parents=True, exist_ok=True)
        return repository_root, snapshot_root

    def _resolve(self, repository_root: Path, current_path: Path) -> dict:
        context = _repository_context(repository_root)
        current = _current_identity(repository_root, context, current_path)
        return resolve_predecessor(current, repository_root, context)

    def test_exact_hour_valid_ok_pair_resolves_from_immutable_tree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repository_root, root = self._repository(tmp)
            predecessor = _write_snapshot(root, BASE_TIME - timedelta(hours=1))
            current = _write_snapshot(root, BASE_TIME)
            _commit(repository_root)
            context = _repository_context(repository_root)
            current_identity = _current_identity(repository_root, context, current)

            result = resolve_predecessor(current_identity, repository_root, context)

            self.assertEqual(result["resolution_status"], "predecessor-resolved")
            self.assertEqual(result["elapsed_seconds"], 3600)
            self.assertEqual(result["repository_context"], context)
            self.assertEqual(result["current"]["sha256"], current_identity["sha256"])
            self.assertEqual(
                result["predecessor"]["path"],
                _repository_path(repository_root, predecessor),
            )
            self.assertEqual(result["current"]["quality_status"], "valid-ok")
            self.assertEqual(result["predecessor"]["quality_status"], "valid-ok")

    def test_valid_degraded_current_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repository_root, root = self._repository(tmp)
            _write_snapshot(root, BASE_TIME - timedelta(hours=1))
            current = _write_snapshot(
                root,
                BASE_TIME,
                fixture="valid_degraded_optional_source_warning.json",
            )
            _commit(repository_root)

            result = self._resolve(repository_root, current)

            self.assertEqual(result["resolution_status"], "predecessor-resolved")
            self.assertEqual(result["current"]["quality_status"], "valid-degraded")
            self.assertTrue(result["current"]["non_blocking_warnings"])

    def test_valid_degraded_predecessor_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repository_root, root = self._repository(tmp)
            _write_snapshot(
                root,
                BASE_TIME - timedelta(hours=1),
                fixture="valid_degraded_optional_source_warning.json",
            )
            current = _write_snapshot(root, BASE_TIME)
            _commit(repository_root)

            result = self._resolve(repository_root, current)

            self.assertEqual(result["resolution_status"], "predecessor-resolved")
            self.assertEqual(result["predecessor"]["quality_status"], "valid-degraded")
            self.assertTrue(result["predecessor"]["non_blocking_warnings"])

    def test_repository_tree_mismatch_fails_validation_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repository_root, root = self._repository(tmp)
            current = _write_snapshot(root, BASE_TIME)
            _commit(repository_root)
            context = _repository_context(repository_root)
            current_identity = _current_identity(repository_root, context, current)
            context["tree_sha"] = "0" * 40

            result = resolve_predecessor(current_identity, repository_root, context)

            self.assertEqual(result["resolution_status"], "validation-contract-mismatch")
            self.assertIsNone(result["current"]["path"])

    def test_modified_validator_in_repository_context_fails_validation_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repository_root, root = self._repository(tmp)
            current = _write_snapshot(root, BASE_TIME)
            validator = repository_root / PINNED_VALIDATOR_PATH
            validator.write_text(
                validator.read_text(encoding="utf-8") + "\n# drift\n",
                encoding="utf-8",
            )
            _commit(repository_root)
            context = _repository_context(repository_root)
            current_identity = {
                "path": _repository_path(repository_root, current),
                "sha256": "0" * 64,
                "schema_version": "0.2",
                "generated_at_utc": _utc_text(BASE_TIME),
            }

            result = resolve_predecessor(current_identity, repository_root, context)

            self.assertEqual(result["resolution_status"], "validation-contract-mismatch")

    def test_modified_config_in_repository_context_fails_validation_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repository_root, root = self._repository(tmp)
            current = _write_snapshot(root, BASE_TIME)
            config = repository_root / PINNED_CONFIG_PATH
            config.write_text(
                config.read_text(encoding="utf-8") + "\n# drift\n",
                encoding="utf-8",
            )
            _commit(repository_root)
            context = _repository_context(repository_root)
            current_identity = {
                "path": _repository_path(repository_root, current),
                "sha256": "0" * 64,
                "schema_version": "0.2",
                "generated_at_utc": _utc_text(BASE_TIME),
            }

            result = resolve_predecessor(current_identity, repository_root, context)

            self.assertEqual(result["resolution_status"], "validation-contract-mismatch")

    def test_missing_yaml_support_fails_validation_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repository_root, root = self._repository(tmp)
            current = _write_snapshot(
                root,
                BASE_TIME,
                fixture="valid_degraded_optional_source_warning.json",
            )
            _commit(repository_root)
            context = _repository_context(repository_root)
            current_identity = _current_identity(repository_root, context, current)
            real_import = __import__

            def import_without_yaml(name, *args, **kwargs):
                if name == "yaml":
                    raise ImportError("simulated missing PyYAML")
                return real_import(name, *args, **kwargs)

            with patch("builtins.__import__", side_effect=import_without_yaml):
                result = resolve_predecessor(
                    current_identity,
                    repository_root,
                    context,
                )

            self.assertEqual(
                result["resolution_status"],
                "validation-contract-mismatch",
            )

    def test_current_exact_byte_identity_mismatch_fails_before_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repository_root, root = self._repository(tmp)

            def invalidate(payload: dict) -> None:
                payload["sources"].pop("defillama", None)

            current = _write_snapshot(root, BASE_TIME, mutate=invalidate)
            _commit(repository_root)
            context = _repository_context(repository_root)
            current_identity = _current_identity(repository_root, context, current)
            current_identity["sha256"] = "0" * 64

            result = resolve_predecessor(current_identity, repository_root, context)

            self.assertEqual(result["resolution_status"], "current-identity-invalid")

    def test_invalid_current_fails_after_identity_is_established(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repository_root, root = self._repository(tmp)

            def invalidate(payload: dict) -> None:
                payload["sources"].pop("defillama", None)

            current = _write_snapshot(root, BASE_TIME, mutate=invalidate)
            _commit(repository_root)

            result = self._resolve(repository_root, current)

            self.assertEqual(result["resolution_status"], "current-invalid")
            self.assertIsNone(result["predecessor"])
            self.assertIsNotNone(result["current"]["sha256"])

    def test_current_path_identity_mismatch_precedes_quality_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repository_root, root = self._repository(tmp)

            def invalidate(payload: dict) -> None:
                payload["sources"].pop("defillama", None)

            wrong = _expected_relative(BASE_TIME).with_name(
                "9999_AEST_source_snapshot.json"
            )
            current = _write_snapshot(
                root,
                BASE_TIME,
                mutate=invalidate,
                relative_override=wrong,
            )
            _commit(repository_root)

            result = self._resolve(repository_root, current)

            self.assertEqual(result["resolution_status"], "current-identity-invalid")

    def test_current_must_exist_in_immutable_tree_even_if_present_in_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repository_root, root = self._repository(tmp)
            _commit(repository_root)
            context = _repository_context(repository_root)
            current = _write_snapshot(root, BASE_TIME)
            raw = current.read_bytes()
            payload = json.loads(raw)
            current_identity = {
                "path": _repository_path(repository_root, current),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "schema_version": payload["schema_version"],
                "generated_at_utc": payload["run"]["generated_at_utc"],
            }

            result = resolve_predecessor(current_identity, repository_root, context)

            self.assertEqual(result["resolution_status"], "current-identity-invalid")

    def test_mutable_worktree_changes_do_not_change_resolution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repository_root, root = self._repository(tmp)
            predecessor = _write_snapshot(root, BASE_TIME - timedelta(hours=1))
            current = _write_snapshot(root, BASE_TIME)
            _commit(repository_root)
            context = _repository_context(repository_root)
            current_identity = _current_identity(repository_root, context, current)
            expected = resolve_predecessor(current_identity, repository_root, context)

            current.write_text("{}\n", encoding="utf-8")
            predecessor.unlink()
            _write_snapshot(root, BASE_TIME - timedelta(minutes=30))

            actual = resolve_predecessor(current_identity, repository_root, context)

            self.assertEqual(actual, expected)
            self.assertEqual(actual["resolution_status"], "predecessor-resolved")

    def test_unorderable_candidate_in_immutable_tree_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repository_root, root = self._repository(tmp)
            current = _write_snapshot(root, BASE_TIME)
            malformed = root / "2026/07/08/0000_AEST_source_snapshot.json"
            malformed.parent.mkdir(parents=True, exist_ok=True)
            malformed.write_text(
                '{"run":{"generated_at_utc":"not-a-timestamp"}}\n',
                encoding="utf-8",
            )
            _commit(repository_root)

            result = self._resolve(repository_root, current)

            self.assertEqual(result["resolution_status"], "candidate-set-unorderable")

    def test_missing_predecessor_is_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repository_root, root = self._repository(tmp)
            current = _write_snapshot(root, BASE_TIME)
            _commit(repository_root)

            result = self._resolve(repository_root, current)

            self.assertEqual(result["resolution_status"], "predecessor-missing")

    def test_equal_greatest_prior_timestamps_are_ambiguous(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repository_root, root = self._repository(tmp)
            prior_time = BASE_TIME - timedelta(hours=1)
            _write_snapshot(root, prior_time)
            alternate = _expected_relative(prior_time).with_name(
                "1335_AEST_source_snapshot.json"
            )
            _write_snapshot(root, prior_time, relative_override=alternate)
            current = _write_snapshot(root, BASE_TIME)
            _commit(repository_root)

            result = self._resolve(repository_root, current)

            self.assertEqual(result["resolution_status"], "predecessor-ambiguous")

    def test_invalid_immediate_predecessor_does_not_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repository_root, root = self._repository(tmp)

            def invalidate(payload: dict) -> None:
                payload["sources"].pop("defillama", None)

            _write_snapshot(root, BASE_TIME - timedelta(hours=2))
            immediate = _write_snapshot(
                root, BASE_TIME - timedelta(minutes=30), mutate=invalidate
            )
            current = _write_snapshot(root, BASE_TIME)
            _commit(repository_root)

            result = self._resolve(repository_root, current)

            self.assertEqual(result["resolution_status"], "predecessor-invalid")
            self.assertEqual(
                result["predecessor"]["path"],
                _repository_path(repository_root, immediate),
            )

    def test_predecessor_identity_mismatch_precedes_quality_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repository_root, root = self._repository(tmp)

            def invalidate(payload: dict) -> None:
                payload["sources"].pop("defillama", None)

            prior_time = BASE_TIME - timedelta(hours=1)
            wrong = _expected_relative(prior_time).with_name(
                "0000_AEST_source_snapshot.json"
            )
            _write_snapshot(
                root,
                prior_time,
                mutate=invalidate,
                relative_override=wrong,
            )
            current = _write_snapshot(root, BASE_TIME)
            _commit(repository_root)

            result = self._resolve(repository_root, current)

            self.assertEqual(
                result["resolution_status"], "predecessor-identity-invalid"
            )

    def test_gap_under_exact_hour_is_out_of_window(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repository_root, root = self._repository(tmp)
            _write_snapshot(root, BASE_TIME - timedelta(minutes=30))
            current = _write_snapshot(root, BASE_TIME)
            _commit(repository_root)

            result = self._resolve(repository_root, current)

            self.assertEqual(result["resolution_status"], "predecessor-out-of-window")
            self.assertEqual(result["elapsed_seconds"], 1800)

    def test_gap_over_exact_hour_is_out_of_window(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repository_root, root = self._repository(tmp)
            _write_snapshot(root, BASE_TIME - timedelta(minutes=90))
            current = _write_snapshot(root, BASE_TIME)
            _commit(repository_root)

            result = self._resolve(repository_root, current)

            self.assertEqual(result["resolution_status"], "predecessor-out-of-window")
            self.assertEqual(result["elapsed_seconds"], 5400)

    def test_schema_mismatch_at_exact_hour_is_incompatible(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repository_root, root = self._repository(tmp)

            def change_schema(payload: dict) -> None:
                payload["schema_version"] = "0.3"

            _write_snapshot(
                root, BASE_TIME - timedelta(hours=1), mutate=change_schema
            )
            current = _write_snapshot(root, BASE_TIME)
            _commit(repository_root)

            result = self._resolve(repository_root, current)

            self.assertEqual(result["resolution_status"], "pair-schema-incompatible")
            self.assertEqual(result["elapsed_seconds"], 3600)

    def test_out_of_window_immediate_predecessor_does_not_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repository_root, root = self._repository(tmp)
            exact_but_older = _write_snapshot(root, BASE_TIME - timedelta(hours=1))
            immediate = _write_snapshot(root, BASE_TIME - timedelta(minutes=30))
            current = _write_snapshot(root, BASE_TIME)
            _commit(repository_root)

            result = self._resolve(repository_root, current)

            self.assertEqual(result["resolution_status"], "predecessor-out-of-window")
            self.assertEqual(
                result["predecessor"]["path"],
                _repository_path(repository_root, immediate),
            )
            self.assertNotEqual(
                result["predecessor"]["path"],
                _repository_path(repository_root, exact_but_older),
            )

    def test_schema_incompatible_immediate_predecessor_does_not_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repository_root, root = self._repository(tmp)

            def change_schema(payload: dict) -> None:
                payload["schema_version"] = "0.3"

            _write_snapshot(root, BASE_TIME - timedelta(hours=2))
            immediate = _write_snapshot(
                root, BASE_TIME - timedelta(hours=1), mutate=change_schema
            )
            current = _write_snapshot(root, BASE_TIME)
            _commit(repository_root)

            result = self._resolve(repository_root, current)

            self.assertEqual(result["resolution_status"], "pair-schema-incompatible")
            self.assertEqual(
                result["predecessor"]["path"],
                _repository_path(repository_root, immediate),
            )

    def test_utc_ordering_selects_badly_named_immediate_then_identity_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repository_root, root = self._repository(tmp)
            older_time = BASE_TIME - timedelta(hours=2)
            immediate_time = BASE_TIME - timedelta(hours=1)
            _write_snapshot(root, older_time)
            wrong = _expected_relative(immediate_time).with_name(
                "1234_AEST_source_snapshot.json"
            )
            immediate = _write_snapshot(
                root, immediate_time, relative_override=wrong
            )
            current = _write_snapshot(root, BASE_TIME)
            _commit(repository_root)

            result = self._resolve(repository_root, current)

            self.assertEqual(
                result["resolution_status"], "predecessor-identity-invalid"
            )
            self.assertEqual(
                result["predecessor"]["path"],
                _repository_path(repository_root, immediate),
            )

    def test_local_timestamp_without_explicit_offset_is_identity_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repository_root, root = self._repository(tmp)
            _write_snapshot(root, BASE_TIME - timedelta(hours=1))

            def remove_offset(payload: dict) -> None:
                payload["run"]["generated_at_local"] = "2026-07-08T14:34:52"

            current = _write_snapshot(root, BASE_TIME, mutate=remove_offset)
            _commit(repository_root)

            result = self._resolve(repository_root, current)

            self.assertEqual(result["resolution_status"], "current-identity-invalid")


if __name__ == "__main__":
    unittest.main()
