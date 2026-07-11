from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

import yaml

from llm_analysis.evaluation import prepare_evaluation

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "evaluation/phase-05/corpus.yml"


class EvaluationCorpusLockTests(unittest.TestCase):
    def test_historical_snapshot_sha256_locks_match_repository_bytes(self) -> None:
        if not (ROOT / "data/crypto/hourly/2026/07/08/1434_AEST_source_snapshot.json").exists():
            self.skipTest("focused local reconstruction does not contain archived snapshots")
        manifest = yaml.safe_load(CORPUS.read_text(encoding="utf-8"))
        mismatches = []
        for case in manifest["cases"]:
            path = ROOT / case["snapshot_path"]
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual != case["snapshot_sha256"]:
                mismatches.append(f"{case['snapshot_path']}={actual}")
        self.assertFalse(mismatches, "Update corpus snapshot_sha256 locks:\n" + "\n".join(mismatches))

    def test_locked_corpus_builds_deterministic_evidence_bundles(self) -> None:
        if not (ROOT / "data/crypto/hourly/2026/07/08/1434_AEST_source_snapshot.json").exists():
            self.skipTest("focused local reconstruction does not contain archived snapshots")
        with tempfile.TemporaryDirectory() as tmp:
            _plan, cases = prepare_evaluation(
                repository_root=ROOT,
                config_path="config/llm-evaluation.yml",
                output_dir=tmp,
            )
            self.assertEqual(len(cases), 5)
            self.assertEqual(len({case.key for case in cases}), 5)


if __name__ == "__main__":
    unittest.main()
