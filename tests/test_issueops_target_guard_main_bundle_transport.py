from __future__ import annotations

import base64
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from issueops_dispatch import core
from issueops_dispatch import target_guard as common
from issueops_dispatch import target_guard_main as guard


class ProtectedMainBundleTransportTests(unittest.TestCase):
    def _download_gh(
        self,
        root: Path,
        *,
        bundles: list[dict[str, object]],
        stderr: bytes = b"",
        returncode: int = 0,
    ) -> Path:
        binary = root / "fake-gh-download"
        bundles_b64 = base64.b64encode(
            b"\n".join(
                json.dumps(item, sort_keys=True).encode("utf-8")
                for item in bundles
            )
            + (b"\n" if bundles else b"")
        ).decode("ascii")
        stderr_b64 = base64.b64encode(stderr).decode("ascii")
        binary.write_text(
            "#!/usr/bin/env python3\n"
            "import base64\n"
            "import hashlib\n"
            "import pathlib\n"
            "import sys\n"
            "args = sys.argv[1:]\n"
            "if args[:2] != ['attestation', 'download']:\n"
            "    raise SystemExit(91)\n"
            "if '--repo' not in args or args[args.index('--repo') + 1] != "
            f"{core.REPOSITORY!r}:\n"
            "    raise SystemExit(92)\n"
            "if '--predicate-type' not in args or args[args.index('--predicate-type') + 1] != "
            f"{core.PREDICATE_TYPE!r}:\n"
            "    raise SystemExit(93)\n"
            "if '--limit' not in args or args[args.index('--limit') + 1] != '1000':\n"
            "    raise SystemExit(94)\n"
            "subject = pathlib.Path(args[2])\n"
            "digest = hashlib.sha256(subject.read_bytes()).hexdigest()\n"
            f"pathlib.Path(f'sha256:{{digest}}.jsonl').write_bytes(base64.b64decode({bundles_b64!r}))\n"
            f"sys.stderr.buffer.write(base64.b64decode({stderr_b64!r}))\n"
            f"raise SystemExit({returncode})\n",
            encoding="utf-8",
        )
        binary.chmod(0o755)
        return binary

    def _verify_gh(
        self,
        root: Path,
        *,
        stdout: bytes,
        stderr: bytes = b"",
        returncode: int = 0,
    ) -> Path:
        binary = root / "fake-gh-verify"
        stdout_b64 = base64.b64encode(stdout).decode("ascii")
        stderr_b64 = base64.b64encode(stderr).decode("ascii")
        binary.write_text(
            "#!/usr/bin/env python3\n"
            "import base64\n"
            "import sys\n"
            "args = sys.argv[1:]\n"
            "if args[:2] != ['attestation', 'verify']:\n"
            "    raise SystemExit(95)\n"
            f"sys.stdout.buffer.write(base64.b64decode({stdout_b64!r}))\n"
            f"sys.stderr.buffer.write(base64.b64decode({stderr_b64!r}))\n"
            f"raise SystemExit({returncode})\n",
            encoding="utf-8",
        )
        binary.chmod(0o755)
        return binary

    def test_pinned_cli_download_returns_one_decoded_json_bundle_per_enumerated_attestation(self) -> None:
        bundles = [
            {"mediaType": "application/vnd.dev.sigstore.bundle.v0.3+json", "n": 1},
            {"mediaType": "application/vnd.dev.sigstore.bundle.v0.3+json", "n": 2},
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subject = root / "dispatch-subject.json"
            subject.write_bytes(b'{"subject":"fixture"}\n')
            digest = hashlib.sha256(subject.read_bytes()).hexdigest()
            result = guard.download_attestation_bundles(
                gh_binary=self._download_gh(root, bundles=bundles),
                subject_path=subject,
                subject_digest=digest,
                expected_count=2,
                destination=root,
                token="unused",
            )

        self.assertEqual([json.loads(line) for line in result], bundles)

    def test_decoded_bundle_count_must_match_bounded_api_enumeration(self) -> None:
        bundles = [{"mediaType": "application/vnd.dev.sigstore.bundle.v0.3+json"}]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subject = root / "dispatch-subject.json"
            subject.write_bytes(b"fixture")
            digest = hashlib.sha256(subject.read_bytes()).hexdigest()
            with self.assertRaisesRegex(common.GuardError, "count does not match"):
                guard.download_attestation_bundles(
                    gh_binary=self._download_gh(root, bundles=bundles),
                    subject_path=subject,
                    subject_digest=digest,
                    expected_count=2,
                    destination=root,
                    token="unused",
                )

    def test_attestation_download_bound_fails_closed_before_subprocess(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subject = root / "dispatch-subject.json"
            subject.write_bytes(b"fixture")
            with self.assertRaisesRegex(common.GuardError, "exceeds"):
                guard.download_attestation_bundles(
                    gh_binary=root / "does-not-exist",
                    subject_path=subject,
                    subject_digest="a" * 64,
                    expected_count=guard.GH_ATTESTATION_LIMIT + 1,
                    destination=root,
                    token="unused",
                )

    def test_download_failure_diagnostic_is_bounded_and_redacted(self) -> None:
        token = "ghs_SECRET123"
        stderr = (b"failure for ghs_SECRET123\n" + b"x" * 1000)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subject = root / "dispatch-subject.json"
            subject.write_bytes(b"fixture")
            digest = hashlib.sha256(subject.read_bytes()).hexdigest()
            with self.assertRaises(common.GuardError) as raised:
                guard.download_attestation_bundles(
                    gh_binary=self._download_gh(
                        root, bundles=[], stderr=stderr, returncode=1
                    ),
                    subject_path=subject,
                    subject_digest=digest,
                    expected_count=1,
                    destination=root,
                    token=token,
                )
        message = str(raised.exception)
        self.assertNotIn(token, message)
        self.assertIn("***", message)
        self.assertLessEqual(
            len(message),
            len("pinned gh attestation download failed: ")
            + guard.VERIFIER_DIAGNOSTIC_LIMIT,
        )

    def test_nonzero_verifier_exit_preserves_fail_closed_none_with_sanitised_diagnostic(self) -> None:
        token = "github_pat_SECRET123"
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subject = root / "dispatch-subject.json"
            bundle = root / "bundle.json"
            subject.write_bytes(b"fixture")
            bundle.write_text("{}\n", encoding="utf-8")
            payload, diagnostic = guard.run_gh_verify_main(
                gh_binary=self._verify_gh(
                    root,
                    stdout=b"ignored",
                    stderr=b"policy rejected github_pat_SECRET123\n\xff",
                    returncode=1,
                ),
                subject_path=subject,
                bundle_path=bundle,
                source_sha="a" * 40,
                token=token,
            )
        self.assertIsNone(payload)
        self.assertIsNotNone(diagnostic)
        self.assertNotIn(token, diagnostic or "")
        self.assertIn("***", diagnostic or "")
        self.assertLessEqual(len(diagnostic or ""), guard.VERIFIER_DIAGNOSTIC_LIMIT)

    def test_successful_verifier_json_is_returned_without_diagnostic(self) -> None:
        expected = [{"verificationResult": {"fixture": True}}]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subject = root / "dispatch-subject.json"
            bundle = root / "bundle.json"
            subject.write_bytes(b"fixture")
            bundle.write_text("{}\n", encoding="utf-8")
            payload, diagnostic = guard.run_gh_verify_main(
                gh_binary=self._verify_gh(
                    root, stdout=json.dumps(expected).encode("utf-8")
                ),
                subject_path=subject,
                bundle_path=bundle,
                source_sha="a" * 40,
                token="unused",
            )
        self.assertEqual(payload, expected)
        self.assertIsNone(diagnostic)


if __name__ == "__main__":
    unittest.main()
