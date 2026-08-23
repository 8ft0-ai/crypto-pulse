import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1] / "tools" / "operator"
sys.path.insert(0, str(ROOT))

from cryptopulse_operator.evidence import Evidence, Status, canonical_json_bytes
from cryptopulse_operator.redact import RedactionError, assert_safe


def sample(runtime_commit="a" * 40):
    return Evidence(command="doctor", repository="8ft0-ai/crypto-pulse", invocation_target={"kind": "local-runtime"}, runtime={"repository": "8ft0-ai/crypto-pulse", "commit_sha": runtime_commit, "tree_sha": "b" * 40, "toolkit_identity": {}, "config_identity": "c" * 40, "provenance": "current-main", "clean": True}, remote={}, local={}, status=Status.PASS, completeness={"complete": True})


class EvidenceTests(unittest.TestCase):
    def test_canonical_evidence_is_deterministic_and_hash_bound(self):
        first = sample().payload(); second = sample().payload(); self.assertEqual(first, second)
        without = dict(first); digest = without.pop("evidence_sha256")
        self.assertEqual(digest, hashlib.sha256(canonical_json_bytes(without)).hexdigest())
    def test_runtime_identity_changes_evidence_identity(self):
        self.assertNotEqual(sample("a"*40).payload()["evidence_sha256"], sample("d"*40).payload()["evidence_sha256"])
    def test_evidence_envelope_is_paste_safe_json(self):
        envelope = sample().envelope().splitlines(); self.assertEqual(envelope[0], "CRYPTOPULSE_OPERATOR_EVIDENCE/v1"); self.assertEqual(json.loads(envelope[1])["status"], "PASS")
    def test_sensitive_tokens_and_private_keys_fail_closed(self):
        for value in ("ghp_abcdefghijklmnopqrstuvwxyz1234567890", "github_pat_abcdefghijklmnopqrstuvwxyz_123456", "token=supersecretvalue", "-----BEGIN PRIVATE KEY-----"):
            with self.subTest(value=value):
                with self.assertRaises(RedactionError): assert_safe({"finding": value})


if __name__ == "__main__": unittest.main()
