from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1] / "tools" / "operator"
sys.path.insert(0, str(ROOT))

from cryptopulse_operator.commands.doctor import python_supported, run as doctor_run
from cryptopulse_operator.commands.snapshot import run as snapshot_run
from cryptopulse_operator.evidence import Status
from cryptopulse_operator.github_read import GitHubReadError, GitHubReader, flatten_pages
from cryptopulse_operator.git_local import normalise_remote, observe_repository
from cryptopulse_operator.process import ProcessError, ProcessResult, ProcessRunner


class RecordingRunner(ProcessRunner):
    def __init__(self):
        self._executables = {"git": "/usr/bin/git", "gh": "/usr/bin/gh"}
        self._env = {}
        self.argv = []
    def run(self, argv, cwd=None):
        self.argv.append(tuple(argv)); return ProcessResult(0, "", "")


class CapabilityRunner:
    def __init__(self, *, git=True, gh=True): self.cap = {"git": git, "gh": gh}
    def has_executable(self, name): return self.cap[name]


class AuthOnlyGitHub:
    def __init__(self, ok): self.ok = ok
    def auth_ok(self): return self.ok


def make_launcher_repo(*, python_candidates=None):
    td = tempfile.TemporaryDirectory()
    root = Path(td.name)
    target = root / "tools" / "operator"
    shutil.copytree(ROOT, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    launcher = target / "cp"
    if python_candidates is not None:
        text = launcher.read_text(encoding="utf-8")
        start = 'PYTHON_CANDIDATES="/opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3 /Library/Frameworks/Python.framework/Versions/Current/bin/python3"'
        text = text.replace(start, f'PYTHON_CANDIDATES="{python_candidates}"')
        launcher.write_text(text, encoding="utf-8")
        launcher.chmod(0o755)
    subprocess.run(["/usr/bin/git", "init", "-q"], cwd=root, check=True)
    subprocess.run(["/usr/bin/git", "config", "user.email", "test@example.com"], cwd=root, check=True)
    subprocess.run(["/usr/bin/git", "config", "user.name", "test"], cwd=root, check=True)
    subprocess.run(["/usr/bin/git", "add", "."], cwd=root, check=True)
    subprocess.run(["/usr/bin/git", "commit", "-qm", "fixture"], cwd=root, check=True)
    return td, root, launcher


class CommandSubstrateTests(unittest.TestCase):
    def test_remote_normalisation_accepts_https_and_ssh_only(self):
        self.assertEqual(normalise_remote("https://github.com/8ft0-ai/crypto-pulse.git"), "8ft0-ai/crypto-pulse")
        self.assertEqual(normalise_remote("git@github.com:8ft0-ai/crypto-pulse.git"), "8ft0-ai/crypto-pulse")
        self.assertIsNone(normalise_remote("https://example.invalid/8ft0-ai/crypto-pulse.git"))

    def test_paginated_pages_exhaust_and_verify_total(self):
        self.assertEqual(flatten_pages([[1, 2], [3]], expected_total=3), [1, 2, 3])
        with self.assertRaises(GitHubReadError): flatten_pages([[1], [2]], expected_total=3)

    def test_malformed_page_fails_closed(self):
        with self.assertRaises(GitHubReadError): flatten_pages([[1], {"unexpected": True}])

    def test_process_adapter_uses_only_absolute_approved_executables(self):
        runner = RecordingRunner(); runner.git(["rev-parse", "HEAD"]); runner.gh(["auth", "status"])
        self.assertEqual(runner.argv[0][0], "/usr/bin/git"); self.assertEqual(runner.argv[1][0], "/usr/bin/gh")
        with self.assertRaises(ProcessError): ProcessRunner().run(["git", "rev-parse", "HEAD"])

    def test_process_resolver_ignores_malicious_path_for_git_and_gh(self):
        shadow = Path(tempfile.mkdtemp()); self.addCleanup(shutil.rmtree, shadow)
        for name in ("git", "gh"):
            fake = shadow / name; fake.write_text("#!/bin/sh\nexit 77\n", encoding="utf-8"); fake.chmod(0o755)
        runner = ProcessRunner(env={"PATH": str(shadow)})
        for name in ("git", "gh"):
            resolved = runner.executable(name)
            self.assertNotEqual(resolved, str(shadow / name))
            if resolved is not None:
                self.assertTrue(Path(resolved).is_absolute())

    def test_launcher_ignores_path_and_pythonpath_shadowing(self):
        td, root, launcher = make_launcher_repo()
        self.addCleanup(td.cleanup)
        shadow = Path(tempfile.mkdtemp()); self.addCleanup(shutil.rmtree, shadow)
        marker = shadow / "executed"
        for name in ("python3", "git", "gh"):
            fake = shadow / name; fake.write_text(f"#!/bin/sh\necho {name} >> '{marker}'\nexit 77\n", encoding="utf-8"); fake.chmod(0o755)
        package = shadow / "cryptopulse_operator"; package.mkdir(); (package / "__init__.py").write_text("raise SystemExit(77)\n", encoding="utf-8")
        env = dict(os.environ); env["PATH"] = str(shadow); env["PYTHONPATH"] = str(shadow)
        proc = subprocess.run([str(launcher), "--help"], cwd=shadow, env=env, capture_output=True, text=True, check=False)
        self.assertEqual(proc.returncode, 0, proc.stderr); self.assertFalse(marker.exists()); self.assertIn("CryptoPulse read-only operator evidence toolkit", proc.stdout)

    def test_launcher_fails_closed_when_python_missing_or_old(self):
        td, _, launcher = make_launcher_repo(python_candidates="/definitely/missing/python3")
        self.addCleanup(td.cleanup)
        missing = subprocess.run([str(launcher), "--help"], capture_output=True, text=True, check=False)
        self.assertEqual(missing.returncode, 4); self.assertIn("python3 >= 3.12", missing.stderr)
        fake_dir = Path(tempfile.mkdtemp()); self.addCleanup(shutil.rmtree, fake_dir)
        old_python = fake_dir / "python3"; old_python.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8"); old_python.chmod(0o755)
        td2, _, launcher2 = make_launcher_repo(python_candidates=str(old_python)); self.addCleanup(td2.cleanup)
        old = subprocess.run([str(launcher2), "--help"], capture_output=True, text=True, check=False)
        self.assertEqual(old.returncode, 4); self.assertIn("python3 >= 3.12", old.stderr)

    def test_doctor_prerequisite_regressions(self):
        self.assertFalse(python_supported(None)); self.assertFalse(python_supported((3, 11))); self.assertTrue(python_supported((3, 12)))
        missing_git = doctor_run(CapabilityRunner(git=False), AuthOnlyGitHub(True)); self.assertEqual(missing_git.status, Status.ERROR)
        missing_gh = doctor_run(CapabilityRunner(gh=False), AuthOnlyGitHub(False)); self.assertEqual(missing_gh.status, Status.ERROR)
        unauth = doctor_run(CapabilityRunner(), AuthOnlyGitHub(False)); self.assertEqual(unauth.status, Status.ERROR)

    def test_snapshot_prerequisite_regressions(self):
        missing_git = snapshot_run(Path("/tmp/repo"), CapabilityRunner(git=False), AuthOnlyGitHub(True)); self.assertEqual(missing_git.status, Status.ERROR)
        missing_gh = snapshot_run(Path("/tmp/repo"), CapabilityRunner(gh=False), AuthOnlyGitHub(False)); self.assertEqual(missing_gh.status, Status.ERROR)
        unauth = snapshot_run(Path("/tmp/repo"), CapabilityRunner(), AuthOnlyGitHub(False)); self.assertEqual(unauth.status, Status.ERROR)

    def test_collection_uses_central_paginate_and_fails_closed_on_error(self):
        class GhRunner:
            def __init__(self, code=0, out="[[1,2],[3]]"): self.code=code; self.out=out; self.calls=[]
            def gh(self, args, cwd=None): self.calls.append(tuple(args)); return ProcessResult(self.code, self.out, "")
        runner=GhRunner(); reader=GitHubReader(runner); self.assertEqual(reader.collection("repos/x/y/items", expected_total=3), [1,2,3])
        self.assertEqual(runner.calls[0][:5], ("api","--method","GET","--paginate","--slurp"))
        with self.assertRaises(GitHubReadError): GitHubReader(GhRunner(code=1, out="")).collection("repos/x/y/items")

    def test_local_snapshot_reports_dirty_and_wrong_origin_truthfully(self):
        class LocalRunner:
            def git(self,args,cwd=None):
                joined=" ".join(args)
                if "--show-toplevel" in args: value="/tmp/repo"
                elif "symbolic-ref --quiet --short HEAD" in joined: value="feature"
                elif args[-1]=="HEAD": value="1"*40
                elif args[-1]=="HEAD^{tree}": value="2"*40
                elif "remote get-url origin" in joined: value="https://github.com/other/repo.git"
                elif "status --porcelain=v1" in joined: value="?? candidate.txt"
                else: raise AssertionError(args)
                return ProcessResult(0,value+"\n","")
        observed=observe_repository(Path("/tmp/repo"),LocalRunner()); self.assertTrue(observed["dirty"]); self.assertFalse(observed["origin_matches"]); self.assertEqual(observed["branch"],"feature")


if __name__ == "__main__": unittest.main()
