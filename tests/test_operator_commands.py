from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]/"tools"/"operator"
sys.path.insert(0,str(ROOT))

from cryptopulse_operator.github_read import GitHubReadError,GitHubReader,flatten_pages
from cryptopulse_operator.git_local import normalise_remote,observe_repository
from cryptopulse_operator.process import ProcessResult,ProcessRunner


class RecordingRunner(ProcessRunner):
    def __init__(self): self.argv=[]
    def run(self,argv,cwd=None): self.argv.append(tuple(argv)); return ProcessResult(0,"","")


class CommandSubstrateTests(unittest.TestCase):
    def test_remote_normalisation_accepts_https_and_ssh_only(self):
        self.assertEqual(normalise_remote("https://github.com/8ft0-ai/crypto-pulse.git"),"8ft0-ai/crypto-pulse"); self.assertEqual(normalise_remote("git@github.com:8ft0-ai/crypto-pulse.git"),"8ft0-ai/crypto-pulse"); self.assertIsNone(normalise_remote("https://example.invalid/8ft0-ai/crypto-pulse.git"))
    def test_paginated_pages_exhaust_and_verify_total(self):
        self.assertEqual(flatten_pages([[1,2],[3]],expected_total=3),[1,2,3]);
        with self.assertRaises(GitHubReadError): flatten_pages([[1],[2]],expected_total=3)
    def test_malformed_page_fails_closed(self):
        with self.assertRaises(GitHubReadError): flatten_pages([[1],{"unexpected":True}])
    def test_candidate_paths_cannot_select_subprocess_executable(self):
        runner=RecordingRunner(); runner.git(["rev-parse","HEAD"]); runner.gh(["auth","status"]); self.assertEqual(runner.argv[0][0],"git"); self.assertEqual(runner.argv[1][0],"gh")
    def test_no_shell_is_required_by_process_adapter_contract(self):
        runner=RecordingRunner(); runner.git(["cat-file","-e","deadbeef^{commit}"]); self.assertEqual(runner.argv,[("git","cat-file","-e","deadbeef^{commit}")])
    def test_collection_uses_central_paginate_and_fails_closed_on_error(self):
        class GhRunner:
            def __init__(self,code=0,out="[[1,2],[3]]"): self.code=code; self.out=out; self.calls=[]
            def gh(self,args,cwd=None): self.calls.append(tuple(args)); return ProcessResult(self.code,self.out,"")
        runner=GhRunner(); reader=GitHubReader(runner); self.assertEqual(reader.collection("repos/x/y/items",expected_total=3),[1,2,3]); self.assertEqual(runner.calls[0][:5],("api","--method","GET","--paginate","--slurp"));
        with self.assertRaises(GitHubReadError): GitHubReader(GhRunner(code=1,out="")).collection("repos/x/y/items")
    def test_launcher_ignores_pythonpath_shadow_package(self):
        import os,subprocess,tempfile
        launcher=ROOT/"cp"
        with tempfile.TemporaryDirectory() as td:
            shadow=Path(td)/"cryptopulse_operator"; shadow.mkdir(); (shadow/"__init__.py").write_text("raise SystemExit(77)\n",encoding="utf-8"); env=dict(os.environ); env["PYTHONPATH"]=td; proc=subprocess.run([str(launcher),"--help"],cwd=td,env=env,capture_output=True,text=True,check=False)
        self.assertEqual(proc.returncode,0,proc.stderr); self.assertIn("CryptoPulse read-only operator evidence toolkit",proc.stdout)
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
    def test_github_reader_uses_get_only_for_fixed_main_endpoint(self):
        class GhRunner:
            def __init__(self): self.calls=[]
            def gh(self,args,cwd=None): self.calls.append(tuple(args)); return ProcessResult(0,'{"commit":{"sha":"'+'1'*40+'","commit":{"tree":{"sha":"'+'2'*40+'"}}},"protected":true}',"")
        runner=GhRunner(); data=GitHubReader(runner).main_branch(); self.assertTrue(data["protected"]); self.assertEqual(runner.calls[0][:3],("api","--method","GET")); self.assertNotIn("POST",runner.calls[0]); self.assertNotIn("PATCH",runner.calls[0]); self.assertNotIn("DELETE",runner.calls[0])


if __name__=="__main__": unittest.main()
