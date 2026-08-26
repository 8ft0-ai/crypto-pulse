from __future__ import annotations

import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
DEV_ROOT = ROOT / "tools" / "dev"
LAUNCHER = DEV_ROOT / "cp-dev"
sys.path.insert(0, str(DEV_ROOT))

from cryptopulse_dev import cli
from cryptopulse_dev.checks import EXPECTED_SITE_ARTIFACTS
from cryptopulse_dev.commands import bootstrap, check, doctor
from cryptopulse_dev.environment import (
    PrerequisiteError,
    normalise_remote,
    python_supported,
    validate_recreate_target,
    validate_venv,
)
from cryptopulse_dev.process import ProcessResult


class FixtureRunner:
    def __init__(
        self,
        root: Path | None,
        *,
        origin: str = "https://github.com/8ft0-ai/crypto-pulse.git",
        venv_version: tuple[int, int, int] = (3, 12, 1),
        dependency_ok: bool = True,
        tracked_site: tuple[str, ...] = (),
        fail_unit: bool = False,
        fail_docs: bool = False,
        fail_build: bool = False,
        fail_pip: bool = False,
        create_artifacts: bool = True,
    ) -> None:
        self.root = root
        self.origin = origin
        self.venv_version = venv_version
        self.dependency_ok = dependency_ok
        self.tracked_site = tracked_site
        self.fail_unit = fail_unit
        self.fail_docs = fail_docs
        self.fail_build = fail_build
        self.fail_pip = fail_pip
        self.create_artifacts = create_artifacts
        self.calls: list[tuple[tuple[str, ...], Path | None, bool]] = []

    def run(self, argv, *, cwd=None, capture=False):
        argv = tuple(str(item) for item in argv)
        cwd_path = Path(cwd) if cwd is not None else None
        self.calls.append((argv, cwd_path, capture))

        if argv[:3] == ("git", "rev-parse", "--show-toplevel"):
            if self.root is None:
                return ProcessResult(128, "", "not a git repository")
            return ProcessResult(0, str(self.root) + "\n", "")
        if argv[:4] == ("git", "remote", "get-url", "origin"):
            return ProcessResult(0, self.origin + "\n", "")
        if argv[:4] == ("git", "ls-files", "--", "_site"):
            body = "\n".join(self.tracked_site)
            return ProcessResult(0, body + ("\n" if body else ""), "")

        if "-m" in argv and "venv" in argv:
            target = Path(argv[-1])
            target.mkdir(parents=True, exist_ok=True)
            (target / "bin").mkdir(exist_ok=True)
            (target / "bin" / "python").write_text("", encoding="utf-8")
            (target / "pyvenv.cfg").write_text("home = fixture\n", encoding="utf-8")
            return ProcessResult(0, "", "")

        if "-c" in argv:
            script = argv[argv.index("-c") + 1]
            if "sys.prefix" in script and self.root is not None:
                payload = {
                    "version": list(self.venv_version),
                    "prefix": str(self.root / ".venv"),
                }
                return ProcessResult(0, json.dumps(payload) + "\n", "")
            if "importlib.import_module" in script:
                return ProcessResult(0 if self.dependency_ok else 1, "", "missing")

        if "-m" in argv and "pip" in argv:
            return ProcessResult(1 if self.fail_pip else 0, "", "")
        if "unittest" in argv:
            return ProcessResult(1 if self.fail_unit else 0, "", "")
        if any(item.endswith("scripts/validate_documentation.py") for item in argv):
            return ProcessResult(1 if self.fail_docs else 0, "", "")
        if "-m" in argv and "site_generator" in argv:
            if not self.fail_build and self.root is not None and self.create_artifacts:
                for relative in EXPECTED_SITE_ARTIFACTS:
                    path = self.root / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text("fixture", encoding="utf-8")
            return ProcessResult(1 if self.fail_build else 0, "", "")
        return ProcessResult(0, "", "")


class DevToolkitTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        (self.root / "requirements-dev.txt").write_text("pyyaml\nmarkdown\n", encoding="utf-8")

    def make_venv(self) -> None:
        venv = self.root / ".venv"
        (venv / "bin").mkdir(parents=True)
        (venv / "bin" / "python").write_text("", encoding="utf-8")
        (venv / "pyvenv.cfg").write_text("home = fixture\n", encoding="utf-8")

    def test_remote_normalisation_accepts_only_canonical_repository_forms(self) -> None:
        self.assertEqual(
            normalise_remote("https://github.com/8ft0-ai/crypto-pulse.git"),
            "8ft0-ai/crypto-pulse",
        )
        self.assertEqual(
            normalise_remote("git@github.com:8ft0-ai/crypto-pulse.git"),
            "8ft0-ai/crypto-pulse",
        )
        self.assertIsNone(normalise_remote("https://example.invalid/8ft0-ai/crypto-pulse.git"))
        self.assertIsNone(
            normalise_remote("https://token@github.com/8ft0-ai/crypto-pulse.git")
        )

    def test_outside_git_worktree_is_prerequisite_error(self) -> None:
        with self.assertRaisesRegex(PrerequisiteError, "Git worktree"):
            doctor.run(cwd=self.root, runner=FixtureRunner(None), host_version=(3, 12, 0))

    def test_wrong_repository_origin_fails_doctor_and_blocks_check(self) -> None:
        self.make_venv()
        runner = FixtureRunner(self.root, origin="git@github.com:8ft0-ai/other.git")
        with patch("sys.stdout", new=io.StringIO()):
            self.assertEqual(doctor.run(cwd=self.root, runner=runner, host_version=(3, 12, 0)), 2)
        with self.assertRaisesRegex(PrerequisiteError, "origin must identify"):
            check.run(cwd=self.root, runner=runner)

    def test_launcher_reports_missing_supported_python(self) -> None:
        empty_path = self.root / "empty-path"
        empty_path.mkdir()
        completed = subprocess.run(
            ["/bin/sh", str(LAUNCHER), "doctor"],
            text=True,
            capture_output=True,
            env={"PATH": str(empty_path)},
            check=False,
        )
        self.assertEqual(completed.returncode, 3)
        self.assertIn("Python >= 3.12 is required", completed.stderr)

    def test_missing_or_unsupported_host_python_is_detected(self) -> None:
        self.assertFalse(python_supported((3, 11, 9)))
        self.assertTrue(python_supported((3, 12, 0)))
        runner = FixtureRunner(self.root)
        with self.assertRaisesRegex(PrerequisiteError, "Python >= 3.12"):
            bootstrap.run(
                cwd=self.root,
                runner=runner,
                host_python=Path("/usr/bin/python3"),
                host_version=(3, 11, 9),
            )

    def test_missing_and_malformed_venv_are_rejected(self) -> None:
        runner = FixtureRunner(self.root)
        with self.assertRaisesRegex(PrerequisiteError, "missing or malformed"):
            validate_venv(self.root, runner)
        (self.root / ".venv").mkdir()
        with self.assertRaisesRegex(PrerequisiteError, "missing or malformed"):
            validate_venv(self.root, runner)

    def test_unsupported_venv_python_is_rejected(self) -> None:
        self.make_venv()
        runner = FixtureRunner(self.root, venv_version=(3, 11, 9))
        with self.assertRaisesRegex(PrerequisiteError, "Python >= 3.12"):
            validate_venv(self.root, runner)

    def test_missing_declared_dependency_is_reported_by_doctor(self) -> None:
        self.make_venv()
        runner = FixtureRunner(self.root, dependency_ok=False)
        with patch("sys.stdout", new=io.StringIO()):
            self.assertEqual(doctor.run(cwd=self.root, runner=runner, host_version=(3, 12, 0)), 2)

    def test_bootstrap_creates_once_and_is_idempotent(self) -> None:
        runner = FixtureRunner(self.root)
        with patch("sys.stdout", new=io.StringIO()):
            self.assertEqual(
                bootstrap.run(
                    cwd=self.root,
                    runner=runner,
                    host_python=Path("/usr/bin/python3"),
                    host_version=(3, 12, 0),
                ),
                0,
            )
            self.assertEqual(
                bootstrap.run(
                    cwd=self.root,
                    runner=runner,
                    host_python=Path("/usr/bin/python3"),
                    host_version=(3, 12, 0),
                ),
                0,
            )
        venv_creates = [argv for argv, _, _ in runner.calls if "-m" in argv and "venv" in argv]
        pip_installs = [argv for argv, _, _ in runner.calls if "-m" in argv and "pip" in argv]
        self.assertEqual(len(venv_creates), 1)
        self.assertEqual(len(pip_installs), 2)

    def test_bootstrap_recreate_refuses_symlink_escape(self) -> None:
        outside = self.root / "outside"
        outside.mkdir()
        (outside / "pyvenv.cfg").write_text("fixture", encoding="utf-8")
        (self.root / ".venv").symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(PrerequisiteError, "symlink"):
            validate_recreate_target(self.root)

    def test_bootstrap_recreate_refuses_unproven_directory(self) -> None:
        (self.root / ".venv").mkdir()
        with self.assertRaisesRegex(PrerequisiteError, "cannot be proven"):
            validate_recreate_target(self.root)

    def test_bootstrap_child_process_failure_propagates(self) -> None:
        self.make_venv()
        runner = FixtureRunner(self.root, fail_pip=True)
        with self.assertRaisesRegex(bootstrap.TaskFailure, "installation failed"):
            bootstrap.run(
                cwd=self.root,
                runner=runner,
                host_python=Path("/usr/bin/python3"),
                host_version=(3, 12, 0),
            )

    def test_check_reports_unit_docs_and_build_failures(self) -> None:
        self.make_venv()
        runner = FixtureRunner(
            self.root,
            fail_unit=True,
            fail_docs=True,
            fail_build=True,
            create_artifacts=False,
        )
        with patch("sys.stdout", new=io.StringIO()):
            self.assertEqual(check.run(cwd=self.root, runner=runner), 2)
        commands = [argv for argv, _, _ in runner.calls]
        self.assertTrue(any("unittest" in argv for argv in commands))
        self.assertTrue(any(any(item.endswith("scripts/validate_documentation.py") for item in argv) for argv in commands))
        self.assertTrue(any("site_generator" in argv for argv in commands))

    def test_tracked_site_fails_doctor_and_check(self) -> None:
        self.make_venv()
        runner = FixtureRunner(self.root, tracked_site=("_site/index.html",))
        with patch("sys.stdout", new=io.StringIO()):
            self.assertEqual(doctor.run(cwd=self.root, runner=runner, host_version=(3, 12, 0)), 2)
            self.assertEqual(check.run(cwd=self.root, runner=runner), 2)

    def test_untracked_site_is_informational_for_doctor(self) -> None:
        self.make_venv()
        (self.root / "_site").mkdir()
        runner = FixtureRunner(self.root)
        output = io.StringIO()
        with patch("sys.stdout", new=output):
            self.assertEqual(doctor.run(cwd=self.root, runner=runner, host_version=(3, 12, 0)), 0)
        self.assertIn("disposable _site/ is present and untracked", output.getvalue())

    def test_missing_expected_artifact_fails_check(self) -> None:
        self.make_venv()
        runner = FixtureRunner(self.root, create_artifacts=False)
        for relative in EXPECTED_SITE_ARTIFACTS[:-1]:
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("fixture", encoding="utf-8")
        with patch("sys.stdout", new=io.StringIO()):
            self.assertEqual(check.run(cwd=self.root, runner=runner), 2)

    def test_dirty_working_tree_is_allowed_and_no_gh_is_used(self) -> None:
        self.make_venv()
        (self.root / "dirty.txt").write_text("edited", encoding="utf-8")
        runner = FixtureRunner(self.root)
        with patch("sys.stdout", new=io.StringIO()):
            self.assertEqual(doctor.run(cwd=self.root, runner=runner, host_version=(3, 12, 0)), 0)
        self.assertTrue(all(argv[0] != "gh" for argv, _, _ in runner.calls))
        self.assertTrue(all("status" not in argv for argv, _, _ in runner.calls))

    def test_check_runs_in_fixed_order_from_repository_root_when_invoked_below_root(self) -> None:
        self.make_venv()
        subdir = self.root / "docs" / "nested"
        subdir.mkdir(parents=True)
        runner = FixtureRunner(self.root)
        with patch("sys.stdout", new=io.StringIO()):
            self.assertEqual(check.run(cwd=subdir, runner=runner), 0)

        relevant = []
        for argv, cwd, _ in runner.calls:
            if "unittest" in argv:
                relevant.append(("unit", cwd))
            elif any(item.endswith("scripts/validate_documentation.py") for item in argv):
                relevant.append(("docs", cwd))
            elif argv[:4] == ("git", "ls-files", "--", "_site"):
                relevant.append(("tracked", cwd))
            elif "site_generator" in argv:
                relevant.append(("build", cwd))
        self.assertEqual([name for name, _ in relevant], ["unit", "docs", "tracked", "build"])
        self.assertTrue(all(cwd == self.root for _, cwd in relevant))

    def test_cli_exit_mapping_is_stable(self) -> None:
        with patch("cryptopulse_dev.cli.doctor.run", return_value=2):
            self.assertEqual(cli.main(["doctor"]), 2)
        with patch(
            "cryptopulse_dev.cli.doctor.run",
            side_effect=PrerequisiteError("missing"),
        ), patch("sys.stderr", new=io.StringIO()):
            self.assertEqual(cli.main(["doctor"]), 3)
        with patch(
            "cryptopulse_dev.cli.doctor.run",
            side_effect=RuntimeError("boom"),
        ), patch("sys.stderr", new=io.StringIO()):
            self.assertEqual(cli.main(["doctor"]), 4)
        with patch("sys.stderr", new=io.StringIO()):
            self.assertEqual(cli.main(["unknown"]), 3)


if __name__ == "__main__":
    unittest.main()
