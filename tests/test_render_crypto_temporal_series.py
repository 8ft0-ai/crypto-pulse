from __future__ import annotations

import copy, json, os, subprocess, sys, tempfile, unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from crypto_temporal_series import TemporalSeriesError, build_temporal_series, series_id_for_record  # noqa: E402
from render_crypto_temporal_series import HEIGHT, WIDTH, _render_validated_series, render_temporal_series  # noqa: E402
from validate_crypto_snapshot_comparison import CONFIG_BLOB_SHA, CONFIG_PATH, VALIDATOR_BLOB_SHA, VALIDATOR_PATH  # noqa: E402

CORPUS = ROOT / "tests" / "fixtures" / "phase10_comparison_proof_v1.json"
CASE = "01-comparison-available-mixed-evidence"


def git(repo: Path, *args: str, data: bytes | None = None, env_extra: dict[str,str] | None = None) -> bytes:
    env=os.environ.copy(); env.update({"GIT_CONFIG_NOSYSTEM":"1","GIT_OPTIONAL_LOCKS":"0","LC_ALL":"C"}); env.update(env_extra or {})
    p=subprocess.run(["git","-C",str(repo),*args],input=data,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env)
    if p.returncode: raise AssertionError(p.stderr.decode(errors="replace") or f"git {' '.join(args)} failed")
    return p.stdout


def text(v: bytes) -> str: return v.decode().strip()


def identity(name: str, when: str, quality="valid-ok", warns=None) -> dict:
    return {"path":name,"sha256":(("a" if "current" in name else "b")*64),"schema_version":"0.2","generated_at_utc":when,"quality_status":quality,"non_blocking_warnings":list(warns or [])}


def value(slot: str, datum, cur: dict, pred: dict) -> dict:
    return {"slot_utc":slot,"gap":None,"value":{"datum":datum,"comparison_id":"c"*64,"current":copy.deepcopy(cur),"predecessor":copy.deepcopy(pred),"evidence":{"family":"market-asset","symbol":"BTC","field":"price_usd","predecessor":{"present":True,"value":1},"current":{"present":True,"value":datum},"comparison_state":"comparable","relation":"current-greater"}}}


def record(entries: list[dict], kind="metric", key="BTC.price_usd") -> dict:
    r={"schema_version":"crypto-temporal-series/v1","series_kind":kind,"series_key":key,"window":{"start_utc":entries[0]["slot_utc"],"end_utc":entries[-1]["slot_utc"]},"repository_context":{"commit_sha":"1"*40,"tree_sha":"2"*40,"validator":{"path":VALIDATOR_PATH,"git_blob_sha":VALIDATOR_BLOB_SHA},"config":{"path":CONFIG_PATH,"git_blob_sha":CONFIG_BLOB_SHA}},"phase10":{"comparison_schema_version":"crypto-snapshot-comparison/v1","predecessor_policy_version":"phase10-predecessor-exact-hour/v1","semantic_contract_version":"phase10-snapshot-semantics-0.2/v1"},"entries":entries,"series_id":""}
    r["series_id"]=series_id_for_record(r); return r


class RendererTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.corpus=json.loads(CORPUS.read_text())

    def seed(self):
        case=self.corpus["cases"][CASE]; tmp=tempfile.TemporaryDirectory(prefix="phase11-render-"); repo=Path(tmp.name); git(repo,"init","-q")
        files={VALIDATOR_PATH:(ROOT/VALIDATOR_PATH).read_text(),CONFIG_PATH:(ROOT/CONFIG_PATH).read_text(),**case["repository_files"],**case.get("contract_override",{})}
        self.assertEqual(text(git(repo,"hash-object","--stdin",data=files[VALIDATOR_PATH].encode())),VALIDATOR_BLOB_SHA)
        self.assertEqual(text(git(repo,"hash-object","--stdin",data=files[CONFIG_PATH].encode())),CONFIG_BLOB_SHA)
        for path in sorted(files):
            blob=text(git(repo,"hash-object","-w","--stdin",data=files[path].encode())); git(repo,"update-index","--add","--cacheinfo",f"100644,{blob},{path}")
        tree=text(git(repo,"write-tree")); s=self.corpus["seed_commit"]
        env={"GIT_AUTHOR_NAME":s["author_name"],"GIT_AUTHOR_EMAIL":s["author_email"],"GIT_AUTHOR_DATE":s["author_date"],"GIT_COMMITTER_NAME":s["committer_name"],"GIT_COMMITTER_EMAIL":s["committer_email"],"GIT_COMMITTER_DATE":s["committer_date"]}
        commit=text(git(repo,"-c","commit.gpgsign=false","commit-tree",tree,data=(s["message"]+"\n").encode(),env_extra=env)); return tmp,repo,commit

    def slot(self):
        c=self.corpus["cases"][CASE]; return json.loads(c["repository_files"][c["current_repository_path"]])["run"]["generated_at_utc"]

    def test_metric_real_validation_determinism_and_complete_table(self):
        tmp,repo,commit=self.seed()
        try:
            s=self.slot(); r=build_temporal_series(repo,commit,"metric","BTC.price_usd",s,s); a=render_temporal_series(repo,r); b=render_temporal_series(repo,r)
            self.assertEqual(a.encode(),b.encode()); self.assertEqual(a.count("<figure>"),1); self.assertEqual(a.count("<svg "),1); self.assertEqual(a.count("<table "),1)
            self.assertEqual(a.count("<tr data-slot-utc="),len(r["entries"])); self.assertIn(f'width="{WIDTH}" height="{HEIGHT}"',a); self.assertIn('data-visual-mode="numeric"',a)
            self.assertIn("61000",a); self.assertIn("valid-degraded",a); self.assertIn("valid-ok",a); self.assertIn("optional exchange source coinbase_exchange has status: error",a)
            for forbidden in ("<script","<canvas","http://","https://"): self.assertNotIn(forbidden,a.lower())
        finally: tmp.cleanup()

    def test_source_status_is_categorical(self):
        tmp,repo,commit=self.seed()
        try:
            s=self.slot(); r=build_temporal_series(repo,commit,"source-status","coinbase_exchange",s,s); out=render_temporal_series(repo,r)
            self.assertIn('data-series-kind="source-status"',out); self.assertIn('data-visual-mode="categorical"',out); self.assertIn("no numeric market axis",out); self.assertIn('data-status="error"',out); self.assertNotIn('data-visual-mode="numeric"',out)
        finally: tmp.cleanup()

    def test_gap_and_identity_discontinuity_break_numeric_line(self):
        p0=identity("pred0","2026-01-01T00:00:00Z"); c0=identity("current0","2026-01-01T01:00:00Z"); c1=identity("current1","2026-01-01T02:00:00Z")
        p3=identity("pred3","2026-01-01T02:00:00Z"); c3=identity("current3","2026-01-01T04:00:00Z"); wrong=identity("wrong","2026-01-01T04:00:00Z"); c4=identity("current4","2026-01-01T05:00:00Z")
        es=[value("2026-01-01T01:00:00Z",10,c0,p0),value("2026-01-01T02:00:00Z",11,c1,c0),{"slot_utc":"2026-01-01T03:00:00Z","value":None,"gap":{"reason":"current-missing","current_candidates":[]}},value("2026-01-01T04:00:00Z",12,c3,p3),value("2026-01-01T05:00:00Z",13,c4,wrong)]
        out=_render_validated_series(record(es)); self.assertIn('data-segment-count="3"',out); self.assertEqual(out.count('class="metric-line"'),1); self.assertIn('class="gap-marker" data-slot-index="2"',out)
        for i in range(3): self.assertIn(f'class="metric-segment" data-segment="{i}"',out)

    def test_degraded_ambiguity_escaping_and_exact_number_text(self):
        pred=identity("pred","2026-01-01T00:00:00Z","valid-degraded",["pred <warning> & evidence"]); cur=identity("current","2026-01-01T01:00:00Z","valid-degraded",["current <warning> & evidence"])
        amb={"slot_utc":"2026-01-01T02:00:00Z","value":None,"gap":{"reason":"current-ambiguous","current_candidates":[{"path":"data/<candidate>_source_snapshot.json","sha256":"d"*64,"schema_version":"0.2<&>","generated_at_utc":"2026-01-01T02:00:00Z"},{"path":"data/second_source_snapshot.json","sha256":"e"*64,"schema_version":"0.2","generated_at_utc":"2026-01-01T02:00:00Z"}]}}
        out=_render_validated_series(record([value("2026-01-01T01:00:00Z","10.2500",cur,pred),amb]))
        for expected in ("10.2500","current &lt;warning&gt; &amp; evidence","pred &lt;warning&gt; &amp; evidence","current-ambiguous","&lt;candidate&gt;","0.2&lt;&amp;&gt;","d"*64,"e"*64): self.assertIn(expected,out)
        self.assertNotIn("current <warning>",out); self.assertNotIn("<candidate>",out)

    def test_invalid_input_is_rejected_before_pure_renderer(self):
        with mock.patch("render_crypto_temporal_series.validate_temporal_series",side_effect=TemporalSeriesError("invalid")) as v, mock.patch("render_crypto_temporal_series._render_validated_series") as pure:
            with self.assertRaises(TemporalSeriesError): render_temporal_series(Path("."),{"schema_version":"tampered"})
            v.assert_called_once(); pure.assert_not_called()

    def test_fixed_dimensions_order_and_format_stable(self):
        p=identity("pred","2026-01-01T00:00:00Z"); c=identity("current","2026-01-01T01:00:00Z"); r=record([value("2026-01-01T01:00:00Z","1.2300",c,p)])
        a=_render_validated_series(r); b=_render_validated_series(r); self.assertEqual(a,b); self.assertIn(f'width="{WIDTH}" height="{HEIGHT}"',a); self.assertIn("<td>1.2300</td>",a); self.assertNotIn("<td>1.2300%</td>",a); self.assertLess(a.index("<figure>"),a.index("<table ")); self.assertTrue(a.endswith("\n"))


if __name__ == "__main__": unittest.main()
