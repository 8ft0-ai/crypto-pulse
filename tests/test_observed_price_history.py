"""Hostile contract tests for observed-price-history/v2-terminal."""
import copy
import hashlib
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from observed_price_history import (ObservedPriceError, _classify, canonical, materialise, validate_replay)

COMMIT = "cbaac787015cce6ecf9d2f07bba4a603d3f0f4c2"


class ObservedPriceContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.record = materialise(ROOT, COMMIT)

    def test_exact_24_hour_oracle(self):
        data = self.record
        self.assertEqual(data["window"], {"start_utc": "2026-09-11T01:00:00Z", "end_utc": "2026-09-12T00:00:00Z", "slots": 24})
        self.assertEqual(len(data["entries"]), 24)
        self.assertEqual(sum(x["state"] == "OBSERVED" for x in data["entries"]), 6)
        self.assertEqual(sum(x["state"] == "MISSING" for x in data["entries"]), 18)
        self.assertEqual(sum(v is not None for e in data["entries"] for v in e["prices_usd"].values()), 18)

    def test_deterministic_canonical_bytes(self):
        self.assertEqual(canonical(self.record), canonical(materialise(ROOT, COMMIT)))
        self.assertEqual(validate_replay(ROOT, self.record), self.record)
        without_id = {k: v for k, v in self.record.items() if k != "record_id"}
        self.assertEqual(hashlib.sha256(canonical(without_id)).hexdigest(), self.record["record_id"])

    def test_tampered_canonical_fields_never_validate(self):
        samples = [
            lambda j: j["entries"][3]["prices_usd"].update(BTC=12),
            lambda j: j["entries"].pop(),
            lambda j: j["entries"].reverse(),
            lambda j: j["repository_context"].update(tree_sha="0" * 40),
            lambda j: j["entries"][3]["candidates"][0].update(snapshot_sha256="0" * 64),
            lambda j: j["entries"][3]["candidates"][0].update(git_blob_sha="0" * 40),
            lambda j: j["entries"][3].update(state="MISSING"),
            lambda j: j["entries"][3].update(warnings=["invented"]),
        ]
        for change in samples:
            with self.subTest(change=change):
                record = copy.deepcopy(self.record)
                change(record)
                record["record_id"] = hashlib.sha256(canonical({k: v for k, v in record.items() if k != "record_id"})).hexdigest()
                with self.assertRaises(ObservedPriceError):
                    validate_replay(ROOT, record)

    def test_duplicate_hour_is_blocked(self):
        slot = "2026-09-11T04:00:00Z"
        from resolve_crypto_observation_hour_adjacency import prepare_observation_hour_replay_context
        ctx = prepare_observation_hour_replay_context(ROOT, COMMIT)
        item = ctx._population[slot][0]
        result = _classify([item, item], slot, ctx._config)
        self.assertEqual(result["state"], "AMBIGUOUS")
        self.assertTrue(all(x is None for x in result["prices_usd"].values()))

    def test_missing_hour_is_not_an_invalid_hour(self):
        row = _classify([], "2026-09-11T01:00:00Z", {})
        self.assertEqual(row["state"], "MISSING")
        self.assertEqual(row["candidates"], [])

    def test_validator_runtime_failure_is_terminal(self):
        from resolve_crypto_observation_hour_adjacency import prepare_observation_hour_replay_context
        ctx = prepare_observation_hour_replay_context(ROOT, COMMIT)
        item = ctx._population["2026-09-11T04:00:00Z"][0]
        with patch("observed_price_history.validate_observation_hour", side_effect=OSError("I/O failure")):
            with self.assertRaises(OSError):
                _classify([item], "2026-09-11T04:00:00Z", ctx._config)

    def test_invalid_repository_authority_aborts(self):
        with self.assertRaises(ObservedPriceError):
            materialise(ROOT, "0" * 40)

    def test_unsupported_candidate_shape_rejected(self):
        for bad in (None, [], {"repository_context": {}}, {"repository_context": {"commit_sha": "0" * 40}}):
            with self.subTest(bad=bad), self.assertRaises(ObservedPriceError):
                validate_replay(ROOT, bad)


if __name__ == "__main__":
    unittest.main()
