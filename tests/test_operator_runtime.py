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
    def __init__(self, root: Path, *, dirty=False, mismatch=None): self.root=root; self.dirty=dirty; self.mismatch=mismatch; self.calls=[]
    def git(self, args, cwd=None):
        self.calls.append(tuple(args)); joined=" ".join(args)
        if "--show-toplevel" in args: return ProcessResult(0, str(self.root)+"\n", "")
        if "status --porcelain=v1" in joined: return ProcessResult(0, " M tools/operator/cp\n" if self.dirty else "", "")
        if "diff-index --cached --quiet" in joined: return ProcessResult(1 if self.mismatch=="index" else 0, "", "")
        if "diff-files --quiet" in joined: return ProcessResult(1 if self.mismatch=="worktree" else 0, "", "")
        if "ls-files -v" in joined:
            flag = "h" if self.mismatch=="hidden" else "H"
            return ProcessResult(0, f"{flag} tools/operator/cp\nH tools/operator/operator.toml\nH tools/operator/cryptopulse_operator/runtime.py\n", "")
        if "ls-tree -r HEAD" in joined:
            return ProcessResult(0, "100755 blob " + "3"*40 + "\ttools/operator/cp\n100644 blob " + "4"*40 + "\ttools/operator/operator.toml\n100644 blob " + "6"*40 + "\ttools/operator/cryptopulse_operator/runtime.py\n", "")
        if "hash-object --no-filters" in joined:
            path=args[-1]; expected={"tools/operator/cp":"3"*40,"tools/operator/operator.toml":"4"*40,"tools/operator/cryptopulse_operator/runtime.py":"6"*40}[path]
            return ProcessResult(0, (("7"*40) if self.mismatch=="hash" and path.endswith("runtime.py") else expected)+"\n", "")
        if "ls-files --others" in joined: return ProcessResult(0, "tools/operator/evil.py\n" if self.mismatch=="untracked" else "", "")
        if args[-1]=="HEAD": value="1"*40
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
        self.temp=tempfile.TemporaryDirectory(); self.root=Path(self.temp.name).resolve(); config_dir=self.root/"tools"/"operator"; config_dir.mkdir(parents=True); (config_dir/"operator.toml").write_text((ROOT/"operator.toml").read_text(encoding="utf-8"), encoding="utf-8")
    def tearDown(self): self.temp.cleanup()
    def test_clean_main_ancestor_runtime_is_trusted(self):
        result=inspect_runtime(FakeRunner(self.root), FakeGitHub(), root=self.root); self.assertTrue(result.complete); self.assertTrue(result.trusted); self.assertEqual(result.identity["commit_sha"],"1"*40); self.assertTrue(result.identity["clean"])
    def test_dirty_runtime_is_error_precondition(self):
        result=inspect_runtime(FakeRunner(self.root,dirty=True),FakeGitHub(),root=self.root); self.assertTrue(result.complete); self.assertFalse(result.trusted); self.assertEqual(result.reason,"dirty-runtime")
    def test_runtime_object_mismatch_is_error_precondition(self):
        for mismatch in ("index","worktree","hidden","hash","untracked"):
            with self.subTest(mismatch=mismatch):
                result=inspect_runtime(FakeRunner(self.root,mismatch=mismatch),FakeGitHub(),root=self.root); self.assertTrue(result.complete); self.assertFalse(result.trusted); self.assertEqual(result.reason,"runtime-object-mismatch")
    def test_runtime_not_on_main_history_is_rejected(self):
        result=inspect_runtime(FakeRunner(self.root),FakeGitHub(provenance="not-on-current-main-history"),root=self.root); self.assertTrue(result.complete); self.assertFalse(result.trusted); self.assertEqual(result.reason,"runtime-not-on-protected-main-history")
    def test_protected_main_provenance_unavailable_is_incomplete(self):
        result=inspect_runtime(FakeRunner(self.root),FakeGitHub(fail=True),root=self.root); self.assertFalse(result.complete); self.assertFalse(result.trusted); self.assertEqual(result.reason,"protected-main-provenance-unavailable")
    def test_unprotected_main_is_rejected(self):
        result=inspect_runtime(FakeRunner(self.root),FakeGitHub(protected=False),root=self.root); self.assertTrue(result.complete); self.assertFalse(result.trusted); self.assertEqual(result.reason,"main-not-protected")

if __name__=="__main__": unittest.main()
