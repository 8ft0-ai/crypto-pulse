"""Adversarial unit tests for the separately invoked Stage 4A recovery path."""
from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import trusted_main_historical_gap_recovery as recovery
import trusted_main_source_evidence_accumulation as core

MAIN = "a" * 40
OLD = "b" * 40
ORIGINAL_ID = "c" * 64
TREE = "d" * 40
ANCHOR = "2026-11-24T02:00:00Z"


class HistoricalRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.rows = []
        self.blobs = {}
        self.sources = []
        for i in range(2):
            path = f"data/crypto/hourly/2026/11/13/{17+i:02d}07_AEDT_source_snapshot.json"
            blob = f"immutable-original-{i}".encode()
            self.blobs[path] = blob
            row = {
                "canonical_observation_hour_utc": f"2026-11-13T0{6+i}:00:00Z",
                "git_blob_sha": core.git_blob_sha(blob),
                "path": path,
                "sha256": core.sha256_bytes(blob),
                "source_run_id": 100 + i,
                "source_run_attempt": 1,
            }
            self.rows.append(row)
            self.sources.append({"run_id": 100+i, "run_attempt": 1,
                                 "event": "workflow_dispatch", "conclusion": "success"})
        self.manifest = {"base_sha": "e"*40, "candidate_id": ORIGINAL_ID,
                         "added_paths": self.rows}
        self.original_closure = {"sha256": "f"*64}
        self.source_set = {
            "contract": recovery.SOURCE_SET_CONTRACT,
            "original_candidate_commit_sha": OLD,
            "original_candidate_id": ORIGINAL_ID,
            "records": copy.deepcopy(self.rows),
        }

    def run_recovery(self, *, source_set=None, trusted=MAIN, observed=MAIN,
                     source_list=None, main_bytes=None, original_bytes=None,
                     quality="valid-ok", verifier_failure=None):
        if source_set is None:
            source_set = self.source_set
        if source_list is None:
            source_list = self.sources

        def git_bytes(_root, sha, path):
            if sha == OLD:
                return self.blobs[path] if original_bytes is None else (None if original_bytes is False else original_bytes)
            if sha == MAIN:
                return main_bytes
            raise AssertionError("unexpected Git revision")

        def proof(_root, _main, _config, source):
            if verifier_failure is not None:
                raise ValueError(verifier_failure)
            row = self.rows[source["run_id"] - 100]
            return {
                "snapshot_bytes": self.blobs[row["path"]],
                "snapshot_sha256": row["sha256"],
                "snapshot_git_blob_sha": row["git_blob_sha"],
                "snapshot_path": row["path"],
                "canonical_observation_hour_utc": row["canonical_observation_hour_utc"],
                "quality_status": quality,
                "publication_intent_sha256": "1"*64,
                "accepted_hour_receipt_sha256": "2"*64,
                "input_identity": {"run_id": source["run_id"], "run_attempt": 1},
            }
        with (patch.object(recovery, "verify_original_evidence",
                           return_value=(self.manifest, self.original_closure)),
              patch.object(recovery.core, "_require_exact_commit", return_value=(MAIN, TREE)),
              patch.object(recovery.core, "_resolve_anchor", return_value=ANCHOR),
              patch.object(recovery.core, "_load_base_config", return_value={}),
              patch.object(recovery.core, "_git_bytes_at", side_effect=git_bytes),
              patch.object(recovery.candidate, "source_inputs_from_bundle",
                           return_value=source_list),
              patch.object(recovery.prospective, "_verify_candidate_source",
                           side_effect=proof)):
            return recovery.build_recovery(Path("/tmp"), trusted, observed, OLD,
                                           source_set, Path("/unused"))

    def test_accepts_originals_without_byte_changes(self):
        manifest, closure, files = self.run_recovery()
        self.assertEqual(files, self.blobs)
        self.assertEqual(len(manifest["added_paths"]), 2)
        self.assertEqual(closure["sha256"],
                         recovery._hash({k:v for k,v in closure.items() if k != "sha256"}))
        self.assertEqual(manifest["candidate_id"], core._candidate_id(manifest))
        self.assertEqual(manifest["base_sha"], MAIN)
        self.assertEqual(manifest["source_population_closure_sha256"], closure["sha256"])

    def test_stale_or_mismatched_main_is_rejected(self):
        with self.assertRaisesRegex(recovery.RecoveryError, "stale or mismatched"):
            self.run_recovery(observed="9"*40)

    def test_duplicate_utc_hour_rejected(self):
        self.rows[1]["canonical_observation_hour_utc"] = self.rows[0]["canonical_observation_hour_utc"]
        self.source_set["records"][1]["canonical_observation_hour_utc"] = self.rows[0]["canonical_observation_hour_utc"]
        with self.assertRaisesRegex(recovery.RecoveryError, "duplicate UTC hour"):
            self.run_recovery()

    def test_duplicate_path_rejected(self):
        self.rows[1]["path"] = self.rows[0]["path"]
        self.source_set["records"][1]["path"] = self.rows[0]["path"]
        with self.assertRaisesRegex(recovery.RecoveryError, "duplicate UTC hour, source path"):
            self.run_recovery()

    def test_same_path_differing_trusted_bytes_rejected(self):
        with self.assertRaisesRegex(recovery.RecoveryError, "same-path differing bytes"):
            self.run_recovery(main_bytes=b"tampered-trusted")

    def test_already_trusted_identical_is_idempotent(self):
        # All records have distinct original bytes; use one-record fixture.
        self.manifest["added_paths"] = self.rows[:1]
        self.source_set["records"] = self.source_set["records"][:1]
        self.sources = self.sources[:1]
        def same(_root, sha, path):
            return self.blobs[path] if sha in (MAIN, OLD) else None
        with (patch.object(recovery, "verify_original_evidence",
                           return_value=(self.manifest, self.original_closure)),
              patch.object(recovery.core, "_require_exact_commit", return_value=(MAIN, TREE)),
              patch.object(recovery.core, "_resolve_anchor", return_value=ANCHOR),
              patch.object(recovery.core, "_load_base_config", return_value={}),
              patch.object(recovery.core, "_git_bytes_at", side_effect=same),
              patch.object(recovery.candidate, "source_inputs_from_bundle",
                           return_value=self.sources),
              patch.object(recovery.prospective, "_verify_candidate_source",
                           return_value={
                               "snapshot_bytes": self.blobs[self.rows[0]["path"]],
                               "snapshot_sha256": self.rows[0]["sha256"],
                               "snapshot_git_blob_sha": self.rows[0]["git_blob_sha"],
                               "snapshot_path": self.rows[0]["path"],
                               "canonical_observation_hour_utc": self.rows[0]["canonical_observation_hour_utc"],
                               "quality_status": "valid-ok",
                               "publication_intent_sha256": "1"*64,
                               "accepted_hour_receipt_sha256": "2"*64,
                               "input_identity": {},
                           })):
            manifest, _, files = recovery.build_recovery(
                Path("/tmp"), MAIN, MAIN, OLD, self.source_set, Path("/unused"))
        self.assertFalse(files)
        self.assertEqual(manifest["added_paths"], [])
        self.assertEqual(len(manifest["already_trusted_paths"]), 1)

    def test_missing_original_blob_rejected(self):
        with self.assertRaisesRegex(recovery.RecoveryError, "missing historical Git source"):
            self.run_recovery(original_bytes=False)

    def test_altered_original_blob_rejected(self):
        with self.assertRaisesRegex(recovery.RecoveryError, "original Git blob identity differs"):
            self.run_recovery(original_bytes=b"tampered")

    def test_invalid_source_quality_rejected(self):
        with self.assertRaisesRegex(recovery.RecoveryError, "quality differs"):
            self.run_recovery(quality="invalid")

    def test_invalid_provenance_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "bad receipt"):
            self.run_recovery(verifier_failure="bad receipt")

    def test_missing_source_provenance_rejected(self):
        with self.assertRaisesRegex(recovery.RecoveryError, "missing or ambiguous"):
            self.run_recovery(source_list=self.sources[:1])

    def test_unsupported_event_rejected(self):
        sources = copy.deepcopy(self.sources)
        sources[0]["event"] = "unsupported"
        with self.assertRaisesRegex(recovery.RecoveryError, "unsupported historical source"):
            self.run_recovery(source_list=sources)

    def test_incorrect_manifest_digest_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            bad_manifest = {"candidate_id": "0"*64, "base_sha": "e"*40,
                            "added_paths": list(self.rows)}
            closure = {"expected_main_sha": "e"*40}
            closure["sha256"] = recovery._hash(closure)
            evidence = {"expected_main_sha": "e"*40,
                        "candidate_id": bad_manifest["candidate_id"],
                        "source_population_closure_sha256": closure["sha256"]}
            for name, value in [("accumulation-manifest.json", bad_manifest),
                                ("source-population-closure.json", closure),
                                ("candidate-evidence.json", evidence)]:
                (p / name).write_text(json.dumps(value))
            with patch.object(recovery.candidate, "verify_bundle"):
                with self.assertRaisesRegex(recovery.RecoveryError, "incorrect original manifest digest"):
                    recovery.verify_original_evidence(Path("/tmp"), p, OLD)

    def test_incorrect_closure_digest_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp)
            m = {"base_sha": "e"*40, "added_paths": self.rows}
            m["candidate_id"] = core._candidate_id(m)
            closure = {"expected_main_sha": "e"*40, "sha256": "0"*64}
            for name, value in [("accumulation-manifest.json", m),
                                ("source-population-closure.json", closure),
                                ("candidate-evidence.json", {"candidate_id": m["candidate_id"]})]:
                (p / name).write_text(json.dumps(value))
            with patch.object(recovery.candidate, "verify_bundle"):
                with self.assertRaisesRegex(recovery.RecoveryError, "incorrect original source-population closure digest"):
                    recovery.verify_original_evidence(Path("/tmp"), p, OLD)

    def test_source_set_digest_changed_rejected(self):
        mutated = copy.deepcopy(self.source_set)
        mutated["records"][0]["sha256"] = "0"*64
        with self.assertRaisesRegex(recovery.RecoveryError, "differs from original"):
            self.run_recovery(source_set=mutated)


if __name__ == "__main__":
    unittest.main()
