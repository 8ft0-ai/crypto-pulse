from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import trusted_main_source_evidence_candidate as candidate  # noqa: E402


class TrustedMainSourceEvidenceV12WrapperTests(unittest.TestCase):
    def test_public_bounded_renderer_is_used_by_v12_cli_delegate(self) -> None:
        self.assertIs(candidate._impl.render_pr_body, candidate.render_pr_body)
        self.assertTrue(hasattr(candidate._impl, "_legacy"))
        self.assertIs(candidate._impl._legacy.render_pr_body, candidate.render_pr_body)


if __name__ == "__main__":
    unittest.main()
