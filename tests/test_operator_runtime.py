from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1] / "tools" / "operator"
sys.path.insert(0, str(ROOT))

from cryptopulse_operator.github_read import GitHubReadError
from cryptopulse_operator.process import ProcessResult
from cryptopulse_operator.runtime import inspect_runtime


class FakeRunner:
    def __init__(self, root: Path, *, dirty=False): self.root=root; self.dirty=dirty; self.calls=[]
    def git(self, args, cwd=None):
        self.calls.append(tuple(args)); joined=" ".join(args)
        if "--show-toplevel" in args: value=str(self.root)
        elif "status --porcelain=v1" in joined: value=" M tools/operator/cp" if self.dirty else ""
        elif args[-1]=="HEAD": value="1"*40
        elif args[-1]=="HEAD^{tree}": value="2"*40
        elif args[-1]=="HEAD:tools/operator/cp": value="3"*40
        elif args[-1]=="HEAD:tools/operator/operator.toml": value="4"*40
        elif args[-1]=="HEAD:tools/operator/cryptopulse_operator": value="5"*40
        else: raise AssertionError(args)
        return ProcessResult(0, value+"\n", "")


class FakeGitHub:
    def __init__(self, *, protected=True, provenance="ancestor-of-current-main", fail=False): self.protected=protected; self.provenance=provenance; self.fail=fail
    def main_branch(self):
        if self.fail: raise GitHubReadError("unavailable")
        return {"sha":"9"*40,"tree_sha":"8"*40,"protected":self.protected,"required_checks":[]}
    def runtime_provenance(self, runtime_sha, main_sha):
        if self.fail: raise GitHubReadError("unavailable")
        return self.provenance


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.root=Path(self.temp.name).resolve(); config_dir=self.root/"tools"/"operator"; config_dir.mkdir(parents=True); source_config=ROOT/"operator.toml"; (config_dir/"operator.toml").write_text(source_config.read_text(encoding="utf-8"), encoding="utf-8")
    def tearDown(self): self.temp.cleanup()
    def test_clean_main_ancestor_runtime_is_trusted(self):
        result=inspect_runtime(FakeRunner(self.root), FakeGitHub(), root=self.root); self.assertTrue(result.complete); self.assertTrue(result.trusted); self.assertEqual(result.identity["commit_sha"],"1"*40); self.assertEqual(result.identity["toolkit_identity"]["launcher_blob"],"3"*40)
    def test_dirty_runtime_is_error_precondition(self):
        result=inspect_runtime(FakeRunner(self.root,dirty=True),FakeGitHub(),root=self.root); self.assertTrue(result.complete); self.assertFalse(result.trusted); self.assertEqual(result.reason,"dirty-runtime")
    def test_runtime_not_on_main_history_is_rejected(self):
        result=inspect_runtime(FakeRunner(self.root),FakeGitHub(provenance="not-on-current-main-history"),root=self.root); self.assertTrue(result.complete); self.assertFalse(result.trusted); self.assertEqual(result.reason,"runtime-not-on-protected-main-history")
    def test_protected_main_provenance_unavailable_is_incomplete(self):
        result=inspect_runtime(FakeRunner(self.root),FakeGitHub(fail=True),root=self.root); self.assertFalse(result.complete); self.assertFalse(result.trusted); self.assertEqual(result.reason,"protected-main-provenance-unavailable")
    def test_unprotected_main_is_rejected(self):
        result=inspect_runtime(FakeRunner(self.root),FakeGitHub(protected=False),root=self.root); self.assertTrue(result.complete); self.assertFalse(result.trusted); self.assertEqual(result.reason,"main-not-protected")


if __name__=="__main__": unittest.main()
